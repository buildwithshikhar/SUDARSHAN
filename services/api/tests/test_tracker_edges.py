"""Edge cases of the tracker and association that the scenario tests do not reach."""

import pytest

from app.contracts.common import Vec3
from sim.rng import RngStreams
from sim.sensors.geometry import Geometry, Truth
from sim.tracking import (
    Measurement,
    Resolution,
    Track,
    Tracker,
    TrackerConfig,
    kalman,
)
from sim.tracking.associate import Pair, check, components

from .test_tracker_core import ORIGIN, view


def bare_track(track_id: str, x: float = 0.0) -> Track:
    p = kalman.zeros()
    for i in range(6):
        p[i][i] = 25.0
    return Track(track_id, track_id, "confirmed", 0, 0, 0, 5, [x, 1500.0, 150.0, 0, 0, 0], p)


def bearing(
    sensor_id: str, at: Vec3, target: tuple[float, float, float], tick: int = 0
) -> Measurement:
    g = Geometry.between(at, Truth("t", "rotary-small", *target, 0.0, 0.0, 0.0))
    return Measurement.from_view(
        view(
            sensor_id=sensor_id,
            tick=tick,
            azimuth_deg=g.azimuth_deg,
            elevation_deg=g.elevation_deg,
            range_m=None,
            radial_speed_mps=None,
            sigma_range_m=None,
            sigma_azimuth_deg=0.3,
            sigma_elevation_deg=0.3,
        )
    )


def test_a_track_id_cannot_be_used_twice_even_after_the_track_is_dropped() -> None:
    tracker = Tracker({"radar-1": ORIGIN})
    tracker.insert(bare_track("T001"))
    with pytest.raises(ValueError, match="already used"):
        tracker.insert(bare_track("T001"))
    tracker.drop("T001", 5, "operator")
    with pytest.raises(ValueError, match="already used"):
        tracker.insert(bare_track("T001"))


def test_a_track_ahead_of_the_clock_is_refused() -> None:
    tracker = Tracker({"radar-1": ORIGIN})
    track = bare_track("T001")
    track.last_predict = 50
    tracker.insert(track)
    with pytest.raises(ValueError, match="ahead of tick"):
        tracker.update(10, [], RngStreams(1))


def test_a_dropped_tracks_duplicate_counter_is_forgotten() -> None:
    tracker = Tracker({"radar-1": ORIGIN}, config=TrackerConfig(duplicate_hold_s=1.0))
    tracker.insert(bare_track("T001"))
    tracker._close = {"T001|T002": 99}  # T002 was dropped by the operator meanwhile
    tracker.update(0, [], RngStreams(1))
    assert tracker._close == {}


def test_three_rays_to_one_point_make_one_track_and_keep_the_spare_ray() -> None:
    sites = {
        "a": Vec3(x=0.0, y=0.0, z=0.0),
        "b": Vec3(x=1000.0, y=0.0, z=0.0),
        "c": Vec3(x=500.0, y=-800.0, z=0.0),
    }
    tracker = Tracker(sites)
    target = (500.0, 500.0, 100.0)
    tracker.update(0, [bearing(k, v, target) for k, v in sites.items()], RngStreams(1))
    (track,) = tracker.tracks.values()
    assert abs(track.x[0] - 500.0) < 20.0 and abs(track.x[1] - 500.0) < 20.0
    assert len(tracker._orphans) == 1


def test_a_ray_that_points_away_from_the_other_sensor_never_meets_it() -> None:
    sites = {"a": Vec3(x=0.0, y=0.0, z=0.0), "b": Vec3(x=1000.0, y=0.0, z=0.0)}
    tracker = Tracker(sites)
    # a sees the point to the north-east; b's ray points north-east too (away from a's point)
    ms = [
        bearing("a", sites["a"], (500.0, 500.0, 50.0)),
        bearing("b", sites["b"], (1500.0, 500.0, 50.0)),
    ]
    tracker.update(0, ms, RngStreams(1))
    assert tracker.tracks == {}


def test_a_component_reports_the_cost_of_a_gated_pair_and_none_otherwise() -> None:
    (comp,) = components(
        "radar-1", [Pair("T001", 0, 2.0), Pair("T001", 1, 5.0), Pair("T002", 1, 3.0)]
    )
    assert comp.cost("T001", 1) == 5.0 and comp.cost("T002", 0) is None
    assert comp.ambiguous and [p.track for p in comp.nominal] == ["T001", "T002"]


def test_a_resolution_that_is_not_a_reading_of_its_component_is_refused() -> None:
    (comp,) = components(
        "radar-1", [Pair("T001", 0, 2.0), Pair("T002", 0, 3.0), Pair("T002", 1, 4.0)]
    )
    with pytest.raises(ValueError, match="twice"):
        check(comp, Resolution("swap", (("T001", 0), ("T002", 0))))
    with pytest.raises(ValueError, match="twice"):
        check(comp, Resolution("swap", (("T002", 0), ("T002", 1))))
    with pytest.raises(ValueError, match="cannot start a track"):
        check(comp, Resolution("split", (("T001", 0),), spawn=(0,)))
    with pytest.raises(ValueError, match="cannot start a track"):
        check(comp, Resolution("split", (("T001", 0),), spawn=(7,)))
    check(comp, Resolution("split", (("T001", 0),), spawn=(1,)))


def test_the_configuration_can_be_written_out_whole() -> None:
    state = TrackerConfig().to_state()
    assert state["confirm_hits"] == 3 and TrackerConfig(**state) == TrackerConfig()


def test_rays_that_meet_behind_the_sensors_or_too_far_away_make_no_track() -> None:
    sites = {"a": Vec3(x=0.0, y=0.0, z=0.0), "b": Vec3(x=1000.0, y=0.0, z=0.0)}
    behind = Tracker(sites)
    # the lines cross at (500, 500), which is behind both sensors for these bearings
    ms = [
        Measurement.from_view(
            view(
                sensor_id=k,
                tick=0,
                azimuth_deg=az,
                elevation_deg=0.0,
                range_m=None,
                radial_speed_mps=None,
                sigma_range_m=None,
            )
        )
        for k, az in (("a", 225.0), ("b", 135.0))
    ]
    behind.update(0, ms, RngStreams(1))
    assert behind.tracks == {}
    far = Tracker(sites, config=TrackerConfig(triangulation_max_range_m=100.0))
    far.update(0, [bearing(k, v, (500.0, 500.0, 0.0)) for k, v in sites.items()], RngStreams(1))
    assert far.tracks == {}


def test_three_duplicates_fold_into_the_oldest_with_one_drop_each() -> None:
    tracker = Tracker({"radar-1": ORIGIN}, config=TrackerConfig(duplicate_hold_s=0.5))
    for _ in range(3):
        tracker.insert(bare_track(tracker.allocate_id()))
    events = [e for t in range(30) for e in tracker.update(t, [], RngStreams(1)).events]
    drops = [(e.track_id, e.payload["merged_into"]) for e in events if e.kind == "drop"]
    assert drops == [("T002", "T001"), ("T003", "T001")]
    assert list(tracker.tracks) == ["T001"]
