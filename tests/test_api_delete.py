"""Destructive run operations retain ownership and recoverable history."""

import json
import os
import shutil
from unittest.mock import Mock

import pytest

pytest.importorskip("fastapi")

from dicomqc.api.jobs import Jobs
from dicomqc.api import jobs as jobs_module
from test_api import AUTH, PRIVILEGED, client, finish, register
from test_api_lifecycle import DEMO, stopped_jobs


def terminal(jobs, status="cancelled"):
    job = jobs.submit(DEMO)
    job["status"] = status
    jobs._save(job)
    return job


@pytest.mark.parametrize("status", ["queued", "running"])
def test_delete_rejects_active_runs(tmp_path, status):
    jobs = stopped_jobs(tmp_path)
    job = terminal(jobs, status)
    directory = jobs.directory(job["id"])
    try:
        with pytest.raises(ValueError, match="inactive"):
            jobs.delete(job["id"])
        assert directory.is_dir()
        assert jobs.get(job["id"])["status"] == status
    finally:
        jobs.close()


def test_http_delete_preserves_inputs_other_runs_and_history(client, tmp_path):
    path = tmp_path / "input.dcm"
    path.write_bytes(b"source data must survive")
    handle = register(client, path)
    response = client.post("/api/v1/jobs", headers=AUTH, json={"mode": "scan", "inputs": {"paths": [handle]}})
    job = finish(client, response.json())
    assert job["status"] == "completed"
    jobs = client.app.state.jobs
    with jobs.mutex:
        other = terminal(jobs)
        directory = jobs.directory(job["id"])
        (directory / "outside-link").symlink_to(tmp_path, target_is_directory=True)
    url = f'/api/v1/jobs/{job["id"]}'
    assert client.delete(url).status_code == 401
    assert client.delete(url, headers=AUTH).status_code == 403
    response = client.delete(url, headers=PRIVILEGED)
    assert response.status_code == 200
    assert response.json() == {"id": job["id"], "status": "deleted"}
    assert not directory.exists()
    assert path.read_bytes() == b"source data must survive"
    assert jobs.get(other["id"])["status"] == "cancelled"
    assert jobs.directory(other["id"]).is_dir()
    assert client.get(url, headers=AUTH).status_code == 400
    assert client.delete(url, headers=PRIVILEGED).status_code == 400
    assert [entry["id"] for entry in jobs.list()] == [other["id"]]
    assert jobs.db.execute("SELECT id FROM run_directories").fetchall() == [(other["id"],)]


@pytest.mark.parametrize("replacement", [
    pytest.param(
        "root_symlink",
        marks=pytest.mark.skipif(os.name == "nt", reason="Windows prevents renaming an open workspace"),
    ),
    "run_symlink",
    "run_directory",
])
def test_delete_rejects_replaced_ownership(tmp_path, replacement):
    jobs = stopped_jobs(tmp_path)
    job = terminal(jobs)
    directory = jobs.directory(job["id"])
    if replacement == "root_symlink":
        moved = tmp_path / "moved"
        jobs.root.rename(moved)
        jobs.root.symlink_to(moved, target_is_directory=True)
    else:
        moved = tmp_path / "moved"
        directory.rename(moved)
        if replacement == "run_symlink":
            directory.symlink_to(moved, target_is_directory=True)
        else:
            directory.mkdir()
            (directory / "unrelated").write_text("keep")
    try:
        with pytest.raises(ValueError):
            jobs.delete(job["id"])
        assert jobs.get(job["id"])["status"] == "cancelled"
        assert moved.is_dir()
        if replacement == "run_directory":
            assert (directory / "unrelated").read_text() == "keep"
    finally:
        jobs.close()


@pytest.mark.parametrize("identifier", ["../outside", ".", "", "a" * 31, "a" * 32])
def test_delete_rejects_traversal_and_unknown_runs(tmp_path, identifier):
    jobs = stopped_jobs(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    try:
        with pytest.raises(ValueError):
            jobs.delete(identifier)
        assert outside.is_dir()
    finally:
        jobs.close()


@pytest.mark.parametrize("remove_all", [False, True])
@pytest.mark.parametrize("compatibility", [False, True])
def test_failed_delete_retains_row_and_retries_after_restart(tmp_path, monkeypatch, remove_all, compatibility):
    if compatibility:
        monkeypatch.setattr(jobs_module, "RMTREE_HAS_DIR_FD", False)
    jobs = stopped_jobs(tmp_path)
    job = terminal(jobs)
    directory = jobs.directory(job["id"])
    # Simulate a pre-migration run, whose identity is still in request.json.
    jobs.db.execute("DELETE FROM run_directories WHERE id = ?", (job["id"],))
    jobs.db.commit()
    original = jobs_module.remove_run_tree

    def fail(path, **kwargs):
        if remove_all:
            original(path, **kwargs)
        else:
            (directory / "request.json").unlink()
        raise OSError("interrupted deletion")

    with monkeypatch.context() as patch:
        patch.setattr(jobs_module, "remove_run_tree", fail)
        with pytest.raises(OSError):
            jobs.delete(job["id"])
    assert jobs.get(job["id"])["status"] == "cancelled"
    assert not (directory / "request.json").exists()
    jobs.close()
    recovered = Jobs(tmp_path / "runs")
    try:
        assert recovered.delete(job["id"])["status"] == "deleted"
        assert not directory.exists()
        assert recovered.list() == []
    finally:
        recovered.close()


def test_delete_without_ownership_evidence_fails_closed(tmp_path):
    jobs = stopped_jobs(tmp_path)
    job = terminal(jobs)
    directory = jobs.directory(job["id"])
    jobs.db.execute("DELETE FROM run_directories")
    jobs.db.commit()
    (directory / "request.json").write_text(json.dumps(DEMO))
    try:
        with pytest.raises(ValueError, match="ownership"):
            jobs.delete(job["id"])
        assert directory.exists()
        assert len(jobs.list()) == 1
    finally:
        jobs.close()


def test_delete_reaps_cancelled_worker_before_removing_history(tmp_path):
    jobs = stopped_jobs(tmp_path)
    job = terminal(jobs)
    jobs.current = job["id"]
    jobs.process = Mock(poll=Mock(return_value=None))
    guard = jobs.guard = Mock()
    try:
        with pytest.raises(ValueError, match="not stopped"):
            jobs.delete(job["id"])
        jobs.process.poll.return_value = 0
        assert jobs.delete(job["id"])["status"] == "deleted"
        guard.close.assert_called_once()
        assert jobs.current is jobs.process is jobs.guard is None
        jobs._tick()
        assert not jobs.stopping.is_set()
    finally:
        jobs.close()


@pytest.mark.skipif(not shutil.rmtree.avoids_symlink_attacks, reason="Descriptor-based rmtree required")
def test_delete_checks_open_workspace_identity(tmp_path, monkeypatch):
    jobs = stopped_jobs(tmp_path)
    job = terminal(jobs)
    original = os.fstat

    def replaced(fd):
        value = original(fd)
        return type("Changed", (), {"st_dev": value.st_dev, "st_ino": value.st_ino + 1})()

    try:
        with monkeypatch.context() as patch:
            patch.setattr(jobs_module.os, "fstat", replaced)
            with pytest.raises(ValueError, match="Workspace changed"):
                jobs.delete(job["id"])
        assert jobs.directory(job["id"]).exists()
        assert len(jobs.list()) == 1
    finally:
        jobs.close()


@pytest.mark.skipif(not shutil.rmtree.avoids_symlink_attacks, reason="Descriptor operations required")
def test_python310_delete_preserves_link_targets(tmp_path, monkeypatch):
    monkeypatch.setattr(jobs_module, "RMTREE_HAS_DIR_FD", False)
    jobs = stopped_jobs(tmp_path)
    job = terminal(jobs)
    directory = jobs.directory(job["id"])
    outside = tmp_path / "input.dcm"
    outside.write_bytes(b"original DICOM")
    nested = directory / "reports" / "nested"
    nested.mkdir(parents=True)
    (nested / "report.txt").write_text("report")
    (nested / "input-link").symlink_to(outside)
    (nested / "directory-link").symlink_to(tmp_path, target_is_directory=True)
    (nested / "broken-link").symlink_to(tmp_path / "missing")
    try:
        assert jobs.delete(job["id"])["status"] == "deleted"
        assert not directory.exists()
        assert outside.read_bytes() == b"original DICOM"
        assert jobs.list() == []
    finally:
        jobs.close()


@pytest.mark.skipif(not shutil.rmtree.avoids_symlink_attacks, reason="Descriptor operations required")
@pytest.mark.parametrize("replacement", ["directory", "symlink"])
def test_python310_delete_rejects_directory_swap(tmp_path, monkeypatch, replacement):
    monkeypatch.setattr(jobs_module, "RMTREE_HAS_DIR_FD", False)
    parent = tmp_path / "parent"
    parent.mkdir()
    target = parent / "run"
    target.mkdir()
    moved = parent / "moved"
    original_open = os.open
    fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY)

    def swap(path, flags, **kwargs):
        target.rename(moved)
        if replacement == "symlink":
            target.symlink_to(moved, target_is_directory=True)
        else:
            target.mkdir()
        return original_open(path, flags, **kwargs)

    try:
        with monkeypatch.context() as patch:
            patch.setattr(jobs_module.os, "open", swap)
            with pytest.raises((ValueError, OSError)):
                jobs_module.remove_run_tree("run", dir_fd=fd)
        assert moved.is_dir()
        assert target.exists()
    finally:
        os.close(fd)
