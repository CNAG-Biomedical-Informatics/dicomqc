"""Self-contained demo workflow for dicomqc."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from dicomqc.compare import ComparisonResult, compare_datasets
from dicomqc.fixtures import write_comparison_fixtures, write_synthetic_dicom_fixtures
from dicomqc.reports import write_csv, write_html, write_json, write_multiqc
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


@dataclass(frozen=True)
class ComparisonDemoResult:
    output_dir: Path
    manifest: Path
    before: ComparisonResult
    after: ComparisonResult


class DemoValidationError(ValueError):
    """The generated example did not produce its expected audit results."""


def _prepare_output(output_dir: Path, force: bool) -> None:
    resolved = output_dir.resolve()
    if output_dir.is_symlink() or resolved in (Path.home(), Path.cwd()) or resolved in Path.cwd().parents:
        raise ValueError("Choose a separate demo directory, not a symlink, home, or working directory ancestor.")
    if output_dir.exists():
        if not force:
            raise FileExistsError(
                f"Demo output already exists: {output_dir}. Use --force to replace it."
            )
        marker = output_dir / ".dicomqc-demo"
        if marker.is_symlink() or not marker.is_file() or marker.read_text() != "dicomqc demo\n":
            raise ValueError("--force only replaces directories created by this version of dicomqc demo.")
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)
    (output_dir / ".dicomqc-demo").write_text("dicomqc demo\n")


def run_comparison_demo(output_dir: Path, *, force: bool = False) -> ComparisonDemoResult:
    """Generate independent synthetic failing and corrected comparison examples."""
    _prepare_output(output_dir, force)
    manifest = write_comparison_fixtures(output_dir)
    before = compare_datasets(output_dir / "source", output_dir / "candidate", manifest)
    after = compare_datasets(output_dir / "source", output_dir / "corrected", manifest)
    for name, result in (("before", before), ("after", after)):
        write_json(result, output_dir / f"{name}.json")
        write_csv(result, output_dir / f"{name}.csv")
        write_html(result, output_dir / f"{name}.html", synthetic=True, demo_phase=name)
    expected_rules = {
        "dataset-comparison-v0.1.missing_candidate",
        "dataset-comparison-v0.1.inconsistent_pseudonym",
    }
    if (before.exit_code() != 2 or before.error_count != 3
            or {finding.rule_id for finding in before.findings} != expected_rules
            or after.exit_code() != 0 or after.comparison["identity_pairs_checked"] != 3):
        raise DemoValidationError("Comparison demo produced unexpected results; inspect the before/after reports.")
    return ComparisonDemoResult(output_dir, manifest, before, after)


def run_demo(output_dir: Path, *, force: bool = False) -> DemoResult:
    """Generate synthetic DICOM files and run dicomqc reports into output_dir."""

    _prepare_output(output_dir, force)

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
    write_html(result, report_dir / "report.html", synthetic=True)
    write_multiqc(result, multiqc_dir)
    if result.exit_code() != 2 or result.files_scanned != 3:
        raise DemoValidationError("Scan demo produced unexpected results; inspect its reports.")

    return DemoResult(
        output_dir=output_dir,
        dicom_dir=dicom_dir,
        report_dir=report_dir,
        json_path=json_path,
        csv_path=csv_path,
        multiqc_dir=multiqc_dir,
        scan_exit_code=result.exit_code(),
    )
