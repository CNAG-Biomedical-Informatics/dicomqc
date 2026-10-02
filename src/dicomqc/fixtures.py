"""Synthetic DICOM fixtures used by demos and tests."""

from __future__ import annotations

from pathlib import Path
import csv

from pydicom.dataset import FileDataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian

ROOT_UID = "1.2.826.0.1.3680043.10.54321"


def write_comparison_fixtures(output_dir: Path) -> Path:
    """Create two source patients, broken/corrected outputs, and their manifest."""
    for name in ("source", "candidate", "corrected"):
        (output_dir / name).mkdir(parents=True, exist_ok=True)
    pairs = [
        ("patient-a-visit-1.dcm", "image-001.dcm", "LOCAL001", "sub-001"),
        ("patient-a-visit-2.dcm", "image-002.dcm", "LOCAL001", "sub-001"),
        ("patient-b-visit-1.dcm", "image-003.dcm", "LOCAL002", "sub-002"),
    ]
    for index, (source_name, output_name, patient_id, pseudonym) in enumerate(pairs, 1):
        _write_dicom(
            output_dir / "source" / source_name, fixture_index=index,
            patient_name="Example^Patient", patient_id=patient_id,
            patient_birth_date="19700101", private_creator=None,
        )
        _write_dicom(
            output_dir / "corrected" / output_name, fixture_index=index + 100,
            patient_name=pseudonym, patient_id=pseudonym,
            patient_birth_date=None, private_creator=None,
        )
        # The second visit gets a different pseudonym; the third file is missing.
        if index < 3:
            broken_id = "sub-099" if index == 2 else pseudonym
            _write_dicom(
                output_dir / "candidate" / output_name, fixture_index=index + 200,
                patient_name=broken_id, patient_id=broken_id,
                patient_birth_date=None, private_creator=None,
            )
    manifest = output_dir / "pairs.csv"
    with manifest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["source", "candidate"])
        writer.writerows((source_name, output_name) for source_name, output_name, _, _ in pairs)
    return manifest


def write_synthetic_dicom_fixtures(output_dir: Path) -> list[Path]:
    """Write a compact set of synthetic DICOM files for dicomqc demos."""

    output_dir.mkdir(parents=True, exist_ok=True)
    fixtures = [
        (
            output_dir / "raw_phi.dcm",
            {
                "fixture_index": 1,
                "patient_name": "Smith^Jane",
                "patient_id": "LOCAL123",
                "patient_birth_date": "19700101",
                "private_creator": "SIEMENS CSA HEADER",
            },
        ),
        (
            output_dir / "pseudonymized.dcm",
            {
                "fixture_index": 2,
                "patient_name": "SUBJ001",
                "patient_id": "SUBJ001",
                "patient_birth_date": None,
                "private_creator": None,
            },
        ),
        (
            output_dir / "private_tags.dcm",
            {
                "fixture_index": 3,
                "patient_name": "SUBJ002",
                "patient_id": "SUBJ002",
                "patient_birth_date": None,
                "private_creator": "SIEMENS CSA HEADER",
            },
        ),
    ]
    for path, options in fixtures:
        _write_dicom(path, **options)
    return [path for path, _options in fixtures]


def _write_dicom(
    path: Path,
    *,
    fixture_index: int,
    patient_name: str,
    patient_id: str,
    patient_birth_date: str | None,
    private_creator: str | None,
) -> None:
    meta = FileMetaDataset()
    meta.TransferSyntaxUID = ExplicitVRLittleEndian
    meta.MediaStorageSOPClassUID = f"{ROOT_UID}.1"
    meta.MediaStorageSOPInstanceUID = f"{ROOT_UID}.2.{fixture_index}"
    meta.ImplementationClassUID = f"{ROOT_UID}.3"
    dataset = FileDataset(str(path), {}, file_meta=meta, preamble=b"\0" * 128)
    dataset.SOPClassUID = meta.MediaStorageSOPClassUID
    dataset.SOPInstanceUID = meta.MediaStorageSOPInstanceUID
    dataset.StudyInstanceUID = f"{ROOT_UID}.4.1"
    dataset.SeriesInstanceUID = f"{ROOT_UID}.5.{fixture_index}"
    dataset.Modality = "MR"
    dataset.Manufacturer = "SIEMENS"
    dataset.PatientName = patient_name
    dataset.PatientID = patient_id
    if patient_birth_date is not None:
        dataset.PatientBirthDate = patient_birth_date
    if private_creator is not None:
        dataset.add_new((0x0029, 0x0010), "LO", private_creator)
    dataset.save_as(str(path), enforce_file_format=True)
