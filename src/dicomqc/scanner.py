"""High-level scan orchestration."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Iterable

from dicomqc.backend.base import DicomBackend, DicomReadError
from dicomqc.backend.pydicom_backend import PydicomBackend
from dicomqc.model.metadata import MetadataRecord
from dicomqc.model.results import Finding, ScanResult
from dicomqc.rules.builtin import DEFAULT_PROFILE_ID, evaluate_record


def scan_paths(
    paths: Iterable[str | Path],
    *,
    profile: str = DEFAULT_PROFILE_ID,
    backend: DicomBackend | None = None,
    cwd: Path | None = None,
) -> ScanResult:
    if profile != DEFAULT_PROFILE_ID:
        raise ValueError(f"Unknown profile: {profile}")

    root = (cwd or Path.cwd()).resolve()
    reader = backend or PydicomBackend()
    records: list[MetadataRecord] = []
    findings: list[Finding] = []
    skipped: dict[str, str] = {}

    for file_path in _iter_files(paths):
        display_path = _display_path(file_path, root)
        try:
            record = reader.read_metadata(file_path)
        except DicomReadError as exc:
            skipped[display_path] = str(exc)
            continue

        record = replace(record, path=Path(display_path))
        records.append(record)
        findings.extend(evaluate_record(record, profile_id=profile))

    return ScanResult(profile_id=profile, records=records, findings=findings, skipped_files=skipped)


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
