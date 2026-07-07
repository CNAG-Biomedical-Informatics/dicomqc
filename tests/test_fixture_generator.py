from __future__ import annotations

import subprocess
import sys

from dicomqc.scanner import scan_paths


def test_fixture_generator_creates_expected_dicom_cases(tmp_path):
    output_dir = tmp_path / "fixtures"

    subprocess.run(
        [sys.executable, "scripts/make_dicom_fixtures.py", "--output-dir", str(output_dir)],
        check=True,
        capture_output=True,
        text=True,
    )

    raw = scan_paths([output_dir / "raw_phi.dcm"], cwd=output_dir)
    clean = scan_paths([output_dir / "pseudonymized.dcm"], cwd=output_dir)
    private = scan_paths([output_dir / "private_tags.dcm"], cwd=output_dir)

    assert raw.exit_code() == 2
    assert {finding.keyword for finding in raw.findings} == {"PatientBirthDate", "PatientID", "PatientName", "PrivateTags"}
    assert clean.exit_code() == 0
    assert private.exit_code() == 1
    assert [finding.keyword for finding in private.findings] == ["PrivateTags"]
