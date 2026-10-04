"""Project-policy integration, provenance, and read-only safety checks."""

from __future__ import annotations

import csv
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path

import pytest
import yaml
from pydicom import dcmread
from pydicom.dataset import Dataset

from dicomqc.backend.pydicom_backend import PydicomBackend
from dicomqc.cli import main
from dicomqc.compare import compare_datasets
from dicomqc.fixtures import _write_dicom
from dicomqc.reports import write_csv, write_html, write_json, write_multiqc
from dicomqc.reports.csv import FIELDNAMES
from dicomqc.reports.json import result_to_dict
from dicomqc.rules.builtin import DEFAULT_PROFILE_ID
from dicomqc.rules.policy import load_policy
from dicomqc.scanner import scan_paths


def _image(path: Path, *, patient_id: str = "sub-001", **values) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_dicom(
        path,
        fixture_index=1,
        patient_id=patient_id,
        patient_name="sub-001",
        patient_birth_date=None,
        private_creator=None,
    )
    dataset = dcmread(path)
    for keyword, value in values.items():
        setattr(dataset, keyword, value)
    dataset.save_as(path, enforce_file_format=True)
    return path


def _policy(path: Path, *rules: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump({"version": 1, "id": "project-test", "rules": list(rules)}),
        encoding="utf-8",
    )
    return path


def _description_rule(**overrides) -> dict:
    return {
        "id": "descriptions",
        "keyword": "StudyDescription",
        "check": "allowed_values",
        "values": ["T1w", "T2w"],
        "severity": "error",
        **overrides,
    }


def _pair(tmp_path: Path, **candidate_values) -> tuple[Path, Path, Path]:
    source, candidate = tmp_path / "source", tmp_path / "candidate"
    _image(
        source / "sensitive-source-name.dcm",
        patient_id="SOURCE_PATIENT_SECRET",
        StudyDescription="SOURCE_DESCRIPTION_SECRET",
        PatientComments="SOURCE_COMMENT_SECRET",
    )
    _image(candidate / "sensitive-candidate-name.dcm", **candidate_values)
    manifest = tmp_path / "pairs.csv"
    manifest.write_text(
        "source,candidate\nsensitive-source-name.dcm,sensitive-candidate-name.dcm\n",
        encoding="utf-8",
    )
    return source, candidate, manifest


def _provenance(policy: Path) -> dict[str, str]:
    return {"id": "project-test", "sha256": hashlib.sha256(policy.read_bytes()).hexdigest()}


def test_scan_policy_is_additive_and_never_changes_inputs(tmp_path):
    path = _image(
        tmp_path / "dicom" / "image.dcm",
        StudyDescription="DESCRIPTION_SECRET",
        PatientBirthDate="19700101",
    )
    policy = _policy(tmp_path / "policy.yaml", _description_rule())
    original = path.read_bytes()

    baseline = scan_paths([path])
    result = scan_paths([path], policy=load_policy(policy))

    assert baseline.error_count == 1
    assert result.error_count == 2
    assert result.profile_id == DEFAULT_PROFILE_ID
    assert {finding.keyword for finding in result.findings} == {"PatientBirthDate", "StudyDescription"}
    assert result.policy == _provenance(policy)
    assert path.read_bytes() == original
    assert "DESCRIPTION_SECRET" not in json.dumps(result_to_dict(result))


@pytest.mark.parametrize("severity,exit_code", [("error", 2), ("warning", 1), ("info", 0)])
def test_cli_policy_severity_controls_exit_code(tmp_path, severity, exit_code):
    path = _image(tmp_path / "image.dcm", StudyDescription="FREE_TEXT_SECRET")
    policy = _policy(tmp_path / "policy.yaml", _description_rule(severity=severity))

    assert main(["scan", str(path), "--policy", str(policy), "--quiet"]) == exit_code


def test_all_reports_preserve_policy_provenance_without_raw_values(tmp_path):
    path = _image(tmp_path / "image.dcm", StudyDescription="DESCRIPTION_SECRET")
    policy = _policy(
        tmp_path / "policy.yaml",
        _description_rule(values=["POLICY_ALLOWLIST_SECRET"]),
    )
    result = scan_paths([path], policy=load_policy(policy))
    report_json, report_csv, report_html = (tmp_path / name for name in ("report.json", "report.csv", "report.html"))
    write_json(result, report_json)
    write_csv(result, report_csv)
    write_html(result, report_html)
    bundle = write_multiqc(result, tmp_path / "multiqc")

    payload = json.loads(report_json.read_text(encoding="utf-8"))
    assert payload["policy"] == _provenance(policy)
    for report in (report_html, bundle / "dicomqc_00_overview_mqc.html"):
        text = report.read_text(encoding="utf-8")
        assert "project-test" in text
        assert payload["policy"]["sha256"] in text
    with report_csv.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames == FIELDNAMES
        rows = list(reader)
    assert len(rows) == 1
    assert rows[0]["keyword"] == "StudyDescription"
    combined = "\n".join(file.read_text(encoding="utf-8") for file in (report_json, report_csv, report_html, *bundle.iterdir()))
    for secret in ("DESCRIPTION_SECRET", "POLICY_ALLOWLIST_SECRET"):
        assert secret not in combined


def test_passing_policy_is_recorded_even_with_no_findings(tmp_path):
    path = _image(tmp_path / "image.dcm", StudyDescription="T1w")
    policy = _policy(tmp_path / "policy.yaml", _description_rule())
    report_json, report_html, bundle = (tmp_path / name for name in ("report.json", "report.html", "multiqc"))

    assert main([
        "scan", str(path), "--policy", str(policy), "--json", str(report_json),
        "--html", str(report_html), "--multiqc", str(bundle), "--quiet",
    ]) == 0
    payload = json.loads(report_json.read_text(encoding="utf-8"))
    assert payload["findings"] == []
    assert payload["policy"] == _provenance(policy)
    assert payload["policy"]["sha256"] in report_html.read_text(encoding="utf-8")
    assert payload["policy"]["sha256"] in (bundle / "dicomqc_00_overview_mqc.html").read_text(encoding="utf-8")


def test_policy_scan_json_omits_all_raw_record_context(tmp_path):
    values = {
        "Manufacturer": "VENDOR_CONTEXT_SECRET",
        "Modality": "PRIVATE_MODALITY",
        "StudyInstanceUID": "1.2.826.0.1.3680043.10.54321.987654321",
        "SeriesInstanceUID": "1.2.826.0.1.3680043.10.54321.123456789",
    }
    path = _image(tmp_path / "image.dcm", StudyDescription="T1w", **values)
    # The policy does not inspect any of the context fields: all raw values
    # must still be omitted, rather than redacting only policy-targeted fields.
    policy = _policy(tmp_path / "policy.yaml", _description_rule())
    report = tmp_path / "policy.json"
    assert main(["scan", str(path), "--policy", str(policy), "--json", str(report), "--quiet"]) == 0
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["findings"] == []
    assert payload["policy"] == _provenance(policy)
    for value in values.values():
        assert value not in report.read_text(encoding="utf-8")
    assert not {"manufacturer", "modality", "study_uid", "series_uid"}.intersection(payload["records"][0])


def test_scan_without_policy_preserves_existing_json_context(tmp_path):
    path = _image(tmp_path / "image.dcm", Manufacturer="EXAMPLE_VENDOR", Modality="MR")
    dataset = dcmread(path)
    payload = result_to_dict(scan_paths([path]))
    assert payload["records"][0]["manufacturer"] == "EXAMPLE_VENDOR"
    assert payload["records"][0]["modality"] == "MR"
    assert payload["records"][0]["study_uid"] == dataset.StudyInstanceUID
    assert payload["records"][0]["series_uid"] == dataset.SeriesInstanceUID


def test_unreadable_scan_retains_policy_provenance(tmp_path):
    image = tmp_path / "broken.dcm"
    image.write_bytes(b"not a DICOM file")
    policy = _policy(tmp_path / "policy.yaml", _description_rule())
    result = scan_paths([image], policy=load_policy(policy))
    assert result.exit_code() == 2
    assert result.files_scanned == 0
    assert result_to_dict(result)["policy"] == _provenance(policy)


def test_identifier_formats_and_required_metadata_run_on_pydicom_values(tmp_path):
    path = _image(tmp_path / "image.dcm", patient_id="sub-ABC", DeidentificationMethod="")
    policy = _policy(tmp_path / "policy.yaml", {
        "id": "patient-format", "keyword": "PatientID", "check": "matches", "pattern": "sub-[0-9][0-9][0-9]",
    }, {
        "id": "method", "keyword": "DeidentificationMethod", "check": "nonempty",
    })
    result = scan_paths([path], policy=load_policy(policy))
    assert result.error_count == 2
    assert result.warning_count == 0
    assert {finding.keyword for finding in result.findings} == {"PatientID", "DeidentificationMethod"}
    _image(path, patient_id="sub-001", DeidentificationMethod="Example project protocol")
    assert scan_paths([path], policy=load_policy(policy)).exit_code() == 0


def test_nested_markers_cannot_satisfy_top_level_policy(tmp_path):
    previous = Dataset()
    previous.PatientIdentityRemoved = "YES"
    original = Dataset()
    original.ModifiedAttributesSequence = [previous]
    path = _image(tmp_path / "image.dcm", OriginalAttributesSequence=[original])
    record = PydicomBackend().read_metadata(path)
    marker = [tag for tag in record.tags.values() if tag.keyword == "PatientIdentityRemoved"]
    assert len(marker) == 1 and marker[0].is_nested
    policy = _policy(tmp_path / "policy.yaml", {
        "id": "identity-marker", "keyword": "PatientIdentityRemoved",
        "check": "allowed_values", "values": ["YES"], "severity": "error", "scope": "top_level",
    })

    result = scan_paths([path], policy=load_policy(policy))
    assert result.error_count == 1
    assert result.findings[0].value_state.value == "absent"


def test_all_scope_checks_every_repeated_nested_value(tmp_path):
    items = []
    for value in ("", "NESTED_COMMENT_SECRET_A", "NESTED_COMMENT_SECRET_B"):
        item = Dataset()
        item.PatientComments = value
        items.append(item)
    path = _image(tmp_path / "image.dcm", RequestAttributesSequence=items)
    rule = {"id": "comments", "keyword": "PatientComments", "check": "absent_or_empty", "severity": "error"}
    policy = _policy(tmp_path / "all.yaml", rule)
    top_policy = _policy(tmp_path / "top.yaml", {**rule, "scope": "top_level"})

    result = scan_paths([path], policy=load_policy(policy))
    assert result.error_count == 2
    assert scan_paths([path], policy=load_policy(top_policy)).exit_code() == 0
    assert "NESTED_COMMENT_SECRET" not in json.dumps(result_to_dict(result))


def test_comparison_policy_is_candidate_only_and_uses_safe_pair_references(tmp_path):
    source, candidate, manifest = _pair(tmp_path, StudyDescription="T1w")
    policy = _policy(tmp_path / "policy.yaml", _description_rule(), {
        "id": "comments", "keyword": "PatientComments", "check": "absent_or_empty", "severity": "error",
    })
    original = {path: path.read_bytes() for root in (source, candidate) for path in root.iterdir()}

    passing = compare_datasets(source, candidate, manifest, policy=load_policy(policy))
    assert passing.exit_code() == 0
    assert passing.policy == _provenance(policy)
    assert all(path.read_bytes() == data for path, data in original.items())
    _image(candidate / "sensitive-candidate-name.dcm", StudyDescription="CANDIDATE_DESCRIPTION_SECRET")
    report_json, report_csv, report_html = (tmp_path / name for name in ("compare.json", "compare.csv", "compare.html"))
    assert main([
        "compare", str(source), str(candidate), "--manifest", str(manifest), "--policy", str(policy),
        "--json", str(report_json), "--csv", str(report_csv), "--html", str(report_html), "--quiet",
    ]) == 2
    payload = json.loads(report_json.read_text(encoding="utf-8"))
    assert payload["policy"] == _provenance(policy)
    assert len(payload["findings"]) == 1
    assert payload["findings"][0]["path"] == "pair-000001/candidate"
    combined = "\n".join(report.read_text(encoding="utf-8") for report in (report_json, report_csv, report_html))
    for secret in (
        "SOURCE_PATIENT_SECRET", "SOURCE_DESCRIPTION_SECRET", "SOURCE_COMMENT_SECRET",
        "CANDIDATE_DESCRIPTION_SECRET", "sensitive-source-name", "sensitive-candidate-name",
    ):
        assert secret not in combined


@pytest.mark.parametrize("command", ["scan", "compare"])
@pytest.mark.parametrize("content", [
    "version: [PRIVATE_POLICY_SECRET\n",
    "version: 1\nid: project-test\nrules:\n  - id: marker\n    keyword: PatientIdentityRemoved\n    check: allowed_values\n    values: [YES, PRIVATE_POLICY_SECRET]\n",
    "version: 1\nid: project-test\nrules:\n  - id: field\n    keyword: PRIVATE_POLICY_SECRET\n    check: nonempty\n",
])
def test_invalid_policy_cli_errors_do_not_expose_values_or_write_reports(tmp_path, capsys, command, content):
    source, candidate, manifest = _pair(tmp_path, StudyDescription="T1w")
    policy = tmp_path / "policy.yaml"
    policy.write_text(content, encoding="utf-8")
    report = tmp_path / "report.json"
    args = (["scan", str(candidate)] if command == "scan" else [
        "compare", str(source), str(candidate), "--manifest", str(manifest),
    ])

    assert main([*args, "--policy", str(policy), "--json", str(report)]) == 2
    captured = capsys.readouterr()
    assert "PRIVATE_POLICY_SECRET" not in captured.out + captured.err
    assert not report.exists()


@pytest.mark.parametrize("command", ["scan", "compare"])
def test_missing_policy_is_a_controlled_cli_error(tmp_path, capsys, command):
    source, candidate, manifest = _pair(tmp_path, StudyDescription="T1w")
    args = (["scan", str(candidate)] if command == "scan" else [
        "compare", str(source), str(candidate), "--manifest", str(manifest),
    ])
    assert main([*args, "--policy", str(tmp_path / "MISSING_POLICY_SECRET.yaml")]) == 2
    captured = capsys.readouterr()
    assert "MISSING_POLICY_SECRET" not in captured.out + captured.err


@pytest.mark.parametrize("command", ["scan", "compare"])
@pytest.mark.parametrize("output_flag", ["--json", "--csv", "--html"])
@pytest.mark.parametrize("alias_kind", ["same", "symlink", "hardlink"])
def test_report_outputs_cannot_overwrite_policy(tmp_path, command, output_flag, alias_kind):
    source, candidate, manifest = _pair(tmp_path, StudyDescription="T1w")
    policy = _policy(tmp_path / "policy.yaml", _description_rule())
    original = policy.read_bytes()
    output = policy
    if alias_kind != "same":
        output = tmp_path / "alias"
        if alias_kind == "symlink":
            output.symlink_to(policy)
        else:
            os.link(policy, output)
    args = (["scan", str(candidate)] if command == "scan" else [
        "compare", str(source), str(candidate), "--manifest", str(manifest),
    ])

    assert main([*args, "--policy", str(policy), output_flag, str(output), "--quiet"]) == 2
    assert policy.read_bytes() == original
    assert output.read_bytes() == original


@pytest.mark.parametrize("command,side", [("scan", "candidate"), ("compare", "candidate"), ("compare", "source")])
def test_policy_must_be_stored_outside_scanned_inputs(tmp_path, command, side):
    source, candidate, manifest = _pair(tmp_path, StudyDescription="T1w")
    policy = _policy((source if side == "source" else candidate) / "policy.yaml", _description_rule())
    original = policy.read_bytes()
    report = tmp_path / "report.json"
    args = (["scan", str(candidate)] if command == "scan" else [
        "compare", str(source), str(candidate), "--manifest", str(manifest),
    ])

    assert main([*args, "--policy", str(policy), "--json", str(report), "--quiet"]) == 2
    assert not report.exists()
    assert policy.read_bytes() == original


@pytest.mark.parametrize("alias_kind", ["same", "symlink", "hardlink", "cleanup"])
def test_multiqc_output_preflight_preserves_policy_and_avoids_partial_reports(tmp_path, alias_kind):
    path = _image(tmp_path / "image.dcm", StudyDescription="T1w")
    bundle = tmp_path / "multiqc"
    bundle.mkdir()
    policy_location = bundle / "dicomqc_summary_mqc.yaml" if alias_kind == "same" else tmp_path / "policy.yaml"
    if alias_kind == "cleanup":
        policy_location = bundle / "custom_policy_mqc.yaml"
    policy = _policy(policy_location, _description_rule())
    original = policy.read_bytes()
    if alias_kind == "symlink":
        (bundle / "dicomqc_summary_mqc.yaml").symlink_to(policy)
    elif alias_kind == "hardlink":
        os.link(policy, bundle / "dicomqc_summary_mqc.yaml")
    report = tmp_path / "report.json"

    assert main([
        "scan", str(path), "--policy", str(policy), "--json", str(report), "--multiqc", str(bundle), "--quiet",
    ]) == 2
    assert policy.read_bytes() == original
    assert not report.exists()


@pytest.mark.parametrize("relation", ["equal_directory", "inside_directory", "ancestor_directory", "equal_file", "file_parent"])
def test_multiqc_bundle_cannot_overlap_dicom_inputs_or_change_existing_reports(tmp_path, relation):
    input_dir = tmp_path / "inputs" / "dicom"
    # DICOM discovery is extension-independent, so cleanup-looking names
    # remain legitimate input data and must never be unlinked by MultiQC.
    image = _image(input_dir / "image_mqc.yaml", StudyDescription="T1w")
    original = image.read_bytes()
    scan_input = image if relation in {"equal_file", "file_parent"} else input_dir
    bundles = {
        "equal_directory": input_dir,
        "inside_directory": input_dir / "reports",
        "ancestor_directory": input_dir.parent,
        "equal_file": image,
        "file_parent": input_dir,
    }
    bundle = bundles[relation]
    report = tmp_path / "report.json"
    report.write_text("PREEXISTING_REPORT", encoding="utf-8")

    assert main([
        "scan", str(scan_input), "--json", str(report), "--multiqc", str(bundle), "--quiet",
    ]) == 2
    assert image.read_bytes() == original
    assert report.read_text(encoding="utf-8") == "PREEXISTING_REPORT"


@pytest.mark.parametrize("output_flag", ["--json", "--csv", "--html"])
def test_multiqc_bundle_cannot_overlap_explicit_report_outputs(tmp_path, output_flag):
    image = _image(tmp_path / "image.dcm", StudyDescription="T1w")
    bundle = tmp_path / "multiqc"
    bundle.mkdir()
    output = bundle / "dicomqc_summary_mqc.yaml"
    output.write_text("PREEXISTING_REPORT", encoding="utf-8")
    another_output = bundle / "custom_mqc.html"
    another_output.write_text("UNRELATED_EXISTING_REPORT", encoding="utf-8")

    assert main([
        "scan", str(image), output_flag, str(output), "--multiqc", str(bundle), "--quiet",
    ]) == 2
    assert output.read_text(encoding="utf-8") == "PREEXISTING_REPORT"
    assert another_output.read_text(encoding="utf-8") == "UNRELATED_EXISTING_REPORT"


def test_multiqc_bundle_symlink_cannot_alias_input_directory(tmp_path):
    image = _image(tmp_path / "dicom" / "dicomqc_summary_mqc.yaml", StudyDescription="T1w")
    original = image.read_bytes()
    bundle = tmp_path / "multiqc"
    bundle.symlink_to(image.parent, target_is_directory=True)
    report = tmp_path / "report.json"

    assert main([
        "scan", str(image.parent), "--json", str(report), "--multiqc", str(bundle), "--quiet",
    ]) == 2
    assert image.read_bytes() == original
    assert not report.exists()


def test_policy_demo_is_reproducible_and_before_after_reports_are_real_audits(tmp_path):
    output = tmp_path / "policy-demo"
    assert main(["demo", "--policy-demo", "--output-dir", str(output)]) == 0
    assert (output / "policy.yaml").is_file()
    before, after = (json.loads((output / f"{name}.json").read_text(encoding="utf-8")) for name in ("before", "after"))
    assert before["summary"]["errors"] == 3
    assert after["summary"]["errors"] == 0
    assert after["findings"] == []
    assert before["policy"] == after["policy"]
    assert before["policy"]["sha256"] == hashlib.sha256((output / "policy.yaml").read_bytes()).hexdigest()
    assert scan_paths([output / "candidate"]).exit_code() == 0
    assert scan_paths([output / "candidate"], policy=load_policy(output / "policy.yaml")).error_count == 3
    assert scan_paths([output / "corrected"], policy=load_policy(output / "policy.yaml")).exit_code() == 0
    for name in ("before", "after"):
        assert (output / f"{name}.html").is_file()
        with (output / f"{name}.csv").open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        assert len(rows) == (3 if name == "before" else 0)
    assert main(["demo", "--policy-demo", "--output-dir", str(output)]) == 2
    assert main(["demo", "--policy-demo", "--output-dir", str(output), "--force"]) == 0


def test_policy_and_comparison_demos_are_mutually_exclusive(tmp_path):
    with pytest.raises(SystemExit, match="2"):
        main(["demo", "--policy-demo", "--compare", "--output-dir", str(tmp_path / "demo")])


@pytest.mark.parametrize("problem", ["before_findings", "after_skipped", "before_inventory", "after_inventory"])
def test_policy_demo_rejects_unexpected_audit_results(tmp_path, monkeypatch, capsys, problem):
    def unexpected(paths, **kwargs):
        result = scan_paths(paths, **kwargs)
        before = paths[0].name == "candidate"
        if problem == "before_findings" and before:
            return replace(result, findings=[])
        if problem == "after_skipped" and not before:
            return replace(result, skipped_files={"unreadable.dcm": "Cannot read DICOM metadata."})
        if (problem == "before_inventory" and before) or (problem == "after_inventory" and not before):
            return replace(result, records=[])
        return result

    monkeypatch.setattr("dicomqc.demo.scan_paths", unexpected)
    output = tmp_path / "policy-demo"
    assert main(["demo", "--policy-demo", "--output-dir", str(output)]) == 2
    captured = capsys.readouterr()
    assert "unexpected results" in captured.err
    assert "expected: 0" not in captured.out
    assert (output / "after.json").exists()
