"""Run display names are validated, durable, and separate from run identity."""

import json

import pytest

pytest.importorskip("fastapi")

from dicomqc.api.jobs import Jobs
from test_api import AUTH, client
from test_api_lifecycle import DEMO, stopped_jobs


@pytest.mark.parametrize("status", ["queued", "running", "cancelled"])
def test_http_rename_trims_active_and_inactive_run_names(client, status):
    jobs = client.app.state.jobs
    jobs.stopping.set()
    jobs.thread.join()
    jobs.stopping.clear()
    job = jobs.submit(DEMO)
    if status != "queued":
        job["status"] = status
        jobs._save(job)
    directory = jobs.directory(job["id"])
    reports = directory / "reports"
    reports.mkdir()
    artifact = reports / "audit-report.html"
    artifact.write_text("unchanged")
    entries = {path.name for path in jobs.root.iterdir()}

    response = client.patch(
        f'/api/v1/jobs/{job["id"]}',
        headers=AUTH,
        json={"name": "  3TR baseline audit  "},
    )

    assert response.status_code == 200
    assert response.json()["name"] == "3TR baseline audit"
    assert response.json()["status"] == status
    assert jobs.get(job["id"])["name"] == "3TR baseline audit"
    assert jobs.directory(job["id"]) == directory
    assert {path.name for path in jobs.root.iterdir()} == entries
    assert artifact.read_text() == "unchanged"


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"name": "valid", "other": True},
        {"name": 123},
        {"name": "   "},
        {"name": "x" * 81},
        {"name": "line\nbreak"},
        {"name": "tab\tname"},
        {"name": "null\x00name"},
    ],
)
def test_http_rename_rejects_invalid_or_non_strict_bodies(client, payload):
    job = client.app.state.jobs.submit(DEMO)
    response = client.patch(f'/api/v1/jobs/{job["id"]}', headers=AUTH, json=payload)
    assert response.status_code == 422
    assert response.json() == {"detail": "Invalid request fields or options."}
    assert client.app.state.jobs.get(job["id"])["name"] is None


def test_http_rename_requires_authentication_and_known_run(client):
    job = client.app.state.jobs.submit(DEMO)
    url = f'/api/v1/jobs/{job["id"]}'
    assert client.patch(url, json={"name": "Private name"}).status_code == 401
    assert client.patch("/api/v1/jobs/missing", headers=AUTH, json={"name": "Name"}).status_code == 400


def test_renamed_job_persists_across_restart(tmp_path):
    jobs = stopped_jobs(tmp_path)
    root = jobs.root
    job = jobs.submit(DEMO)
    identifier = job["id"]
    try:
        updated = jobs.rename(identifier, "  Follow-up audit  ")
        assert updated["name"] == "Follow-up audit"
        stored = json.loads(jobs.db.execute("SELECT value FROM jobs WHERE id = ?", (identifier,)).fetchone()[0])
        assert stored["name"] == "Follow-up audit"
    finally:
        jobs.close()

    reopened = Jobs(root)
    try:
        assert reopened.get(identifier)["name"] == "Follow-up audit"
    finally:
        reopened.close()
