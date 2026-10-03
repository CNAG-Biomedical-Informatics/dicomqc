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


def test_pydicom_backend_reports_missing_dependency(monkeypatch, tmp_path):
    import builtins

    from dicomqc.backend.base import DicomReadError

    real_import = builtins.__import__

    def blocked_import(name, *args, **kwargs):
        if name == "pydicom":
            raise ImportError("blocked")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", blocked_import)

    with pytest.raises(DicomReadError, match="pydicom is required"):
        PydicomBackend().read_metadata(tmp_path / "image.dcm")


def test_repeated_sequence_tags_do_not_hide_identifiers(tmp_path):
    from pydicom.dataset import Dataset
    from dicomqc.fixtures import write_synthetic_dicom_fixtures
    from dicomqc.rules.builtin import evaluate_record
    path = write_synthetic_dicom_fixtures(tmp_path)[1]
    ds = pydicom.dcmread(path)
    first, second = Dataset(), Dataset()
    first.PatientBirthDate = "19700101"
    first.PatientName = "Hidden^Person"
    second.PatientBirthDate = ""
    second.PatientName = "sub-001"
    ds.RequestAttributesSequence = [first, second]
    ds.save_as(path, enforce_file_format=True)
    record = PydicomBackend().read_metadata(path)
    assert len([t for t in record.tags.values() if t.keyword == "PatientBirthDate"]) == 2
    assert {f.keyword for f in evaluate_record(record)} == {"PatientBirthDate", "PatientName"}


def test_lazy_metadata_error_is_wrapped_and_redacted(tmp_path, monkeypatch):
    from dicomqc.backend.base import DicomReadError
    class InvalidDataset:
        def __iter__(self):
            raise ValueError("SECRET_VALUE")
    monkeypatch.setattr(pydicom, "dcmread", lambda *args, **kwargs: InvalidDataset())
    with pytest.raises(DicomReadError, match="Cannot read DICOM metadata") as error:
        PydicomBackend().read_metadata(tmp_path / "file")
    assert "SECRET_VALUE" not in str(error.value)
