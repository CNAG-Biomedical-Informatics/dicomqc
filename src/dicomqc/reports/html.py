"""Standalone, offline HTML reports with no third-party dependencies."""

from __future__ import annotations

import base64
import hashlib
from collections import Counter
from html import escape
from pathlib import Path

from dicomqc import __version__
from dicomqc.model.results import Finding, ScanResult
from dicomqc.reports.status import audit_guidance, audit_status
from dicomqc.reports.vendor import VENDOR_STYLE, render_vendor_inventory
from dicomqc.reports.uid import render_uid_coverage


_STYLE = """
:root{color-scheme:light dark;--bg:#f6f7f9;--surface:#fff;--ink:#1c2b3c;--muted:#596778;--line:#dce2e8;--accent:#096d78;--error:#a83d30;--warning:#805a0a;--pass:#246c54;--nav:#142c3a}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.6 ui-sans-serif,system-ui,sans-serif}
a{color:var(--accent)}button,input,select{font:inherit}button,a,input,select,summary{-webkit-tap-highlight-color:transparent}:focus-visible{outline:3px solid var(--accent);outline-offset:4px}
.skip-link{position:absolute;left:16px;top:-100px;background:var(--surface);padding:12px;z-index:2}.skip-link:focus{top:12px}
.topbar{background:var(--nav);color:#fff;padding:16px max(24px,calc((100vw - 1376px)/2));display:flex;align-items:center;justify-content:space-between;gap:20px}
.brand{font-size:24px;font-weight:800;letter-spacing:-1px}.brand small{font-size:12px;font-weight:500;letter-spacing:2px;text-transform:uppercase;margin-left:18px;color:#c1d2db}
main{max-width:1120px;margin:auto;padding:0 32px 28px}h1,h2,h3,p{margin:0}h1{font-size:clamp(28px,3vw,40px);letter-spacing:-1.3px;line-height:1.2;margin:8px 0 12px}h2{font-size:20px;letter-spacing:-.5px}h3{font-size:18px;letter-spacing:-.2px}
code{font-size:1em;overflow-wrap:anywhere}small{font-size:inherit}small,.muted{color:var(--muted)}.error{color:var(--error)}.warning{color:var(--warning)}.pass{color:var(--pass)}.info{color:var(--accent)}
.demo-note{padding:10px 0;color:var(--muted);font-size:14px;border-bottom:1px dashed var(--line)}.demo-nav{display:flex;gap:20px;margin:12px 0 0}.demo-nav a{font-size:14px;text-decoration:none;padding-bottom:4px}.demo-nav a[aria-current]{color:var(--ink);border-bottom:2px solid var(--accent);font-weight:700}
.hero{padding:26px 0 24px;border-bottom:1px solid var(--line);display:block}.eyebrow{text-transform:uppercase;font-size:12px;font-weight:750;letter-spacing:1.5px;color:var(--muted)}.next-step{max-width:85ch;color:var(--muted);font-size:16px}.tally{display:flex;flex-wrap:wrap;gap:18px;margin:14px 0 0;font-size:14px}.tally strong{font-size:18px;margin-right:4px;font-variant-numeric:tabular-nums}
.audit-meta{align-self:center;border-left:1px solid var(--line);padding-left:24px;font-size:14px}.audit-meta p+p{margin-top:6px}.audit-meta span{display:block;color:var(--muted)}
.workspace{display:block;margin-top:32px}.overview{min-width:0;border-right:1px solid var(--line);padding-right:24px}.overview>h2{font-size:14px;text-transform:uppercase;letter-spacing:1px;margin-bottom:20px;color:var(--muted)}
.chart{margin:0 0 26px;min-width:0}.chart h2{font-size:16px;letter-spacing:0;margin-bottom:6px}.chart p,.coverage-note{font-size:14px;color:var(--muted);margin:8px 0}.bar-row{margin-top:12px}.bar-label{display:flex;justify-content:space-between;gap:12px;font-size:14px;margin-bottom:5px}.bar-label strong{font-variant-numeric:tabular-nums}.bar-row svg{display:block;width:100%;height:5px}.bar-track{fill:var(--line)}.bar-fill{fill:var(--accent)}.bar-fill.error{fill:var(--error)}.bar-fill.warning{fill:var(--warning)}.bar-fill.pass{fill:var(--pass)}
.category-bar{display:block;width:100%;text-align:left;border:1px solid transparent;padding:7px;border-radius:4px;background:transparent;color:var(--ink);font-weight:400}.category-bar:disabled{cursor:default;opacity:1}.category-bar:not(:disabled):hover,.category-bar[aria-pressed=true]{border-color:var(--accent);background:var(--surface)}
.inventory{margin:16px 0 24px;padding:0;font-size:14px}.inventory div{display:flex;justify-content:space-between;gap:16px;padding:7px 0;border-bottom:1px solid var(--line)}.inventory dt{color:var(--muted)}.inventory dd{margin:0;font-weight:700}
.review{min-width:0}.section-heading{display:flex;justify-content:space-between;align-items:baseline;gap:12px}.section-heading p{font-size:14px;color:var(--muted)}
button,input,select{border:1px solid var(--line);border-radius:5px;background:var(--surface);color:var(--ink);font-size:14px;min-height:38px;padding:8px 10px}button{cursor:pointer;font-weight:600}button:hover{border-color:var(--accent)}#print{background:transparent;color:#fff;border-color:#58707d}
.controls{display:flex;align-items:end;flex-wrap:wrap;gap:10px;padding:16px 0 12px;border-bottom:1px solid var(--line)}label{display:grid;gap:4px;font-size:12px;font-weight:650}.controls label:first-child{flex:1;min-width:160px}input{width:100%}
.review-tools{display:flex;align-items:center;justify-content:space-between;gap:12px;margin:12px 0 16px}.review-tools p{font-size:14px;color:var(--muted)}.review-tools button{font-size:14px;min-height:30px;padding:5px 8px}
.issue{background:var(--surface);border:1px solid var(--line);border-radius:8px;margin-bottom:24px;overflow:hidden}.issue-head{display:flex;align-items:center;justify-content:space-between;gap:16px;padding:16px 20px 0}.issue-count{font-size:14px;color:var(--muted);text-align:right}.badge{font-size:12px;font-weight:800;text-transform:uppercase;letter-spacing:.7px;display:inline-flex;align-items:center;gap:6px}.badge:before{content:'●';font-size:12px}
.issue-content{padding:8px 20px 16px}.issue h3{margin-bottom:12px}.action{display:grid;grid-template-columns:88px minmax(0,1fr);gap:12px;font-size:16px}.action>span{font-size:12px;font-weight:700;letter-spacing:.8px;text-transform:uppercase;color:var(--accent);padding-top:3px}.rule-meta{margin:0;padding:12px 20px;color:var(--muted);font-size:14px}.rule-meta small{display:block;margin-top:4px}
.occurrences{border-top:1px solid var(--line)}summary{cursor:pointer;font-size:14px;font-weight:600;color:var(--accent);padding:12px 20px}.occurrences[open] summary{border-bottom:1px solid var(--line);background:var(--bg)}
.table-wrap{overflow-x:auto}table{border-collapse:collapse;width:100%;text-align:left;table-layout:fixed}th,td{padding:10px 20px;border-bottom:1px solid var(--line);vertical-align:top;overflow-wrap:anywhere;font-size:14px}th{font-size:12px;text-transform:uppercase;letter-spacing:.5px;color:var(--muted);background:var(--bg)}th:first-child{width:55%}tr:last-child td{border:0}.cell-label{display:none}.print-copy{display:none}
.panel{padding:24px;background:var(--surface);border:1px solid var(--line);border-radius:8px}.empty-state{text-align:center;padding:40px 24px;margin-top:20px}.empty-state strong{display:block;font-size:20px;margin-bottom:8px}.empty-state p{max-width:65ch;margin:auto;font-size:16px;color:var(--muted)}.empty-mark{display:block;font-size:32px;margin-bottom:8px}.empty-state a{display:inline-block;margin-top:12px}
#no-matches{border:1px dashed var(--line);border-radius:6px;padding:24px;color:var(--muted);font-size:16px}
.unreadable{margin-top:24px}.unreadable h2{margin-bottom:12px}.unreadable ul{list-style:none;padding:0;margin:0}.unreadable li{padding:10px 0;border-bottom:1px solid var(--line);overflow-wrap:anywhere}.unreadable li:last-child{border:0}.unreadable small{display:block}
footer{margin-top:28px;border-top:1px solid var(--line);padding:16px 0;color:var(--muted);font-size:14px}footer p+p{margin-top:6px}
.supporting{border-bottom:1px solid var(--line);margin:12px 0 24px}.supporting>summary{padding:16px 0}.supporting-content{padding:8px 0 24px}.supporting .insights{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,280px),1fr));gap:32px}.supporting .audit-meta{border:0;padding:0;margin:20px 0 0}.supporting .inventory{display:flex;flex-wrap:wrap;gap:24px}.supporting .inventory div{gap:12px}.filter-panel>summary{padding:12px 0}.filter-panel .controls{padding-top:0}.print-overview{display:none}
@media print{.supporting,.filter-panel{display:none!important}.print-overview{display:block}.print-overview .audit-meta{border:0;padding:0;font-size:10px}.print-overview .insights{display:flex}}
[hidden]{display:none!important}
@media(prefers-color-scheme:dark){:root{--bg:#151f2b;--surface:#1e2b3b;--ink:#e7edf5;--muted:#afbed0;--line:#394b60;--accent:#80cbd2;--error:#ffa18e;--warning:#edcd79;--pass:#8bd3a3;--nav:#101a25}}
@media screen and (max-width:900px){.workspace{grid-template-columns:240px minmax(0,1fr);gap:20px}.overview{padding-right:16px}.hero{grid-template-columns:minmax(0,1fr) 200px;gap:20px}.controls label{flex:1}.controls label:first-child{flex-basis:100%}}
@media screen and (max-width:650px){main{padding:0 16px 20px}.topbar{padding:12px 16px}.brand small{display:none}.hero{display:block;padding:22px 0}.audit-meta{border:0;padding:0;margin-top:16px}.audit-meta span{display:inline;margin-right:8px}.workspace{display:flex;flex-direction:column;gap:20px;margin-top:20px}.overview{border:0;padding:0;border-bottom:1px solid var(--line)}.overview>h2{margin-bottom:12px}.insights{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:16px}.chart{margin-bottom:16px}.inventory{margin:0 0 16px}.review-tools{align-items:start}.section-heading{display:block}.issue-head{padding:14px 16px 0;gap:10px}.issue-content{padding:8px 16px 14px}.action{display:block}.action>span{display:block;margin-bottom:4px}summary{padding:12px 16px}
 .table-wrap{overflow:visible}table,tbody{display:block}thead{position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%)}tr{display:block;border-bottom:1px solid var(--line);padding:12px 16px}td{display:block;border:0;padding:0;margin-bottom:8px}td:last-child{margin-bottom:0}.cell-label{display:block;font-size:12px;text-transform:uppercase;letter-spacing:.5px;color:var(--muted);margin-bottom:3px}
}
@media print{
 :root{color-scheme:light;--bg:white;--surface:white;--ink:black;--muted:#444;--line:#bbb;--accent:#075761;--error:#822d22;--warning:#725000;--pass:#205640}
 @page{margin:14mm}main{max-width:none;padding:0}.topbar{background:white;color:black;padding:0 0 10px;border-bottom:1px solid #bbb}.brand small{color:#444}.hero{padding:14px 0;gap:20px;grid-template-columns:minmax(0,1fr) 180px}h1{font-size:25px}
 nav,.skip-link,.controls,.review-tools,#no-matches,#print{display:none!important}.demo-note{font-size:9px}.workspace{display:block;margin-top:16px}.overview{border:0;padding:0}.overview>h2{margin-bottom:8px}.insights{display:flex;gap:24px}.chart{flex:1;margin-bottom:12px}.inventory{margin:0 0 12px;display:flex;flex-wrap:wrap;gap:16px}.inventory div{gap:8px}.coverage-note{font-size:9px}
 .issue{overflow:visible;border-radius:0;margin-top:12px}.issue-head,.issue-content{padding:10px 12px}.issue-head{break-after:avoid}.issue-content{padding-top:0;break-after:avoid}.issue h3{font-size:14px}.action{font-size:11px}.occurrences{display:none}.print-copy{display:block}.print-copy table{font-size:10px}
 .issue[hidden]{display:block!important}.print-copy tr{break-inside:avoid}thead{display:table-header-group}th,td{font-size:9px;padding:6px 10px}h2,h3{break-after:avoid}.empty-state{break-inside:avoid}.category-bar,.category-bar[aria-pressed=true]{border-color:transparent;background:transparent}svg{print-color-adjust:exact}
}
"""


def _bars(items: list[tuple[str, int, str]], maximum: int, *, interactive: bool = False) -> str:
    """Use fixed geometry and escaped labels; exact counts also work without SVG."""
    return "".join(
        (f'<button type="button" class="bar-row category-bar" data-category="{escape(label)}" aria-pressed="false" aria-controls="findings-body" disabled>' if interactive else '<div class="bar-row">')
        + f'<span class="bar-label"><span>{escape(label)}</span>'
        f'<strong>{count}</strong></span><svg viewBox="0 0 1000 10" preserveAspectRatio="none" aria-hidden="true">'
        f'<rect class="bar-track" width="1000" height="10" rx="5"/>'
        f'<rect class="bar-fill {tone}" width="{1000 * count / max(maximum, 1):.2f}" height="10" rx="5"/>'
        '</svg>' + ('</button>' if interactive else '</div>') for label, count, tone in items
    )


def _category(finding: Finding) -> str:
    if finding.profile_id == "uid-integrity-v0.1":
        return "UID integrity"
    """Share classification between chart controls and finding rows."""
    if finding.profile_id.startswith("policy."):
        return "Project policy"
    name = finding.rule_id.removeprefix(finding.profile_id + ".")
    if name.startswith("direct_phi."):
        return "Identifying fields"
    if name.startswith("private_tags."):
        return "Private tags"
    if name.startswith("pseudonym_format.") or name in {"missing_patient_id", "unchanged_patient_id", "inconsistent_pseudonym", "pseudonym_collision"}:
        return "Patient identifiers"
    if name in {"missing_source", "missing_candidate", "unpaired_source", "unpaired_candidate", "unreadable_source", "unreadable_candidate"}:
        return "File coverage"
    return "Other checks"


def _charts(result: ScanResult) -> str:
    categories = Counter(_category(finding) for finding in result.findings)
    charts = ""
    if categories:
        bars = _bars([(label, count, "") for label, count in categories.most_common()], max(categories.values()), interactive=True)
        charts += f'<figure class="chart"><figcaption><h2>Findings by category</h2><p>All severities · Counts are findings, not unique files. Filters below do not change this chart.</p></figcaption>{bars}</figure>'
    comparison = getattr(result, "comparison", None)
    if comparison is not None and comparison["manifest_pairs"]:
        missing, unreadable = set(), set()
        for finding in result.findings:
            name = finding.rule_id.removeprefix(finding.profile_id + ".")
            if name in {"missing_source", "missing_candidate"}:
                missing.add(finding.path.split("/")[0])
            elif name in {"unreadable_source", "unreadable_candidate"}:
                unreadable.add(finding.path.split("/")[0])
        bars = _bars([
            ("Both files readable", comparison["readable_pairs"], "pass"),
            ("Missing a file", len(missing), "error"),
            ("Unreadable file (neither missing)", len(unreadable - missing), "warning"),
        ], comparison["manifest_pairs"])
        charts += f'<figure class="chart"><figcaption><h2>Manifest pair coverage</h2><p>{comparison["manifest_pairs"]} expected pairs · Readable does not mean checks passed. Missing takes precedence over unreadable; unpaired files are excluded.</p></figcaption>{bars}</figure>'
    return f'<div class="insights">{charts}</div>' if charts else ""


_SCRIPT = """
(() => {
  const search = document.getElementById('search');
  const severity = document.getElementById('severity');
  const category = document.getElementById('category');
  const bars = Array.from(document.querySelectorAll('#overview-panel .category-bar'));
  const issues = Array.from(document.querySelectorAll('.issue'));
  const data = issues.map(issue => ({
    issue,
    shared: (issue.querySelector('.issue-content').textContent + issue.querySelector('.rule-meta').textContent).toLowerCase(),
    rows: Array.from(issue.querySelectorAll('.occurrences tbody tr')).map(row => ({row, text: row.textContent.toLowerCase()})),
    details: issue.querySelector('.occurrences'),
    count: issue.querySelector('.match-count'),
    refs: issue.querySelector('.reference-count')
  }));
  const total = data.reduce((n, item) => n + item.rows.length, 0);
  const count = document.getElementById('visible-count');
  const empty = document.getElementById('no-matches');
  const expand = document.getElementById('expand');
  function syncDetails() {
    const visible = data.filter(item => !item.issue.hidden);
    const open = visible.length > 0 && visible.every(item => item.details.open);
    expand.textContent = open ? 'Collapse file lists' : 'Expand file lists';
    expand.setAttribute('aria-expanded', String(open));
  }
  expand.addEventListener('click', () => {
    const visible = data.filter(item => !item.issue.hidden);
    const open = !visible.every(item => item.details.open);
    visible.forEach(item => { item.details.open = open; });
    syncDetails();
  });
  data.forEach(item => item.details.addEventListener('toggle', syncDetails));
  function filter() {
    const query = search.value.trim().toLowerCase();
    let findings = 0, groups = 0;
    data.forEach(item => {
      const allowed = (!severity.value || item.issue.dataset.severity === severity.value) && (!category.value || item.issue.dataset.category === category.value);
      const sharedMatch = item.shared.includes(query);
      let matches = 0;
      const references = new Set();
      item.rows.forEach(({row, text}) => {
        row.hidden = !(allowed && (sharedMatch || text.includes(query)));
        if (!row.hidden) { matches++; references.add(row.querySelector('code').textContent); }
      });
      item.issue.hidden = matches === 0;
      item.count.textContent = matches + (matches === 1 ? ' finding' : ' findings');
      item.refs.textContent = references.size + (references.size === 1 ? ' reference' : ' references');
      if (matches) { groups++; findings += matches; }
      // A file search reveals its matching occurrences; reset restores a compact view.
      if (query) item.details.open = matches > 0;
    });
    const active = [category.value, severity.value, query && 'text search'].filter(Boolean);
    count.textContent = `${groups} of ${issues.length} issue groups · ${findings} of ${total} findings` + (active.length ? ' · Filtered by: ' + active.join(' + ') : ' · Errors first');
    empty.hidden = findings !== 0 || total === 0;
    bars.forEach(bar => bar.setAttribute('aria-pressed', String(bar.dataset.category === category.value)));
    syncDetails();
  }
  search.addEventListener('input', filter);
  severity.addEventListener('change', filter);
  category.addEventListener('change', filter);
  bars.forEach(bar => {
    bar.disabled = false;
    bar.title = 'Filter findings: ' + bar.dataset.category;
    bar.addEventListener('click', () => {
      category.value = category.value === bar.dataset.category ? '' : bar.dataset.category;
      filter();
      document.getElementById('filter-panel').open = true;
      document.getElementById('findings-title').scrollIntoView({block: 'start'});
      category.focus({preventScroll: true});
    });
  });
  document.getElementById('reset').addEventListener('click', () => {
    search.value = ''; severity.value = ''; category.value = '';
    data.forEach(item => { item.details.open = false; });
    filter(); search.focus();
  });
  document.getElementById('print').addEventListener('click', () => window.print());
  document.getElementById('print').hidden = false;
  document.getElementById('controls').hidden = total === 0;
  document.getElementById('filter-panel').hidden = total === 0;
  expand.hidden = total === 0;
  filter();
})();
"""


def _groups(findings: list[Finding]) -> list[list[Finding]]:
    """Group shared issues without losing per-occurrence fields or differences in advice."""
    groups: dict[tuple, list[Finding]] = {}
    order = {"error": 0, "warning": 1, "info": 2}
    for finding in sorted(findings, key=lambda item: order[item.severity.value]):
        key = (finding.profile_id, finding.rule_id, finding.severity, finding.message,
               finding.recommendation, finding.standard_refs)
        groups.setdefault(key, []).append(finding)
    return list(groups.values())


def _issue(group: list[Finding], number: int) -> str:
    first = group[0]
    level = first.severity.value
    reference_count = len({finding.path for finding in group})
    finding_label = f'{len(group)} finding' + ('s' if len(group) != 1 else '')
    reference_label = f'{reference_count} reference' + ('s' if reference_count != 1 else '')
    distinct_label = f'{reference_count} distinct reference' + ('s' if reference_count != 1 else '')
    rows = []
    for finding in group:
        field = " / ".join(value for value in (finding.keyword, finding.tag) if value) or "Dataset"
        state = finding.value_state.value if finding.tag else "Not applicable"
        rows.append(
            f'<tr><td><span class="cell-label" aria-hidden="true">File / pair reference</span><code>{escape(finding.path)}</code></td>'
            f'<td><span class="cell-label" aria-hidden="true">Field</span>{escape(field)}</td>'
            f'<td><span class="cell-label" aria-hidden="true">Value state</span>{escape(state)}</td></tr>'
        )
    table = (
        '<div class="table-wrap"><table><thead><tr><th scope="col">File / pair reference</th>'
        '<th scope="col">Field</th><th scope="col">Value state</th></tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table></div>'
    )
    refs = f'<small>References: {escape("; ".join(first.standard_refs))}</small>' if first.standard_refs else ""
    return (
        f'<article class="issue" data-severity="{level}" data-category="{escape(_category(first))}" aria-labelledby="issue-{number}">'
        f'<div class="issue-head"><span class="badge {level}">{level}</span>'
        f'<span class="issue-count">{finding_label} · {distinct_label}</span></div>'
        f'<div class="issue-content"><h3 id="issue-{number}">{escape(first.message)}</h3>'
        f'<div class="action"><span>Next step</span><p>{escape(first.recommendation)}</p></div>'
        '</div>'
        f'<details class="occurrences"><summary>View affected files / pairs · <span class="match-count">{finding_label}</span>'
        f' in <span class="reference-count">{reference_label}</span></summary><p class="rule-meta"><code>{escape(first.rule_id)}</code>{refs}</p>{table}</details>'
        f'<div class="print-copy"><p class="rule-meta"><code>{escape(first.rule_id)}</code>{refs}</p>{table}</div></article>'
    )


def render_html(result: ScanResult, *, synthetic: bool = False, demo_phase: str | None = None) -> str:
    """Render findings only; never embed raw records, JSON, or parser messages."""
    comparison = getattr(result, "comparison", None)
    if demo_phase is not None and (
        not synthetic or (comparison is None and result.policy is None and result.uid_checks is None) or demo_phase not in {"before", "after"}
    ):
        raise ValueError("Demo navigation requires a synthetic comparison, policy, or UID audit and a before/after phase.")
    demo_nav = ""
    if demo_phase is not None:
        demo_nav = '<nav class="demo-nav" aria-label="Before and after demo">'
        for phase, label in (("before", "Before corrections"), ("after", "After corrections")):
            current = ' aria-current="page"' if phase == demo_phase else ""
            demo_nav += f'<a href="{phase}.html"{current}>{label}</a>'
        demo_nav += '</nav>'
    title = "Dataset comparison" if comparison is not None else "DICOM metadata audit"
    demo_note = '<aside class="demo-note"><strong>Synthetic demo</strong> · These results use generated example data, not patient files.</aside>' if synthetic else ""
    code = result.exit_code()
    status, status_class = audit_status(result)
    next_step = audit_guidance(result)
    groups = _groups(result.findings)
    rows = [_issue(group, number) for number, group in enumerate(groups, 1)]
    inventory_items = (
        [("Source files", comparison["source_files"]), ("Candidate files", comparison["candidate_files"]),
         ("Candidates read", result.files_scanned), ("Identity pairs checked", comparison["identity_pairs_checked"])]
        if comparison is not None else [("Files read", result.files_scanned)]
    )
    inventory_items.append(("Unreadable files", len(result.skipped_files)))
    inventory = '<dl class="inventory">' + "".join(
        f'<div><dt>{escape(label)}</dt><dd>{count}</dd></div>' for label, count in inventory_items
    ) + '</dl>'
    coverage_note = (
        "Coverage counts manifest pairs, not privacy passes. Unpaired files appear as issues. "
        "Pair references identify rows in your restricted manifest."
        if comparison is not None else "Files read were checked for metadata issues only. Unreadable files are not fully audited."
    )
    no_findings = ""
    if not rows:
        complete = bool(result.files_scanned) and not result.skipped_files
        mark = "✓" if complete else "—"
        explanation = (
            "The checked metadata produced no findings. This is not an approval to share data; complete the remaining privacy review."
            if complete else "This does not indicate a clean audit. No findings were recorded for the unreadable or absent input; resolve coverage before proceeding."
        )
        unreadable_link = '<a href="#unreadable-title">Review unreadable files ↓</a>' if result.skipped_files else ""
        no_findings = f'<div class="panel empty-state"><span class="empty-mark {status_class}" aria-hidden="true">{mark}</span><strong>No findings were recorded</strong><p>{explanation}</p>{unreadable_link}</div>'
    skipped = ""
    if result.skipped_files:
        skipped = '<section class="unreadable" aria-labelledby="unreadable-title"><h2 id="unreadable-title">Unreadable files</h2><div class="panel"><p>These files were not fully audited. Inspect them locally and rerun the audit.</p><ul>'
        skipped += "".join(f'<li><code>{escape(path)}</code><small>Could not read DICOM metadata.</small></li>' for path in result.skipped_files)
        skipped += '</ul></div></section>'
    script_hash = base64.b64encode(hashlib.sha256(_SCRIPT.encode()).digest()).decode()
    category_options = "".join(f'<option>{escape(label)}</option>' for label in sorted({_category(finding) for finding in result.findings}))
    policy_meta = ""
    if result.policy is not None:
        policy_meta = (
            f'<p><span>Project policy</span><code>{escape(result.policy["id"])}</code> · Additive checks</p>'
            f'<p><span>Policy SHA-256</span><code>{escape(result.policy["sha256"])}</code></p>'
        )
    overview = (
        f'{_charts(result)}{inventory}<p class="coverage-note">{coverage_note}</p>'
        f'<div class="audit-meta"><p><span>Audit profile</span><code>{escape(result.profile_id)}</code></p>'
        f'<p><span>Engine</span>dicomqc {escape(__version__)} · Exit code {code}</p>'
        f'{policy_meta}'
        '<p><span>Scope</span>Metadata only · Read-only</p></div>'
        f'{render_uid_coverage(result.uid_checks)}'
    )
    vendor_body = render_vendor_inventory(result.vendor_summary) if result.vendor_summary is not None else ""
    vendor_panel = (
        '<details class="supporting" id="vendor-panel"><summary>Scanner and private-tag inventory</summary>'
        f'<div class="supporting-content">{vendor_body}</div></details>'
        f'<div class="print-overview">{vendor_body}</div>'
    ) if vendor_body else ""
    privacy_note = (
        "Vendor inventory includes observed metadata labels. Findings omit raw tag values."
        if vendor_body else "Raw tag values are omitted."
    )
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'sha256-{script_hash}'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>dicomqc — {title}</title><style>{_STYLE}{VENDOR_STYLE if vendor_body else ""}</style></head>
<body><a class="skip-link" href="#findings-title">Skip to findings</a>
<div class="topbar"><div class="brand">dicomqc <small>Audit workspace</small></div><button type="button" id="print" hidden>Print report</button></div>
<main>{demo_note}{demo_nav}<header class="hero" id="summary">
<div><p class="eyebrow">{title}</p><h1 class="{status_class}">{status}</h1><p class="next-step">{next_step}</p>
<p class="tally"><span><strong>{result.error_count}</strong> errors</span><span><strong>{result.warning_count}</strong> warnings</span><span><strong>{result.info_count}</strong> information</span><span><strong>{len(groups)}</strong> issue {'group' if len(groups) == 1 else 'groups'}</span></p></div>
</header>
<details class="supporting" id="overview-panel"><summary>{"Pairing coverage, charts and audit details" if comparison is not None else "Charts and audit details"}</summary><div class="supporting-content">{overview}</div></details>
<div class="print-overview">{overview}</div>
{vendor_panel}
<div class="workspace"><div class="review"><section aria-labelledby="findings-title"><div class="section-heading"><h2 id="findings-title" tabindex="-1">Issues to review</h2></div>
<details class="filter-panel" id="filter-panel" hidden><summary>Search and filter</summary>
<div class="controls" id="controls" hidden>
<label for="search">Search findings<input id="search" type="search" placeholder="File, rule, field or action…"></label>
<label for="severity">Severity<select id="severity"><option value="">All severities</option><option value="error">Errors</option><option value="warning">Warnings</option><option value="info">Information</option></select></label>
<label for="category">Category<select id="category"><option value="">All categories</option>{category_options}</select></label>
<button type="button" id="reset">Reset filters</button></div></details>
<noscript><p>All issue groups are shown. Expand a group to inspect its files. Enable JavaScript to search and filter.</p></noscript>
<div class="review-tools"{' hidden' if not rows else ''}><p id="visible-count" role="status" aria-live="polite">{len(groups)} issue groups · {len(result.findings)} findings · Errors first</p><button type="button" id="expand" aria-expanded="false" aria-controls="findings-body" hidden>Expand file lists</button></div>{no_findings}
<p id="no-matches" hidden>No findings match these filters. Change your search or choose Reset filters to see all findings.</p>
<div id="findings-body">{"".join(rows)}</div></section>{skipped}</div></div>
<footer id="report-notes"><p>Metadata audit only. Pixels and facial features are not inspected. A passing result is not approval to share data.</p>
<p>{privacy_note} Scan paths may still identify people; review reports before sharing. Comparison reports use manifest references.</p>
<p>This report works offline. Printing includes all findings, regardless of active filters.</p></footer>
</main><script>{_SCRIPT}</script></body></html>
'''


def write_html(result: ScanResult, path: Path, *, synthetic: bool = False, demo_phase: str | None = None) -> None:
    path.write_text(render_html(result, synthetic=synthetic, demo_phase=demo_phase), encoding="utf-8")
