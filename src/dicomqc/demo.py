"""Self-contained demo workflow for dicomqc."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from dicomqc.compare import ComparisonResult, compare_datasets
from dicomqc.fixtures import (
    write_comparison_fixtures, write_policy_fixtures, write_synthetic_dicom_fixtures, write_vendor_fixtures,
    write_uid_fixtures,
)
from dicomqc.model.results import ScanResult
from dicomqc.rules.policy import load_policy
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


@dataclass(frozen=True)
class PolicyDemoResult:
    output_dir: Path
    policy_path: Path
    before: ScanResult
    after: ScanResult


@dataclass(frozen=True)
class UIDDemoResult:
    output_dir: Path
    before: ScanResult
    after: ScanResult


def run_uid_demo(output_dir: Path, *, force: bool = False) -> UIDDemoResult:
    """Show UID checks on independent failing and corrected synthetic exports."""
    _prepare_output(output_dir, force)
    write_uid_fixtures(output_dir)
    before = scan_paths([output_dir / "candidate"], cwd=output_dir, uid_checks=True)
    after = scan_paths([output_dir / "corrected"], cwd=output_dir, uid_checks=True)
    for name, result in (("before", before), ("after", after)):
        write_json(result, output_dir / f"{name}.json")
        write_csv(result, output_dir / f"{name}.csv")
        write_html(result, output_dir / f"{name}.html", synthetic=True, demo_phase=name)
        write_multiqc(result, output_dir / f"{name}_mqc")
    if (before.error_count != 7 or before.exit_code() != 2 or after.exit_code() != 0
            or before.files_scanned != 4 or after.files_scanned != 4):
        raise DemoValidationError("UID demo produced unexpected results; inspect the before/after reports.")
    return UIDDemoResult(output_dir, before, after)


def run_vendor_demo(output_dir: Path, *, force: bool = False) -> DemoResult:
    """Show explicit vendor inventory without exposing private-element payloads."""
    _prepare_output(output_dir, force)
    dicom_dir = output_dir / "dicom"
    report_dir = output_dir / "dicomqc"
    multiqc_dir = report_dir / "dicomqc_mqc"
    json_path = report_dir / "report.json"
    csv_path = report_dir / "findings.csv"
    write_vendor_fixtures(dicom_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    result = scan_paths([dicom_dir], cwd=output_dir, vendor_summary=True)
    write_json(result, json_path)
    write_csv(result, csv_path)
    write_html(result, report_dir / "report.html", synthetic=True)
    write_multiqc(result, multiqc_dir)
    summary = result.vendor_summary or {}
    if (result.exit_code() != 1 or result.files_scanned != 3 or result.warning_count != 3
            or summary.get("files") != 3 or summary.get("private_elements") != 5
            or summary.get("creator_elements") != 4 or summary.get("unassigned_private_elements") != 1
            or len(summary.get("equipment", [])) != 2 or len(summary.get("private_blocks", [])) != 3):
        raise DemoValidationError("Vendor demo produced unexpected results; inspect its reports.")
    return DemoResult(
        output_dir=output_dir, dicom_dir=dicom_dir, report_dir=report_dir,
        json_path=json_path, csv_path=csv_path, multiqc_dir=multiqc_dir,
        scan_exit_code=result.exit_code(),
    )


def run_policy_demo(output_dir: Path, *, force: bool = False) -> PolicyDemoResult:
    """Show opt-in policy checks on synthetic descriptors and de-identification markers."""
    _prepare_output(output_dir, force)
    policy_path = write_policy_fixtures(output_dir)
    policy = load_policy(policy_path)
    before = scan_paths([output_dir / "candidate"], cwd=output_dir, policy=policy)
    after = scan_paths([output_dir / "corrected"], cwd=output_dir, policy=policy)
    for name, result in (("before", before), ("after", after)):
        write_json(result, output_dir / f"{name}.json")
        write_csv(result, output_dir / f"{name}.csv")
        write_html(result, output_dir / f"{name}.html", synthetic=True, demo_phase=name)
    if (before.error_count != 3 or before.exit_code() != 2 or after.exit_code() != 0
            or before.files_scanned != 1 or after.files_scanned != 1):
        raise DemoValidationError("Policy demo produced unexpected results; inspect the before/after reports.")
    return PolicyDemoResult(output_dir, policy_path, before, after)


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
