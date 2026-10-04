"""Regression tests for supervisor ownership, damaged state, and native lifetime."""

import io
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from unittest.mock import Mock

import pytest

pytest.importorskip("fastapi")

from dicomqc.api.jobs import Jobs
from dicomqc.api import jobs as jobs_module
from dicomqc.api.server import main, watch_parent
from dicomqc.api.storage import write_json
from dicomqc.api.worker import execute
from dicomqc.progress import emit
from test_api import AUTH, LOCAL, PRIVILEGED, TOKEN, client, register


DEMO = {"mode": "demo", "inputs": {}, "options": {}, "example": "uid"}


def stopped_jobs(tmp_path):
    jobs = Jobs(tmp_path / "runs")
    jobs.stopping.set()
    jobs.thread.join()
    jobs.stopping.clear()
    return jobs


@pytest.mark.parametrize("name", ["owner.lock", "runs.sqlite", "runs.sqlite-journal", "runs.sqlite-wal", "runs.sqlite-shm"])
@pytest.mark.parametrize("link", ["symlink", "hardlink"])
def test_state_links_never_write_the_target(tmp_path, name, link):
    root = tmp_path / "runs"
    root.mkdir()
    target = tmp_path / "selected-input"
    target.write_bytes(b"must remain unchanged")
    (root / "owner.lock").touch()
    (root / "runs.sqlite").touch()
    path = root / name
    path.unlink(missing_ok=True)
    if link == "symlink":
        path.symlink_to(target)
    else:
        os.link(target, path)
    with pytest.raises(ValueError):
        Jobs(root)
    assert target.read_bytes() == b"must remain unchanged"


def test_unrelated_workspace_rejected_without_writes(tmp_path):
    root = tmp_path / "inputs"
    root.mkdir()
    (root / "patient.dcm").write_bytes(b"input")
    with pytest.raises(ValueError, match="do not belong to a dicomqc run workspace"):
        Jobs(root)
    assert [p.name for p in root.iterdir()] == ["patient.dcm"]
    link = tmp_path / "linked"
    link.symlink_to(root, target_is_directory=True)
    with pytest.raises(ValueError, match="symbolic"):
        Jobs(link)


@pytest.mark.skipif(os.name != "nt", reason="Windows extended path aliases")
@pytest.mark.parametrize("selected", ["workspace", "child", "parent"])
def test_extended_windows_paths_cannot_overlap_workspace(tmp_path, selected):
    jobs = stopped_jobs(tmp_path)
    paths = {"workspace": jobs.root, "child": jobs.root / "owner.lock", "parent": tmp_path}
    alias = "\\\\?\\" + str(paths[selected].resolve())
    try:
        with pytest.raises(ValueError, match="Keep inputs separate"):
            jobs.register(alias)
        outside = tmp_path / "input.dcm"
        outside.write_bytes(b"synthetic input")
        assert jobs.register("\\\\?\\" + str(outside.resolve()))["kind"] == "file"
    finally:
        jobs.close()


@pytest.mark.parametrize("extended", [False, True])
def test_workspace_reopens_and_deletes_with_native_path_spelling(tmp_path, extended):
    if extended and os.name != "nt":
        pytest.skip("Windows extended path aliases")
    jobs = stopped_jobs(tmp_path / "workspace #100%")
    job = jobs.submit(DEMO)
    jobs.cancel(job["id"])
    root = jobs.root
    jobs.close()
    reopened = Jobs(Path("\\\\?\\" + str(root)) if extended else root)
    try:
        assert reopened.get(job["id"])["status"] == "cancelled"
        assert reopened.delete(job["id"])["status"] == "deleted"
        assert reopened.list() == []
    finally:
        reopened.close()


@pytest.mark.skipif(os.name == "nt", reason="Windows prevents renaming an open workspace")
def test_root_replaced_by_symlink_blocks_reads_writes_and_worker(tmp_path):
    jobs = stopped_jobs(tmp_path)
    job = jobs.submit(DEMO)
    directory = jobs.directory(job["id"])
    root = jobs.root
    moved = tmp_path / "moved"
    root.rename(moved)
    root.symlink_to(moved, target_is_directory=True)
    before = sorted(str(p.relative_to(moved)) for p in moved.rglob("*"))
    try:
        for action in (lambda: jobs.submit(DEMO), lambda: jobs.directory(job["id"]),
                       lambda: jobs.register(str(tmp_path)), lambda: execute(directory)):
            with pytest.raises(ValueError):
                action()
        jobs._loop()
        assert jobs.stopping.is_set()
    finally:
        jobs.close()
        jobs.close()
    assert before == sorted(str(p.relative_to(moved)) for p in moved.rglob("*"))


def test_changed_queued_input_fails_then_queue_continues(tmp_path):
    jobs = stopped_jobs(tmp_path)
    path = tmp_path / "input.dcm"
    path.write_bytes(b"old")
    handle = jobs.register(str(path))["id"]
    first = jobs.submit({"mode": "scan", "inputs": {"paths": [handle]}, "options": {}})
    second = jobs.submit(DEMO)
    path.write_bytes(b"changed")
    try:
        jobs._tick()
        assert jobs.get(first["id"])["status"] == "failed"
        assert jobs.get(second["id"])["status"] == "queued"
        jobs._tick()
        assert jobs.get(second["id"])["status"] == "running"
        process = jobs.process
        assert jobs.cancel(second["id"])["status"] == "cancelled"
        assert process.poll() is not None
        jobs._tick()
        assert jobs.process is None
    finally:
        jobs.close()


def test_corrupt_completion_does_not_stop_queue(tmp_path):
    jobs = stopped_jobs(tmp_path)
    job = jobs.submit(DEMO)
    job["status"] = "running"
    jobs._save(job)
    jobs.current = job["id"]
    jobs.process = Mock(poll=Mock(return_value=0))
    (jobs.directory(job["id"]) / "completion.json").write_text("{broken")
    try:
        jobs._tick()
        assert jobs.get(job["id"])["status"] == "failed"
        assert not jobs.stopping.is_set()
        assert jobs.process is None
    finally:
        jobs.close()


@pytest.mark.parametrize("handshake", ["fragmented", "wrong", "eof", "timeout", "spawn_error"])
def test_worker_handshake_cleanup_and_token_isolation(tmp_path, monkeypatch, handshake):
    jobs = stopped_jobs(tmp_path)
    job = jobs.submit(DEMO)
    directory = jobs.directory(job["id"])
    listener, connection, process = Mock(), Mock(), Mock()
    listener.getsockname.return_value = ("127.0.0.1", 1234)
    listener.accept.return_value = (connection, ("127.0.0.1", 4321))
    process.poll.return_value = None
    received = 0

    def recv(size):
        nonlocal received
        if handshake == "wrong":
            return b"x" * size
        if handshake == "eof":
            return b""
        if handshake == "timeout":
            raise TimeoutError()
        secret = json.loads((directory / "guard.json").read_text())["secret"].encode()
        chunk = secret[received:received + min(size, 3)]
        received += len(chunk)
        return chunk

    connection.recv.side_effect = recv
    monkeypatch.setattr(jobs_module.socket, "socket", Mock(return_value=listener))
    spawn = Mock(return_value=process)
    if handshake == "spawn_error":
        spawn.side_effect = OSError("private path")
    monkeypatch.setattr(jobs_module.subprocess, "Popen", spawn)
    monkeypatch.setenv("DICOMQC_API_TOKEN", TOKEN)
    monkeypatch.setenv("DICOMQC_LOCAL_TOKEN", LOCAL)
    try:
        jobs._tick()
        assert "DICOMQC_API_TOKEN" not in spawn.call_args.kwargs["env"]
        assert "DICOMQC_LOCAL_TOKEN" not in spawn.call_args.kwargs["env"]
        listener.close.assert_called_once()
        if handshake == "fragmented":
            assert jobs.get(job["id"])["status"] == "running"
            assert connection.recv.call_count > 1
            jobs._tick()
            spawn.assert_called_once()
            jobs.cancel(job["id"])
            process.terminate.assert_called_once()
            process.poll.return_value = 0
        else:
            assert jobs.get(job["id"])["status"] == "failed"
            assert jobs.process is None
            if handshake != "spawn_error":
                connection.close.assert_called_once()
                process.kill.assert_called_once()
                process.wait.assert_called_once()
    finally:
        jobs.close()


@pytest.mark.parametrize("payload", [{}, {"audit_exit_code": 9}, []])
def test_invalid_completion_metadata_never_publishes(tmp_path, payload):
    jobs = stopped_jobs(tmp_path)
    job = jobs.submit(DEMO)
    job["status"] = "running"
    jobs._save(job)
    jobs.current = job["id"]
    jobs.process = Mock(poll=Mock(return_value=0))
    write_json(jobs.directory(job["id"]) / "completion.json", payload)
    try:
        jobs._tick()
        assert jobs.get(job["id"])["status"] == "failed"
        assert jobs.get(job["id"])["artifacts"] == []
    finally:
        jobs.close()


def test_unrelated_database_rejected_without_schema_change(tmp_path):
    import sqlite3
    root = tmp_path / "runs"
    root.mkdir()
    (root / "owner.lock").touch()
    database = root / "runs.sqlite"
    connection = sqlite3.connect(database)
    connection.execute("CREATE TABLE unrelated (data TEXT)")
    connection.close()
    before = database.read_bytes()
    with pytest.raises(ValueError, match="valid dicomqc run database"):
        Jobs(root)
    assert database.read_bytes() == before


def test_corrupt_history_releases_owner_lock(tmp_path):
    import sqlite3
    jobs = stopped_jobs(tmp_path)
    jobs.db.execute("INSERT INTO jobs VALUES ('broken', 0, 'not json')")
    jobs.db.commit()
    root = jobs.root
    jobs.close()
    with pytest.raises(ValueError):
        Jobs(root)
    connection = sqlite3.connect(root / "runs.sqlite")
    connection.execute("DELETE FROM jobs")
    connection.commit()
    connection.close()
    recovered = Jobs(root)
    recovered.close()


def test_database_initialization_failure_releases_resources(tmp_path, monkeypatch):
    import sqlite3
    database = Mock()
    database.execute.side_effect = sqlite3.DatabaseError("failure")
    monkeypatch.setattr(jobs_module.sqlite3, "connect", Mock(return_value=database))
    with pytest.raises(sqlite3.DatabaseError):
        Jobs(tmp_path / "runs")
    database.close.assert_called_once()
    if os.name != "nt":
        import fcntl
        with (tmp_path / "runs/owner.lock").open("r+b") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)


@pytest.mark.skipif(os.name == "nt", reason="Unix special-file input")
def test_special_input_cannot_be_registered(tmp_path):
    jobs = stopped_jobs(tmp_path)
    fifo = tmp_path / "fifo"
    os.mkfifo(fifo)
    try:
        with pytest.raises(ValueError, match="regular"):
            jobs.register(str(fifo))
    finally:
        jobs.close()


def test_atomic_write_failure_leaves_original_intact(tmp_path, monkeypatch):
    import dicomqc.api.storage as storage
    path = tmp_path / "state.json"
    write_json(path, {"old": True})
    monkeypatch.setattr(storage.os, "replace", Mock(side_effect=OSError("disk failure")))
    with pytest.raises(OSError):
        write_json(path, {"new": True})
    assert json.loads(path.read_text()) == {"old": True}
    assert not list(tmp_path.glob(".pending-*"))


def test_run_and_report_redirects_are_rejected(tmp_path):
    jobs = stopped_jobs(tmp_path)
    job = jobs.submit(DEMO)
    directory = jobs.directory(job["id"])
    reports = directory / "reports"
    reports.mkdir()
    outside = tmp_path / "outside.json"
    outside.write_text("{}")
    (reports / "report.json").symlink_to(outside)
    (reports / "review.json").symlink_to(outside)
    job.update(status="completed", artifacts=["report.json"])
    jobs._save(job)
    try:
        with pytest.raises(ValueError, match="path changed"):
            jobs.artifact(job["id"], 0)
        with pytest.raises(ValueError, match="path changed"):
            jobs.review(job["id"])
        directory.rename(tmp_path / "moved-run")
        directory.symlink_to(tmp_path / "moved-run", target_is_directory=True)
        with pytest.raises(ValueError, match="directory changed"):
            jobs.directory(job["id"])
    finally:
        jobs.close()


def test_corrupt_progress_cannot_block_running_cancellation(tmp_path):
    jobs = stopped_jobs(tmp_path)
    job = jobs.submit(DEMO)
    job["status"] = "running"
    jobs._save(job)
    (jobs.directory(job["id"]) / "progress.json").write_text("{")
    jobs.current = job["id"]
    process = jobs.process = Mock(poll=Mock(return_value=None))
    process.wait.side_effect = [subprocess.TimeoutExpired("worker", 3), 0]
    try:
        assert jobs.cancel(job["id"])["status"] == "cancelled"
        process.terminate.assert_called_once()
        process.kill.assert_called_once()
        process.poll.return_value = 0
    finally:
        jobs.close()


def test_jobs_polling_includes_live_progress(client):
    jobs = client.app.state.jobs
    with jobs.mutex:
        job = jobs.submit(DEMO)
        job["status"] = "running"
        jobs._save(job)
        path = jobs.directory(job["id"]) / "progress.json"
        first = {"phase": "reading", "completed": 0, "total": 2}
        write_json(path, first)
        assert jobs.list()[0]["progress"] == first
    assert client.get("/api/v1/jobs", headers=AUTH).json()[0]["progress"] == first
    second = {**first, "completed": 1}
    write_json(path, second)
    assert client.get("/api/v1/jobs", headers=AUTH).json()[0]["progress"] == second
    assert jobs.get(job["id"])["progress"] == second
    path.write_text("corrupted")
    assert "progress" not in client.get("/api/v1/jobs", headers=AUTH).json()[0]


def test_run_log_merges_only_predefined_worker_events(client):
    jobs = client.app.state.jobs
    jobs.stopping.set()
    jobs.thread.join()
    jobs.stopping.clear()
    with jobs.mutex:
        job = jobs.submit(DEMO)
        assert [event["event"] for event in job["log"]] == ["queued"]
        events = jobs.directory(job["id"]) / "events.json"
        write_json(events, [{"at": 123.5, "event": "reading"}])
        assert {"at": 123.5, "event": "reading"} in jobs.get(job["id"])["log"]
        write_json(events, [{"at": 124.5, "event": "PRIVATE_PATIENT_VALUE"}])
    response = client.get("/api/v1/jobs", headers=AUTH)
    assert "PRIVATE_PATIENT_VALUE" not in response.text
    assert [event["event"] for event in response.json()[0]["log"]] == ["queued"]


def test_validation_errors_do_not_echo_inputs(client):
    secret = "PRIVATE_PATIENT_VALUE"
    response = client.post("/api/v1/jobs", headers=AUTH, json={"mode": secret})
    assert response.status_code == 422
    assert secret not in response.text
    response = client.post("/api/v1/inputs/local", headers=PRIVILEGED, json={"path": {secret: True}})
    assert response.status_code == 422
    assert secret not in response.text


def test_policy_and_manifest_roles_require_files(client, tmp_path):
    directory = tmp_path / "data"
    directory.mkdir()
    handle = register(client, directory)
    response = client.post("/api/v1/jobs", headers=AUTH,
                           json={"mode": "scan", "inputs": {"paths": [handle], "policy": [handle]}})
    assert response.status_code == 400


def test_progress_forwards_completed_counts_unchanged():
    events = []
    emit(events.append, "reading", 0, 2)
    emit(events.append, "reading", 1, 2)
    emit(events.append, "reading", 2, 2)
    emit(events.append, "relationships", 2, 2)
    assert events == [
        {"phase": "reading", "completed": count, "total": 2} for count in (0, 1, 2)
    ] + [{"phase": "relationships", "completed": 2, "total": 2}]


def test_parent_watcher_waits_for_eof():
    shutdown = Mock()
    watch_parent(io.BytesIO(b"keepalive"), shutdown)
    shutdown.assert_called_once_with()
    watch_parent(Mock(read=Mock(side_effect=OSError("closed"))), shutdown)
    assert shutdown.call_count == 2


@pytest.mark.parametrize("args", [["--port", "-1"], ["--port", "65536"], []])
def test_server_configuration_errors_are_generic(tmp_path, monkeypatch, capsys, args):
    monkeypatch.delenv("DICOMQC_API_TOKEN", raising=False)
    monkeypatch.delenv("DICOMQC_LOCAL_TOKEN", raising=False)
    assert main(["--state-dir", str(tmp_path / "private-path"), *args]) == 2
    output = capsys.readouterr().err
    assert "Cannot start" in output
    assert "Traceback" not in output and "private-path" not in output


def test_real_server_ready_and_parent_eof(tmp_path):
    ready = tmp_path / "ready.json"
    process = subprocess.Popen([sys.executable, "-m", "dicomqc.api.server", "--state-dir", str(tmp_path / "runs"),
                                "--port", "0", "--ready-file", str(ready), "--parent-stdin"],
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               env={**os.environ, "DICOMQC_API_TOKEN": TOKEN, "DICOMQC_LOCAL_TOKEN": LOCAL})
    try:
        deadline = time.monotonic() + 15
        while not ready.exists() and process.poll() is None and time.monotonic() < deadline:
            time.sleep(0.02)
        assert ready.exists()
        import httpx2 as httpx
        with httpx.Client(base_url=f'http://127.0.0.1:{json.loads(ready.read_text())["port"]}', trust_env=False) as http:
            assert http.get("/api/v1/health", headers=AUTH).json()["status"] == "ready"
            job = http.post("/api/v1/jobs", headers=AUTH, json=DEMO).json()
        process.stdin.close()
        assert process.wait(timeout=15) == 0
        assert not ready.exists()
        assert b"Traceback" not in process.stderr.read()
        jobs = Jobs(tmp_path / "runs")
        try:
            assert jobs.get(job["id"])["status"] in {"cancelled", "completed"}
        finally:
            jobs.close()
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        process.stdout.close()
        process.stderr.close()


def test_real_worker_exits_when_supervisor_disappears(tmp_path):
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        listener.settimeout(10)
        secret = "guard-secret"
        write_json(tmp_path / "guard.json", {"port": listener.getsockname()[1], "secret": secret})
        # Keep the engine busy without manufacturing a large patient dataset.
        script = ("import sys,time; from dicomqc.api import runner,worker; "
                  "worker.main=lambda directory: time.sleep(60); "
                  "raise SystemExit(runner.run(sys.argv[1]))")
        process = subprocess.Popen([sys.executable, "-c", script, str(tmp_path)],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            connection, _ = listener.accept()
            with connection:
                connection.settimeout(5)
                received = b""
                while len(received) < len(secret):
                    chunk = connection.recv(len(secret) - len(received))
                    assert chunk
                    received += chunk
                assert received == secret.encode()
                assert process.poll() is None
            assert process.wait(timeout=10) == 1
            assert not process.stderr.read()
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
            process.stdout.close()
            process.stderr.close()
