from __future__ import annotations

import csv
import json
import os
import logging
import warnings
from pathlib import Path

import pytest
from pydicom import dcmread

from dicomqc.backend.base import DicomReadError
from dicomqc.cli import main
from dicomqc.compare import compare_datasets
from dicomqc.fixtures import _write_dicom
from dicomqc.reports.json import result_to_dict


def dataset(tmp_path, identities=(("LOCAL_SECRET", "sub-001"),)):
    source, candidate = tmp_path / "source", tmp_path / "candidate"
    source.mkdir()
    candidate.mkdir()
    pairs = []
    for index, (before, after) in enumerate(identities, 1):
        names = (f"source-secret-{index}.dcm", f"renamed-{index}.dcm")
        for root, name, patient in zip((source, candidate), names, (before, after)):
            _write_dicom(root / name, fixture_index=index, patient_id=patient,
                         patient_name="sub-001", patient_birth_date=None, private_creator=None)
        pairs.append(names)
    manifest = tmp_path / "pairs.csv"
    write_manifest(manifest, pairs)
    return source, candidate, manifest


def write_manifest(path, pairs):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["source", "candidate"])
        writer.writerows(pairs)


def rules(result):
    return {finding.rule_id.rsplit(".", 1)[-1] for finding in result.findings}


def test_clean_renamed_files_and_reports(tmp_path, capsys):
    source, candidate, manifest = dataset(tmp_path, (("SECRET", "sub-001"), ("SECRET", "sub-001")))
    original = {p: p.read_bytes() for root in (source, candidate) for p in root.iterdir()}
    report, findings = tmp_path / "report.json", tmp_path / "findings.csv"
    assert main(["compare", str(source), str(candidate), "--manifest", str(manifest),
                 "--json", str(report), "--csv", str(findings)]) == 0
    payload = json.loads(report.read_text())
    assert payload["comparison"] == {"source_files": 2, "candidate_files": 2,
                                      "manifest_pairs": 2, "readable_pairs": 2, "identity_pairs_checked": 2}
    assert payload["records"] == [{"path": "pair-000001/candidate"}, {"path": "pair-000002/candidate"}]
    assert "Identity pairs checked: 2" in capsys.readouterr().out
    assert all(p.read_bytes() == content for p, content in original.items())
    assert "SECRET" not in report.read_text()


@pytest.mark.parametrize("identities,expected", [
    ((("A", "sub-001"), ("A", "sub-002")), "inconsistent_pseudonym"),
    ((("A", "sub-001"), ("B", "sub-001")), "pseudonym_collision"),
    ((("sub-001", "sub-001"),), "unchanged_patient_id"),
    ((("", "sub-001"),), "missing_patient_id"),
    ((("A", ""),), "missing_patient_id"),
])
def test_identity_errors(tmp_path, identities, expected):
    result = compare_datasets(*dataset(tmp_path, identities))
    assert expected in rules(result)
    assert result.exit_code() == 2
    assert result.files_failed == len(identities)


def test_issuer_scopes_source_ids(tmp_path):
    args = dataset(tmp_path, (("A", "sub-001"), ("A", "sub-002")))
    for index, path in enumerate(sorted(args[0].iterdir())):
        ds = dcmread(path)
        ds.IssuerOfPatientID = f"SITE{index}"
        ds.save_as(path, enforce_file_format=True)
    assert compare_datasets(*args).exit_code() == 0


def test_nested_issuer_cannot_change_patient_grouping(tmp_path):
    from pydicom.dataset import Dataset
    args = dataset(tmp_path, (("A", "sub-001"), ("A", "sub-002")))
    for index, path in enumerate(sorted(args[0].iterdir())):
        ds = dcmread(path)
        ds.IssuerOfPatientID = "SAME_SITE"
        item = Dataset()
        item.IssuerOfPatientID = f"DIFFERENT_SITE_{index}"
        ds.RequestAttributesSequence = [item]
        ds.save_as(path, enforce_file_format=True)
    assert "inconsistent_pseudonym" in rules(compare_datasets(*args))


def test_inventory_cannot_silently_skip_inaccessible_directory(tmp_path, monkeypatch):
    args = dataset(tmp_path)
    def denied_walk(root, *, onerror, followlinks):
        onerror(PermissionError("SECRET_PATH"))
        return iter(())
    monkeypatch.setattr("dicomqc.compare.os.walk", denied_walk)
    with pytest.raises(ValueError, match="inventory every input directory") as error:
        compare_datasets(*args)
    assert "SECRET_PATH" not in str(error.value)


def test_inventory_rejects_special_files(tmp_path):
    args = dataset(tmp_path)
    os.mkfifo(args[0] / "fifo")
    with pytest.raises(ValueError, match="regular files"):
        compare_datasets(*args)


@pytest.mark.parametrize("side", [0, 1])
def test_missing_file(tmp_path, side):
    args = dataset(tmp_path)
    next(args[side].iterdir()).unlink()
    result = compare_datasets(*args)
    assert f"missing_{('source', 'candidate')[side]}" in rules(result)
    assert result.comparison["readable_pairs"] == 0
    assert result.exit_code() == 2
    assert result.files_failed <= result.files_scanned


def test_unpaired_and_unreadable_files(tmp_path):
    args = dataset(tmp_path)
    for root in args[:2]:
        (root / "extra-secret").write_text("bad")
        next(root.glob("*.dcm")).write_text("bad")
    result = compare_datasets(*args)
    assert rules(result) == {"unpaired_source", "unpaired_candidate", "unreadable_source", "unreadable_candidate"}
    assert len(result.skipped_files) == 2
    assert result.files_scanned == result.files_failed == 0
    assert result.exit_code() == 2


def test_candidate_rules_and_no_sensitive_report_context(tmp_path):
    args = dataset(tmp_path)
    path = next(args[1].iterdir())
    ds = dcmread(path)
    ds.PatientBirthDate = "19700101"
    ds.Manufacturer = "SECRET_VENDOR"
    ds.add_new((0x0029, 0x0010), "LO", "PRIVATE_SECRET")
    ds.save_as(path, enforce_file_format=True)
    result = compare_datasets(*args)
    assert result.error_count == 1 and result.warning_count == 1
    report, findings = tmp_path / "out.json", tmp_path / "out.csv"
    assert main(["compare", str(args[0]), str(args[1]), "--manifest", str(args[2]),
                 "--json", str(report), "--csv", str(findings), "--quiet"]) == 2
    content = report.read_text() + findings.read_text()
    for secret in ("19700101", "SECRET_VENDOR", "PRIVATE_SECRET", "LOCAL_SECRET", "source-secret", "renamed-1", ds.StudyInstanceUID):
        assert secret not in content


def test_warning_exit(tmp_path):
    args = dataset(tmp_path, (("A", "bad-format"),))
    assert compare_datasets(*args).exit_code() == 1


def test_parser_exception_is_redacted(tmp_path):
    args = dataset(tmp_path)
    class Broken:
        def read_metadata(self, path):
            raise DicomReadError("SECRET_IN_EXCEPTION")
    result = compare_datasets(*args, backend=Broken())
    assert "SECRET_IN_EXCEPTION" not in json.dumps(result_to_dict(result))


def test_parser_warnings_fail_closed_without_leaking(tmp_path, caplog):
    from dicomqc.backend.pydicom_backend import PydicomBackend
    args = dataset(tmp_path)
    class WarningReader:
        def read_metadata(self, path):
            logging.getLogger("pydicom").warning("SECRET_IN_LOG")
            warnings.warn("SECRET_IN_WARNING")
            return PydicomBackend().read_metadata(path)
    logger = logging.getLogger("pydicom")
    previous_filters = list(logger.filters)
    with warnings.catch_warnings(record=True) as emitted:
        result = compare_datasets(*args, backend=WarningReader())
    assert result.exit_code() == 2
    assert len(result.skipped_files) == 2
    assert not emitted
    assert "SECRET_IN_LOG" not in caplog.text
    assert "SECRET_IN_WARNING" not in json.dumps(result_to_dict(result))
    assert logger.filters == previous_filters


@pytest.mark.parametrize("content,match", [
    ("bad,header\na,b\n", "header"),
    ("source,candidate\n", "at least one"),
    ("source,candidate\na,\n", "two paths"),
    ("source,candidate\na\n", "two paths"),
    ("source,candidate\na,b,c\n", "two paths"),
    ("source,candidate\n../secret,b\n", "relative"),
    ("source,candidate\n/a,b\n", "relative"),
    ("source,candidate\n.,b\n", "relative"),
    ("source,candidate\na,b\na,c\n", "one-to-one"),
    ("source,candidate\na,b\nc,b\n", "one-to-one"),
    ('source,candidate\n"unterminated', "UTF-8"),
])
def test_invalid_manifest(tmp_path, content, match):
    args = dataset(tmp_path)
    args[2].write_text(content)
    with pytest.raises(ValueError, match=match):
        compare_datasets(*args)


def test_missing_manifest(tmp_path):
    args = dataset(tmp_path)
    args[2].unlink()
    with pytest.raises(ValueError, match="UTF-8"):
        compare_datasets(*args)


def test_invalid_roots_and_symlinks(tmp_path):
    source, candidate, manifest = dataset(tmp_path)
    for roots in ((source, source), (tmp_path, candidate), (source / "absent", candidate)):
        with pytest.raises(ValueError):
            compare_datasets(*roots, manifest)
    with pytest.raises(ValueError, match="outside"):
        compare_datasets(source, candidate, source / "pairs.csv")
    (source / "link").symlink_to(candidate, target_is_directory=True)
    with pytest.raises(ValueError, match="symbolic"):
        compare_datasets(source, candidate, manifest)


@pytest.mark.parametrize("target", ["input", "manifest", "same", "missing_parent"])
def test_cli_output_protection(tmp_path, capsys, target):
    source, candidate, manifest = dataset(tmp_path)
    output = {"input": next(source.iterdir()), "manifest": manifest,
              "same": tmp_path / "report", "missing_parent": tmp_path / "absent" / "report"}[target]
    original = output.read_bytes() if output.exists() else None
    argv = ["compare", str(source), str(candidate), "--manifest", str(manifest), "--json", str(output)]
    if target == "same":
        argv += ["--csv", str(output)]
    assert main(argv) == 2
    assert "dicomqc:" in capsys.readouterr().err
    if original is not None:
        assert output.read_bytes() == original


def test_hardlinked_report_cannot_overwrite_input(tmp_path):
    source, candidate, manifest = dataset(tmp_path)
    original = next(source.iterdir())
    content = original.read_bytes()
    output = tmp_path / "report.json"
    os.link(original, output)
    assert main(["compare", str(source), str(candidate), "--manifest", str(manifest),
                 "--json", str(output)]) == 2
    assert original.read_bytes() == content


def test_compare_html_cli_and_output_protection(tmp_path):
    source, candidate, manifest = dataset(tmp_path)
    report = tmp_path / "report.html"
    args = ["compare", str(source), str(candidate), "--manifest", str(manifest)]
    assert main(args + ["--html", str(report)]) == 0
    assert "Pairing coverage" in report.read_text() and "Checks passed" in report.read_text()
    assert main(args + ["--html", str(manifest)]) == 2
    assert main(args + ["--html", str(next(candidate.iterdir()))]) == 2
    assert main(args + ["--html", str(report), "--csv", str(report)]) == 2
