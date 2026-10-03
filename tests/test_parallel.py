from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest

from dicomqc.fixtures import write_large_fixtures
from dicomqc.model.metadata import MetadataRecord
from dicomqc import parallel
from dicomqc import scanner
from dicomqc.parallel import (
    DEFAULT_THREADS, MAX_THREADS, bounded_ordered_map, bounded_ordered_process_map,
    validate_threads,
)
from dicomqc.scanner import _ScanBatch, _inspect_batch, scan_paths


class ConcurrentBackend:
    def __init__(self) -> None:
        self.active = 0
        self.maximum = 0
        self.lock = threading.Lock()

    def read_metadata(self, path: Path) -> MetadataRecord:
        with self.lock:
            self.active += 1
            self.maximum = max(self.maximum, self.active)
        try:
            time.sleep(0.02)
            return MetadataRecord(path, None, None, None, None, None, {})
        finally:
            with self.lock:
                self.active -= 1


def test_scan_parallelizes_files_but_preserves_order(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    for name in ("c.dcm", "a.dcm", "b.dcm", "d.dcm", "f.dcm", "e.dcm"):
        (data / name).touch()
    backend = ConcurrentBackend()

    workers = min(4, MAX_THREADS)
    result = scan_paths([data], backend=backend, cwd=tmp_path, threads=workers)

    assert backend.maximum > 1 if workers > 1 else backend.maximum == 1
    assert [record.path.as_posix() for record in result.records] == [
        f"data/{name}.dcm" for name in "abcdef"
    ]


def test_bounded_map_returns_input_order():
    def delayed(value):
        time.sleep((4 - value) * 0.002)
        return value * 2

    assert list(bounded_ordered_map(delayed, range(5), threads=min(3, MAX_THREADS))) == [0, 2, 4, 6, 8]
    assert list(bounded_ordered_map(delayed, range(3), threads=1)) == [0, 2, 4]


@pytest.mark.skipif(MAX_THREADS < 2, reason="requires two logical processors")
def test_process_workers_match_serial_scan(tmp_path, monkeypatch):
    data = tmp_path / "data"
    write_large_fixtures(data, 6)

    serial = scan_paths([data], cwd=tmp_path, threads=1)
    monkeypatch.setattr(scanner, "SCAN_BATCH_SIZE", 1)
    parallel_result = scan_paths([data], cwd=tmp_path, threads=2)

    assert parallel_result.records == serial.records
    assert parallel_result.findings == serial.findings
    batch = _ScanBatch(tuple(sorted(data.iterdir())), tmp_path, serial.profile_id, None, False)
    assert len(_inspect_batch(batch)) == 6


def _double(value):
    return value * 2


@pytest.mark.skipif(MAX_THREADS < 2, reason="requires two logical processors")
def test_bounded_process_map_returns_input_order():
    assert list(bounded_ordered_process_map(_double, range(6), workers=2)) == [0, 2, 4, 6, 8, 10]


@pytest.mark.parametrize("value", [0, MAX_THREADS + 1, True, 1.5, "4"])
def test_thread_count_is_strictly_bounded(value):
    with pytest.raises(ValueError, match=rf"between 1 and {MAX_THREADS}"):
        validate_threads(value)


def test_default_never_exceeds_available_hardware():
    assert DEFAULT_THREADS == min(4, MAX_THREADS)


def test_available_threads_falls_back_to_cpu_count(monkeypatch):
    monkeypatch.delattr(parallel.os, "sched_getaffinity", raising=False)
    monkeypatch.setattr(parallel.os, "cpu_count", lambda: None)

    assert parallel._available_threads() == 1
