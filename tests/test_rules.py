from pathlib import Path

from dicomqc.model.metadata import DicomTag, MetadataRecord, ValueState
from dicomqc.model.metadata import value_state
from dicomqc.rules.builtin import evaluate_record


def _record(*tags: DicomTag) -> MetadataRecord:
    return MetadataRecord(
        path=Path("study/image.dcm"),
        patient_id=None,
        study_uid="1.2.3",
        series_uid="1.2.3.4",
        manufacturer="SIEMENS",
        modality="MR",
        tags={tag.tag: tag for tag in tags},
    )


def _tag(keyword, value, tag="(0010,0010)", private=False):
    return DicomTag(
        tag=tag,
        keyword=keyword,
        vr="LO",
        is_private=private,
        value_state=ValueState.PRESENT if value else ValueState.EMPTY,
        raw_value=value,
    )


def test_direct_phi_tag_is_error():
    findings = evaluate_record(_record(_tag("PatientBirthDate", "19700101", "(0010,0030)")))

    assert len(findings) == 1
    assert findings[0].severity == "error"
    assert findings[0].keyword == "PatientBirthDate"
    assert findings[0].value_state == ValueState.PRESENT


def test_patient_id_research_pseudonym_passes():
    findings = evaluate_record(_record(_tag("PatientID", "SUBJ001", "(0010,0020)")))

    assert findings == []


def test_patient_name_human_like_value_warns():
    findings = evaluate_record(_record(_tag("PatientName", "Smith^Jane")))

    assert len(findings) == 1
    assert findings[0].severity == "warning"
    assert findings[0].keyword == "PatientName"


def test_private_tags_are_summarized_per_record():
    findings = evaluate_record(
        _record(
            _tag("PrivateCreator", "SIEMENS CSA HEADER", "(0029,0010)", private=True),
            _tag("PrivateData", "secret", "(0029,1010)", private=True),
        )
    )

    assert len(findings) == 1
    assert findings[0].rule_id.endswith(".private_tags.present")
    assert "2 private DICOM tag" in findings[0].message


def test_value_state_handles_absent_bytes_and_empty_sequences():
    assert value_state(None) == ValueState.ABSENT
    assert value_state(b"") == ValueState.EMPTY
    assert value_state([]) == ValueState.EMPTY
    assert value_state(123) == ValueState.PRESENT
