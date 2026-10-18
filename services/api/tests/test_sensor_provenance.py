"""Q-20: nothing derived from an unverified sensor parameter reaches a trainee unlabelled."""

import json
from dataclasses import replace
from typing import Any

import pytest

from app.contracts import SensorProfile
from sim.sensors import (
    DATA_REFERENCE,
    DATA_VERIFIED,
    Detection,
    SensorParams,
    SensorSuite,
)

from .sensor_toy import AlwaysDetects, NoisyAlarms, placement, profile_data, scene, south_of
from .test_sensor_models_together import PROFILES, suite_and_world


def verified_params() -> SensorParams:
    data: dict[str, Any] = profile_data()
    for q in data["parameters"].values():
        q["verified"] = True
    for table in data["confusion"].values():
        table["verified"] = True
    return SensorParams(SensorProfile.model_validate(data))


def test_a_detection_built_without_provenance_is_labelled_reference_data() -> None:
    bare = Detection("s", "radar", 0, None, 10.0, 5.0)
    assert bare.reference_data
    assert bare.trainee_view()["data_status"] == DATA_REFERENCE


def test_every_shipped_profile_has_unverified_values_so_every_report_is_reference_data() -> None:
    suite, world = suite_and_world()
    for sensor in suite.sensors:
        assert sensor.params.unverified, sensor.id
    seen: set[str] = set()
    for _ in range(2400):
        for d in suite.detect(world):
            view = d.trainee_view()
            assert view["data_status"] == DATA_REFERENCE, d.sensor_id
            seen.add(d.sensor_id)
        world.step()
    # not every sensor sees a target in this window (night vision at noon, a 300 m acoustic array)
    assert {"radar-1", "rf-1"} <= seen <= {p[0] for p in PROFILES}


def test_false_alarms_are_labelled_exactly_like_real_contacts() -> None:
    world, truth = scene()
    sensor = NoisyAlarms(placement(south_of(truth)), SensorParams(_unverified_profile()))
    found = sensor.detect(world, world.tick, world.rng)
    alarms = [d for d in found if d.false_alarm]
    assert alarms and all(d.trainee_view()["data_status"] == DATA_REFERENCE for d in alarms)


def test_only_a_fully_verified_profile_produces_a_verified_report() -> None:
    world, truth = scene()
    sensor = AlwaysDetects(placement(south_of(truth)), verified_params())
    assert not sensor.params.unverified
    found = sensor.detect(world, world.tick, world.rng)
    assert found and all(d.trainee_view()["data_status"] == DATA_VERIFIED for d in found)


@pytest.mark.parametrize("name", ["instrumented_range", "sigma_azimuth"])
def test_one_unverified_parameter_is_enough_to_label_the_report(name: str) -> None:
    world, truth = scene()
    data: dict[str, Any] = profile_data()
    for key, q in data["parameters"].items():
        q["verified"] = key != name
    for table in data["confusion"].values():
        table["verified"] = True
    params = SensorParams(SensorProfile.model_validate(data))
    assert params.unverified == (name,)
    found = AlwaysDetects(placement(south_of(truth)), params).detect(world, world.tick, world.rng)
    assert found and {d.trainee_view()["data_status"] for d in found} == {DATA_REFERENCE}


def test_an_unverified_confusion_table_alone_labels_the_report() -> None:
    world, truth = scene()
    data: dict[str, Any] = profile_data()
    for q in data["parameters"].values():
        q["verified"] = True
    params = SensorParams(SensorProfile.model_validate(data))
    assert params.unverified == ("confusion:default",)
    found = AlwaysDetects(placement(south_of(truth)), params).detect(world, world.tick, world.rng)
    assert found and {d.trainee_view()["data_status"] for d in found} == {DATA_REFERENCE}


def test_the_label_is_set_by_the_framework_not_by_each_model() -> None:
    # A model that builds its Detection by hand (as radar and RF do for false alarms) cannot
    # drop the label: the template method stamps every report.
    world, truth = scene()
    sensor = NoisyAlarms(placement(south_of(truth)), verified_params())
    found = sensor.detect(world, world.tick, world.rng)
    assert any(d.false_alarm for d in found)
    assert all(not d.reference_data for d in found)
    stamped = replace(found[0], reference_data=True)
    assert stamped.trainee_view()["data_status"] == DATA_REFERENCE


def test_the_trainee_view_still_carries_no_ground_truth_for_any_profile() -> None:
    suite, world = suite_and_world()
    ids = {t.id for t in world.spec.threats}
    for _ in range(2400):
        for d in suite.detect(world):
            text = json.dumps(d.trainee_view())
            assert "truth" not in text and not any(i in text for i in ids)
        world.step()


def test_a_suite_labels_every_sensor_from_its_own_profile() -> None:
    suite, _ = suite_and_world()
    assert isinstance(suite, SensorSuite)
    assert all(s.params.unverified for s in suite.sensors)


def _unverified_profile() -> SensorProfile:
    return SensorProfile.model_validate(profile_data())
