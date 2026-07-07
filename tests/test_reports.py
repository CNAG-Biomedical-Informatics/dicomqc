from pathlib import Path

from dicomqc.model.metadata import DicomTag, MetadataRecord, ValueState
from dicomqc.model.results import ScanResult
from dicomqc.reports.csv import write_csv
from dicomqc.reports.json import result_to_dict, write_json
from dicomqc.rules.builtin import evaluate_record


def test_json_report_redacts_raw_values(tmp_path):
    record = MetadataRecord(
        path=Path("image.dcm"),
        patient_id="JaneSmith",
        study_uid="1.2.3",
        series_uid="1.2.3.4",
        manufacturer="ACME",
        modality="MR",
        tags={
            "(0010,0010)": DicomTag(
                tag="(0010,0010)",
                keyword="PatientName",
                vr="PN",
                is_private=False,
                value_state=ValueState.PRESENT,
                raw_value="Smith^Jane",
            )
        },
    )
    result = ScanResult("research-release-v0.1", [record], evaluate_record(record))
    path = tmp_path / "report.json"

    write_json(result, path)
    payload = path.read_text(encoding="utf-8")

    assert "Smith^Jane" not in payload
    assert "JaneSmith" not in payload
    assert result_to_dict(result)["records"][0]["patient_id_present"] is True


def test_csv_report_redacts_raw_values(tmp_path):
    record = MetadataRecord(
        path=Path("image.dcm"),
        patient_id=None,
        study_uid=None,
        series_uid=None,
        manufacturer=None,
        modality=None,
        tags={
            "(0010,0030)": DicomTag(
                tag="(0010,0030)",
                keyword="PatientBirthDate",
                vr="DA",
                is_private=False,
                value_state=ValueState.PRESENT,
                raw_value="19700101",
            )
        },
    )
    result = ScanResult("research-release-v0.1", [record], evaluate_record(record))
    path = tmp_path / "findings.csv"

    write_csv(result, path)

    assert "19700101" not in path.read_text(encoding="utf-8")
