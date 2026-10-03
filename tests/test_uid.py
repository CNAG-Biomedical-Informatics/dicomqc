"""UID syntax, scope, associations, coverage, and diagnostic privacy."""

from dataclasses import replace
import logging
from pathlib import Path
import warnings

import pytest

from dicomqc.backend.base import DicomReadError
from dicomqc.backend.diagnostics import _HideParserDetails, read_metadata_safely
from dicomqc.model.metadata import DicomTag, MetadataRecord, value_state
from dicomqc.rules.uid import UID_FIELDS, UID_PROFILE, evaluate_uids


def record(study="1.2.1", series="1.2.2", sop="1.2.3", path="image.dcm"):
    tags = {number: DicomTag(number, key, "UI", False, value_state(value), value)
            for (key, number), value in zip(UID_FIELDS.items(), (study, series, sop))}
    return MetadataRecord(Path(path), None, study, series, None, None, tags)


@pytest.mark.parametrize("value", ["1.02.3", "01.2", "1..2", ".1", "1.", "1.a", "١.2", "1.2\n",
                                  "1. 2", "1\\2", "1." + "2" * 63, ["1.2", "1.3"], b"1.2", 123])
def test_invalid_format_is_redacted(value):
    findings, summary = evaluate_uids([record(sop=value)])
    assert len(findings) == 1
    assert findings[0].rule_id == UID_PROFILE + ".invalid_format"
    assert findings[0].keyword == "SOPInstanceUID"
    assert findings[0].standard_refs == ("DICOM PS3.5 Section 9",)
    assert summary["fields"]["SOPInstanceUID"] == {"valid": 0, "absent_or_empty": 0, "invalid": 1}
    assert summary["complete_hierarchies_checked"] == 0


@pytest.mark.parametrize("value", ["0", "1.0.2", "2.25.12345", "1." + "2" * 61, "1." + "2" * 62])
def test_normalized_syntax_accepts_zero_components_and_63_64_char_values(value):
    findings, summary = evaluate_uids([record(sop=value)])
    assert not findings
    assert summary["complete_hierarchies_checked"] == 1


def test_wrong_vr_and_empty_or_missing_fields():
    item = record(study=None, series="")
    number = UID_FIELDS["SOPInstanceUID"]
    item.tags[number] = replace(item.tags[number], vr="LO")
    findings, summary = evaluate_uids([item])
    assert len(findings) == 1
    assert summary["fields"]["StudyInstanceUID"]["absent_or_empty"] == 1
    assert summary["fields"]["SeriesInstanceUID"]["absent_or_empty"] == 1
    assert summary["series_study_pairs_checked"] == 0
    findings, summary = evaluate_uids([replace(item, tags={})])
    assert not findings
    assert summary["fields"]["SOPInstanceUID"]["absent_or_empty"] == 1


def test_top_level_numeric_tags_only_not_keyword_or_nested_references():
    item = record()
    nested = replace(item.tags["(0020,000D)"], raw_value="1.2.2", is_nested=True, dataset_path=("item[0]",))
    item.tags["nested"] = nested
    item.tags["nested-with-path-only"] = replace(nested, is_nested=False)
    item.tags["private"] = replace(nested, tag="(0029,1010)", dataset_path=(), is_nested=False)
    item.tags["class"] = DicomTag("(0008,0016)", "SOPClassUID", "UI", False, value_state("1.2.2"), "1.2.2")
    assert evaluate_uids([item])[0] == []


def test_role_reuse_flags_every_affected_field_across_files():
    first, second = record(path="a"), record("1.2.2", "1.2.4", "1.2.5", path="b")
    findings, _ = evaluate_uids([first, second])
    assert [(f.path, f.keyword) for f in findings] == [("a", "SeriesInstanceUID"), ("b", "StudyInstanceUID")]
    assert {f.rule_id for f in findings} == {UID_PROFILE + ".role_reuse"}


def test_series_and_instance_conflicts_flag_all_files_not_just_last():
    a, b = record(path="a"), record(study="1.2.4", path="b")
    findings, summary = evaluate_uids([a, b])
    assert len(findings) == 4
    assert {f.path for f in findings} == {"a", "b"}
    assert {f.rule_id for f in findings} == {UID_PROFILE + ".series_study_conflict", UID_PROFILE + ".instance_context_conflict"}
    assert summary["complete_hierarchies_checked"] == 2
    assert evaluate_uids([b, a])[1] == summary


def test_instance_series_conflict_and_partial_context():
    findings, _ = evaluate_uids([record(study=None, path="a"), record(study=None, series="1.2.4", path="b")])
    assert len(findings) == 2
    assert {f.rule_id for f in findings} == {UID_PROFILE + ".instance_context_conflict"}
    assert not evaluate_uids([record(study=None), record(series=None)])[0]


def test_repeated_instances_shared_study_series_and_invalid_values_do_not_create_false_conflicts():
    assert not evaluate_uids([record(path="a"), record(path="b"), record(sop="1.2.4", path="c")])[0]
    findings, _ = evaluate_uids([record(study="bad", series="bad")])
    assert len(findings) == 2
    assert {f.rule_id for f in findings} == {UID_PROFILE + ".invalid_format"}
    assert evaluate_uids([])[1]["files_checked"] == 0


@pytest.mark.parametrize("message,allowed", [
    ("Invalid value for VR UI: 'SECRET'", True),
    ("The value length (70) exceeds the maximum length of 64 allowed for VR UI.", True),
    ("Invalid value for VR PN: SECRET", False),
    ("Unexpected parser warning SECRET", False),
])
def test_diagnostics_never_disclose_raw_values(message, allowed, caplog):
    class Reader:
        def read_metadata(self, path):
            logging.getLogger("pydicom").warning("SECRET")
            warnings.warn(message)
            return record()
    logger = logging.getLogger("pydicom")
    original_filters = logger.filters[:]
    with warnings.catch_warnings(record=True) as emitted:
        if allowed:
            assert read_metadata_safely(Reader(), Path("file"), allow_uid_warnings=True).path == Path("image.dcm")
        else:
            with pytest.raises(DicomReadError, match="Cannot read DICOM metadata"):
                read_metadata_safely(Reader(), Path("file"), allow_uid_warnings=True)
    assert not emitted
    assert "SECRET" not in caplog.text
    assert logger.filters == original_filters
    with pytest.raises(DicomReadError):
        read_metadata_safely(Reader(), Path("file"))


def test_filter_does_not_hide_another_threads_log():
    filter_ = _HideParserDetails()
    log = logging.LogRecord("pydicom", logging.WARNING, "", 0, "message", (), None)
    log.thread = filter_.thread + 1
    assert filter_.filter(log)


def test_backend_errors_are_sanitized_and_filters_restored():
    class Reader:
        def read_metadata(self, path):
            raise DicomReadError("SECRET")
    filters = logging.getLogger("pydicom").filters[:]
    with pytest.raises(DicomReadError, match="^Cannot read DICOM metadata.$"):
        read_metadata_safely(Reader(), Path("file"), allow_uid_warnings=True)
    assert logging.getLogger("pydicom").filters == filters
