"""Contracts: examples validate, malformed inputs are rejected, schemas match the models."""

import copy
import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import jsonschema
import pytest
from pydantic import ValidationError

from app.contracts import PACKS, SCHEMAS, ActionRecord, EventRecord, SessionRecord
from app.contracts.export import SCHEMA_DIR, main, render, stale, write
from app.contracts.loader import PackError, load_pack, parse_text

REPO = Path(__file__).resolve().parents[3]
PACK_FILES = sorted(p for p in (REPO / "packs").rglob("*.v1.*") if "schemas" not in p.parts)
SCENARIO = REPO / "packs" / "scenarios" / "kestrel-dawn-approach.v1.json"
RULEPACK = REPO / "packs" / "rule-packs" / "training-baseline.v1.yaml"
PROFILE = REPO / "packs" / "sensor-profiles" / "radar-generic-s.v1.yaml"
HASH = "a" * 64


def raw(path: Path) -> dict[str, Any]:
    data = parse_text(path.read_text(encoding="utf-8"), path.suffix)
    assert isinstance(data, dict)
    return data


def schema(name: str) -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads((SCHEMA_DIR / f"{name}.json").read_text("utf-8"))
    return loaded


def event(**changes: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "seq": 0,
        "t": 0.0,
        "type": "session.start",
        "actor": "sim",
        "payload": {},
        "prev_hash": "0" * 64,
        "hash": HASH,
    }
    return base | changes


# ---------------------------------------------------------------------------- examples


def test_there_is_one_example_of_each_pack_contract() -> None:
    """One example per contract, except sensor profiles (wave 4a ships one per modality model)
    and scenarios (wave 5 adds the playable Harrier Field scenario to the Kestrel example; wave 7
    adds Heron Ridge, the first on a terrain pack; wave 9a adds the twelve curriculum scenarios)."""
    contracts = sorted(raw(p)["contract"] for p in PACK_FILES)
    assert sorted(set(contracts)) == sorted(PACKS)
    for contract in PACKS:
        if contract not in ("sensor-profile.v1", "scenario.v1", "threat-class.v1"):
            assert contracts.count(contract) == 1
    assert sorted(raw(p)["id"] for p in PACK_FILES if raw(p)["contract"] == "scenario.v1") == [
        "curriculum-01-first-contact",
        "curriculum-02-town-traffic",
        "curriculum-03-dusk-watch",
        "curriculum-04-night-watch",
        "curriculum-05-silent-approach",
        "curriculum-06-sensor-outage",
        "curriculum-07-blind-sector",
        "curriculum-08-small-swarm",
        "curriculum-09-decoy-swarm",
        "curriculum-10-fast-mover",
        "curriculum-11-fixed-wing-clutter",
        "curriculum-12-night-swarm-capstone",
        "harrier-morning-watch",
        "heron-ridge-low-approach",
        "kestrel-dawn-approach",
    ]


@pytest.mark.parametrize("path", PACK_FILES, ids=lambda p: p.name)
def test_examples_validate_against_models_and_exported_schemas(path: Path) -> None:
    data = raw(path)
    model = load_pack(path)
    assert model.fictional is True
    jsonschema.validate(data, schema(data["contract"]))
    # round trip: dumping and re-validating gives the same model
    assert type(model).model_validate(model.model_dump(mode="json")) == model


@pytest.mark.parametrize("path", PACK_FILES, ids=lambda p: p.name)
def test_every_source_id_is_in_the_data_register(path: Path) -> None:
    register = (REPO / "docs" / "DATA_REGISTER.md").read_text(encoding="utf-8")
    known = set(re.findall(r"^\| ([DGWXF][0-9]{2}) \|", register, flags=re.MULTILINE))
    used = set(re.findall(r'source_id"?: "?([A-Z][0-9]{2})', path.read_text(encoding="utf-8")))
    assert used <= known, f"unregistered source IDs: {sorted(used - known)}"


def test_event_action_and_session_records_validate() -> None:
    record = EventRecord.model_validate(event())
    action = ActionRecord(tick=40, actor="trainee:op-1", action="designate", payload={"x": 1})
    session = SessionRecord.model_validate(
        {
            "contract": "session-record.v1",
            "scenario": {"id": "kestrel-dawn-approach", "version": "1.0.0"},
            "seed": 7,
            "ticks": 100,
            "actions": [action.model_dump(mode="json")],
            "events": [record.model_dump(mode="json")],
            "final_state_hash": HASH,
        }
    )
    jsonschema.validate(session.model_dump(mode="json"), schema("session-record.v1"))
    assert session.picture is False  # absent means a session without the sensor picture
    with_picture = session.model_copy(update={"picture": True})
    jsonschema.validate(with_picture.model_dump(mode="json"), schema("session-record.v1"))
    jsonschema.validate(action.model_dump(mode="json"), schema("action-record.v1"))
    jsonschema.validate(record.model_dump(mode="json"), schema("event-record.v1"))


# ---------------------------------------------------------------------------- malformed

Mutation = Callable[[dict[str, Any]], None]


def setter(path: str, value: Any) -> Mutation:
    def apply(data: dict[str, Any]) -> None:
        *parents, last = path.split(".")
        node: Any = data
        for key in parents:
            node = node[int(key)] if key.isdigit() else node[key]
        node[int(last) if last.isdigit() else last] = value

    return apply


def deleter(key: str) -> Mutation:
    def apply(data: dict[str, Any]) -> None:
        data.pop(key)

    return apply


# (label, mutation, rejected by the JSON Schema too) — cross-field rules live only in the models
SCENARIO_BAD: list[tuple[str, Mutation, bool]] = [
    ("missing threats", deleter("threats"), True),
    ("unknown field", setter("difficulty", "hard"), True),
    ("wrong contract", setter("contract", "scenario.v2"), True),
    ("not fictional", setter("fictional", False), True),
    ("tick rate", setter("tick_hz", 30), True),
    ("bad id", setter("id", "Kestrel Dawn"), True),
    ("bad version", setter("version", "1.0"), True),
    ("negative seed", setter("default_seed", -1), True),
    ("visibility zero", setter("world.weather.visibility_m", 0), True),
    ("heading 360", setter("threats.0.start_heading_deg", 360), True),
    ("non-flat terrain", setter("world.terrain.kind", "dem"), True),
    ("empty route", setter("threats.0.route", []), True),
    ("hindi missing", setter("title", {"en": "Only English"}), True),
    ("speed above class", setter("threats.0.route.0.speed_mps", 40), False),
    ("start above band", setter("threats.0.start.z", 900), False),
    ("route leaves area", setter("threats.0.route.0.position.x", 9000), False),
    ("duplicate threat", setter("threats.1.id", "contact-a"), False),
    ("spawn after end", setter("threats.1.spawn_s", 500), False),
    ("inverted band", setter("threats.0.limits.min_altitude_m", 500), False),
]
RULEPACK_BAD: list[tuple[str, Mutation, bool]] = [
    ("unknown action", setter("rules.0.permits", ["fire"]), True),
    ("no rules", setter("rules", []), True),
    ("bad source id", setter("effector_classes.0.max_range.source_id", "Z99"), True),
    ("missing verified", lambda d: d["effector_classes"][0]["max_range"].pop("verified"), True),
    ("confidence above 1", setter("rules.1.when.min_confidence", 1.5), True),
    ("default engage", setter("default_action", "engage"), True),
    ("weights sum", setter("weights.detect", 0.5), False),
    ("engage without effector", setter("rules.1.effector_classes", []), False),
    ("effector without engage", setter("rules.0.effector_classes", ["ec-a"]), False),
    ("unknown effector", setter("rules.2.effector_classes", ["ec-z"]), False),
    ("duplicate rule", setter("rules.1.id", "track-everything"), False),
]
PROFILE_BAD: list[tuple[str, Mutation, bool]] = [
    ("bare number", setter("parameters.update_interval", 1.2), True),
    ("no source", lambda d: d["parameters"]["update_interval"].pop("source_id"), True),
    ("bad modality", setter("modality", "lidar"), True),
    (
        "bad parameter name",
        setter("parameters.Range Max", dict(raw(PROFILE)["parameters"]["update_interval"])),
        True,
    ),
    ("no parameters", setter("parameters", {}), True),
    ("infinite value", setter("parameters.update_interval.value", float("inf")), False),
]
EVENT_BAD: list[tuple[str, dict[str, Any]]] = [
    ("negative seq", event(seq=-1)),
    ("short hash", event(hash="abc")),
    ("upper-case hash", event(prev_hash="A" * 64)),
    ("bad type", event(type="Start")),
    ("bad actor", event(actor="trainee")),
    ("extra field", event(sig="x")),
    ("negative time", event(t=-0.05)),
]


def cases(path: Path, bad: list[tuple[str, Mutation, bool]]) -> list[Any]:
    return [pytest.param(path, m, s, id=f"{path.stem}:{label}") for label, m, s in bad]


@pytest.mark.parametrize(
    ("path", "mutate", "schema_rejects"),
    cases(SCENARIO, SCENARIO_BAD) + cases(RULEPACK, RULEPACK_BAD) + cases(PROFILE, PROFILE_BAD),
)
def test_malformed_packs_are_rejected(path: Path, mutate: Mutation, schema_rejects: bool) -> None:
    data = copy.deepcopy(raw(path))
    mutate(data)
    model = PACKS[raw(path)["contract"]]
    with pytest.raises(ValidationError):
        model.model_validate(data)
    if schema_rejects:
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(data, schema(raw(path)["contract"]))


@pytest.mark.parametrize(("label", "data"), EVENT_BAD, ids=[label for label, _ in EVENT_BAD])
def test_malformed_events_are_rejected(label: str, data: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        EventRecord.model_validate(data)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(data, schema("event-record.v1"))


def test_contracts_are_immutable() -> None:
    record = EventRecord.model_validate(event())
    with pytest.raises(ValidationError):
        record.seq = 5  # type: ignore[misc]


# ---------------------------------------------------------------------------- loader


def test_yaml_duplicate_keys_are_rejected(tmp_path: Path) -> None:
    path = tmp_path / "dup.yaml"
    path.write_text("contract: rulepack.v1\nid: a\nid: b\n", encoding="utf-8")
    with pytest.raises(PackError, match="duplicate key 'id' at line 3"):
        load_pack(path)


def test_json_duplicate_keys_are_rejected(tmp_path: Path) -> None:
    path = tmp_path / "dup.json"
    path.write_text('{"contract": "scenario.v1", "contract": "scenario.v1"}', encoding="utf-8")
    with pytest.raises(PackError, match="duplicate key"):
        load_pack(path)


def test_yaml_tags_cannot_build_python_objects(tmp_path: Path) -> None:
    path = tmp_path / "evil.yaml"
    path.write_text("contract: !!python/object/apply:os.getcwd []\n", encoding="utf-8")
    with pytest.raises(Exception, match="python/object"):
        load_pack(path)


@pytest.mark.parametrize(
    ("name", "text", "message"),
    [
        ("list.yaml", "- a\n- b\n", "must be a mapping"),
        ("other.yaml", "contract: terrain.v1\n", "unknown contract"),
        ("pack.toml", "contract = 1", "unsupported pack file type"),
    ],
)
def test_loader_reports_unusable_files(tmp_path: Path, name: str, text: str, message: str) -> None:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    with pytest.raises(PackError, match=message):
        load_pack(path)


# ---------------------------------------------------------------------------- schema export


def test_exported_schemas_match_the_models() -> None:
    assert stale() == [], "run `make schemas` and commit packs/schemas/"


def test_every_exported_schema_is_a_valid_draft_2020_12_schema() -> None:
    for name in SCHEMAS:
        jsonschema.Draft202012Validator.check_schema(schema(name))
        assert schema(name)["$id"] == f"{name}.json"


def test_export_check_detects_drift_and_rewrite_fixes_it(tmp_path: Path) -> None:
    write(tmp_path)
    assert stale(tmp_path) == []
    (tmp_path / "scenario.v1.json").write_text("{}\n", encoding="utf-8")
    (tmp_path / "orphan.v1.json").write_text("{}\n", encoding="utf-8")
    (tmp_path / "rulepack.v1.json").unlink()
    assert stale(tmp_path) == ["scenario.v1.json", "rulepack.v1.json", "orphan.v1.json"]
    write(tmp_path)
    assert stale(tmp_path) == ["orphan.v1.json"]
    assert (tmp_path / "scenario.v1.json").read_text(encoding="utf-8") == render("scenario.v1")


def test_export_cli_check_passes_on_the_committed_schemas(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["--check"]) == 0
    assert "up to date" in capsys.readouterr().out


# ---------------------------------------------------------------------------- confusion tables

CONFUSION = {
    "labels": ["rotary-small", "unknown"],
    "rows": {"rotary-small": [0.75, 0.25]},
    "source_id": "F01",
    "verified": False,
}


def profile_with(confusion: dict[str, Any]) -> dict[str, Any]:
    return raw(PROFILE) | {"confusion": {"default": confusion}}


def test_a_profile_may_carry_a_row_normalised_confusion_table() -> None:
    data = profile_with(CONFUSION)
    jsonschema.validate(data, schema("sensor-profile.v1"))
    assert PACKS["sensor-profile.v1"].model_validate(data).model_dump(mode="json") == data


@pytest.mark.parametrize(
    "changes",
    [
        {"rows": {"rotary-small": [0.7, 0.2]}},
        {"rows": {"rotary-small": [1.0]}},
        {"labels": ["a", "a"]},
    ],
    ids=["row sum", "row length", "duplicate label"],
)
def test_confusion_tables_that_are_not_row_normalised_are_rejected(changes: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        PACKS["sensor-profile.v1"].model_validate(profile_with(CONFUSION | changes))
