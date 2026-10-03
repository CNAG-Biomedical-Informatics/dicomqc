"""Synthetic DICOM fixtures used by demos and tests."""

from __future__ import annotations

from pathlib import Path
import csv
import warnings

from pydicom import dcmread
from pydicom.dataset import Dataset, FileDataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian

ROOT_UID = "1.2.826.0.1.3680043.10.54321"

POLICY_DEMO_YAML = """version: 1
id: research-demo
rules:
  - id: identity-marker
    keyword: PatientIdentityRemoved
    check: allowed_values
    values: ["YES"]
    scope: top_level
  - id: study-description
    keyword: StudyDescription
    check: allowed_values
    values: ["T1w", "T2w"]
  - id: patient-comments
    keyword: PatientComments
    check: absent_or_empty
"""


def write_uid_fixtures(output_dir: Path) -> None:
    """Four invented exports with syntax, role, and hierarchy errors."""
    for phase in ("candidate", "corrected"):
        folder = output_dir / phase
        folder.mkdir(parents=True, exist_ok=True)
        for index in range(1, 5):
            study = f"{ROOT_UID}.60.{index}"
            series = f"{ROOT_UID}.61.{index}"
            sop = f"{ROOT_UID}.62.{index}"
            if phase == "candidate":
                if index == 1:
                    sop = f"{ROOT_UID}.62.01"  # Illegal leading zero.
                elif index == 2:
                    series = study
                else:
                    series, sop = f"{ROOT_UID}.61.3", f"{ROOT_UID}.62.3"
            # Only fixture generation writes DICOM; the audits remain read-only.
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", message="Invalid value for VR UI:", category=UserWarning)
                _write_dicom(
                    folder / f"image-{index:03d}.dcm", fixture_index=500 + index,
                    patient_name="sub-001", patient_id="sub-001",
                    patient_birth_date=None, private_creator=None,
                    metadata={"StudyInstanceUID": study, "SeriesInstanceUID": series, "SOPInstanceUID": sop},
                )


def write_vendor_fixtures(output_dir: Path) -> list[Path]:
    """Create invented equipment labels and dataset-local private-block examples."""
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for index, version in enumerate(("1.0", "1.0", "1.1"), start=1):
        path = output_dir / f"image-{index:03d}.dcm"
        _write_dicom(
            path, fixture_index=400 + index,
            patient_name="sub-001", patient_id="sub-001",
            patient_birth_date=None, private_creator="ACME_ACQUISITION",
            metadata={
                "Manufacturer": "Example Imaging",
                "ManufacturerModelName": "Research MR",
                "SoftwareVersions": version,
            },
        )
        dataset = dcmread(path)
        dataset.add_new((0x0029, 0x1010), "LO", "SYNTHETIC_PRIVATE_PAYLOAD_DO_NOT_REPORT")
        if index == 3:
            processing = Dataset()
            processing.add_new((0x0029, 0x0010), "LO", "ACME_PROCESSING")
            processing.add_new((0x0029, 0x1010), "LO", "SYNTHETIC_NESTED_PAYLOAD_DO_NOT_REPORT")
            orphan = Dataset()
            orphan.add_new((0x0029, 0x1010), "LO", "SYNTHETIC_ORPHAN_PAYLOAD_DO_NOT_REPORT")
            dataset.RequestAttributesSequence = [processing, orphan]
        dataset.save_as(path, enforce_file_format=True)
        paths.append(path)
    return paths


def write_policy_fixtures(output_dir: Path) -> Path:
    """Create synthetic descriptor/marker failures and independent corrected data."""
    for name in ("candidate", "corrected"):
        folder = output_dir / name
        folder.mkdir(parents=True, exist_ok=True)
        metadata = (
            {"PatientIdentityRemoved": "NO", "StudyDescription": "T1w - Example Patient",
             "PatientComments": "Synthetic identifying comment"}
            if name == "candidate" else
            {"PatientIdentityRemoved": "YES", "StudyDescription": "T1w"}
        )
        _write_dicom(
            folder / "image-001.dcm", fixture_index=301 if name == "candidate" else 302,
            patient_name="sub-001", patient_id="sub-001",
            patient_birth_date=None, private_creator=None, metadata=metadata,
        )
    policy_path = output_dir / "policy.yaml"
    policy_path.write_text(POLICY_DEMO_YAML, encoding="utf-8")
    return policy_path


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
    metadata: dict[str, str] | None = None,
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
    for keyword, value in (metadata or {}).items():
        setattr(dataset, keyword, value)
    dataset.save_as(str(path), enforce_file_format=True)
