from pathlib import Path

from dicomqc.model.metadata import DicomTag, MetadataRecord, ValueState
from dicomqc.model.results import ScanResult
from dicomqc.reports.multiqc import (
    build_findings_payload,
    build_overview_html,
    build_release_status_payload,
    build_summary_payload,
    write_multiqc,
)
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
    overview = build_overview_html(result)
    findings = build_findings_payload(result)
    status = build_release_status_payload(result)

    assert "dicomqc-dashboard dicomqc-status-review" in overview
    assert summary["parent_id"] == "dicomqc"
    assert summary["plot_type"] == "generalstats"
    assert summary["data"]["dicomqc"]["warnings"] == 2
    assert summary["headers"]["errors"]["scale"] == "Reds"
    assert findings["plot_type"] == "table"
    assert len(findings["data"]) == 2
    assert "finding_001" in findings["data"]
    assert findings["headers"]["severity"]["bgcols"]["error"] == "#dc2626"
    assert findings["headers"]["message"]["title"] == "Finding"
    assert status["data"]["dicomqc"]["Status"] == "review"
    assert status["headers"]["Status"]["bgcols"]["review"] == "#f59e0b"
    assert status["section_name"] == "dicomqc audit status"


def test_multiqc_writer_redacts_raw_values(tmp_path):
    output = write_multiqc(_result(), tmp_path / "mqc")

    assert (output / "dicomqc_00_overview_mqc.html").exists()
    assert (output / "dicomqc_summary_mqc.yaml").exists()
    assert (output / "dicomqc_01_release_status_mqc.yaml").exists()
    findings = (output / "dicomqc_02_findings_mqc.yaml").read_text(encoding="utf-8")
    assert "Smith^Jane" not in findings
    assert "SIEMENS CSA HEADER" not in findings


def test_multiqc_writer_clears_stale_yaml_and_rejects_yaml_path(tmp_path):
    outdir = tmp_path / "mqc"
    outdir.mkdir()
    stale = outdir / "stale_mqc.yaml"
    stale.write_text("stale: true\n", encoding="utf-8")
    stale_html = outdir / "stale_mqc.html"
    stale_html.write_text("<p>stale</p>\n", encoding="utf-8")
    keep = outdir / "keep.txt"
    keep.write_text("keep\n", encoding="utf-8")

    write_multiqc(_result(), outdir)

    assert not stale.exists()
    assert not stale_html.exists()
    assert keep.exists()
    assert (outdir / "dicomqc_summary_mqc.yaml").exists()

    import pytest

    with pytest.raises(ValueError, match="directory"):
        write_multiqc(_result(), tmp_path / "old_mqc.yaml")
