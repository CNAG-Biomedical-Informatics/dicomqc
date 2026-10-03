"""Read-only comparison of explicitly paired source and candidate DICOM files."""

from __future__ import annotations

import csv
import os
from collections import defaultdict
from dataclasses import dataclass, field, replace
from functools import partial
from itertools import islice
from pathlib import Path

from dicomqc.backend.base import DicomBackend, DicomReadError
from dicomqc.backend.diagnostics import read_metadata_safely
from dicomqc.backend.pydicom_backend import PydicomBackend
from dicomqc.model.metadata import MetadataRecord
from dicomqc.model.results import Finding, ScanResult, Severity
from dicomqc.parallel import (
    DEFAULT_THREADS, bounded_ordered_map, bounded_ordered_process_map, validate_threads,
)
from dicomqc.rules.builtin import evaluate_record
from dicomqc.rules.policy import Policy, evaluate_policy

COMPARE_PROFILE = "dataset-comparison-v0.1"
COMPARISON_BATCH_SIZE = 128


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
    def inaccessible(error: OSError) -> None:
        raise ValueError("Cannot inventory every input directory; check access permissions.") from error

    for directory, directories, files in os.walk(root, onerror=inaccessible, followlinks=False):
        for name in directories + files:
            path = Path(directory) / name
            if path.is_symlink():
                raise ValueError("Comparison inputs must not contain symbolic links.")
        for name in files:
            path = Path(directory) / name
            if not path.is_file():
                raise ValueError("Comparison inputs must contain only regular files and directories.")
            paths.add(path.relative_to(root).as_posix())
    return paths


def compare_datasets(
    source: Path, candidate: Path, manifest: Path, *, backend: DicomBackend | None = None,
    policy: Policy | None = None,
    threads: int = DEFAULT_THREADS,
    progress=None,
) -> ComparisonResult:
    """Check coverage, candidate metadata, and PatientID mapping consistency.

    The manifest is trusted pairing evidence, not proof of file correspondence.
    Paths and patient identifiers remain internal; reports use pair ordinals.
    """
    from dicomqc.progress import emit
    threads = validate_threads(threads)
    emit(progress, "discovery")
    source, candidate = comparison_roots(source, candidate)
    manifest = manifest.resolve()
    if source in manifest.parents or candidate in manifest.parents:
        raise ValueError("Keep the pairing manifest outside both input directories.")
    pairs = _manifest(manifest)
    inventories = [_inventory(source), _inventory(candidate)]
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

    numbered_pairs = ((number, pair, pair[0] in inventories[0], pair[1] in inventories[1])
                      for number, pair in enumerate(pairs, 1))
    if backend is None and threads > 1:
        batches = (_ComparisonBatch(tuple(batch), source, candidate, policy)
                   for batch in _pair_batches(numbered_pairs, COMPARISON_BATCH_SIZE))
        inspections = (inspection
                       for batch in bounded_ordered_process_map(_inspect_pair_batch, batches, workers=threads)
                       for inspection in batch)
    else:
        inspect_pair = partial(_inspect_pair, source=source, candidate=candidate, policy=policy,
                               reader=backend or PydicomBackend())
        inspections = bounded_ordered_map(inspect_pair, numbered_pairs, threads=threads)
    for number, inspection in enumerate(
        inspections, 1,
    ):
        records.extend(inspection.records)
        findings.extend(inspection.findings)
        skipped.update(inspection.skipped)
        readable_pairs += int(inspection.readable)
        if inspection.mapping is not None:
            mappings.append(inspection.mapping)
        emit(progress, "reading", number, len(pairs))

    emit(progress, "relationships", len(pairs), len(pairs))
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
        policy={"id": policy.id, "sha256": policy.sha256} if policy else None,
        comparison={"source_files": len(inventories[0]), "candidate_files": len(inventories[1]),
                    "manifest_pairs": len(pairs), "readable_pairs": readable_pairs,
                    "identity_pairs_checked": len(mappings)},
    )


@dataclass(frozen=True)
class _PairInspection:
    records: tuple[MetadataRecord, ...]
    findings: tuple[Finding, ...]
    skipped: dict[str, str]
    mapping: tuple[tuple[str, str], str, str] | None
    readable: bool


@dataclass(frozen=True)
class _ComparisonBatch:
    pairs: tuple[tuple[int, tuple[str, str], bool, bool], ...]
    source: Path
    candidate: Path
    policy: Policy | None


def _inspect_pair(
    numbered_pair: tuple[int, tuple[str, str], bool, bool], *, source: Path,
    candidate: Path, policy: Policy | None, reader: DicomBackend,
) -> _PairInspection:
    number, pair, source_exists, candidate_exists = numbered_pair
    loaded = []
    local_findings: list[Finding] = []
    local_skipped: dict[str, str] = {}
    local_records: list[MetadataRecord] = []

    def pair_error(rule: str, reference: str, message: str, recommendation: str) -> None:
        local_findings.append(_error_finding(rule, reference, message, recommendation))

    for side, (root, relative, exists) in enumerate(zip(
        (source, candidate), pair, (source_exists, candidate_exists),
    )):
        role = ("source", "candidate")[side]
        reference = f"pair-{number:06d}/{role}"
        if not exists:
            pair_error(f"missing_{role}", reference, f"The listed {role} file is missing.",
                       "Check the manifest and regenerate missing output files.")
            loaded.append(None)
            continue
        try:
            record = read_metadata_safely(reader, root / relative)
        except DicomReadError:
            local_skipped[reference] = "Cannot read DICOM metadata."
            pair_error(f"unreadable_{role}", reference, f"The {role} file is unreadable.",
                       "Inspect the file locally and rerun the comparison.")
            loaded.append(None)
            continue
        loaded.append(record)
        if side == 1:
            safe_record = replace(record, path=Path(reference))
            local_findings.extend(evaluate_record(safe_record))
            if policy is not None:
                local_findings.extend(evaluate_policy(safe_record, policy))
            # Do not serialize paths, UIDs, manufacturer, or other raw context.
            local_records.append(MetadataRecord(Path(reference), None, None, None, None, None, {}))
    before, after = loaded
    if before is None or after is None:
        return _PairInspection(tuple(local_records), tuple(local_findings), local_skipped, None, False)
    reference = f"pair-{number:06d}/candidate"
    if not before.patient_id or not after.patient_id:
        pair_error("missing_patient_id", reference, "A paired file has no usable PatientID.",
                   "Supply PatientID on both sides so identity consistency can be checked.")
        return _PairInspection(tuple(local_records), tuple(local_findings), local_skipped, None, True)
    issuer = before.issuer_of_patient_id or ""
    identity = (issuer, before.patient_id)
    mapping = (identity, after.patient_id, reference)
    if before.patient_id == after.patient_id:
        pair_error("unchanged_patient_id", reference, "PatientID was not changed.",
                   "Verify the de-identification process replaces the source identifier.")
    return _PairInspection(tuple(local_records), tuple(local_findings), local_skipped, mapping, True)


def _inspect_pair_batch(batch: _ComparisonBatch) -> tuple[_PairInspection, ...]:
    reader = PydicomBackend()
    inspect = partial(_inspect_pair, source=batch.source, candidate=batch.candidate,
                      policy=batch.policy, reader=reader)
    return tuple(inspect(pair) for pair in batch.pairs)


def _pair_batches(values, size: int):
    iterator = iter(values)
    while batch := tuple(islice(iterator, size)):
        yield batch


def _error_finding(rule: str, reference: str, message: str, recommendation: str) -> Finding:
    return Finding(
        rule_id=f"{COMPARE_PROFILE}.{rule}", profile_id=COMPARE_PROFILE,
        severity=Severity.ERROR, path=reference, message=message,
        recommendation=recommendation,
    )
