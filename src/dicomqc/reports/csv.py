"""CSV finding reports."""

from __future__ import annotations

import csv
from pathlib import Path

from dicomqc.model.results import ScanResult

FIELDNAMES = [
    "path",
    "rule_id",
    "profile_id",
    "severity",
    "tag",
    "keyword",
    "value_state",
    "message",
    "recommendation",
    "standard_refs",
]


def write_csv(result: ScanResult, path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        for finding in result.findings:
            writer.writerow(
                {
                    "path": finding.path,
                    "rule_id": finding.rule_id,
                    "profile_id": finding.profile_id,
                    "severity": finding.severity.value,
                    "tag": finding.tag or "",
                    "keyword": finding.keyword or "",
                    "value_state": finding.value_state.value,
                    "message": finding.message,
                    "recommendation": finding.recommendation,
                    "standard_refs": ";".join(finding.standard_refs),
                }
            )
