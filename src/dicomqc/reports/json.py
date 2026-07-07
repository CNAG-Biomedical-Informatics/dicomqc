"""Redaction-safe JSON reports."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from dicomqc import __version__
from dicomqc.model.metadata import MetadataRecord
from dicomqc.model.results import Finding, ScanResult


def result_to_dict(result: ScanResult) -> dict[str, Any]:
    return {
        "tool": {"name": "dicomqc", "version": __version__},
        "profile_id": result.profile_id,
        "summary": {
            "files_scanned": result.files_scanned,
            "files_passed": result.files_passed,
            "files_failed": result.files_failed,
            "errors": result.error_count,
            "warnings": result.warning_count,
            "info": result.info_count,
            "skipped_files": len(result.skipped_files),
        },
        "records": [_record_to_dict(record) for record in result.records],
        "findings": [_finding_to_dict(finding) for finding in result.findings],
        "skipped_files": result.skipped_files,
    }


def write_json(result: ScanResult, path: Path) -> None:
    path.write_text(json.dumps(result_to_dict(result), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _record_to_dict(record: MetadataRecord) -> dict[str, Any]:
    return {
        "path": str(record.path),
        "patient_id_present": record.patient_id is not None,
        "study_uid": record.study_uid,
        "series_uid": record.series_uid,
        "manufacturer": record.manufacturer,
        "modality": record.modality,
        "tags": [
            {
                "tag": tag.tag,
                "keyword": tag.keyword,
                "vr": tag.vr,
                "is_private": tag.is_private,
                "value_state": tag.value_state.value,
            }
            for tag in sorted(record.tags.values(), key=lambda item: item.tag)
        ],
    }


def _finding_to_dict(finding: Finding) -> dict[str, Any]:
    return {
        "rule_id": finding.rule_id,
        "profile_id": finding.profile_id,
        "severity": finding.severity.value,
        "path": finding.path,
        "tag": finding.tag,
        "keyword": finding.keyword,
        "value_state": finding.value_state.value,
        "message": finding.message,
        "recommendation": finding.recommendation,
        "standard_refs": list(finding.standard_refs),
    }
