"""Cueing a sensor to a track: bearing from the estimate, the sensor's own answer, JSON payloads."""

import json
import math
from typing import Any

import pytest

from app.contracts.common import Vec3
from sim.sensors import Degradation, Geometry, SensorSuite
from sim.sensors.geometry import truths
from sim.tracking import Tracker, cueing
from sim.tracking.cueing import COVERAGE_SIGMAS, CueOutcome

from .tracking_cases import RADAR, bare_track, crossing_threats
from .tracking_rig import Rig, profile, radar_params, scenario, sensor

THERMAL_AT = Vec3(x=40, y=0, z=6)


def deg(radians: float) -> float:
    return radians * 180.0 / math.pi


def rig_with_camera(seed: int = 3) -> Rig:
    rig = Rig(
        scenario(crossing_threats()),
        seed,
        [
            sensor("radar-1", radar_params(), RADAR),
            sensor("ir-1", profile("ir-generic-thermal"), THERMAL_AT),
        ],
    )
    rig.run_to(300)
    return rig


def camera_and_radar(**track_fields: Any) -> tuple[Tracker, SensorSuite]:
    """A tracker with one confirmed track (T001), a thermal camera and a radar, no world."""
    tracker = Tracker({"radar-1": RADAR, "ir-1": THERMAL_AT})
    tracker.allocate_id()
    tracker.insert(bare_track("T001", **track_fields))
    suite = SensorSuite(
        [
            sensor("radar-1", radar_params(), RADAR),
            sensor("ir-1", profile("ir-generic-thermal"), THERMAL_AT),
        ]
    )
    return tracker, suite


# ---------------------------------------------------------------------------- pointing


def test_a_cue_points_the_camera_at_the_track_within_the_track_error_and_narrows_it() -> None:
    rig = rig_with_camera()
    tick = rig.history[-1][0]
    track = rig.tracker.tracks["T001"]
    camera = rig.suite["ir-1"]
    assert camera.pointing.fov_deg == 24.0

    out = cueing.cue_for_track(rig.tracker, rig.suite, tick, "ir-1", "T001")
    assert isinstance(out, CueOutcome) and out.ok and out.reason is None
    assert out.request is not None and out.request.kind == "narrow"
    assert out.result is not None and out.result.accepted

    drone = rig.follows("T001")
    (truth,) = [t for t in truths(rig.world) if t.id == drone]
    g = Geometry.between(THERMAL_AT, truth)
    sigma_deg = deg(math.atan(track.view(tick, 20)["sigma_position_m"] / g.slant_range_m))
    miss = abs((out.payload["bearing_deg"] - g.azimuth_deg + 180.0) % 360.0 - 180.0)
    assert miss <= COVERAGE_SIGMAS * sigma_deg
    assert abs(out.payload["elevation_deg"] - g.elevation_deg) <= COVERAGE_SIGMAS * sigma_deg

    # The field narrows to the camera's narrowest because the track is well known.
    assert out.payload["fov_deg"] == 6.0
    assert camera.pointing.fov_deg == 6.0
    rig.step(40)  # two seconds: the slew at 40 deg/s is done
    assert abs(camera.pointing.azimuth_deg - out.payload["bearing_deg"]) < 0.01
    assert camera.pointing.fov_deg == 6.0


def test_a_slew_cue_keeps_the_field_of_view() -> None:
    rig = rig_with_camera()
    out = cueing.cue_for_track(
        rig.tracker, rig.suite, rig.history[-1][0], "ir-1", "T001", narrow=False
    )
    assert out.ok and out.request is not None and out.request.kind == "slew"
    assert out.request.fov_deg is None and out.payload["fov_deg"] == 24.0


def test_the_bearing_is_the_estimate_projected_to_the_cue_tick() -> None:
    tracker, suite = camera_and_radar()
    tracker.tracks["T001"].x = [200.0, 1500.0, 150.0, 30.0, 0.0, -3.0]
    now = cueing.cue_for_track(tracker, suite, 0, "ir-1", "T001")
    later = cueing.cue_for_track(tracker, suite, 40, "ir-1", "T001")  # two seconds on
    dx, dy, dz = 200.0 - 40.0, 1500.0, 150.0 - 6.0
    assert now.payload["bearing_deg"] == pytest.approx(round(deg(math.atan2(dx, dy)), 3))
    assert now.payload["elevation_deg"] == pytest.approx(
        round(deg(math.atan2(dz, math.hypot(dx, dy))), 3)
    )
    dx, dz = dx + 60.0, dz - 6.0
    assert later.payload["bearing_deg"] == pytest.approx(round(deg(math.atan2(dx, dy)), 3))
    assert later.payload["elevation_deg"] == pytest.approx(
        round(deg(math.atan2(dz, math.hypot(dx, dy))), 3)
    )


def test_an_uncertain_track_gets_a_wide_look_and_a_known_one_a_tight_look() -> None:
    tracker, suite = camera_and_radar()
    tight = cueing.cue_for_track(tracker, suite, 0, "ir-1", "T001")
    assert tight.request is not None and tight.request.fov_deg is not None
    slant = math.sqrt(40.0**2 + 1500.0**2 + 144.0**2)
    assert tight.request.fov_deg == pytest.approx(
        2.0 * deg(math.atan(3.0 * 20.0 / slant)), rel=1e-6
    )
    assert tight.payload["fov_deg"] == 6.0  # 3.4 degrees asked for, clamped to the narrowest
    track = tracker.tracks["T001"]
    for i in range(3):
        track.p[i][i] = 150.0 * 150.0
    loose = cueing.cue_for_track(tracker, suite, 0, "ir-1", "T001")
    assert loose.payload["fov_deg"] == 24.0  # 3 sigma is wider than the lens
    again = cueing.cue_for_track(tracker, suite, 0, "ir-1", "T001")
    assert again.payload == loose.payload  # same inputs, same cue


# ---------------------------------------------------------------------------- refusals


def test_a_radar_cannot_be_cued_and_says_so() -> None:
    tracker, suite = camera_and_radar()
    out = cueing.cue_for_track(tracker, suite, 0, "radar-1", "T001")
    assert not out.ok and out.reason == "this sensor cannot be cued"
    assert out.payload["accepted"] is False and out.payload["reason"] == out.reason
    assert out.request is not None and out.result is not None and not out.result.accepted
    assert out.payload["bearing_deg"] is not None  # the cue was worked out, the sensor refused it
    assert out.request.fov_deg is not None
    assert out.payload["fov_deg"] == round(out.request.fov_deg, 3)  # what was asked for


def test_a_sensor_in_outage_refuses() -> None:
    tracker, suite = camera_and_radar()
    suite.inject(Degradation("ir-1", "outage", 0, 100))
    out = cueing.cue_for_track(tracker, suite, 10, "ir-1", "T001")
    assert not out.ok and out.reason == "sensor is out of service"
    assert cueing.cue_for_track(tracker, suite, 100, "ir-1", "T001").ok  # the window is over


def test_a_track_above_the_cameras_elevation_limit_is_refused() -> None:
    tracker, suite = camera_and_radar()
    tracker.tracks["T001"].x = [40.0, 10.0, 3000.0, 0.0, 0.0, 0.0]
    out = cueing.cue_for_track(tracker, suite, 0, "ir-1", "T001")
    assert not out.ok and out.reason == "elevation is outside the sensor's limits"
    assert out.payload["elevation_deg"] > 85.0


def test_an_unknown_sensor_or_track_is_refused_before_the_sensor_is_asked() -> None:
    tracker, suite = camera_and_radar()
    no_sensor = cueing.cue_for_track(tracker, suite, 0, "eo-9", "T001")
    assert (no_sensor.ok, no_sensor.reason) == (False, "no sensor 'eo-9'")
    assert no_sensor.request is None and no_sensor.result is None
    no_track = cueing.cue_for_track(tracker, suite, 0, "ir-1", "T404")
    assert (no_track.ok, no_track.reason) == (False, "no live track 'T404'")
    assert no_track.payload["bearing_deg"] is None and no_track.payload["accepted"] is False


def test_a_sensor_the_suite_does_not_hold_is_refused_by_the_suite() -> None:
    tracker, suite = camera_and_radar()
    tracker.sensor_positions["ghost"] = Vec3(x=0, y=0, z=0)
    out = cueing.cue_for_track(tracker, suite, 0, "ghost", "T001")
    assert (out.ok, out.reason) == (False, "no sensor 'ghost'")
    assert out.request is not None and out.payload["fov_deg"] is not None


# ---------------------------------------------------------------------------- the action record


def test_the_sensor_cue_action_runs_narrow_by_default() -> None:
    tracker, suite = camera_and_radar()
    out = cueing.apply_cue(tracker, suite, 0, {"sensor": "ir-1", "track": "T001"})
    assert out.ok and out.request is not None and out.request.kind == "narrow"
    slew = cueing.apply_cue(tracker, suite, 1, {"sensor": "ir-1", "track": "T001", "narrow": False})
    assert slew.ok and slew.request is not None and slew.request.kind == "slew"
    for outcome in (out, slew):
        assert json.loads(json.dumps(outcome.payload)) == outcome.payload
        assert set(outcome.payload) == {
            "sensor",
            "track",
            "bearing_deg",
            "elevation_deg",
            "fov_deg",
            "accepted",
            "reason",
        }


@pytest.mark.parametrize(
    ("payload", "text"),
    [
        ({"sensor": "ir-1"}, "needs sensor"),
        ({"track": "T001"}, "needs sensor"),
        ({"sensor": 1, "track": "T001"}, "needs sensor"),
        ({"sensor": "ir-1", "track": ["T001"]}, "needs sensor"),
        ({"sensor": "ir-1", "track": "T001", "narrow": "yes"}, "needs sensor"),
        ({"sensor": "ir-1", "track": "T001", "zoom": 2}, "unexpected field"),
    ],
)
def test_bad_cue_payloads_are_refused_with_a_reason(payload: dict[str, Any], text: str) -> None:
    tracker, suite = camera_and_radar()
    out = cueing.apply_cue(tracker, suite, 0, payload)
    assert not out.ok and text in (out.reason or "")
    assert out.request is None and out.result is None
    assert json.loads(json.dumps(out.payload)) == out.payload
    assert suite["ir-1"].pointing.fov_deg == 24.0  # nothing was sent to the sensor
