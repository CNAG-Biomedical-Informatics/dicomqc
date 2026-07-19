from __future__ import annotations

from pathlib import Path

import pytest

from dicomqc import __version__
from dicomqc.cli import main

pydicom = pytest.importorskip("pydicom")
from pydicom.dataset import FileDataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, generate_uid


def _write_dicom(path: Path, **values) -> None:
    meta = FileMetaDataset()
    meta.TransferSyntaxUID = ExplicitVRLittleEndian
    meta.MediaStorageSOPClassUID = generate_uid()
    meta.MediaStorageSOPInstanceUID = generate_uid()
    meta.ImplementationClassUID = generate_uid()
    dataset = FileDataset(str(path), {}, file_meta=meta, preamble=b"\0" * 128)
    dataset.SOPClassUID = meta.MediaStorageSOPClassUID
    dataset.SOPInstanceUID = meta.MediaStorageSOPInstanceUID
    dataset.StudyInstanceUID = values.pop("StudyInstanceUID", generate_uid())
    dataset.SeriesInstanceUID = values.pop("SeriesInstanceUID", generate_uid())
    dataset.Modality = values.pop("Modality", "MR")
    dataset.Manufacturer = values.pop("Manufacturer", "SIEMENS")
    for key, value in values.items():
        setattr(dataset, key, value)
    dataset.save_as(str(path), enforce_file_format=True)


def test_cli_scan_writes_json_and_csv_with_error_exit(tmp_path, capsys):
    dicom_path = tmp_path / "image"
    _write_dicom(dicom_path, PatientName="Smith^Jane", PatientBirthDate="19700101")
    json_path = tmp_path / "report.json"
    csv_path = tmp_path / "findings.csv"

    code = main(["scan", str(tmp_path), "--json", str(json_path), "--csv", str(csv_path)])
    out = capsys.readouterr().out

    assert code == 2
    assert "Files scanned: 1" in out
    assert json_path.exists()
    assert csv_path.exists()
    assert "Smith^Jane" not in json_path.read_text(encoding="utf-8")
    assert "19700101" not in csv_path.read_text(encoding="utf-8")


def test_cli_scan_writes_multiqc_custom_content(tmp_path):
    dicom_path = tmp_path / "image"
    _write_dicom(dicom_path, PatientName="Smith^Jane")
    multiqc_dir = tmp_path / "dicomqc_mqc"

    code = main(["scan", str(dicom_path), "--multiqc", str(multiqc_dir), "--quiet"])

    assert code == 1
    summary = multiqc_dir / "dicomqc_summary_mqc.yaml"
    findings = multiqc_dir / "dicomqc_02_findings_mqc.yaml"
    assert summary.exists()
    assert findings.exists()
    assert "plot_type: generalstats" in summary.read_text(encoding="utf-8")
    finding_payload = findings.read_text(encoding="utf-8")
    assert "plot_type: table" in finding_payload
    assert "Smith^Jane" not in finding_payload


def test_cli_scan_warning_exit_for_nonmatching_pseudonym(tmp_path):
    dicom_path = tmp_path / "image.dcm"
    _write_dicom(dicom_path, PatientName="Smith^Jane")

    assert main(["scan", str(dicom_path), "--quiet"]) == 1


def test_cli_scan_clean_exit_for_research_pseudonym(tmp_path):
    dicom_path = tmp_path / "image.dcm"
    _write_dicom(dicom_path, PatientID="SUBJ001")

    assert main(["scan", str(dicom_path), "--quiet"]) == 0


def test_cli_demo_writes_synthetic_dicom_and_reports(tmp_path, capsys):
    output_dir = tmp_path / "demo"

    assert main(["demo", "--output-dir", str(output_dir)]) == 0
    out = capsys.readouterr().out

    assert "Demo directory:" in out
    assert "Demo scan exit code: 2" in out
    assert (output_dir / "dicom" / "raw_phi.dcm").exists()
    assert (output_dir / "dicom" / "pseudonymized.dcm").exists()
    assert (output_dir / "dicomqc" / "report.json").exists()
    assert (output_dir / "dicomqc" / "findings.csv").exists()
    assert (output_dir / "dicomqc" / "dicomqc_mqc" / "dicomqc_summary_mqc.yaml").exists()


def test_cli_demo_refuses_to_overwrite_without_force(tmp_path, capsys):
    output_dir = tmp_path / "demo"
    output_dir.mkdir()

    assert main(["demo", "--output-dir", str(output_dir)]) == 2
    assert "Use --force to replace it" in capsys.readouterr().err


def test_cli_scan_invalid_file_is_fatal(tmp_path):
    bad = tmp_path / "not-dicom"
    bad.write_text("not a dicom", encoding="utf-8")

    assert main(["scan", str(bad), "--quiet"]) == 2


def test_cli_without_subcommand_prints_help(capsys):
    assert main([]) == 2
    assert "Validate DICOM metadata" in capsys.readouterr().out


def test_cli_version(capsys):
    with pytest.raises(SystemExit, match="0"):
        main(["--version"])

    assert capsys.readouterr().out.strip() == f"dicomqc {__version__}"


def test_cli_rejects_unknown_profile(tmp_path, capsys):
    dicom_path = tmp_path / "image.dcm"
    _write_dicom(dicom_path, PatientID="SUBJ001")

    assert main(["scan", str(dicom_path), "--profile", "missing-profile"]) == 2
    assert "Unknown profile" in capsys.readouterr().err
