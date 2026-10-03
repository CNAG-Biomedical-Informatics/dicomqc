"""Exercise worker publication and server startup with observable engine output."""

import os
from pathlib import Path
import socket
import threading
import time
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

pytest.importorskip("fastapi")

from dicomqc.api import runner, server, worker
from dicomqc.api.storage import identity, read_json, write_json
from dicomqc.fixtures import write_comparison_fixtures, write_policy_fixtures
from test_api import AUTH, LOCAL, TOKEN
from test_api_lifecycle import DEMO, stopped_jobs


@pytest.mark.parametrize("example", ["scan", "compare", "policy", "uid", "vendor"])
def test_worker_publishes_complete_demo_atomically(tmp_path, example):
    jobs = stopped_jobs(tmp_path)
    try:
        job = jobs.submit({**DEMO, "example": example})
        directory = jobs.directory(job["id"])
        worker.execute(directory)
        completion = read_json(directory / "completion.json")
        assert completion["audit_exit_code"] == (1 if example == "vendor" else 2)
        assert not (directory / "pending").exists()
        assert completion["summary"]["files_scanned"] > 0
        review = read_json(directory / "reports/review.json")
        assert "records" not in review
        assert all((directory / "reports" / name).is_file() for name in completion["artifacts"])
    finally:
        jobs.close()


@pytest.mark.parametrize("mode", ["scan", "compare"])
def test_worker_real_audit_publication_and_policy(tmp_path, mode):
    jobs = stopped_jobs(tmp_path)
    try:
        if mode == "scan":
            policy = write_policy_fixtures(tmp_path / "data")
            paths = {"paths": [policy.parent / "corrected"], "policy": [policy]}
        else:
            manifest = write_comparison_fixtures(tmp_path / "data")
            paths = {"source": [manifest.parent / "source"], "candidate": [manifest.parent / "candidate"],
                     "manifest": [manifest]}
        handles = {key: [jobs.register(str(path))["id"] for path in values] for key, values in paths.items()}
        job = jobs.submit({"mode": mode, "inputs": handles,
                           "options": {"uid_checks": False, "vendor_summary": False, "multiqc": mode == "scan"}})
        directory = jobs.directory(job["id"])
        worker.execute(directory)
        completion = read_json(directory / "completion.json")
        assert completion["audit_exit_code"] == (0 if mode == "scan" else 2)
        assert "report.html" in completion["artifacts"]
        assert read_json(directory / "progress.json")["phase"] == "reports"
    finally:
        jobs.close()


def test_worker_rejects_injected_overlapping_inputs(tmp_path):
    jobs = stopped_jobs(tmp_path)
    try:
        job = jobs.submit(DEMO)
        directory = jobs.directory(job["id"])
        request = read_json(directory / "request.json")
        request.update(mode="scan", inputs={"paths": [identity(jobs.root)]})
        write_json(directory / "request.json", request)
        with pytest.raises(ValueError, match="separate"):
            worker.execute(directory)
        assert not (directory / "completion.json").exists()
    finally:
        jobs.close()


def test_worker_main_redacts_failure_and_restores_warnings(tmp_path, monkeypatch, capsys):
    import logging
    previous = logging.root.manager.disable
    try:
        monkeypatch.setattr(worker, "execute", Mock(side_effect=ValueError("PRIVATE INPUT")))
        assert worker.main(str(tmp_path)) == 1
        assert not capsys.readouterr().err
        monkeypatch.setattr(worker, "execute", Mock())
        assert worker.main(str(tmp_path)) == 0
    finally:
        logging.disable(previous)


@pytest.mark.parametrize("ready_file,cleanup_error", [(True, False), (False, False), (True, True)])
def test_server_in_process_native_lifetime(tmp_path, monkeypatch, capsys, ready_file, cleanup_error):
    monkeypatch.setenv("DICOMQC_API_TOKEN", TOKEN)
    monkeypatch.setenv("DICOMQC_LOCAL_TOKEN", LOCAL)
    read_fd, write_fd = os.pipe()
    read_end = os.fdopen(read_fd, "rb", buffering=0)
    monkeypatch.setattr(server.sys, "stdin", SimpleNamespace(buffer=read_end))
    ready = tmp_path / "ready.json"
    if cleanup_error:
        original_unlink = Path.unlink

        def unlink(path, *args, **kwargs):
            if path == ready:
                raise OSError("readiness directory is no longer writable")
            return original_unlink(path, *args, **kwargs)

        monkeypatch.setattr(Path, "unlink", unlink)
    # Reserve the port while constructing the invocation, then release it.
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    args = ["--state-dir", str(tmp_path / "runs"), "--port", str(port), "--parent-stdin"]
    if ready_file:
        args.extend(["--ready-file", str(ready)])
    result = []
    thread = threading.Thread(target=lambda: result.append(server.main(args)))
    thread.start()
    try:
        import httpx
        deadline = time.monotonic() + 10
        with httpx.Client(base_url=f"http://127.0.0.1:{port}", trust_env=False, timeout=0.2) as http:
            while True:
                try:
                    response = http.get("/api/v1/health", headers=AUTH)
                    assert response.status_code == 200
                    break
                except httpx.TransportError:
                    assert thread.is_alive() and time.monotonic() < deadline
                    time.sleep(0.02)
        if ready_file:
            assert read_json(ready)["port"] == port
    finally:
        os.close(write_fd)
        thread.join(timeout=15)
        read_end.close()
    assert not thread.is_alive()
    assert result == [0]
    assert ready.exists() == cleanup_error
    if not ready_file:
        assert "dicomqc local API" in capsys.readouterr().out


def test_startup_failure_does_not_publish_ready_or_tracebacks(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("DICOMQC_API_TOKEN", TOKEN)
    monkeypatch.setenv("DICOMQC_LOCAL_TOKEN", LOCAL)
    root = tmp_path / "patient-data"
    root.mkdir()
    (root / "secret.dcm").write_text("PRIVATE")
    ready = tmp_path / "ready.json"
    assert server.main(["--state-dir", str(root), "--port", "0", "--ready-file", str(ready)]) == 2
    assert not ready.exists()
    output = capsys.readouterr().err
    assert "Cannot start" in output
    assert "Traceback" not in output and "patient-data" not in output


def test_runner_watchdog_authenticates_and_exits_on_disconnect(tmp_path, monkeypatch):
    write_json(tmp_path / "guard.json", {"port": 1234, "secret": "private"})
    connection = Mock()
    connection.recv.return_value = b""
    monkeypatch.setattr(runner.socket, "create_connection", Mock(return_value=connection))
    exit_process = Mock()
    monkeypatch.setattr(runner.os, "_exit", exit_process)
    monkeypatch.setattr(runner.threading, "Thread", lambda target, daemon: SimpleNamespace(start=target))
    engine = Mock(return_value=0)
    monkeypatch.setattr(worker, "main", engine)
    assert runner.run(str(tmp_path)) == 0
    connection.sendall.assert_called_once_with(b"private")
    exit_process.assert_called_once_with(1)
    engine.assert_called_once_with(str(tmp_path))
    connection.recv.side_effect = OSError("disconnected")
    assert runner.run(str(tmp_path)) == 0
    assert exit_process.call_count == 2


def test_runner_connection_failure_is_private(tmp_path, monkeypatch):
    assert runner.run(str(tmp_path)) == 1
    write_json(tmp_path / "guard.json", {"port": 1234, "secret": "private"})
    connection = Mock()
    connection.sendall.side_effect = OSError("PRIVATE")
    monkeypatch.setattr(runner.socket, "create_connection", Mock(return_value=connection))
    assert runner.run(str(tmp_path)) == 1
    connection.close.assert_called_once_with()


def test_frozen_worker_entrypoint_dispatch(tmp_path, monkeypatch):
    run = Mock(return_value=1)
    monkeypatch.setattr(runner, "run", run)
    assert server.main(["--worker", str(tmp_path)]) == 1
    run.assert_called_once_with(str(tmp_path))


def test_optional_api_dependency_missing_is_actionable(tmp_path, monkeypatch, capsys):
    import builtins
    original = builtins.__import__

    def missing(name, *args, **kwargs):
        if name == "uvicorn":
            raise ImportError("missing")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", missing)
    root = tmp_path / "runs"
    assert server.main(["--state-dir", str(root)]) == 2
    assert 'pip install "dicomqc[api]"' in capsys.readouterr().err
    assert not root.exists()
