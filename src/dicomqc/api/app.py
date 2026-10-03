"""Versioned local HTTP interface, authenticated including its OpenAPI schema."""

from contextlib import asynccontextmanager
import hmac
from pathlib import Path
import re
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from dicomqc import __version__
from dicomqc.api.jobs import Jobs, WorkspaceError, normalize_job_name
from dicomqc.fixtures import LARGE_DEMO_FILES, LARGE_DEMO_STEP, MAX_LARGE_DEMO_FILES, MIN_LARGE_DEMO_FILES
from dicomqc.parallel import DEFAULT_THREADS, MAX_THREADS
from dicomqc.rules.policy import parse_policy


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Inputs(StrictModel):
    paths: list[str] = Field(default_factory=list, max_length=1000)
    source: list[str] = Field(default_factory=list, max_length=1)
    candidate: list[str] = Field(default_factory=list, max_length=1)
    manifest: list[str] = Field(default_factory=list, max_length=1)
    policy: list[str] = Field(default_factory=list, max_length=1)


class Options(StrictModel):
    uid_checks: bool = False
    vendor_summary: bool = False
    multiqc: bool = False
    threads: int = Field(default=DEFAULT_THREADS, ge=1, le=MAX_THREADS)


class JobRequest(StrictModel):
    mode: Literal["scan", "compare", "demo"]
    inputs: Inputs = Field(default_factory=Inputs)
    options: Options = Field(default_factory=Options)
    example: Literal["scan", "compare", "policy", "uid", "vendor", "large"] = "scan"
    example_files: int | None = Field(
        default=None, ge=MIN_LARGE_DEMO_FILES, le=MAX_LARGE_DEMO_FILES,
        multiple_of=LARGE_DEMO_STEP,
    )

    @model_validator(mode="after")
    def validate_mode(self):
        values = self.inputs
        if self.mode == "scan" and (not values.paths or values.source or values.candidate or values.manifest):
            raise ValueError("Select scan inputs only.")
        if self.mode == "compare" and (values.paths or not all((values.source, values.candidate, values.manifest))
                                       or any((self.options.uid_checks, self.options.vendor_summary, self.options.multiqc))):
            raise ValueError("Comparison needs source, candidate and manifest; scan-only options are unavailable.")
        if self.mode == "demo" and (any(self.inputs.model_dump().values())
                                    or self.options.uid_checks or self.options.vendor_summary):
            raise ValueError("Synthetic examples do not accept input references or scan-only checks.")
        if self.example_files is not None and (self.mode != "demo" or self.example != "large"):
            raise ValueError("A synthetic cohort size is available only for the large example.")
        return self


class Registration(StrictModel):
    path: str = Field(min_length=1, max_length=32768)


class JobRename(StrictModel):
    name: str

    @field_validator("name")
    @classmethod
    def validate_name(cls, value):
        return normalize_job_name(value)


class PolicyText(StrictModel):
    text: str = Field(min_length=1, max_length=65536)


class ProjectSave(StrictModel):
    path: str
    project: dict


class ProjectOpen(StrictModel):
    path: str
    storage: str


def create_app(root: Path, token: str, local_token: str, shutdown=None) -> FastAPI:
    if (min(len(token), len(local_token)) < 32 or token == local_token
            or not all(33 <= ord(c) <= 126 for c in token + local_token)):
        raise ValueError("Provide two distinct private tokens of at least 32 characters.")

    @asynccontextmanager
    async def lifespan(app):
        try:
            app.state.jobs = Jobs(root)
        except WorkspaceError as exc:
            app.state.startup_error = str(exc)
            raise
        except OSError:
            app.state.startup_error = "Cannot access the output folder. Check permissions or choose a writable local folder."
            raise
        try:
            yield
        finally:
            app.state.jobs.close()

    app = FastAPI(title="dicomqc local API", version=__version__, lifespan=lifespan,
                  docs_url=None, redoc_url=None, openapi_url="/api/v1/openapi.json")

    @app.middleware("http")
    async def authorize(request: Request, call_next):
        host = request.headers.get("host", "")
        if not re.fullmatch(r"(?:127\.0\.0\.1|localhost)(?::[0-9]+)?", host):
            return JSONResponse({"detail": "Invalid host."}, status_code=400)
        # Tauri calls through Rust; no cross-origin browser access is needed.
        if request.headers.get("origin") is not None:
            return JSONResponse({"detail": "Browser origins are not allowed."}, status_code=403)
        if not hmac.compare_digest(request.headers.get("authorization", "").encode(), ("Bearer " + token).encode()):
            return JSONResponse({"detail": "Authentication required."}, status_code=401)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    def privileged(request):
        if not hmac.compare_digest(request.headers.get("x-dicomqc-local", "").encode(), local_token.encode()):
            raise HTTPException(403, "Local authorization required.")

    @app.exception_handler(ValueError)
    async def invalid(request, exc):
        return JSONResponse({"detail": "Invalid request or changed input. Select inputs again and check run status."}, status_code=400)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        # Pydantic's default response includes user-supplied paths and values.
        return JSONResponse({"detail": "Invalid request fields or options."}, status_code=422)

    @app.exception_handler(OSError)
    async def filesystem_error(request, exc):
        return JSONResponse({"detail": "Cannot access the selected input or workspace."}, status_code=400)

    @app.get("/api/v1/health")
    def health():
        return {"status": "ready", "version": __version__, "api_version": 1}

    @app.get("/api/v1/capabilities")
    def capabilities():
        return {"modes": ["scan", "compare", "demo"], "examples": ["scan", "compare", "policy", "uid", "vendor", "large"],
                "scan_options": ["policy", "uid_checks", "vendor_summary", "multiqc", "threads"],
                "compare_options": ["policy", "threads"], "default_threads": DEFAULT_THREADS,
                "max_threads": MAX_THREADS, "max_concurrent_jobs": 1,
                "large_demo": {"default_files": LARGE_DEMO_FILES, "min_files": MIN_LARGE_DEMO_FILES,
                               "max_files": MAX_LARGE_DEMO_FILES, "step_files": LARGE_DEMO_STEP}}

    @app.post("/api/v1/inputs/local")
    def register(value: Registration, request: Request):
        privileged(request)
        return app.state.jobs.register(value.path)

    @app.post("/api/v1/projects/save/local")
    def save_project(value: ProjectSave, request: Request):
        privileged(request)
        from dicomqc.api.projects import save_project
        save_project(app.state.jobs, Path(value.path), value.project)
        return {"saved": True}

    @app.post("/api/v1/projects/open/local")
    def open_project(value: ProjectOpen, request: Request):
        privileged(request)
        from dicomqc.api.projects import open_project
        return open_project(Path(value.path), Path(value.storage))

    @app.post("/api/v1/jobs", status_code=202)
    def submit(value: JobRequest):
        payload = value.model_dump()
        payload["inputs"] = {key: values for key, values in payload["inputs"].items() if values}
        if payload["mode"] == "demo" and payload["example"] == "large" and payload["example_files"] is None:
            payload["example_files"] = LARGE_DEMO_FILES
        return app.state.jobs.submit(payload)

    @app.post("/api/v1/policies/validate")
    def validate_policy(value: PolicyText):
        try:
            policy = parse_policy(value.text.encode("utf-8"))
        except ValueError as exc:
            # Policy parser messages are intentionally value-free and useful to editors.
            raise HTTPException(400, str(exc)) from None
        return {"id": policy.id, "sha256": policy.sha256, "rules": len(policy.rules)}

    @app.get("/api/v1/jobs")
    def jobs():
        return app.state.jobs.list()

    @app.get("/api/v1/jobs/{identifier}")
    def job(identifier: str):
        return app.state.jobs.get(identifier)

    @app.patch("/api/v1/jobs/{identifier}")
    def rename(identifier: str, value: JobRename):
        return app.state.jobs.rename(identifier, value.name)

    @app.post("/api/v1/jobs/{identifier}/cancel")
    def cancel(identifier: str):
        return app.state.jobs.cancel(identifier)

    @app.delete("/api/v1/jobs/{identifier}")
    def delete(identifier: str, request: Request):
        privileged(request)
        return app.state.jobs.delete(identifier)

    @app.get("/api/v1/jobs/{identifier}/results")
    def results(identifier: str, offset: int = 0, limit: int = 100):
        if offset < 0 or not 1 <= limit <= 500:
            raise HTTPException(400, "Invalid page bounds.")
        value = app.state.jobs.review(identifier)
        findings = value.pop("findings")
        return {**value, "findings": findings[offset:offset + limit], "total_findings": len(findings)}

    @app.get("/api/v1/jobs/{identifier}/artifacts/{index}")
    def artifact(identifier: str, index: int):
        path = app.state.jobs.artifact(identifier, index)
        return FileResponse(path, filename=path.name)

    @app.post("/api/v1/shutdown")
    def stop(request: Request):
        privileged(request)
        if shutdown:
            shutdown()
        return {"status": "stopping"}

    return app
