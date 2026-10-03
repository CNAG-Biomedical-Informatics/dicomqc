"""High-level scan orchestration."""

from __future__ import annotations

from dataclasses import dataclass, replace
from functools import partial
from itertools import islice
from pathlib import Path
import os
from typing import Iterable

from dicomqc.backend.base import DicomBackend, DicomReadError
from dicomqc.backend.pydicom_backend import PydicomBackend
from dicomqc.backend.diagnostics import read_metadata_safely
from dicomqc.model.metadata import MetadataRecord
from dicomqc.model.results import Finding, ScanResult
from dicomqc.parallel import (
    DEFAULT_THREADS, bounded_ordered_map, bounded_ordered_process_map, validate_threads,
)
from dicomqc.rules.builtin import DEFAULT_PROFILE_ID, evaluate_record
from dicomqc.rules.policy import Policy, evaluate_policy
from dicomqc.rules.uid import evaluate_uids
from dicomqc.vendor import summarize_vendors
from dicomqc.progress import Progress, emit

SCAN_BATCH_SIZE = 256


def scan_paths(
    paths: Iterable[str | Path],
    *,
    profile: str = DEFAULT_PROFILE_ID,
    backend: DicomBackend | None = None,
    cwd: Path | None = None,
    policy: Policy | None = None,
    vendor_summary: bool = False,
    uid_checks: bool = False,
    threads: int = DEFAULT_THREADS,
    progress: Progress | None = None,
) -> ScanResult:
    if profile != DEFAULT_PROFILE_ID:
        raise ValueError(f"Unknown profile: {profile}")

    threads = validate_threads(threads)
    root = (cwd or Path.cwd()).resolve()
    records: list[MetadataRecord] = []
    findings: list[Finding] = []
    skipped: dict[str, str] = {}

    emit(progress, "discovery")
    processed = 0
    files = _iter_files(paths)
    if backend is None and threads > 1:
        batches = (_ScanBatch(tuple(batch), root, profile, policy, uid_checks)
                   for batch in _batches(files, SCAN_BATCH_SIZE))
        inspections = (inspection
                       for batch in bounded_ordered_process_map(_inspect_batch, batches, workers=threads)
                       for inspection in batch)
    else:
        reader = backend or PydicomBackend()
        inspect = partial(_inspect_file, root=root, profile=profile, policy=policy,
                          uid_checks=uid_checks, reader=reader)
        inspections = bounded_ordered_map(inspect, files, threads=threads)
    for inspection in inspections:
        processed += 1
        if inspection.error is not None:
            skipped[inspection.display_path] = inspection.error
        else:
            assert inspection.record is not None
            records.append(inspection.record)
            findings.extend(inspection.findings)
        emit(progress, "reading", processed)

    uid_summary = None
    emit(progress, "relationships", processed, processed)
    if uid_checks:
        uid_findings, uid_summary = evaluate_uids(records)
        findings.extend(uid_findings)
    return ScanResult(profile_id=profile, records=records, findings=findings, skipped_files=skipped,
                      policy={"id": policy.id, "sha256": policy.sha256} if policy else None,
                      vendor_summary=summarize_vendors(records) if vendor_summary else None,
                      uid_checks=uid_summary)


@dataclass(frozen=True)
class _FileInspection:
    display_path: str
    record: MetadataRecord | None
    findings: tuple[Finding, ...]
    error: str | None


@dataclass(frozen=True)
class _ScanBatch:
    paths: tuple[Path, ...]
    root: Path
    profile: str
    policy: Policy | None
    uid_checks: bool


def _inspect_file(
    file_path: Path, *, root: Path, profile: str, policy: Policy | None,
    uid_checks: bool, reader: DicomBackend,
) -> _FileInspection:
    display_path = _display_path(file_path, root)
    try:
        record = (read_metadata_safely(reader, file_path, allow_uid_warnings=True)
                  if uid_checks else reader.read_metadata(file_path))
    except DicomReadError as exc:
        return _FileInspection(display_path, None, (), str(exc))

    record = replace(record, path=Path(display_path))
    local_findings = evaluate_record(record, profile_id=profile)
    if policy is not None:
        local_findings.extend(evaluate_policy(record, policy))
    return _FileInspection(display_path, record, tuple(local_findings), None)


def _inspect_batch(batch: _ScanBatch) -> tuple[_FileInspection, ...]:
    reader = PydicomBackend()
    inspect = partial(_inspect_file, root=batch.root, profile=batch.profile,
                      policy=batch.policy, uid_checks=batch.uid_checks, reader=reader)
    return tuple(inspect(path) for path in batch.paths)


def _batches(values: Iterable[Path], size: int) -> Iterable[tuple[Path, ...]]:
    iterator = iter(values)
    while batch := tuple(islice(iterator, size)):
        yield batch


def _iter_files(paths: Iterable[str | Path]) -> Iterable[Path]:
    for raw_path in paths:
        path = Path(raw_path)
        if path.is_dir():
            yield from _walk_directory(path)
        elif path.is_file() and not path.is_symlink():
            yield path
        else:
            # Preserve the reader's existing missing/special-path diagnostics.
            yield path


def _walk_directory(path: Path) -> Iterable[Path]:
    """Traverse deterministically without retaining the complete file tree."""
    with os.scandir(path) as directory:
        entries = sorted(directory, key=lambda entry: entry.name)
    for entry in entries:
        if entry.is_symlink():
            continue
        child = Path(entry.path)
        if entry.is_file(follow_symlinks=False):
            yield child
        elif entry.is_dir(follow_symlinks=False):
            yield from _walk_directory(child)


def _display_path(path: Path, root: Path) -> str:
    try:
        return str(Path(os.path.abspath(path)).relative_to(root))
    except ValueError:
        return str(path)
