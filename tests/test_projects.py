"""Portable desktop sessions use the same synthetic fixtures as engine tests."""

import json
from pathlib import Path
import shutil
import zipfile

import pytest

pytest.importorskip("fastapi")

from dicomqc.api.jobs import Jobs
from dicomqc.api.projects import open_project, save_project
from dicomqc.fixtures import write_synthetic_dicom_fixtures
from test_api import AUTH, PRIVILEGED, client, finish, register


def settings(inputs=None):
    return {"format": "dicomqc-project", "version": 1, "mode": "scan", "inputs": inputs or {},
            "options": {"threads": 1, "uid_checks": False, "vendor_summary": False, "multiqc": False}}


def test_portable_project_preserves_example_runs_and_reports(client, tmp_path):
    original = client.app.state.jobs
    identifiers = []
    for example in ("scan", "policy", "compare"):
        submitted = client.post('/api/v1/jobs', headers=AUTH, json={"mode": "demo", "example": example}).json()
        run = finish(client, submitted)
        assert run["status"] == "completed"
        identifiers.append(run["id"])
    original.rename(identifiers[0], "Baseline privacy")
    policy = tmp_path / "policy.yaml"
    policy.write_text("version: 1\nid: project\nrules:\n  - id: comments\n    keyword: PatientComments\n    check: absent_or_empty\n")
    dicom = tmp_path / "dicom"
    write_synthetic_dicom_fixtures(dicom)
    run = finish(client, client.post('/api/v1/jobs', headers=AUTH, json={"mode": "scan", "inputs": {
        "paths": [register(client, dicom)], "policy": [register(client, policy)]}}).json())
    assert run["status"] == "completed"
    assert "project-policy.yaml" in run["artifacts"]
    target = tmp_path / "Study.dicomqc"
    response = client.post('/api/v1/projects/save/local', headers=PRIVILEGED,
                           json={"path": str(target), "project": settings({"paths": [str(dicom)], "policy": [str(policy)]})})
    assert response.status_code == 200, response.text
    with zipfile.ZipFile(target) as archive:
        assert not any(name.endswith((".dcm", ".sqlite")) or name.endswith("request.json") for name in archive.namelist())
        assert "inputs/policy-0.yaml" in archive.namelist()
    expected = original.list()
    reviews = {run["id"]: original.review(run["id"]) for run in expected}
    artifacts = {(run["id"], index): original.artifact(run["id"], index).read_bytes()
                 for run in expected for index in range(len(run["artifacts"]))}
    original.close()
    shutil.rmtree(original.root)
    policy.unlink()
    shutil.rmtree(dicom)
    moved = tmp_path / "Moved.dicomqc"
    target.rename(moved)
    storage = tmp_path / "internal"
    storage.mkdir()
    project = open_project(moved, storage)
    assert Path(project["inputs"]["policy"][0]).read_text().startswith("version: 1")
    assert project["inputs"]["paths"] == [str(dicom)]
    restored = Jobs(Path(project["output"]))
    try:
        assert restored.list() == expected
        for run in expected:
            assert restored.review(run["id"]) == reviews[run["id"]]
        for (identifier, index), content in artifacts.items():
            assert restored.artifact(identifier, index).read_bytes() == content
        second = tmp_path / "Copy.dicomqc"
        save_project(restored, second, project)
        assert second.is_file()
        assert restored.delete(identifiers[0]) is not None
    finally:
        restored.close()


def test_project_endpoints_require_local_authorization(client, tmp_path):
    for action, payload in [("save", {"path": str(tmp_path / "x.dicomqc"), "project": settings()}),
                            ("open", {"path": str(tmp_path / "x.dicomqc"), "storage": str(tmp_path)})]:
        response = client.post(f'/api/v1/projects/{action}/local', headers=AUTH, json=payload)
        assert response.status_code == 403


def test_save_rejects_active_runs_and_preserves_existing_file(client, tmp_path):
    jobs = client.app.state.jobs
    jobs.stopping.set()
    jobs.thread.join()
    jobs.stopping.clear()
    jobs.submit({"mode": "demo", "example": "scan", "inputs": {}, "options": {}})
    target = tmp_path / "previous.dicomqc"
    target.write_bytes(b"previous version")
    with pytest.raises(ValueError, match="Finish or cancel"):
        save_project(jobs, target, settings())
    assert target.read_bytes() == b"previous version"


@pytest.mark.parametrize("member", ["../escape", "/absolute", "runs/../escape", "inputs/../../escape", "inputs\\escape", "unrelated"])
def test_archive_rejects_unsafe_members_and_cleans_up(tmp_path, member):
    storage = tmp_path / "storage"
    storage.mkdir()
    source = tmp_path / "unsafe.dicomqc"
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr(member, "bad")
    with pytest.raises(ValueError):
        open_project(source, storage)
    assert list(storage.iterdir()) == []


def test_corrupt_archive_and_missing_report_are_rejected(tmp_path):
    source = tmp_path / "bad.dicomqc"
    source.write_text("not an archive")
    with pytest.raises(ValueError):
        open_project(source, tmp_path)


@pytest.mark.parametrize("change", [
    {"format": "other"}, {"mode": "execute"}, {"inputs": {"bad": []}},
    {"inputs": {"paths": "not a list"}}, {"inputs": {"paths": ["relative/path"]}},
    {"unknown": True},
])
def test_save_rejects_invalid_settings(client, tmp_path, change):
    with pytest.raises(ValueError):
        save_project(client.app.state.jobs, tmp_path / "x.dicomqc", {**settings(), **change})


def test_failed_atomic_save_keeps_previous_project(client, tmp_path, monkeypatch):
    from dicomqc.api import projects
    target = tmp_path / "existing.dicomqc"
    target.write_bytes(b"previous snapshot")
    def fail(*args):
        raise OSError("disk full")
    monkeypatch.setattr(projects.os, "replace", fail)
    with pytest.raises(OSError):
        save_project(client.app.state.jobs, target, settings())
    assert target.read_bytes() == b"previous snapshot"
    assert not list(tmp_path.glob('.dicomqc-*'))


def test_save_rejects_input_and_workspace_locations(client, tmp_path):
    jobs = client.app.state.jobs
    for target, project in [(tmp_path / "wrong.json", settings()),
                            (jobs.root / "bad.dicomqc", settings()),
                            (tmp_path / "bad.dicomqc", settings({"paths": [str(tmp_path)]}))]:
        with pytest.raises(ValueError):
            save_project(jobs, target, project)


def test_archive_limits_and_symlinks(tmp_path, monkeypatch):
    from dicomqc.api import projects
    source = tmp_path / "invalid.dicomqc"
    with zipfile.ZipFile(source, "w") as archive:
        entry = zipfile.ZipInfo("inputs/policy-0.yaml")
        entry.external_attr = 0o120777 << 16
        archive.writestr(entry, "/outside")
    with pytest.raises(ValueError):
        open_project(source, tmp_path)
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr("project.json", json.dumps({**settings(), "version": 2}))
        archive.writestr("runs.json", "[]")
    monkeypatch.setattr(projects, "MAX_EXPANDED", 1)
    with pytest.raises(ValueError):
        open_project(source, tmp_path)
    monkeypatch.setattr(projects, "MAX_EXPANDED", 10000)
    monkeypatch.setattr(projects, "MAX_METADATA", 1)
    with pytest.raises(ValueError):
        open_project(source, tmp_path)


@pytest.mark.parametrize("project,runs", [
    ({**settings(), "version": 1}, []),
    ({**settings(), "version": 2}, [{"id": "invalid", "status": "completed"}]),
    ({**settings(), "version": 2}, [{"id": "a" * 32, "status": "completed", "artifacts": []}]),
    ({**settings({"policy": ["inputs/policy-0.yaml"]}), "version": 2}, []),
])
def test_archive_rejects_invalid_metadata(tmp_path, project, runs):
    source = tmp_path / "invalid.dicomqc"
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr("project.json", json.dumps(project))
        archive.writestr("runs.json", json.dumps(runs))
    with pytest.raises(ValueError):
        open_project(source, tmp_path)
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr("project.json", json.dumps({**settings(), "version": 2}))
        archive.writestr("runs.json", json.dumps([{"id": "a" * 32, "status": "completed", "artifacts": ["missing.html"]}]))
    with pytest.raises(ValueError):
        open_project(source, tmp_path)
