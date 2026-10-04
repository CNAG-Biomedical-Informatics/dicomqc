"""Small, private, atomic files for the local worker protocol."""

import json
import os
from pathlib import Path
import stat
import tempfile
import time


def write_json(path: Path, value: object) -> None:
    fd, name = tempfile.mkstemp(prefix=".pending-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle)
            handle.flush()
            os.fsync(handle.fileno())
        # Windows readers can briefly deny replacement of progress/event files.
        for attempt in range(20):
            try:
                os.replace(name, path)
                break
            except PermissionError as exc:
                if getattr(exc, "winerror", None) not in {5, 32, 33} or attempt == 19:
                    raise
                time.sleep(0.025)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def read_json(path: Path) -> dict:
    regular_file(path)
    return json.loads(path.read_text(encoding="utf-8"))


def regular_file(path: Path, *, missing: bool = False) -> None:
    """Reject redirected or shared state files before opening them."""
    try:
        info = path.lstat()
    except FileNotFoundError:
        if missing:
            return
        raise
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise ValueError("Workspace files must be private regular files.")


def identity(path: Path) -> dict:
    info = path.stat()
    return {"path": str(path), "device": info.st_dev, "inode": info.st_ino,
            "size": info.st_size if stat.S_ISREG(info.st_mode) else None,
            "modified": info.st_mtime_ns if stat.S_ISREG(info.st_mode) else None}


def validate_identity(value: dict) -> Path:
    path = Path(value["path"])
    if path.resolve(strict=True) != path or identity(path) != value:
        raise ValueError("A selected input changed or moved; select it again.")
    return path
