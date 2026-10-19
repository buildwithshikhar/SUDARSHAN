"""The YAML form of scenario.v1: deterministic writing, exact round trips, errors with lines."""

from pathlib import Path
from typing import Any

import pytest
import yaml

from app.contracts.loader import load_pack
from app.contracts.paths import packs_root
from app.contracts.scenario import ScenarioSpec
from app.scenarios.language import (
    HEADER,
    KEY_ORDER,
    LineMap,
    ScenarioTextError,
    load_text,
    to_yaml,
    validate_text,
)

SCENARIOS = sorted((packs_root() / "scenarios").glob("*.v1.*"))


def pack_spec(name: str = "kestrel-dawn-approach") -> ScenarioSpec:
    spec = load_pack(packs_root() / "scenarios" / f"{name}.v1.json")
    assert isinstance(spec, ScenarioSpec)
    return spec


def base_text() -> str:
    return to_yaml(pack_spec())


def line_of(text: str, needle: str, nth: int = 0) -> int:
    """1-based line of the nth line containing `needle`."""
    hits = [i + 1 for i, line in enumerate(text.splitlines()) if needle in line]
    return hits[nth]


def variant(**changes: Any) -> str:
    data = pack_spec().model_dump(mode="json")
    data.update(changes)
    return to_yaml(ScenarioSpec.model_validate(data))


# ---------------------------------------------------------------------------------- writing
@pytest.mark.parametrize("path", SCENARIOS, ids=lambda p: p.name)
def test_every_pack_scenario_round_trips(path: Path) -> None:
    spec = load_pack(path)
    assert isinstance(spec, ScenarioSpec)
    text = to_yaml(spec)
    assert load_text(text) == spec
    assert to_yaml(load_text(text)) == text


def test_layout_header_order_and_unicode() -> None:
    text = base_text()
    assert text.startswith(HEADER)
    assert HEADER == "# Fictional scenario \u00b7 open-source parameters\n"
    keys = [k for k in yaml.safe_load(text)]
    assert keys == [k for k in KEY_ORDER if k in keys]
    assert keys[:3] == ["contract", "id", "version"]
    assert "\\u" not in text and "केस्ट्रल" in text
    assert text.endswith("\n") and "\t" not in text


def test_absent_and_empty_fields_are_left_out() -> None:
    bare = pack_spec().model_copy(update={"meta": None})
    text = to_yaml(bare)
    for absent in ("meta:", "degradations:", "groups:", "motion:", "null", "[]", "leader"):
        assert absent not in text


def test_meta_and_degradations_are_written_in_place() -> None:
    meta = {"origin": "scripted", "curriculum_order": 3, "tags": ["night"], "difficulty": 30}
    sensor = pack_spec().sensors[0].id
    degr = [{"sensor": sensor, "kind": "outage", "from_s": 20, "to_s": 40}]
    text = variant(meta=meta, degradations=degr)
    keys = list(yaml.safe_load(text))
    assert keys.index("meta") == keys.index("duration_s") + 1
    assert keys.index("degradations") == keys.index("sensors") + 1
    assert keys.index("threats") == keys.index("degradations") + 1
    again = load_text(text)
    assert again.meta is not None and again.meta.curriculum_order == 3
    assert to_yaml(again) == text


def test_writing_is_deterministic() -> None:
    assert to_yaml(pack_spec()) == to_yaml(pack_spec()) == base_text()


def test_no_aliases_even_for_equal_values() -> None:
    assert "&id" not in base_text() and "*id" not in base_text()


# ------------------------------------------------------------------------------------ lines
def test_line_map_positions() -> None:
    text = base_text()
    lines = LineMap.from_text(text)
    assert lines
    assert lines.lookup(("id",)) == (line_of(text, "id: kestrel-dawn-approach"), 5)
    assert lines.lookup(("threats",))[0] == line_of(text, "threats:")
    first = lines.lookup(("threats", 0))
    assert first[0] == line_of(text, "threats:") + 1
    assert text.splitlines()[first[0] - 1].strip().startswith("- id:")
    spawn = lines.lookup(("threats", 1, "spawn_s"))
    assert text.splitlines()[spawn[0] - 1].strip().startswith("spawn_s:")
    assert spawn[1] == text.splitlines()[spawn[0] - 1].index(":") + 3
    deep = lines.lookup(("threats", 0, "route", 1, "position", "x"))
    assert text.splitlines()[deep[0] - 1].strip().startswith("x:")


def test_line_map_falls_back_to_the_deepest_ancestor() -> None:
    text = base_text()
    lines = LineMap.from_text(text)
    parent = lines.lookup(("threats", 0))
    assert lines.lookup(("threats", 0, "no_such_field")) == parent
    assert lines.lookup(("threats", 0, "no_such_field", "deeper")) == parent
    assert lines.lookup(("threats", 99)) == lines.lookup(("threats",))
    assert lines.lookup(("threats", True)) == lines.lookup(("threats",))
    assert lines.lookup(("id", "scalar-has-no-children")) == lines.lookup(("id",))
    assert lines.lookup(("nothing",)) == (1, 1)
    assert lines.lookup(()) == (1, 1)


def test_line_map_skips_a_union_tag() -> None:
    lines = LineMap.from_text(base_text())
    assert lines.lookup(("world", "terrain", "flat", "kind")) == lines.lookup(
        ("world", "terrain", "kind")
    )


def test_empty_line_map() -> None:
    for lines in (LineMap(), LineMap.from_text(""), LineMap.from_text("a: [1, 2")):
        assert not lines
        assert lines.lookup(("threats", 0, "spawn_s")) == (1, 1)
        assert lines.lookup(()) == (1, 1)


def test_line_map_handles_non_scalar_keys() -> None:
    lines = LineMap.from_text("? [a, b]\n: 1\nok: 2\n")
    assert lines.lookup(("ok",)) == (3, 5)


# ------------------------------------------------------------------------------- validation
def test_valid_text() -> None:
    result = validate_text(base_text())
    assert result.valid and result.errors == [] and result.spec == pack_spec()
    assert result.lines


def test_yaml_syntax_error_has_position() -> None:
    text = "contract: scenario.v1\nid: [unclosed\nversion: 1.0.0\n"
    result = validate_text(text)
    assert not result.valid and result.spec is None and not result.lines
    (error,) = result.errors
    assert error.code == "yaml.syntax" and error.line >= 2 and error.column >= 1
    assert error.message.startswith("YAML syntax")


def test_syntax_error_without_a_mark() -> None:
    (error,) = validate_text("a: 1\n---\nb: 2\n").errors
    assert error.code == "yaml.syntax" and (error.line, error.column) >= (1, 1)


def test_constructor_error_is_a_syntax_error() -> None:
    text = "contract: !!python/object:os.system x\n"
    (error,) = validate_text(text).errors
    assert error.code == "yaml.syntax" and error.line == 1


def test_duplicate_keys_report_the_repeat() -> None:
    text = base_text()
    lines = text.splitlines()
    at = line_of(text, "default_seed:")
    lines.insert(at, "default_seed: 5")
    text = "\n".join(lines) + "\n"
    result = validate_text(text)
    assert not result.valid and result.spec is None
    (error,) = result.errors
    assert (error.code, error.line) == ("yaml.duplicate-key", at + 1)
    assert "'default_seed'" in error.message


def test_duplicate_keys_nested_and_sorted() -> None:
    text = (
        "contract: scenario.v1\nworld:\n  a: 1\n  a: 2\n  b: 1\n  b: 3\nlist:\n  - x: 1\n    x: 2\n"
    )
    errors = validate_text(text).errors
    assert [(e.code, e.line) for e in errors] == [("yaml.duplicate-key", n) for n in (4, 6, 9)]


def test_keys_that_are_equal_once_loaded_count_as_repeats() -> None:
    (error,) = validate_text("1: a\ntrue: b\n").errors
    assert error.code == "yaml.duplicate-key" and error.line == 2


def test_loader_repeat_without_a_line_in_the_message() -> None:
    from app.contracts.loader import PackError
    from app.scenarios import language

    assert language._loader_repeat(PackError("duplicate key 'k'")).line == 1


def test_a_list_cannot_be_a_key() -> None:
    (error,) = validate_text("? [a, b]\n: 1\n").errors
    assert (error.code, error.line) == ("yaml.syntax", 1)


def test_recursive_alias_does_not_hang() -> None:
    result = validate_text("a: &x\n  - *x\n")
    assert not result.valid


@pytest.mark.parametrize("text", ["", "# only a comment\n", "   \n"])
def test_empty_document(text: str) -> None:
    (error,) = validate_text(text).errors
    assert (error.code, error.line, error.column) == ("yaml.not-a-mapping", 1, 1)


@pytest.mark.parametrize("text", ["- a\n- b\n", "just text\n", "42\n"])
def test_non_mapping_document(text: str) -> None:
    (error,) = validate_text(text).errors
    assert error.code == "yaml.not-a-mapping" and error.line == 1


def test_unknown_contract_points_at_the_contract_line() -> None:
    text = base_text().replace("contract: scenario.v1", "contract: scenario.v9")
    (error,) = validate_text(text).errors
    assert (error.code, error.path, error.line) == ("contract.unknown", "contract", 2)
    assert "scenario.v9" in error.message


def test_missing_contract() -> None:
    (error,) = validate_text("id: x\n").errors
    assert error.code == "contract.unknown" and (error.line, error.column) == (1, 1)


def test_schema_error_names_the_line_of_the_value() -> None:
    text = base_text()
    n = next(
        i + 1
        for i, line in enumerate(text.splitlines())
        if line.strip().startswith("speed_mps:") and i + 1 > line_of(text, "route:")
    )
    broken = "\n".join(
        line.split(":")[0] + ": -3.5" if i + 1 == n else line
        for i, line in enumerate(text.splitlines())
    )
    result = validate_text(broken + "\n")
    assert not result.valid and result.spec is None
    (error,) = result.errors
    assert error.line == n and error.code == "schema.greater_than"
    assert error.path.startswith("threats.") and error.path.endswith(".speed_mps")
    assert "route" in error.path
    assert error.column == broken.splitlines()[n - 1].index(": -3.5") + 3


def test_schema_errors_are_collected_and_ordered() -> None:
    text = (
        base_text()
        .replace("duration_s: 420.0", "duration_s: -1")
        .replace("fictional: true", "fictional: false")
    )
    errors = validate_text(text).errors
    assert [e.path for e in errors] == ["fictional", "duration_s"]
    assert [e.line for e in errors] == sorted(e.line for e in errors)
    assert {e.code for e in errors} == {"schema.literal_error", "schema.greater_than"}


def test_missing_and_extra_fields_point_at_the_parent() -> None:
    text = base_text().replace("summary:", "sumary:")
    errors = validate_text(text).errors
    assert {e.code for e in errors} == {"schema.missing", "schema.extra_forbidden"}
    extra = next(e for e in errors if e.code == "schema.extra_forbidden")
    assert extra.line == line_of(text, "sumary:")


def test_whole_document_rule_points_at_the_named_threat() -> None:
    data = pack_spec().model_dump(mode="json")
    data["duration_s"] = 5.0  # threats spawn after the scenario ends
    text = yaml.safe_dump(data, sort_keys=False)
    result = validate_text(text)
    assert not result.valid
    error = next(e for e in result.errors if "spawns after" in e.message)
    assert error.code == "schema.value_error" and error.path.startswith("threats.")
    assert not error.message.startswith("Value error")
    assert text.splitlines()[error.line - 1].strip().startswith(("- id:", "id:"))


def test_whole_document_rule_without_a_known_owner_points_at_the_top() -> None:
    data = pack_spec().model_dump(mode="json")
    data["zones"] = [data["zones"][0], data["zones"][0]]
    result = validate_text(yaml.safe_dump(data, sort_keys=False))
    (error,) = result.errors
    assert error.path == "" and (error.line, error.column) == (1, 1)
    assert "duplicate zone" in error.message


def test_owner_hint_for_other_kinds_and_for_a_non_list() -> None:
    from app.scenarios.language import _owner_path

    data: dict[str, Any] = {"groups": [{"id": "g-1"}, "stray"], "zones": 5}
    assert _owner_path("group g-1: a leader-follower group needs a leader", data) == ("groups", 0)
    assert _owner_path("zone z-1: bad", data) == ()
    assert _owner_path("group g-2: bad", data) == ()
    assert _owner_path("nothing named here", data) == ()


# ------------------------------------------------------------------------------------- load
def test_load_text_returns_the_spec_or_raises_with_every_error() -> None:
    assert load_text(base_text()) == pack_spec()
    broken = base_text().replace("duration_s: 420.0", "duration_s: -1")
    with pytest.raises(ScenarioTextError) as raised:
        load_text(broken)
    assert raised.value.errors[0].line == line_of(broken, "duration_s")
    assert f"line {raised.value.errors[0].line}" in str(raised.value)
    assert isinstance(raised.value, ValueError)


def test_messages_never_overclaim() -> None:
    texts = ["", "- a", "a: [", "contract: scenario.v9\n", base_text().replace("true", "7")]
    for text in texts:
        for error in validate_text(text).errors:
            assert "provably" not in error.message.lower()
            assert "guaranteed" not in error.message.lower()


def test_validate_text_never_raises_on_odd_input() -> None:
    for text in [
        "\x00",
        "a: !!binary |\n  ???",
        "{{{{",
        "? ? ?",
        "a:\n\t- b",
        "%YAML 9.9\n---\na: 1",
    ]:
        result = validate_text(text)
        assert not result.valid and result.errors
