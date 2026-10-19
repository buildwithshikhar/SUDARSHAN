"""Every sensor profile covers every class of the threat catalogue (closes Q-21), and the sensors
behave as the catalogue says they should for the new classes."""

import copy
import dataclasses
from pathlib import Path
from typing import Any

import pytest

from app.contracts import ScenarioSpec, SensorProfile
from app.contracts.loader import load_pack, parse_text
from app.contracts.threat_class import SIGNATURE_UNITS
from sim.catalogue import PROFILE_PARAMS, Catalogue, load_catalogue, profile_problems
from sim.sensors import MODELS, Sensor, SensorParams, load_sensor_profile
from sim.sensors.rf import RfSensor

from .sensor_models import PROFILE_DIR, build, observation, sweep
from .sim_cases import REPO

CATALOGUE = load_catalogue()
FILES = sorted(PROFILE_DIR.glob("*.v1.yaml"))
SCENARIOS = sorted((REPO / "packs" / "scenarios").glob("*.v1.json"))
NEW_LABELS = ["fpv-small", "fixed-wing-medium", "fixed-wing-large", "kite", "balloon"]
SILENT = [c.id for c in CATALOGUE if c.signature["emits"].value == 0]


def profile(path: Path) -> SensorParams:
    return load_sensor_profile(path)


def modified(path: Path, change: Any) -> SensorParams:
    """The shipped profile as raw data, changed by `change(data)`, validated again."""
    data = parse_text(path.read_text(encoding="utf-8"), ".yaml")
    data = copy.deepcopy(data)
    change(data)
    return SensorParams(SensorProfile.model_validate(data))


def by_id(name: str) -> Path:
    return PROFILE_DIR / f"{name}.v1.yaml"


def sensor(path: Path) -> Sensor:
    params = profile(path)
    return build(MODELS[params.modality], params)


# ------------------------------------------------------------------ profiles equal the catalogue


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
def test_every_profile_covers_every_class_with_the_catalogue_signature(path: Path) -> None:
    assert profile_problems(CATALOGUE, [profile(path)]) == []


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
@pytest.mark.parametrize("class_id", CATALOGUE.ids)
def test_per_class_parameters_equal_the_catalogue(path: Path, class_id: str) -> None:
    params, cls = profile(path), CATALOGUE.get(class_id)
    for prefix in PROFILE_PARAMS[params.modality]:
        got = params.for_class(prefix, class_id, SIGNATURE_UNITS[prefix])
        if params.modality == "eo" and prefix == "contrast":
            want = params.value("contrast_default") * cls.signature["contrast_eo"].value
        else:
            want = cls.signature[prefix].value
        assert got == pytest.approx(want, abs=1e-9), f"{params.id}:{prefix}:{class_id}"
        name = f"{prefix}_{class_id.replace('-', '_')}"
        if name in params:  # a listed parameter carries the catalogue's provenance
            q = params.quantity(name)
            assert q.unit == SIGNATURE_UNITS[prefix]
            assert not q.verified
            assert q.source_id in {"F01", "D08", "D10", "D11", "D12"}


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
def test_confusion_tables_have_a_row_per_class_and_sum_to_one(path: Path) -> None:
    params = profile(path)
    keys = MODELS[params.modality].confusion_keys
    assert keys and set(keys) <= set(params.profile.confusion)
    for key in keys:
        table = params.profile.confusion[key]
        for class_id in CATALOGUE.ids:
            assert class_id in table.rows, f"{params.id}:{key}:{class_id}"
        for class_id, row in table.rows.items():
            assert sum(row) == pytest.approx(1.0, abs=1e-9), f"{params.id}:{key}:{class_id}"
            assert len(row) == len(table.labels)


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
def test_every_sensor_can_report_the_recognition_class_of_what_it_can_see(path: Path) -> None:
    params = profile(path)
    for key in MODELS[params.modality].confusion_keys:
        if key == "micro_doppler":
            continue
        labels = params.profile.confusion[key].labels
        assert "unknown" in labels
        for cls in CATALOGUE:
            if params.modality == "rf" and cls.signature["emits"].value == 0:
                continue  # a silent class is never reported by RF
            assert cls.recognition_class in labels, f"{params.id}:{key}:{cls.id}"


# ------------------------------------------------------------------ the original rows are intact


#: The first four columns of each original row, as shipped before wave 8.
ORIGINAL = {
    "radar-generic-s": {
        "default": {
            "rotary-small": [0.86, 0.02, 0.04, 0.08],
            "fixed-wing-small": [0.03, 0.78, 0.09, 0.10],
            "bird": [0.03, 0.04, 0.85, 0.08],
            "clutter": [0.05, 0.05, 0.20, 0.70],
        },
        "unresolved": {
            "rotary-small": [0.44, 0.10, 0.16, 0.30],
            "bird": [0.14, 0.12, 0.44, 0.30],
            "clutter": [0.05, 0.05, 0.10, 0.80],
        },
    },
    "eo-generic-day": {
        "default": {"rotary-small": [0.90, 0.02, 0.04, 0.04], "bird": [0.04, 0.06, 0.86, 0.04]},
        "distant": {"fixed-wing-small": [0.12, 0.40, 0.18, 0.30]},
    },
    "eo-generic-nv": {"default": {"fixed-wing-small": [0.05, 0.80, 0.07, 0.08]}},
    "ir-generic-thermal": {"default": {"bird": [0.06, 0.08, 0.80, 0.06]}},
    "rf-generic-passive": {
        "default": {
            "rotary-small": [0.80, 0.03, 0.09, 0.08],
            "wifi-bluetooth": [0.10, 0.04, 0.72, 0.14],
            "bird": [0.00, 0.00, 0.00, 1.00],
        }
    },
    "acoustic-generic-array": {
        "default": {
            "bird": [0.04, 0.14, 0.58, 0.24],
            "autonomous-small": [0.80, 0.05, 0.03, 0.12],
        }
    },
}


@pytest.mark.parametrize("profile_id", ORIGINAL)
def test_labels_were_only_appended_and_the_original_rows_are_unchanged(profile_id: str) -> None:
    params = profile(by_id(profile_id))
    for key, rows in ORIGINAL[profile_id].items():
        table = params.profile.confusion[key]
        appended = table.labels[4:]
        assert appended, f"{profile_id}:{key} was not extended"
        assert set(appended) <= set(NEW_LABELS)
        for class_id, head in rows.items():
            row = table.rows[class_id]
            assert row[:4] == head, f"{profile_id}:{key}:{class_id}"
            assert row[4:] == [0.0] * len(appended), f"{profile_id}:{key}:{class_id}"


def test_the_label_vocabulary_matches_the_brief() -> None:
    for name in ("radar-generic-s", "eo-generic-day", "eo-generic-nv", "ir-generic-thermal"):
        for key in ("default", "unresolved", "distant"):
            table = profile(by_id(name)).profile.confusion.get(key)
            if table is not None:
                assert table.labels == [
                    "rotary-small",
                    "fixed-wing-small",
                    "bird",
                    "unknown",
                    *NEW_LABELS,
                ]
    assert profile(by_id("acoustic-generic-array")).profile.confusion["default"].labels == [
        "rotary-small",
        "fixed-wing-small",
        "bird",
        "unknown",
        *NEW_LABELS,
    ]
    assert profile(by_id("rf-generic-passive")).profile.confusion["default"].labels == [
        "rotary-small",
        "fixed-wing-small",
        "wifi-bluetooth",
        "unknown",
        "fpv-small",
        "fixed-wing-medium",
        "fixed-wing-large",
    ]


def test_the_look_alike_rule_shapes_the_rows() -> None:
    radar = profile(by_id("radar-generic-s")).profile.confusion["default"]
    labels = radar.labels

    def p(table: Any, true: str, label: str) -> float:
        return float(table.rows[true][table.labels.index(label)])

    # radar cannot tell fpv-small from rotary-small: mostly a quad, fpv only sometimes
    assert p(radar, "fpv-small", "rotary-small") > p(radar, "fpv-small", "fpv-small") > 0.1
    for quad_like in ("decoy-small", "autonomous-small", "civil-drone"):
        assert p(radar, quad_like, "rotary-small") == max(radar.rows[quad_like])
    assert labels.index("rotary-small") == 0
    # medium and large fixed-wing spread over the fixed-wing labels, by size
    for true in ("fixed-wing-medium", "fixed-wing-large"):
        spread = sum(p(radar, true, f) for f in ("fixed-wing-small", *NEW_LABELS[1:3]))
        assert spread > 0.75
    # kite and balloon: radar mostly unknown or bird, a camera resolves them best
    for true in ("kite", "balloon"):
        assert p(radar, true, "unknown") + p(radar, true, "bird") > 0.7
        for camera in ("eo-generic-day", "eo-generic-nv"):
            table = profile(by_id(camera)).profile.confusion["default"]
            assert p(table, true, true) > 0.7
    thermal = profile(by_id("ir-generic-thermal")).profile.confusion["default"]
    assert p(thermal, "balloon", "balloon") < 0.2 and p(thermal, "balloon", "unknown") > 0.5
    # RF: a silent class is `unknown` with certainty
    rf = profile(by_id("rf-generic-passive")).profile.confusion["default"]
    for silent in SILENT:
        assert p(rf, silent, "unknown") == 1.0


# ------------------------------------------------------------------ scenarios


@pytest.mark.parametrize("path", SCENARIOS, ids=lambda p: p.name)
def test_every_shipped_scenario_passes_the_catalogue_check(path: Path) -> None:
    spec = load_pack(path)
    assert isinstance(spec, ScenarioSpec)
    assert CATALOGUE.check_scenario(spec) == []


# ------------------------------------------------------------------ the check itself


def test_the_check_reports_a_changed_value() -> None:
    path = by_id("radar-generic-s")
    params = modified(path, lambda d: d["parameters"]["rcs_kite"].update(value=-10))
    (problem,) = profile_problems(CATALOGUE, [params])
    assert problem == "radar-generic-s: rcs_kite is -10, the catalogue says -30"


def test_the_check_reports_a_default_that_no_longer_matches_a_class_without_an_entry() -> None:
    params = modified(
        by_id("radar-generic-s"), lambda d: d["parameters"]["rcs_default"].update(value=-9)
    )
    problems = profile_problems(CATALOGUE, [params])
    assert any("rcs_civil_drone is -9, the catalogue says -16" in p for p in problems)


def test_the_check_reports_a_changed_source_or_verified_flag() -> None:
    def change(d: dict[str, Any]) -> None:
        d["parameters"]["size_kite"].update(source_id="D12")
        d["parameters"]["size_balloon"].update(verified=True)

    problems = profile_problems(CATALOGUE, [modified(by_id("eo-generic-day"), change)])
    assert len(problems) == 2
    assert any(
        "size_kite cites D12 (verified False), the catalogue cites F01" in p for p in problems
    )
    assert any("size_balloon cites F01 (verified True)" in p for p in problems)


def test_the_check_reports_a_missing_default_and_a_wrong_unit() -> None:
    gone = modified(
        by_id("radar-generic-s"),
        lambda d: (
            d["parameters"].pop("aspect_swing_kite"),
            d["parameters"].pop("aspect_swing_default"),
        ),
    )
    problems = profile_problems(CATALOGUE, [gone])
    assert any("aspect_swing_default" in p and "missing" in p for p in problems)
    unit = modified(
        by_id("radar-generic-s"), lambda d: d["parameters"]["rcs_kite"].update(unit="dB")
    )
    assert any(
        "'rcs_kite' is in 'dB', expected 'dBsm'" in p for p in profile_problems(CATALOGUE, [unit])
    )


def test_the_check_reports_a_missing_row_and_a_missing_label() -> None:
    def change(d: dict[str, Any]) -> None:
        del d["confusion"]["default"]["rows"]["kite"]
        labels = d["confusion"]["default"]["labels"]
        labels[labels.index("bird")] = "gull"

    params = modified(by_id("eo-generic-day"), change)
    problems = profile_problems(CATALOGUE, [params])
    assert "eo-generic-day: confusion table 'default' has no row for kite" in problems
    assert "eo-generic-day: confusion table 'default' cannot report bird for bird" in problems


def test_rf_labels_only_what_a_class_emits() -> None:
    def change(d: dict[str, Any]) -> None:
        table = d["confusion"]["default"]
        table["labels"][table["labels"].index("fixed-wing-large")] = "fw-large"

    problems = profile_problems(CATALOGUE, [modified(by_id("rf-generic-passive"), change)])
    assert problems == [
        "rf-generic-passive: confusion table 'default' cannot report fixed-wing-large for fixed-wing-large"
    ]


def test_the_check_reports_a_derived_camera_contrast_that_drifts() -> None:
    params = modified(
        by_id("eo-generic-nv"), lambda d: d["parameters"]["contrast_kite"].update(value=0.5)
    )
    (problem,) = profile_problems(CATALOGUE, [params])
    assert "contrast_kite is 0.5, the catalogue says 0.975" in problem


def test_a_profile_may_now_carry_up_to_128_parameters() -> None:
    data = parse_text(by_id("radar-generic-s").read_text(encoding="utf-8"), ".yaml")
    template = data["parameters"]["update_interval"]
    for count in (128, 129):
        data = copy.deepcopy(data)
        data["parameters"] = {f"filler_{i}": dict(template) for i in range(count)}
        if count == 128:
            assert SensorProfile.model_validate(data)
        else:
            with pytest.raises(ValueError, match="at most 128"):
                SensorProfile.model_validate(data)


# ------------------------------------------------------------------ sensors over the catalogue


def half_range(s: Sensor, class_id: str, **kw: Any) -> float:
    lo, hi = 2.0, 40000.0
    for _ in range(50):
        mid = (lo + hi) / 2
        hit = s.p_detect(observation(class_id=class_id, slant_range_m=mid, **kw)) > 0.5
        lo, hi = (mid, hi) if hit else (lo, mid)
    return (lo + hi) / 2


def test_radar_range_grows_with_cross_section() -> None:
    radar = sensor(by_id("radar-generic-s"))
    ranges = {c: half_range(radar, c, elevation_deg=20.0) for c in CATALOGUE.ids}
    ordered = ["kite", "balloon", "bird", "decoy-small", "fpv-small", "rotary-small"]
    ordered += ["fixed-wing-small", "fixed-wing-medium", "fixed-wing-large"]
    values = [ranges[c] for c in ordered]
    assert values == sorted(values) and len(set(values)) == len(values)
    assert ranges["autonomous-small"] == ranges["civil-drone"] == ranges["rotary-small"]


def test_the_cameras_see_a_bigger_class_further() -> None:
    for name in ("eo-generic-day", "eo-generic-nv", "ir-generic-thermal"):
        cam = sensor(by_id(name))
        ranges = {c: half_range(cam, c) for c in CATALOGUE.ids}
        assert ranges["fixed-wing-large"] > ranges["fixed-wing-medium"] > ranges["fixed-wing-small"]
        assert ranges["fixed-wing-small"] > ranges["rotary-small"] > ranges["decoy-small"]
    thermal = sensor(by_id("ir-generic-thermal"))
    assert half_range(thermal, "decoy-small") < half_range(thermal, "rotary-small") / 2
    assert half_range(thermal, "balloon") < half_range(thermal, "bird") / 2
    day = sensor(by_id("eo-generic-day"))
    assert half_range(day, "kite") > half_range(day, "rotary-small")  # bright and distinctive


def test_the_acoustic_array_hears_the_louder_classes_further() -> None:
    array = sensor(by_id("acoustic-generic-array"))
    ranges = {c: half_range(array, c) for c in CATALOGUE.ids}
    assert ranges["fixed-wing-large"] > ranges["fixed-wing-medium"] > ranges["fixed-wing-small"]
    assert ranges["fpv-small"] > ranges["rotary-small"] > ranges["decoy-small"] > ranges["bird"]


@pytest.mark.parametrize("class_id", SILENT)
def test_an_rf_silent_class_is_never_detected_by_rf(class_id: str) -> None:
    rf = sensor(by_id("rf-generic-passive"))
    assert isinstance(rf, RfSensor)
    for r in sweep(2.0, 3000.0, 150.0):
        for noise in (1.0, 0.25):
            effects = dataclasses.replace(observation().effects, noise_factor=noise)
            obs = observation(class_id=class_id, slant_range_m=r, effects=effects)
            assert rf.p_detect(obs) == 0.0


def test_the_emitting_classes_are_heard_and_the_silent_ones_are_not() -> None:
    rf = sensor(by_id("rf-generic-passive"))
    heard = [
        c.id
        for c in CATALOGUE
        if rf.p_detect(observation(class_id=c.id, slant_range_m=500.0)) > 0.9
    ]
    assert sorted(heard) == sorted(c.id for c in CATALOGUE if c.id not in SILENT)


def test_the_fpv_link_is_the_5_8_ghz_hopping_one() -> None:
    rf = sensor(by_id("rf-generic-passive"))
    assert isinstance(rf, RfSensor)
    assert rf.band("fpv-small")[0] == "5.8 GHz" and rf.band("fixed-wing-medium")[0] == "900 MHz"
    assert (
        rf.band("fixed-wing-large")[0] == "1.2-1.3 GHz" and rf.band("civil-drone")[0] == "2.4 GHz"
    )
    assert rf.params.for_class("hop_rate", "fpv-small") > rf.params.for_class(
        "hop_rate", "rotary-small"
    )


@pytest.mark.parametrize("class_id", ["kite", "balloon"])
def test_a_kite_or_balloon_is_never_heard_by_the_acoustic_array(class_id: str) -> None:
    array = sensor(by_id("acoustic-generic-array"))
    calm = dataclasses.replace(observation().env, wind_speed_mps=0.0)
    limit = array.instrumented_range_m
    ranges = [1.0, 2.0, *sweep(5.0, limit, 5.0)]
    for r in ranges:
        for env in (observation().env, calm):
            obs = observation(class_id=class_id, slant_range_m=r)
            obs = dataclasses.replace(obs, env=env)
            assert array.p_detect(obs) < 1e-6, (class_id, r)
    # while a quadcopter at the same range is heard
    assert array.p_detect(observation(class_id="rotary-small", slant_range_m=50.0)) > 0.95
    assert array.params.for_class("source_level", class_id) <= 0.0


def test_p_detect_is_non_increasing_in_range_for_the_whole_catalogue() -> None:
    for path in FILES:
        s = sensor(path)
        for class_id in CATALOGUE.ids:
            values = [
                s.p_detect(observation(class_id=class_id, slant_range_m=r))
                for r in sweep(2.0, 12000.0, 40.0)
            ]
            assert all(0.0 <= v <= 1.0 for v in values)
            assert all(b <= a + 1e-12 for a, b in zip(values, values[1:], strict=False)), (
                path.name,
                class_id,
            )


def test_every_class_resolves_through_a_sensor_built_from_a_scenario_of_that_class() -> None:
    """`check_scenario` of each sensor accepts a spec that flies any catalogue class."""
    from .test_catalogue_flights import scenario_for  # reuses the flight scenario builder

    for cls in CATALOGUE:
        spec = scenario_for(cls.id, "heron-ridge")
        for path in FILES:
            sensor(path).check_scenario(spec)


def test_a_catalogue_without_a_class_leaves_the_profile_check_quiet_about_it() -> None:
    smaller = Catalogue([CATALOGUE.get("bird"), CATALOGUE.get("rotary-small")])
    assert profile_problems(smaller, [profile(by_id("radar-generic-s"))]) == []


def test_a_profile_missing_every_default_is_reported_per_parameter() -> None:
    def change(d: dict[str, Any]) -> None:
        for name in [n for n in d["parameters"] if n.startswith("source_level")]:
            del d["parameters"][name]

    params = modified(by_id("acoustic-generic-array"), change)
    problems = profile_problems(CATALOGUE, [params])
    assert len(problems) == len(CATALOGUE) and all("source_level_default" in p for p in problems)
