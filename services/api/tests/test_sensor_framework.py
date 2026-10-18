"""Sensor framework: geometry, the detect template, degradations, cueing, snapshot, the suite."""

import copy
import hashlib
import json
import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml

from app.contracts.common import Vec3
from sim.rng import RngStreams
from sim.sensors import (
    DRAWS_PER_CANDIDATE,
    MODELS,
    CueRequest,
    Degradation,
    Detection,
    Effects,
    Environment,
    Geometry,
    ProfileError,
    Sensor,
    SensorSuite,
    Truth,
    build_sensors,
    default_profile_dir,
    register_model,
)
from sim.sensors.geometry import daylight_at, truths
from sim.world import World

from .sensor_toy import (
    AlwaysDetects,
    LinearPd,
    NeverDetects,
    NoCueSensor,
    NoisyAlarms,
    ToySensor,
    make,
    placement,
    profile_data,
    q,
    scene,
    south_of,
    toy_params,
)
from .sim_cases import kestrel

API_DIR = Path(__file__).resolve().parents[1]


def at(x: float = 0.0, y: float = 0.0, z: float = 0.0, **v: float) -> Truth:
    return Truth("t", "rotary-small", x, y, z, v.get("vx", 0.0), v.get("vy", 0.0), v.get("vz", 0.0))


def sig(value: float | None) -> float:
    assert value is not None
    return value


def stream_position(rng: RngStreams) -> object:
    return rng.state()["sensors"]


def uniforms_consumed(n: int, seed: int = 7) -> object:
    rng = RngStreams(seed)
    for _ in range(n):
        rng.uniform("sensors")
    return stream_position(rng)


# ---------------------------------------------------------------------------- geometry

ORIGIN = Vec3(x=0, y=0, z=0)


@pytest.mark.parametrize(
    ("target", "azimuth"),
    [((0, 100), 0), ((100, 0), 90), ((0, -100), 180), ((-100, 0), 270), ((100, 100), 45)],
)
def test_azimuth_is_a_compass_bearing(target: tuple[float, float], azimuth: float) -> None:
    g = Geometry.between(ORIGIN, at(*target))
    assert g.azimuth_deg == pytest.approx(azimuth, abs=1e-12)
    assert 0.0 <= g.azimuth_deg < 360.0


def test_elevation_slant_and_ground_range() -> None:
    g = Geometry.between(ORIGIN, at(300, 400, 500))
    assert g.ground_range_m == 500.0
    assert g.elevation_deg == pytest.approx(45.0, abs=1e-12)
    assert g.slant_range_m == pytest.approx(500 * 2**0.5, abs=1e-9)
    below = Geometry.between(Vec3(x=0, y=0, z=100), at(0, 1000, 0))
    assert below.elevation_deg < 0


def test_a_target_overhead_has_a_defined_bearing_and_elevation() -> None:
    g = Geometry.between(ORIGIN, at(0, 0, 100))
    assert g.elevation_deg == pytest.approx(90.0, abs=1e-12)
    assert g.azimuth_deg == 0.0
    assert Geometry.between(ORIGIN, at(0, 0, 0)).slant_range_m == 0.0


@pytest.mark.parametrize(
    ("velocity", "radial", "aspect"),
    [
        ({"vy": -20.0}, -20.0, 0.0),  # flying straight at a sensor to the south
        ({"vy": 20.0}, 20.0, 180.0),  # flying straight away
        ({"vx": 20.0}, 0.0, 90.0),  # crossing
        ({}, 0.0, 90.0),  # hovering
    ],
)
def test_radial_speed_and_aspect(velocity: dict[str, float], radial: float, aspect: float) -> None:
    g = Geometry.between(ORIGIN, at(0, 1000, 0, **velocity))
    assert g.radial_speed_mps == pytest.approx(radial, abs=1e-9)
    assert g.aspect_deg == pytest.approx(aspect, abs=1e-6)
    assert g.ground_speed_mps == pytest.approx(
        (velocity.get("vx", 0) ** 2 + velocity.get("vy", 0) ** 2) ** 0.5
    )


def test_truths_are_the_active_drones_in_scenario_order_with_wind_applied() -> None:
    assert truths(World(kestrel(), 7)) == []  # nothing has spawned at tick 0
    world, first = scene(tick=200)
    assert [t.id for t in truths(world)] == ["contact-a"]
    drone = world.drones[0]
    wx, wy = world.wind()
    assert first.vx == pytest.approx(drone.ux * drone.airspeed + wx)
    assert first.class_id == "rotary-small"
    while world.tick < 2000:  # contact-b spawns at 95 s
        world.step()
    ids = [t.id for t in truths(world)]
    assert ids == sorted(ids) and "contact-b" in ids


# ---------------------------------------------------------------------------- environment


def test_daylight_ramps_through_twilight() -> None:
    assert [daylight_at(h) for h in (0.0, 5.5, 6.0, 6.5, 12.0, 17.5, 18.0, 18.5, 23.0)] == [
        0.0,
        0.0,
        0.5,
        1.0,
        1.0,
        1.0,
        0.5,
        0.0,
        0.0,
    ]


def test_environment_reads_the_modelled_weather_and_clock() -> None:
    world, _ = scene()
    env = Environment.of(world, 200)
    assert env.condition == "haze" and env.visibility_m == 4200
    assert env.wind_speed_mps > 0
    assert env.time_of_day_h == pytest.approx(5.75 + 200 / 20 / 3600)
    assert env.phase == "twilight" and 0.0 < env.daylight < 1.0
    later = Environment.of(world, 3600 * 20 * 24)  # wraps past midnight
    assert later.time_of_day_h == pytest.approx(5.75)
    noon = Environment.of(world, int(6.5 * 3600 * 20))
    assert noon.phase == "day" and noon.daylight == 1.0
    night = Environment.of(world, int(-5.0 * 3600 * 20) + 24 * 3600 * 20)
    assert night.phase == "night" and night.daylight == 0.0


# ---------------------------------------------------------------------------- construction


def test_a_sensor_is_built_from_its_placement_and_profile() -> None:
    _, truth = scene()
    s = make(ToySensor, truth)
    assert s.id == "toy-1" and s.period_ticks == 2 and s.instrumented_range_m == 5000
    assert s.pointing.azimuth_deg == 0.0 and s.pointing.fov_deg == 60.0


def test_a_profile_for_another_sensor_or_modality_is_refused() -> None:
    _, truth = scene()
    pos = south_of(truth)
    with pytest.raises(ProfileError, match="asks for"):
        ToySensor(placement(pos, version="2.0.0"), toy_params())
    wrong = copy.deepcopy(profile_data())
    wrong["modality"] = "rf"
    from app.contracts import SensorProfile
    from sim.sensors import SensorParams

    with pytest.raises(ProfileError, match="rf"):
        ToySensor(placement(pos), SensorParams(SensorProfile.model_validate(wrong)))


@pytest.mark.parametrize(
    "missing", ["instrumented_range", "update_interval", "sigma_range", "fov_wide"]
)
def test_missing_required_parameters_are_refused(missing: str) -> None:
    _, truth = scene()
    with pytest.raises(ProfileError, match=missing):
        ToySensor(placement(south_of(truth)), toy_params(**{missing: None}))


def test_a_cue_capable_sensor_needs_a_narrower_narrow_field() -> None:
    _, truth = scene()
    with pytest.raises(ProfileError, match="wider"):
        make(ToySensor, truth, fov_narrow=q(90, "deg"))


def test_a_declared_confusion_table_must_exist() -> None:
    _, truth = scene()
    data = profile_data()
    data["confusion"] = {}
    from app.contracts import SensorProfile
    from sim.sensors import SensorParams

    with pytest.raises(ProfileError, match="default"):
        ToySensor(placement(south_of(truth)), SensorParams(SensorProfile.model_validate(data)))


# ---------------------------------------------------------------------------- the detect template


def test_a_covered_target_is_detected_with_noisy_measurements_and_a_truth_link() -> None:
    world, truth = scene()
    s = make(AlwaysDetects, truth)
    (d,) = s.detect(world, 200, world.rng)
    g = Geometry.between(s.position, truth)
    assert d.truth_id == "contact-a" and not d.false_alarm
    assert d.sensor_id == "toy-1" and d.modality == "radar" and d.tick == 200
    assert d.azimuth_deg != g.azimuth_deg and d.range_m != g.slant_range_m
    bound = 2 * 3**0.5  # normalish is bounded at +-2 sqrt(3) sigma
    assert abs(d.azimuth_deg - g.azimuth_deg) <= bound * 1.0 + 1e-9
    assert d.range_m is not None and abs(d.range_m - g.slant_range_m) <= bound * 10.0 + 1e-9
    assert (d.sigma_range_m, d.sigma_azimuth_deg, d.sigma_elevation_deg) == (10.0, 1.0, 0.5)
    assert d.reported_class in ("rotary-small", "fixed-wing-small", "unknown")


def test_the_update_interval_gates_detection() -> None:
    world, truth = scene()
    s = make(AlwaysDetects, truth)  # 0.1 s, so every second tick
    hits = [t for t in range(200, 212) if s.detect(world, t, world.rng)]
    assert hits == [200, 202, 204, 206, 208, 210]


def test_probability_zero_never_detects_and_one_always_does() -> None:
    world, truth = scene()
    never, always = make(NeverDetects, truth), make(AlwaysDetects, truth)
    for t in range(200, 260, 2):
        assert never.detect(world, t, world.rng) == []
        assert len(always.detect(world, t, world.rng)) == 1


def test_detection_follows_the_model_probability() -> None:
    world, truth = scene()
    near = make(LinearPd, truth, distance=500.0)  # p = 0.9
    far = make(LinearPd, truth, distance=4500.0)  # p = 0.1
    n_near = sum(len(near.detect(world, t, world.rng)) for t in range(200, 2200, 2))
    n_far = sum(len(far.detect(world, t, world.rng)) for t in range(200, 2200, 2))
    assert n_near > 4 * n_far > 0


@pytest.mark.parametrize(
    ("kwargs", "why"),
    [
        ({"distance": 5200.0}, "beyond instrumented range"),
        ({"boresight": 180.0}, "outside the field of view"),
        ({"z": 400.0}, "below the minimum elevation"),
        ({"z": -400.0}, "above the maximum elevation"),
    ],
)
def test_targets_outside_coverage_are_not_detected(kwargs: dict[str, float], why: str) -> None:
    world, truth = scene()
    pos = Vec3(x=truth.x, y=truth.y - kwargs.get("distance", 1000.0), z=kwargs.get("z", 6.0))
    s = AlwaysDetects(placement(pos, kwargs.get("boresight", 0.0)), toy_params())
    if why.startswith("above"):
        s = AlwaysDetects(
            placement(Vec3(x=truth.x, y=truth.y - 100.0, z=truth.z - 400.0), 0.0), toy_params()
        )
    assert s.detect(world, 200, world.rng) == [], why


def test_every_candidate_takes_the_same_draws_whatever_happens_to_it() -> None:
    world, truth = scene()
    expected = uniforms_consumed(DRAWS_PER_CANDIDATE, seed=7)
    cases = {
        "detected": make(AlwaysDetects, truth),
        "missed": make(NeverDetects, truth),
        "out of range": make(AlwaysDetects, truth, distance=9000.0),
        "outage": make(AlwaysDetects, truth),
    }
    cases["outage"].inject(Degradation("toy-1", "outage", 0))
    for label, sensor in cases.items():
        rng = RngStreams(7)
        sensor.detect(world, 200, rng)
        assert stream_position(rng) == expected, label
    # off-interval ticks and an inactive world consume nothing
    rng = RngStreams(7)
    make(AlwaysDetects, truth).detect(world, 201, rng)
    assert stream_position(rng) == uniforms_consumed(0)


def test_the_draw_budget_is_sixteen_noise_plus_two_uniforms() -> None:
    assert DRAWS_PER_CANDIDATE == 18


def test_other_random_streams_are_untouched() -> None:
    world, truth = scene()
    before = {k: v for k, v in world.rng.state().items() if k != "sensors"}
    make(AlwaysDetects, truth).detect(world, 200, world.rng)
    after = {k: v for k, v in world.rng.state().items() if k != "sensors"}
    assert before == after


def test_outputs_are_deterministic_for_a_seed_and_differ_between_seeds() -> None:
    def run(seed: int) -> list[dict[str, object]]:
        world, truth = scene(seed=seed)
        s = make(AlwaysDetects, truth)
        out = []
        for _ in range(60):
            world.step()
            out += [d.payload() for d in s.detect(world, world.tick, world.rng)]
        return out

    assert run(7) == run(7)
    assert run(7) != run(8)


DETERMINISM_SCRIPT = """
import hashlib, json
from tests.sensor_toy import AlwaysDetects, make, scene
world, truth = scene()
s = make(AlwaysDetects, truth)
out = []
for _ in range(400):
    world.step()
    out += [d.payload() for d in s.detect(world, world.tick, world.rng)]
print(hashlib.sha256(json.dumps(out, sort_keys=True).encode()).hexdigest())
"""


def test_detections_are_identical_in_two_processes_with_different_hash_salts() -> None:
    outputs = []
    for salt in ("1", "2"):
        done = subprocess.run(  # noqa: S603 - fixed interpreter and script
            [sys.executable, "-c", DETERMINISM_SCRIPT],
            cwd=API_DIR,
            env=os.environ | {"PYTHONHASHSEED": salt},
            capture_output=True,
            text=True,
            check=True,
        )
        outputs.append(done.stdout.strip())
    world, truth = scene()
    s = make(AlwaysDetects, truth)
    out: list[dict[str, object]] = []
    for _ in range(400):
        world.step()
        out += [d.payload() for d in s.detect(world, world.tick, world.rng)]
    here = hashlib.sha256(json.dumps(out, sort_keys=True).encode()).hexdigest()
    assert outputs[0] == outputs[1] == here


# ---------------------------------------------------------------------------- detections


def test_the_trainee_view_never_carries_ground_truth_and_looks_the_same_for_false_alarms() -> None:
    world, truth = scene()
    (real,) = make(AlwaysDetects, truth).detect(world, 200, world.rng)
    false = Detection("toy-1", "radar", 200, None, 12.3456789, 2.0, features={"x": 1.23456})
    assert real.payload()["truth_id"] == "contact-a"
    assert "truth_id" not in real.trainee_view()
    assert "contact-a" not in json.dumps(real.trainee_view())
    assert false.false_alarm and set(false.trainee_view()) == set(real.trainee_view())
    assert false.trainee_view()["azimuth_deg"] == 12.346
    assert false.trainee_view()["features"] == {"x": 1.235}


# ---------------------------------------------------------------------------- false alarms


def test_false_alarms_come_from_the_model_hook_and_stop_in_an_outage() -> None:
    world, truth = scene()
    s = make(NoisyAlarms, truth)
    found = s.detect(world, 200, world.rng)
    assert len([d for d in found if d.false_alarm]) == 2 and len(found) == 3
    s.inject(Degradation("toy-1", "outage", 0))
    assert s.detect(world, 202, world.rng) == []


def test_an_outage_takes_the_same_draws_so_the_stream_never_shifts() -> None:
    world, truth = scene()

    def stream_after(outage: bool) -> list[float]:
        s = make(NoisyAlarms, truth)
        if outage:
            s.inject(Degradation("toy-1", "outage", 0))
        rng = RngStreams(7)
        s.detect(world, 200, rng)
        return [rng.uniform("sensors") for _ in range(3)]

    assert stream_after(True) == stream_after(False)


# ---------------------------------------------------------------------------- degradations


def test_degradation_windows_and_validation() -> None:
    d = Degradation("toy-1", "haze", 10, 20, 0.5)
    assert [d.active(t) for t in (9, 10, 19, 20)] == [False, True, True, False]
    assert Degradation("toy-1", "haze", 10).active(10_000_000)
    assert Degradation.from_state(d.to_state()) == d
    bad_ones: list[Callable[[], object]] = [
        lambda: Degradation("s", "fog-of-war", 0),
        lambda: Degradation("s", "haze", 0, severity=1.5),
        lambda: Degradation("s", "haze", 5, 5),
        lambda: Degradation("s", "haze", -1),
        lambda: Degradation("s", "sector-outage", 0),
        lambda: Degradation("s", "haze", 0, sector_from_deg=0, sector_to_deg=10),
    ]
    for bad in bad_ones:
        with pytest.raises(ValueError):
            bad()


def test_a_full_outage_silences_the_sensor_for_its_window_only() -> None:
    world, truth = scene()
    s = make(AlwaysDetects, truth)
    s.inject(Degradation("toy-1", "outage", 204, 208))
    hits = [t for t in range(200, 212, 2) if s.detect(world, t, world.rng)]
    assert hits == [200, 202, 208, 210]


def test_a_sector_outage_blocks_only_targets_inside_the_sector() -> None:
    world, truth = scene()
    blocked = make(AlwaysDetects, truth)  # target bears 0 deg
    blocked.inject(Degradation("toy-1", "sector-outage", 0, sector_from_deg=350, sector_to_deg=10))
    clear = make(AlwaysDetects, truth)
    clear.inject(Degradation("toy-1", "sector-outage", 0, sector_from_deg=20, sector_to_deg=60))
    assert blocked.detect(world, 200, world.rng) == []
    assert len(clear.detect(world, 200, world.rng)) == 1


def test_effects_combine_in_injection_order_and_sector_blocking_wraps() -> None:
    a = Effects(
        pd_factor=0.5, noise_factor=2.0, clutter_factor=3.0, blocked_sectors=((350.0, 10.0),)
    )
    b = Effects(outage=True, pd_factor=0.5, blocked_sectors=((100.0, 120.0),))
    c = a.then(b)
    assert (c.outage, c.pd_factor, c.noise_factor, c.clutter_factor) == (True, 0.25, 2.0, 3.0)
    assert [c.blocks(az) for az in (355, 0, 10, 11, 110, 130)] == [
        True,
        True,
        True,
        False,
        True,
        False,
    ]
    assert not Effects().blocks(0.0)


def test_modality_degradations_scale_probability_and_noise_and_unknown_kinds_are_ignored() -> None:
    world, truth = scene()
    base = make(AlwaysDetects, truth)
    (clean,) = base.detect(world, 200, RngStreams(7))

    hazy = make(AlwaysDetects, truth)
    hazy.inject(Degradation("toy-1", "haze", 0, severity=0.1))  # p = 0.9, noise x1.1
    (d,) = hazy.detect(world, 200, RngStreams(7))
    assert d.sigma_azimuth_deg == pytest.approx(sig(clean.sigma_azimuth_deg) * 1.1)
    assert d.sigma_range_m == pytest.approx(sig(clean.sigma_range_m) * 1.1)
    assert d.azimuth_deg != clean.azimuth_deg  # same draws, larger sigma, larger error

    total = make(AlwaysDetects, truth)
    total.inject(Degradation("toy-1", "haze", 0, severity=1.0))  # pd_factor 0
    assert total.detect(world, 200, world.rng) == []

    ignored = make(AlwaysDetects, truth)
    ignored.inject(Degradation("toy-1", "interference", 0))  # the toy model is not affected
    assert ignored.effects_at(5) == Effects()


def test_a_degradation_for_another_sensor_is_refused() -> None:
    _, truth = scene()
    with pytest.raises(ValueError, match="other"):
        make(ToySensor, truth).inject(Degradation("other", "outage", 0))


# ---------------------------------------------------------------------------- cueing


def test_a_cue_slews_at_the_profile_rate_by_the_short_way_round() -> None:
    _, truth = scene()
    s = make(ToySensor, truth, boresight=350.0, slew_rate=q(30, "deg/s"))
    assert s.cue(CueRequest("toy-1", 20.0), 0).accepted  # 30 deg clockwise, across north
    s._advance(10)  # 0.5 s -> 15 deg
    assert s.pointing.azimuth_deg == pytest.approx(5.0)
    s._advance(20)
    assert s.pointing.azimuth_deg == pytest.approx(20.0)


def test_without_a_slew_rate_pointing_is_immediate() -> None:
    _, truth = scene()
    s = make(ToySensor, truth, slew_rate=None)
    s.cue(CueRequest("toy-1", 123.0, 12.0), 0)
    s._advance(1)
    assert (s.pointing.azimuth_deg, s.pointing.elevation_deg) == (123.0, 12.0)


def test_a_narrow_cue_tightens_the_field_and_improves_precision_deterministically() -> None:
    world, truth = scene()

    def measure(request: CueRequest | None) -> Detection:
        s = make(AlwaysDetects, truth, slew_rate=None)
        if request:
            result = s.cue(request, 200)
            assert result.accepted
        (d,) = s.detect(world, 200, RngStreams(7))
        return d

    wide = measure(None)
    narrow = measure(CueRequest("toy-1", 0.0, kind="narrow"))
    assert wide.sigma_azimuth_deg == 1.0 and narrow.sigma_azimuth_deg == pytest.approx(10 / 60)
    assert sig(narrow.sigma_range_m) < sig(wide.sigma_range_m)
    again = measure(CueRequest("toy-1", 0.0, kind="narrow"))
    assert again == narrow  # same seed, same cue, same report


def test_a_narrow_cue_zooms_at_once_before_the_next_tick() -> None:
    _, truth = scene()
    s = make(ToySensor, truth)
    assert s.pointing.fov_deg == 60
    assert s.cue(CueRequest("toy-1", 0, kind="narrow"), 200).accepted
    assert s.pointing.fov_deg == 10


def test_narrowing_sets_the_requested_field_within_the_sensor_limits() -> None:
    _, truth = scene()
    s = make(ToySensor, truth)
    assert s.cue(CueRequest("toy-1", 0, kind="narrow"), 0).target.fov_deg == 10  # type: ignore[union-attr]
    assert s.cue(CueRequest("toy-1", 0, kind="narrow", fov_deg=25), 0).target.fov_deg == 25  # type: ignore[union-attr]
    assert s.cue(CueRequest("toy-1", 0, kind="narrow", fov_deg=2), 0).target.fov_deg == 10  # type: ignore[union-attr]
    assert s.cue(CueRequest("toy-1", 0, kind="narrow", fov_deg=500), 0).target.fov_deg == 60  # type: ignore[union-attr]
    # a plain slew keeps whatever field is set
    s.cue(CueRequest("toy-1", 0, kind="narrow", fov_deg=25), 0)
    assert s.cue(CueRequest("toy-1", 90), 0).target.fov_deg == 25  # type: ignore[union-attr]


def test_a_narrowed_field_stops_seeing_what_is_outside_it() -> None:
    world, truth = scene()
    s = make(AlwaysDetects, truth, slew_rate=None)
    assert len(s.detect(world, 200, world.rng)) == 1
    s.cue(CueRequest("toy-1", 40.0, kind="narrow"), 200)  # 10 deg field aimed 40 deg off
    assert s.detect(world, 202, world.rng) == []
    s.cue(
        CueRequest("toy-1", 0.0, elevation_deg=40.0, kind="narrow"), 202
    )  # right bearing, 36 deg high
    assert s.detect(world, 204, world.rng) == []
    s.cue(CueRequest("toy-1", 0.0, kind="narrow"), 204)
    assert len(s.detect(world, 206, world.rng)) == 1


def test_a_cue_expires_and_the_sensor_returns_home() -> None:
    _, truth = scene()
    s = make(ToySensor, truth, slew_rate=None, cue_hold=q(2, "s"))
    s.cue(CueRequest("toy-1", 90.0, kind="narrow"), 100)
    s._advance(139)
    assert s.pointing.azimuth_deg == 90.0 and s.pointing.fov_deg == 10
    s._advance(140)
    assert s.pointing.azimuth_deg == 0.0 and s.pointing.fov_deg == 60


def test_cues_that_cannot_be_honoured_are_rejected_with_a_reason() -> None:
    _, truth = scene()
    s = make(ToySensor, truth)
    assert s.cue(CueRequest("elsewhere", 0), 0).reason == "cue is for elsewhere, not toy-1"
    assert "elevation" in str(s.cue(CueRequest("toy-1", 0, elevation_deg=80), 0).reason)
    assert "elevation" in str(s.cue(CueRequest("toy-1", 0, elevation_deg=-20), 0).reason)
    s.inject(Degradation("toy-1", "outage", 0))
    assert s.cue(CueRequest("toy-1", 0), 0).reason == "sensor is out of service"
    assert (
        make(NoCueSensor, truth).cue(CueRequest("toy-1", 0), 0).reason
        == "this sensor cannot be cued"
    )
    assert not make(ToySensor, truth).cue(CueRequest("toy-1", 0, elevation_deg=80), 0).accepted


def test_time_cannot_run_backwards() -> None:
    _, truth = scene()
    s = make(ToySensor, truth)
    s._advance(50)
    with pytest.raises(ValueError, match="already advanced"):
        s._advance(49)


def test_sparse_updates_slew_by_the_elapsed_time() -> None:
    _, truth = scene()
    s = make(ToySensor, truth, slew_rate=q(10, "deg/s"))
    s.cue(CueRequest("toy-1", 90.0), 0)
    s._advance(100)  # 5 s later in one step
    assert s.pointing.azimuth_deg == pytest.approx(50.0)


# ---------------------------------------------------------------------------- snapshot


def test_restoring_sensor_and_stream_state_continues_exactly() -> None:
    world, truth = scene()
    a = make(AlwaysDetects, truth)
    a.inject(Degradation("toy-1", "haze", 230, 260, 0.3))
    a.cue(CueRequest("toy-1", 10.0, kind="narrow", fov_deg=40.0), 200)

    def advance(s: ToySensor, n: int) -> list[dict[str, object]]:
        out: list[dict[str, object]] = []
        for _ in range(n):
            world.step()
            out += [d.payload() for d in s.detect(world, world.tick, world.rng)]
        return out

    advance(a, 20)
    sensor_state = json.loads(json.dumps(a.state()))
    rng_state = copy.deepcopy(world.rng.state())
    tick = world.tick
    straight = advance(a, 80)

    world2, _ = scene(tick=tick)
    world2.rng.restore(rng_state)
    b = make(AlwaysDetects, truth)
    b.restore(sensor_state)
    resumed: list[dict[str, object]] = []
    for _ in range(80):
        world2.step()
        resumed += [d.payload() for d in b.detect(world2, world2.tick, world2.rng)]
    assert world2.tick == world.tick
    assert resumed and resumed == straight


def test_sensor_state_for_another_sensor_is_refused() -> None:
    _, truth = scene()
    s = make(ToySensor, truth)
    state = s.state()
    state["id"] = "other"
    with pytest.raises(ValueError, match="other"):
        s.restore(state)


# ---------------------------------------------------------------------------- suite and builder


def write_profile(directory: Path, **overrides: Any) -> None:
    (directory / "toy.v1.yaml").write_text(
        yaml.safe_dump(profile_data(**overrides), allow_unicode=True), encoding="utf-8"
    )


def scenario_with(*ids: str):  # type: ignore[no-untyped-def]
    spec = kestrel()
    sensors = [
        placement(Vec3(x=0, y=-100.0 * i, z=6), 0.0, sensor_id=sid) for i, sid in enumerate(ids)
    ]
    return spec.model_copy(update={"sensors": sensors})


def test_build_sensors_resolves_profiles_and_runs_the_suite(tmp_path: Path) -> None:
    write_profile(tmp_path)
    spec = scenario_with("toy-1", "toy-2")
    suite = build_sensors(spec, tmp_path, models={"radar": AlwaysDetects})
    assert [s.id for s in suite.sensors] == ["toy-1", "toy-2"]
    assert suite["toy-2"].id == "toy-2"
    world, _ = scene()
    world.spec  # noqa: B018 - the scene uses the same Kestrel scenario
    found = suite.detect(world)
    assert {d.sensor_id for d in found} <= {"toy-1", "toy-2"}


def test_the_suite_runs_sensors_in_scenario_order_and_is_deterministic(tmp_path: Path) -> None:
    write_profile(tmp_path, sigma_range=q(10, "m"), update_interval=q(0.05, "s"))
    spec = scenario_with("toy-1", "toy-2")

    def run() -> list[dict[str, object]]:
        suite = build_sensors(spec, tmp_path, models={"radar": AlwaysDetects})
        from sim.world import World

        world = World(spec.model_copy(update={"sensors": spec.sensors}), 11)
        out: list[dict[str, object]] = []
        for _ in range(400):
            world.step()
            out += [d.payload() for d in suite.detect(world)]
        return out

    first = run()
    assert first == run()
    ticks: dict[object, list[str]] = {}
    for d in first:
        ticks.setdefault(d["tick"], []).append(str(d["sensor_id"]))
    assert all(order == sorted(order) for order in ticks.values())


def test_building_fails_early_for_missing_models_profiles_and_class_rows(tmp_path: Path) -> None:
    write_profile(tmp_path)
    spec = scenario_with("toy-1")
    with pytest.raises(ProfileError, match="no sensor model for modality 'radar'"):
        build_sensors(spec, tmp_path, models={})
    with pytest.raises(ProfileError, match="no sensor profile toy-radar 1.0.0"):
        build_sensors(spec, tmp_path / "nowhere", models={"radar": AlwaysDetects})
    data = profile_data()
    del data["confusion"]["default"]["rows"]["fixed-wing-small"]
    (tmp_path / "toy.v1.yaml").write_text(
        yaml.safe_dump(data, allow_unicode=True), encoding="utf-8"
    )
    with pytest.raises(ProfileError, match="no row for fixed-wing-small"):
        build_sensors(spec, tmp_path, models={"radar": AlwaysDetects})


def test_building_checks_the_register_when_given_one(tmp_path: Path) -> None:
    write_profile(tmp_path)
    spec = scenario_with("toy-1")
    build_sensors(spec, tmp_path, models={"radar": AlwaysDetects}, register={"F01"})
    with pytest.raises(ProfileError, match="data register"):
        build_sensors(spec, tmp_path, models={"radar": AlwaysDetects}, register={"D01"})


def test_cues_and_degradations_are_routed_by_sensor_id(tmp_path: Path) -> None:
    write_profile(tmp_path)
    suite = build_sensors(
        scenario_with("toy-1", "toy-2"), tmp_path, models={"radar": AlwaysDetects}
    )
    assert suite.cue(CueRequest("toy-2", 90.0), 0).accepted
    assert suite["toy-2"].pointing.azimuth_deg == 0.0  # starts to slew on the next advance
    assert suite.cue(CueRequest("nope", 0.0), 0).reason == "no sensor 'nope'"
    suite.inject(Degradation("toy-1", "outage", 0))
    assert suite["toy-1"].effects_at(0).outage and not suite["toy-2"].effects_at(0).outage
    with pytest.raises(KeyError):
        suite.inject(Degradation("nope", "outage", 0))


def test_suite_state_round_trips_and_rejects_a_different_sensor_set(tmp_path: Path) -> None:
    write_profile(tmp_path)
    suite = build_sensors(
        scenario_with("toy-1", "toy-2"), tmp_path, models={"radar": AlwaysDetects}
    )
    suite.cue(CueRequest("toy-1", 45.0, kind="narrow"), 10)
    suite.inject(Degradation("toy-2", "haze", 5, 50, 0.4))
    state = json.loads(json.dumps(suite.state()))
    other = build_sensors(
        scenario_with("toy-1", "toy-2"), tmp_path, models={"radar": AlwaysDetects}
    )
    other.restore(state)
    assert other.state() == suite.state()
    with pytest.raises(ValueError, match="does not match"):
        build_sensors(scenario_with("toy-1"), tmp_path, models={"radar": AlwaysDetects}).restore(
            state
        )


def test_duplicate_sensor_ids_are_refused() -> None:
    _, truth = scene()
    with pytest.raises(ValueError, match="duplicate"):
        SensorSuite([make(ToySensor, truth), make(ToySensor, truth)])


def test_models_register_once_per_modality(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sim.sensors.suite.MODELS", dict(MODELS))
    from sim.sensors import suite

    class Spare(ToySensor):
        modalities = ("spare",)  # not a real modality, so this holds once every model registers

    assert register_model(Spare) is Spare and suite.MODELS["spare"] is Spare
    with pytest.raises(ValueError, match="already registered"):
        register_model(Spare)


def test_importing_the_package_registers_the_four_modality_models() -> None:
    assert {"radar", "eo", "ir", "rf", "acoustic"} <= set(MODELS)


def test_the_default_profile_directory_holds_the_shipped_profiles() -> None:
    assert (default_profile_dir() / "radar-generic-s.v1.yaml").is_file()


# ---------------------------------------------------------------------------- defaults


class BareSensor(ToySensor):
    """A model that overrides only the two required methods."""

    supports_cue = False
    fixed_pd = 1.0
    false_alarms = Sensor.false_alarms
    degradation_effect = Sensor.degradation_effect
    precision_factor = Sensor.precision_factor


def test_optional_hooks_default_to_no_false_alarms_no_response_and_full_precision() -> None:
    world, truth = scene()
    s = make(BareSensor, truth, fov_wide=None, fov_narrow=None, slew_rate=None)
    s.inject(Degradation("toy-1", "haze", 0))
    assert s.effects_at(0) == Effects()
    assert s.precision_factor() == 1.0
    found = s.detect(world, 200, world.rng)
    assert len(found) == 1 and not found[0].false_alarm


def test_a_sensor_with_no_pointed_field_covers_every_bearing() -> None:
    world, truth = scene()
    s = make(BareSensor, truth, fov_wide=None, fov_narrow=None, boresight=180.0)
    assert s.pointing.fov_deg is None and len(s.detect(world, 200, world.rng)) == 1


def test_a_camera_reports_its_pixel_count_for_the_console_and_a_radar_does_not() -> None:
    from tests.live_helpers import harrier_world

    world = harrier_world()
    assert world.picture is not None
    views = {v["id"]: v for v in (s.view(0) for s in world.picture.suite.sensors)}
    assert views["eo-1"]["pixels_h"] == 1920
    assert views["radar-1"]["pixels_h"] is None
