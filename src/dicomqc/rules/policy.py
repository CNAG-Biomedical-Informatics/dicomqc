"""Bounded, additive project checks for DICOM metadata.

Policy messages deliberately exclude configured values and observed metadata.
Patterns use shell-style glob matching, never regular expressions or executable
expressions. Loading a policy does not change the built-in audit rules.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from fnmatch import fnmatchcase
from hashlib import sha256
from pathlib import Path
import re

from pydicom.datadict import dictionary_VR, tag_for_keyword
import yaml
from yaml.tokens import (
    AliasToken,
    AnchorToken,
    BlockEndToken,
    BlockMappingStartToken,
    BlockSequenceStartToken,
    FlowMappingEndToken,
    FlowMappingStartToken,
    FlowSequenceEndToken,
    FlowSequenceStartToken,
    ScalarToken,
    TagToken,
)

from dicomqc.model.metadata import DicomTag, MetadataRecord, ValueState, value_state
from dicomqc.model.results import Finding, Severity

_MAX_BYTES = 64 * 1024
_MAX_RULES = 100
_MAX_VALUES = 100
_MAX_STRING = 256
_SLUG = re.compile(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*\Z")
_CHECKS = {"absent_or_empty", "nonempty", "allowed_values", "matches"}
_PRESENCE_CHECKS = {"absent_or_empty", "nonempty"}
_BINARY_VRS = {"OB", "OD", "OF", "OL", "OV", "OW", "UN"}
_MESSAGES = {
    "absent_or_empty": (
        "must be absent or empty under the project policy.",
        "Remove or empty this field in the upstream de-identification workflow, then rerun the audit.",
    ),
    "nonempty": (
        "must be present and nonempty under the project policy.",
        "Populate this field with an appropriate value upstream, then rerun the audit.",
    ),
    "allowed_values": (
        "does not satisfy the project policy's allowed-values check.",
        "Review the configured allowed values and correct this field upstream, then rerun the audit.",
    ),
    "matches": (
        "does not satisfy the project policy's format check.",
        "Review the configured field format and correct this field upstream, then rerun the audit.",
    ),
}


@dataclass(frozen=True)
class PolicyRule:
    id: str
    keyword: str
    check: str
    severity: Severity = Severity.ERROR
    scope: str = "all"
    values: tuple[str, ...] = ()
    pattern: str | None = None


@dataclass(frozen=True)
class Policy:
    id: str
    rules: tuple[PolicyRule, ...]
    sha256: str


class _PolicyLoader(yaml.SafeLoader):
    """Reject duplicate or non-string mapping keys rather than overwriting them."""

    def construct_mapping(self, node, deep=False):
        mapping = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if not isinstance(key, str) or key in mapping:
                raise ValueError("Policy mapping keys must be unique strings.")
            mapping[key] = self.construct_object(value_node, deep=deep)
        return mapping


def _validate_tokens(source: str) -> None:
    """Bound nesting before composing YAML; aliases and explicit tags are forbidden."""
    starts = (BlockMappingStartToken, BlockSequenceStartToken, FlowMappingStartToken, FlowSequenceStartToken)
    ends = (BlockEndToken, FlowMappingEndToken, FlowSequenceEndToken)
    depth = 0
    for token in yaml.scan(source):
        if isinstance(token, (AliasToken, AnchorToken, TagToken)):
            raise ValueError("Policy aliases, anchors and explicit YAML tags are not supported.")
        if isinstance(token, ScalarToken) and len(token.value) > _MAX_STRING:
            raise ValueError("Policy strings must not exceed 256 characters.")
        if isinstance(token, starts):
            depth += 1
            if depth > 16:
                raise ValueError("Policy nesting exceeds the supported limit.")
        elif isinstance(token, ends):
            depth -= 1


def _slug(value: object) -> bool:
    return isinstance(value, str) and len(value) <= 64 and bool(_SLUG.fullmatch(value))


def _text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip()) and len(value) <= _MAX_STRING


def _parse_rule(data: object) -> PolicyRule:
    required = {"id", "keyword", "check"}
    optional = {"severity", "scope", "values", "pattern"}
    if not isinstance(data, dict) or not required <= data.keys() or data.keys() - required - optional:
        raise ValueError("Policy rules must contain only the supported fields and all required fields.")
    if not _slug(data["id"]):
        raise ValueError("Policy rule IDs must be lowercase slugs of at most 64 characters.")
    keyword = data["keyword"]
    if not _text(keyword):
        raise ValueError("Policy keywords must identify supported standard DICOM fields.")
    tag_number = tag_for_keyword(keyword)
    if tag_number is None:
        raise ValueError("Policy keywords must identify supported standard DICOM fields.")
    check = data["check"]
    if not isinstance(check, str) or check not in _CHECKS:
        raise ValueError("Policy check must be absent_or_empty, nonempty, allowed_values or matches.")
    vr = dictionary_VR(tag_number)
    if _BINARY_VRS.intersection(vr.split(" or ")) or (vr == "SQ" and check not in _PRESENCE_CHECKS):
        raise ValueError("Binary fields are not supported; sequence fields allow presence checks only.")
    severity = data.get("severity", "error")
    if not isinstance(severity, str) or severity not in {item.value for item in Severity}:
        raise ValueError("Policy severity must be error, warning or info.")
    scope = data.get("scope", "all")
    if not isinstance(scope, str) or scope not in {"top_level", "all"}:
        raise ValueError("Policy scope must be top_level or all.")
    values = data.get("values")
    pattern = data.get("pattern")
    if check == "allowed_values":
        if not isinstance(values, list) or not 1 <= len(values) <= _MAX_VALUES or not all(_text(v) for v in values):
            raise ValueError("Policy allowed values must contain 1 to 100 nonempty, quoted strings.")
    elif "values" in data:
        raise ValueError("Policy values are supported only for allowed_values checks.")
    if check == "matches":
        if not _text(pattern):
            raise ValueError("Policy matches checks require a nonempty glob pattern.")
    elif "pattern" in data:
        raise ValueError("Policy patterns are supported only for matches checks.")
    return PolicyRule(
        id=data["id"], keyword=keyword, check=check, severity=Severity(severity),
        scope=scope, values=tuple(values or ()), pattern=pattern,
    )


def load_policy(path: Path) -> Policy:
    """Load a strict YAML policy without exposing its contents in errors."""
    try:
        if not path.is_file():
            raise ValueError("Policy input must be a readable regular file.")
        with path.open("rb") as handle:
            source = handle.read(_MAX_BYTES + 1)
    except OSError:
        raise ValueError("Unable to read policy file.") from None
    if len(source) > _MAX_BYTES:
        raise ValueError("Policy files must not exceed 64 KiB.")
    try:
        decoded = source.decode("utf-8")
        _validate_tokens(decoded)
        data = yaml.load(decoded, Loader=_PolicyLoader)
    except (UnicodeError, yaml.YAMLError):
        raise ValueError("Policy file must contain valid UTF-8 YAML.") from None
    if not isinstance(data, dict) or data.keys() != {"version", "id", "rules"}:
        raise ValueError("Policy must contain exactly version, id and rules.")
    if type(data["version"]) is not int or data["version"] != 1:
        raise ValueError("Policy version must be the integer 1.")
    if not _slug(data["id"]):
        raise ValueError("Policy ID must be a lowercase slug of at most 64 characters.")
    rules = data["rules"]
    if not isinstance(rules, list) or not 1 <= len(rules) <= _MAX_RULES:
        raise ValueError("Policy must contain 1 to 100 rules.")
    parsed = tuple(_parse_rule(rule) for rule in rules)
    if len({rule.id for rule in parsed}) != len(parsed):
        raise ValueError("Policy rule IDs must be unique.")
    return Policy(id=data["id"], rules=parsed, sha256=sha256(source).hexdigest())


def _values(tag: DicomTag) -> tuple[object, ...]:
    value = tag.raw_value
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return tuple(value)
    return (value,)


def _passes(tag: DicomTag | None, rule: PolicyRule) -> bool:
    values = _values(tag) if tag is not None else ()
    present = bool(tag is not None and tag.value_state == ValueState.PRESENT)
    if tag is not None and tag.vr == "SQ":
        return not present if rule.check == "absent_or_empty" else present
    if rule.check == "absent_or_empty":
        return not present or all(value_state(value) != ValueState.PRESENT for value in values)
    if not present or not values or any(value_state(value) != ValueState.PRESENT for value in values):
        return False
    if rule.check == "nonempty":
        return True
    if rule.check == "allowed_values":
        return all(str(value) in rule.values for value in values)
    return all(fnmatchcase(str(value), rule.pattern or "") for value in values)


def evaluate_policy(record: MetadataRecord, policy: Policy) -> list[Finding]:
    """Evaluate each in-scope occurrence; missing required fields also fail."""
    findings = []
    profile_id = f"policy.{policy.id}"
    for rule in policy.rules:
        matching = [
            tag for tag in record.tags.values()
            if tag.keyword == rule.keyword and (rule.scope == "all" or not tag.is_nested)
        ]
        for tag in matching or [None]:
            if _passes(tag, rule):
                continue
            number = tag_for_keyword(rule.keyword)
            tag_label = tag.tag if tag is not None else f"({number >> 16:04X},{number & 0xFFFF:04X})"
            message, recommendation = _MESSAGES[rule.check]
            findings.append(Finding(
                rule_id=f"{profile_id}.{rule.id}", profile_id=profile_id,
                severity=rule.severity, path=str(record.path), tag=tag_label,
                keyword=rule.keyword, value_state=tag.value_state if tag else ValueState.ABSENT,
                message=f"{rule.keyword} {message}", recommendation=recommendation,
            ))
    return findings
