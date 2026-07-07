"""Backend interfaces for reading DICOM metadata."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from dicomqc.model.metadata import MetadataRecord


class DicomReadError(Exception):
    """Raised when a file cannot be read as DICOM metadata."""


class DicomBackend(Protocol):
    """Protocol implemented by DICOM metadata readers."""

    def read_metadata(self, path: Path) -> MetadataRecord:
        """Read normalized metadata from one DICOM file."""
