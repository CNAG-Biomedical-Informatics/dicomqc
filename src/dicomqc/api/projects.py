"""Portable project snapshots; original DICOM inputs are never copied."""

import copy
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import shutil
import stat
import tempfile
import zipfile

from dicomqc.api.jobs import ACTIVE, Jobs
from dicomqc.api.storage import identity, regular_file

MAX_METADATA = 16 * 1024 * 1024
MAX_EXPANDED = 20 * 1024 ** 3


def _validate_project(project):
    from dicomqc.api.app import Options
    if (not isinstance(project, dict) or project.get("format") != "dicomqc-project"
            or set(project) - {"format", "version", "mode", "inputs", "options", "output", "saved_runs"}
            or project.get("version") not in (1, 2) or project.get("mode") not in {"scan", "compare"}
            or not isinstance(project.get("inputs"), dict)
            or set(project["inputs"]) - {"paths", "source", "candidate", "manifest", "policy"}):
        raise ValueError("Invalid project settings.")
    options = dict(project.get("options", {}))
    # A project saved on a larger machine can be opened on a smaller one.
    from dicomqc.parallel import MAX_THREADS
    if type(options.get("threads")) is int and options["threads"] > MAX_THREADS:
        options["threads"] = MAX_THREADS
    Options.model_validate(options)
    project["options"] = options
    for key, paths in project["inputs"].items():
        if (not isinstance(paths, list) or len(paths) > (1000 if key == "paths" else 1)
                or any(not isinstance(p, str) or not p or "\0" in p for p in paths)):
            raise ValueError("Invalid project input references.")
        if (project["version"] == 1 or key not in {"policy", "manifest"}) and any(not (Path(p).is_absolute() or PureWindowsPath(p).is_absolute()) for p in paths):
            raise ValueError("External input references must be absolute paths.")


def save_project(jobs: Jobs, target: Path, project: dict) -> None:
    if target.suffix != ".dicomqc" or not target.is_absolute() or target.is_symlink():
        raise ValueError("Select a local .dicomqc project file.")
    if target.resolve().is_relative_to(jobs.root):
        raise ValueError("Save the project outside its internal working storage.")
    project = copy.deepcopy(project)
    _validate_project(project)
    for key, paths in project["inputs"].items():
        for raw in paths:
            source = Path(raw).resolve()
            if target.resolve() == source or (key in {"paths", "source", "candidate"} and target.resolve().is_relative_to(source)):
                raise ValueError("Keep the project file separate from its input datasets.")
    with jobs.mutex:
        runs = jobs.list()
        if jobs.current is not None or any(run["status"] in ACTIVE for run in runs):
            raise ValueError("Finish or cancel active audits before saving the project.")
        project.update(format="dicomqc-project", version=2)
        project.pop("saved_runs", None)
        project.pop("output", None)
        attachments = []
        for key in ("policy", "manifest"):
            paths = project["inputs"].get(key, [])
            copied = []
            for index, raw in enumerate(paths):
                source = Path(raw)
                regular_file(source)
                name = f"inputs/{key}-{index}{'.yaml' if key == 'policy' else '.csv'}"
                attachments.append((source, name))
                copied.append(name)
            project["inputs"][key] = copied
        encoded_project, encoded_runs = json.dumps(project).encode(), json.dumps(runs).encode()
        if max(len(encoded_project), len(encoded_runs)) > MAX_METADATA:
            raise ValueError("Project metadata exceeds supported limits.")
        fd, pending = tempfile.mkstemp(dir=target.parent, prefix=".dicomqc-")
        try:
            with os.fdopen(fd, "w+b") as stream:
                with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                    archive.writestr("project.json", encoded_project)
                    archive.writestr("runs.json", encoded_runs)
                    for source, name in attachments:
                        archive.write(source, name)
                    for run in runs:
                        for index, name in enumerate(run["artifacts"]):
                            source = jobs.artifact(run["id"], index)
                            archive.write(source, f"runs/{run['id']}/reports/{name}")
                        if run["status"] == "completed" and "review.json" not in run["artifacts"]:
                            review = jobs.directory(run["id"]) / "reports/review.json"
                            regular_file(review)
                            archive.write(review, f"runs/{run['id']}/reports/review.json")
                    if len(archive.filelist) > 100_000 or sum(entry.file_size for entry in archive.filelist) > MAX_EXPANDED:
                        raise ValueError("Project archive exceeds supported limits.")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(pending, target)
        finally:
            if os.path.exists(pending):
                os.unlink(pending)


def open_project(source: Path, storage: Path) -> dict:
    """Extract only validated members into a new private session directory."""
    regular_file(source)
    session = Path(tempfile.mkdtemp(prefix="project-", dir=storage))
    try:
        with zipfile.ZipFile(source) as archive:
            entries = archive.infolist()
            names = [entry.filename for entry in entries]
            if len(names) != len(set(names)) or len(names) > 100_000 or sum(e.file_size for e in entries) > MAX_EXPANDED:
                raise ValueError("Project archive exceeds supported limits or contains duplicate files.")
            for entry in entries:
                name = entry.filename
                path = PurePosixPath(name)
                if (path.is_absolute() or ".." in path.parts or "\\" in name
                        or str(path) != name or stat.S_ISLNK(entry.external_attr >> 16)
                        or not (name in {"project.json", "runs.json"}
                                or re.fullmatch(r"inputs/(policy|manifest)-[0-9]+\.[A-Za-z0-9]+", name)
                                or re.fullmatch(r"runs/[a-f0-9]{32}/reports/.+", name))):
                    raise ValueError("Invalid project archive member.")
            def metadata(name):
                if archive.getinfo(name).file_size > MAX_METADATA:
                    raise ValueError("Project metadata exceeds supported limits.")
                return json.loads(archive.read(name))
            project, runs = metadata("project.json"), metadata("runs.json")
            _validate_project(project)
            if (project.get("format") != "dicomqc-project" or project.get("version") != 2
                    or project.get("mode") not in {"scan", "compare"} or not isinstance(runs, list)):
                raise ValueError("Unsupported project format.")
            seen = set()
            for run in runs:
                identifier = run["id"]
                if (not re.fullmatch(r"[a-f0-9]{32}", identifier) or identifier in seen
                        or run["status"] not in {"completed", "failed", "cancelled", "interrupted"}):
                    raise ValueError("Invalid saved run.")
                seen.add(identifier)
                for artifact in run["artifacts"]:
                    if (not isinstance(artifact, str) or ".." in PurePosixPath(artifact).parts
                            or PurePosixPath(artifact).is_absolute()
                            or f"runs/{identifier}/reports/{artifact}" not in names):
                        raise ValueError("A saved report is missing.")
                if run["status"] == "completed" and f"runs/{identifier}/reports/review.json" not in names:
                    raise ValueError("Saved findings are missing.")
            for entry in entries:
                if entry.filename in {"project.json", "runs.json"}:
                    continue
                target = session / entry.filename
                target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                with archive.open(entry) as incoming, target.open("xb") as outgoing:
                    shutil.copyfileobj(incoming, outgoing)
                target.chmod(0o600)
            for key in ("policy", "manifest"):
                paths = project["inputs"].get(key, [])
                if any(not isinstance(p, str) or not p.startswith(f"inputs/{key}-") or p not in names for p in paths):
                    raise ValueError("Invalid project input attachment.")
                project["inputs"][key] = [str(session / p) for p in paths]
        root = session / "workspace"
        root.mkdir(mode=0o700)
        with_snapshot = Jobs(root)
        try:
            with with_snapshot.mutex:
                for run in reversed(runs):
                    directory = root / run["id"]
                    stored = session / "runs" / run["id"]
                    if stored.exists():
                        stored.rename(directory)
                    else:
                        directory.mkdir(mode=0o700)
                    with_snapshot.db.execute("INSERT INTO run_directories VALUES (?, ?)",
                                             (run["id"], json.dumps(identity(directory))))
                    with_snapshot._save(run)
        finally:
            with_snapshot.close()
        project.update(version=1, output=str(root), saved_runs=runs)
        return project
    except Exception as exc:
        shutil.rmtree(session)
        if isinstance(exc, (ValueError, KeyError, TypeError, zipfile.BadZipFile)):
            raise ValueError("The project archive is invalid, incomplete, or unsupported.") from None
        raise
