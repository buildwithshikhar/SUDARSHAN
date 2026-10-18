"""RF sensor model: link budget, silent emitters, band and hop features, confusers, degradations."""

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

import sim.sensors.rf as rf_module
from app.contracts.common import PackRef, Vec3
from app.contracts.scenario import SensorPlacement
from sim.rng import RngStreams
from sim.sensors import (
    Degradation,
    Effects,
    ProfileError,
    build_sensors,
    load_sensor_profile,
    register_ids,
    suite,
)
from sim.sensors.detection import DRAWS_PER_CANDIDATE, Detection, Draws
from sim.sensors.rf import BANDS, FALSE_ALARM_DRAWS
from sim.world import World

from .sensor_rfac import (
    LUCKY,
    PROFILE_DIR,
    REGISTER,
    RF_FILE,
    SENSOR_ID,
    UNLUCKY,
    RfSensor,
    build,
    env,
    observe,
    params_from,
    profile_data,
    q,
    scene,
    south_of,
    with_classes,
)
from .sim_cases import kestrel

API_DIR = Path(__file__).resolve().parents[1]
CLASSES = ("rotary-small", "fixed-wing-small")
SILENT = ("bird", "autonomous-small")
NO_ALARMS = {"false_alarm_slots": q(0, "count")}


def rf(**over: dict[str, Any] | None) -> RfSensor:
    return build(RfSensor, RF_FILE, **over)


def sig(value: float | None) -> float:
    assert value is not None
    return value


def pd(s: RfSensor, class_id: str, range_m: float, **kwargs: Any) -> float:
    return s.p_detect(observe(s, class_id, range_m, **kwargs))


def stream_position(rng: RngStreams) -> object:
    return rng.state()["sensors"]


def uniforms_consumed(n: int, seed: int = 7) -> object:
    rng = RngStreams(seed)
    for _ in range(n):
        rng.uniform("sensors")
    return stream_position(rng)


def lucky(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make every detection roll succeed with zero noise, whatever the stream says."""
    monkeypatch.setattr(Draws, "take", classmethod(lambda cls, rng: LUCKY))


RANGES = [float(r) for r in range(5, 3001, 25)]


# ---------------------------------------------------------------------------- probability of detection


@pytest.mark.parametrize("class_id", CLASSES)
def test_pd_never_rises_with_range(class_id: str) -> None:
    s = rf()
    values = [pd(s, class_id, r) for r in RANGES]
    assert all(b <= a for a, b in zip(values, values[1:], strict=False))
    assert values[0] > 0.99 and values[-1] < values[0]


def test_pd_never_rises_with_range_under_interference_or_rain() -> None:
    s = rf()
    fx = s.degradation_effect("interference", 0.7)
    for kwargs in ({"effects": fx}, {"environment": env(condition="rain")}):
        values = [pd(s, "rotary-small", r, **kwargs) for r in RANGES]
        assert all(b <= a for a, b in zip(values, values[1:], strict=False))


def test_received_power_follows_the_free_space_loss_law() -> None:
    s = rf()
    near, far = observe(s, "rotary-small", 500.0), observe(s, "rotary-small", 1000.0)
    dropped = s.received_dbm(near) - s.received_dbm(far)
    expected = 20.0 * math.log10(far.geometry.slant_range_m / near.geometry.slant_range_m)
    assert dropped == pytest.approx(expected, abs=1e-6)


def test_a_higher_band_loses_more_for_the_same_emitter() -> None:
    low = rf(band_rotary_small=q(1, "index"))
    high = rf(band_rotary_small=q(2, "index"))
    assert pd(high, "rotary-small", 2000.0) < pd(low, "rotary-small", 2000.0)


def test_weather_and_time_of_day_shift_pd_only_as_documented() -> None:
    s = rf()
    clear = pd(s, "rotary-small", 2200.0)
    rain = pd(s, "rotary-small", 2200.0, environment=env(condition="rain"))
    assert 0.0 < clear - rain < 0.01  # rain loss is real but negligible at these bands
    for kwargs in (
        {"condition": "fog"},
        {"condition": "dust"},
        {"condition": "haze", "visibility": 400.0},
        {"hour": 2.0, "daylight": 0.0},
        {"hour": 6.0, "daylight": 0.5},
        {"wind": 15.0},
        {"temperature": -20.0, "cloud": 100.0},
    ):
        assert pd(s, "rotary-small", 2200.0, environment=env(**kwargs)) == clear, kwargs


def test_interference_lowers_pd_and_stacked_injects_add_in_decibels() -> None:
    s = rf()
    clean = pd(s, "rotary-small", 1500.0)
    half = s.degradation_effect("interference", 0.5)
    full = s.degradation_effect("interference", 1.0)
    assert half is not None and full is not None
    assert (
        pd(s, "rotary-small", 1500.0, effects=full)
        < pd(s, "rotary-small", 1500.0, effects=half)
        < clean
    )
    margin = s.margin_db(observe(s, "rotary-small", 1500.0))
    assert s.margin_db(observe(s, "rotary-small", 1500.0, effects=full)) == pytest.approx(
        margin - 15.0, abs=1e-9
    )
    both = half.then(half)
    assert s.margin_db(observe(s, "rotary-small", 1500.0, effects=both)) == pytest.approx(
        s.margin_db(observe(s, "rotary-small", 1500.0, effects=full)), abs=1e-9
    )


def test_zero_severity_interference_changes_nothing() -> None:
    assert rf().degradation_effect("interference", 0.0) == Effects()


@pytest.mark.parametrize("kind", ["haze", "glare", "clutter", "wind-noise"])
def test_other_degradation_kinds_do_not_affect_rf(kind: str) -> None:
    s = rf()
    assert s.degradation_effect(kind, 1.0) is None
    s.inject(Degradation(SENSOR_ID, kind, 0))
    assert s.effects_at(0) == Effects()


# ---------------------------------------------------------------------------- RF-silent targets


@pytest.mark.parametrize("class_id", SILENT)
def test_a_silent_class_has_zero_pd_at_every_range_and_under_every_condition(class_id: str) -> None:
    s = rf()
    jam = s.degradation_effect("interference", 1.0)
    for r in RANGES:
        assert pd(s, class_id, r) == 0.0
        assert pd(s, class_id, r, effects=jam) == 0.0
        assert pd(s, class_id, r, environment=env(condition="rain")) == 0.0
    assert pd(s, class_id, 1.0) == 0.0


def test_a_silent_class_is_never_detected_even_when_every_roll_is_lucky(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lucky(monkeypatch)
    for class_id in SILENT:
        world, target = scene(class_id)
        s = build(RfSensor, RF_FILE, south_of(target, 100.0), **NO_ALARMS)
        assert s.detect(world, 200, world.rng) == []
    # control: the same set-up detects an emitter
    world, target = scene("rotary-small")
    s = build(RfSensor, RF_FILE, south_of(target, 100.0), **NO_ALARMS)
    assert len(s.detect(world, 200, world.rng)) == 1


def test_a_silent_class_stays_unseen_with_a_receiver_that_hears_everything(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Zero-power-floor profile: a vanishing noise floor, no SNR needed, absurdly strong emitters."""
    lucky(monkeypatch)
    over = {
        **NO_ALARMS,
        "noise_floor": q(-400, "dBm"),
        "required_snr": q(-100, "dB"),
        "emitter_power_bird": q(200, "dBm"),
        "emitter_power_autonomous_small": q(200, "dBm"),
    }
    s = rf(**over)
    assert pd(s, "rotary-small", 2999.0) == pytest.approx(1.0, abs=1e-9)
    for class_id in SILENT:
        assert pd(s, class_id, 1.0) == 0.0
        world, target = scene(class_id)
        loud = build(RfSensor, RF_FILE, south_of(target, 50.0), **over)
        assert loud.detect(world, 200, world.rng) == []


def test_an_unlisted_class_follows_the_default_emitter_flag() -> None:
    assert pd(rf(), "mystery-craft", 800.0) > 0.9
    assert pd(rf(emits_default=q(0, "flag")), "mystery-craft", 800.0) == 0.0


# ---------------------------------------------------------------------------- measurements


def test_a_report_gives_bearing_without_range_and_wide_sigmas() -> None:
    s = rf()
    d = s.measure(observe(s, "rotary-small", 800.0))
    assert d.modality == "rf" and d.truth_id == "t-1"
    assert d.range_m is None and d.sigma_range_m is None and d.radial_speed_mps is None
    assert d.azimuth_deg == pytest.approx(0.0, abs=1e-9) or d.azimuth_deg > 359.999
    assert sig(d.sigma_azimuth_deg) == 9.0 and sig(d.sigma_elevation_deg) == 18.0
    assert d.reported_class == "rotary-small"  # lucky classify draw takes the first label


def test_band_hop_pattern_and_signal_strength_features() -> None:
    s = rf()
    hopper = s.measure(observe(s, "rotary-small", 800.0))
    assert hopper.features["band"] == "2.4 GHz" and hopper.features["hopping"] is True
    assert hopper.features["hop_rate_hz"] == 80.0
    assert hopper.features["rssi_dbm"] == s.received_dbm(observe(s, "rotary-small", 800.0))
    fixed = s.measure(observe(s, "fixed-wing-small", 800.0))
    assert fixed.features["band"] == "900 MHz" and fixed.features["hopping"] is False
    assert "hop_rate_hz" not in fixed.features


def test_noise_moves_the_estimates_and_is_scaled_by_the_degradation() -> None:
    s = rf(sigma_hop_rate=q(5.0, "ratio"))
    draws = Draws(0.0, 0.0, (1.0, 1.0, 1.0, 1.0))
    base = s.measure(observe(s, "rotary-small", 800.0, draws=draws))
    exact = s.measure(observe(s, "rotary-small", 800.0))
    assert base.features["rssi_dbm"] == sig(exact.features["rssi_dbm"]) + 2.5  # type: ignore[operator]
    assert base.features["hop_rate_hz"] == 80.0 * (1.0 + 5.0)
    down = Draws(0.0, 0.0, (-1.0, -1.0, -1.0, -1.0))
    assert s.measure(observe(s, "rotary-small", 800.0, draws=down)).features["hop_rate_hz"] == 0.0
    jam = s.degradation_effect("interference", 1.0)
    assert jam is not None
    wide = s.measure(observe(s, "rotary-small", 800.0, effects=jam))
    assert sig(wide.sigma_azimuth_deg) == pytest.approx(9.0 * jam.noise_factor)
    assert sig(wide.sigma_azimuth_deg) > 5.0 * sig(exact.sigma_azimuth_deg)


@pytest.mark.parametrize(("index", "label"), [(i + 1, b[0]) for i, b in enumerate(BANDS)])
def test_the_band_plan_labels(index: int, label: str) -> None:
    s = rf(band_rotary_small=q(index, "index"))
    assert s.band("rotary-small")[0] == label
    assert s.measure(observe(s, "rotary-small", 500.0)).features["band"] == label


@pytest.mark.parametrize("index", [0, len(BANDS) + 1, -3])
def test_a_band_index_outside_the_plan_is_refused(index: int) -> None:
    with pytest.raises(ProfileError, match="band index"):
        rf(band_rotary_small=q(index, "index")).band("rotary-small")


# ---------------------------------------------------------------------------- confusers


def alarm_sensor(probability: float = 1.0, **over: dict[str, Any] | None) -> RfSensor:
    return rf(false_alarm_probability=q(probability, "ratio", "D09"), **over)


def empty_world() -> World:
    return World(kestrel(), 7)  # no drone has spawned at tick 0


def test_wifi_and_bluetooth_confusers_appear_as_contact_shaped_false_alarms() -> None:
    world, target = scene()
    s = build(
        RfSensor, RF_FILE, south_of(target, 800.0), false_alarm_probability=q(1.0, "ratio", "D09")
    )
    found = s.detect(world, 200, world.rng)
    real = [d for d in found if not d.false_alarm]
    fake = [d for d in found if d.false_alarm]
    assert len(real) <= 1 and len(fake) == 2  # two slots, probability 1
    labels = set(s.params.confusion().labels)
    for d in fake:
        assert d.truth_id is None and d.modality == "rf" and d.range_m is None
        assert d.reported_class in labels
        assert set(d.features) <= {"band", "rssi_dbm", "hopping", "hop_rate_hz"}
        assert {"band", "rssi_dbm", "hopping"} <= set(d.features)
        assert 0.0 <= d.azimuth_deg < 360.0 and 0.0 <= d.elevation_deg <= 25.0
        assert sig(d.sigma_azimuth_deg) == 9.0 and sig(d.sigma_elevation_deg) == 18.0
        assert d.features["hopping"] == ("hop_rate_hz" in d.features)
    if real:
        assert set(real[0].trainee_view()) == set(fake[0].trainee_view())


def test_confusers_are_mostly_labelled_as_the_wifi_bluetooth_class() -> None:
    s = alarm_sensor()
    world = empty_world()
    labels: dict[str | None, int] = {}
    bands: dict[object, int] = {}
    hops = 0
    for k in range(300):
        for d in s.detect(world, 20 * k, world.rng):
            labels[d.reported_class] = labels.get(d.reported_class, 0) + 1
            bands[d.features["band"]] = bands.get(d.features["band"], 0) + 1
            hops += bool(d.features["hopping"])
    total = sum(labels.values())
    assert total == 600
    assert labels["wifi-bluetooth"] > 0.6 * total and len(labels) > 1
    assert set(bands) == {"2.4 GHz", "5.8 GHz"} and bands["2.4 GHz"] > bands["5.8 GHz"]
    assert 0.3 * total < hops < 0.7 * total


def false_alarm_count(s: RfSensor, calls: int = 400) -> int:
    world = empty_world()
    return sum(len(s.detect(world, 20 * k, world.rng)) for k in range(calls))


def test_interference_raises_the_false_alarm_rate() -> None:
    quiet = alarm_sensor(0.1)
    noisy = alarm_sensor(0.1)
    noisy.inject(Degradation(SENSOR_ID, "interference", 0, severity=1.0))
    mild = alarm_sensor(0.1)
    mild.inject(Degradation(SENSOR_ID, "interference", 0, severity=0.2))
    base, mid, high = false_alarm_count(quiet), false_alarm_count(mild), false_alarm_count(noisy)
    assert 40 < base < 160  # 800 slot-calls at 10 per cent
    assert base < mid < high == 800  # severity 1 multiplies the rate beyond certainty


def test_the_false_alarm_hook_takes_a_fixed_number_of_draws() -> None:
    world = empty_world()
    for probability in (0.0, 0.3, 1.0):
        rng = RngStreams(7)
        alarm_sensor(probability).detect(world, 0, rng)
        assert stream_position(rng) == uniforms_consumed(2 * FALSE_ALARM_DRAWS), probability
    rng = RngStreams(7)
    rf(**NO_ALARMS).detect(world, 0, rng)
    assert stream_position(rng) == uniforms_consumed(0)


def test_a_blocked_sector_hides_false_alarms_without_changing_the_stream() -> None:
    world = empty_world()
    open_sky, blocked = alarm_sensor(), alarm_sensor()
    blocked.inject(
        Degradation(SENSOR_ID, "sector-outage", 0, sector_from_deg=0, sector_to_deg=359.9)
    )
    rng_a, rng_b = RngStreams(7), RngStreams(7)
    assert len(open_sky.detect(world, 0, rng_a)) == 2
    assert blocked.detect(world, 0, rng_b) == []
    assert stream_position(rng_a) == stream_position(rng_b)


def test_candidates_take_the_framework_budget_before_the_false_alarm_slots() -> None:
    world, target = scene()
    expected = uniforms_consumed(DRAWS_PER_CANDIDATE + 2 * FALSE_ALARM_DRAWS)
    for distance in (400.0, 9000.0):  # in range, and beyond the instrumented range
        for probability in (0.0, 1.0):
            s = build(
                RfSensor,
                RF_FILE,
                south_of(target, distance),
                false_alarm_probability=q(probability, "ratio", "D09"),
            )
            rng = RngStreams(7)
            s.detect(world, 200, rng)
            assert stream_position(rng) == expected, (distance, probability)


# ---------------------------------------------------------------------------- coverage and outages


def test_targets_beyond_the_instrumented_range_are_not_detected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lucky(monkeypatch)
    world, target = scene()
    far = build(RfSensor, RF_FILE, south_of(target, 3500.0), **NO_ALARMS)
    assert far.detect(world, 200, world.rng) == []


def test_an_outage_silences_detections_and_false_alarms_for_its_window_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lucky(monkeypatch)
    world, target = scene()
    s = build(
        RfSensor, RF_FILE, south_of(target, 600.0), false_alarm_probability=q(1.0, "ratio", "D09")
    )
    s.inject(Degradation(SENSOR_ID, "outage", 180, 220))
    assert s.detect(world, 200, world.rng) == []
    assert any(not d.false_alarm for d in s.detect(world, 240, world.rng))


def test_a_sector_outage_blocks_only_its_bearings(monkeypatch: pytest.MonkeyPatch) -> None:
    lucky(monkeypatch)
    world, target = scene()
    pos = south_of(target, 600.0)  # the target bears 0 degrees
    covered = build(RfSensor, RF_FILE, pos, **NO_ALARMS)
    covered.inject(
        Degradation(SENSOR_ID, "sector-outage", 0, sector_from_deg=350, sector_to_deg=10)
    )
    elsewhere = build(RfSensor, RF_FILE, pos, **NO_ALARMS)
    elsewhere.inject(
        Degradation(SENSOR_ID, "sector-outage", 0, sector_from_deg=90, sector_to_deg=180)
    )
    assert covered.detect(world, 200, world.rng) == []
    assert len(elsewhere.detect(world, 200, world.rng)) == 1


def test_the_rf_sensor_cannot_be_cued() -> None:
    from sim.sensors import CueRequest

    assert not RfSensor.supports_cue
    assert rf().cue(CueRequest(SENSOR_ID, 90.0), 0).reason == "this sensor cannot be cued"


# ---------------------------------------------------------------------------- determinism and state


def run_detections(seed: int, ticks: int = 400) -> list[dict[str, object]]:
    world, target = scene(seed=seed)
    s = build(
        RfSensor, RF_FILE, south_of(target, 1500.0), false_alarm_probability=q(0.3, "ratio", "D09")
    )
    s.inject(Degradation(SENSOR_ID, "interference", 250, 300, 0.4))
    out: list[dict[str, object]] = []
    for _ in range(ticks):
        world.step()
        out += [d.payload() for d in s.detect(world, world.tick, world.rng)]
    return out


def test_outputs_are_deterministic_for_a_seed_and_differ_between_seeds() -> None:
    first = run_detections(7)
    assert len(first) > 20
    assert first == run_detections(7)
    assert first != run_detections(8)
    assert any(d["truth_id"] is None for d in first) and any(d["truth_id"] for d in first)


DETERMINISM_SCRIPT = """
import hashlib, json
from tests.test_sensor_rf import run_detections
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

    def make() -> RfSensor:
        s = build(
            RfSensor,
            RF_FILE,
            south_of(target, 1500.0),
            false_alarm_probability=q(0.3, "ratio", "D09"),
        )
        s.inject(Degradation(SENSOR_ID, "interference", 260, 330, 0.6))
        return s

    def advance(w: World, s: RfSensor, n: int) -> list[dict[str, object]]:
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
    p = load_sensor_profile(RF_FILE, register=register_ids(REGISTER))
    assert (p.id, p.version, p.modality) == ("rf-generic-passive", "1.0.0", "rf")
    assert p.profile.fictional
    assert set(p.unverified) == set(p.profile.parameters) | {"confusion:default"}
    sources = {q_.source_id for q_ in p.profile.parameters.values()} | {
        t.source_id for t in p.profile.confusion.values()
    }
    assert sources == {"D08", "D09", "F01"}
    assert all(not q_.verified for q_ in p.profile.parameters.values())
    assert p.profile.title.en and p.profile.title.hi and p.profile.notes is not None


def test_the_shipped_confusion_table_is_row_normalised_and_covers_the_classes() -> None:
    p = load_sensor_profile(RF_FILE)
    table = p.profile.confusion["default"]
    for row in table.rows.values():
        assert sum(row) == pytest.approx(1.0, abs=1e-9)
    assert {*CLASSES, *SILENT, "wifi-bluetooth"} <= set(table.rows)
    assert {*CLASSES, "wifi-bluetooth", "unknown"} <= set(table.labels)
    for cls in SILENT:  # never sampled, but a scenario may contain them
        assert table.rows[cls][table.labels.index("unknown")] == 1.0


def test_every_per_class_parameter_has_a_default_and_the_silent_flags_are_set() -> None:
    p = load_sensor_profile(RF_FILE)
    for prefix in rf_module.PER_CLASS:
        assert f"{prefix}_default" in p
    assert [p.for_class("emits", c, "flag") for c in (*CLASSES, *SILENT)] == [1, 1, 0, 0]
    assert 1 <= p.value("band_rotary_small", "index") <= len(BANDS)


def test_reported_classes_follow_the_confusion_table() -> None:
    world, target = scene()
    s = build(RfSensor, RF_FILE, south_of(target, 500.0), **NO_ALARMS)
    d = s.measure(observe(s, "rotary-small", 500.0, draws=Draws(0.0, 0.95, (0, 0, 0, 0))))
    assert d.reported_class == "unknown"
    assert (
        s.measure(observe(s, "rotary-small", 500.0, draws=LUCKY)).reported_class == "rotary-small"
    )
    assert world.tick == 200


def test_a_profile_without_a_confuser_row_or_a_required_parameter_is_refused() -> None:
    data = profile_data(RF_FILE)
    del data["confusion"]["default"]["rows"]["wifi-bluetooth"]
    p = params_from(data)
    with pytest.raises(ProfileError, match="wifi-bluetooth"):
        RfSensor(
            SensorPlacement(
                id=SENSOR_ID,
                profile=PackRef(id=p.id, version=p.version),
                position=Vec3(x=0, y=0, z=0),
                boresight_deg=0.0,
            ),
            p,
        )
    with pytest.raises(ProfileError, match="noise_floor"):
        rf(noise_floor=None)
    with pytest.raises(ProfileError, match="expected 'dBm'"):
        pd(rf(noise_floor=q(-95, "dB")), "rotary-small", 100.0)


def test_a_scenario_check_refuses_classes_the_profile_cannot_resolve() -> None:
    spec = with_classes(kestrel(), "rotary-small", "fixed-wing-small")
    rf().check_scenario(spec)
    with pytest.raises(ProfileError, match="band index"):
        rf(band_rotary_small=q(9, "index")).check_scenario(spec)
    with pytest.raises(ProfileError, match="emits_default"):
        rf(emits_fixed_wing_small=None, emits_default=None).check_scenario(spec)
    with pytest.raises(ProfileError, match="no row for mystery-craft"):
        rf().check_scenario(with_classes(spec, "mystery-craft", "rotary-small"))


def test_the_model_registers_itself_for_the_rf_modality(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(suite, "MODELS", {})
    reloaded = importlib.reload(rf_module)
    assert {"rf": reloaded.RfSensor} == suite.MODELS


def test_a_suite_built_from_a_scenario_with_a_silent_class_never_sees_it() -> None:
    spec = with_classes(kestrel(), "autonomous-small", "rotary-small")
    spec = spec.model_copy(
        update={
            "sensors": [
                SensorPlacement(
                    id="rf-1",
                    profile=PackRef(id="rf-generic-passive", version="1.0.0"),
                    position=Vec3(x=0, y=0, z=6),
                    boresight_deg=0.0,
                )
            ]
        }
    )

    def run() -> list[Detection]:
        sensors = build_sensors(
            spec, PROFILE_DIR, models={"rf": RfSensor}, register=register_ids(REGISTER)
        )
        world = World(spec, 5)
        found: list[Detection] = []
        for _ in range(4000):
            world.step()
            found.extend(sensors.detect(world))
        return found

    found = run()
    real = [d for d in found if not d.false_alarm]
    assert real and {d.truth_id for d in real} == {"contact-b"}  # contact-a is the silent class
    assert [d.payload() for d in found] == [d.payload() for d in run()]


def test_unlucky_rolls_miss_even_a_strong_emitter(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Draws, "take", classmethod(lambda cls, rng: UNLUCKY))
    world, target = scene()
    s = build(RfSensor, RF_FILE, south_of(target, 50.0), **NO_ALARMS)
    assert pd(rf(), "rotary-small", 50.0) > 0.999
    assert s.detect(world, 200, world.rng) == []
