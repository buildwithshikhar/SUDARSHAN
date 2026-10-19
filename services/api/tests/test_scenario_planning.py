"""Route timing and sensor coverage as the linter and the generator estimate them, and the small
hooks the oracle needs from the sim core."""

import math

import pytest

from app.contracts import ScenarioSpec
from app.contracts.loader import load_pack
from app.contracts.paths import packs_root
from app.scenarios.coverage import COVER_PD, coverage_of, covers, environment
from app.scenarios.routes import leg_time_s, route_end_s, sample_route
from sim.sensors import build_sensors
from sim.terrain import terrain_for
from sim.world import ActionError, World

from .live_helpers import act, harrier_spec, harrier_world, run_until_track


def pack_scenario(name: str) -> ScenarioSpec:
    spec = load_pack(packs_root() / "scenarios" / f"{name}.v1.json")
    assert isinstance(spec, ScenarioSpec)
    return spec


def threat(spec: ScenarioSpec, threat_id: str):  # type: ignore[no-untyped-def]
    return next(t for t in spec.threats if t.id == threat_id)


# ----------------------------------------------------------------------------- routes


def test_leg_time_is_distance_over_the_slower_of_leg_speed_and_class_speed() -> None:
    assert leg_time_s(100.0, 10.0, 18.0) == 10.0
    assert leg_time_s(100.0, 50.0, 20.0) == 5.0
    assert leg_time_s(100.0, 0.0, 20.0) == pytest.approx(1000.0)  # a floor on speed, never /0


def test_route_end_adds_legs_and_holds_to_the_spawn_time() -> None:
    quad = threat(harrier_spec(), "contact-quad")
    legs = 0.0
    x, y, z = quad.start.x, quad.start.y, quad.start.z
    for w in quad.route:
        legs += (
            math.dist((x, y, z), (w.position.x, w.position.y, w.position.z))
            / min(w.speed_mps, quad.limits.max_speed_mps)
            + w.hold_s
        )
        x, y, z = w.position.x, w.position.y, w.position.z
    assert route_end_s(quad) == pytest.approx(quad.spawn_s + legs)


def test_sample_route_starts_at_the_spawn_and_ends_at_the_last_waypoint() -> None:
    quad = threat(harrier_spec(), "contact-quad")
    points = sample_route(quad, 1.0)
    first, last = points[0], points[-1]
    assert (first.t, first.x, first.y, first.z) == (
        quad.spawn_s,
        quad.start.x,
        quad.start.y,
        quad.start.z,
    )
    end = quad.route[-1].position
    assert (last.x, last.y, last.z) == pytest.approx(
        (end.x, end.y, end.z), abs=quad.limits.max_speed_mps
    )
    assert all(b.t - a.t == pytest.approx(1.0) for a, b in zip(points, points[1:], strict=False))
    assert math.hypot(first.vx, first.vy) > 0


def test_sample_route_holds_at_the_end_until_the_scenario_ends() -> None:
    quad = threat(harrier_spec(), "contact-quad")
    held = sample_route(quad, 5.0, until_s=420.0)
    end = quad.route[-1].position
    assert held[-1].t >= 415.0 and (held[-1].x, held[-1].y) == (end.x, end.y)
    assert held[-1].vx == held[-1].vy == 0.0


def test_a_hold_at_a_waypoint_stands_still() -> None:
    quad = threat(harrier_spec(), "contact-quad")
    held_route = [w.model_copy(update={"hold_s": 20.0}) for w in quad.route[:1]]
    waiting = quad.model_copy(update={"route": held_route})
    points = sample_route(waiting, 1.0)
    at_wp = [p for p in points if (p.x, p.y, p.z) == (
        held_route[0].position.x, held_route[0].position.y, held_route[0].position.z
    )]  # fmt: skip
    assert len(at_wp) >= 20 and all(p.vx == 0.0 for p in at_wp[1:])


# ----------------------------------------------------------------------------- coverage


def test_the_environment_follows_the_scenario_clock_and_weather() -> None:
    spec = harrier_spec()
    now = environment(spec, 0.0)
    assert now.condition == spec.world.weather.condition
    assert now.time_of_day_h == spec.world.start_time_of_day_h
    later = environment(spec, 3600.0)
    assert later.time_of_day_h == pytest.approx((spec.world.start_time_of_day_h + 1) % 24)


def test_the_hostile_quad_is_covered_by_the_radar_and_the_rf_receiver_late() -> None:
    spec = harrier_spec()
    cov = coverage_of(spec, threat(spec, "contact-quad"))
    assert cov.sensors == ("radar-1", "rf-1")
    assert cov.first_s is not None and 60 < cov.first_s < 90 and cov.last_s == 419.0


def test_birds_far_from_every_sensor_are_never_covered() -> None:
    spec = harrier_spec()
    cov = coverage_of(spec, threat(spec, "contact-bird-1"))
    assert (cov.first_s, cov.last_s, cov.sensors) == (None, None, ())


def test_coverage_uses_the_given_sensors_when_asked() -> None:
    spec = harrier_spec()
    radar_only = [s for s in build_sensors(spec).sensors if s.id == "radar-1"]
    cov = coverage_of(spec, threat(spec, "contact-quad"), radar_only)
    assert cov.sensors == ("radar-1",)


def test_terrain_hides_what_it_stands_between() -> None:
    spec = pack_scenario("heron-ridge-low-approach")
    quad = threat(spec, "contact-quad")
    cov = coverage_of(spec, quad)
    assert cov.first_s is not None
    terrain = terrain_for(spec.world.terrain)
    assert terrain is not None
    radar = next(s for s in build_sensors(spec).sensors if s.id == "radar-1")
    points = sample_route(quad, 1.0, spec.duration_s)
    seen = [p for p in points if covers(radar, spec, quad, p, terrain)]
    open_air = [p for p in points if covers(radar, spec, quad, p, None)]
    assert len(open_air) >= len(seen) and COVER_PD == 0.5


def test_a_point_outside_the_sensors_view_is_not_covered() -> None:
    spec = harrier_spec()
    quad = threat(spec, "contact-quad")
    radar = next(s for s in build_sensors(spec).sensors if s.id == "radar-1")
    far = sample_route(quad, 1.0)[0]
    assert not covers(radar, spec, quad, far, None)  # spawn is outside the radar's range


# ----------------------------------------------------------------------------- sim hooks


def test_the_operator_context_is_what_the_rules_are_asked_about() -> None:
    world = harrier_world()
    track = run_until_track(world, "contact-quad")
    world.step([act(world, "assess", track=track, identity="suspect")])
    ctx = world.operator_context(track)
    assert ctx.identity == "suspect" and ctx.classification is None
    assert ctx.zone_role in ("outer", "inner", None) and 0.0 <= ctx.confidence <= 1.0


def test_the_operator_context_needs_rules_and_a_live_track() -> None:
    world = harrier_world()
    with pytest.raises(ActionError, match="no live track"):
        world.operator_context("T999")
    bare = World(harrier_spec(), 1)
    with pytest.raises(ActionError, match="no rules of engagement"):
        bare.operator_context("T001")


def test_the_ledger_lists_every_label_bound_to_a_drone() -> None:
    world = harrier_world()
    track = run_until_track(world, "contact-quad")
    assert world.picture is not None
    ledger = world.picture.ledger
    label = ledger.label_of(track)
    assert label in ledger.bound_labels("contact-quad")
    assert ledger.bound_labels("no-such-drone") == []
