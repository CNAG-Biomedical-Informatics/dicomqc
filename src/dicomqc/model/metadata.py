"""Normalized metadata records independent of any DICOM parser."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any


class ValueState(str, Enum):
    """Redaction-safe state for an observed DICOM value."""

    ABSENT = "absent"
    EMPTY = "empty"
    PRESENT = "present"


@dataclass(frozen=True)
class DicomTag:
    tag: str
    keyword: str
    vr: str
    is_private: bool
    value_state: ValueState
    raw_value: Any = None


@dataclass(frozen=True)
class MetadataRecord:
    path: Path
    patient_id: str | None
    study_uid: str | None
    series_uid: str | None
    manufacturer: str | None
    modality: str | None
    tags: dict[str, DicomTag]

    def by_keyword(self, keyword: str) -> DicomTag | None:
        for tag in self.tags.values():
            if tag.keyword == keyword:
                return tag
        return None


def value_state(value: Any) -> ValueState:
    if value is None:
        return ValueState.ABSENT
    if isinstance(value, str):
        return ValueState.PRESENT if value.strip() else ValueState.EMPTY
    if isinstance(value, bytes):
        return ValueState.PRESENT if value else ValueState.EMPTY
    try:
        if len(value) == 0:  # type: ignore[arg-type]
            return ValueState.EMPTY
    except TypeError:
        pass
    return ValueState.PRESENT
