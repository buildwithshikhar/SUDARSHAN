"""Radar model: signal model, micro-Doppler, clutter and false alarms, determinism, provenance."""

import copy
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from app.contracts import SensorProfile
from sim.rng import RngStreams
from sim.sensors import (
    MODELS,
    ConfusionMatrix,
    Degradation,
    Detection,
    Draws,
    Effects,
    ProfileError,
    SensorParams,
    build_sensors,
    register_ids,
)
from sim.sensors.radar import CLUTTER, RadarSensor
from sim.world import World

from .sensor_models import (
    CLASSES,
    PROFILE_DIR,
    RADAR,
    REGISTER,
    build,
    environment,
    observation,
    params_with,
    placement,
    raw,
    shipped,
    sweep,
)
from .sensor_toy import scene, south_of
from .sim_cases import kestrel

API_DIR = Path(__file__).resolve().parents[1]
CONDITIONS = ("clear", "haze", "fog", "dust", "rain")
#: The tick at which the radar (1.2 s update) is due and the scene's contact is flying.
DUE = 216
BUDGET = 18 + 4 * 8  # one candidate, plus four false-alarm slots of eight uniforms


def radar(params: SensorParams | None = None) -> RadarSensor:
    return build(RadarSensor, params or shipped(RADAR))


def radar_at(distance: float = 1000.0, params: SensorParams | None = None) -> RadarSensor:
    """A radar `distance` m due south of the scene's contact, at the contact's bearing 0."""
    world, truth = scene(tick=DUE)
    del world
    p = params or shipped(RADAR)
    return RadarSensor(placement(p, south_of(truth, distance)), p)


def uniforms_consumed(n: int, seed: int = 7) -> object:
    rng = RngStreams(seed)
    for _ in range(n):
        rng.uniform("sensors")
    return rng.state()["sensors"]


def pd(sensor: RadarSensor, **kw: float | str) -> float:
    return sensor.p_detect(observation(**kw))  # type: ignore[arg-type]


# ---------------------------------------------------------------------------- the model is wired


def test_the_model_registers_for_the_radar_modality() -> None:
    assert MODELS["radar"] is RadarSensor
    assert RadarSensor.modalities == ("radar",) and not RadarSensor.supports_cue


def test_a_radar_has_no_cue() -> None:
    from sim.sensors import CueRequest

    s = radar()
    assert not s.cue(CueRequest("s-1", 10.0), 0).accepted


# ---------------------------------------------------------------------------- probability of detection


@pytest.mark.parametrize("class_id", [*CLASSES, "unlisted-class"])
@pytest.mark.parametrize("condition", CONDITIONS)
@pytest.mark.parametrize(
    ("elevation", "radial"), [(1.0, 0.0), (1.0, -12.0), (25.0, 0.0), (8.0, 4.0)]
)
def test_pd_never_rises_with_range(
    class_id: str, condition: str, elevation: float, radial: float
) -> None:
    s = radar()
    values = [
        pd(
            s,
            class_id=class_id,
            slant_range_m=r,
            condition=condition,
            visibility_m=2500.0,
            elevation_deg=elevation,
            radial_speed_mps=radial,
        )
        for r in sweep(10.0, 15000.0, 20.0)
    ]
    assert all(0.0 <= v <= 1.0 for v in values)
    assert all(b <= a + 1e-12 for a, b in zip(values, values[1:], strict=False))
    assert values[0] > 0.99 and values[-1] < 0.05  # the sweep spans certain to hopeless


def test_pd_is_about_one_half_where_the_radar_equation_says() -> None:
    # 45 dB at 1 km for 0 dBsm, -16 dBsm, 13 dB threshold, no weather or clutter: R^-4 gives 2.51 km
    s = radar()
    p = pd(s, slant_range_m=2512.0, elevation_deg=90.0, radial_speed_mps=-12.0, aspect_deg=45.0)
    assert p == pytest.approx(0.5, abs=0.03)


def test_classes_order_by_cross_section_and_their_ranges_overlap() -> None:
    s = radar()
    near = {c: pd(s, class_id=c, slant_range_m=2500.0, elevation_deg=20.0) for c in CLASSES}
    assert near["bird"] < near["rotary-small"] < near["fixed-wing-small"]
    # radar cross-section alone cannot separate a bird from a small multirotor
    spans = {
        c: [s.effective_rcs_dbsm(c, a) for a in sweep(0.0, 180.0, 5.0)]
        for c in ("rotary-small", "bird")
    }
    assert min(spans["rotary-small"]) < max(spans["bird"])
    # published ranges: small multirotor -20 to -8 dBsm, bird -30 to -19 dBsm
    assert all(-20.0 <= v <= -8.0 for v in spans["rotary-small"])
    assert all(-30.0 <= v <= -19.0 for v in spans["bird"] + [max(spans["bird"])])


def test_aspect_changes_rcs_deterministically_within_the_swing() -> None:
    s = radar()
    base = shipped(RADAR).value("rcs_fixed_wing_small", "dBsm")
    swing = shipped(RADAR).value("aspect_swing_fixed_wing_small", "dB")
    values = [s.effective_rcs_dbsm("fixed-wing-small", a) for a in sweep(0.0, 360.0, 7.5)]
    assert max(values) == pytest.approx(base + swing) and min(values) == pytest.approx(base - swing)
    assert s.effective_rcs_dbsm("fixed-wing-small", 90.0) > s.effective_rcs_dbsm(
        "fixed-wing-small", 0.0
    )
    assert s.effective_rcs_dbsm("fixed-wing-small", 33.0) == s.effective_rcs_dbsm(
        "fixed-wing-small", 33.0
    )
    # an unlisted class uses the default figures
    assert s.effective_rcs_dbsm("kite", 90.0) == pytest.approx(
        shipped(RADAR).value("rcs_default") + shipped(RADAR).value("aspect_swing_default")
    )


def test_rain_and_low_visibility_lower_pd_and_clear_air_is_best() -> None:
    s = radar()
    at = {"slant_range_m": 2300.0, "elevation_deg": 20.0, "visibility_m": 5000.0}
    by_condition = [pd(s, condition=c, **at) for c in CONDITIONS]  # clear first, rain last
    assert by_condition == sorted(by_condition, reverse=True)
    assert by_condition[-1] < by_condition[0] - 0.01
    rain = [pd(s, condition="rain", **{**at, "visibility_m": v}) for v in (500, 1500, 5000, 20000)]
    assert rain == sorted(rain)  # worse visibility, lower Pd
    assert rain[0] < rain[-1]
    # clear air is not touched by visibility
    clear = [pd(s, condition="clear", **{**at, "visibility_m": v}) for v in (500, 20000)]
    assert clear[0] == clear[1]


def test_weather_loss_scales_with_range_and_is_bounded_in_visibility() -> None:
    s = radar()
    one_way = shipped(RADAR).value("loss_rain")
    loss = s.weather_loss_db(2000.0, environment("rain", 5000.0))
    assert loss == pytest.approx(2 * one_way * 2.0)  # two-way, 2 km, reference visibility
    assert s.weather_loss_db(2000.0, environment("rain", 1.0)) == pytest.approx(loss * 2.0)
    assert s.weather_loss_db(2000.0, environment("rain", 1e9)) == pytest.approx(loss * 0.5)
    assert s.weather_loss_db(4000.0, environment("rain", 5000.0)) == pytest.approx(loss * 2.0)


def test_a_condition_without_a_loss_figure_costs_nothing() -> None:
    plain = radar(params_with(RADAR, loss_dust=None))
    clear = pd(plain, condition="clear", slant_range_m=2500.0)
    assert pd(plain, condition="dust", slant_range_m=2500.0) == clear


def test_low_slow_small_targets_are_penalised_near_the_horizon() -> None:
    s = radar()
    at = {"slant_range_m": 2300.0}
    crossing = pd(s, elevation_deg=0.5, radial_speed_mps=0.0, **at)
    closing = pd(s, elevation_deg=0.5, radial_speed_mps=-12.0, **at)
    high_crossing = pd(s, elevation_deg=40.0, radial_speed_mps=0.0, **at)
    high_closing = pd(s, elevation_deg=40.0, radial_speed_mps=-12.0, **at)
    assert crossing < closing  # Doppler notch
    assert closing < high_closing  # ground clutter near the horizon
    assert crossing < high_crossing
    assert high_crossing == pytest.approx(high_closing, abs=1e-3)  # little clutter overhead
    # the notch is symmetric in the sign of the radial speed
    assert pd(s, elevation_deg=0.5, radial_speed_mps=1.0, **at) == pytest.approx(
        pd(s, elevation_deg=0.5, radial_speed_mps=-1.0, **at)
    )


def test_a_target_below_the_horizon_gets_the_full_clutter_exposure() -> None:
    s = radar()
    assert pd(s, elevation_deg=-3.0) == pd(s, elevation_deg=0.0)


# ---------------------------------------------------------------------------- micro-Doppler


def reports(
    sensor: RadarSensor, class_id: str, n: int = 200, range_m: float = 150.0
) -> list[Detection]:
    out = []
    for i in range(n):
        u = (i + 0.5) / n
        out.append(
            sensor.measure(
                observation(
                    class_id=class_id,
                    slant_range_m=range_m,
                    draws=Draws(u, u, (0.0, 0.0, 0.0, 0.5 - u)),
                )
            )
        )
    return out


def test_micro_doppler_separates_rotor_from_bird_where_rcs_overlaps() -> None:
    s = radar()
    rotary, bird = reports(s, "rotary-small"), reports(s, "bird")

    def count(ds: list[Detection], label: str) -> int:
        return sum(d.features["micro_doppler"] == label for d in ds)

    assert count(rotary, "rotor") > 0.8 * len(rotary) and count(rotary, "wing-beat") < 0.05 * 200
    assert count(bird, "wing-beat") > 0.7 * len(bird) and count(bird, "rotor") < 0.05 * 200
    rotor_hz = [
        d.features["md_modulation_hz"] for d in rotary if d.features["micro_doppler"] == "rotor"
    ]
    wing_hz = [
        d.features["md_modulation_hz"] for d in bird if d.features["micro_doppler"] == "wing-beat"
    ]
    assert rotor_hz and wing_hz
    assert min(h for h in rotor_hz if isinstance(h, float)) > 80.0
    assert max(h for h in wing_hz if isinstance(h, float)) < 40.0


def test_modulation_frequency_follows_the_label_with_bounded_jitter() -> None:
    p = shipped(RADAR)
    s = radar()
    for d in reports(s, "rotary-small") + reports(s, "bird"):
        label = d.features["micro_doppler"]
        if label == "none":
            assert "md_modulation_hz" not in d.features
            continue
        base = p.value("md_hz_rotor" if label == "rotor" else "md_hz_wing_beat", "Hz")
        hz = d.features["md_modulation_hz"]
        assert isinstance(hz, float) and abs(hz - base) <= base * p.value("md_hz_spread") * 0.51


def test_an_unresolved_signature_reports_none_and_a_more_confused_class() -> None:
    s = radar()
    far = observation(slant_range_m=3000.0, elevation_deg=20.0)
    p_hit = s.p_detect(far)
    hit = observation(
        slant_range_m=3000.0,
        elevation_deg=20.0,
        draws=Draws(0.999 * p_hit, 0.5, (0.0, 0.0, 0.0, 0.0)),
    )
    d = s.measure(hit)
    assert d.features == {"micro_doppler": "none"}
    assert d.reported_class == "fixed-wing-small"  # 'unresolved' row: rotary 0.44, fixed-wing 0.10
    close = s.measure(observation(slant_range_m=150.0, draws=Draws(0.5, 0.5, (0.0, 0.0, 0.0, 0.0))))
    assert close.reported_class == "rotary-small"  # resolved: the sharper 'default' row


def test_resolution_gets_less_likely_with_range() -> None:
    s = radar()
    probs = [
        s._resolve_probability(s.snr_db(observation(slant_range_m=r)))
        for r in sweep(100, 4000, 100)
    ]
    assert probs == sorted(probs, reverse=True) and probs[0] > 0.99 and probs[-1] < 0.1


def test_the_detect_draw_doubles_as_the_signature_draw_without_extra_randomness() -> None:
    # u = detect / p is uniform given a hit, so the label depends on the draw, not on a new number
    s = radar()
    cases = [
        s.measure(observation(slant_range_m=150.0, draws=Draws(u, 0.5, (0.0, 0.0, 0.0, 0.0))))
        for u in (0.05, 0.95)
    ]
    # rotary row [rotor 0.90, wing-beat 0.01, none 0.09]: the draw alone picks the label
    assert [c.features["micro_doppler"] for c in cases] == ["rotor", "none"]
    zero_p = s.measure(
        observation(slant_range_m=1.0e6, draws=Draws(0.5, 0.5, (0.0, 0.0, 0.0, 0.0)))
    )
    assert zero_p.features == {"micro_doppler": "none"}  # a direct call with p = 0 does not divide


# ---------------------------------------------------------------------------- measurement noise


def test_measurement_sigma_grows_as_snr_falls_within_bounds() -> None:
    s = radar()
    base = shipped(RADAR)
    sigmas = [
        s.measure(observation(slant_range_m=r, elevation_deg=30.0)).sigma_range_m
        for r in sweep(50.0, 6000.0, 250.0)
    ]
    assert all(x is not None for x in sigmas)
    clean = [x for x in sigmas if x is not None]
    assert clean == sorted(clean)
    assert clean[0] == pytest.approx(base.value("sigma_range") * 0.5)
    assert clean[-1] == pytest.approx(base.value("sigma_range") * 4.0)


def test_a_detection_carries_range_azimuth_elevation_and_radial_speed() -> None:
    s = radar()
    d = s.measure(observation(slant_range_m=1000.0, elevation_deg=12.0, radial_speed_mps=-9.0))
    assert d.modality == "radar" and d.truth_id == "tgt"
    assert d.range_m == pytest.approx(1000.0) and d.radial_speed_mps == pytest.approx(-9.0)
    assert d.azimuth_deg == pytest.approx(45.0) and d.elevation_deg == pytest.approx(12.0)
    assert None not in (d.sigma_range_m, d.sigma_azimuth_deg, d.sigma_elevation_deg)


# ---------------------------------------------------------------------------- provenance


def test_the_shipped_radar_profile_loads_against_the_register_and_lists_what_is_unverified() -> (
    None
):
    from sim.sensors import load_sensor_profile

    p = load_sensor_profile(PROFILE_DIR / RADAR, register=register_ids(REGISTER))
    assert (p.id, p.version, p.modality) == ("radar-generic-s", "0.2.0", "radar")
    assert {"rcs_bird", "md_hz_wing_beat", "confusion:default"} <= set(p.unverified)
    assert all(q.source_id in ("F01", "D14") for q in p.profile.parameters.values())
    assert all(not q.verified for q in p.profile.parameters.values())  # nothing extracted yet
    assert {t.source_id for t in p.profile.confusion.values()} == {"F01"}
    assert p.profile.fictional and p.profile.title.hi and p.profile.notes is not None


def test_every_shipped_radar_confusion_table_is_row_normalised() -> None:
    p = shipped(RADAR)
    for key in ("default", "unresolved", "micro_doppler"):
        matrix: ConfusionMatrix = p.confusion(key)
        assert set(matrix.classes) >= {*CLASSES, CLUTTER}
        for true_class in matrix.classes:
            assert sum(matrix.row(true_class)) == pytest.approx(1.0, abs=1e-9)


def test_resolved_classification_beats_unresolved_on_the_diagonal() -> None:
    p = shipped(RADAR)
    for c in CLASSES:
        resolved, unresolved = p.confusion("default"), p.confusion("unresolved")
        i = resolved.labels.index(c)
        assert resolved.row(c)[i] > unresolved.row(c)[i]


def test_a_profile_missing_a_parameter_or_a_clutter_row_is_refused() -> None:
    with pytest.raises(ProfileError, match="notch_depth"):
        radar(params_with(RADAR, notch_depth=None))
    data = copy.deepcopy(raw(RADAR))
    del data["confusion"]["micro_doppler"]["rows"][CLUTTER]
    with pytest.raises(ProfileError, match="micro_doppler.*clutter"):
        radar(SensorParams(SensorProfile.model_validate(data)))
    with pytest.raises(ProfileError, match="expected 'm'"):
        radar(
            params_with(
                RADAR,
                instrumented_range={
                    "value": 4.6,
                    "unit": "km",
                    "source_id": "F01",
                    "verified": False,
                },
            )
        )


def test_the_kestrel_scenario_builds_a_radar_from_the_shipped_profile() -> None:
    spec = kestrel()
    suite = build_sensors(spec, register=register_ids(REGISTER))
    sensor = suite["radar-1"]
    assert isinstance(sensor, RadarSensor) and sensor.params.version == "0.2.0"
    world = World(spec, 240117)
    found: list[Detection] = []
    while world.tick < 4000:
        world.step()
        found += suite.detect(world)
    assert any(not d.false_alarm for d in found)
    assert all(d.sensor_id == "radar-1" for d in found)


# ---------------------------------------------------------------------------- determinism and budget


@pytest.mark.parametrize(
    "case",
    ["detected", "clutter", "sector-blocked", "out of range", "far", "alarm-heavy"],
)
def test_the_radar_takes_a_fixed_number_of_draws_whatever_happens(case: str) -> None:
    world, _ = scene(tick=DUE)
    sensor = radar_at(distance=9000.0 if case == "out of range" else 1000.0)
    if case == "clutter":
        sensor.inject(Degradation("s-1", "clutter", 0, severity=1.0))
    if case == "sector-blocked":
        sensor.inject(Degradation("s-1", "sector-outage", 0, sector_from_deg=300, sector_to_deg=60))
    if case == "far":
        sensor = radar_at(distance=4400.0)
    if case == "alarm-heavy":
        sensor = radar_at(params=params_with(RADAR, false_alarm_rate=4.0))
    rng = RngStreams(7)
    sensor.detect(world, DUE, rng)
    assert rng.state()["sensors"] == uniforms_consumed(BUDGET), case


def test_nothing_is_drawn_between_updates() -> None:
    world, _ = scene(tick=DUE)
    rng = RngStreams(7)
    radar_at().detect(world, DUE + 1, rng)
    assert rng.state()["sensors"] == uniforms_consumed(0)


def run_suite(seed: int = 240117, ticks: int = 3000) -> list[dict[str, object]]:
    spec = kestrel()
    world, suite = World(spec, seed), build_sensors(spec)
    out: list[dict[str, object]] = []
    for _ in range(ticks):
        world.step()
        out += [d.payload() for d in suite.detect(world)]
    return out


def test_the_radar_is_deterministic_for_a_seed_and_differs_between_seeds() -> None:
    assert run_suite() == run_suite()
    assert run_suite() != run_suite(seed=1)


DETERMINISM_SCRIPT = """
import hashlib, json
from tests.test_sensor_radar import run_suite
print(hashlib.sha256(json.dumps(run_suite(), sort_keys=True).encode()).hexdigest())
"""


def test_radar_detections_are_identical_in_two_processes_with_different_hash_salts() -> None:
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
    here = hashlib.sha256(json.dumps(run_suite(), sort_keys=True).encode()).hexdigest()
    assert outputs[0] == outputs[1] == here


def test_restoring_the_radar_and_the_stream_continues_exactly() -> None:
    world, _ = scene(tick=DUE)

    def fresh() -> RadarSensor:
        s = radar_at(distance=1500.0)
        s.inject(Degradation("s-1", "clutter", 480, 960, 0.7))
        return s

    def advance(s: RadarSensor, w: World, start: int, n: int) -> list[dict[str, object]]:
        out: list[dict[str, object]] = []
        for k in range(n):
            out += [d.payload() for d in s.detect(w, start + 24 * k, w.rng)]
        return out

    a = fresh()
    advance(a, world, DUE, 10)
    saved = json.loads(json.dumps(a.state()))
    rng_state = copy.deepcopy(world.rng.state())
    straight = advance(a, world, DUE + 240, 30)

    world2, _ = scene(tick=DUE)
    world2.rng.restore(rng_state)
    b = fresh()
    b.restore(saved)
    resumed = advance(b, world2, DUE + 240, 30)
    assert resumed and resumed == straight


# ---------------------------------------------------------------------------- degradations


def test_clutter_lowers_pd_widens_noise_and_raises_the_false_alarm_factor() -> None:
    s = radar()
    p = shipped(RADAR)
    assert s.degradation_effect("clutter", 0.0) == Effects()
    fx = s.degradation_effect("clutter", 1.0)
    assert fx == Effects(
        pd_factor=1.0 - p.value("clutter_pd_loss"),
        noise_factor=1.0 + p.value("clutter_noise_gain"),
        clutter_factor=1.0 + p.value("clutter_false_alarm_gain"),
    )
    half = s.degradation_effect("clutter", 0.5)
    assert half is not None and fx is not None
    assert 1.0 > half.pd_factor > fx.pd_factor and half.clutter_factor < fx.clutter_factor
    s.inject(Degradation("s-1", "clutter", 10, 20, 1.0))
    assert s.effects_at(5) == Effects() and s.effects_at(10) == fx and s.effects_at(20) == Effects()


@pytest.mark.parametrize("kind", ["haze", "glare", "interference", "wind-noise"])
def test_other_degradation_kinds_do_not_touch_a_radar(kind: str) -> None:
    s = radar()
    assert s.degradation_effect(kind, 1.0) is None
    s.inject(Degradation("s-1", kind, 0, severity=1.0))
    assert s.effects_at(0) == Effects()


def test_clutter_reports_fewer_real_contacts_and_more_false_ones() -> None:
    def tally(inject: bool) -> tuple[int, int]:
        world, _ = scene(tick=DUE)
        s = radar_at(distance=2300.0)
        if inject:
            s.inject(Degradation("s-1", "clutter", 0, severity=1.0))
        found = [d for k in range(400) for d in s.detect(world, DUE + 24 * k, world.rng)]
        return sum(not d.false_alarm for d in found), sum(d.false_alarm for d in found)

    (real_clear, fa_clear), (real_clutter, fa_clutter) = tally(False), tally(True)
    assert real_clutter < real_clear
    assert fa_clutter > 3 * fa_clear > 0


def test_a_sector_outage_hides_targets_and_false_alarms_in_the_sector() -> None:
    world, _ = scene(tick=DUE)
    s = radar_at(distance=1000.0)  # contact bears 000
    s.inject(Degradation("s-1", "sector-outage", 0, sector_from_deg=300, sector_to_deg=60))
    blocked = [d for k in range(400) for d in s.detect(world, DUE + 24 * k, world.rng)]
    assert all(d.false_alarm for d in blocked)
    assert all(60.0 < d.azimuth_deg < 300.0 for d in blocked)  # sector 300 to 060 is dark
    open_sector = radar_at(distance=1000.0)
    seen = [d for k in range(400) for d in open_sector.detect(world, DUE + 24 * k, world.rng)]
    assert any(not d.false_alarm for d in seen) and any(
        d.azimuth_deg > 300 for d in seen if d.false_alarm
    )


def test_a_full_outage_silences_the_radar_including_false_alarms() -> None:
    world, _ = scene(tick=DUE)
    s = radar_at(distance=1000.0)
    s.inject(Degradation("s-1", "outage", DUE, DUE + 24 * 100))
    assert [d for k in range(100) for d in s.detect(world, DUE + 24 * k, world.rng)] == []
    assert any(s.detect(world, DUE + 24 * (100 + k), world.rng) for k in range(20))


# ---------------------------------------------------------------------------- false alarms


def test_false_alarms_look_like_real_contacts_and_stay_inside_coverage() -> None:
    world, _ = scene(tick=DUE)
    s = radar_at(distance=1000.0)
    found = [d for k in range(600) for d in s.detect(world, DUE + 24 * k, world.rng)]
    fa = [d for d in found if d.false_alarm]
    real = [d for d in found if not d.false_alarm]
    assert len(fa) > 50 and real
    shape = set(real[0].trainee_view())
    for d in fa:
        assert d.truth_id is None and set(d.trainee_view()) == shape
        assert (
            d.range_m is not None
            and 0.1 * s.instrumented_range_m <= d.range_m <= s.instrumented_range_m
        )
        assert d.radial_speed_mps is not None and abs(d.radial_speed_mps) <= 6.0
        assert -2.0 <= d.elevation_deg <= 38.0 and 0.0 <= d.azimuth_deg < 360.0
        assert d.reported_class in ("rotary-small", "fixed-wing-small", "bird", "unknown")
        assert "micro_doppler" in d.features
        assert None not in (d.sigma_range_m, d.sigma_azimuth_deg, d.sigma_elevation_deg)
    labels = {d.features["micro_doppler"] for d in fa}
    assert "none" in labels
    # clutter hugs the horizon: more low elevations than high ones
    low = sum(d.elevation_deg < 10.0 for d in fa)
    assert low > len(fa) - low


def test_false_alarm_slots_cap_the_plots_per_update() -> None:
    world, _ = scene(tick=DUE)
    s = radar_at(distance=9000.0, params=params_with(RADAR, false_alarm_rate=40.0))
    for k in range(20):
        assert len([d for d in s.detect(world, DUE + 24 * k, world.rng) if d.false_alarm]) == 4
