"""The scripted curriculum: twelve scenarios, each valid, lint-clean, playable and "verified
solvable by test run" (docs/SCENARIO_ENGINE.md). Fictional sites; the Hindi text is unreviewed."""

import math
import re
from functools import cache
from pathlib import Path
from typing import Any

import pytest
import yaml

from app.contracts.scenario import ScenarioSpec, Waypoint
from app.live.catalog import ScenarioCatalog
from app.scenarios.language import load_text, to_yaml, validate_text
from app.scenarios.lint import LintItem, lint
from app.scenarios.oracle import play
from app.scenarios.solvability import evaluate, solved, wording
from sim.catalogue import load_catalogue
from sim.constants import ORBIT_RADIUS_M
from sim.terrain import load_pack, pack_dir

from .sim_cases import REPO

SCENARIOS = REPO / "packs" / "scenarios"
FILES = sorted(SCENARIOS.glob("curriculum-*.v1.yaml"))
STAND_OFF_M = 250.0
DEVANAGARI = re.compile("[ऀ-ॿ]")


@cache
def text_of(path: Path) -> str:
    return path.read_text(encoding="utf-8")


@cache
def spec_of(path: Path) -> ScenarioSpec:
    return load_text(text_of(path))


@cache
def catalog() -> ScenarioCatalog:
    return ScenarioCatalog()


@cache
def lint_of(path: Path) -> tuple[LintItem, ...]:
    result = validate_text(text_of(path))
    assert result.spec is not None
    return tuple(lint(result.spec, result.lines))


@cache
def oracle_run(path: Path) -> tuple[bool, float]:
    spec = spec_of(path)
    result = play(spec, spec.default_seed)
    checks = evaluate(spec, result, 80)
    lowest = next(c.value for c in checks if c.name == "oracle-score")
    assert isinstance(lowest, float)
    return solved(checks) and wording(checks) == "verified solvable by test run", lowest


def stem(path: Path) -> str:
    return path.name.removesuffix(".v1.yaml")


def texts(node: Any) -> list[dict[str, str]]:
    """Every {en, hi} object in a document."""
    found: list[dict[str, str]] = []
    if isinstance(node, dict):
        if set(node) == {"en", "hi"}:
            found.append(node)
        for value in node.values():
            found.extend(texts(value))
    elif isinstance(node, list):
        for item in node:
            found.extend(texts(item))
    return found


def distance_to_segment(
    p: tuple[float, float], a: tuple[float, float], b: tuple[float, float]
) -> float:
    ax, ay = a
    dx, dy = b[0] - ax, b[1] - ay
    length2 = dx * dx + dy * dy
    t = 0.0 if length2 == 0 else max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / length2))
    return math.hypot(p[0] - (ax + t * dx), p[1] - (ay + t * dy))


def clearance_m(
    start: tuple[float, float],
    route: list[Waypoint],
    loiter: bool,
    site: tuple[float, float],
) -> float:
    """Closest approach of a flown route to the defended place, in the ground plane, counting the
    orbit flown while loitering at the last waypoint."""
    points = [start, *((w.position.x, w.position.y) for w in route)]
    near = min(distance_to_segment(site, a, b) for a, b in zip(points, points[1:], strict=False))
    near = min(near, math.hypot(start[0] - site[0], start[1] - site[1]))
    if loiter:
        last = points[-1]
        near = min(near, math.hypot(last[0] - site[0], last[1] - site[1]) - ORBIT_RADIUS_M)
    return near


def test_there_are_twelve_files() -> None:
    assert len(FILES) == 12
    assert [stem(p)[11:13] for p in FILES] == [f"{n:02d}" for n in range(1, 13)]


@pytest.mark.parametrize("path", FILES, ids=stem)
class TestEachScenario:
    def test_loads_and_round_trips(self, path: Path) -> None:
        spec = spec_of(path)
        assert load_text(to_yaml(spec)) == spec
        assert to_yaml(spec) == text_of(path), "the file is the canonical written form"
        assert spec.id == stem(path)
        assert spec.version == "1.0.0" and spec.fictional is True

    def test_meta(self, path: Path) -> None:
        meta = spec_of(path).meta
        assert meta is not None
        assert meta.origin == "scripted" and meta.playable is True
        assert meta.curriculum_order == int(stem(path)[11:13])
        assert meta.difficulty is not None and 0 <= meta.difficulty <= 100
        assert meta.tags and len(set(meta.tags)) == len(meta.tags)

    def test_no_lint_errors(self, path: Path) -> None:
        errors = [i for i in lint_of(path) if i.severity == "error"]
        assert errors == [], [(i.code, i.line, i.message) for i in errors]

    def test_the_catalogue_accepts_every_threat(self, path: Path) -> None:
        assert load_catalogue().check_scenario(spec_of(path)) == []

    def test_verified_solvable_by_test_run(self, path: Path) -> None:
        ok, lowest = oracle_run(path)
        assert ok, f"the oracle did not clear {stem(path)} (lowest hostile score {lowest})"
        assert lowest >= 0.8

    def test_every_route_keeps_its_stand_off(self, path: Path) -> None:
        spec = spec_of(path)
        site = (spec.assets[0].position.x, spec.assets[0].position.y)
        for threat in spec.threats:
            start = (threat.start.x, threat.start.y)
            loiter = threat.on_route_end == "loiter" and threat.motion is None
            near = clearance_m(start, threat.route, loiter, site)
            assert near >= STAND_OFF_M, f"{threat.id} comes within {near:.0f} m"
            if threat.motion is not None and hasattr(threat.motion, "anchor"):
                anchor = (threat.motion.anchor.x, threat.motion.anchor.y)
                assert math.hypot(anchor[0] - site[0], anchor[1] - site[1]) >= STAND_OFF_M
        for group in spec.groups:
            guide = (group.route[0].position.x, group.route[0].position.y)
            loiter = group.on_route_end == "loiter"
            near = clearance_m(guide, group.route, loiter, site)
            assert near >= STAND_OFF_M, f"group {group.id} comes within {near:.0f} m"

    def test_text_is_present_in_both_languages(self, path: Path) -> None:
        found = texts(yaml.safe_load(text_of(path)))
        assert len(found) >= 6
        for item in found:
            assert item["en"].strip() and item["hi"].strip()
            assert DEVANAGARI.search(item["hi"]), item
            assert not DEVANAGARI.search(item["en"]), item
            assert len(item["en"]) <= 400 and len(item["hi"]) <= 400

    def test_no_overclaiming_words(self, path: Path) -> None:
        lowered = text_of(path).lower()
        assert "provably" not in lowered and "guaranteed" not in lowered
        assert "verified" not in lowered, "a scenario file does not state its own verification"

    def test_fits_the_play_area_and_the_terrain(self, path: Path) -> None:
        spec = spec_of(path)
        terrain = spec.world.terrain
        assert terrain.kind == "pack" and terrain.id in {"heron-ridge", "osprey-town"}
        pack = load_pack(pack_dir(terrain.id))
        assert (pack.pack_id, pack.version) == (terrain.id, terrain.version)
        assert spec.world.half_extent_m <= pack.half_extent_m
        assert 240.0 <= spec.duration_s <= 420.0
        site = spec.assets[0].position
        assert (site.x, site.y) == (0.0, 0.0)
        assert [z.role for z in spec.zones] == ["inner", "outer"]
        assert spec.zones[0].radius_m < spec.zones[1].radius_m

    def test_a_trainee_can_start_it(self, path: Path) -> None:
        entry = catalog().get(spec_of(path).id)
        assert entry is not None and entry.spec == spec_of(path)

    def test_the_rule_pack_is_the_baseline(self, path: Path) -> None:
        ref = spec_of(path).rule_pack
        assert (ref.id, ref.version) == ("training-baseline", "1.0.0")


def test_ids_orders_and_seeds_are_unique() -> None:
    specs = [spec_of(p) for p in FILES]
    assert len({s.id for s in specs}) == 12
    assert len({s.default_seed for s in specs}) == 12
    orders = sorted(s.meta.curriculum_order for s in specs if s.meta and s.meta.curriculum_order)
    assert orders == list(range(1, 13))
    assert [spec_of(p).meta.curriculum_order for p in FILES] == list(range(1, 13))  # type: ignore[union-attr]


def hour_band(hour: float) -> str:
    if 5.5 <= hour < 7.0:
        return "dawn"
    if 7.0 <= hour < 17.5:
        return "day"
    if 17.5 <= hour < 19.0:
        return "dusk"
    return "night"


#: What each step of the curriculum adds: (time of day, terrain, hostile contacts at least,
#: groups, degradations, civil flights, clutter contacts at least).
EXPECTED = {
    1: ("day", "heron-ridge", 1, 0, 0, 0, 0),
    2: ("day", "osprey-town", 1, 0, 0, 1, 3),
    3: ("dusk", "heron-ridge", 1, 0, 0, 0, 0),
    4: ("night", "heron-ridge", 1, 0, 0, 0, 0),
    5: ("night", "osprey-town", 1, 0, 0, 0, 0),
    6: ("day", "heron-ridge", 1, 0, 1, 0, 0),
    7: ("day", "osprey-town", 1, 0, 1, 0, 0),
    8: ("day", "heron-ridge", 6, 1, 0, 0, 0),
    9: ("night", "osprey-town", 6, 1, 0, 0, 0),
    10: ("dawn", "heron-ridge", 1, 1, 0, 0, 1),
    11: ("day", "osprey-town", 1, 0, 0, 0, 2),
    12: ("night", "heron-ridge", 6, 1, 1, 1, 0),
}


@pytest.mark.parametrize("order", range(1, 13))
def test_each_step_adds_what_it_says(order: int) -> None:
    path = FILES[order - 1]
    spec = spec_of(path)
    band, terrain, hostile_min, groups, degraded, flights, clutter_min = EXPECTED[order]
    assert hour_band(spec.world.start_time_of_day_h) == band
    assert spec.world.terrain.kind == "pack" and spec.world.terrain.id == terrain
    hostile = [t for t in spec.threats if t.disposition == "hostile"]
    assert len(hostile) >= hostile_min
    if order not in (8, 9, 12):
        assert len(hostile) == 1
    assert len(spec.groups) == groups
    assert (len(spec.degradations) > 0) == bool(degraded)
    assert len(spec.filed_flights) == flights
    assert sum(t.disposition == "clutter" for t in spec.threats) >= clutter_min


def test_the_swarms_cover_their_formation() -> None:
    swarms = 0
    for path in FILES:
        for group in spec_of(path).groups:
            if group.kind == "swarm":
                swarms += 1
                assert 6 <= len(group.members) <= 12
        assert [i for i in lint_of(path) if i.code == "group.link-range"] == []
    assert swarms == 3


def test_special_cases_are_present() -> None:
    by_order = {spec_of(p).meta.curriculum_order: spec_of(p) for p in FILES}  # type: ignore[union-attr]
    classes = {n: {t.class_id for t in s.threats} for n, s in by_order.items()}
    assert "autonomous-small" in classes[5]
    assert "decoy-small" in classes[9] and "decoy-small" in classes[12]
    assert "fpv-small" in classes[10]
    assert "fixed-wing-medium" in classes[11] and {"kite", "balloon"} <= classes[11]
    assert any(g.kind == "flock" for g in by_order[10].groups)
    kinds = {d.kind for d in by_order[6].degradations} | {d.kind for d in by_order[7].degradations}
    assert {"outage", "haze", "sector-outage", "interference"} <= kinds
    night_profiles = {s.profile.id for s in by_order[4].sensors}
    assert {"eo-generic-nv", "ir-generic-thermal"} <= night_profiles


def test_the_readme_lists_every_scenario() -> None:
    readme = (SCENARIOS / "README.md").read_text(encoding="utf-8")
    for path in FILES:
        assert stem(path) in readme
