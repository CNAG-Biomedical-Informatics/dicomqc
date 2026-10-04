from dataclasses import replace
from html.parser import HTMLParser
from pathlib import Path
import base64
import hashlib

import pytest

from dicomqc.demo import run_comparison_demo, run_demo, run_policy_demo, run_uid_demo, run_vendor_demo
from dicomqc.compare import ComparisonResult, COMPARE_PROFILE
from dicomqc.model.metadata import MetadataRecord
from dicomqc.model.results import Finding, ScanResult, Severity
from dicomqc.reports.html import render_html, write_html


class ParsedReport(HTMLParser):
    def __init__(self, document):
        super().__init__()
        self.tags = []
        self.feed(document)

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


def sample(level=Severity.ERROR):
    record = MetadataRecord(Path("image.dcm"), "SECRET_ID", "SECRET_UID", None, "SECRET_VENDOR", "MR", {})
    finding = Finding("rule", "profile", level, "image.dcm", "A field needs review.", "Remove the value.", tag="(0010,0030)", keyword="PatientBirthDate", standard_refs=("Reference",))
    return ScanResult("profile", [record], [finding])


@pytest.mark.parametrize("runner,title,checks", [
    (run_demo, "Privacy audit", "Privacy metadata"),
    (run_comparison_demo, "Dataset comparison", "Privacy metadata · Dataset comparison"),
    (run_policy_demo, "Privacy audit", "Privacy metadata · Project policy"),
    (run_uid_demo, "Privacy audit", "Privacy metadata · UID integrity"),
    (run_vendor_demo, "Privacy audit", "Privacy metadata · Scanner inventory"),
])
def test_report_names_match_audit_scenarios(tmp_path, runner, title, checks):
    output = tmp_path / "example"
    runner(output, multiqc=False)
    reports = list(output.rglob("*.html"))
    assert reports
    for report in reports:
        document = report.read_text(encoding="utf-8")
        assert f"<title>dicomqc — {title}</title>" in document
        assert f'<p class="eyebrow">{title}</p>' in document
        assert f"Checks: {checks}</p>" in document
        assert "Audit workspace" not in document


@pytest.mark.parametrize("level,label", [(Severity.ERROR, "Errors require attention"), (Severity.WARNING, "Warnings require review"), (Severity.INFO, "Checks passed")])
def test_html_status_content_and_redaction(tmp_path, level, label):
    path = tmp_path / "report.html"
    write_html(sample(level), path)
    text = path.read_text(encoding="utf-8")
    assert label in text
    assert "Remove the value." in text
    assert "PatientBirthDate" in text
    assert "References: Reference" in text
    assert "SECRET_" not in text
    assert 'data-severity="' + level.value + '"' in text
    assert "Synthetic demo" not in text
    assert '<details class="occurrences"><summary>View affected files / pairs' in text
    assert 'class="print-copy"' in text
    assert 'aria-label="Comparison demo"' not in text


def test_html_escapes_untrusted_text_and_has_no_external_resources():
    attack = '</script><img src="https://bad.invalid/x" onerror="alert(1)">'
    item = replace(sample().findings[0], path=attack, message=attack, recommendation=attack,
                   rule_id=attack, keyword=attack, tag=attack, standard_refs=(attack,))
    document = render_html(ScanResult(attack, findings=[item], skipped_files={attack: "SECRET_REASON"}))
    parsed = ParsedReport(document)
    assert not any(tag in {"img", "iframe", "link", "form"} for tag, _ in parsed.tags)
    assert sum(tag == "script" for tag, _ in parsed.tags) == 1
    assert not any("src" in attrs or any(name.startswith("on") for name in attrs) for _, attrs in parsed.tags)
    assert "&lt;/script&gt;" in document
    assert "SECRET_REASON" not in document
    script = document.split("<script>")[1].split("</script>")[0]
    digest = base64.b64encode(hashlib.sha256(script.encode()).digest()).decode()
    assert f"script-src 'sha256-{digest}'" in document
    assert "default-src 'none'" in document


def test_html_empty_and_unreadable_are_not_clean_passes():
    empty = render_html(ScanResult("profile"))
    assert "No readable files" in empty and "No findings were recorded" in empty
    skipped = render_html(ScanResult("profile", skipped_files={"bad.dcm": "SECRET"}))
    assert "Errors require attention" in skipped and "Could not read DICOM metadata" in skipped
    assert "SECRET" not in skipped


def test_html_comparison_coverage_and_demo_reports(tmp_path):
    scan = run_demo(tmp_path / "scan")
    assert "Synthetic demo" in (scan.report_dir / "report.html").read_text(encoding="utf-8")
    comparison = run_comparison_demo(tmp_path / "compare")
    for phase, status in (("before", "Errors require attention"), ("after", "Checks passed")):
        document = (comparison.output_dir / f"{phase}.html").read_text(encoding="utf-8")
        assert status in document
        assert "Pairing coverage" in document and "Identity pairs checked" in document
        assert "Synthetic demo" in document
        assert f'href="{phase}.html" aria-current="page"' in document
        assert 'href="before.html"' in document and 'href="after.html"' in document
        assert "LOCAL001" not in document and "19700101" not in document
    assert "pair-000001/candidate" in render_html(comparison.before)


def test_category_charts_count_findings_and_omit_empty_charts():
    rules = ["direct_phi.PatientName", "direct_phi.PatientID", "private_tags.present",
             "pseudonym_format.PatientID", "inconsistent_pseudonym", "unpaired_source", "custom"]
    findings = [replace(sample().findings[0], rule_id="profile." + rule) for rule in rules]
    document = render_html(ScanResult("profile", findings=findings))
    assert '<span>Identifying fields</span><strong>2</strong>' in document
    assert '<span>Patient identifiers</span><strong>2</strong>' in document
    assert '<span>Private tags</span><strong>1</strong>' in document
    assert '<span>File coverage</span><strong>1</strong>' in document
    assert '<span>Other checks</span><strong>1</strong>' in document
    assert "Findings by category" not in render_html(ScanResult("profile"))


def test_pair_chart_counts_pairs_once_and_prioritizes_missing():
    findings = [replace(sample().findings[0], profile_id=COMPARE_PROFILE,
                        rule_id=f"{COMPARE_PROFILE}.{rule}", path=path)
                for rule, path in [("missing_source", "pair-000001/source"),
                                   ("unreadable_candidate", "pair-000001/candidate"),
                                   ("unreadable_source", "pair-000002/source"),
                                   ("unreadable_candidate", "pair-000002/candidate"),
                                   ("unpaired_candidate", "unpaired-candidate-000001")]]
    counts = dict(source_files=3, candidate_files=4, manifest_pairs=3,
                  readable_pairs=1, identity_pairs_checked=1)
    result = ComparisonResult(COMPARE_PROFILE, findings=findings, comparison=counts)
    document = render_html(result)
    for label in ("Both files readable", "Missing a file", "Unreadable file (neither missing)"):
        assert f'<span>{label}</span><strong>1</strong>' in document
    assert 'width="333.33"' in document
    counts["manifest_pairs"] = 0
    assert "Manifest pair coverage" not in render_html(result)


@pytest.mark.parametrize("synthetic,phase", [(False, "before"), (True, "before"), (True, "../report.html")])
def test_demo_navigation_rejects_invalid_context(synthetic, phase):
    with pytest.raises(ValueError, match="Demo navigation"):
        render_html(sample(), synthetic=synthetic, demo_phase=phase)


def test_review_order_is_severity_first_without_mutating_results():
    findings = [replace(sample(level).findings[0], message=message)
                for level, message in [(Severity.INFO, "info_marker"),
                                       (Severity.WARNING, "warning_marker"),
                                       (Severity.ERROR, "error_marker")]]
    result = ScanResult("profile", findings=findings)
    document = render_html(result)
    assert document.index("error_marker") < document.index("warning_marker") < document.index("info_marker")
    assert result.findings == findings


def test_state_specific_guidance_and_empty_design():
    record = sample().records[0]
    passed = render_html(ScanResult("profile", records=[record]))
    assert "complete the remaining data-sharing review" in passed
    assert 'class="empty-mark pass"' in passed
    empty = render_html(ScanResult("profile"))
    assert "Check the input location" in empty
    assert "This does not indicate a clean audit" in empty
    unreadable = render_html(ScanResult("profile", skipped_files={"bad.dcm": "SECRET"}))
    assert "Coverage is incomplete" in unreadable
    assert 'href="#unreadable-title"' in unreadable
    assert 'class="empty-mark pass"' not in unreadable
    assert "Review each warning" in render_html(sample(Severity.WARNING))
    assert "correct the files or pairing" in render_html(sample())


def test_grouping_preserves_occurrences_fields_and_distinct_references():
    item = sample().findings[0]
    findings = [item, replace(item, tag="(0010,0010)", keyword="PatientName"),
                replace(item, path="second.dcm")]
    document = render_html(ScanResult("profile", findings=findings))
    parsed = ParsedReport(document)
    assert sum(tag == "article" for tag, _ in parsed.tags) == 1
    assert '3 findings · 2 distinct references' in document
    assert document.count("PatientName") == 2  # screen and complete print copy
    assert document.count("PatientBirthDate") == 4
    assert document.count("Remove the value.") == 1
    assert 'second.dcm' in document


def test_grouping_does_not_hide_different_messages_actions_or_severities():
    item = sample().findings[0]
    findings = [item, replace(item, message="Another issue"),
                replace(item, recommendation="A different action"),
                replace(item, severity=Severity.WARNING),
                replace(item, standard_refs=("Different reference",))]
    document = render_html(ScanResult("profile", findings=findings))
    assert sum(tag == "article" for tag, _ in ParsedReport(document).tags) == 5


def test_large_report_is_one_issue_with_all_occurrences():
    item = sample().findings[0]
    result = ScanResult("profile", findings=[replace(item, path=f"file-{i:04d}.dcm") for i in range(250)])
    document = render_html(result)
    assert sum(tag == "article" for tag, _ in ParsedReport(document).tags) == 1
    assert "250 findings · 250 distinct references" in document
    assert "file-0249.dcm" in document
