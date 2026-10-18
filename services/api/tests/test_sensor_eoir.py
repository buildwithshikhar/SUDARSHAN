"""EO/IR model: Johnson criteria, light and visibility, cueing, degradations, determinism."""

import copy
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from app.contracts.common import PackRef, Vec3
from app.contracts.scenario import ScenarioSpec, SensorPlacement
from sim.rng import RngStreams
from sim.sensors import (
    MODELS,
    CueRequest,
    Degradation,
    Detection,
    Draws,
    Effects,
    Geometry,
    ProfileError,
    SensorParams,
    build_sensors,
    load_sensor_profile,
    register_ids,
)
from sim.sensors.eoir import EoIrSensor
from sim.sensors.geometry import truths
from sim.world import World

from .sensor_models import (
    CLASSES,
    EO_DAY,
    EO_NV,
    PROFILE_DIR,
    REGISTER,
    THERMAL,
    bisect,
    build,
    observation,
    params_with,
    placement,
    shipped,
    sweep,
)
from .sensor_toy import scene
from .sim_cases import kestrel

API_DIR = Path(__file__).resolve().parents[1]
FILES = (EO_DAY, EO_NV, THERMAL)
CONDITIONS = ("clear", "haze", "fog", "dust", "rain")
#: The camera updates every 4 ticks; this tick is due and the scene's contact is flying.
DUE = 200
DT = 4


def camera(name: str = THERMAL, params: SensorParams | None = None) -> EoIrSensor:
    return build(EoIrSensor, params or shipped(name))


def camera_at(
    distance: float = 200.0, params: SensorParams | None = None, name: str = THERMAL
) -> EoIrSensor:
    """A camera `distance` m due south of the scene's contact, level with it, so it bears 000/0."""
    _, truth = scene(tick=DUE)
    p = params or shipped(name)
    return EoIrSensor(placement(p, Vec3(x=truth.x, y=truth.y - distance, z=truth.z)), p)


def settle(sensor: EoIrSensor, world: World, t: int) -> None:
    """Run one update so a cue's pointing and zoom take effect (a throwaway random stream)."""
    sensor.detect(world, t, RngStreams(0))


def pd(sensor: EoIrSensor, **kw: float | str) -> float:
    return sensor.p_detect(observation(**kw))  # type: ignore[arg-type]


def uniforms_consumed(n: int, seed: int = 7) -> object:
    rng = RngStreams(seed)
    for _ in range(n):
        rng.uniform("sensors")
    return rng.state()["sensors"]


# ---------------------------------------------------------------------------- the model is wired


def test_the_model_registers_for_eo_and_ir_and_supports_cues() -> None:
    assert MODELS["eo"] is EoIrSensor and MODELS["ir"] is EoIrSensor
    assert EoIrSensor.supports_cue and EoIrSensor.modalities == ("eo", "ir")
    assert [camera(f).params.modality for f in FILES] == ["eo", "eo", "ir"]


# ---------------------------------------------------------------------------- Johnson criteria


@pytest.mark.parametrize("name", FILES)
def test_apparent_size_is_size_over_range_times_ifov(name: str) -> None:
    s = camera(name)
    p = shipped(name)
    ifov = p.value("fov_wide") * (3.141592653589793 / 180.0) / p.value("pixels_h")
    for class_id in (*CLASSES, "kite"):
        size = p.for_class("size", class_id)
        for r in (25.0, 100.0, 400.0):
            assert s.geometric_px(class_id, r) == pytest.approx(size / (r * ifov))
    assert s.ifov_rad() == pytest.approx(ifov)


def test_the_research_section_camera_reaches_the_cited_ranges() -> None:
    # 320 x 256, 24 deg thermal: drone detection about 60 m and recognition about 20 m, bird
    # about 120 m and 40 m (docs/02-research.md section 2), in clear air
    s = camera(THERMAL)
    for class_id, detect_m, recognise_m in (("rotary-small", 60.0, 20.0), ("bird", 120.0, 40.0)):
        r50 = bisect(
            lambda r, c=class_id: pd(s, class_id=c, slant_range_m=r, visibility_m=1e6),
            1.0,
            2000.0,
            0.5,
        )
        px = shipped(THERMAL).value("johnson_detect_px")
        assert r50 == pytest.approx(detect_m, rel=0.05)
        assert s.effective_px(
            observation(class_id=class_id, slant_range_m=r50, visibility_m=1e6)
        ) == (pytest.approx(px, rel=0.01))
        r15 = bisect(
            lambda r, c=class_id: s.effective_px(
                observation(class_id=c, slant_range_m=r, visibility_m=1e6)
            ),
            1.0,
            2000.0,
            shipped(THERMAL).value("johnson_recognise_px"),
        )
        assert r15 == pytest.approx(recognise_m, rel=0.05)
        assert s.recognised(
            observation(class_id=class_id, slant_range_m=0.9 * r15, visibility_m=1e6)
        )
        assert not s.recognised(
            observation(class_id=class_id, slant_range_m=1.1 * r15, visibility_m=1e6)
        )


@pytest.mark.parametrize("name", FILES)
@pytest.mark.parametrize("class_id", [*CLASSES, "kite"])
@pytest.mark.parametrize("daylight", [0.0, 0.5, 1.0])
@pytest.mark.parametrize(
    ("condition", "visibility"), [("clear", 20000.0), ("haze", 3000.0), ("fog", 400.0)]
)
def test_pd_never_rises_with_range(
    name: str, class_id: str, daylight: float, condition: str, visibility: float
) -> None:
    s = camera(name)
    values = [
        pd(
            s,
            class_id=class_id,
            slant_range_m=r,
            daylight=daylight,
            condition=condition,
            visibility_m=visibility,
        )
        for r in sweep(2.0, 6000.0, 4.0)
    ]
    assert all(0.0 <= v <= 1.0 for v in values)
    assert all(b <= a + 1e-12 for a, b in zip(values, values[1:], strict=False))


@pytest.mark.parametrize("fov", [24.0, 12.0, 6.0])
def test_pd_never_rises_with_range_at_any_zoom(fov: float) -> None:
    s = camera_at()
    s.cue(CueRequest("s-1", 0.0, kind="narrow", fov_deg=fov), DUE)
    values = [pd(s, slant_range_m=r) for r in sweep(2.0, 3000.0, 4.0)]
    assert all(b <= a + 1e-12 for a, b in zip(values, values[1:], strict=False))
    assert values[0] > 0.99 and values[-1] < 0.01


# ---------------------------------------------------------------------------- light and weather


@pytest.mark.parametrize("name", FILES)
def test_worse_visibility_never_helps(name: str) -> None:
    s = camera(name)
    r50 = bisect(lambda r: pd(s, slant_range_m=r), 1.0, 6000.0, 0.5)
    by_visibility = [pd(s, slant_range_m=r50, visibility_m=v) for v in (200, 800, 3000, 20000, 1e6)]
    assert by_visibility == sorted(by_visibility)
    assert by_visibility[0] < by_visibility[-1] - 0.1


def test_thermal_loses_less_to_haze_than_visible_light() -> None:
    def retained(name: str) -> float:
        s = camera(name)
        r = bisect(lambda x: pd(s, slant_range_m=x, visibility_m=20000.0), 1.0, 6000.0, 0.5)
        return pd(s, slant_range_m=r, visibility_m=600.0) / pd(
            s, slant_range_m=r, visibility_m=20000.0
        )

    # compare at the same optical conditions; transmission is the only difference per range
    thermal, day = camera(THERMAL), camera(EO_DAY)
    assert thermal.transmission(200.0, 600.0) > day.transmission(200.0, 600.0)
    assert thermal.transmission(200.0, 1e9) == pytest.approx(1.0, abs=1e-4)
    assert retained(THERMAL) > retained(EO_DAY)


def test_transmission_is_beer_lambert() -> None:
    s = camera(EO_DAY)
    t1, t2 = s.transmission(300.0, 4000.0), s.transmission(600.0, 4000.0)
    assert t2 == pytest.approx(t1 * t1)  # exp(-beta r) is multiplicative along the path
    assert s.transmission(4000.0, 4000.0) == pytest.approx(0.02, abs=2e-4)  # Koschmieder, 2 %
    assert s.transmission(100.0, 0.0) < 1.0  # zero visibility is held at 1 m, not divided by


def test_night_collapses_day_eo_helps_nv_partly_and_does_not_touch_thermal() -> None:
    def ratio(name: str) -> float:
        s = camera(name)
        r = bisect(lambda x: pd(s, slant_range_m=x, daylight=1.0), 1.0, 6000.0, 0.5)
        return pd(s, slant_range_m=r, daylight=0.0) / pd(s, slant_range_m=r, daylight=1.0)

    day, nv, thermal = ratio(EO_DAY), ratio(EO_NV), ratio(THERMAL)
    assert day < 0.01 < nv < 0.9 and thermal == pytest.approx(1.0)
    assert day < nv < thermal


def test_with_the_same_optics_night_ranks_day_below_night_vision_below_thermal() -> None:
    modes = {
        "day": camera(params=params_with(THERMAL, low_light_floor=0.03)),
        "nv": camera(params=params_with(THERMAL, low_light_floor=0.7)),
        "thermal": camera(THERMAL),
    }
    night = {m: pd(s, slant_range_m=55.0, daylight=0.0) for m, s in modes.items()}
    assert night["day"] < night["nv"] < night["thermal"]
    sunny = {m: pd(s, slant_range_m=55.0, daylight=1.0) for m, s in modes.items()}
    assert sunny["day"] == sunny["nv"] == sunny["thermal"]


def test_twilight_sits_between_night_and_day_for_light_dependent_cameras() -> None:
    for name in (EO_DAY, EO_NV):
        s = camera(name)
        r = bisect(lambda x, s=s: pd(s, slant_range_m=x), 1.0, 6000.0, 0.5)
        night, dusk, day = (pd(s, slant_range_m=r, daylight=d) for d in (0.0, 0.5, 1.0))
        assert night < dusk < day
    thermal = camera(THERMAL)
    assert pd(thermal, slant_range_m=55.0, daylight=0.0) == pd(
        thermal, slant_range_m=55.0, daylight=1.0
    )


def test_light_factor_interpolates_from_the_floor() -> None:
    s = camera(EO_NV)
    floor = shipped(EO_NV).value("low_light_floor")
    assert s.light_factor(0.0) == floor and s.light_factor(1.0) == 1.0
    assert s.light_factor(0.5) == pytest.approx((1.0 + floor) / 2.0)


# ---------------------------------------------------------------------------- classification


def test_recognised_targets_use_the_sharper_table_and_distant_ones_the_confused_one() -> None:
    s = camera(THERMAL)
    draws = Draws(0.0, 0.5, (0.0, 0.0, 0.0, 0.0))
    near = s.measure(observation(slant_range_m=10.0, draws=draws))
    far = s.measure(observation(slant_range_m=40.0, draws=draws))
    assert near.features["recognised"] is True and far.features["recognised"] is False
    assert near.reported_class == "rotary-small"  # default row: rotary 0.85
    assert far.reported_class == "bird"  # distant row [0.35, 0.12, 0.20, 0.33]: 0.5 lands on bird
    assert isinstance(near.features["apparent_px"], float)
    assert near.features["apparent_px"] > far.features["apparent_px"]  # type: ignore[operator]


@pytest.mark.parametrize("name", FILES)
def test_shipped_confusion_tables_are_row_normalised_and_recognition_helps(name: str) -> None:
    p = shipped(name)
    for key in ("default", "distant"):
        m = p.confusion(key)
        assert set(m.classes) >= set(CLASSES)
        for c in m.classes:
            assert sum(m.row(c)) == pytest.approx(1.0, abs=1e-9)
    for c in CLASSES:
        i = p.confusion("default").labels.index(c)
        assert p.confusion("default").row(c)[i] > p.confusion("distant").row(c)[i]


def test_a_camera_reports_angles_only() -> None:
    d = camera(THERMAL).measure(observation(slant_range_m=30.0, elevation_deg=5.0))
    assert d.range_m is None and d.radial_speed_mps is None and d.sigma_range_m is None
    assert d.azimuth_deg == pytest.approx(45.0) and d.elevation_deg == pytest.approx(5.0)
    assert d.sigma_azimuth_deg is not None and d.sigma_azimuth_deg == d.sigma_elevation_deg
    assert d.modality == "ir"


# ---------------------------------------------------------------------------- cueing


def test_a_narrow_cue_narrows_the_field_and_improves_precision_and_range_deterministically() -> (
    None
):
    world, truth = scene(tick=DUE)
    s = camera_at(200.0)
    g = Geometry.between(s.position, truth)
    wide = s.measure(observation(slant_range_m=30.0))
    p_wide = pd(s, slant_range_m=100.0)
    assert s.fov_deg() == 24.0 and s.precision_factor() == 1.0

    result = s.cue(CueRequest("s-1", g.azimuth_deg, g.elevation_deg, kind="narrow"), DUE)
    settle(s, world, DUE)  # the zoom takes effect on the sensor's next update
    assert result.accepted and s.pointing.fov_deg == 6.0
    assert s.fov_deg() == 6.0 and s.precision_factor() == pytest.approx(0.25)
    narrow = s.measure(observation(slant_range_m=30.0))
    assert narrow.sigma_azimuth_deg is not None and wide.sigma_azimuth_deg is not None
    assert narrow.sigma_azimuth_deg <= 0.25 * wide.sigma_azimuth_deg + 1e-12
    assert narrow.sigma_elevation_deg is not None and wide.sigma_elevation_deg is not None
    assert narrow.sigma_elevation_deg < wide.sigma_elevation_deg
    assert pd(s, slant_range_m=100.0) > p_wide + 0.5  # four times the pixels on target
    r50 = bisect(lambda r: pd(s, slant_range_m=r), 1.0, 6000.0, 0.5)
    assert r50 == pytest.approx(4.0 * 59.5, rel=0.05)  # IFOV a quarter, so range four times

    def reports(cue: bool) -> list[Detection]:
        cam = camera_at(200.0)
        if cue:
            cam.cue(CueRequest("s-1", g.azimuth_deg, g.elevation_deg, kind="narrow"), DUE)
        rng = RngStreams(7)
        return [d for k in range(40) for d in cam.detect(world, DUE + DT * k, rng)]

    first, second = reports(True), reports(True)
    assert first and first == second  # same seed, same cue, same reports
    assert len(first) > len(reports(False))  # the zoom finds the target more often
    assert all(d.sigma_azimuth_deg is not None and d.sigma_azimuth_deg < 0.04 for d in first)


def test_the_zoom_applies_between_the_profile_limits_and_expires() -> None:
    s = camera_at(200.0)
    world, _ = scene(tick=DUE)
    s.cue(CueRequest("s-1", 0.0, kind="narrow", fov_deg=1.0), DUE)  # narrower than the lens allows
    settle(s, world, DUE)
    assert s.fov_deg() == 6.0
    s.cue(CueRequest("s-1", 0.0, kind="narrow", fov_deg=15.0), DUE)
    settle(s, world, DUE)
    assert s.fov_deg() == 15.0 and s.precision_factor() == pytest.approx(15.0 / 24.0)
    s.cue(CueRequest("s-1", 0.0), DUE)  # a plain slew keeps the zoom
    settle(s, world, DUE)
    assert s.fov_deg() == 15.0
    s.detect(world, DUE + 200 + DT, world.rng)  # the 10 s hold has lapsed
    assert s.fov_deg() == 24.0 and s.precision_factor() == 1.0


def test_a_zoomed_camera_loses_a_target_outside_its_field() -> None:
    world, _ = scene(tick=DUE)
    s = camera_at(100.0, params=params_with(THERMAL, slew_rate=None))  # instant pointing
    s.cue(CueRequest("s-1", 90.0, kind="narrow"), DUE)
    assert [d for k in range(40) for d in s.detect(world, DUE + DT * k, world.rng)] == []


# ---------------------------------------------------------------------------- degradations


@pytest.mark.parametrize("name", FILES)
def test_haze_and_glare_cost_probability_and_add_noise_by_the_profile_figures(name: str) -> None:
    s, p = camera(name), shipped(name)
    for kind in ("haze", "glare"):
        assert s.degradation_effect(kind, 0.0) == Effects()
        fx = s.degradation_effect(kind, 1.0)
        assert fx == Effects(
            pd_factor=1.0 - p.value(f"{kind}_pd_loss"),
            noise_factor=1.0 + p.value(f"{kind}_noise_gain"),
        )
        half = s.degradation_effect(kind, 0.5)
        assert half is not None and fx is not None and fx.pd_factor < half.pd_factor < 1.0


def test_glare_hurts_day_eo_most_and_thermal_least() -> None:
    loss = {n: camera(n).degradation_effect("glare", 1.0) for n in FILES}
    factors = {n: fx.pd_factor for n, fx in loss.items() if fx is not None}
    assert factors[THERMAL] > factors[EO_DAY]
    assert factors[THERMAL] > factors[EO_NV]


@pytest.mark.parametrize("kind", ["clutter", "interference", "wind-noise"])
def test_other_degradation_kinds_do_not_touch_a_camera(kind: str) -> None:
    s = camera(THERMAL)
    assert s.degradation_effect(kind, 1.0) is None
    s.inject(Degradation("s-1", kind, 0))
    assert s.effects_at(0) == Effects()


def test_haze_and_glare_reduce_detections_and_widen_the_reports() -> None:
    world, truth = scene(tick=DUE)

    def run(kind: str | None) -> list[Detection]:
        cam = camera_at(100.0, params=params_with(THERMAL, fov_wide=12.0))
        if kind:
            cam.inject(Degradation("s-1", kind, 0, severity=1.0))
        rng = RngStreams(7)
        return [d for k in range(120) for d in cam.detect(world, DUE + DT * k, rng)]

    clean, hazy, glary = run(None), run("haze"), run("glare")
    assert len(hazy) < len(clean) and len(glary) <= len(clean)
    assert hazy and clean
    assert hazy[0].sigma_azimuth_deg is not None and clean[0].sigma_azimuth_deg is not None
    assert hazy[0].sigma_azimuth_deg > clean[0].sigma_azimuth_deg


def test_sector_outage_and_full_outage_are_honoured() -> None:
    world, _ = scene(tick=DUE)
    s = camera_at(100.0, params=params_with(THERMAL, fov_wide=12.0))
    s.inject(Degradation("s-1", "sector-outage", 0, 2000, sector_from_deg=350, sector_to_deg=10))
    assert [d for k in range(120) for d in s.detect(world, DUE + DT * k, world.rng)] == []
    s.inject(Degradation("s-1", "outage", 0, 1200))
    assert [d for k in range(120) for d in s.detect(world, DUE + 480 + DT * k, world.rng)] == []
    assert not s.cue(CueRequest("s-1", 0.0), DUE + 960).accepted


# ---------------------------------------------------------------------------- budget and determinism


@pytest.mark.parametrize(
    "case", ["detected", "out of range", "outside the field", "outage", "haze"]
)
def test_a_camera_takes_the_same_draws_whatever_happens(case: str) -> None:
    world, _ = scene(tick=DUE)
    s = camera_at(9000.0 if case == "out of range" else 100.0)
    if case == "outside the field":
        s.cue(CueRequest("s-1", 180.0, kind="narrow"), DUE)
    if case == "outage":
        s.inject(Degradation("s-1", "outage", 0))
    if case == "haze":
        s.inject(Degradation("s-1", "haze", 0))
    rng = RngStreams(7)
    s.detect(world, DUE, rng)
    assert rng.state()["sensors"] == uniforms_consumed(18), case


def eo_spec() -> ScenarioSpec:
    sensors = [
        SensorPlacement(
            id=sid,
            profile=PackRef(id=profile, version="0.1.0"),
            position=Vec3(x=900, y=900, z=6),
            boresight_deg=45.0,
        )
        for sid, profile in (
            ("eo-day", "eo-generic-day"),
            ("eo-nv", "eo-generic-nv"),
            ("ir-1", "ir-generic-thermal"),
        )
    ]
    return kestrel().model_copy(update={"sensors": sensors})


def run_suite(seed: int = 240117, ticks: int = 6000) -> list[dict[str, object]]:
    spec = eo_spec()
    world, suite = World(spec, seed), build_sensors(spec)
    out: list[dict[str, object]] = []
    for _ in range(ticks):
        world.step()
        if world.tick % 100 == 0:
            for sensor in suite.sensors:
                if truths(world):
                    g = Geometry.between(sensor.position, truths(world)[0])
                    suite.cue(
                        CueRequest(sensor.id, g.azimuth_deg, g.elevation_deg, kind="narrow"),
                        world.tick,
                    )
        out += [d.payload() for d in suite.detect(world)]
    return out


def test_eo_ir_is_deterministic_for_a_seed_and_differs_between_seeds() -> None:
    first = run_suite()
    assert first and first == run_suite()
    assert {p["sensor_id"] for p in first} >= {"eo-day", "ir-1"}
    assert first != run_suite(seed=1)


DETERMINISM_SCRIPT = """
import hashlib, json
from tests.test_sensor_eoir import run_suite
print(hashlib.sha256(json.dumps(run_suite(), sort_keys=True).encode()).hexdigest())
"""


def test_eo_ir_detections_are_identical_in_two_processes_with_different_hash_salts() -> None:
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


def test_restoring_a_cued_hazy_camera_and_the_stream_continues_exactly() -> None:
    world, truth = scene(tick=DUE)
    g = Geometry.between(camera_at(150.0).position, truth)

    def fresh() -> EoIrSensor:
        s = camera_at(150.0)
        s.inject(Degradation("s-1", "haze", DUE + 40, DUE + 120, 0.6))
        s.cue(CueRequest("s-1", g.azimuth_deg, g.elevation_deg, kind="narrow", fov_deg=8.0), DUE)
        return s

    def advance(s: EoIrSensor, w: World, start: int, n: int) -> list[dict[str, object]]:
        out: list[dict[str, object]] = []
        for k in range(n):
            out += [d.payload() for d in s.detect(w, start + DT * k, w.rng)]
        return out

    a = fresh()
    advance(a, world, DUE, 10)
    saved = json.loads(json.dumps(a.state()))
    rng_state = copy.deepcopy(world.rng.state())
    straight = advance(a, world, DUE + 40, 30)

    world2, _ = scene(tick=DUE)
    world2.rng.restore(rng_state)
    b = fresh()
    b.restore(saved)
    resumed = advance(b, world2, DUE + 40, 30)
    assert resumed and resumed == straight


# ---------------------------------------------------------------------------- provenance


@pytest.mark.parametrize("name", FILES)
def test_shipped_profiles_load_against_the_register_and_report_what_is_unverified(
    name: str,
) -> None:
    p = load_sensor_profile(PROFILE_DIR / name, register=register_ids(REGISTER))
    assert p.profile.fictional and p.profile.title.hi and p.profile.notes is not None
    assert p.unverified and "confusion:default" in p.unverified
    verified = {n for n, q in p.profile.parameters.items() if q.verified}
    assert verified <= {"johnson_detect_px", "johnson_recognise_px", "fov_wide", "pixels_h"}
    assert {"johnson_detect_px", "johnson_recognise_px"} <= verified
    assert all(p.profile.parameters[n].source_id == "D12" for n in verified)
    assert {q.source_id for q in p.profile.parameters.values()} <= {"F01", "D12"}


def test_thermal_contrast_is_flagged_unverified_and_the_research_camera_is_cited() -> None:
    p = shipped(THERMAL)
    assert {"contrast_rotary_small", "contrast_bird", "contrast_default"} <= set(p.unverified)
    assert p.value("pixels_h") == 320 and p.value("fov_wide") == 24
    assert p.profile.parameters["pixels_h"].verified and p.profile.parameters["fov_wide"].verified
    assert "radiometric" in p.profile.notes.en and "unverified" in p.profile.notes.en  # type: ignore[union-attr]


def test_the_three_modes_differ_as_documented() -> None:
    day, nv, ir = shipped(EO_DAY), shipped(EO_NV), shipped(THERMAL)
    assert (
        day.value("low_light_floor")
        < nv.value("low_light_floor")
        < ir.value("low_light_floor")
        == 1.0
    )
    assert (
        ir.value("extinction_scale") < nv.value("extinction_scale") < day.value("extinction_scale")
    )
    assert (day.modality, nv.modality, ir.modality) == ("eo", "eo", "ir")


def test_a_profile_missing_a_parameter_or_a_distant_table_is_refused() -> None:
    with pytest.raises(ProfileError, match="johnson_slope"):
        camera(params=params_with(THERMAL, johnson_slope=None))
    with pytest.raises(ProfileError, match="fov_narrow"):
        camera(params=params_with(THERMAL, fov_narrow=None))
    with pytest.raises(ProfileError, match="expected 'deg'"):
        camera(
            params=params_with(
                THERMAL,
                fov_wide={"value": 0.4, "unit": "rad", "source_id": "D12", "verified": True},
            )
        )


def test_the_kestrel_scenario_builds_cameras_from_the_shipped_profiles() -> None:
    suite = build_sensors(eo_spec(), register=register_ids(REGISTER))
    assert [type(s) for s in suite.sensors] == [EoIrSensor] * 3
    assert [s.params.modality for s in suite.sensors] == ["eo", "eo", "ir"]
