"""Equipment labels and dataset-local private ownership, never private payloads."""

from dataclasses import replace
import json
from pathlib import Path

from pydicom.dataset import Dataset
from pydicom.multival import MultiValue
import pytest

from dicomqc.backend.pydicom_backend import PydicomBackend
from dicomqc.fixtures import write_synthetic_dicom_fixtures
from dicomqc.model.metadata import DicomTag, MetadataRecord, value_state
from dicomqc.rules.builtin import evaluate_record
from dicomqc.vendor import summarize_vendors


def _normalize(dataset, filename="image.dcm"):
    return PydicomBackend()._normalize(dataset, Path(filename))


def _tag(number, value, *, vr="LO", keyword="PrivateData", scope=()):
    return DicomTag(
        tag=number, keyword=keyword, vr=vr, is_private=int(number[1:5], 16) % 2 == 1,
        raw_value=value, value_state=value_state(value), is_nested=bool(scope), dataset_path=scope,
    )


def _record(*tags, filename="image.dcm"):
    return MetadataRecord(
        Path(filename), None, None, None, None, None,
        {str(index): tag for index, tag in enumerate(tags)},
    )


def _private(dataset, *, creator="ACME", payload="PRIVATE_PAYLOAD_SECRET", slot=0x10, group=0x0029):
    if creator is not None:
        dataset.add_new((group, slot), "LO", creator)
    dataset.add_new((group, slot << 8 | 0x01), "LO", payload)
    return dataset


def _block(summary, *, creator, state="present", group="0029", block="10"):
    return next(row for row in summary["private_blocks"] if (
        row["creator"], row["creator_state"], row["group"], row["block"]
    ) == (creator, state, group, block))


def test_empty_inventory_has_stable_shape():
    assert summarize_vendors([]) == {
        "files": 0, "equipment": [], "private_blocks": [], "private_elements": 0,
        "creator_elements": 0, "unassigned_private_elements": 0,
    }


def test_no_equipment_headers_are_grouped_explicitly():
    summary = summarize_vendors([_normalize(Dataset()), _normalize(Dataset(), "second.dcm")])
    assert summary["equipment"] == [{"manufacturer": None, "model": None, "software_versions": [], "files": 2}]
    assert summary["private_blocks"] == []
    assert summary["files"] == 2


def test_equipment_groups_preserve_observed_labels_and_multivalued_software():
    first = Dataset()
    first.Manufacturer = "Example Imaging"
    first.ManufacturerModelName = "  Research MR"
    first.SoftwareVersions = ["1.0", "build-2"]
    second = first.copy()
    third = Dataset()
    third.Manufacturer = "Another Vendor"
    third.SoftwareVersions = "2.0"
    records = [_normalize(first), _normalize(second, "second.dcm"), _normalize(third, "third.dcm")]
    summary = summarize_vendors(iter(records))
    assert summary["equipment"] == [
        {"manufacturer": "Another Vendor", "model": None, "software_versions": ["2.0"], "files": 1},
        {"manufacturer": "Example Imaging", "model": "  Research MR", "software_versions": ["1.0", "build-2"], "files": 2},
    ]
    assert summarize_vendors(reversed(records)) == summary


def test_nested_equipment_does_not_supply_or_replace_top_level_fields():
    dataset = Dataset()
    dataset.Manufacturer = "Top level vendor"
    item = Dataset()
    item.Manufacturer = "Nested vendor"
    item.ManufacturerModelName = "Nested model"
    item.SoftwareVersions = "Nested version"
    dataset.RequestAttributesSequence = [item]
    summary = summarize_vendors([_normalize(dataset)])
    assert summary["equipment"] == [{"manufacturer": "Top level vendor", "model": None, "software_versions": [], "files": 1}]
    assert "Nested" not in json.dumps(summary)


def test_equipment_text_is_not_truncated_or_stripped():
    labels = ["x" * 300 + "a", "x" * 300 + "b"]
    records = [_record(
        _tag("(0008,0070)", label, keyword="Manufacturer"),
        _tag("(0008,1090)", " model ", keyword="ManufacturerModelName"),
        _tag("(0018,1020)", MultiValue(str, [" first ", "", "second"]), keyword="SoftwareVersions"),
    ) for label in labels]
    summary = summarize_vendors(records)
    assert [row["manufacturer"] for row in summary["equipment"]] == labels
    assert all(row["model"] == " model " for row in summary["equipment"])
    assert all(row["software_versions"] == [" first ", "second"] for row in summary["equipment"])


@pytest.mark.parametrize("value", [None, "", "  ", b"BINARY_SECRET", 123, Dataset(), [Dataset()]])
def test_nontext_equipment_cannot_serialize_payload_objects(value):
    summary = summarize_vendors([_record(
        _tag("(0008,0070)", value, keyword="Manufacturer"),
        _tag("(0008,1090)", value, keyword="ManufacturerModelName"),
        _tag("(0018,1020)", value, keyword="SoftwareVersions"),
    )])
    assert summary["equipment"] == [{"manufacturer": None, "model": None, "software_versions": [], "files": 1}]
    assert "SECRET" not in json.dumps(summary)


def test_private_payload_cannot_impersonate_equipment_via_its_keyword():
    summary = summarize_vendors([_record(
        _tag("(0029,1001)", "PRIVATE_PAYLOAD_SECRET", keyword="Manufacturer"),
        _tag("(0029,1002)", "PRIVATE_PAYLOAD_SECRET", keyword="ManufacturerModelName"),
        _tag("(0029,1003)", "PRIVATE_PAYLOAD_SECRET", keyword="SoftwareVersions"),
    )])
    assert summary["equipment"] == [{"manufacturer": None, "model": None, "software_versions": [], "files": 1}]
    assert summary["private_elements"] == 3
    assert "PAYLOAD_SECRET" not in json.dumps(summary)


def test_default_demo_inventory_does_not_change_builtin_findings(tmp_path):
    records = [PydicomBackend().read_metadata(path) for path in write_synthetic_dicom_fixtures(tmp_path)]
    before = [evaluate_record(record) for record in records]
    summary = summarize_vendors(records)
    assert summary["files"] == 3
    assert summary["creator_elements"] == 2
    assert summary["private_elements"] == summary["unassigned_private_elements"] == 0
    assert summary["private_blocks"] == [{
        "group": "0029", "block": "10", "creator": "SIEMENS CSA HEADER", "creator_state": "present",
        "files": 2, "occurrences": 2, "elements": 0, "nested_elements": 0,
    }]
    assert [evaluate_record(record) for record in records] == before
    assert sum(len(findings) for findings in before) == 5


def test_ordinary_private_block_counts_without_payload_values():
    dataset = _private(Dataset())
    dataset.add_new((0x0029, 0x10FF), "OB", b"BINARY_PRIVATE_PAYLOAD_SECRET")
    summary = summarize_vendors([_normalize(dataset)])
    assert summary["private_elements"] == 2
    assert summary["creator_elements"] == 1
    assert summary["unassigned_private_elements"] == 0
    assert summary["private_blocks"] == [{
        "group": "0029", "block": "10", "creator": "ACME", "creator_state": "present",
        "files": 1, "occurrences": 1, "elements": 2, "nested_elements": 0,
    }]
    assert "PAYLOAD_SECRET" not in json.dumps(summary)


def test_orphan_payload_does_not_inherit_reservation_from_parent_or_sibling():
    dataset = _private(Dataset(), creator="ROOT")
    first = _private(Dataset(), creator="ITEM_ONE")
    second = _private(Dataset(), creator="ITEM_TWO")
    orphan = _private(Dataset(), creator=None)
    dataset.RequestAttributesSequence = [first, second, orphan]
    record = _normalize(dataset)
    summary = summarize_vendors([record])
    assert summary["private_elements"] == 4
    assert summary["creator_elements"] == 3
    assert summary["unassigned_private_elements"] == 1
    assert len(summary["private_blocks"]) == 4
    assert _block(summary, creator="ROOT")["nested_elements"] == 0
    assert _block(summary, creator="ITEM_ONE")["nested_elements"] == 1
    assert _block(summary, creator="ITEM_TWO")["nested_elements"] == 1
    assert _block(summary, creator=None, state="absent")["nested_elements"] == 1
    payloads = [tag for tag in record.tags.values() if tag.tag == "(0029,1001)"]
    assert {tag.dataset_path for tag in payloads} == {
        (), ("(0040,0275)[0]",), ("(0040,0275)[1]",), ("(0040,0275)[2]",),
    }
    assert [tag.is_nested for tag in payloads].count(False) == 1


@pytest.mark.parametrize("number", ["(0029,0010)", "(0029,1001)"])
def test_unknown_nested_scope_fails_closed_instead_of_inheriting_root_ownership(number):
    unknown = replace(_tag(number, "UNKNOWN_NESTED_SECRET"), is_nested=True)
    record = _record(
        _tag("(0029,0010)", "ROOT_CREATOR"), _tag("(0029,1001)", "ROOT_PAYLOAD_SECRET"), unknown,
    )
    with pytest.raises(ValueError, match="requires dataset paths for nested private elements") as error:
        summarize_vendors([record])
    assert "SECRET" not in str(error.value)
    assert "ROOT_CREATOR" not in str(error.value)


def test_unknown_nested_standard_fields_do_not_require_private_ownership_paths():
    nested_standard = replace(
        _tag("(0008,0070)", "NESTED_VENDOR_SECRET", keyword="Manufacturer"), is_nested=True,
    )
    summary = summarize_vendors([_record(
        _tag("(0029,0010)", "ROOT_CREATOR"), _tag("(0029,1001)", "PAYLOAD_SECRET"), nested_standard,
    )])
    assert _block(summary, creator="ROOT_CREATOR")["elements"] == 1
    assert summary["equipment"] == [{"manufacturer": None, "model": None, "software_versions": [], "files": 1}]
    assert "SECRET" not in json.dumps(summary)


def test_scope_paths_include_every_ancestor_and_sequence_tag():
    dataset = Dataset()
    middle = Dataset()
    middle.RequestAttributesSequence = [_private(Dataset(), creator="DEEP")]
    dataset.RequestAttributesSequence = [middle]
    dataset.SourceImageSequence = [_private(Dataset(), creator="OTHER")]
    record = _normalize(dataset)
    creators = {tag.raw_value: tag.dataset_path for tag in record.tags.values() if tag.tag == "(0029,0010)"}
    assert creators == {
        "DEEP": ("(0040,0275)[0]", "(0040,0275)[0]"),
        "OTHER": ("(0008,2112)[0]",),
    }
    summary = summarize_vendors([record])
    assert _block(summary, creator="DEEP")["nested_elements"] == 1
    assert _block(summary, creator="OTHER")["nested_elements"] == 1


def test_same_creator_in_several_items_counts_occurrences_but_file_once():
    dataset = Dataset()
    dataset.RequestAttributesSequence = [_private(Dataset()), _private(Dataset())]
    summary = summarize_vendors([_normalize(dataset), _normalize(dataset, "second.dcm")])
    assert summary["private_blocks"] == [{
        "group": "0029", "block": "10", "creator": "ACME", "creator_state": "present",
        "files": 2, "occurrences": 4, "elements": 4, "nested_elements": 4,
    }]


def test_private_sequence_is_a_payload_and_its_items_have_independent_ownership():
    dataset = Dataset()
    dataset.add_new((0x0029, 0x0010), "LO", "OUTER")
    child = _private(Dataset(), creator="INNER")
    orphan = _private(Dataset(), creator=None)
    dataset.add_new((0x0029, 0x1010), "SQ", [child, orphan])
    record = _normalize(dataset)
    summary = summarize_vendors([record])
    assert summary["creator_elements"] == 2
    assert summary["private_elements"] == 3
    assert summary["unassigned_private_elements"] == 1
    assert _block(summary, creator="OUTER")["elements"] == 1
    assert _block(summary, creator="OUTER")["nested_elements"] == 0
    assert _block(summary, creator="INNER")["nested_elements"] == 1
    assert _block(summary, creator=None, state="absent")["nested_elements"] == 1
    assert {tag.dataset_path for tag in record.tags.values() if tag.tag == "(0029,1001)"} == {
        ("(0029,1010)[0]",), ("(0029,1010)[1]",),
    }
    assert "PAYLOAD_SECRET" not in json.dumps(summary)


def test_different_groups_and_nonconsecutive_slots_do_not_collide():
    dataset = _private(Dataset(), creator="FIRST", slot=0x10)
    _private(dataset, creator="LAST", slot=0xFF)
    _private(dataset, creator="OTHER_GROUP", slot=0x10, group=0x0019)
    summary = summarize_vendors([_normalize(dataset)])
    assert [(row["group"], row["block"], row["creator"]) for row in summary["private_blocks"]] == [
        ("0019", "10", "OTHER_GROUP"), ("0029", "10", "FIRST"), ("0029", "FF", "LAST"),
    ]
    assert summary["unassigned_private_elements"] == 0


@pytest.mark.parametrize("creator", [None, "", "  "])
def test_present_empty_creator_is_distinct_from_absent_reservation(creator):
    summary = summarize_vendors([_record(
        _tag("(0029,0010)", creator), _tag("(0029,1001)", "PAYLOAD_SECRET"),
    )])
    row = _block(summary, creator=None, state="empty")
    assert row["elements"] == 1
    assert summary["unassigned_private_elements"] == 1
    assert summary["creator_elements"] == 1


@pytest.mark.parametrize("value,vr", [
    ("ACME", "SH"), (b"BINARY_CREATOR_SECRET", "OB"), (12, "UL"),
    (["ACME", "OTHER"], "LO"), ("first\\second", "LO"),
    ("a" * 65, "LO"), ("non-ASCII-\u00e9", "LO"), ("control\ncharacter", "LO"),
])
def test_invalid_creator_cannot_assign_payload_ownership(value, vr):
    summary = summarize_vendors([_record(
        _tag("(0029,0010)", value, vr=vr), _tag("(0029,1001)", "PAYLOAD_SECRET"),
    )])
    row = summary["private_blocks"][0]
    assert row["creator_state"] == "invalid"
    assert row["creator"] == (value if isinstance(value, str) else None)
    assert summary["unassigned_private_elements"] == 1
    assert "SECRET" not in json.dumps(summary)


def test_nonblank_creator_whitespace_is_preserved():
    summary = summarize_vendors([_record(_tag("(0029,0010)", " ACME "))])
    assert summary["private_blocks"][0]["creator"] == " ACME "
    assert summary["private_blocks"][0]["creator_state"] == "present"


@pytest.mark.parametrize("group", ["0001", "0003", "0005", "0007", "FFFF"])
def test_forbidden_private_groups_do_not_get_valid_ownership(group):
    summary = summarize_vendors([_record(
        _tag(f"({group},0010)", "ACME"), _tag(f"({group},1001)", "PAYLOAD_SECRET"),
    )])
    row = summary["private_blocks"][0]
    assert row["group"] == group and row["creator_state"] == "invalid"
    assert summary["unassigned_private_elements"] == 1


def test_reserved_low_element_numbers_and_retired_group_length_are_unassigned():
    summary = summarize_vendors([_record(
        _tag("(0029,0000)", 128, vr="UL"),
        _tag("(0029,0001)", "PAYLOAD_SECRET"),
        _tag("(0029,0100)", "PAYLOAD_SECRET"),
        _tag("(0029,0FFF)", "PAYLOAD_SECRET"),
    )])
    assert summary["private_blocks"] == [{
        "group": "0029", "block": "unassigned", "creator": None, "creator_state": "invalid",
        "files": 1, "occurrences": 1, "elements": 4, "nested_elements": 0,
    }]
    assert summary["private_elements"] == summary["unassigned_private_elements"] == 4
    assert summary["creator_elements"] == 0


def test_order_and_record_boundaries_do_not_change_ownership():
    record = _record(_tag("(0029,1001)", "PAYLOAD_SECRET"), _tag("(0029,0010)", "ACME"))
    orphan = _record(_tag("(0029,1001)", "OTHER_PAYLOAD_SECRET"))
    summary = summarize_vendors([record, orphan])
    assert summary["files"] == 2
    assert _block(summary, creator="ACME")["files"] == 1
    assert _block(summary, creator=None, state="absent")["files"] == 1
    assert summary["unassigned_private_elements"] == 1
    assert summarize_vendors([orphan, replace(record, tags=dict(reversed(list(record.tags.items()))))]) == summary


def test_private_payload_values_are_not_even_stringified():
    class Payload:
        def __str__(self):
            raise AssertionError("Private payload must never be serialized")

    summary = summarize_vendors([_record(_tag("(0029,1001)", Payload()))])
    assert summary["private_elements"] == 1
    assert summary["unassigned_private_elements"] == 1
    assert json.dumps(summary)


@pytest.mark.parametrize("keyword,number,vr", [
    ("PixelData", (0x7FE0, 0x0010), "OB"),
    ("FloatPixelData", (0x7FE0, 0x0008), "OF"),
    ("DoubleFloatPixelData", (0x7FE0, 0x0009), "OD"),
])
def test_recursive_normalizer_excludes_pixel_payloads_even_in_sequence_items(keyword, number, vr):
    dataset = Dataset()
    dataset.add_new(number, vr, b"PIXEL_PAYLOAD_SECRET")
    child = Dataset()
    child.add_new(number, vr, b"NESTED_PIXEL_PAYLOAD_SECRET")
    dataset.RequestAttributesSequence = [child]
    record = _normalize(dataset)
    assert all(tag.keyword != keyword for tag in record.tags.values())
    assert "PIXEL_PAYLOAD_SECRET" not in json.dumps(summarize_vendors([record]))
