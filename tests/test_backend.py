from __future__ import annotations

from pathlib import Path

import pytest

from dicomqc.backend.pydicom_backend import PydicomBackend
from dicomqc.model.metadata import ValueState

pydicom = pytest.importorskip("pydicom")
from pydicom.dataset import FileDataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, generate_uid


def test_pydicom_backend_normalizes_metadata_and_omits_pixel_data(tmp_path):
    path = tmp_path / "pixel.dcm"
    meta = FileMetaDataset()
    meta.TransferSyntaxUID = ExplicitVRLittleEndian
    meta.MediaStorageSOPClassUID = generate_uid()
    meta.MediaStorageSOPInstanceUID = generate_uid()
    meta.ImplementationClassUID = generate_uid()
    dataset = FileDataset(str(path), {}, file_meta=meta, preamble=b"\0" * 128)
    dataset.SOPClassUID = meta.MediaStorageSOPClassUID
    dataset.SOPInstanceUID = meta.MediaStorageSOPInstanceUID
    dataset.PatientID = "SUBJ001"
    dataset.StudyInstanceUID = generate_uid()
    dataset.SeriesInstanceUID = generate_uid()
    dataset.Manufacturer = "SIEMENS"
    dataset.Modality = "MR"
    dataset.Rows = 1
    dataset.Columns = 1
    dataset.BitsAllocated = 8
    dataset.PixelData = b"\x00"
    dataset.add_new((0x0029, 0x0010), "LO", "SIEMENS CSA HEADER")
    dataset.save_as(str(path), enforce_file_format=True)

    record = PydicomBackend().read_metadata(path)

    assert record.patient_id == "SUBJ001"
    assert record.manufacturer == "SIEMENS"
    assert record.modality == "MR"
    assert "(7FE0,0010)" not in record.tags
    assert record.by_keyword("PatientID").value_state == ValueState.PRESENT
    assert record.tags["(0029,0010)"].is_private is True
