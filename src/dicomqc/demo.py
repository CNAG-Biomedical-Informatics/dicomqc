"""Self-contained demo workflow for dicomqc."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from dicomqc.fixtures import write_synthetic_dicom_fixtures
from dicomqc.reports import write_csv, write_json, write_multiqc
from dicomqc.scanner import scan_paths


@dataclass(frozen=True)
class DemoResult:
    output_dir: Path
    dicom_dir: Path
    report_dir: Path
    json_path: Path
    csv_path: Path
    multiqc_dir: Path
    scan_exit_code: int


def run_demo(output_dir: Path, *, force: bool = False) -> DemoResult:
    """Generate synthetic DICOM files and run dicomqc reports into output_dir."""

    if output_dir.exists():
        if not force:
            raise FileExistsError(
                f"Demo output already exists: {output_dir}. Use --force to replace it."
            )
        shutil.rmtree(output_dir)

    dicom_dir = output_dir / "dicom"
    report_dir = output_dir / "dicomqc"
    multiqc_dir = report_dir / "dicomqc_mqc"
    json_path = report_dir / "report.json"
    csv_path = report_dir / "findings.csv"

    write_synthetic_dicom_fixtures(dicom_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    result = scan_paths([dicom_dir], cwd=output_dir)
    write_json(result, json_path)
    write_csv(result, csv_path)
    write_multiqc(result, multiqc_dir)

    return DemoResult(
        output_dir=output_dir,
        dicom_dir=dicom_dir,
        report_dir=report_dir,
        json_path=json_path,
        csv_path=csv_path,
        multiqc_dir=multiqc_dir,
        scan_exit_code=result.exit_code(),
    )
