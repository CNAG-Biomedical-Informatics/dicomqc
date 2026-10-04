"""Build the native onedir API engine; requires Python 3.11+ and desktop-build."""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
import shutil
import subprocess
import sys

import yaml


ROOT = Path(__file__).resolve().parents[1]


def check_versions(root: Path = ROOT) -> str:
    import tomllib

    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    package = json.loads((root / "app/package.json").read_text(encoding="utf-8"))
    tauri = json.loads((root / "app/src-tauri/tauri.conf.json").read_text(encoding="utf-8"))
    cargo = tomllib.loads((root / "app/src-tauri/Cargo.toml").read_text(encoding="utf-8"))
    cargo_lock = tomllib.loads((root / "app/src-tauri/Cargo.lock").read_text(encoding="utf-8"))
    citation = yaml.safe_load((root / "CITATION.cff").read_text(encoding="utf-8"))
    module = ast.parse((root / "src/dicomqc/__init__.py").read_text(encoding="utf-8"))
    runtime_version = next(
        (ast.literal_eval(node.value) for node in module.body if isinstance(node, ast.Assign)
         and any(isinstance(target, ast.Name) and target.id == "__version__" for target in node.targets)),
        None,
    )
    versions = {
        "Python package": project["project"]["version"],
        "Python runtime": runtime_version,
        "app/package.json": package["version"],
        "Tauri config": tauri.get("version"),
        "Cargo package": cargo["package"]["version"],
        "Cargo lockfile": next(
            (package.get("version") for package in cargo_lock.get("package", [])
             if package.get("name") == cargo["package"]["name"]),
            None,
        ),
        "CITATION.cff": str(citation.get("version")),
    }
    lock_path = root / "app/package-lock.json"
    if lock_path.exists():
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
        versions["npm lockfile"] = lock.get("version")
        versions["npm root package"] = lock.get("packages", {}).get("", {}).get("version")
    expected = versions["Python package"]
    if not isinstance(expected, str) or not expected or any(value != expected for value in versions.values()):
        raise ValueError("Desktop versions disagree: " + ", ".join(f"{key}={value!r}" for key, value in versions.items()))
    return expected


def pyinstaller_command(root: Path, work: Path) -> list[str]:
    return [
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir",
        "--name", "dicomqc-api", "--contents-directory", "_internal", "--noupx",
        "--distpath", str(work / "dist"), "--workpath", str(work / "work"),
        "--specpath", str(work), "--paths", str(root / "src"),
        "--collect-all", "dicomqc", "--collect-all", "pydicom",
        "--collect-all", "uvicorn", "--collect-all", "fastapi",
        "--collect-all", "pydantic", "--collect-all", "pydantic_core",
        "--copy-metadata", "dicomqc",
        str(root / "scripts/desktop_engine_entry.py"),
    ]


def validate_engine(directory: Path) -> Path:
    executable = directory / ("dicomqc-api.exe" if sys.platform == "win32" else "dicomqc-api")
    if not executable.is_file() or not (directory / "_internal").is_dir():
        raise ValueError(f"Incomplete onedir engine: {directory}")
    return executable


def build_engine(root: Path = ROOT) -> Path:
    check_versions(root)
    work = root / "build/desktop-engine"
    work.mkdir(parents=True, exist_ok=True)
    subprocess.run(pyinstaller_command(root, work), cwd=root, check=True)
    built = work / "dist/dicomqc-api"
    validate_engine(built)
    destination = root / "app/src-tauri/engine"
    # Do not merge builds: old native libraries can mask missing dependencies.
    if destination.is_symlink():
        raise ValueError(f"Refusing to replace a symlink: {destination}")
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(built, destination, symlinks=True)
    return validate_engine(destination)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-versions", action="store_true", help="Check versions without building.")
    args = parser.parse_args(argv)
    if sys.version_info < (3, 11):
        parser.error("Desktop builds require Python 3.11 or newer (CI uses 3.12).")
    try:
        if args.check_versions:
            print(f"Desktop versions agree: {check_versions()}")
        else:
            print(f"Desktop engine: {build_engine()}")
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as exc:
        print(f"Desktop build failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
