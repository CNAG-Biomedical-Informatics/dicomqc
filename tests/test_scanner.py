from __future__ import annotations

from pathlib import Path

from dicomqc.backend.base import DicomReadError
from dicomqc.model.metadata import MetadataRecord
from dicomqc.scanner import scan_paths


class FakeBackend:
    def read_metadata(self, path: Path) -> MetadataRecord:
        if path.name == "bad":
            raise DicomReadError("fake failure")
        return MetadataRecord(
            path=path,
            patient_id=None,
            study_uid=None,
            series_uid=None,
            manufacturer=None,
            modality=None,
            tags={},
        )


def test_scan_paths_handles_missing_path_as_skipped(tmp_path):
    result = scan_paths([tmp_path / "bad"], backend=FakeBackend(), cwd=tmp_path)

    assert result.exit_code() == 2
    assert result.skipped_files == {"bad": "fake failure"}


def test_scan_paths_preserves_external_display_path(tmp_path):
    external = Path("/tmp/dicomqc-external-test.dcm")
    result = scan_paths([external], backend=FakeBackend(), cwd=tmp_path)

    assert result.records[0].path == external
