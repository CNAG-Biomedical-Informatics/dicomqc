from pathlib import Path

from dicomqc.model.metadata import DicomTag, MetadataRecord, ValueState
from dicomqc.model.results import ScanResult
from dicomqc.reports.multiqc import build_findings_payload, build_summary_payload, write_multiqc
from dicomqc.rules.builtin import evaluate_record


def _result() -> ScanResult:
    record = MetadataRecord(
        path=Path("image.dcm"),
        patient_id=None,
        study_uid="1.2.3",
        series_uid="1.2.3.4",
        manufacturer="SIEMENS",
        modality="MR",
        tags={
            "(0010,0010)": DicomTag(
                tag="(0010,0010)",
                keyword="PatientName",
                vr="PN",
                is_private=False,
                value_state=ValueState.PRESENT,
                raw_value="Smith^Jane",
            ),
            "(0029,0010)": DicomTag(
                tag="(0029,0010)",
                keyword="PrivateCreator",
                vr="LO",
                is_private=True,
                value_state=ValueState.PRESENT,
                raw_value="SIEMENS CSA HEADER",
            ),
        },
    )
    return ScanResult("research-release-v0.1", [record], evaluate_record(record))


def test_multiqc_payloads_are_custom_content_sections():
    result = _result()

    summary = build_summary_payload(result)
    findings = build_findings_payload(result)

    assert summary["parent_id"] == "dicomqc"
    assert summary["plot_type"] == "generalstats"
    assert summary["data"]["DICOMQC"]["warnings"] == 2
    assert findings["plot_type"] == "table"
    assert len(findings["data"]) == 2


def test_multiqc_writer_redacts_raw_values(tmp_path):
    output = write_multiqc(_result(), tmp_path / "mqc")

    assert (output / "dicomqc_summary_mqc.yaml").exists()
    findings = (output / "dicomqc_findings_mqc.yaml").read_text(encoding="utf-8")
    assert "Smith^Jane" not in findings
    assert "SIEMENS CSA HEADER" not in findings
