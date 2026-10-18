"""Acoustic sensor model: spreading and absorption, wind and rain noise, harmonics, range limit."""

import copy
import hashlib
import importlib
import json
import math
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

import sim.sensors.acoustic as acoustic_module
from app.contracts.common import PackRef, Vec3
from app.contracts.scenario import SensorPlacement
from sim.rng import RngStreams
from sim.sensors import (
    CueRequest,
    Degradation,
    Effects,
    ProfileError,
    build_sensors,
    load_sensor_profile,
    register_ids,
    suite,
)
from sim.sensors.detection import DRAWS_PER_CANDIDATE, Detection, Draws
from sim.world import World

from .sensor_rfac import (
    ACOUSTIC_FILE,
    LUCKY,
    PROFILE_DIR,
    REGISTER,
    SENSOR_ID,
    UNLUCKY,
    AcousticSensor,
    build,
    env,
    num,
    observe,
    q,
    scene,
    south_of,
    with_classes,
)
from .sim_cases import kestrel

API_DIR = Path(__file__).resolve().parents[1]
CLASSES = ("rotary-small", "fixed-wing-small", "bird", "autonomous-small")
RANGES = [float(r) for r in range(5, 301, 5)]


def mic(**over: dict[str, Any] | None) -> AcousticSensor:
    return build(AcousticSensor, ACOUSTIC_FILE, **over)


def sig(value: float | None) -> float:
    assert value is not None
    return value


def pd(s: AcousticSensor, class_id: str, range_m: float, **kwargs: Any) -> float:
    return s.p_detect(observe(s, class_id, range_m, **kwargs))


def snr(s: AcousticSensor, class_id: str, range_m: float, **kwargs: Any) -> float:
    return s.snr_db(observe(s, class_id, range_m, **kwargs))


def stream_position(rng: RngStreams) -> object:
    return rng.state()["sensors"]


def uniforms_consumed(n: int, seed: int = 7) -> object:
    rng = RngStreams(seed)
    for _ in range(n):
        rng.uniform("sensors")
    return stream_position(rng)


def lucky(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Draws, "take", classmethod(lambda cls, rng: LUCKY))


# ---------------------------------------------------------------------------- probability of detection


@pytest.mark.parametrize("class_id", CLASSES)
def test_pd_never_rises_with_range(class_id: str) -> None:
    s = mic()
    values = [pd(s, class_id, r) for r in RANGES]
    assert all(b <= a for a, b in zip(values, values[1:], strict=False))
    assert values[0] > values[-1]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"environment": env(wind=0.0)},
        {"environment": env(wind=9.0)},
        {"environment": env(condition="rain")},
        {"effects": Effects(noise_factor=3.0)},
    ],
)
def test_pd_never_rises_with_range_in_any_noise_condition(kwargs: dict[str, Any]) -> None:
    s = mic()
    values = [pd(s, "rotary-small", r, **kwargs) for r in RANGES]
    assert all(b <= a for a, b in zip(values, values[1:], strict=False))


def test_the_level_falls_by_spherical_spreading_plus_linear_absorption() -> None:
    s = mic()
    near, far = observe(s, "rotary-small", 50.0), observe(s, "rotary-small", 100.0)
    dropped = s.snr_db(near) - s.snr_db(far)
    spreading = 20.0 * math.log10(far.geometry.slant_range_m / near.geometry.slant_range_m)
    absorption = 5.0 * (far.geometry.slant_range_m - near.geometry.slant_range_m) / 1000.0
    assert dropped == pytest.approx(spreading + absorption, abs=1e-6)
    doubling = snr(s, "rotary-small", 40.0, z=0.0) - snr(s, "rotary-small", 80.0, z=0.0)
    assert 6.0 < doubling < 6.3


def test_a_noisier_class_is_heard_further_away() -> None:
    s = mic()
    assert pd(s, "rotary-small", 150.0) > pd(s, "fixed-wing-small", 150.0) > pd(s, "bird", 150.0)


def test_there_is_a_hard_range_limit_but_no_line_of_sight_requirement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lucky(monkeypatch)
    world, target = scene()
    beyond = build(AcousticSensor, ACOUSTIC_FILE, south_of(target, 301.0, z=target.z))
    assert beyond.detect(world, 200, world.rng) == []
    inside = build(AcousticSensor, ACOUSTIC_FILE, south_of(target, 120.0, z=target.z))
    assert len(inside.detect(world, 200, world.rng)) == 1
    # a sensor high above the target looks down steeply: no elevation limit, no sight line needed
    above = build(
        AcousticSensor, ACOUSTIC_FILE, Vec3(x=target.x, y=target.y - 60.0, z=target.z + 80.0)
    )
    found = above.detect(world, 200, world.rng)
    assert len(found) == 1 and found[0].elevation_deg < -40.0


# ---------------------------------------------------------------------------- wind, rain, time of day


def test_wind_lowers_pd_and_raises_the_noise_monotonically() -> None:
    s = mic()
    winds = [float(w) for w in range(0, 16)]
    levels = [s.noise_db(observe(s, "rotary-small", 100.0, environment=env(wind=w))) for w in winds]
    assert all(b > a for a, b in zip(levels, levels[1:], strict=False))
    for class_id in ("rotary-small", "fixed-wing-small"):
        values = [pd(s, class_id, 100.0, environment=env(wind=w)) for w in winds]
        assert all(b <= a for a, b in zip(values, values[1:], strict=False))
        assert values[-1] < 0.5 * values[0]
    assert snr(s, "rotary-small", 100.0, environment=env(wind=12.0)) < snr(
        s, "rotary-small", 100.0, environment=env(wind=2.0)
    )


def test_rain_adds_noise_and_other_weather_and_time_of_day_do_not() -> None:
    s = mic()
    clear = pd(s, "rotary-small", 120.0)
    assert pd(s, "rotary-small", 120.0, environment=env(condition="rain")) < clear - 0.05
    for kwargs in (
        {"condition": "fog"},
        {"condition": "haze", "visibility": 300.0},
        {"condition": "dust"},
        {"hour": 2.0, "daylight": 0.0},
        {"hour": 6.0, "daylight": 0.5},
        {"temperature": -20.0, "cloud": 100.0},
    ):
        assert pd(s, "rotary-small", 120.0, environment=env(**kwargs)) == clear, kwargs


def test_background_noise_and_array_gain_move_pd_in_the_obvious_direction() -> None:
    quiet = pd(mic(background_noise=q(30, "dB")), "rotary-small", 150.0)
    base = pd(mic(), "rotary-small", 150.0)
    busy = pd(mic(background_noise=q(48, "dB")), "rotary-small", 150.0)
    assert busy < base < quiet
    assert pd(mic(array_gain=q(6, "dB")), "rotary-small", 150.0) < base


# ---------------------------------------------------------------------------- the wind-noise degradation


def test_wind_noise_degradation_is_an_extra_noise_penalty_that_widens_sigmas() -> None:
    s = mic()
    clean = pd(s, "rotary-small", 100.0)
    half, full = s.degradation_effect("wind-noise", 0.5), s.degradation_effect("wind-noise", 1.0)
    assert half is not None and full is not None
    assert (
        pd(s, "rotary-small", 100.0, effects=full)
        < pd(s, "rotary-small", 100.0, effects=half)
        < clean
    )
    assert snr(s, "rotary-small", 100.0, effects=full) == pytest.approx(
        snr(s, "rotary-small", 100.0) - 12.0, abs=1e-9
    )
    assert s.degradation_effect("wind-noise", 0.0) == Effects()
    wide = s.measure(observe(s, "rotary-small", 80.0, effects=full))
    exact = s.measure(observe(s, "rotary-small", 80.0))
    assert sig(wide.sigma_azimuth_deg) == pytest.approx(
        sig(exact.sigma_azimuth_deg) * full.noise_factor
    )


def test_wind_noise_stacks_with_real_wind() -> None:
    s = mic()
    full = s.degradation_effect("wind-noise", 1.0)
    breezy = env(wind=8.0)
    assert (
        pd(s, "rotary-small", 80.0, environment=breezy, effects=full)
        < pd(s, "rotary-small", 80.0, environment=breezy)
        < pd(s, "rotary-small", 80.0)
    )


@pytest.mark.parametrize("kind", ["haze", "glare", "clutter", "interference"])
def test_other_degradation_kinds_do_not_affect_the_array(kind: str) -> None:
    s = mic()
    assert s.degradation_effect(kind, 1.0) is None
    s.inject(Degradation(SENSOR_ID, kind, 0))
    assert s.effects_at(0) == Effects()


def test_an_injected_wind_noise_window_applies_only_inside_it() -> None:
    s = mic()
    s.inject(Degradation(SENSOR_ID, "wind-noise", 100, 200, 1.0))
    assert s.effects_at(99) == Effects()
    assert s.effects_at(150).noise_factor > 1.0
    assert s.effects_at(200) == Effects()


# ---------------------------------------------------------------------------- measurements


def test_a_report_gives_a_coarse_bearing_and_no_range() -> None:
    s = mic()
    d = s.measure(observe(s, "rotary-small", 80.0))
    assert d.modality == "acoustic" and d.range_m is None and d.sigma_range_m is None
    assert d.radial_speed_mps is None and d.truth_id == "t-1"
    assert sig(d.sigma_azimuth_deg) == 12.0 and sig(d.sigma_elevation_deg) == 20.0
    assert d.reported_class == "rotary-small"


def test_blade_pass_frequency_is_blades_times_revolutions_per_second() -> None:
    s = mic()
    assert s.blade_pass_hz("rotary-small") == 200.0  # 2 blades x 6000 rpm / 60
    assert s.blade_pass_hz("fixed-wing-small") == 100.0
    assert s.blade_pass_hz("bird") == 12.0
    assert s.blade_pass_hz("mystery-craft") == 180.0  # default: 2 x 5400 / 60
    d = s.measure(observe(s, "rotary-small", 60.0))
    assert d.features["blade_pass_hz"] == 200.0  # zero noise draw


def test_the_unverified_bird_band_sits_below_the_drone_fundamentals() -> None:
    s = mic()
    assert 5.0 <= s.blade_pass_hz("bird") <= 20.0
    for class_id in ("rotary-small", "fixed-wing-small", "autonomous-small"):
        assert 50.0 <= s.blade_pass_hz(class_id) <= 400.0
    p = load_sensor_profile(ACOUSTIC_FILE)
    assert "rpm_bird" in p.unverified and not p.quantity("rpm_bird").verified


def test_the_blade_pass_estimate_is_noisy_and_never_negative() -> None:
    s = mic()
    plus = Draws(0.0, 0.0, (1.0, 1.0, 1.0, 1.0))
    minus = Draws(0.0, 0.0, (-1.0, -1.0, -1.0, -1.0))
    up = s.measure(observe(s, "rotary-small", 60.0, draws=plus))
    down = s.measure(observe(s, "rotary-small", 60.0, draws=minus))
    assert up.features["blade_pass_hz"] == 204.0 and down.features["blade_pass_hz"] == 196.0
    huge = mic(sigma_blade_pass=q(500, "Hz"))
    assert huge.measure(observe(huge, "bird", 20.0, draws=minus)).features["blade_pass_hz"] == 0.0
    near_snr = s.measure(observe(s, "rotary-small", 60.0)).features["snr_db"]
    assert up.features["snr_db"] == num(near_snr) + 1.5


def test_harmonics_grow_with_snr_up_to_the_class_cap() -> None:
    s = mic()
    counts = [s.harmonics_visible("rotary-small", float(x)) for x in range(0, 40)]
    assert counts[0] == 1 and counts[-1] == 6
    assert all(b >= a for a, b in zip(counts, counts[1:], strict=False))
    assert s.harmonics_visible("fixed-wing-small", 100.0) == 3
    assert s.harmonics_visible("bird", 100.0) == 1
    assert mic(harmonics_default=q(0, "count")).harmonics_visible("mystery-craft", 99.0) == 1


def test_the_tonal_flag_needs_a_harmonic_structure_and_enough_snr() -> None:
    s = mic()
    near = s.measure(observe(s, "rotary-small", 30.0)).features
    far = s.measure(observe(s, "rotary-small", 250.0)).features
    assert near["tonal"] is True and num(near["harmonics"]) >= 4
    assert far["harmonics"] == 1.0 and far["tonal"] is False
    bird = s.measure(observe(s, "bird", 5.0)).features
    assert bird["harmonics"] == 1.0 and bird["tonal"] is False


# ---------------------------------------------------------------------------- outages and cueing


def test_an_outage_silences_the_array_for_its_window_only(monkeypatch: pytest.MonkeyPatch) -> None:
    lucky(monkeypatch)
    world, target = scene()
    s = build(AcousticSensor, ACOUSTIC_FILE, south_of(target, 100.0, z=target.z))
    s.inject(Degradation(SENSOR_ID, "outage", 180, 220))
    assert s.detect(world, 200, world.rng) == []
    assert len(s.detect(world, 240, world.rng)) == 1


def test_a_sector_outage_blocks_only_its_bearings(monkeypatch: pytest.MonkeyPatch) -> None:
    lucky(monkeypatch)
    world, target = scene()
    pos = south_of(target, 100.0, z=target.z)  # the target bears 0 degrees
    blocked = build(AcousticSensor, ACOUSTIC_FILE, pos)
    blocked.inject(
        Degradation(SENSOR_ID, "sector-outage", 0, sector_from_deg=350, sector_to_deg=10)
    )
    clear = build(AcousticSensor, ACOUSTIC_FILE, pos)
    clear.inject(Degradation(SENSOR_ID, "sector-outage", 0, sector_from_deg=90, sector_to_deg=180))
    assert blocked.detect(world, 200, world.rng) == []
    assert len(clear.detect(world, 200, world.rng)) == 1


def test_the_array_cannot_be_cued() -> None:
    assert not AcousticSensor.supports_cue
    assert mic().cue(CueRequest(SENSOR_ID, 45.0), 0).reason == "this sensor cannot be cued"


def test_unlucky_rolls_miss_even_a_close_source(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Draws, "take", classmethod(lambda cls, rng: UNLUCKY))
    world, target = scene()
    s = build(AcousticSensor, ACOUSTIC_FILE, south_of(target, 20.0, z=target.z))
    assert pd(mic(), "rotary-small", 20.0) > 0.99
    assert s.detect(world, 200, world.rng) == []


# ---------------------------------------------------------------------------- draws, determinism, state


def test_every_candidate_takes_the_framework_budget_and_nothing_else() -> None:
    world, target = scene()
    expected = uniforms_consumed(DRAWS_PER_CANDIDATE)
    for distance in (40.0, 280.0, 9000.0):
        s = build(AcousticSensor, ACOUSTIC_FILE, south_of(target, distance, z=target.z))
        rng = RngStreams(7)
        s.detect(world, 200, rng)
        assert stream_position(rng) == expected, distance
    rng = RngStreams(7)
    mic().detect(World(kestrel(), 7), 0, rng)  # nothing flying, no false alarms from a mic array
    assert stream_position(rng) == uniforms_consumed(0)


def run_detections(seed: int, ticks: int = 400) -> list[dict[str, object]]:
    world, target = scene(seed=seed)
    s = build(AcousticSensor, ACOUSTIC_FILE, south_of(target, 110.0, z=target.z))
    s.inject(Degradation(SENSOR_ID, "wind-noise", 250, 300, 0.5))
    out: list[dict[str, object]] = []
    for _ in range(ticks):
        world.step()
        out += [d.payload() for d in s.detect(world, world.tick, world.rng)]
    return out


def test_outputs_are_deterministic_for_a_seed_and_differ_between_seeds() -> None:
    first = run_detections(7)
    assert len(first) > 10
    assert first == run_detections(7)
    assert first != run_detections(8)


DETERMINISM_SCRIPT = """
import hashlib, json
from tests.test_sensor_acoustic import run_detections
print(hashlib.sha256(json.dumps(run_detections(7), sort_keys=True).encode()).hexdigest())
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
    here = hashlib.sha256(json.dumps(run_detections(7), sort_keys=True).encode()).hexdigest()
    assert outputs[0] == outputs[1] == here


def test_restoring_sensor_and_stream_state_continues_exactly() -> None:
    world, target = scene()

    def make() -> AcousticSensor:
        s = build(AcousticSensor, ACOUSTIC_FILE, south_of(target, 110.0, z=target.z))
        s.inject(Degradation(SENSOR_ID, "wind-noise", 260, 330, 0.6))
        return s

    def advance(w: World, s: AcousticSensor, n: int) -> list[dict[str, object]]:
        out: list[dict[str, object]] = []
        for _ in range(n):
            w.step()
            out += [d.payload() for d in s.detect(w, w.tick, w.rng)]
        return out

    a = make()
    advance(world, a, 40)
    sensor_state = json.loads(json.dumps(a.state()))
    rng_state = copy.deepcopy(world.rng.state())
    tick = world.tick
    straight = advance(world, a, 200)

    world2, _ = scene(tick=tick)
    world2.rng.restore(rng_state)
    b = make()
    b.restore(sensor_state)
    resumed = advance(world2, b, 200)
    assert resumed and resumed == straight


# ---------------------------------------------------------------------------- profile and scenario


def test_the_shipped_profile_loads_with_the_register_and_reports_what_is_unverified() -> None:
    p = load_sensor_profile(ACOUSTIC_FILE, register=register_ids(REGISTER))
    assert (p.id, p.version, p.modality) == ("acoustic-generic-array", "1.0.0", "acoustic")
    assert p.profile.fictional
    assert set(p.unverified) == set(p.profile.parameters) | {"confusion:default"}
    sources = {q_.source_id for q_ in p.profile.parameters.values()} | {
        t.source_id for t in p.profile.confusion.values()
    }
    assert sources == {"D10", "D11", "D12", "F01"}
    assert p.profile.title.en and p.profile.title.hi and p.profile.notes is not None
    assert p.value("instrumented_range", "m") <= 300.0  # research: about 50 to 300 m


def test_the_shipped_confusion_table_is_row_normalised_and_covers_the_classes() -> None:
    p = load_sensor_profile(ACOUSTIC_FILE)
    table = p.profile.confusion["default"]
    for row in table.rows.values():
        assert sum(row) == pytest.approx(1.0, abs=1e-9)
    assert set(CLASSES) <= set(table.rows)
    assert set(table.labels) == {"rotary-small", "fixed-wing-small", "bird", "unknown"}
    for true_class, row in table.rows.items():  # each source is most often labelled as itself
        best = table.labels[row.index(max(row))]
        assert best == ("rotary-small" if true_class == "autonomous-small" else true_class)


def test_every_per_class_parameter_has_a_default() -> None:
    p = load_sensor_profile(ACOUSTIC_FILE)
    for prefix in acoustic_module.PER_CLASS:
        assert f"{prefix}_default" in p


def test_reported_classes_follow_the_confusion_table() -> None:
    s = mic()
    far_roll = Draws(0.0, 0.95, (0, 0, 0, 0))
    assert s.measure(observe(s, "rotary-small", 60.0, draws=far_roll)).reported_class == "unknown"
    assert s.measure(observe(s, "bird", 10.0)).reported_class == "rotary-small"
    mid = Draws(0.0, 0.7, (0, 0, 0, 0))
    assert s.measure(observe(s, "bird", 10.0, draws=mid)).reported_class == "bird"


def test_a_scenario_check_refuses_classes_the_profile_cannot_resolve() -> None:
    spec = with_classes(kestrel(), "rotary-small", "fixed-wing-small")
    mic().check_scenario(spec)
    with pytest.raises(ProfileError, match="rpm_default"):
        mic(rpm_rotary_small=None, rpm_default=None).check_scenario(spec)
    with pytest.raises(ProfileError, match="no row for mystery-craft"):
        mic().check_scenario(with_classes(spec, "mystery-craft", "rotary-small"))
    with pytest.raises(ProfileError, match="noise"):
        mic(background_noise=None)
    with pytest.raises(ProfileError, match="expected 'dB'"):
        pd(mic(array_gain=q(12, "m")), "rotary-small", 50.0)


def test_the_model_registers_itself_for_the_acoustic_modality(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(suite, "MODELS", {})
    reloaded = importlib.reload(acoustic_module)
    assert {"acoustic": reloaded.AcousticSensor} == suite.MODELS


def test_a_suite_built_from_a_scenario_runs_deterministically_and_hears_the_nearby_source() -> None:
    spec = with_classes(kestrel(), "rotary-small", "bird")
    spec = spec.model_copy(
        update={
            "sensors": [
                SensorPlacement(
                    id="mic-1",
                    profile=PackRef(id="acoustic-generic-array", version="1.0.0"),
                    position=Vec3(x=1300.0, y=1450.0, z=6.0),
                    boresight_deg=0.0,
                )
            ]
        }
    )

    def run() -> list[Detection]:
        sensors = build_sensors(
            spec, PROFILE_DIR, models={"acoustic": AcousticSensor}, register=register_ids(REGISTER)
        )
        world = World(spec, 5)
        found: list[Detection] = []
        for _ in range(4000):
            world.step()
            found.extend(sensors.detect(world))
        return found

    found = run()
    assert found and {d.truth_id for d in found} == {
        "contact-a"
    }  # it holds at a waypoint beside the mic
    assert all(d.range_m is None and d.modality == "acoustic" for d in found)
    assert [d.payload() for d in found] == [d.payload() for d in run()]
