"""Checks for installer selection, release guards, and checksum generation."""

import hashlib
import importlib
import json
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.fixture
def release(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "scripts"))
    return importlib.import_module("desktop_release")


def test_platform_selection(release):
    assert len(release.select_platforms("all")) == 5
    for row in release.PLATFORMS:
        assert release.select_platforms(row["platform"]) == [row]
    with pytest.raises(ValueError, match="Unknown platform"):
        release.select_platforms("other")


def test_matrix_command(release, monkeypatch, tmp_path):
    target = tmp_path / "outputs"
    monkeypatch.setenv("GITHUB_OUTPUT", str(target))
    monkeypatch.setenv("PLATFORM", "linux-arm64")
    monkeypatch.setattr(sys, "argv", ["desktop_release.py", "matrix"])
    release.main()
    assert json.loads(target.read_text().split("=", 1)[1]) == release.select_platforms("linux-arm64")


def test_manual_version_check(release, monkeypatch):
    monkeypatch.setattr(release, "check_versions", lambda: "0.2.0")
    monkeypatch.setenv("GITHUB_REF_TYPE", "branch")
    assert release.verify_version() == "0.2.0"


@pytest.mark.parametrize("tag", ["v0.1.0", "v0.2.0rc1", "0.2.0", "v0.2"])
def test_reject_invalid_tag(release, monkeypatch, tag):
    monkeypatch.setattr(release, "check_versions", lambda: "0.2.0")
    monkeypatch.setenv("GITHUB_REF_TYPE", "tag")
    monkeypatch.setenv("GITHUB_REF_NAME", tag)
    with pytest.raises(ValueError, match="Stable tag"):
        release.verify_version()


@pytest.mark.parametrize("kind,target,valid", [("tag", "abc", True), ("commit", "abc", False), ("tag", "def", False)])
def test_annotated_tag_guard(release, monkeypatch, kind, target, valid):
    monkeypatch.setattr(release, "check_versions", lambda: "0.2.0")
    monkeypatch.setenv("GITHUB_REF_TYPE", "tag")
    monkeypatch.setenv("GITHUB_REF_NAME", "v0.2.0")
    answers = iter([kind, target, "abc"])
    monkeypatch.setattr(subprocess, "check_output", lambda *a, **kw: next(answers))
    if valid:
        assert release.verify_version() == "0.2.0"
    else:
        with pytest.raises(ValueError):
            release.verify_version()


def test_find_engine_and_inspect(release, tmp_path, monkeypatch):
    with pytest.raises(ValueError, match="found 0"):
        release.find_engine(tmp_path)
    engine = tmp_path / "resources/engine"
    (engine / "_internal").mkdir(parents=True)
    executable = "dicomqc-api.exe" if sys.platform == "win32" else "dicomqc-api"
    (engine / executable).write_bytes(b"fixture")
    assert release.find_engine(tmp_path) == engine.resolve()
    calls = []
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: calls.append((a, kw)))
    release.inspect(tmp_path)
    args, kwargs = calls[0]
    assert "frozen" in args[0]
    assert kwargs["env"]["DICOMQC_DESKTOP_ENGINE"] == str(engine.resolve())
    assert kwargs["check"] is True
    second = tmp_path / "duplicate"
    (second / "_internal").mkdir(parents=True)
    (second / executable).write_bytes(b"fixture")
    with pytest.raises(ValueError, match="found 2"):
        release.find_engine(tmp_path)


@pytest.mark.parametrize("platform,bundle,filename,suffix", [
    ("linux-x64", "appimage", "app.AppImage", ".AppImage"),
    ("macos-arm64", "dmg", "app.dmg", ".dmg"),
    ("windows-x64", "nsis", "app-setup.exe", "-setup.exe"),
])
def test_collect_checksum(release, tmp_path, monkeypatch, platform, bundle, filename, suffix):
    monkeypatch.setattr(release, "check_versions", lambda root: "0.2.0")
    with pytest.raises(ValueError, match="found 0"):
        release.collect(platform, tmp_path)
    directory = tmp_path / "app/src-tauri/target/release/bundle" / bundle
    directory.mkdir(parents=True)
    (directory / filename).write_bytes(b"installer fixture")
    output = release.collect(platform, tmp_path)
    assert output.name == f"dicomqc-0.2.0-{platform}{suffix}"
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    assert output.with_name(output.name + ".sha256").read_text() == f"{digest}  {output.name}\n"
    (directory / ("extra-" + filename)).write_bytes(b"duplicate")
    with pytest.raises(ValueError, match="found 2"):
        release.collect(platform, tmp_path)


def test_collect_rejects_all(release, tmp_path):
    with pytest.raises(ValueError, match="one platform"):
        release.collect("all", tmp_path)
