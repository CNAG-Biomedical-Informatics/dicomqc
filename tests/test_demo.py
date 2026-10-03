from __future__ import annotations

import json
import pytest

from dicomqc.demo import run_comparison_demo, run_demo, run_large_demo
from dicomqc.compare import compare_datasets
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


def test_large_demo_is_generated_on_demand_with_findings(tmp_path):
    events = []
    result = run_large_demo(tmp_path / "large", count=25, multiqc=False, threads=1,
                            progress=events.append)

    assert result.scan_exit_code == 2
    assert len(list(result.dicom_dir.glob("*.dcm"))) == 25
    assert result.json_path.is_file()
    report = json.loads(result.json_path.read_text())
    assert report["summary"]["errors"] == 25
    assert report["summary"]["warnings"] == 50
    assert len(report["findings"]) == 75
    assert events[0] == {"phase": "generation", "completed": 0, "total": 25}
    assert {event["completed"] for event in events if event["phase"] == "generation"} == set(range(26))
    assert all(event["total"] == 25 for event in events if event["phase"] == "reading")
    assert events[-1]["phase"] == "reports"
    assert not result.multiqc_dir.exists()


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


def test_comparison_demo_can_be_rerun_and_reports_explain_failures(tmp_path):
    output = tmp_path / "comparison"
    demo = run_comparison_demo(output)
    assert demo.before.exit_code() == 2
    assert demo.after.exit_code() == 0
    assert demo.before.error_count == 3
    assert {f.rule_id.rsplit(".", 1)[-1] for f in demo.before.findings} == {
        "missing_candidate", "inconsistent_pseudonym",
    }
    # Each existing candidate passes the individual checks: the problems require comparison.
    assert scan_paths([output / "candidate"]).exit_code() == 0
    original = {p: p.read_bytes() for p in output.rglob("*.dcm")}
    assert compare_datasets(output / "source", output / "candidate", demo.manifest) == demo.before
    assert compare_datasets(output / "source", output / "corrected", demo.manifest) == demo.after
    assert all(p.read_bytes() == content for p, content in original.items())
    for name, expected, readable in (("before", 3, 2), ("after", 0, 3)):
        payload = json.loads((output / f"{name}.json").read_text())
        assert payload["summary"]["errors"] == expected
        assert payload["comparison"]["manifest_pairs"] == 3
        assert payload["comparison"]["readable_pairs"] == readable
        content = (output / f"{name}.json").read_text() + (output / f"{name}.csv").read_text()
        for secret in ("LOCAL001", "LOCAL002", "Example^Patient", "19700101", "patient-a"):
            assert secret not in content


def test_comparison_demo_requires_force_to_replace(tmp_path):
    output = tmp_path / "comparison"
    run_comparison_demo(output)
    marker = output / "old-marker"
    marker.write_text("keep")
    with pytest.raises(FileExistsError):
        run_comparison_demo(output)
    assert marker.read_text() == "keep"
    assert run_comparison_demo(output, force=True).after.exit_code() == 0
    assert not marker.exists()


def test_demo_rejects_unsafe_destination(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError, match="separate demo directory"):
        run_comparison_demo(tmp_path, force=True)
    link = tmp_path / "link"
    link.symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(ValueError, match="separate demo directory"):
        run_demo(link, force=True)


def test_force_preserves_unrecognized_directory(tmp_path):
    output = tmp_path / "real-data"
    output.mkdir()
    original = output / "keep.dcm"
    original.write_bytes(b"must survive")
    with pytest.raises(ValueError, match="only replaces directories created"):
        run_comparison_demo(output, force=True)
    assert original.read_bytes() == b"must survive"


@pytest.mark.parametrize("which", ["before", "after"])
def test_comparison_demo_rejects_unexpected_audit(tmp_path, monkeypatch, which):
    from dataclasses import replace
    from dicomqc.demo import DemoValidationError
    def unexpected(source, candidate, manifest, **kwargs):
        result = compare_datasets(source, candidate, manifest, **kwargs)
        if which == "before" and candidate.name == "candidate":
            return replace(result, findings=[])
        if which == "after" and candidate.name == "corrected":
            return replace(result, comparison={**result.comparison, "identity_pairs_checked": 0})
        return result
    monkeypatch.setattr("dicomqc.demo.compare_datasets", unexpected)
    with pytest.raises(DemoValidationError, match="unexpected results"):
        run_comparison_demo(tmp_path / "demo")
    assert (tmp_path / "demo" / "after.json").exists()


def test_scan_demo_rejects_unexpected_audit(tmp_path, monkeypatch):
    from dataclasses import replace
    from dicomqc.demo import DemoValidationError
    def unexpected(*args, **kwargs):
        return replace(scan_paths(*args, **kwargs), findings=[])
    monkeypatch.setattr("dicomqc.demo.scan_paths", unexpected)
    with pytest.raises(DemoValidationError):
        run_demo(tmp_path / "demo")
