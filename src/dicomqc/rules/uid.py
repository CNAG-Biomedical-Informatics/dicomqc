"""Bounded, dataset-wide checks of top-level instance identifiers."""

from __future__ import annotations

from collections import defaultdict
import re

from dicomqc.model.metadata import MetadataRecord, ValueState
from dicomqc.model.results import Finding, Severity

UID_PROFILE = "uid-integrity-v0.1"
UID_FIELDS = {
    "StudyInstanceUID": "(0020,000D)",
    "SeriesInstanceUID": "(0020,000E)",
    "SOPInstanceUID": "(0008,0018)",
}
ENCODING_REF = "DICOM PS3.5 Section 9"
HIERARCHY_REF = "DICOM PS3.3 Section A.1.2"
_SYNTAX = re.compile(r"(?:0|[1-9][0-9]*)(?:\.(?:0|[1-9][0-9]*))*", re.ASCII)


def evaluate_uids(records: list[MetadataRecord]) -> tuple[list[Finding], dict]:
    """Check normalized values only; retain identifiers internally, never in findings.

    Missing/empty fields are coverage gaps, not IOD-required-attribute findings.
    Only valid, scalar UI values participate in cross-file associations.
    """
    findings = []
    coverage = {key: {"valid": 0, "absent_or_empty": 0, "invalid": 0} for key in UID_FIELDS}
    values = []
    roles: dict[str, set[str]] = defaultdict(set)
    series_studies: dict[str, set[str]] = defaultdict(set)
    sop_studies: dict[str, set[str]] = defaultdict(set)
    sop_series: dict[str, set[str]] = defaultdict(set)

    def finding(record, keyword, rule, message, recommendation, reference):
        findings.append(Finding(
            rule_id=f"{UID_PROFILE}.{rule}", profile_id=UID_PROFILE,
            severity=Severity.ERROR, path=str(record.path), keyword=keyword,
            tag=UID_FIELDS[keyword], value_state=ValueState.PRESENT,
            message=message, recommendation=recommendation, standard_refs=(reference,),
        ))

    for record in records:
        row = {}
        top_level = {tag.tag: tag for tag in record.tags.values() if not tag.is_nested and not tag.dataset_path}
        for keyword, number in UID_FIELDS.items():
            tag = top_level.get(number)
            if tag is None or tag.value_state != ValueState.PRESENT:
                coverage[keyword]["absent_or_empty"] += 1
                continue
            value = tag.raw_value
            if tag.vr != "UI" or not isinstance(value, str) or not (0 < len(value) <= 64) or not _SYNTAX.fullmatch(value):
                coverage[keyword]["invalid"] += 1
                finding(record, keyword, "invalid_format",
                        "An instance identifier is not a single UI value with valid UID syntax.",
                        "Check its VR, multiplicity, numeric components, leading zeros, and 64-character limit in the source pipeline.",
                        ENCODING_REF)
                continue
            coverage[keyword]["valid"] += 1
            row[keyword] = value
            roles[value].add(keyword)
        study, series, sop = (row.get(key) for key in UID_FIELDS)
        if series and study:
            series_studies[series].add(study)
        if sop and study:
            sop_studies[sop].add(study)
        if sop and series:
            sop_series[sop].add(series)
        values.append(row)

    for record, row in zip(records, values):
        for keyword, value in row.items():
            if len(roles[value]) > 1:
                finding(record, keyword, "role_reuse",
                        "The same UID is used for different study, series, or instance roles in this scan.",
                        "Give distinct entities distinct UIDs and update their references consistently in the source pipeline.",
                        ENCODING_REF)
        series = row.get("SeriesInstanceUID")
        if series and len(series_studies[series]) > 1:
            finding(record, "SeriesInstanceUID", "series_study_conflict",
                    "A series UID is associated with more than one study UID in this scan.",
                    "Review the affected files and correct the series-to-study mapping before re-exporting.", HIERARCHY_REF)
        sop = row.get("SOPInstanceUID")
        if sop and (len(sop_studies[sop]) > 1 or len(sop_series[sop]) > 1):
            finding(record, "SOPInstanceUID", "instance_context_conflict",
                    "An instance UID is associated with conflicting study or series UIDs in this scan.",
                    "Check whether different instances received the same UID or an instance was assigned to the wrong series.", HIERARCHY_REF)
    return findings, {
        "profile_id": UID_PROFILE, "files_checked": len(records), "fields": coverage,
        "series_study_pairs_checked": sum("StudyInstanceUID" in row and "SeriesInstanceUID" in row for row in values),
        "complete_hierarchies_checked": sum(len(row) == 3 for row in values),
    }
