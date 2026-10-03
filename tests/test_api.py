"""API security, real isolated audits, persistence, and CLI parity."""

import hashlib
import json
from pathlib import Path
import time

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from dicomqc.api.app import create_app
from dicomqc.api.jobs import Jobs
from dicomqc.api.storage import identity, read_json, validate_identity, write_json
from dicomqc.fixtures import write_uid_fixtures, write_comparison_fixtures, write_policy_fixtures, write_vendor_fixtures
from dicomqc.scanner import scan_paths

TOKEN, LOCAL = "a" * 48, "b" * 48
AUTH = {"Authorization": "Bearer " + TOKEN}
PRIVILEGED = {**AUTH, "X-Dicomqc-Local": LOCAL}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("PYTHONPATH", str(Path(__file__).resolve().parents[1] / "src"))
    with TestClient(create_app(tmp_path / "runs", TOKEN, LOCAL), base_url="http://127.0.0.1") as value:
        yield value


def register(client, path):
    response = client.post("/api/v1/inputs/local", headers=PRIVILEGED, json={"path": str(path)})
    assert response.status_code == 200, response.text
    return response.json()["id"]


def finish(client, job):
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        value = client.get("/api/v1/jobs/" + job["id"], headers=AUTH).json()
        if value["status"] not in {"queued", "running"}:
            return value
        time.sleep(0.02)
    pytest.fail("Worker did not finish")


def test_authentication_host_origin_and_privileged_commands(client, tmp_path):
    assert client.get("/api/v1/health").status_code == 401
    assert client.get("/api/v1/openapi.json").status_code == 401
    assert client.get("/api/v1/health", headers=AUTH).json()["status"] == "ready"
    assert client.get("/api/v1/health", headers={**AUTH, "host": "evil.example"}).status_code == 400
    assert client.get("/api/v1/health", headers={**AUTH, "origin": "http://evil.example"}).status_code == 403
    assert client.post("/api/v1/inputs/local", headers=AUTH, json={"path": str(tmp_path)}).status_code == 403
    assert client.post("/api/v1/shutdown", headers=AUTH).status_code == 403
    assert client.post("/api/v1/shutdown", headers=PRIVILEGED).status_code == 200
    assert client.get("/api/v1/capabilities", headers=AUTH).json()["max_concurrent_jobs"] == 1
    assert client.get("/api/v1/openapi.json", headers=AUTH).status_code == 200


@pytest.mark.parametrize("token,local", [("x", LOCAL), (TOKEN, TOKEN)])
def test_private_tokens_required(tmp_path, token, local):
    with pytest.raises(ValueError):
        create_app(tmp_path, token, local)


def test_uid_scan_matches_cli_and_does_not_expose_raw_context(client, tmp_path):
    write_uid_fixtures(tmp_path / "data")
    folder = tmp_path / "data/candidate"
    before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.iterdir()}
    handle = register(client, folder)
    response = client.post("/api/v1/jobs", headers=AUTH, json={"mode": "scan", "inputs": {"paths": [handle]}, "options": {"uid_checks": True}})
    assert response.status_code == 202
    job = finish(client, response.json())
    assert job["status"] == "completed"
    assert job["audit_exit_code"] == 2
    expected = scan_paths([folder], uid_checks=True)
    assert job["summary"]["errors"] == expected.error_count == 7
    response = client.get(f'/api/v1/jobs/{job["id"]}/results?limit=2', headers=AUTH)
    assert response.json()["total_findings"] == 7
    assert len(response.json()["findings"]) == 2
    assert "records" not in response.json()
    assert "1.2.826" not in response.text
    assert client.get(f'/api/v1/jobs/{job["id"]}/results?limit=999', headers=AUTH).status_code == 400
    for index, artifact in enumerate(job["artifacts"]):
        response = client.get(f'/api/v1/jobs/{job["id"]}/artifacts/{index}', headers=AUTH)
        assert response.status_code == 200
        assert "1.2.826" not in response.text
    assert client.get(f'/api/v1/jobs/{job["id"]}/artifacts/999', headers=AUTH).status_code == 400
    assert before == {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.iterdir()}


def test_comparison_policy_and_multiqc(client, tmp_path):
    data = tmp_path / "comparison"
    manifest = write_comparison_fixtures(data)
    inputs = {name: [register(client, data / name)] for name in ("source", "candidate")}
    inputs["manifest"] = [register(client, manifest)]
    response = client.post("/api/v1/jobs", headers=AUTH, json={"mode": "compare", "inputs": inputs})
    job = finish(client, response.json())
    assert job["status"] == "completed" and job["summary"]["errors"] == 3
    policy = write_policy_fixtures(tmp_path / "policy")
    inputs = {"paths": [register(client, policy.parent / "corrected")], "policy": [register(client, policy)]}
    response = client.post("/api/v1/jobs", headers=AUTH, json={"mode": "scan", "inputs": inputs, "options": {"multiqc": True}})
    job = finish(client, response.json())
    assert job["audit_exit_code"] == 0
    assert any(name.startswith("multiqc/") for name in job["artifacts"])
    assert client.get(f'/api/v1/jobs/{job["id"]}/results', headers=AUTH).json()["policy"]["id"] == "research-demo"


@pytest.mark.parametrize("example", ["scan", "compare", "policy", "uid", "vendor"])
def test_examples(client, example):
    response = client.post("/api/v1/jobs", headers=AUTH, json={"mode": "demo", "example": example})
    job = finish(client, response.json())
    assert job["status"] == "completed"
    assert any(name.endswith(".html") for name in job["artifacts"])
    assert job["audit_exit_code"] == (1 if example == "vendor" else 2)


@pytest.mark.parametrize("payload", [
    {"mode": "scan"}, {"mode": "compare"}, {"mode": "demo", "options": {"uid_checks": True}},
    {"mode": "scan", "inputs": {"paths": ["unknown"]}, "command": "rm"},
    {"mode": "scan", "inputs": {"paths": ["unknown"]}, "options": {"vendor_summary": "yes"}},
])
def test_invalid_requests(client, payload):
    assert client.post("/api/v1/jobs", headers=AUTH, json=payload).status_code == 422


def test_changed_unknown_missing_and_overlapping_inputs(client, tmp_path):
    assert client.post("/api/v1/jobs", headers=AUTH, json={"mode": "scan", "inputs": {"paths": ["unknown"]}}).status_code == 400
    assert client.post("/api/v1/inputs/local", headers=PRIVILEGED, json={"path": str(tmp_path / "missing")}).status_code == 400
    assert client.post("/api/v1/inputs/local", headers=PRIVILEGED, json={"path": str(tmp_path)}).status_code == 400
    path = tmp_path / "input"
    path.write_text("one")
    handle = register(client, path)
    path.write_text("different")
    assert client.post("/api/v1/jobs", headers=AUTH, json={"mode": "scan", "inputs": {"paths": [handle]}}).status_code == 400
    assert client.get("/api/v1/jobs/missing", headers=AUTH).status_code == 400


def test_cancel_queue_shutdown_lock_and_recovery(client, tmp_path):
    jobs = client.app.state.jobs
    with pytest.raises(ValueError, match="already open"):
        Jobs(tmp_path / "runs")
    with jobs.mutex:
        request = {"mode": "demo", "inputs": {}, "options": {}, "example": "uid"}
        job = jobs.submit(request)
        assert jobs.cancel(job["id"])["status"] == "cancelled"
        assert jobs.cancel(job["id"])["status"] == "cancelled"
        with pytest.raises(ValueError):
            jobs.review(job["id"])
        with pytest.raises(ValueError):
            jobs.directory("../escape")
    assert client.get("/api/v1/jobs", headers=AUTH).json()[0]["status"] == "cancelled"
    root = tmp_path / "other-runs"
    other = Jobs(root)
    other.stopping.set()
    other.thread.join()
    with pytest.raises(ValueError, match="shutting down"):
        other.submit(request)
    interrupted = {"id": "a" * 32, "created": 1, "status": "running"}
    other._save(interrupted)
    other.db.close()
    other.lock_file.close()
    recovered = Jobs(root)
    try:
        assert recovered.get("a" * 32)["status"] == "interrupted"
    finally:
        recovered.close()


def test_bad_worker_request_fails_without_leaking(client):
    jobs = client.app.state.jobs
    with jobs.mutex:
        job = jobs.submit({"mode": "demo", "inputs": {}, "options": {}, "example": "invalid"})
    value = finish(client, job)
    assert value["status"] == "failed"
    assert value["artifacts"] == []


def test_atomic_storage_and_identity(tmp_path):
    path = tmp_path / "value.json"
    write_json(path, {"value": 1})
    assert read_json(path) == {"value": 1}
    value = identity(path)
    assert validate_identity(value) == path
    path.write_text("changed")
    with pytest.raises(ValueError):
        validate_identity(value)
    assert not list(tmp_path.glob(".pending-*"))
