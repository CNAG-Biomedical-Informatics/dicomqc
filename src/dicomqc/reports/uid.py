"""Shared, value-free UID coverage for standalone HTML and MultiQC."""

from html import escape


def render_uid_coverage(summary: dict | None) -> str:
    if summary is None:
        return ""
    rows = "".join(
        f'<tr><th scope="row">{escape(keyword)}</th><td>{counts["valid"]}</td>'
        f'<td>{counts["absent_or_empty"]}</td><td>{counts["invalid"]}</td></tr>'
        for keyword, counts in summary["fields"].items()
    )
    return (
        '<section class="uid-coverage"><h3>UID integrity</h3>'
        f'<p><code>{escape(summary["profile_id"])}</code> · Additive checks</p>'
        f'<p>{summary["complete_hierarchies_checked"]} of {summary["files_checked"]} files '
        'have three usable identifiers for hierarchy checks.</p>'
        '<div style="overflow-x:auto"><table><thead><tr><th>Top-level identifier</th>'
        '<th>Valid syntax</th><th>Absent / empty</th><th>Invalid</th></tr></thead>'
        f'<tbody>{rows}</tbody></table></div>'
        '<p>Valid syntax does not imply a consistent hierarchy. Missing fields are coverage gaps, '
        'not required-attribute findings. Checks use only files read in this scan; '
        'nested references, pixel content, and global uniqueness are not checked.</p></section>'
    )
