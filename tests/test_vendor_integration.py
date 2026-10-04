"""Opt-in vendor inventories, report privacy, and reproducible synthetic demos."""

from __future__ import annotations

import csv
from dataclasses import replace
import hashlib
from html import escape
import json
from pathlib import Path

import pytest
from pydicom import dcmread
from pydicom.dataset import Dataset

from dicomqc.cli import main
from dicomqc.demo import DemoValidationError, run_vendor_demo
from dicomqc.fixtures import write_vendor_fixtures
from dicomqc.reports import write_csv, write_html, write_json, write_multiqc
from dicomqc.reports.csv import FIELDNAMES
from dicomqc.reports.json import result_to_dict
from dicomqc.rules.policy import load_policy
from dicomqc.scanner import scan_paths


PRIVATE_PAYLOADS = (
    "SYNTHETIC_PRIVATE_PAYLOAD_DO_NOT_REPORT",
    "SYNTHETIC_NESTED_PAYLOAD_DO_NOT_REPORT",
    "SYNTHETIC_ORPHAN_PAYLOAD_DO_NOT_REPORT",
)


def _digests(paths: list[Path]) -> dict[Path, str]:
    return {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}


def _assert_expected_inventory(summary: dict) -> None:
    assert summary["files"] == 3
    assert summary["private_elements"] == 5
    assert summary["creator_elements"] == 4
    assert summary["unassigned_private_elements"] == 1
    assert sorted(summary["equipment"], key=lambda row: row["software_versions"]) == [
        {"manufacturer": "Example Imaging", "model": "Research MR", "software_versions": ["1.0"], "files": 2},
        {"manufacturer": "Example Imaging", "model": "Research MR", "software_versions": ["1.1"], "files": 1},
    ]
    blocks = {row["creator"]: row for row in summary["private_blocks"]}
    assert len(blocks) == 3
    for creator, files, elements, nested, state in (
        ("ACME_ACQUISITION", 3, 3, 0, "present"),
        ("ACME_PROCESSING", 1, 1, 1, "present"),
        (None, 1, 1, 1, "absent"),
    ):
        assert blocks[creator] == {
            "group": "0029", "block": "10", "creator": creator, "creator_state": state,
            "files": files, "occurrences": files, "elements": elements, "nested_elements": nested,
        }


def test_vendor_inventory_groups_equipment_and_dataset_local_creators_without_modifying_files(tmp_path):
    paths = write_vendor_fixtures(tmp_path / "dicom")
    original = _digests(paths)
    result = scan_paths(paths, vendor_summary=True)

    _assert_expected_inventory(result.vendor_summary)
    assert result.files_scanned == 3
    assert result.warning_count == 3
    assert result.error_count == 0
    assert result.exit_code() == 1
    assert {finding.keyword for finding in result.findings} == {"PrivateTags"}
    assert _digests(paths) == original


def test_vendor_summary_does_not_change_baseline_findings(tmp_path):
    paths = write_vendor_fixtures(tmp_path / "dicom")
    baseline = scan_paths(paths)
    inventory = scan_paths(paths, vendor_summary=True)

    assert baseline.vendor_summary is None
    assert baseline.findings == inventory.findings
    assert baseline.records == inventory.records
    assert baseline.exit_code() == inventory.exit_code() == 1
    assert "vendor_summary" not in result_to_dict(baseline)
    assert result_to_dict(inventory)["vendor_summary"] == inventory.vendor_summary


def test_nested_equipment_values_cannot_override_top_level_equipment(tmp_path):
    paths = write_vendor_fixtures(tmp_path / "dicom")
    dataset = dcmread(paths[2])
    nested = Dataset()
    nested.Manufacturer = "NESTED_VENDOR_MUST_NOT_OVERRIDE"
    nested.ManufacturerModelName = "NESTED_MODEL_MUST_NOT_OVERRIDE"
    nested.SoftwareVersions = "NESTED_VERSION_MUST_NOT_OVERRIDE"
    dataset.ContributingEquipmentSequence = [nested]
    dataset.save_as(paths[2], enforce_file_format=True)

    result = scan_paths(paths, vendor_summary=True)
    _assert_expected_inventory(result.vendor_summary)
    assert "MUST_NOT_OVERRIDE" not in json.dumps(result.vendor_summary)


def test_default_reports_do_not_include_private_creators_models_or_software_values(tmp_path):
    paths = write_vendor_fixtures(tmp_path / "dicom")
    for path in paths:
        dataset = dcmread(path)
        dataset.SoftwareVersions = "VERSION_NOT_OPTED_IN"
        dataset.save_as(path, enforce_file_format=True)
    result = scan_paths(paths)
    report_json, report_html = tmp_path / "report.json", tmp_path / "report.html"
    write_json(result, report_json)
    write_html(result, report_html)
    bundle = write_multiqc(result, tmp_path / "multiqc")

    # Ordinary scan JSON historically includes manufacturer, but not these
    # newly inventoried values or the raw private-element payloads.
    combined = "\n".join(path.read_text(encoding="utf-8") for path in (report_json, report_html, *bundle.iterdir()))
    for value in ("ACME_ACQUISITION", "ACME_PROCESSING", "Research MR", "VERSION_NOT_OPTED_IN", *PRIVATE_PAYLOADS):
        assert value not in combined


def test_cli_opt_in_writes_inventory_to_json_html_multiqc_but_keeps_csv_findings_only(tmp_path, capsys):
    paths = write_vendor_fixtures(tmp_path / "dicom")
    original = _digests(paths)
    report_json, report_html, report_csv = (tmp_path / name for name in ("report.json", "report.html", "findings.csv"))
    bundle = tmp_path / "multiqc"
    assert main([
        "scan", str(tmp_path / "dicom"), "--vendor-summary", "--json", str(report_json),
        "--html", str(report_html), "--csv", str(report_csv), "--multiqc", str(bundle),
    ]) == 1
    console = capsys.readouterr().out
    assert "Files scanned: 3" in console
    assert "Equipment combinations: 2" in console
    assert "Unassigned private elements: 1" in console
    _assert_expected_inventory(json.loads(report_json.read_text(encoding="utf-8"))["vendor_summary"])
    for report in (report_html, bundle / "dicomqc_00_overview_mqc.html"):
        text = report.read_text(encoding="utf-8")
        assert "Example Imaging" in text and "Research MR" in text
        assert "ACME_ACQUISITION" in text and "ACME_PROCESSING" in text
        assert "Scanner and private-tag inventory" in text
        assert "Contains observed metadata labels." in text
        assert "may identify people or sites." in text
        assert "Private payload values are not included." in text
        opening = ('<details class="supporting" id="vendor-panel">' if report == report_html
                   else '<details class="vendor-panel">')
        assert opening in text  # No `open`: the inventory starts collapsed.
    with report_csv.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames == FIELDNAMES
        rows = list(reader)
    assert len(rows) == 3
    assert {row["keyword"] for row in rows} == {"PrivateTags"}
    assert "ACME_ACQUISITION" not in report_csv.read_text(encoding="utf-8")
    combined = "\n".join(path.read_text(encoding="utf-8") for path in (report_json, report_html, report_csv, *bundle.iterdir()))
    for value in PRIVATE_PAYLOADS:
        assert value not in combined
    assert _digests(paths) == original


def test_explicit_vendor_inventory_can_be_combined_with_policy_audit(tmp_path):
    paths = write_vendor_fixtures(tmp_path / "dicom")
    policy_path = tmp_path / "policy.yaml"
    policy_path.write_text(
        'version: 1\nid: inventory-policy\nrules:\n'
        '  - id: patient-format\n    keyword: PatientID\n    check: matches\n'
        '    pattern: "sub-[0-9][0-9][0-9]"\n', encoding="utf-8",
    )
    policy = load_policy(policy_path)
    without_inventory = result_to_dict(scan_paths(paths, policy=policy))
    assert "Example Imaging" not in json.dumps(without_inventory)
    report = tmp_path / "report.json"
    assert main([
        "scan", str(tmp_path / "dicom"), "--policy", str(policy_path), "--vendor-summary",
        "--json", str(report), "--quiet",
    ]) == 1
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["policy"]["id"] == "inventory-policy"
    _assert_expected_inventory(payload["vendor_summary"])
    assert all("manufacturer" not in record for record in payload["records"])
    for value in PRIVATE_PAYLOADS:
        assert value not in report.read_text(encoding="utf-8")


def test_inventory_counts_only_readable_files_and_does_not_hide_read_errors(tmp_path):
    paths = write_vendor_fixtures(tmp_path / "dicom")
    broken = tmp_path / "dicom" / "broken.dcm"
    broken.write_bytes(b"not DICOM")
    result = scan_paths([*paths, broken], vendor_summary=True)
    _assert_expected_inventory(result.vendor_summary)
    assert len(result.skipped_files) == 1
    assert result.exit_code() == 2


def test_inventory_for_no_readable_files_is_not_a_passing_audit(tmp_path):
    broken = tmp_path / "broken.dcm"
    broken.write_bytes(b"not DICOM")
    result = scan_paths([broken], vendor_summary=True)
    summary = result.vendor_summary
    assert summary["files"] == 0
    assert summary["equipment"] == []
    assert summary["private_blocks"] == []
    assert summary["private_elements"] == summary["creator_elements"] == summary["unassigned_private_elements"] == 0
    assert result.exit_code() == 2
    report = tmp_path / "empty.html"
    write_html(result, report)
    bundle = write_multiqc(result, tmp_path / "multiqc")
    for html in (report, bundle / "dicomqc_00_overview_mqc.html"):
        assert "No entries in the readable files." in html.read_text(encoding="utf-8")
        assert "Errors require attention" in html.read_text(encoding="utf-8")


def test_vendor_html_and_multiqc_escape_observed_metadata_labels(tmp_path):
    path = write_vendor_fixtures(tmp_path / "dicom")[0]
    dataset = dcmread(path)
    labels = {
        "Manufacturer": '<script>vendorInjected()</script>',
        "ManufacturerModelName": '<svg onload="modelInjected()">',
        "SoftwareVersions": '<img src=x onerror="versionInjected()">',
    }
    creator = '<svg onload="creatorInjected()">'
    for keyword, value in labels.items():
        setattr(dataset, keyword, value)
    dataset[(0x0029, 0x0010)].value = creator
    dataset.save_as(path, enforce_file_format=True)
    result = scan_paths([path], vendor_summary=True)
    report = tmp_path / "report.html"
    write_html(result, report)
    bundle = write_multiqc(result, tmp_path / "multiqc")
    for html in (report, bundle / "dicomqc_00_overview_mqc.html"):
        content = html.read_text(encoding="utf-8")
        for value in (*labels.values(), creator):
            assert value not in content
            assert escape(value) in content


def test_vendor_reports_explain_missing_equipment_and_unusable_creators(tmp_path):
    path = write_vendor_fixtures(tmp_path / "dicom")[0]
    dataset = dcmread(path)
    for keyword in ("Manufacturer", "ManufacturerModelName", "SoftwareVersions"):
        delattr(dataset, keyword)
    dataset.remove_private_tags()
    dataset.add_new((0x0029, 0x0010), "LO", "")
    dataset.add_new((0x0029, 0x1010), "LO", "EMPTY_CREATOR_PAYLOAD_SECRET")
    dataset.add_new((0x0029, 0x0011), "LT", "INVALID_CREATOR_VR")
    dataset.add_new((0x0029, 0x1110), "LO", "INVALID_CREATOR_PAYLOAD_SECRET")
    dataset.add_new((0x0029, 0x1210), "LO", "ABSENT_CREATOR_PAYLOAD_SECRET")
    dataset.add_new((0x0029, 0x0001), "LO", "UNASSIGNED_BLOCK_PAYLOAD_SECRET")
    dataset.save_as(path, enforce_file_format=True)
    result = scan_paths([path], vendor_summary=True)
    report = tmp_path / "report.html"
    write_html(result, report)
    bundle = write_multiqc(result, tmp_path / "multiqc")
    for html in (report, bundle / "dicomqc_00_overview_mqc.html"):
        content = html.read_text(encoding="utf-8")
        for explanation in ("Not recorded", "Empty creator", "No creator", "Invalid creator", "(0029,unassigned)"):
            assert explanation in content
        assert "PAYLOAD_SECRET" not in content


def test_compare_does_not_accept_vendor_summary_option():
    with pytest.raises(SystemExit, match="2"):
        main(["compare", "source", "candidate", "--manifest", "pairs.csv", "--vendor-summary"])


def test_vendor_demo_produces_expected_real_audit_and_can_be_repeated(tmp_path):
    output = tmp_path / "vendor-demo"
    demo = run_vendor_demo(output)
    assert demo.scan_exit_code == 1
    assert demo.dicom_dir == output / "dicom"
    assert demo.report_dir == output / "dicomqc"
    assert (demo.report_dir / "report.html").is_file()
    assert (demo.multiqc_dir / "dicomqc_00_overview_mqc.html").is_file()
    payload = json.loads(demo.json_path.read_text(encoding="utf-8"))
    _assert_expected_inventory(payload["vendor_summary"])
    assert payload["summary"]["warnings"] == 3
    assert payload["summary"]["errors"] == 0
    original = _digests(list(demo.dicom_dir.iterdir()))
    repeated = scan_paths([demo.dicom_dir], cwd=output, vendor_summary=True)
    assert result_to_dict(repeated) == payload
    assert _digests(list(demo.dicom_dir.iterdir())) == original
    with pytest.raises(FileExistsError):
        run_vendor_demo(output)
    assert run_vendor_demo(output, force=True).scan_exit_code == 1


def test_vendor_demo_cli_and_mutually_exclusive_modes(tmp_path, capsys):
    output = tmp_path / "vendor-demo"
    assert main(["demo", "--vendor-demo", "--output-dir", str(output)]) == 0
    assert (output / "dicomqc" / "report.html").exists()
    captured = capsys.readouterr()
    assert "1" in captured.out
    assert not captured.err
    for other_mode in ("--compare", "--policy-demo"):
        with pytest.raises(SystemExit, match="2"):
            main(["demo", "--vendor-demo", other_mode, "--output-dir", str(output)])


@pytest.mark.parametrize("problem", ["findings", "files", "private_count", "missing_summary", "equipment", "private_blocks"])
def test_vendor_demo_rejects_unexpected_audit_or_inventory(tmp_path, monkeypatch, problem):
    def unexpected(*args, **kwargs):
        result = scan_paths(*args, **kwargs)
        if problem == "findings":
            return replace(result, findings=[])
        if problem == "files":
            return replace(result, records=[])
        if problem == "missing_summary":
            return replace(result, vendor_summary=None)
        summary = dict(result.vendor_summary)
        if problem == "private_count":
            summary["private_elements"] = 0
        else:
            summary[problem] = []
        return replace(result, vendor_summary=summary)

    monkeypatch.setattr("dicomqc.demo.scan_paths", unexpected)
    output = tmp_path / "vendor-demo"
    with pytest.raises(DemoValidationError, match="unexpected results"):
        run_vendor_demo(output)
    assert (output / "dicomqc" / "report.json").exists()


def test_vendor_demo_force_does_not_replace_unrecognized_directory(tmp_path):
    output = tmp_path / "real-data"
    output.mkdir()
    protected = output / "keep.dcm"
    protected.write_bytes(b"user data")
    with pytest.raises(ValueError, match="only replaces directories created"):
        run_vendor_demo(output, force=True)
    assert protected.read_bytes() == b"user data"
