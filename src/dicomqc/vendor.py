"""Opt-in equipment labels and scope-aware private-block inventory.

Observed equipment and creator labels can identify a site. Only callers that
explicitly request this inventory should export it. Private payload values are
never inspected or included in the summary.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any

from dicomqc.model.metadata import DicomTag, MetadataRecord

_FORBIDDEN_PRIVATE_GROUPS = {0x0001, 0x0003, 0x0005, 0x0007, 0xFFFF}
_EQUIPMENT_TAGS = {
    "(0008,0070)": "Manufacturer",
    "(0008,1090)": "ManufacturerModelName",
    "(0018,1020)": "SoftwareVersions",
}


def _label(value: object) -> str | None:
    """Keep observed text intact; never stringify sequences or binary content."""
    return value if isinstance(value, str) and value.strip() else None


def _equipment(record: MetadataRecord) -> tuple[str | None, str | None, tuple[str, ...]]:
    top_level = {
        _EQUIPMENT_TAGS[tag.tag]: tag.raw_value for tag in record.tags.values()
        if not tag.is_nested and not tag.dataset_path
        and not tag.is_private and tag.tag in _EQUIPMENT_TAGS
    }
    software = top_level.get("SoftwareVersions")
    versions = software if isinstance(software, Sequence) and not isinstance(software, (str, bytes)) else (software,)
    return (
        _label(top_level.get("Manufacturer")),
        _label(top_level.get("ManufacturerModelName")),
        tuple(label for value in versions if (label := _label(value)) is not None),
    )


def _creator(tag: DicomTag | None, group: int) -> tuple[str | None, str]:
    if tag is None:
        return None, "absent"
    value = tag.raw_value
    label = _label(value)
    if tag.vr != "LO" or group in _FORBIDDEN_PRIVATE_GROUPS:
        return label, "invalid"
    if value is None or isinstance(value, str) and not value.strip():
        return None, "empty"
    # A creator is LO with VM 1 in the default character repertoire (PS3.5 7.8.1).
    if (not isinstance(value, str) or len(value) > 64
            or any(ord(char) < 32 or ord(char) > 126 or char == "\\" for char in value)):
        return label, "invalid"
    return label, "present"


def summarize_vendors(records: Iterable[MetadataRecord]) -> dict[str, Any]:
    """Aggregate observed labels and private blocks, without assigning safety.

    Private reservations belong only to their own dataset/sequence item. Files
    count readable input records, while occurrences count scope-local blocks.
    """
    equipment: dict[tuple[str | None, str | None, tuple[str, ...]], int] = {}
    blocks: dict[tuple[str, str, str | None, str], dict[str, Any]] = {}
    files = private_elements = creator_elements = unassigned_private_elements = 0
    for record in records:
        files += 1
        equipment_key = _equipment(record)
        equipment[equipment_key] = equipment.get(equipment_key, 0) + 1
        scoped: dict[tuple[tuple[str, ...], int, int | str], dict[str, Any]] = {}
        for tag in record.tags.values():
            if not tag.is_private:
                continue
            if tag.is_nested and not tag.dataset_path:
                raise ValueError("Vendor inventory requires dataset paths for nested private elements.")
            group, element = int(tag.tag[1:5], 16), int(tag.tag[6:10], 16)
            reservation = 0x0010 <= element <= 0x00FF
            block = element if reservation else element >> 8 if element >= 0x1000 else "unassigned"
            key = (tag.dataset_path, group, block)
            item = scoped.setdefault(key, {"creator": None, "elements": 0, "nested_elements": 0})
            if reservation:
                item["creator"] = tag
                creator_elements += 1
            else:
                item["elements"] += 1
                item["nested_elements"] += int(bool(tag.dataset_path) or tag.is_nested)
                private_elements += 1
        seen = set()
        for (_scope, group, block), item in scoped.items():
            label, state = _creator(item["creator"], group)
            if block == "unassigned":
                state = "invalid"
            if state != "present":
                unassigned_private_elements += item["elements"]
            key = (f"{group:04X}", f"{block:02X}" if isinstance(block, int) else block, label, state)
            row = blocks.setdefault(key, {
                "group": key[0], "block": key[1], "creator": label, "creator_state": state,
                "files": 0, "occurrences": 0, "elements": 0, "nested_elements": 0,
            })
            row["files"] += int(key not in seen)
            row["occurrences"] += 1
            row["elements"] += item["elements"]
            row["nested_elements"] += item["nested_elements"]
            seen.add(key)
    return {
        "files": files,
        "equipment": [
            {"manufacturer": maker, "model": model, "software_versions": list(versions), "files": count}
            for (maker, model, versions), count in sorted(
                equipment.items(), key=lambda item: (item[0][0] or "", item[0][1] or "", item[0][2]),
            )
        ],
        "private_blocks": [blocks[key] for key in sorted(blocks, key=lambda key: (key[0], key[1], key[2] or "", key[3]))],
        "private_elements": private_elements,
        "creator_elements": creator_elements,
        "unassigned_private_elements": unassigned_private_elements,
    }
