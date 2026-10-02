"""Read-only comparison of explicitly paired source and candidate DICOM files."""

from __future__ import annotations

import csv
import logging
import threading
import warnings
from collections import defaultdict
from dataclasses import dataclass, field, replace
from pathlib import Path

from dicomqc.backend.base import DicomBackend, DicomReadError
from dicomqc.backend.pydicom_backend import PydicomBackend
from dicomqc.model.metadata import MetadataRecord, ValueState
from dicomqc.model.results import Finding, ScanResult, Severity
from dicomqc.rules.builtin import evaluate_record

COMPARE_PROFILE = "dataset-comparison-v0.1"


@dataclass(frozen=True)
class ComparisonResult(ScanResult):
    comparison: dict[str, int] = field(default_factory=dict)

    @property
    def files_failed(self) -> int:
        # Missing source files are findings, not successfully scanned candidates.
        scanned = {str(record.path) for record in self.records}
        return len({f.path for f in self.findings if f.severity == Severity.ERROR} & scanned)


def comparison_roots(source: Path, candidate: Path) -> tuple[Path, Path]:
    source, candidate = source.resolve(), candidate.resolve()
    if not source.is_dir() or not candidate.is_dir():
        raise ValueError("Source and candidate must be existing directories.")
    if source == candidate or source in candidate.parents or candidate in source.parents:
        raise ValueError("Source and candidate directories must be separate and must not overlap.")
    return source, candidate


def _manifest(path: Path) -> list[tuple[str, str]]:
    try:
        with path.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle, strict=True)
            if reader.fieldnames != ["source", "candidate"]:
                raise ValueError("Manifest header must be exactly: source,candidate")
            pairs = []
            seen = [set(), set()]
            for number, row in enumerate(reader, 1):
                values = [row.get("source"), row.get("candidate")]
                if None in row or any(not value for value in values):
                    raise ValueError(f"Manifest pair {number} must contain two paths.")
                for index, value in enumerate(values):
                    relative = Path(value)
                    if relative.is_absolute() or ".." in relative.parts or relative == Path("."):
                        raise ValueError(f"Manifest pair {number} needs paths relative to each root.")
                    normalized = relative.as_posix()
                    if normalized in seen[index]:
                        raise ValueError(f"Manifest pair {number} repeats a file; pairing must be one-to-one.")
                    seen[index].add(normalized)
                    values[index] = normalized
                pairs.append(tuple(values))
    except (OSError, UnicodeError, csv.Error) as exc:
        raise ValueError("Cannot read the pairing manifest as UTF-8 CSV.") from exc
    if not pairs:
        raise ValueError("The pairing manifest must contain at least one pair.")
    return pairs


def _inventory(root: Path) -> set[str]:
    paths = set()
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ValueError("Comparison inputs must not contain symbolic links.")
        if path.is_file():
            paths.add(path.relative_to(root).as_posix())
    return paths


class _HideParserDetails(logging.Filter):
    """Keep pydicom diagnostics for this read out of application logs."""

    def __init__(self) -> None:
        super().__init__()
        self.thread = threading.get_ident()

    def filter(self, record: logging.LogRecord) -> bool:
        return record.thread != self.thread


def _read(reader: DicomBackend, path: Path) -> MetadataRecord:
    logger = logging.getLogger("pydicom")
    log_filter = _HideParserDetails()
    logger.addFilter(log_filter)
    try:
        with warnings.catch_warnings(record=True) as diagnostics:
            warnings.simplefilter("always")
            record = reader.read_metadata(path)
        if diagnostics:
            raise DicomReadError("DICOM parser reported a warning.")
        return record
    finally:
        logger.removeFilter(log_filter)


def compare_datasets(
    source: Path, candidate: Path, manifest: Path, *, backend: DicomBackend | None = None
) -> ComparisonResult:
    """Check coverage, candidate metadata, and PatientID mapping consistency.

    The manifest is trusted pairing evidence, not proof of file correspondence.
    Paths and patient identifiers remain internal; reports use pair ordinals.
    """
    source, candidate = comparison_roots(source, candidate)
    manifest = manifest.resolve()
    if source in manifest.parents or candidate in manifest.parents:
        raise ValueError("Keep the pairing manifest outside both input directories.")
    pairs = _manifest(manifest)
    inventories = [_inventory(source), _inventory(candidate)]
    reader = backend or PydicomBackend()
    findings: list[Finding] = []
    skipped: dict[str, str] = {}
    records = []
    mappings = []
    readable_pairs = 0

    def error(rule: str, reference: str, message: str, recommendation: str) -> None:
        findings.append(Finding(
            rule_id=f"{COMPARE_PROFILE}.{rule}", profile_id=COMPARE_PROFILE,
            severity=Severity.ERROR, path=reference, message=message,
            recommendation=recommendation,
        ))

    for side, inventory in enumerate(inventories):
        role = ("source", "candidate")[side]
        unpaired = sorted(inventory - {pair[side] for pair in pairs})
        for ordinal, _ in enumerate(unpaired, 1):
            error(f"unpaired_{role}", f"unpaired-{role}-{ordinal:06d}",
                  f"A {role} file is not covered by the manifest.",
                  "Check the complete input inventory and update the pairing manifest.")

    for number, pair in enumerate(pairs, 1):
        loaded = []
        for side, (root, relative) in enumerate(zip((source, candidate), pair)):
            role = ("source", "candidate")[side]
            reference = f"pair-{number:06d}/{role}"
            if relative not in inventories[side]:
                error(f"missing_{role}", reference, f"The listed {role} file is missing.",
                      "Check the manifest and regenerate missing output files.")
                loaded.append(None)
                continue
            try:
                record = _read(reader, root / relative)
            except DicomReadError:
                # Parser exception messages can contain identifiers or file paths.
                skipped[reference] = "Cannot read DICOM metadata."
                error(f"unreadable_{role}", reference, f"The {role} file is unreadable.",
                      "Inspect the file locally and rerun the comparison.")
                loaded.append(None)
                continue
            loaded.append(record)
            if side == 1:
                safe_record = replace(record, path=Path(reference))
                findings.extend(evaluate_record(safe_record))
                # Do not serialize paths, UIDs, manufacturer, or other raw context.
                records.append(MetadataRecord(Path(reference), None, None, None, None, None, {}))
        before, after = loaded
        if before is None or after is None:
            continue
        readable_pairs += 1
        reference = f"pair-{number:06d}/candidate"
        if not before.patient_id or not after.patient_id:
            error("missing_patient_id", reference, "A paired file has no usable PatientID.",
                  "Supply PatientID on both sides so identity consistency can be checked.")
            continue
        # Issuer distinguishes source identifiers assigned by different institutions.
        issuer_tag = before.by_keyword("IssuerOfPatientID")
        issuer = str(issuer_tag.raw_value).strip() if issuer_tag and issuer_tag.value_state == ValueState.PRESENT else ""
        identity = (issuer, before.patient_id)
        mappings.append((identity, after.patient_id, reference))
        if before.patient_id == after.patient_id:
            error("unchanged_patient_id", reference, "PatientID was not changed.",
                  "Verify the de-identification process replaces the source identifier.")

    forward: dict[tuple[str, str], set[str]] = defaultdict(set)
    reverse: dict[str, set[tuple[str, str]]] = defaultdict(set)
    for identity, pseudonym, _ in mappings:
        forward[identity].add(pseudonym)
        reverse[pseudonym].add(identity)
    for identity, pseudonym, reference in mappings:
        if len(forward[identity]) > 1:
            error("inconsistent_pseudonym", reference, "One source patient maps to multiple PatientIDs.",
                  "Use the same pseudonym for every file belonging to this source patient.")
        if len(reverse[pseudonym]) > 1:
            error("pseudonym_collision", reference, "Multiple source patients share one output PatientID.",
                  "Assign a distinct pseudonym to each source patient.")

    return ComparisonResult(
        profile_id=COMPARE_PROFILE, records=records, findings=findings, skipped_files=skipped,
        comparison={"source_files": len(inventories[0]), "candidate_files": len(inventories[1]),
                    "manifest_pairs": len(pairs), "readable_pairs": readable_pairs,
                    "identity_pairs_checked": len(mappings)},
    )
