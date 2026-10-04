"""Atomic state updates remain reliable while Windows readers hold a file."""

import os
from unittest.mock import Mock

import pytest

from dicomqc.api import storage


def sharing_error(code):
    error = PermissionError("File is in use")
    error.winerror = code
    return error


@pytest.mark.parametrize("code", [5, 32, 33])
def test_atomic_write_retries_windows_sharing_errors(tmp_path, monkeypatch, code):
    path = tmp_path / "progress.json"
    storage.write_json(path, {"completed": 1})
    replace = storage.os.replace
    calls = []

    def temporarily_locked(source, destination):
        calls.append(source)
        if len(calls) < 3:
            assert storage.read_json(path) == {"completed": 1}
            raise sharing_error(code)
        replace(source, destination)

    sleep = Mock()
    monkeypatch.setattr(storage.os, "replace", temporarily_locked)
    monkeypatch.setattr(storage.time, "sleep", sleep)
    storage.write_json(path, {"completed": 2})
    assert len(calls) == 3 and len(set(calls)) == 1
    assert sleep.call_count == 2
    assert storage.read_json(path) == {"completed": 2}
    assert list(tmp_path.iterdir()) == [path]


@pytest.mark.parametrize("code,attempts", [(5, 20), (32, 20), (33, 20), (None, 1), (19, 1)])
def test_atomic_write_still_fails_for_persistent_errors(tmp_path, monkeypatch, code, attempts):
    path = tmp_path / "progress.json"
    storage.write_json(path, {"completed": 1})
    replace = Mock(side_effect=sharing_error(code))
    sleep = Mock()
    monkeypatch.setattr(storage.os, "replace", replace)
    monkeypatch.setattr(storage.time, "sleep", sleep)
    with pytest.raises(PermissionError):
        storage.write_json(path, {"completed": 2})
    assert replace.call_count == attempts
    assert sleep.call_count == attempts - 1
    assert storage.read_json(path) == {"completed": 1}
    assert list(tmp_path.iterdir()) == [path]


@pytest.mark.skipif(os.name != "nt", reason="Windows file sharing semantics")
def test_atomic_write_waits_for_native_windows_reader(tmp_path, monkeypatch):
    path = tmp_path / "progress.json"
    storage.write_json(path, {"completed": 1})
    with path.open("rb") as reader:
        release_reader = Mock(side_effect=lambda delay: reader.close())
        monkeypatch.setattr(storage.time, "sleep", release_reader)
        storage.write_json(path, {"completed": 2})
        release_reader.assert_called_once_with(0.025)
    assert storage.read_json(path) == {"completed": 2}
    assert list(tmp_path.iterdir()) == [path]
