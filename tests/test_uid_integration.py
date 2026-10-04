"""UID checks in real DICOM scans, reports, demos, and CLI workflows."""

import hashlib
import json
from pathlib import Path
import warnings

import pytest
from pydicom import dcmread

from dicomqc.cli import main
from dicomqc.demo import DemoValidationError, run_uid_demo
from dicomqc.fixtures import ROOT_UID, write_uid_fixtures, POLICY_DEMO_YAML
from dicomqc.reports.json import result_to_dict
from dicomqc.scanner import scan_paths


def test_demo_redacted_all_formats_and_read_only(tmp_path, capsys, caplog):
    demo = run_uid_demo(tmp_path / "uid")
    assert demo.before.error_count == 7
    assert demo.before.exit_code() == 2
    assert demo.after.exit_code() == 0
    assert len({f.rule_id for f in demo.before.findings}) == 4
    assert demo.before.uid_checks["complete_hierarchies_checked"] == 3
    assert demo.after.uid_checks["complete_hierarchies_checked"] == 4
    inputs = list(demo.output_dir.glob("candidate/*.dcm"))
    hashes = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
    caplog.clear()  # Ignore diagnostics from deliberately malformed synthetic fixture generation.
    result = scan_paths(inputs, uid_checks=True)
    assert hashes == {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
    assert result.error_count == 7
    for path in demo.output_dir.rglob("*"):
        if path.is_file() and path.suffix in {".json", ".csv", ".html", ".yaml"}:
            assert ROOT_UID not in path.read_text(encoding="utf-8")
    before_json = json.loads((demo.output_dir / "before.json").read_text(encoding="utf-8"))
    assert "study_uid" not in before_json["records"][0]
    assert before_json["uid_checks"]["fields"]["SOPInstanceUID"]["invalid"] == 1
    assert 'data-category="UID integrity"' in (demo.output_dir / "before.html").read_text(encoding="utf-8")
    for path in (demo.output_dir / "after.html", demo.output_dir / "after_mqc/dicomqc_00_overview_mqc.html"):
        assert "4 of 4 files" in path.read_text(encoding="utf-8")
        assert "UID integrity" in path.read_text(encoding="utf-8")
    assert not capsys.readouterr().err
    assert ROOT_UID not in caplog.text


def test_cli_demo_and_scan_options_are_opt_in_and_composable(tmp_path, capsys):
    root = tmp_path / "uid"
    assert main(["demo", "--uid-demo", "--output-dir", str(root)]) == 0
    assert "seven findings" in capsys.readouterr().out
    assert main(["demo", "--uid-demo", "--output-dir", str(root)]) == 2
    assert main(["demo", "--uid-demo", "--output-dir", str(root), "--force"]) == 0
    policy = root / "policy.yaml"
    policy.write_text(POLICY_DEMO_YAML)
    report = root / "scan.json"
    assert main(["scan", str(root / "corrected"), "--uid-checks", "--policy", str(policy),
                 "--vendor-summary", "--json", str(report), "--html", str(root / "scan.html"),
                 "--csv", str(root / "scan.csv"), "--multiqc", str(root / "scan_mqc")]) == 2
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["uid_checks"]["complete_hierarchies_checked"] == 4
    assert payload["policy"]["id"] == "research-demo"
    assert payload["vendor_summary"]["files"] == 4
    assert "Usable UID hierarchies: 4 of 4" in capsys.readouterr().out
    assert main(["scan", str(root / "candidate"), "--uid-checks", "--quiet"]) == 2
    assert main(["scan", str(root / "corrected"), "--uid-checks", "--quiet"]) == 0
    assert capsys.readouterr().out == ""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        baseline = scan_paths([root / "candidate"])
    assert baseline.exit_code() == 0
    assert "uid_checks" not in result_to_dict(baseline)
    assert "study_uid" in result_to_dict(baseline)["records"][0]


def test_real_long_multivalued_and_missing_uids(tmp_path):
    write_uid_fixtures(tmp_path)
    path = tmp_path / "corrected/image-001.dcm"
    for value in ["1." + "2" * 63, ["1.2", "1.3"]]:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            data = dcmread(path)
            data.SeriesInstanceUID = value
            data.save_as(path, enforce_file_format=True)
        with warnings.catch_warnings(record=True) as diagnostics:
            result = scan_paths([path], uid_checks=True)
        assert result.error_count == 1
        assert not result.skipped_files
        assert not diagnostics
    data = dcmread(tmp_path / "corrected/image-002.dcm")
    del data.StudyInstanceUID
    data.SeriesInstanceUID = ""
    data.save_as(path, enforce_file_format=True)
    result = scan_paths([path], uid_checks=True)
    assert not result.findings
    assert result.uid_checks["complete_hierarchies_checked"] == 0
    assert result.uid_checks["fields"]["StudyInstanceUID"]["absent_or_empty"] == 1


def test_unreadable_and_empty_inputs_keep_coverage_explicit(tmp_path):
    missing = tmp_path / "missing"
    result = scan_paths([missing], uid_checks=True)
    assert result.exit_code() == 2
    assert result.uid_checks["files_checked"] == 0
    assert list(result.skipped_files.values()) == ["Cannot read DICOM metadata."]
    assert scan_paths([tmp_path], uid_checks=True).uid_checks["files_checked"] == 0


def test_demo_validation_catches_unexpected_results(tmp_path, monkeypatch):
    from dicomqc.model.results import ScanResult
    monkeypatch.setattr("dicomqc.demo.scan_paths", lambda *args, **kwargs: ScanResult("test", uid_checks={
        "profile_id": "test", "complete_hierarchies_checked": 0, "files_checked": 0, "fields": {},
    }))
    with pytest.raises(DemoValidationError, match="UID demo produced unexpected"):
        run_uid_demo(tmp_path / "uid")


def test_demo_modes_remain_mutually_exclusive():
    with pytest.raises(SystemExit) as exc:
        main(["demo", "--uid-demo", "--policy-demo"])
    assert exc.value.code == 2
