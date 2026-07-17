from __future__ import annotations

from dicomqc.demo import run_demo
from dicomqc.scanner import scan_paths


def test_run_demo_generates_synthetic_dicom_and_reports(tmp_path):
    output_dir = tmp_path / "demo"

    result = run_demo(output_dir)

    assert result.scan_exit_code == 2
    assert (output_dir / "dicom" / "raw_phi.dcm").exists()
    assert (output_dir / "dicom" / "pseudonymized.dcm").exists()
    assert (output_dir / "dicom" / "private_tags.dcm").exists()
    assert result.json_path.exists()
    assert result.csv_path.exists()
    assert (result.multiqc_dir / "dicomqc_00_overview_mqc.html").exists()
    assert (result.multiqc_dir / "dicomqc_summary_mqc.yaml").exists()
    assert (result.multiqc_dir / "dicomqc_01_release_status_mqc.yaml").exists()
    assert (result.multiqc_dir / "dicomqc_02_findings_mqc.yaml").exists()
    assert "Smith^Jane" not in result.json_path.read_text(encoding="utf-8")
    assert "19700101" not in result.csv_path.read_text(encoding="utf-8")


def test_demo_fixtures_represent_expected_release_cases(tmp_path):
    result = run_demo(tmp_path / "demo")
    dicom_dir = result.dicom_dir

    raw = scan_paths([dicom_dir / "raw_phi.dcm"], cwd=dicom_dir)
    clean = scan_paths([dicom_dir / "pseudonymized.dcm"], cwd=dicom_dir)
    private = scan_paths([dicom_dir / "private_tags.dcm"], cwd=dicom_dir)

    assert raw.exit_code() == 2
    assert {finding.keyword for finding in raw.findings} == {
        "PatientBirthDate",
        "PatientID",
        "PatientName",
        "PrivateTags",
    }
    assert clean.exit_code() == 0
    assert private.exit_code() == 1
    assert [finding.keyword for finding in private.findings] == ["PrivateTags"]
