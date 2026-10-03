"""Shared, escaped vendor inventory presentation for HTML and MultiQC."""

from __future__ import annotations

from html import escape
from typing import Any


def render_vendor_inventory(summary: dict[str, Any]) -> str:
    """Only render the explicitly requested label inventory, never private payloads."""
    def label(value: str | None) -> str:
        return escape(value) if value is not None else '<em>Not recorded</em>'

    def table(headers: tuple[str, ...], rows: list[list[str]]) -> str:
        if not rows:
            return '<p>No entries in the readable files.</p>'
        head = ''.join(f'<th scope="col">{escape(header)}</th>' for header in headers)
        body = ''.join(
            '<tr>' + ''.join(
                f'<td><span class="vendor-cell-label">{escape(header)}</span>{cell}</td>'
                for header, cell in zip(headers, row)
            ) + '</tr>'
            for row in rows
        )
        return f'<div class="vendor-table-wrap"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'

    equipment = [
        [label(row['manufacturer']), label(row['model']),
         '<br>'.join(label(value) for value in row['software_versions']) or label(None),
         str(row['files'])]
        for row in summary['equipment']
    ]
    creators = []
    for row in summary['private_blocks']:
        creator = label(row['creator']) if row['creator_state'] == 'present' else escape(
            {'empty': 'Empty creator', 'absent': 'No creator', 'invalid': 'Invalid creator'}[row['creator_state']]
        )
        block = f"({row['group']},{row['block']}xx)" if row['block'] != 'unassigned' else f"({row['group']},unassigned)"
        creators.append([
            creator, f'<code>{escape(block)}</code>', str(row['files']),
            str(row['occurrences']), str(row['elements']), str(row['nested_elements']),
        ])
    return (
        '<div class="vendor-inventory">'
        '<p><strong>Contains observed metadata labels.</strong> Manufacturer, model, software and private creator '
        'values may identify people or sites. Review this inventory before sharing, including when a project policy passes.</p>'
        f'<p>{summary["files"]} readable files · {summary["creator_elements"]} creator declarations · '
        f'{summary["private_elements"]} private data elements · '
        f'{summary["unassigned_private_elements"]} unassigned private elements</p>'
        '<h3>Equipment combinations</h3>'
        '<p>Grouped by declared manufacturer, model and software. These are not counts of physical scanners.</p>'
        + table(('Manufacturer', 'Model', 'Software versions', 'Files'), equipment)
        + '<h3>Private creator blocks</h3>'
        '<p>Reservations are local to each dataset or sequence item. Unassigned elements have no usable creator '
        'in their own dataset. Private payload values are not included.</p>'
        + table(('Creator', 'Block', 'Files', 'Occurrences', 'Elements', 'Nested'), creators)
        + '<p>Counts support review; they do not establish whether a private attribute is safe. '
        'The inventory does not change findings or the exit code.</p></div>'
    )


VENDOR_STYLE = """
.vendor-inventory{font-size:14px;line-height:1.6;overflow-wrap:anywhere}
.vendor-inventory h3{font-size:17px;margin:22px 0 8px}
.vendor-inventory p{margin:10px 0}
.vendor-inventory table{width:100%;table-layout:auto;border-collapse:collapse;font-size:14px}
.vendor-inventory th:first-child{width:auto}
.vendor-inventory th,.vendor-inventory td{text-align:left;vertical-align:top;padding:10px 12px;border-bottom:1px solid #94a3b855;white-space:normal;overflow-wrap:anywhere}
.vendor-inventory code{font-size:inherit}
.vendor-table-wrap{overflow-x:auto}
.vendor-cell-label{display:none}
@media screen and (max-width:650px){
 .vendor-inventory table,.vendor-inventory tbody{display:block}
 .vendor-inventory thead{display:none}
 .vendor-inventory tr{display:block;border-bottom:1px solid #94a3b855;padding:10px 0}
 .vendor-inventory td{display:block;border:0;padding:4px 0}
 .vendor-cell-label{display:block;font-size:12px;font-weight:600}
}
"""
