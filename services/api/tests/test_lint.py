"""The scenario linter: one test per code, with the line of the offending node."""

import re
from typing import Any

import pytest

from app.contracts.common import Vec3
from app.contracts.loader import load_pack
from app.contracts.paths import packs_root
from app.contracts.scenario import PackTerrain, ScenarioSpec
from app.scenarios.coverage import coverage_of
from app.scenarios.language import LineMap, to_yaml, validate_text
from app.scenarios.lint import LINT_CODES, LintItem, lint
from sim.breadth import breadth_scenario
from sim.catalogue import Catalogue, load_catalogue
from sim.terrain import load_pack as load_terrain
from sim.terrain import pack_dir

from .sim_cases import REPO


def pack_spec(name: str) -> ScenarioSpec:
    spec = load_pack(packs_root() / "scenarios" / f"{name}.v1.json")
    assert isinstance(spec, ScenarioSpec)
    return spec


def kestrel() -> ScenarioSpec:
    return pack_spec("kestrel-dawn-approach")


def heron() -> ScenarioSpec:
    return pack_spec("heron-ridge-low-approach")


def lint_text(text: str) -> list[LintItem]:
    result = validate_text(text)
    assert result.spec is not None, result.errors
    return lint(result.spec, result.lines)


def codes(items: list[LintItem]) -> list[str]:
    return [i.code for i in items]


def only(items: list[LintItem], code: str) -> LintItem:
    (item,) = [i for i in items if i.code == code]
    return item


def move(spec: ScenarioSpec, index: int, **changes: Any) -> ScenarioSpec:
    """The scenario with one threat changed, bypassing validation (as a hand edit that the
    contract would refuse is not the linter's concern, but the linter must still cope)."""
    threats = list(spec.threats)
    threats[index] = threats[index].model_copy(update=changes)
    return spec.model_copy(update={"threats": threats})


def with_waypoint(spec: ScenarioSpec, ti: int, wi: int, **position: float) -> ScenarioSpec:
    threat = spec.threats[ti]
    route = list(threat.route)
    p = route[wi].position
    route[wi] = route[wi].model_copy(
        update={"position": Vec3(x=p.x, y=p.y, z=p.z).model_copy(update=position)}
    )
    return move(spec, ti, route=route)


# ------------------------------------------------------------------------------------ clean
@pytest.mark.parametrize(
    "name", ["kestrel-dawn-approach", "heron-ridge-low-approach", "harrier-morning-watch"]
)
def test_shipped_scenarios_have_no_errors(name: str) -> None:
    items = lint(pack_spec(name))
    assert [i for i in items if i.severity == "error"] == []


def test_without_lines_every_position_is_zero() -> None:
    spec = kestrel().model_copy(update={"zones": []})
    items = lint(spec)
    assert items and all((i.line, i.column) == (0, 0) for i in items)


def test_items_are_sorted_by_line_then_code() -> None:
    spec = kestrel().model_copy(update={"zones": []})
    text = to_yaml(kestrel())
    items = lint(spec, validate_text(text).lines)
    keys = [(i.line, i.code) for i in items]
    assert keys == sorted(keys) and len(keys) > 1


def test_every_item_is_well_formed() -> None:
    spec = kestrel().model_copy(update={"zones": [], "duration_s": 30.0})
    for item in lint(spec, LineMap.from_text(to_yaml(kestrel()))):
        assert item.severity == LINT_CODES[item.code]
        assert item.message and "provably" not in item.message
        assert "guaranteed" not in item.message
        assert isinstance(item.params, dict)


# ------------------------------------------------------------------------ timing (acceptance)
def test_a_threat_timed_before_the_reaction_window_fails_with_its_line() -> None:
    """The acceptance test: a hostile contact that reaches the inner zone sooner than the rules
    allow a response fails lint with `timing.reaction-window` and the line of its `spawn_s`."""
    data = kestrel().model_dump(mode="json")
    quick = data["threats"][0]
    quick["spawn_s"] = 60.0
    quick["start"] = {"x": 1500.0, "y": 0.0, "z": 60.0}
    quick["start_speed_mps"] = 16.0
    quick["route"] = [
        {"position": {"x": 400.0, "y": 0.0, "z": 50.0}, "speed_mps": 18.0, "hold_s": 0.0}
    ]
    text = to_yaml(ScenarioSpec.model_validate(data))
    spawn_line = next(
        i + 1 for i, line in enumerate(text.splitlines()) if line.strip() == "spawn_s: 60.0"
    )
    result = validate_text(text)
    assert result.valid
    items = lint(result.spec, result.lines)  # type: ignore[arg-type]
    item = only(items, "timing.reaction-window")
    assert item.severity == "error"
    assert item.line == spawn_line
    assert text.splitlines()[item.line - 1].strip() == "spawn_s: 60.0"
    assert item.params["threat"] == quick["id"]
    assert item.params["minimum_s"] == 45.0
    assert float(item.params["window_s"]) < 45.0  # type: ignore[arg-type]


def test_a_comfortable_window_passes() -> None:
    assert "timing.reaction-window" not in codes(lint(kestrel()))


def test_a_threat_that_never_enters_the_inner_zone_is_measured_to_the_end() -> None:
    data = kestrel().model_dump(mode="json")
    data["zones"] = [z for z in data["zones"] if z["role"] != "inner"]
    assert "timing.reaction-window" not in codes(lint(ScenarioSpec.model_validate(data)))


def test_spawning_inside_coverage_and_the_inner_zone_has_no_time_at_all() -> None:
    spec = kestrel()
    start = Vec3(x=300.0, y=0.0, z=50.0)
    item = only(lint(move(spec, 0, spawn_s=10.0, start=start)), "timing.reaction-window")
    assert float(item.params["window_s"]) <= 1.0  # type: ignore[arg-type]


# ---------------------------------------------------------------------------------- coverage
def test_no_coverage_is_an_error_at_the_threat_id() -> None:
    spec = kestrel().model_copy(update={"sensors": []})
    text = to_yaml(kestrel())
    items = lint(spec, validate_text(text).lines)
    none = [i for i in items if i.code == "coverage.none"]
    assert [i.params["threat"] for i in none] == [t.id for t in spec.threats]
    assert text.splitlines()[none[0].line - 1].strip() == f"- id: {spec.threats[0].id}"
    assert none[0].severity == "error"


def test_late_coverage_is_a_warning() -> None:
    spec = kestrel()
    first = coverage_of(spec, spec.threats[0]).first_s
    assert first is not None and first > 20
    short = spec.model_copy(update={"duration_s": first + 10.0})
    item = only(
        [i for i in lint(short) if i.params.get("threat") == spec.threats[0].id],
        "coverage.late",
    )
    assert item.severity == "warning" and item.params["first_s"] == round(first, 1)


def test_clutter_and_civil_contacts_are_not_checked_for_coverage() -> None:
    spec = heron().model_copy(update={"sensors": []})
    flagged = {i.params["threat"] for i in lint(spec) if i.code == "coverage.none"}
    assert flagged == {t.id for t in spec.threats if t.disposition == "hostile"}


# --------------------------------------------------------------------------------------- ROE
def test_no_zone_means_no_engagement_is_possible() -> None:
    spec = kestrel().model_copy(update={"zones": []})
    text = to_yaml(kestrel())
    items = lint(spec, validate_text(text).lines)
    item = only(items, "roe.no-engage-rule")
    assert item.severity == "error" and item.params["zone_roles"] == []
    assert text.splitlines()[item.line - 1].startswith("rule_pack:")
    assert "it has no zone" in item.message


def test_only_a_restricted_zone_cannot_host_an_engagement() -> None:
    zone = kestrel().zones[0].model_copy(update={"role": "restricted"})
    item = only(lint(kestrel().model_copy(update={"zones": [zone]})), "roe.no-engage-rule")
    assert item.params["zone_roles"] == ["restricted"]


def test_a_missing_zone_role_is_a_warning_at_the_zones() -> None:
    spec = kestrel()
    outer_only = spec.model_copy(update={"zones": [z for z in spec.zones if z.role == "outer"]})
    text = to_yaml(spec)
    items = lint(outer_only, validate_text(text).lines)
    missing = [i for i in items if i.code == "roe.zone-missing"]
    assert {i.params["rule"] for i in missing} == {"suspect-outer-zone", "hostile-inner-zone"}
    assert all(i.severity == "warning" and i.params["zone_role"] == "inner" for i in missing)
    assert text.splitlines()[missing[0].line - 1].startswith("zones:")
    assert "roe.no-engage-rule" not in codes(items)


def test_a_missing_rule_pack_is_an_error_and_does_not_crash() -> None:
    spec = kestrel()
    ref = spec.rule_pack.model_copy(update={"version": "9.9.9"})
    text = to_yaml(spec)
    items = lint(spec.model_copy(update={"rule_pack": ref}), validate_text(text).lines)
    item = only(items, "roe.pack-missing")
    assert item.severity == "error" and item.params["version"] == "9.9.9"
    assert text.splitlines()[item.line - 1].startswith("rule_pack:")
    assert "timing.reaction-window" not in codes(items)
    assert "roe.no-engage-rule" not in codes(items)


# --------------------------------------------------------------------------------------- routes
def test_a_waypoint_outside_the_play_area() -> None:
    spec = with_waypoint(kestrel(), 0, 1, x=9000.0)
    text = to_yaml(kestrel())
    item = only(lint(spec, validate_text(text).lines), "route.leaves-area")
    assert item.severity == "error" and item.params["waypoint"] == 1
    assert text.splitlines()[item.line - 1].strip() == "- position:"


def test_a_waypoint_below_the_envelope() -> None:
    spec = with_waypoint(kestrel(), 0, 2, z=1.0)
    text = to_yaml(kestrel())
    item = only(lint(spec, validate_text(text).lines), "route.below-envelope")
    assert item.params["minimum_m"] == 5.0 and item.params["z_m"] == 1.0
    assert text.splitlines()[item.line - 1].strip() == "z: 40.0"


def test_a_waypoint_above_the_envelope() -> None:
    spec = with_waypoint(kestrel(), 0, 0, z=900.0)
    item = only(lint(spec), "route.above-envelope")
    assert item.params["maximum_m"] == 400.0 and item.severity == "error"


def test_the_narrower_of_the_threat_and_class_limits_applies() -> None:
    spec = kestrel()
    wide = spec.threats[0].limits.model_copy(update={"max_altitude_m": 900.0})
    spec = move(spec, 0, limits=wide)
    spec = with_waypoint(spec, 0, 0, z=600.0)
    assert only(lint(spec), "route.above-envelope").params["maximum_m"] == 400.0
    assert any(i.code == "catalogue.limits" for i in lint(spec))


def test_a_waypoint_faster_than_the_class() -> None:
    spec = kestrel()
    threat = spec.threats[0]
    route = [threat.route[0].model_copy(update={"speed_mps": 40.0}), *threat.route[1:]]
    text = to_yaml(spec)
    item = only(lint(move(spec, 0, route=route), validate_text(text).lines), "route.speed")
    assert item.params["maximum_mps"] == 18.0 and item.params["speed_mps"] == 40.0
    assert text.splitlines()[item.line - 1].strip().startswith("speed_mps:")


def test_a_route_that_outlasts_the_scenario() -> None:
    spec = kestrel().model_copy(update={"duration_s": 60.0})
    text = to_yaml(kestrel())
    items = lint(spec, validate_text(text).lines)
    flagged = [i for i in items if i.code == "route.unreachable"]
    assert [i.params["threat"] for i in flagged] == ["contact-a", "contact-b"]
    assert flagged[0].severity == "error"
    assert text.splitlines()[flagged[0].line - 1].strip() == "route:"


def test_a_looping_route_is_never_unreachable() -> None:
    spec = kestrel().model_copy(update={"duration_s": 60.0})
    spec = move(spec, 0, on_route_end="loop")
    flagged = [i.params["threat"] for i in lint(spec) if i.code == "route.unreachable"]
    assert flagged == ["contact-b"]


def test_non_hostile_routes_may_outlast_the_scenario() -> None:
    spec = heron().model_copy(update={"duration_s": 50.0})
    flagged = {i.params["threat"] for i in lint(spec) if i.code == "route.unreachable"}
    hostile = {t.id for t in spec.threats if t.disposition == "hostile"}
    assert flagged <= hostile


def test_a_waypoint_below_the_ground() -> None:
    spec = heron()
    ti = next(i for i, t in enumerate(spec.threats) if t.disposition == "hostile")
    x, y = spec.threats[ti].route[1].position.x, spec.threats[ti].route[1].position.y
    ground = load_terrain(pack_dir("heron-ridge")).ground_m(x, y)
    low = with_waypoint(spec, ti, 1, z=ground - 3.0)
    item = only(lint(low), "route.underground")
    assert item.params["waypoint"] == 1 and item.severity == "error"
    assert item.params["ground_m"] == round(ground, 1)


def test_a_clutter_motion_ignores_the_route() -> None:
    spec = breadth_scenario()
    kite = next(i for i, t in enumerate(spec.threats) if t.motion is not None)
    spec = with_waypoint(spec, kite, 0, z=-50.0)
    assert not [i for i in lint(spec) if i.params.get("threat") == spec.threats[kite].id]


# ----------------------------------------------------------------------------------- catalogue
def test_limits_wider_than_the_class_name_the_threat() -> None:
    spec = kestrel()
    wide = spec.threats[1].limits.model_copy(update={"max_speed_mps": 90.0})
    text = to_yaml(spec)
    items = lint(move(spec, 1, limits=wide), validate_text(text).lines)
    item = only(items, "catalogue.limits")
    assert item.params["threat"] == spec.threats[1].id and item.severity == "error"
    assert "max_speed_mps" in item.message
    assert text.splitlines()[item.line - 1].strip() == f"- id: {spec.threats[1].id}"


def test_a_class_the_catalogue_lacks() -> None:
    spec = move(kestrel(), 0, class_id="mystery-class")
    items = lint(spec)
    assert "catalogue.limits" in codes(items)
    assert "sensor.profile" in codes(items)  # the sensors cannot score a class they do not know


def test_a_problem_that_names_no_threat_points_at_the_threats() -> None:
    class Odd(Catalogue):
        def check_scenario(self, spec: ScenarioSpec) -> list[str]:
            return ["something general", "threat nobody: not here"]

    base = load_catalogue()
    odd = Odd(list(base))
    text = to_yaml(kestrel())
    items = [
        i for i in lint(kestrel(), validate_text(text).lines, odd) if i.code == "catalogue.limits"
    ]
    assert len(items) == 2 and all(i.params["threat"] is None for i in items)
    assert text.splitlines()[items[0].line - 1].startswith("threats:")


# --------------------------------------------------------------------------------------- groups
def test_a_link_range_that_does_not_cover_the_formation() -> None:
    spec = breadth_scenario()
    assert "group.link-range" not in codes(lint(spec))
    groups = [g.model_copy(update={"link_range_m": 30.0}) for g in spec.groups]
    items = [
        i for i in lint(spec.model_copy(update={"groups": groups})) if i.code == "group.link-range"
    ]
    assert {i.params["group"] for i in items} == {g.id for g in spec.groups}
    assert all(i.severity == "warning" and float(i.params["needed_m"]) > 30.0 for i in items)  # type: ignore[arg-type]


def test_group_warning_points_at_the_link_range_line() -> None:
    spec = breadth_scenario()
    groups = [spec.groups[0].model_copy(update={"link_range_m": 30.0}), *spec.groups[1:]]
    changed = spec.model_copy(update={"groups": groups})
    text = to_yaml(changed)
    item = [i for i in lint(changed, validate_text(text).lines) if i.code == "group.link-range"][0]
    assert text.splitlines()[item.line - 1].strip() == "link_range_m: 30.0"


# --------------------------------------------------------------------------------------- sensors
def test_a_sensor_profile_that_cannot_be_resolved() -> None:
    spec = kestrel()
    bad = spec.sensors[0].model_copy(
        update={"profile": spec.sensors[0].profile.model_copy(update={"version": "9.9.9"})}
    )
    text = to_yaml(spec)
    items = lint(spec.model_copy(update={"sensors": [bad]}), validate_text(text).lines)
    item = only(items, "sensor.profile")
    assert item.params["sensor"] == "radar-1" and item.severity == "error"
    assert text.splitlines()[item.line - 1].startswith("    profile:")
    assert "coverage.none" not in codes(items)


def test_each_failing_sensor_is_reported_once() -> None:
    spec = heron()
    placed = [
        s.model_copy(update={"profile": s.profile.model_copy(update={"version": "9.9.9"})})
        if i < 2
        else s
        for i, s in enumerate(spec.sensors)
    ]
    items = lint(spec.model_copy(update={"sensors": placed}))
    assert [i.params["sensor"] for i in items if i.code == "sensor.profile"] == [
        s.id for s in spec.sensors[:2]
    ]


def test_sensors_that_only_fail_together_are_reported_at_the_sensors() -> None:
    spec = kestrel()
    twice = spec.model_copy(update={"sensors": [spec.sensors[0], spec.sensors[0]]})
    text = to_yaml(spec)
    items = lint(twice, validate_text(text).lines)
    item = only(items, "sensor.profile")
    assert text.splitlines()[item.line - 1].startswith("sensors:")
    assert "together" in item.message


# ---------------------------------------------------------------------------------------- terrain
def test_a_terrain_pack_that_cannot_be_loaded() -> None:
    spec = heron()
    wrong = PackTerrain(kind="pack", id="heron-ridge", version="9.9.9")
    world = spec.world.model_copy(update={"terrain": wrong})
    text = to_yaml(spec)
    items = lint(spec.model_copy(update={"world": world}), validate_text(text).lines)
    item = only(items, "world.terrain-missing")
    assert item.severity == "error"
    assert text.splitlines()[item.line - 1].strip() == "terrain:"
    assert "coverage.none" not in codes(items)


# ------------------------------------------------------------------------------------ the table
def test_the_documented_codes_are_the_implemented_ones() -> None:
    text = (REPO / "docs" / "SCENARIO_ENGINE.md").read_text(encoding="utf-8")
    start = text.index("## The scenario language")
    section = text[start : text.index("\n## ", start + 5)]
    documented: dict[str, str] = {}
    for row in re.findall(r"^\| ([^|]+) \| (error|warning) \|", section, re.MULTILINE):
        for code in re.findall(r"`([a-z]+\.[a-z-]+)`", row[0]):
            documented[code] = row[1]
    assert documented == LINT_CODES
