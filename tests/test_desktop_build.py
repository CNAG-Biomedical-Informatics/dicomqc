"""Packaging contracts and opt-in end-to-end tests of a native frozen engine."""

import importlib.util
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("build_desktop_engine", ROOT / "scripts/build_desktop_engine.py")
build = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(build)


@pytest.fixture
def version_tree(tmp_path):
    pytest.importorskip("tomllib")
    files = {
        "pyproject.toml": '[project]\nversion = "0.2.0"\n',
        "src/dicomqc/__init__.py": '__version__ = "0.2.0"\n',
        "app/package.json": '{"version":"0.2.0"}',
        "app/package-lock.json": '{"version":"0.2.0","packages":{"":{"version":"0.2.0"}}}',
        "app/src-tauri/tauri.conf.json": '{"version":"0.2.0"}',
        "app/src-tauri/Cargo.toml": '[package]\nversion = "0.2.0"\n',
    }
    for name, content in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return tmp_path


def test_versions_agree(version_tree):
    assert build.check_versions(version_tree) == "0.2.0"


def test_repository_versions_and_resource_layout():
    pytest.importorskip("tomllib")
    from dicomqc import __version__

    assert build.check_versions(ROOT) == __version__
    config = json.loads((ROOT / "app/src-tauri/tauri.conf.json").read_text(encoding="utf-8"))
    assert config["bundle"]["resources"]["engine"] == "engine"


@pytest.mark.parametrize("name", [
    "pyproject.toml", "src/dicomqc/__init__.py", "app/package.json",
    "app/package-lock.json", "app/src-tauri/tauri.conf.json", "app/src-tauri/Cargo.toml",
])
def test_version_drift_rejected(version_tree, name):
    path = version_tree / name
    path.write_text(path.read_text(encoding="utf-8").replace("0.2.0", "0.3.0"), encoding="utf-8")
    with pytest.raises(ValueError, match="versions disagree"):
        build.check_versions(version_tree)


def test_missing_runtime_version_rejected(version_tree):
    (version_tree / "src/dicomqc/__init__.py").write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="Python runtime=None"):
        build.check_versions(version_tree)


def test_npm_root_version_drift_rejected(version_tree):
    path = version_tree / "app/package-lock.json"
    lock = json.loads(path.read_text())
    lock["packages"][""]["version"] = "0.3.0"
    path.write_text(json.dumps(lock), encoding="utf-8")
    with pytest.raises(ValueError, match="npm root package"):
        build.check_versions(version_tree)


def test_pyinstaller_command(tmp_path):
    root = tmp_path / "repo with spaces"
    command = build.pyinstaller_command(root, root / "build/desktop-engine")
    assert command[:3] == [sys.executable, "-m", "PyInstaller"]
    assert "--onedir" in command and "--onefile" not in command
    assert command[command.index("--name") + 1] == "dicomqc-api"
    assert command[command.index("--contents-directory") + 1] == "_internal"
    assert command[-1] == str(root / "scripts/desktop_engine_entry.py")
    assert [command[i + 1] for i, value in enumerate(command) if value == "--collect-all"] == [
        "dicomqc", "pydicom", "uvicorn", "fastapi", "pydantic", "pydantic_core",
    ]


@pytest.mark.parametrize("platform,name", [("linux", "dicomqc-api"), ("darwin", "dicomqc-api"),
                                           ("win32", "dicomqc-api.exe")])
def test_engine_layout(tmp_path, monkeypatch, platform, name):
    monkeypatch.setattr(build.sys, "platform", platform)
    (tmp_path / name).touch()
    with pytest.raises(ValueError, match="Incomplete onedir"):
        build.validate_engine(tmp_path)
    (tmp_path / "_internal").mkdir()
    assert build.validate_engine(tmp_path) == tmp_path / name


def test_build_stages_clean_engine(version_tree, monkeypatch):
    executable = "dicomqc-api.exe" if sys.platform == "win32" else "dicomqc-api"
    destination = version_tree / "app/src-tauri/engine"
    destination.mkdir()
    (destination / "stale-library").touch()

    def fake_run(command, **kwargs):
        assert kwargs == {"cwd": version_tree, "check": True}
        output = version_tree / "build/desktop-engine/dist/dicomqc-api"
        (output / "_internal").mkdir(parents=True)
        (output / executable).write_bytes(b"native executable")
        (output / "_internal/library").write_bytes(b"dependency")

    monkeypatch.setattr(build.subprocess, "run", fake_run)
    assert build.build_engine(version_tree) == destination / executable
    assert not (destination / "stale-library").exists()
    assert (destination / "_internal/library").read_bytes() == b"dependency"


def test_failed_build_preserves_existing_engine(version_tree, monkeypatch):
    destination = version_tree / "app/src-tauri/engine"
    destination.mkdir()
    (destination / "previous-build").touch()

    def fail(*args, **kwargs):
        raise subprocess.CalledProcessError(1, "PyInstaller")

    monkeypatch.setattr(build.subprocess, "run", fail)
    with pytest.raises(subprocess.CalledProcessError):
        build.build_engine(version_tree)
    assert (destination / "previous-build").exists()


def test_incomplete_build_preserves_existing_engine(version_tree, monkeypatch):
    destination = version_tree / "app/src-tauri/engine"
    destination.mkdir()
    (destination / "previous-build").touch()
    monkeypatch.setattr(build.subprocess, "run", lambda *args, **kwargs: None)
    with pytest.raises(ValueError, match="Incomplete onedir"):
        build.build_engine(version_tree)
    assert (destination / "previous-build").exists()


@pytest.mark.skipif(sys.version_info < (3, 11), reason="Desktop build CLI requires Python 3.11+")
def test_check_only_does_not_build(monkeypatch, capsys):
    monkeypatch.setattr(build, "check_versions", lambda: "0.2.0")

    def unexpected_build():
        pytest.fail("Version check must not build")

    monkeypatch.setattr(build, "build_engine", unexpected_build)
    assert build.main(["--check-versions"]) == 0
    assert "0.2.0" in capsys.readouterr().out


@pytest.mark.skipif(sys.version_info < (3, 11), reason="Desktop build CLI requires Python 3.11+")
def test_build_cli_reports_failure(monkeypatch, capsys):
    def fail():
        raise ValueError("Desktop versions disagree")

    monkeypatch.setattr(build, "build_engine", fail)
    assert build.main([]) == 1
    assert "Desktop versions disagree" in capsys.readouterr().err


@pytest.mark.parametrize("arguments", [
    ["--worker", "private workspace"],
    ["--state-dir", "private workspace", "--parent-stdin"],
])
def test_entry_delegates_arguments(monkeypatch, arguments):
    import dicomqc.api.server
    import multiprocessing

    calls = []
    monkeypatch.setattr(sys, "argv", ["dicomqc-api", *arguments])
    monkeypatch.setattr(multiprocessing, "freeze_support", lambda: calls.append("freeze"))

    def main():
        calls.append(sys.argv[1:])
        return 7

    monkeypatch.setattr(dicomqc.api.server, "main", main)
    with pytest.raises(SystemExit) as exc:
        runpy.run_path(str(ROOT / "scripts/desktop_engine_entry.py"), run_name="__main__")
    assert exc.value.code == 7
    assert calls == ["freeze", arguments]


def test_workflow_is_manual_artifact_only():
    # BaseLoader preserves GitHub's "on" key (YAML 1.1 treats it as a boolean).
    workflow = yaml.load((ROOT / ".github/workflows/build-desktop.yml").read_text(), Loader=yaml.BaseLoader)
    assert set(workflow["on"]) == {"workflow_dispatch"}
    assert workflow["permissions"] == {"contents": "read"}
    assert set(workflow["jobs"]) == {"desktop"}
    job = workflow["jobs"]["desktop"]
    assert {row["platform"] for row in job["strategy"]["matrix"]["include"]} == {
        "macos-x64", "macos-arm64", "windows-x64", "linux-x64", "linux-arm64",
    }
    assert "permissions" not in job
    steps = job["steps"]
    assert any(step.get("uses", "").startswith("actions/upload-artifact@") for step in steps)
    assert any(step.get("env", {}).get("DICOMQC_DESKTOP_ENGINE") for step in steps)
    native = next(step for step in steps if step.get("name") == "Test native bridge with frozen engine")
    assert native["run"] == "cargo test --manifest-path app/src-tauri/Cargo.toml --locked -- --ignored"
    assert native["env"]["DICOMQC_TEST_ENGINE"].startswith("${{ github.workspace }}/app/src-tauri/engine/dicomqc-api")
    assert "'.exe'" in native["env"]["DICOMQC_TEST_ENGINE"]
    assert steps.index(native) > next(i for i, step in enumerate(steps) if step.get("name") == "Test Rust launcher")
    assert not any("release" in step.get("uses", "") or "gh release" in step.get("run", "")
                   or "twine" in step.get("run", "") for step in steps)


def test_native_gui_workflow_is_linux_only_and_excludes_private_data():
    workflow = yaml.load((ROOT / ".github/workflows/build-desktop.yml").read_text(), Loader=yaml.BaseLoader)
    steps = workflow["jobs"]["desktop"]["steps"]
    smoke = next(step for step in steps if step.get("name") == "Smoke test Linux native GUI")
    assert smoke["if"] == "runner.os == 'Linux'"
    assert smoke["run"] == (
        "xvfb-run -a timeout 120s cargo run --manifest-path app/src-tauri/Cargo.toml --features native-smoke --locked"
    )
    assert smoke["env"] == {
        "DICOMQC_SMOKE_DIR": "${{ github.workspace }}/build/native-verification",
        "DICOMQC_DESKTOP_ENGINE": "${{ github.workspace }}/app/src-tauri/engine/dicomqc-api",
        "GDK_BACKEND": "x11",
        "WEBKIT_DISABLE_COMPOSITING_MODE": "1",
    }
    dependencies = next(step for step in steps if step.get("name") == "Install Linux native dependencies")
    assert {"xvfb", "xauth"} <= set(dependencies["run"].split())
    evidence = next(step for step in steps if step.get("name") == "Upload Linux native GUI evidence")
    assert evidence["if"] == "always() && runner.os == 'Linux'"
    assert evidence["with"]["path"].splitlines() == [
        "build/native-verification/*.png", "build/native-verification/*.json",
        "!build/native-verification/app-data/**",
    ]
    installer = next(step for step in steps if step.get("name") == "Build native installer")
    assert "--features" not in installer["run"]
    assert steps.index(smoke) < steps.index(installer)


def test_cli_workflow_runs_api_coverage_once():
    workflow = yaml.load((ROOT / ".github/workflows/build-and-test.yml").read_text(), Loader=yaml.BaseLoader)
    assert set(workflow["on"]) == {"workflow_dispatch"}
    steps = workflow["jobs"]["test"]["steps"]
    assert any('.[test,api,api-test]' in step.get("run", "") for step in steps)
    runs = [step["run"] for step in steps if "pytest" in step.get("run", "")]
    assert len(runs) == 1
    assert "--cov-report=xml" in runs[0]
    assert "--cov-fail-under=95.01" in runs[0]


@pytest.mark.skipif(not os.environ.get("DICOMQC_DESKTOP_ENGINE"), reason="Set DICOMQC_DESKTOP_ENGINE to a native onedir build")
@pytest.mark.parametrize("shutdown_mode", ["api", "parent-eof"])
def test_frozen_engine_relocation_workers_and_shutdown(tmp_path, shutdown_mode):
    source = Path(os.environ["DICOMQC_DESKTOP_ENGINE"]).resolve(strict=True)
    # Running outside the checkout with no PYTHONPATH catches source-tree dependencies.
    relocated = tmp_path / "relocated application with spaces/engine"
    shutil.copytree(source, relocated, symlinks=True)
    executable = build.validate_engine(relocated)
    token, local = "a" * 48, "b" * 48
    token_file, local_file, ready = (tmp_path / name for name in ("token", "local-token", "ready.json"))
    token_file.write_text(token, encoding="utf-8")
    local_file.write_text(local, encoding="utf-8")
    env = {key: value for key, value in os.environ.items()
           if not key.startswith(("PYTHON", "DICOMQC_", "_PYI_")) and key != "VIRTUAL_ENV"}
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with (tmp_path / "engine.log").open("w+b") as log:
        process = subprocess.Popen([
            str(executable), "--state-dir", str(tmp_path / "state"), "--port", "0",
            "--token-file", str(token_file), "--local-token-file", str(local_file),
            "--ready-file", str(ready), "--parent-stdin",
        ], cwd=tmp_path, env=env, stdin=subprocess.PIPE, stdout=log, stderr=log)
        try:
            deadline = time.monotonic() + 60
            while not ready.exists():
                assert process.poll() is None, "Frozen server exited before readiness"
                assert time.monotonic() < deadline, "Frozen server readiness timed out"
                time.sleep(0.1)
            base = f'http://127.0.0.1:{json.loads(ready.read_text())["port"]}/api/v1'

            def request(path, payload=None, privileged=False, authenticated=True):
                headers = {"Authorization": "Bearer " + token} if authenticated else {}
                if privileged:
                    headers["X-Dicomqc-Local"] = local
                data = None if payload is None else json.dumps(payload).encode()
                if data is not None:
                    headers["Content-Type"] = "application/json"
                with opener.open(urllib.request.Request(base + path, data=data, headers=headers), timeout=5) as response:
                    return response.read()

            # Verify HTTP readiness in addition to the server's ready-file contract.
            while True:
                try:
                    health = json.loads(request("/health"))
                    break
                except (urllib.error.URLError, TimeoutError):
                    assert process.poll() is None and time.monotonic() < deadline
                    time.sleep(0.1)
            from dicomqc import __version__
            assert health == {"status": "ready", "version": __version__, "api_version": 1}
            with pytest.raises(urllib.error.HTTPError) as unauthorized:
                request("/health", authenticated=False)
            assert unauthorized.value.code == 401
            for example in ("scan", "compare", "policy", "uid", "vendor"):
                job = json.loads(request("/jobs", {"mode": "demo", "example": example}))
                deadline = time.monotonic() + 60
                while job["status"] in {"queued", "running"}:
                    assert time.monotonic() < deadline, f"Frozen {example} worker timed out"
                    time.sleep(0.1)
                    job = json.loads(request("/jobs/" + job["id"]))
                assert job["status"] == "completed", job
                assert job["audit_exit_code"] == (1 if example == "vendor" else 2)
                index = next(i for i, name in enumerate(job["artifacts"])
                             if name.endswith(".html") and not name.endswith("_mqc.html"))
                assert b"<html" in request(f'/jobs/{job["id"]}/artifacts/{index}').lower()
                assert "summary" in json.loads(request(f'/jobs/{job["id"]}/results'))
            if shutdown_mode == "api":
                request("/shutdown", {}, privileged=True)
            else:
                process.stdin.close()
            assert process.wait(timeout=20) == 0
            assert not ready.exists()
        except Exception:
            log.flush()
            log.seek(0)
            print(log.read().decode(errors="replace"))
            raise
        finally:
            process.stdin.close()
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)
