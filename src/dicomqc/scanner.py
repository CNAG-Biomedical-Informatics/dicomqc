"""High-level scan orchestration."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Iterable

from dicomqc.backend.base import DicomBackend, DicomReadError
from dicomqc.backend.pydicom_backend import PydicomBackend
from dicomqc.backend.diagnostics import read_metadata_safely
from dicomqc.model.metadata import MetadataRecord
from dicomqc.model.results import Finding, ScanResult
from dicomqc.rules.builtin import DEFAULT_PROFILE_ID, evaluate_record
from dicomqc.rules.policy import Policy, evaluate_policy
from dicomqc.rules.uid import evaluate_uids
from dicomqc.vendor import summarize_vendors
from dicomqc.progress import Progress, emit


def scan_paths(
    paths: Iterable[str | Path],
    *,
    profile: str = DEFAULT_PROFILE_ID,
    backend: DicomBackend | None = None,
    cwd: Path | None = None,
    policy: Policy | None = None,
    vendor_summary: bool = False,
    uid_checks: bool = False,
    progress: Progress | None = None,
) -> ScanResult:
    if profile != DEFAULT_PROFILE_ID:
        raise ValueError(f"Unknown profile: {profile}")

    root = (cwd or Path.cwd()).resolve()
    reader = backend or PydicomBackend()
    records: list[MetadataRecord] = []
    findings: list[Finding] = []
    skipped: dict[str, str] = {}

    emit(progress, "discovery")
    processed = 0
    for file_path in _iter_files(paths):
        processed += 1
        emit(progress, "reading", processed - 1)
        display_path = _display_path(file_path, root)
        try:
            record = (read_metadata_safely(reader, file_path, allow_uid_warnings=True)
                      if uid_checks else reader.read_metadata(file_path))
        except DicomReadError as exc:
            skipped[display_path] = str(exc)
            continue

        record = replace(record, path=Path(display_path))
        records.append(record)
        findings.extend(evaluate_record(record, profile_id=profile))
        if policy is not None:
            findings.extend(evaluate_policy(record, policy))

    uid_summary = None
    emit(progress, "relationships", processed, processed)
    if uid_checks:
        uid_findings, uid_summary = evaluate_uids(records)
        findings.extend(uid_findings)
    return ScanResult(profile_id=profile, records=records, findings=findings, skipped_files=skipped,
                      policy={"id": policy.id, "sha256": policy.sha256} if policy else None,
                      vendor_summary=summarize_vendors(records) if vendor_summary else None,
                      uid_checks=uid_summary)


def _iter_files(paths: Iterable[str | Path]) -> Iterable[Path]:
    for raw_path in paths:
        path = Path(raw_path)
        if path.is_dir():
            for child in sorted(path.rglob("*")):
                if child.is_file() and not child.is_symlink():
                    yield child
        elif path.is_file() and not path.is_symlink():
            yield path
        else:
            yield path


def _display_path(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root))
    except ValueError:
        return str(path)
