from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from dicomqc.scanner import scan_paths

pydicom = pytest.importorskip("pydicom")
from pydicom.dataset import FileDataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, generate_uid


pytestmark = pytest.mark.skipif(shutil.which("dcmodify") is None, reason="dcmodify is not installed")


def test_dcmodify_pseudonymized_dicom_passes_dicomqc(tmp_path):
    path = tmp_path / "image.dcm"
    _write_dicom(path)

    before = scan_paths([path], cwd=tmp_path)
    assert before.exit_code() == 2
    assert {finding.keyword for finding in before.findings} == {"PatientBirthDate", "PatientID", "PatientName"}

    subprocess.run(
        [
            "dcmodify",
            "-nb",
            "-gin",
            "-i",
            "PatientName=SUBJ001",
            "-i",
            "PatientID=SUBJ001",
            "-e",
            "PatientBirthDate",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    after = scan_paths([path], cwd=tmp_path)
    assert after.exit_code() == 0
    assert after.findings == []


def _write_dicom(path: Path) -> None:
    meta = FileMetaDataset()
    meta.TransferSyntaxUID = ExplicitVRLittleEndian
    meta.MediaStorageSOPClassUID = generate_uid()
    meta.MediaStorageSOPInstanceUID = generate_uid()
    meta.ImplementationClassUID = generate_uid()
    dataset = FileDataset(str(path), {}, file_meta=meta, preamble=b"\0" * 128)
    dataset.SOPClassUID = meta.MediaStorageSOPClassUID
    dataset.SOPInstanceUID = meta.MediaStorageSOPInstanceUID
    dataset.StudyInstanceUID = generate_uid()
    dataset.SeriesInstanceUID = generate_uid()
    dataset.Modality = "MR"
    dataset.Manufacturer = "SIEMENS"
    dataset.PatientName = "Smith^Jane"
    dataset.PatientID = "LOCAL123"
    dataset.PatientBirthDate = "19700101"
    dataset.save_as(str(path), enforce_file_format=True)
