from dataclasses import FrozenInstanceError, asdict
from hashlib import sha256
from pathlib import Path

from pydicom.dataset import Dataset
from pydicom.multival import MultiValue
from pydicom.valuerep import DSfloat, PersonName
import pytest
import yaml

from dicomqc.model.metadata import DicomTag, MetadataRecord, ValueState, value_state
from dicomqc.model.results import Severity
from dicomqc.rules.policy import Policy, PolicyRule, evaluate_policy, load_policy


_DEFAULT = object()


def _load(tmp_path, rules=_DEFAULT, **changes):
    document = {
        "version": 1,
        "id": "project-review",
        "rules": rules if rules is not _DEFAULT else [
            {"id": "identity", "keyword": "PatientIdentityRemoved", "check": "allowed_values", "values": ["YES"]}
        ],
    }
    document.update(changes)
    path = tmp_path / "policy.yaml"
    path.write_text(yaml.safe_dump(document), encoding="utf-8")
    return load_policy(path)


def _rule(check="nonempty", **changes):
    result = {"id": "patient-id", "keyword": "PatientID", "check": check}
    result.update(changes)
    return result


def _tag(value, *, keyword="PatientID", nested=False, vr="LO"):
    return DicomTag(
        tag="(0010,0020)", keyword=keyword, vr=vr, is_private=False,
        value_state=value_state(value), raw_value=value, is_nested=nested,
    )


def _record(*tags):
    return MetadataRecord(
        path=Path("candidate/image.dcm"), patient_id=None, study_uid=None,
        series_uid=None, manufacturer=None, modality=None,
        tags={str(index): tag for index, tag in enumerate(tags)},
    )


def test_load_policy_defaults_and_digest(tmp_path):
    policy = _load(tmp_path)
    assert policy.id == "project-review"
    assert policy.rules == (PolicyRule(
        id="identity", keyword="PatientIdentityRemoved", check="allowed_values", values=("YES",),
    ),)
    assert policy.sha256 == sha256((tmp_path / "policy.yaml").read_bytes()).hexdigest()
    with pytest.raises(FrozenInstanceError):
        policy.id = "changed"
    with pytest.raises(FrozenInstanceError):
        policy.rules[0].scope = "top_level"
    changed = _load(tmp_path, id="different-id")
    assert changed.sha256 != policy.sha256


@pytest.mark.parametrize("severity", ["error", "warning", "info"])
def test_policy_findings_identify_rule_and_scope_without_values(tmp_path, severity):
    policy = _load(tmp_path, [_rule("matches", pattern="secret-[0-9]", severity=severity, scope="top_level")])
    findings = evaluate_policy(_record(_tag("Smith^Jane")), policy)
    assert len(findings) == 1
    finding = findings[0]
    assert finding.rule_id == "policy.project-review.patient-id"
    assert finding.profile_id == "policy.project-review"
    assert finding.severity == Severity(severity)
    assert finding.path == "candidate/image.dcm"
    assert finding.keyword == "PatientID"
    assert finding.tag == "(0010,0020)"
    assert finding.value_state == ValueState.PRESENT
    output = str(asdict(finding))
    assert "Smith" not in output and "Jane" not in output and "secret" not in output


@pytest.mark.parametrize("check,options", [
    ("absent_or_empty", {}), ("nonempty", {}),
    ("allowed_values", {"values": ["sub-001"]}), ("matches", {"pattern": "sub-???"}),
])
@pytest.mark.parametrize("value", [None, "", "  ", [], [""], [None]])
def test_empty_values_and_missing_fields(tmp_path, check, options, value):
    policy = _load(tmp_path, [_rule(check, **options)])
    findings = evaluate_policy(_record(_tag(value)), policy)
    missing = evaluate_policy(_record(), policy)
    if check == "absent_or_empty":
        assert findings == missing == []
    else:
        assert len(findings) == len(missing) == 1
        assert missing[0].value_state == ValueState.ABSENT
        assert missing[0].tag == "(0010,0020)"


@pytest.mark.parametrize("check,options,passing,failing", [
    ("absent_or_empty", {}, None, "sub-001"),
    ("nonempty", {}, "sub-001", None),
    ("allowed_values", {"values": ["sub-001", "sub-002"]}, "sub-001", "sub-003"),
    ("matches", {"pattern": "sub-[0-9][0-9][0-9]"}, "sub-012", "sub-ABC"),
])
def test_each_check_has_passing_and_failing_results(tmp_path, check, options, passing, failing):
    policy = _load(tmp_path, [_rule(check, **options)])
    assert evaluate_policy(_record(_tag(passing)), policy) == []
    findings = evaluate_policy(_record(_tag(failing)), policy)
    assert len(findings) == 1
    assert findings[0].message and findings[0].recommendation


@pytest.mark.parametrize("value,passes", [
    ("sub-001", True), ("SUB-001", False), ("prefix-sub-001", False),
    ("sub-001-suffix", False), ("sub-001 ", False), (" sub-001", False),
    ("sub-AB1", False),
])
def test_globs_are_case_sensitive_full_string_matches(tmp_path, value, passes):
    policy = _load(tmp_path, [_rule("matches", pattern="sub-[0-9][0-9][0-9]")])
    assert (evaluate_policy(_record(_tag(value)), policy) == []) is passes


def test_pattern_is_not_a_regular_expression(tmp_path):
    policy = _load(tmp_path, [_rule("matches", pattern="^sub-[0-9]+$")])
    assert len(evaluate_policy(_record(_tag("sub-001")), policy)) == 1
    assert evaluate_policy(_record(_tag("^sub-1+$")), policy) == []


@pytest.mark.parametrize("check,options", [
    ("nonempty", {}), ("allowed_values", {"values": ["sub-001", "sub-002"]}),
    ("matches", {"pattern": "sub-00[12]"}),
])
def test_multivalues_require_every_component_to_pass(tmp_path, check, options):
    policy = _load(tmp_path, [_rule(check, **options)])
    assert evaluate_policy(_record(_tag(MultiValue(str, ["sub-001", "sub-002"]))), policy) == []
    assert len(evaluate_policy(_record(_tag(MultiValue(str, ["sub-001", ""]))), policy)) == 1
    if check != "nonempty":
        assert len(evaluate_policy(_record(_tag(MultiValue(str, ["sub-001", "other"]))), policy)) == 1


def test_absent_or_empty_requires_every_component_empty(tmp_path):
    policy = _load(tmp_path, [_rule("absent_or_empty")])
    assert evaluate_policy(_record(_tag(["", None])), policy) == []
    assert len(evaluate_policy(_record(_tag(["", "populated"])), policy)) == 1


@pytest.mark.parametrize("value,text", [(512, "512"), (0, "0"), (DSfloat("1.25"), "1.25"), (PersonName("sub-001"), "sub-001")])
def test_scalar_values_are_compared_as_strings(tmp_path, value, text):
    policy = _load(tmp_path, [_rule("allowed_values", values=[text])])
    assert evaluate_policy(_record(_tag(value)), policy) == []


def test_top_level_does_not_accept_a_nested_required_marker(tmp_path):
    rule = _rule("allowed_values", keyword="PatientIdentityRemoved", values=["YES"], scope="top_level")
    policy = _load(tmp_path, [rule])
    findings = evaluate_policy(_record(_tag("YES", keyword="PatientIdentityRemoved", nested=True)), policy)
    assert len(findings) == 1 and findings[0].value_state == ValueState.ABSENT
    assert findings[0].tag == "(0012,0062)"
    assert evaluate_policy(_record(
        _tag("YES", keyword="PatientIdentityRemoved"),
        _tag("NO", keyword="PatientIdentityRemoved", nested=True),
    ), policy) == []


def test_all_scope_checks_every_repeated_occurrence(tmp_path):
    policy = _load(tmp_path, [_rule("allowed_values", values=["sub-001"])])
    findings = evaluate_policy(_record(
        _tag("sub-001"), _tag("unexpected", nested=True), _tag("unexpected-again", nested=True),
    ), policy)
    assert len(findings) == 2
    nested_only = evaluate_policy(_record(_tag("sub-001", nested=True)), policy)
    assert nested_only == []


@pytest.mark.parametrize("check", ["nonempty", "absent_or_empty"])
@pytest.mark.parametrize("value,present", [([], False), ([Dataset()], True)])
def test_sequence_presence_only_checks_sequence_occupancy(tmp_path, check, value, present):
    policy = _load(tmp_path, [_rule(check, keyword="DeidentificationMethodCodeSequence")])
    findings = evaluate_policy(_record(_tag(value, keyword="DeidentificationMethodCodeSequence", vr="SQ")), policy)
    assert bool(findings) is (present if check == "absent_or_empty" else not present)


@pytest.mark.parametrize("field,value", [
    ("version", "1"), ("version", True), ("version", 1.0), ("version", 2),
    ("id", "UpperCase"), ("id", "../secret"), ("id", "a" * 65),
    ("id", "bad--slug"), ("id", "-slug"), ("id", "slug-"),
    ("id", ""), ("id", None), ("id", 12), ("id", ["slug"]),
    ("rules", []), ("rules", {}), ("rules", "not-a-list"), ("rules", None),
    ("unknown", "secret"),
])
def test_invalid_top_level_fields(tmp_path, field, value):
    with pytest.raises(ValueError):
        _load(tmp_path, **{field: value})


@pytest.mark.parametrize("document", [None, [], "text", 42, {"id": "only-id"}])
def test_invalid_top_level_documents(tmp_path, document):
    path = tmp_path / "policy.yaml"
    path.write_text(yaml.safe_dump(document), encoding="utf-8")
    with pytest.raises(ValueError, match="exactly version, id and rules"):
        load_policy(path)


@pytest.mark.parametrize("rule", [
    None, [], "text", {}, {"id": "x"},
    _rule(id="Bad"), _rule(id=True), _rule(id="a" * 65),
    _rule(keyword="NotADicomKeyword"), _rule(keyword="PixelData"),
    _rule(keyword="FloatPixelData"), _rule(keyword="DoubleFloatPixelData"),
    _rule(keyword="EncapsulatedDocument"), _rule(keyword="WaveformData"),
    _rule(keyword="PatientName "), _rule(keyword=12), _rule(keyword=[]),
    _rule(check="unknown"), _rule(check=[]), _rule(check=True),
    _rule(severity="critical"), _rule(severity=[]), _rule(severity=True),
    _rule(scope="nested"), _rule(scope=[]), _rule(scope=True),
    _rule(message="private patient name"), _rule(recommendation="secret"),
    _rule(values=[]), _rule(pattern="*"),
    _rule("allowed_values"), _rule("allowed_values", values=[]),
    _rule("allowed_values", values="YES"), _rule("allowed_values", values=[True]),
    _rule("allowed_values", values=[1]), _rule("allowed_values", values=[None]),
    _rule("allowed_values", values=[""]), _rule("allowed_values", values=[" "]),
    _rule("allowed_values", values=["YES"], pattern="*"),
    _rule("allowed_values", values=["YES"], keyword="SourceImageSequence"),
    _rule("matches"), _rule("matches", pattern=""), _rule("matches", pattern="  "),
    _rule("matches", pattern=42), _rule("matches", pattern=["*"]),
    _rule("matches", pattern="*", values=[]),
    _rule("matches", pattern="*", keyword="DeidentificationMethodCodeSequence"),
])
def test_invalid_rules(tmp_path, rule):
    with pytest.raises(ValueError):
        _load(tmp_path, [rule])


def test_duplicate_rule_ids_rejected(tmp_path):
    with pytest.raises(ValueError, match="IDs must be unique"):
        _load(tmp_path, [_rule(), _rule(keyword="PatientName")])


@pytest.mark.parametrize("source", [
    "version: 1\nid: secret\nid: duplicate\nrules: []\n",
    "version: 1\nid: secret\nrules: [{id: x, id: y, keyword: PatientID, check: nonempty}]\n",
    "version: 1\nid: secret\nrules: []\n1: bad-key\n",
    "version: 1\nid: &secret secret\nrules: []\n",
    "version: 1\nid: *secret\nrules: []\n",
    "!!python/object/apply:os.system ['secret-command']",
    "version: !!int 1\nid: secret\nrules: []\n",
    "version: 1\nid: secret\nrules: [\n",
    "version: 1\nid: secret\nrules: []\n---\nsecret: document\n",
    "version: 1\nid: secret\nrules: [{id: x, keyword: PatientIdentityRemoved, check: allowed_values, values: [YES]}]",
    "version: 1\nid: secret\nrules: []\nsecret: " + "[" * 100 + "0" + "]" * 100,
])
def test_hostile_yaml_is_rejected_without_echoing_contents(tmp_path, source):
    path = tmp_path / "sensitive-policy.yaml"
    path.write_text(source, encoding="utf-8")
    with pytest.raises(ValueError) as caught:
        load_policy(path)
    assert "secret" not in str(caught.value)
    assert "sensitive-policy" not in str(caught.value)
    assert "Patient" not in str(caught.value)


def test_invalid_utf8_has_generic_error(tmp_path):
    path = tmp_path / "private-person.yaml"
    path.write_bytes(b"\xff\x80 patient-name")
    with pytest.raises(ValueError, match="valid UTF-8 YAML") as caught:
        load_policy(path)
    assert "patient-name" not in str(caught.value)


def test_policy_size_limit(tmp_path):
    path = tmp_path / "policy.yaml"
    path.write_bytes(b"#" * (64 * 1024 + 1))
    with pytest.raises(ValueError, match="64 KiB"):
        load_policy(path)


def test_policy_rule_count_limit(tmp_path):
    with pytest.raises(ValueError, match="1 to 100 rules"):
        _load(tmp_path, [_rule(id=f"rule-{n}") for n in range(101)])
    assert len(_load(tmp_path, [_rule(id=f"rule-{n}") for n in range(100)]).rules) == 100


def test_policy_value_count_limit(tmp_path):
    with pytest.raises(ValueError, match="1 to 100 nonempty"):
        _load(tmp_path, [_rule("allowed_values", values=[str(n) for n in range(101)])])
    assert len(_load(tmp_path, [_rule("allowed_values", values=[str(n) for n in range(100)])]).rules[0].values) == 100


def test_policy_string_limit(tmp_path):
    with pytest.raises(ValueError, match="256 characters"):
        _load(tmp_path, [_rule("matches", pattern="a" * 257)])
    assert _load(tmp_path, [_rule("matches", pattern="a" * 256)]).rules[0].pattern == "a" * 256


def test_missing_or_nonregular_policy_input(tmp_path):
    for path in [tmp_path / "missing.yaml", tmp_path]:
        with pytest.raises(ValueError, match="readable regular file"):
            load_policy(path)


def test_policy_read_error_is_generic(tmp_path, monkeypatch):
    path = tmp_path / "private-name.yaml"
    path.write_text("version: 1", encoding="utf-8")

    def denied(*args, **kwargs):
        raise OSError("private-name.yaml has a sensitive path")

    monkeypatch.setattr(Path, "open", denied)
    with pytest.raises(ValueError, match="Unable to read policy file") as caught:
        load_policy(path)
    assert "private-name" not in str(caught.value)


def test_configured_values_are_not_in_findings(tmp_path):
    policy = _load(tmp_path, [_rule("allowed_values", values=["allowed-secret"])])
    rendered = str([asdict(item) for item in evaluate_policy(_record(_tag("observed-secret")), policy)])
    assert "allowed-secret" not in rendered and "observed-secret" not in rendered


def test_independent_policy_rules_are_all_evaluated(tmp_path):
    policy = _load(tmp_path, [
        _rule("nonempty"),
        _rule("absent_or_empty", id="comments", keyword="PatientComments", severity="warning"),
    ])
    findings = evaluate_policy(_record(_tag("sensitive comment", keyword="PatientComments")), policy)
    assert [item.keyword for item in findings] == ["PatientID", "PatientComments"]
    assert [item.severity for item in findings] == [Severity.ERROR, Severity.WARNING]


def test_policy_dataclass_is_usable_for_valid_programmatic_rules():
    policy = Policy("programmatic", (PolicyRule("patient-id", "PatientID", "nonempty"),), "digest")
    assert evaluate_policy(_record(_tag("sub-001")), policy) == []
