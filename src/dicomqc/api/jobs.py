"""Single-owner queue with isolated workers and durable, value-free run state."""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
import re
import shutil
import socket
import sqlite3
import subprocess
import sys
import threading
import time
import unicodedata
import uuid

from dicomqc.api.storage import identity, read_json, regular_file, validate_identity, write_json
from dicomqc.execution import validate_audit_inputs

ACTIVE = {"queued", "running"}
WORKER_EVENTS = {"synthetic demo", "generation", "discovery", "reading", "relationships", "reports"}
MAX_LOG_EVENTS = 32


class WorkspaceError(ValueError):
    """A path-free workspace diagnostic safe to display in the desktop app."""


def normalize_job_name(value: str) -> str:
    """Return a safe display name without changing the run's stable identity."""
    if not isinstance(value, str):
        raise ValueError("Run name must be text.")
    if any(unicodedata.category(character) == "Cc" for character in value):
        raise ValueError("Run name must not contain control characters.")
    value = value.strip()
    if not 1 <= len(value) <= 80:
        raise ValueError("Run name must contain between 1 and 80 characters.")
    return value


class Jobs:
    def __init__(self, root: Path):
        selected = root.expanduser().absolute()
        if selected.is_symlink():
            raise WorkspaceError("Workspace must not be a symbolic link.")
        self.root = selected.resolve()
        if self.root.exists():
            entries = {path.name for path in self.root.iterdir()}
            known = {"owner.lock", "runs.sqlite", "runs.sqlite-journal", "runs.sqlite-wal", "runs.sqlite-shm"}
            if entries and (not {"owner.lock", "runs.sqlite"} <= entries
                            or any(name not in known and not re.fullmatch(r"[a-f0-9]{32}", name)
                                   for name in entries)):
                raise WorkspaceError("The selected output folder contains files that do not belong to a dicomqc run workspace.")
        for name in ("owner.lock", "runs.sqlite", "runs.sqlite-journal", "runs.sqlite-wal", "runs.sqlite-shm"):
            regular_file(self.root / name, missing=True)
        if (self.root / "runs.sqlite").exists():
            existing = sqlite3.connect((self.root / "runs.sqlite").as_uri() + "?mode=ro", uri=True)
            try:
                if [row[1] for row in existing.execute("PRAGMA table_info(jobs)")] != ["id", "created", "value"]:
                    raise WorkspaceError("The selected output folder does not contain a valid dicomqc run database.")
            finally:
                existing.close()
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.root_identity = identity(self.root)
        self.closed = False
        # An advisory file lock survives crashes and excludes another supervisor.
        fd = os.open(self.root / "owner.lock", os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
        self.lock_file = os.fdopen(fd, "r+b", buffering=0)
        try:
            if os.name == "nt":
                import msvcrt
                if os.fstat(self.lock_file.fileno()).st_size == 0:
                    self.lock_file.write(b"0")
                self.lock_file.seek(0)
                msvcrt.locking(self.lock_file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.lock_file.close()
            raise WorkspaceError("This output folder is already open in another dicomqc process, or its filesystem does not support locking. Close the other app or choose a local output folder.") from None
        try:
            fd = os.open(self.root / "runs.sqlite", os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
            os.close(fd)
            self.db = sqlite3.connect(self.root / "runs.sqlite", check_same_thread=False)
            self.db.execute("CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, created REAL, value TEXT)")
            self.db.execute("CREATE TABLE IF NOT EXISTS run_directories (id TEXT PRIMARY KEY, value TEXT)")
        except Exception:
            if hasattr(self, "db"):
                self.db.close()
            self.lock_file.close()
            raise
        self.mutex = threading.RLock()
        self.handles: dict[str, dict] = {}
        self.stopping = threading.Event()
        self.process: subprocess.Popen | None = None
        self.current: str | None = None
        self.guard: socket.socket | None = None
        try:
            for job in self.list():
                if job["status"] in ACTIVE:
                    job.update(status="interrupted", message="The application stopped before this audit completed.")
                    self._event(job, "interrupted")
                    self._save(job)
        except Exception:
            self.db.close()
            self.lock_file.close()
            raise
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def _save(self, job):
        validate_identity(self.root_identity)
        self.db.execute("INSERT OR REPLACE INTO jobs VALUES (?, ?, ?)", (job["id"], job["created"], json.dumps(job)))
        self.db.commit()

    def list(self):
        with self.mutex:
            return [self._progress(json.loads(row[0])) for row in
                    self.db.execute("SELECT value FROM jobs ORDER BY created DESC, rowid DESC")]

    def get(self, identifier):
        with self.mutex:
            row = self.db.execute("SELECT value FROM jobs WHERE id = ?", (identifier,)).fetchone()
            if row is None:
                raise ValueError("Run not found.")
            return self._progress(json.loads(row[0]))

    def _progress(self, job):
        if "parameters" not in job:
            try:
                job["parameters"] = self._public_parameters(read_json(self.directory(job["id"]) / "request.json"))
            except (OSError, ValueError, KeyError, TypeError):
                pass  # Older or incomplete runs remain readable without provenance details.
        existing = {(event.get("at"), event.get("event")) for event in job.get("log", [])
                    if isinstance(event, dict)}
        for event in self._worker_events(job["id"]):
            if (event["at"], event["event"]) not in existing:
                job.setdefault("log", []).append(event)
        if "log" in job:
            job["log"] = sorted(job["log"], key=lambda value: value.get("at", 0))[-MAX_LOG_EVENTS:]
        if job["status"] == "running":
            try:
                job["progress"] = read_json(self.directory(job["id"]) / "progress.json")
            except (OSError, ValueError):
                pass  # Progress is advisory; it must never break cancellation.
        return job

    @staticmethod
    def _public_parameters(request):
        """Return useful run provenance without paths, handles, or DICOM values."""
        inputs = request.get("inputs", {})
        options = request.get("options", {})
        counts = {key: len(values) for key, values in inputs.items()
                  if key in {"paths", "source", "candidate", "manifest", "policy"}
                  and isinstance(values, list) and values}
        safe_options = {}
        for key in ("uid_checks", "vendor_summary", "multiqc", "threads"):
            value = options.get(key)
            if isinstance(value, bool) and key != "threads":
                safe_options[key] = value
            elif key == "threads" and isinstance(value, int) and not isinstance(value, bool):
                safe_options[key] = value
        parameters = {"input_counts": counts, "options": safe_options}
        files = request.get("example_files")
        if isinstance(files, int) and not isinstance(files, bool):
            parameters["example_files"] = files
        return parameters

    def _worker_events(self, identifier):
        try:
            values = read_json(self.directory(identifier) / "events.json")
            if not isinstance(values, list):
                return []
            events = []
            for value in values[-MAX_LOG_EVENTS:]:
                if (not isinstance(value, dict) or set(value) != {"at", "event"}
                        or isinstance(value["at"], bool) or not isinstance(value["at"], (int, float))
                        or not math.isfinite(value["at"]) or not 0 <= value["at"] <= time.time() + 86400
                        or value["event"] not in WORKER_EVENTS):
                    return []
                events.append({"at": float(value["at"]), "event": value["event"]})
            return events
        except (OSError, ValueError, TypeError):
            return []

    @staticmethod
    def _event(job, event):
        job.setdefault("log", []).append({"at": time.time(), "event": event})
        job["log"] = job["log"][-MAX_LOG_EVENTS:]

    def directory(self, identifier):
        validate_identity(self.root_identity)
        if not re.fullmatch(r"[a-f0-9]{32}", identifier):
            raise ValueError("Invalid run identifier.")
        directory = self.root / identifier
        if directory.resolve() != directory:
            raise ValueError("Run directory changed.")
        return directory

    def register(self, raw: str):
        validate_identity(self.root_identity)
        path = Path(raw).expanduser().resolve(strict=True)
        if not (path.is_file() or path.is_dir()):
            raise ValueError("Select a regular file or directory.")
        # Resolve alone does not unify Windows extended and ordinary path spellings.
        if (any(self.root.samefile(parent) for parent in (path, *path.parents))
                or any(path.samefile(parent) for parent in self.root.parents)):
            raise ValueError("Keep inputs separate from the run workspace.")
        identifier = uuid.uuid4().hex
        with self.mutex:
            self.handles[identifier] = identity(path)
        return {"id": identifier, "name": path.name, "kind": "directory" if path.is_dir() else "file"}

    def submit(self, request):
        with self.mutex:
            if self.stopping.is_set():
                raise ValueError("The API is shutting down.")
            resolved = {}
            for key, handles in request["inputs"].items():
                resolved[key] = []
                for handle in handles:
                    if handle not in self.handles:
                        raise ValueError("Select the input again; its handle is no longer available.")
                    value = self.handles[handle]
                    validate_identity(value)
                    resolved[key].append(value)
            validate_audit_inputs(request["mode"], {key: [Path(value["path"]) for value in values]
                                                    for key, values in resolved.items()})
            identifier = uuid.uuid4().hex
            directory = self.directory(identifier)
            directory.mkdir(mode=0o700)
            request = {**request, "inputs": resolved, "workspace": self.root_identity,
                       "directory": identity(directory)}
            write_json(directory / "request.json", request)
            job = {"id": identifier, "created": time.time(), "mode": request["mode"],
                   "example": request.get("example"), "name": None, "status": "queued", "audit_exit_code": None,
                   "summary": None, "artifacts": [], "message": None, "log": [],
                   "parameters": self._public_parameters(request)}
            self._event(job, "queued")
            self.db.execute("INSERT INTO run_directories VALUES (?, ?)",
                            (identifier, json.dumps(request["directory"])))
            self._save(job)
            return job

    def _loop(self):
        while not self.stopping.wait(0.1):
            try:
                self._tick()
            except (OSError, ValueError, sqlite3.Error, KeyError, TypeError):
                # A replaced workspace is no longer ours to write into.
                self.stopping.set()
                self._stop_worker()

    def _tick(self):
        with self.mutex:
            validate_identity(self.root_identity)
            if self.process is not None:
                code = self.process.poll()
                if code is None:
                    return
                job = self.get(self.current)
                completion = self.directory(self.current) / "completion.json"
                if job["status"] == "running":
                    try:
                        if code != 0:
                            raise ValueError("Worker failed")
                        result = read_json(completion)
                        if (result.get("audit_exit_code") not in (0, 1, 2)
                                or not isinstance(result.get("summary"), dict)
                                or not isinstance(result.get("artifacts"), list)
                                or not all(isinstance(p, str) for p in result["artifacts"])):
                            raise ValueError("Invalid completion")
                        job.update({key: result[key] for key in ("audit_exit_code", "summary", "artifacts")}, status="completed")
                        if result.get("policy"):
                            job["policy"] = result["policy"]
                        self._event(job, "completed")
                    except (OSError, ValueError, TypeError, AttributeError):
                        job.update(status="failed", message="Could not complete the audit. Check the selected inputs and workspace.")
                        self._event(job, "failed")
                    self._save(job)
                if self.guard:
                    self.guard.close()
                self.process, self.current, self.guard = None, None, None
            queued = [job for job in reversed(self.list()) if job["status"] == "queued"]
            if not queued:
                return
            job = queued[0]
            process = connection = guard = None
            # A separate sentinel kills a worker if its supervisor disappears.
            command = ([sys.executable, "--worker"] if getattr(sys, "frozen", False)
                       else [sys.executable, "-m", "dicomqc.api.runner"])
            try:
                directory = self.directory(job["id"])
                request = read_json(directory / "request.json")
                validate_identity(request["directory"])
                for values in request["inputs"].values():
                    for value in values:
                        validate_identity(value)
                guard = socket.socket()
                guard.bind(("127.0.0.1", 0))
                guard.listen(1)
                guard.settimeout(10)
                secret = uuid.uuid4().hex
                write_json(directory / "guard.json", {"port": guard.getsockname()[1], "secret": secret})
                environment = {key: value for key, value in os.environ.items()
                               if key not in {"DICOMQC_API_TOKEN", "DICOMQC_LOCAL_TOKEN"}}
                process = subprocess.Popen([*command, str(directory)], stdin=subprocess.DEVNULL,
                                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                           env=environment,
                                           creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
                connection, _ = guard.accept()
                connection.settimeout(5)
                received = b""
                deadline = time.monotonic() + 5
                while len(received) < len(secret):
                    connection.settimeout(max(0.001, deadline - time.monotonic()))
                    chunk = connection.recv(len(secret) - len(received))
                    if not chunk or time.monotonic() > deadline:
                        break
                    received += chunk
                if received != secret.encode("ascii"):
                    raise OSError("Invalid worker handshake")
                connection.settimeout(None)
            except (OSError, ValueError, KeyError, TypeError):
                if connection:
                    connection.close()
                if process is not None and process.poll() is None:
                    process.kill()
                    process.wait()
                job.update(status="failed", message="Could not start the audit worker.")
                self._event(job, "failed")
                self._save(job)
                if guard:
                    guard.close()
                return
            guard.close()
            self.guard, self.process, self.current = connection, process, job["id"]
            job["status"] = "running"
            self._event(job, "started")
            self._save(job)

    def cancel(self, identifier):
        with self.mutex:
            job = self.get(identifier)
            if job["status"] in ACTIVE:
                job.update(status="cancelled", message="Audit cancelled; no complete report was published.", artifacts=[])
                self._event(job, "cancelled")
                self._save(job)
                if self.current == identifier and self.process:
                    self._stop_worker()
            return job

    def rename(self, identifier, name):
        with self.mutex:
            job = self.get(identifier)
            job["name"] = normalize_job_name(name)
            self._save(job)
            return job

    def artifact(self, identifier, index):
        job = self.get(identifier)
        if job["status"] != "completed" or index < 0 or index >= len(job["artifacts"]):
            raise ValueError("Report not available.")
        root = self.directory(identifier) / "reports"
        path = root / job["artifacts"][index]
        if path.resolve(strict=True) != path or root not in path.parents or not path.is_file():
            raise ValueError("Report path changed.")
        regular_file(path)
        return path

    def delete(self, identifier):
        with self.mutex:
            directory = self.directory(identifier)
            job = self.get(identifier)
            if job["status"] not in {"completed", "failed", "cancelled", "interrupted"}:
                raise ValueError("Only inactive runs can be deleted.")
            if self.current == identifier:
                if self.process is not None and self.process.poll() is None:
                    raise ValueError("The audit worker has not stopped yet.")
                if self.guard:
                    self.guard.close()
                self.process, self.current, self.guard = None, None, None
            if directory.exists():
                row = self.db.execute("SELECT value FROM run_directories WHERE id = ?", (identifier,)).fetchone()
                # Upgrade older runs before removing anything; a partial rmtree
                # may remove the request file, but the database survives retries.
                expected = json.loads(row[0]) if row else read_json(directory / "request.json").get("directory")
                if not expected or expected.get("path") != str(directory) or not directory.is_dir():
                    raise ValueError("Run directory ownership is unavailable.")
                validate_identity(expected)
                self.db.execute("INSERT OR REPLACE INTO run_directories VALUES (?, ?)",
                                (identifier, json.dumps(expected)))
                self.db.commit()
                validate_identity(self.root_identity)
                if shutil.rmtree.avoids_symlink_attacks:
                    fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
                    try:
                        info = os.fstat(fd)
                        if (info.st_dev, info.st_ino) != (self.root_identity["device"], self.root_identity["inode"]):
                            raise ValueError("Workspace changed.")
                        shutil.rmtree(identifier, dir_fd=fd)
                    finally:
                        os.close(fd)
                else:
                    # Windows rmtree removes directory links/junctions themselves,
                    # not their targets. Top-level redirects were rejected above.
                    shutil.rmtree(directory)
            validate_identity(self.root_identity)
            with self.db:
                self.db.execute("DELETE FROM run_directories WHERE id = ?", (identifier,))
                self.db.execute("DELETE FROM jobs WHERE id = ?", (identifier,))
            return {"id": identifier, "status": "deleted"}

    def review(self, identifier):
        if self.get(identifier)["status"] != "completed":
            raise ValueError("Audit results are not available.")
        path = self.directory(identifier) / "reports/review.json"
        if path.resolve(strict=True) != path:
            raise ValueError("Report path changed.")
        return read_json(path)

    def close(self):
        if self.closed:
            return
        self.stopping.set()
        self.thread.join()
        try:
            with self.mutex:
                self._stop_worker()
                for job in self.list():
                    if job["status"] in ACTIVE:
                        job.update(status="cancelled", message="Application closed.", artifacts=[])
                        self._event(job, "cancelled")
                        self._save(job)
        except (OSError, ValueError, sqlite3.Error):
            pass  # Do not write through a replaced workspace during cleanup.
        finally:
            self.db.close()
            self.lock_file.close()
            self.closed = True

    def _stop_worker(self):
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
        if self.guard:
            self.guard.close()
            self.guard = None
