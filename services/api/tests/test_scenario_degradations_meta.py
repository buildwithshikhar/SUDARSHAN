"""The `degradations` and `meta` additions to scenario.v1: validation, effect and defaults."""

import json
from typing import Any

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from app.contracts import ScenarioSpec
from app.contracts.paths import packs_root
from app.contracts.scenario import DEGRADATION_KINDS
from sim.sensors.degradation import KINDS
from sim.tracking.picture import Picture
from sim.world import World

from .live_helpers import harrier_spec


def with_extras(**extra: Any) -> ScenarioSpec:
    data = harrier_spec().model_dump(mode="json")
    data.update(extra)
    return ScenarioSpec.model_validate(data)


def test_the_contract_lists_the_kinds_the_sensor_framework_has() -> None:
    assert DEGRADATION_KINDS == KINDS


def test_a_scenario_without_the_fields_reads_as_before() -> None:
    spec = harrier_spec()
    assert spec.degradations == [] and spec.meta is None


def test_a_degradation_has_a_window_a_severity_and_a_sector_where_the_kind_needs_one() -> None:
    spec = with_extras(
        degradations=[
            {"sensor": "radar-1", "kind": "outage", "from_s": 60, "to_s": 120},
            {"sensor": "eo-1", "kind": "haze", "from_s": 0, "severity": 0.6},
            {
                "sensor": "radar-1",
                "kind": "sector-outage",
                "from_s": 10,
                "sector_from_deg": 340,
                "sector_to_deg": 20,
            },
        ]
    )
    assert [d.kind for d in spec.degradations] == ["outage", "haze", "sector-outage"]
    assert spec.degradations[1].to_s is None and spec.degradations[0].severity == 1.0


@pytest.mark.parametrize(
    ("degradation", "message"),
    [
        ({"sensor": "radar-1", "kind": "outage", "from_s": 60, "to_s": 60}, "must end after"),
        ({"sensor": "nope", "kind": "outage", "from_s": 1}, "no sensor 'nope'"),
        ({"sensor": "radar-1", "kind": "outage", "from_s": 9999}, "after the scenario ends"),
        ({"sensor": "radar-1", "kind": "sector-outage", "from_s": 1}, "sector is required"),
        (
            {"sensor": "radar-1", "kind": "outage", "from_s": 1, "sector_from_deg": 1,
             "sector_to_deg": 2},
            "only for sector-outage",
        ),
        (
            {"sensor": "radar-1", "kind": "sector-outage", "from_s": 1, "sector_from_deg": 1},
            "needs both ends",
        ),
        ({"sensor": "radar-1", "kind": "haze", "from_s": 1, "severity": 1.5}, "less than or equal"),
        ({"sensor": "radar-1", "kind": "melt", "from_s": 1}, "Input should be"),
    ],
)  # fmt: skip
def test_a_malformed_degradation_is_refused(degradation: dict[str, Any], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        with_extras(degradations=[degradation])


def test_the_picture_applies_scenario_degradations_at_build_in_ticks() -> None:
    spec = with_extras(
        degradations=[
            {"sensor": "radar-1", "kind": "outage", "from_s": 60, "to_s": 120},
            {
                "sensor": "radar-1",
                "kind": "sector-outage",
                "from_s": 5,
                "sector_from_deg": 340,
                "sector_to_deg": 20,
            },
        ]
    )
    picture = Picture.build(spec, spec.default_seed)
    radar = next(s for s in picture.suite.sensors if s.id == "radar-1")
    first, second = radar.degradations
    assert (first.kind, first.start_tick, first.end_tick) == ("outage", 1200, 2400)
    assert (second.start_tick, second.end_tick, second.sector_from_deg) == (100, None, 340.0)


def test_a_scenario_outage_silences_the_sensor_for_its_window() -> None:
    spec = with_extras(
        degradations=[{"sensor": "radar-1", "kind": "outage", "from_s": 0, "to_s": 200}]
    )
    quiet = World(spec, 3, picture=Picture.build(spec, 3))
    plain = World(harrier_spec(), 3, picture=Picture.build(harrier_spec(), 3))
    for _ in range(round(150 * 20)):
        quiet.step()
        plain.step()

    def radar_reports(world: World) -> int:
        return sum(
            1 for r in world.log.records if r.type == "ledger.first_report"
            and r.payload.get("modality") == "radar"
        )  # fmt: skip

    assert radar_reports(quiet) == 0 < radar_reports(plain)
    assert quiet.state_hash() != plain.state_hash()


def test_a_scenario_without_degradations_replays_to_the_same_hash() -> None:
    spec = harrier_spec()
    a = World(spec, 5, picture=Picture.build(spec, 5))
    b = World(spec, 5, picture=Picture.build(spec, 5))
    for _ in range(200):
        a.step()
        b.step()
    assert a.state_hash() == b.state_hash()


def test_meta_defaults_and_ranges() -> None:
    spec = with_extras(meta={})
    assert spec.meta is not None
    assert (spec.meta.origin, spec.meta.playable, spec.meta.tags) == ("scripted", True, [])
    assert spec.meta.curriculum_order is None and spec.meta.generated is None
    full = with_extras(
        meta={
            "origin": "generated",
            "playable": False,
            "tags": ["night", "swarm"],
            "curriculum_order": 4,
            "difficulty": 55,
            "generated": {"generator_version": "1.0.0", "code": "SD1-ABCD-EFGH"},
        }
    )
    assert full.meta is not None and full.meta.generated is not None
    assert full.meta.generated.generator_version == "1.0.0"


@pytest.mark.parametrize(
    "meta",
    [
        {"origin": "invented"},
        {"tags": ["Not A Slug"]},
        {"tags": [f"t{i}" for i in range(13)]},
        {"curriculum_order": 0},
        {"difficulty": 101},
        {"generated": {"generator_version": "x", "code": "SD1-ABCD"}},
        {"generated": {"generator_version": "1.0.0", "code": "lower-case"}},
        {"surprise": True},
    ],
)
def test_a_malformed_meta_is_refused(meta: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        with_extras(meta=meta)


def test_the_exported_schema_accepts_the_new_fields() -> None:
    schema = json.loads((packs_root() / "schemas" / "scenario.v1.json").read_text("utf-8"))
    data = harrier_spec().model_dump(mode="json")
    data["degradations"] = [{"sensor": "radar-1", "kind": "outage", "from_s": 1, "to_s": 2}]
    data["meta"] = {"origin": "authored", "tags": ["day"]}
    Draft202012Validator(schema).validate(data)
