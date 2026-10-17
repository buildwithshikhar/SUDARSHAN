"""Sensor profiles: provenance is mandatory, confusion tables are row-normalised."""

import copy
from pathlib import Path
from typing import Any

import pytest
import yaml
from pydantic import ValidationError

from app.contracts import SensorProfile
from app.contracts.common import PackRef
from sim.sensors import (
    ProfileError,
    SensorParams,
    load_sensor_profile,
    register_ids,
    resolve_profile,
)
from sim.sensors.confusion import ConfusionMatrix

from .sensor_toy import profile_data, q, toy_params

REPO = Path(__file__).resolve().parents[3]
REGISTER = REPO / "docs" / "DATA_REGISTER.md"
PROFILE_DIR = REPO / "packs" / "sensor-profiles"


def write(tmp_path: Path, data: dict[str, Any], name: str = "toy.v1.yaml") -> Path:
    path = tmp_path / name
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------- provenance


@pytest.mark.parametrize(
    "mutate",
    [
        lambda p: p["instrumented_range"].pop("source_id"),
        lambda p: p["instrumented_range"].update(source_id=""),
        lambda p: p["instrumented_range"].update(source_id=None),
        lambda p: p["instrumented_range"].update(source_id="made up"),
        lambda p: p["instrumented_range"].update(source_id="Q99"),
        lambda p: p["instrumented_range"].pop("verified"),
        lambda p: p["instrumented_range"].pop("unit"),
        lambda p: p["instrumented_range"].update(value="far"),
    ],
    ids=[
        "no source",
        "empty source",
        "null source",
        "free-text source",
        "bad prefix",
        "no verified flag",
        "no unit",
        "text value",
    ],
)
def test_a_parameter_without_complete_provenance_is_refused(tmp_path: Path, mutate: Any) -> None:
    data = profile_data()
    mutate(data["parameters"])
    with pytest.raises(ProfileError):
        load_sensor_profile(write(tmp_path, data))


def test_a_source_id_that_is_not_in_the_register_is_refused_when_a_register_is_given(
    tmp_path: Path,
) -> None:
    data = profile_data(instrumented_range={**q(5000, "m"), "source_id": "D99"})
    path = write(tmp_path, data)
    load_sensor_profile(path)  # shape alone is valid
    with pytest.raises(ProfileError, match="instrumented_range"):
        load_sensor_profile(path, register=register_ids(REGISTER))


def test_the_register_lists_the_sources_the_packs_use() -> None:
    ids = register_ids(REGISTER)
    assert "F01" in ids
    assert all(i[0] in "DGWXF" and len(i) == 3 for i in ids)


def test_a_confusion_table_source_is_checked_against_the_register(tmp_path: Path) -> None:
    data = profile_data()
    data["confusion"]["default"]["source_id"] = "D99"
    with pytest.raises(ProfileError, match="confusion:default"):
        load_sensor_profile(write(tmp_path, data), register=register_ids(REGISTER))


def test_the_shipped_profiles_load_against_the_register() -> None:
    for path in sorted(PROFILE_DIR.glob("*.yaml")):
        load_sensor_profile(path, register=register_ids(REGISTER))


def test_unverified_values_are_listed() -> None:
    params = toy_params(
        instrumented_range={**q(5000, "m"), "verified": True},
        sigma_range={**q(10, "m"), "verified": True},
    )
    assert "instrumented_range" not in params.unverified
    assert "sigma_range" not in params.unverified
    assert "sigma_azimuth" in params.unverified
    assert "confusion:default" in params.unverified
    assert list(params.unverified) == sorted(params.unverified)


# ---------------------------------------------------------------------------- reading values


def test_value_checks_the_unit() -> None:
    params = toy_params()
    assert params.value("instrumented_range", "m") == 5000
    assert params.value("instrumented_range") == 5000
    with pytest.raises(ProfileError, match="expected 'km'"):
        params.value("instrumented_range", "km")


def test_missing_parameters_are_reported_together() -> None:
    params = toy_params()
    with pytest.raises(ProfileError, match="nope"):
        params.value("nope")
    assert params.optional("nope") is None
    with pytest.raises(ProfileError, match="a, b"):
        params.require("sigma_range", "a", "b")
    params.require("sigma_range")


def test_per_class_values_fall_back_to_the_default() -> None:
    params = toy_params(rcs_rotary_small=q(0.01, "m^2"), rcs_default=q(0.5, "m^2"))
    assert params.for_class("rcs", "rotary-small", "m^2") == 0.01
    assert params.for_class("rcs", "fixed-wing-small") == 0.5
    with pytest.raises(ProfileError, match="rcs_default"):
        toy_params().for_class("rcs", "rotary-small")


def test_resolve_profile_needs_the_exact_id_and_version(tmp_path: Path) -> None:
    write(tmp_path, profile_data())
    assert resolve_profile(PackRef(id="toy-radar", version="1.0.0"), tmp_path).id == "toy-radar"
    for ref in (PackRef(id="toy-radar", version="1.0.1"), PackRef(id="other", version="1.0.0")):
        with pytest.raises(ProfileError, match="no sensor profile"):
            resolve_profile(ref, tmp_path)


def test_the_loader_refuses_other_packs_and_unreadable_files(tmp_path: Path) -> None:
    scenario = REPO / "packs" / "scenarios" / "kestrel-dawn-approach.v1.json"
    with pytest.raises(ProfileError, match="not a sensor profile"):
        load_sensor_profile(scenario)
    bad = tmp_path / "bad.v1.yaml"
    bad.write_text("contract: sensor-profile.v1\ncontract: sensor-profile.v1\n", encoding="utf-8")
    with pytest.raises(ProfileError, match="duplicate key"):
        load_sensor_profile(bad)
    assert isinstance(toy_params(), SensorParams)


def test_missing_confusion_table_is_reported() -> None:
    with pytest.raises(ProfileError, match="thermal"):
        toy_params().confusion("thermal")


# ---------------------------------------------------------------------------- confusion tables


def table(**changes: Any) -> dict[str, Any]:
    base: dict[str, Any] = copy.deepcopy(profile_data()["confusion"]["default"])
    return base | changes


@pytest.mark.parametrize(
    "changes",
    [
        {"rows": {"rotary-small": [0.5, 0.2, 0.2]}},  # sums to 0.9
        {"rows": {"rotary-small": [0.6, 0.5, 0.2]}},  # sums to 1.3
        {"rows": {"rotary-small": [0.5, 0.5]}},  # too short
        {"rows": {"rotary-small": [1.2, -0.1, -0.1]}},  # outside [0, 1]
        {"labels": ["a", "a", "b"]},  # duplicate label
        {"labels": ["only"], "rows": {"rotary-small": [1.0]}},  # fewer than two labels
        {"source_id": "nope"},
        {"extra": 1},
    ],
    ids=["low", "high", "short", "range", "duplicate", "one label", "source", "extra field"],
)
def test_malformed_confusion_tables_are_refused(changes: dict[str, Any]) -> None:
    data = profile_data()
    data["confusion"]["default"] = table(**changes)
    with pytest.raises(ValidationError):
        SensorProfile.model_validate(data)


def test_every_row_of_a_valid_table_sums_to_one() -> None:
    matrix = toy_params().confusion()
    for true_class in matrix.classes:
        assert sum(matrix.row(true_class)) == pytest.approx(1.0, abs=1e-9)


def test_sampling_follows_the_row_and_is_a_function_of_the_draw() -> None:
    matrix = toy_params().confusion()
    n = 1000
    for true_class in matrix.classes:
        counts = dict.fromkeys(matrix.labels, 0)
        for i in range(n):
            counts[matrix.sample(true_class, (i + 0.5) / n)] += 1
        for label, p in zip(matrix.labels, matrix.row(true_class), strict=True):
            assert counts[label] / n == pytest.approx(p, abs=2 / n)
    assert matrix.sample("rotary-small", 0.123) == matrix.sample("rotary-small", 0.123)


def test_a_zero_probability_label_is_never_reported() -> None:
    data = profile_data()
    data["confusion"]["default"]["rows"]["rotary-small"] = [1.0, 0.0, 0.0]
    matrix = ConfusionMatrix(SensorProfile.model_validate(data).confusion["default"])
    assert {matrix.sample("rotary-small", u / 100) for u in range(100)} == {"rotary-small"}
    assert matrix.sample("rotary-small", 0.9999999999999999) == "rotary-small"


def test_sampling_an_unlisted_class_is_an_error() -> None:
    matrix = toy_params().confusion()
    assert matrix.has("rotary-small") and not matrix.has("bird")
    with pytest.raises(KeyError, match="bird"):
        matrix.sample("bird", 0.5)


def test_the_exported_json_schema_knows_the_confusion_table() -> None:
    import json

    schema = json.loads((REPO / "packs" / "schemas" / "sensor-profile.v1.json").read_text("utf-8"))
    assert "confusion" in schema["properties"]


def test_a_draw_in_the_rounding_gap_reports_the_last_possible_label() -> None:
    data = profile_data()
    data["confusion"]["default"]["rows"]["rotary-small"] = [0.5, 0.5 - 5e-10, 0.0]
    matrix = ConfusionMatrix(SensorProfile.model_validate(data).confusion["default"])
    assert matrix.sample("rotary-small", 0.9999999999) == "fixed-wing-small"
