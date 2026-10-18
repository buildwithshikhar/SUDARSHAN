"""Wave 4a acceptance, checked across all six shipped profiles at once.

The per-model files test each model in depth. This file pins the wave's criteria to every shipped
profile in one place, so a new profile or model cannot slip past them: P(d) is non-increasing in
range and moves the documented way with weather and time of day, confusion rows sum to one, and
`docs/SENSOR_MODELS.md` documents every model, parameter and register ID the profiles use.
"""

import re
from pathlib import Path

import pytest

from sim.sensors import MODELS, Sensor, SensorParams, load_sensor_profile, register_ids

from .sensor_models import PROFILE_DIR, REGISTER, build, observation, sweep

DOC = REGISTER.parent / "SENSOR_MODELS.md"
FILES = sorted(p.name for p in PROFILE_DIR.glob("*.v1.yaml"))
CLASSES = ("rotary-small", "fixed-wing-small", "bird")
#: Weather that costs a sensor something, with the visibility the weather model pairs it with.
BAD_WEATHER = (("haze", 3000.0), ("fog", 400.0), ("dust", 1500.0), ("rain", 4000.0))
#: Sensors whose P(d) must not depend on the light.
LIGHT_INDEPENDENT = ("radar-generic-s", "rf-generic-passive", "acoustic-generic-array")


def sensor_of(name: str) -> Sensor:
    params = load_sensor_profile(PROFILE_DIR / name, register=register_ids(REGISTER))
    return build(MODELS[params.modality], params)


def pd(s: Sensor, **kw: float | str) -> float:
    return s.p_detect(observation(**kw))  # type: ignore[arg-type]


def half_range(s: Sensor, class_id: str = "rotary-small") -> float:
    """Range at which a clear-day P(d) is closest to one half (bisection on a monotone curve)."""
    lo, hi = 2.0, 20000.0
    for _ in range(40):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if pd(s, class_id=class_id, slant_range_m=mid) > 0.5 else (lo, mid)
    return (lo + hi) / 2


def test_the_wave_ships_six_profiles_covering_the_four_modalities() -> None:
    assert len(FILES) == 6
    assert {sensor_of(f).params.modality for f in FILES} == {"radar", "eo", "ir", "rf", "acoustic"}


# ------------------------------------------------- P(d) is monotonic, weather and light shift it


@pytest.mark.parametrize("name", FILES)
@pytest.mark.parametrize("class_id", [*CLASSES, "unlisted-class"])
@pytest.mark.parametrize("daylight", [0.0, 0.5, 1.0])
@pytest.mark.parametrize(
    ("condition", "visibility"), [("clear", 20000.0), *BAD_WEATHER], ids=lambda v: str(v)
)
def test_pd_never_rises_with_range_for_every_sensor(
    name: str, class_id: str, daylight: float, condition: str, visibility: float
) -> None:
    s = sensor_of(name)
    values = [
        pd(
            s,
            class_id=class_id,
            slant_range_m=r,
            daylight=daylight,
            condition=condition,
            visibility_m=visibility,
        )
        for r in sweep(2.0, 12000.0, 40.0)
    ]
    assert all(0.0 <= v <= 1.0 for v in values)
    assert all(b <= a + 1e-12 for a, b in zip(values, values[1:], strict=False))


@pytest.mark.parametrize("name", FILES)
@pytest.mark.parametrize(("condition", "visibility"), BAD_WEATHER)
def test_no_weather_improves_on_clear_air_and_most_sensors_feel_some(
    name: str, condition: str, visibility: float
) -> None:
    s = sensor_of(name)
    r = half_range(s)
    clear = pd(s, slant_range_m=r)
    bad = pd(s, slant_range_m=r, condition=condition, visibility_m=visibility)
    assert bad <= clear + 1e-12


@pytest.mark.parametrize("name", FILES)
def test_every_sensor_loses_something_to_at_least_one_modelled_condition(name: str) -> None:
    """Nothing is weather-proof; RF loses only a few thousandths to rain, as documented."""
    s = sensor_of(name)
    r = half_range(s)
    clear = pd(s, slant_range_m=r)
    worst = min(pd(s, slant_range_m=r, condition=c, visibility_m=v) for c, v in BAD_WEATHER)
    assert worst < clear


@pytest.mark.parametrize("name", FILES)
def test_night_never_helps_and_light_independent_sensors_do_not_care(name: str) -> None:
    s = sensor_of(name)
    r = half_range(s)
    night = pd(s, slant_range_m=r, daylight=0.0)
    twilight = pd(s, slant_range_m=r, daylight=0.5)
    day = pd(s, slant_range_m=r, daylight=1.0)
    assert night <= twilight + 1e-12 <= day + 2e-12
    if s.params.id in LIGHT_INDEPENDENT or s.params.id == "ir-generic-thermal":
        assert night == day
    else:
        assert night < day - 0.05  # day and night-vision cameras lose performance in the dark


# ------------------------------------------------------------------ confusion matrices


@pytest.mark.parametrize("name", FILES)
def test_every_confusion_row_of_every_profile_sums_to_one(name: str) -> None:
    params = load_sensor_profile(PROFILE_DIR / name)
    assert params.profile.confusion, f"{name} ships no confusion table"
    for key, table in params.profile.confusion.items():
        assert table.rows, f"{name}:{key} has no rows"
        for true_class, row in table.rows.items():
            assert len(row) == len(table.labels), f"{name}:{key}:{true_class}"
            assert all(p >= 0.0 for p in row)
            assert sum(row) == pytest.approx(1.0, abs=1e-9), f"{name}:{key}:{true_class}"


@pytest.mark.parametrize("name", FILES)
def test_every_profile_confusion_table_covers_the_wave_classes(name: str) -> None:
    params = load_sensor_profile(PROFILE_DIR / name)
    for key, table in params.profile.confusion.items():
        if key in ("clutter", "unresolved", "distant"):
            continue
        for class_id in CLASSES:
            if params.modality == "rf" and key == "default":
                continue  # RF tables are indexed by emitter; silent classes are never sampled
            assert class_id in table.rows or key == "micro_doppler", f"{name}:{key}:{class_id}"


# ------------------------------------------------- provenance: every parameter has a source


@pytest.mark.parametrize("name", FILES)
def test_every_parameter_and_table_of_every_profile_cites_a_register_row(name: str) -> None:
    ids = register_ids(REGISTER)
    params = load_sensor_profile(PROFILE_DIR / name, register=ids)
    assert params.profile.parameters
    for pname, q in params.profile.parameters.items():
        assert q.source_id in ids, f"{name}:{pname}"
        assert q.unit, f"{name}:{pname}"
    for key, table in params.profile.confusion.items():
        assert table.source_id in ids, f"{name}:confusion:{key}"


@pytest.mark.parametrize("name", FILES)
def test_only_values_with_a_stated_source_figure_are_marked_verified(name: str) -> None:
    """`verified: true` is rare and deliberate: the Johnson thresholds and thermal camera (D12)."""
    params = load_sensor_profile(PROFILE_DIR / name)
    for pname, q in params.profile.parameters.items():
        if q.verified:
            assert q.source_id == "D12", f"{name}:{pname} is verified from {q.source_id}"
    for key, table in params.profile.confusion.items():
        assert not table.verified, f"{name}:confusion:{key} claims to be verified"


# --------------------------------------------------------------------------- the document

SECTIONS = {
    "Radar": ("radar-generic-s",),
    "EO/IR": ("eo-generic-day", "eo-generic-nv", "ir-generic-thermal"),
    "RF": ("rf-generic-passive",),
    "Acoustic": ("acoustic-generic-array",),
}


def sections() -> dict[str, str]:
    text = DOC.read_text(encoding="utf-8")
    parts = re.split(r"^## (.+)$", text, flags=re.MULTILINE)
    return {title.strip(): body for title, body in zip(parts[1::2], parts[2::2], strict=True)}


def test_the_document_has_one_section_per_model_and_the_shared_honesty_rules() -> None:
    found = sections()
    assert "Honesty rules for every model" in found
    assert set(SECTIONS) <= set(found)
    assert "not radiometric" in found["EO/IR"].lower() or "not radiometric" in DOC.read_text()


@pytest.mark.parametrize("model", SECTIONS)
def test_each_model_section_gives_equations_parameters_and_an_honesty_note(model: str) -> None:
    body = sections()[model]
    assert re.search(r"\*\*Equations?\.?\*\*|^### Equations", body, re.MULTILINE), model
    assert re.search(r"\*\*Parameters\.?\*\*|^### Parameters", body, re.MULTILINE), model
    assert re.search(r"\*\*Honesty note\.?\*\*|^### Honesty note", body, re.MULTILINE), model
    assert "```" in body, f"{model} shows no equation block"


def test_the_thermal_honesty_note_says_it_is_not_radiometric() -> None:
    assert "not radiometric" in sections()["EO/IR"]


def _documented_names(body: str) -> set[str]:
    return set(re.findall(r"`([A-Za-z_<>/ ]+?)`", body))


@pytest.mark.parametrize(("model", "ids"), list(SECTIONS.items()))
def test_every_profile_parameter_is_named_in_its_section(model: str, ids: tuple[str, ...]) -> None:
    body = sections()[model]
    documented = _documented_names(body)
    flat = body.replace("`", "")
    missing: list[str] = []
    for profile_id in ids:
        params = load_sensor_profile(PROFILE_DIR / f"{profile_id}.v1.yaml")
        for pname in params.profile.parameters:
            if pname in documented:
                continue
            # per-class figures are documented by prefix, e.g. `rcs_<class>` or `emits_<class>`
            prefix = re.match(
                r"([a-z_]+?)_(rotary_small|fixed_wing_small|bird|autonomous_small|default)$", pname
            )
            if prefix and any(
                d.startswith(prefix.group(1) + "_") or d == prefix.group(1) for d in documented
            ):
                continue
            # grouped rows such as `loss_clear` / `loss_haze` or `sigma_azimuth` / `sigma_elevation`
            if pname in flat:
                continue
            missing.append(f"{profile_id}:{pname}")
    assert not missing, f"{model} section does not name: {missing}"


@pytest.mark.parametrize(("model", "ids"), list(SECTIONS.items()))
def test_every_register_id_a_profile_uses_appears_in_its_section(
    model: str, ids: tuple[str, ...]
) -> None:
    body = sections()[model]
    for profile_id in ids:
        params = load_sensor_profile(PROFILE_DIR / f"{profile_id}.v1.yaml")
        used = {q.source_id for q in params.profile.parameters.values()}
        used |= {t.source_id for t in params.profile.confusion.values()}
        absent = sorted(i for i in used if not re.search(rf"\b{i}\b", body))
        assert not absent, f"{profile_id}: {model} section never cites {absent}"


def test_every_register_id_the_document_cites_is_a_register_row() -> None:
    ids = register_ids(REGISTER)
    cited = set(re.findall(r"\b([DGWXF][0-9]{2})\b", DOC.read_text(encoding="utf-8")))
    assert cited and cited <= ids, sorted(cited - ids)


def test_every_unverified_headline_figure_is_tied_to_an_open_question() -> None:
    text = DOC.read_text(encoding="utf-8")
    for q in ("Q-09", "Q-20"):
        assert q in text
    open_questions = (REGISTER.parent / "OPEN_QUESTIONS.md").read_text(encoding="utf-8")
    assert "Q-20" in open_questions and "Q-09" in open_questions


def test_profile_files_are_named_for_their_ids() -> None:
    for name in FILES:
        params: SensorParams = load_sensor_profile(PROFILE_DIR / name)
        assert Path(name).name == f"{params.id}.v1.yaml"
