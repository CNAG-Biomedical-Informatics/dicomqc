#!/usr/bin/env python3
"""Generate small synthetic DICOM fixtures for DICOMQC development."""

from __future__ import annotations

import argparse
from pathlib import Path

from pydicom.dataset import FileDataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, generate_uid


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate synthetic DICOMQC test fixtures.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("tests/fixtures/dicom/generated"),
        help="Directory where synthetic .dcm files will be written.",
    )
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    _write_dicom(
        args.output_dir / "raw_phi.dcm",
        patient_name="Smith^Jane",
        patient_id="LOCAL123",
        patient_birth_date="19700101",
        private_creator="SIEMENS CSA HEADER",
    )
    _write_dicom(
        args.output_dir / "pseudonymized.dcm",
        patient_name="SUBJ001",
        patient_id="SUBJ001",
        patient_birth_date=None,
        private_creator=None,
    )
    _write_dicom(
        args.output_dir / "private_tags.dcm",
        patient_name="SUBJ002",
        patient_id="SUBJ002",
        patient_birth_date=None,
        private_creator="SIEMENS CSA HEADER",
    )
    print(f"Wrote synthetic DICOM fixtures to {args.output_dir}")
    return 0


def _write_dicom(
    path: Path,
    *,
    patient_name: str,
    patient_id: str,
    patient_birth_date: str | None,
    private_creator: str | None,
) -> None:
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
    dataset.PatientName = patient_name
    dataset.PatientID = patient_id
    if patient_birth_date is not None:
        dataset.PatientBirthDate = patient_birth_date
    if private_creator is not None:
        dataset.add_new((0x0029, 0x0010), "LO", private_creator)
    dataset.save_as(str(path), enforce_file_format=True)


if __name__ == "__main__":
    raise SystemExit(main())
