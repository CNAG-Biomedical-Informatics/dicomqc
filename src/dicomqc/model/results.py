"""Scan result models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from dicomqc.model.metadata import MetadataRecord, ValueState


class Severity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True)
class Finding:
    rule_id: str
    profile_id: str
    severity: Severity
    path: str
    message: str
    recommendation: str
    tag: str | None = None
    keyword: str | None = None
    value_state: ValueState = ValueState.ABSENT
    standard_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class ScanResult:
    profile_id: str
    records: list[MetadataRecord] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    skipped_files: dict[str, str] = field(default_factory=dict)

    @property
    def error_count(self) -> int:
        return sum(1 for finding in self.findings if finding.severity == Severity.ERROR)

    @property
    def warning_count(self) -> int:
        return sum(1 for finding in self.findings if finding.severity == Severity.WARNING)

    @property
    def info_count(self) -> int:
        return sum(1 for finding in self.findings if finding.severity == Severity.INFO)

    @property
    def files_scanned(self) -> int:
        return len(self.records)

    @property
    def files_failed(self) -> int:
        failed = {finding.path for finding in self.findings if finding.severity == Severity.ERROR}
        return len(failed)

    @property
    def files_passed(self) -> int:
        return max(0, self.files_scanned - self.files_failed)

    def exit_code(self) -> int:
        if self.error_count or self.skipped_files:
            return 2
        if self.warning_count:
            return 1
        return 0
