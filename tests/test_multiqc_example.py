from __future__ import annotations

import subprocess
import os
from pathlib import Path


def test_multiqc_example_script_generates_custom_content():
    output = Path("examples/multiqc/output-test")
    result = subprocess.run(
        ["bash", "examples/multiqc/run_example.sh"],
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "OUT_DIR": str(output.resolve())},
    )

    assert result.returncode == 0
    assert (output / "dicomqc" / "report.json").exists()
    assert (output / "dicomqc" / "findings.csv").exists()
    assert (output / "dicomqc" / "dicomqc_mqc" / "dicomqc_00_overview_mqc.html").exists()
    assert (output / "dicomqc" / "dicomqc_mqc" / "dicomqc_summary_mqc.yaml").exists()
    assert (output / "dicomqc" / "dicomqc_mqc" / "dicomqc_01_release_status_mqc.yaml").exists()
    assert (output / "dicomqc" / "dicomqc_mqc" / "dicomqc_02_findings_mqc.yaml").exists()
    if "MultiQC report:" in result.stdout:
        assert (output / "multiqc_report.html").exists()
        assert (output / "multiqc_data").is_dir()
    else:
        assert "MultiQC is not installed" in result.stdout
