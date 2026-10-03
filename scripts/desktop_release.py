"""Select desktop targets and inspect the engine inside finished installers."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

from build_desktop_engine import ROOT, check_versions, validate_engine


PLATFORMS = [
    {"platform": "macos-x64", "os": "macos-15-intel", "bundle": "dmg"},
    {"platform": "macos-arm64", "os": "macos-15", "bundle": "dmg"},
    {"platform": "windows-x64", "os": "windows-2022", "bundle": "nsis"},
    {"platform": "linux-x64", "os": "ubuntu-22.04", "bundle": "appimage"},
    {"platform": "linux-arm64", "os": "ubuntu-24.04-arm", "bundle": "appimage"},
]


def select_platforms(name: str) -> list[dict[str, str]]:
    selected = [row for row in PLATFORMS if name in ("all", row["platform"])]
    if not selected:
        raise ValueError(f"Unknown platform: {name}")
    return selected


def output(name: str, value: str) -> None:
    print(f"{name}={value}")
    if os.environ.get("GITHUB_OUTPUT"):
        with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as handle:
            handle.write(f"{name}={value}\n")


def verify_version() -> str:
    version = check_versions()
    if os.environ.get("GITHUB_REF_TYPE") == "tag":
        tag = os.environ["GITHUB_REF_NAME"]
        if not re.fullmatch(r"v\d+\.\d+\.\d+", tag) or tag != f"v{version}":
            raise ValueError("Stable tag must match the package version: vX.Y.Z")
        ref = f"refs/tags/{tag}"
        def git(*args: str) -> str:
            return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()
        if git("cat-file", "-t", ref) != "tag":
            raise ValueError("Release tag must be annotated")
        if git("rev-parse", f"{ref}^{{commit}}") != git("rev-parse", "HEAD"):
            raise ValueError("Tag does not match the checked-out commit")
    return version


def find_engine(directory: Path) -> Path:
    executable = "dicomqc-api.exe" if sys.platform == "win32" else "dicomqc-api"
    engines = [path.parent for path in directory.rglob(executable)
               if path.is_file() and (path.parent / "_internal").is_dir()]
    if len(engines) != 1:
        raise ValueError(f"Expected one packaged engine, found {len(engines)}")
    validate_engine(engines[0])
    return engines[0].resolve()


def inspect(directory: Path) -> None:
    engine = find_engine(directory)
    env = {**os.environ, "DICOMQC_DESKTOP_ENGINE": str(engine)}
    # Reuse relocation, authentication, demo-worker and shutdown tests against
    # the installed copy, not the pre-bundle staging directory.
    subprocess.run([
        sys.executable, "-m", "pytest", "tests/test_desktop_build.py", "-k", "frozen",
        "--no-cov", "--junitxml=build/installed-engine-tests.xml",
    ], cwd=ROOT, env=env, check=True)


def collect(platform: str, root: Path = ROOT) -> Path:
    row = select_platforms(platform)
    if len(row) != 1:
        raise ValueError("Collect requires one platform")
    bundle = row[0]["bundle"]
    pattern = {"dmg": "*.dmg", "nsis": "*-setup.exe", "appimage": "*.AppImage"}[bundle]
    files = list((root / "app/src-tauri/target/release/bundle" / bundle).glob(pattern))
    if len(files) != 1:
        raise ValueError(f"Expected one installer, found {len(files)}")
    version = check_versions(root)
    suffix = "-setup.exe" if bundle == "nsis" else files[0].suffix
    destination = root / "build/installers" / f"dicomqc-{version}-{platform}{suffix}"
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(files[0], destination)
    digest = hashlib.sha256()
    with destination.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    destination.with_name(destination.name + ".sha256").write_text(
        f"{digest.hexdigest()}  {destination.name}\n", encoding="ascii")
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("matrix", "version", "inspect", "collect"))
    parser.add_argument("directory", nargs="?", type=Path)
    args = parser.parse_args()
    if args.command == "matrix":
        output("matrix", json.dumps(select_platforms(os.environ.get("PLATFORM", "all"))))
    elif args.command == "version":
        output("version", verify_version())
    elif args.command == "inspect":
        if args.directory is None:
            parser.error("inspect requires an extracted or installed package directory")
        inspect(args.directory)
    else:
        print(collect(os.environ["PLATFORM"]))


if __name__ == "__main__":
    main()
