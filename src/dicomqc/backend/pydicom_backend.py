"""pydicom-backed metadata reader."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from dicomqc.backend.base import DicomReadError
from dicomqc.model.metadata import DicomTag, MetadataRecord, value_state


class PydicomBackend:
    """Read DICOM metadata with pydicom while avoiding pixel data."""

    def read_metadata(self, path: Path) -> MetadataRecord:
        try:
            import pydicom
            from pydicom.errors import InvalidDicomError
        except ImportError as exc:  # pragma: no cover - exercised only without dependency
            raise DicomReadError("pydicom is required to read DICOM metadata") from exc

        try:
            dataset = pydicom.dcmread(str(path), stop_before_pixels=True, force=False)
        except (InvalidDicomError, OSError, EOFError, ValueError) as exc:
            raise DicomReadError(str(exc)) from exc

        tags: dict[str, DicomTag] = {}
        for elem in dataset.iterall():
            if elem.keyword == "PixelData":
                continue
            tag_key = f"({elem.tag.group:04X},{elem.tag.element:04X})"
            keyword = elem.keyword or elem.name or tag_key
            raw_value = elem.value
            tags[tag_key] = DicomTag(
                tag=tag_key,
                keyword=keyword,
                vr=str(elem.VR),
                is_private=bool(elem.tag.is_private),
                value_state=value_state(raw_value),
                raw_value=raw_value,
            )

        return MetadataRecord(
            path=path,
            patient_id=_string_value(dataset.get("PatientID")),
            study_uid=_string_value(dataset.get("StudyInstanceUID")),
            series_uid=_string_value(dataset.get("SeriesInstanceUID")),
            manufacturer=_string_value(dataset.get("Manufacturer")),
            modality=_string_value(dataset.get("Modality")),
            tags=tags,
        )


def _string_value(value: Any) -> str | None:
    if value is None:
        return None
    rendered = str(value).strip()
    return rendered or None
