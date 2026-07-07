"""Built-in research-release validation rules."""

from __future__ import annotations

import re

from dicomqc.model.metadata import DicomTag, MetadataRecord, ValueState
from dicomqc.model.results import Finding, Severity

DEFAULT_PROFILE_ID = "research-release-v0.1"

DIRECT_PHI_KEYWORDS = {
    "PatientBirthDate",
    "PatientAddress",
    "PatientTelephoneNumbers",
    "InstitutionAddress",
    "ReferringPhysicianName",
    "OperatorsName",
    "AccessionNumber",
}

PSEUDONYM_KEYWORDS = {"PatientName", "PatientID"}
PSEUDONYM_RE = re.compile(
    r"^(?:sub|subj|subject|participant|anon|case|pat|id)[-_]?[A-Za-z0-9]{2,}$",
    re.IGNORECASE,
)


def evaluate_record(record: MetadataRecord, *, profile_id: str = DEFAULT_PROFILE_ID) -> list[Finding]:
    findings: list[Finding] = []

    for keyword in sorted(DIRECT_PHI_KEYWORDS):
        tag = record.by_keyword(keyword)
        if _is_present(tag):
            findings.append(
                Finding(
                    rule_id=f"{profile_id}.direct_phi.{keyword}",
                    profile_id=profile_id,
                    severity=Severity.ERROR,
                    path=str(record.path),
                    tag=tag.tag,
                    keyword=keyword,
                    value_state=tag.value_state,
                    message=f"{keyword} is populated and may contain direct PHI.",
                    recommendation="Remove this value or verify that the upstream anonymizer removes it for research release.",
                )
            )

    for keyword in sorted(PSEUDONYM_KEYWORDS):
        tag = record.by_keyword(keyword)
        if _is_present(tag) and not _looks_like_pseudonym(tag.raw_value):
            findings.append(
                Finding(
                    rule_id=f"{profile_id}.pseudonym_format.{keyword}",
                    profile_id=profile_id,
                    severity=Severity.WARNING,
                    path=str(record.path),
                    tag=tag.tag,
                    keyword=keyword,
                    value_state=tag.value_state,
                    message=f"{keyword} is populated but does not match the built-in research pseudonym pattern.",
                    recommendation="Use a non-identifying research identifier such as sub-001, SUBJ001, participant-123, or anon-001.",
                )
            )

    private_tags = [tag for tag in record.tags.values() if tag.is_private]
    if private_tags:
        findings.append(
            Finding(
                rule_id=f"{profile_id}.private_tags.present",
                profile_id=profile_id,
                severity=Severity.WARNING,
                path=str(record.path),
                tag=None,
                keyword="PrivateTags",
                value_state=ValueState.PRESENT,
                message=f"{len(private_tags)} private DICOM tag(s) are present.",
                recommendation="Review vendor-specific private tags before release; private tags can contain site, protocol, or operator identifiers.",
            )
        )

    return findings


def _is_present(tag: DicomTag | None) -> bool:
    return tag is not None and tag.value_state == ValueState.PRESENT


def _looks_like_pseudonym(value: object) -> bool:
    text = str(value).strip() if value is not None else ""
    if "^" in text:
        return False
    return bool(PSEUDONYM_RE.match(text))
