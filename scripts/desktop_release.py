"""Select desktop targets and inspect the engine inside finished installers."""

from __future__ import annotations

import argparse
from datetime import date
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
        verify_release_metadata(version)
    return version


def verify_release_metadata(version: str, root: Path = ROOT) -> None:
    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    match = re.search(
        rf"^## \[{re.escape(version)}\] - (\d{{4}}-\d{{2}}-\d{{2}})$",
        changelog,
        flags=re.MULTILINE,
    )
    if match is None:
        raise ValueError(f"CHANGELOG.md must contain a dated {version} release section")
    try:
        date.fromisoformat(match.group(1))
    except ValueError as exc:
        raise ValueError(f"CHANGELOG.md has an invalid release date for {version}") from exc


def binary_architectures(path: Path) -> set[str]:
    data = path.read_bytes()
    if len(data) < 64:
        raise ValueError(f"Executable is too small to identify: {path}")

    if data[:4] == b"\x7fELF":
        if data[4] != 2 or data[5] not in (1, 2):
            raise ValueError("Desktop Linux executables must be 64-bit ELF files")
        byteorder = "little" if data[5] == 1 else "big"
        machine = int.from_bytes(data[18:20], byteorder)
        return {62: {"x64"}, 183: {"arm64"}}.get(machine, set())

    if data[:2] == b"MZ":
        offset = int.from_bytes(data[0x3C:0x40], "little")
        if data[offset:offset + 4] != b"PE\0\0":
            raise ValueError("Invalid PE executable")
        machine = int.from_bytes(data[offset + 4:offset + 6], "little")
        return {0x8664: {"x64"}, 0xAA64: {"arm64"}}.get(machine, set())

    thin = {
        b"\xcf\xfa\xed\xfe": "little",
        b"\xfe\xed\xfa\xcf": "big",
    }
    if data[:4] in thin:
        cpu = int.from_bytes(data[4:8], thin[data[:4]])
        return {0x01000007: {"x64"}, 0x0100000C: {"arm64"}}.get(cpu, set())

    fat = {
        b"\xca\xfe\xba\xbe": ("big", 20),
        b"\xbe\xba\xfe\xca": ("little", 20),
        b"\xca\xfe\xba\xbf": ("big", 32),
        b"\xbf\xba\xfe\xca": ("little", 32),
    }
    if data[:4] in fat:
        byteorder, entry_size = fat[data[:4]]
        count = int.from_bytes(data[4:8], byteorder)
        if count == 0 or count > 32 or len(data) < 8 + count * entry_size:
            raise ValueError("Invalid universal Mach-O executable")
        cpus = {
            int.from_bytes(data[8 + index * entry_size:12 + index * entry_size], byteorder)
            for index in range(count)
        }
        return {
            architecture
            for cpu, architecture in ((0x01000007, "x64"), (0x0100000C, "arm64"))
            if cpu in cpus
        }

    raise ValueError(f"Unsupported executable format: {path}")


def verify_architecture(path: Path, platform: str) -> None:
    selected = select_platforms(platform)
    if len(selected) != 1:
        raise ValueError("Architecture verification requires one platform")
    expected = platform.rsplit("-", 1)[1]
    architectures = binary_architectures(path)
    if architectures != {expected}:
        found = ", ".join(sorted(architectures)) or "unknown"
        raise ValueError(f"Expected a {platform} executable, found: {found}")


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
    parser.add_argument("command", choices=("matrix", "version", "inspect", "architecture", "collect"))
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
    elif args.command == "architecture":
        if args.directory is None:
            parser.error("architecture requires an executable")
        verify_architecture(args.directory, os.environ["PLATFORM"])
        print(f"Verified {os.environ['PLATFORM']} executable: {args.directory}")
    else:
        print(collect(os.environ["PLATFORM"]))


if __name__ == "__main__":
    main()
