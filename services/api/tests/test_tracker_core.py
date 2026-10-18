"""Tracker input contract, filter, measurement model and track lifecycle (wave 4b, step 1)."""

import json
import math
from typing import Any

import pytest

from app.contracts.common import Vec3
from sim import detmath
from sim.rng import RngStreams
from sim.sensors import DATA_REFERENCE, DATA_VERIFIED, Degradation
from sim.sensors.geometry import Geometry, Truth
from sim.tracking import (
    CHI2_GATE,
    Measurement,
    MeasurementError,
    Track,
    Tracker,
    TrackerConfig,
    kalman,
)
from sim.tracking.model import polar_to_enu, ray, rows_for

from .tracking_rig import Rig, drone, profile, radar_params, scenario, sensor

ORIGIN = Vec3(x=0.0, y=0.0, z=6.0)
CFG = TrackerConfig()


def view(**over: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "sensor_id": "radar-1",
        "modality": "radar",
        "tick": 10,
        "azimuth_deg": 45.0,
        "elevation_deg": 5.0,
        "range_m": 1000.0,
        "radial_speed_mps": -3.0,
        "sigma_range_m": 7.5,
        "sigma_azimuth_deg": 0.6,
        "sigma_elevation_deg": 1.0,
        "sigma_radial_mps": 0.4,
        "reported_class": "rotary-small",
        "features": {"micro_doppler": "rotor"},
        "data_status": DATA_REFERENCE,
    }
    base.update(over)
    return base


def lone_drone(heading: float = 90.0, y: float = 1500.0) -> Rig:
    x0 = -600.0 if heading == 90.0 else 600.0
    end = 1500.0 if heading == 90.0 else -1500.0
    spec = scenario([drone("alpha", "rotary-small", (x0, y, 150), heading, 15, [(end, y, 150)])])
    return Rig(spec, 5, [sensor("radar-1", radar_params(), ORIGIN)])


# ---------------------------------------------------------------- input contract


def test_a_measurement_is_built_from_the_trainee_view_and_nothing_else() -> None:
    m = Measurement.from_view(view(), ref=7)
    assert (m.sensor_id, m.tick, m.ref, m.has_range) == ("radar-1", 10, 7, True)
    assert m.reported_class == "rotary-small" and m.features == {"micro_doppler": "rotor"}
    assert Measurement.from_state(m.to_state()) == m


def test_a_report_that_names_the_true_target_is_refused() -> None:
    with pytest.raises(MeasurementError, match="truth_id"):
        Measurement.from_view(view(truth_id="contact-a"))


def test_a_full_detection_payload_is_not_a_tracker_input() -> None:
    rig = lone_drone()
    detection = None
    while detection is None:
        found = [d for d in rig.suite.detect(rig.world) if d.truth_id]
        detection = found[0] if found else None
        if detection is None:
            rig.world.step()
    # the instructor payload carries truth_id; only trainee_view() is accepted
    with pytest.raises(MeasurementError):
        Measurement.from_view(detection.payload())
    assert Measurement.from_view(detection.trainee_view()).sensor_id == "radar-1"


@pytest.mark.parametrize("key", ["sensor_id", "tick", "azimuth_deg", "sigma_azimuth_deg"])
def test_a_report_without_what_the_filter_needs_is_refused(key: str) -> None:
    data = view()
    del data[key]
    with pytest.raises(MeasurementError, match=key):
        Measurement.from_view(data)


def test_an_unknown_data_status_is_refused_and_a_missing_one_is_reference_data() -> None:
    with pytest.raises(MeasurementError, match="data_status"):
        Measurement.from_view(view(data_status="trusted"))
    data = view()
    del data["data_status"]
    assert Measurement.from_view(data).data_status == DATA_REFERENCE


def test_a_bearing_only_report_has_no_range() -> None:
    m = Measurement.from_view(view(range_m=None, sigma_range_m=None, radial_speed_mps=None))
    assert not m.has_range


def test_the_tracker_refuses_unknown_sensors_wrong_ticks_and_time_going_backwards() -> None:
    tracker = Tracker({"radar-1": ORIGIN})
    rng = RngStreams(1)
    with pytest.raises(MeasurementError, match="unknown sensor"):
        tracker.update(10, [Measurement.from_view(view(sensor_id="ghost"))], rng)
    with pytest.raises(MeasurementError, match="tick 10, not 11"):
        tracker.update(11, [Measurement.from_view(view())], rng)
    tracker.update(10, [], rng)
    with pytest.raises(ValueError, match="already advanced"):
        tracker.update(9, [], rng)


# ---------------------------------------------------------------- filter


def fresh() -> tuple[list[float], list[list[float]]]:
    p = kalman.zeros()
    for i in range(3):
        p[i][i] = 100.0
        p[i + 3][i + 3] = 25.0
    return [10.0, 20.0, 30.0, 1.0, -2.0, 0.5], p


def test_prediction_moves_the_state_and_grows_the_uncertainty() -> None:
    x, p = fresh()
    before = p[0][0]
    kalman.predict(x, p, 2.0, 3.0)
    assert x == [12.0, 16.0, 31.0, 1.0, -2.0, 0.5]
    assert p[0][0] > before and p[3][3] > 25.0 and p[0][3] > 0.0


def test_a_zero_step_changes_nothing() -> None:
    x, p = fresh()
    x0, p0 = x[:], [r[:] for r in p]
    kalman.predict(x, p, 0.0, 3.0)
    assert (x, p) == (x0, p0)


def test_prediction_does_not_depend_on_how_often_the_filter_is_stepped() -> None:
    x1, p1 = fresh()
    x2, p2 = fresh()
    kalman.predict(x1, p1, 1.0, 3.0)
    for _ in range(20):
        kalman.predict(x2, p2, 0.05, 3.0)
    assert x1 == pytest.approx(x2, abs=1e-9)
    for i in range(6):
        assert p1[i] == pytest.approx(p2[i], rel=1e-9, abs=1e-9)


def test_a_scalar_update_matches_the_textbook_result() -> None:
    x = [0.0] * 6
    p = kalman.zeros()
    p[0][0] = 4.0
    s = kalman.update_scalar(x, p, [1.0, 0, 0, 0, 0, 0], 10.0, 1.0)
    assert s == 5.0
    assert x[0] == pytest.approx(8.0)  # gain 4/5
    assert p[0][0] == pytest.approx(0.8)  # (1 - 4/5) * 4


def test_updates_keep_the_covariance_symmetric_and_shrink_it() -> None:
    x, p = fresh()
    kalman.predict(x, p, 1.0, 3.0)
    h = [0.6, 0.8, 0.0, 0.0, 0.0, 0.0]
    before = kalman.innovation_variance(p, h, 1.0)
    kalman.update_scalar(x, p, h, 2.0, 1.0)
    assert kalman.innovation_variance(p, h, 1.0) < before
    assert all(p[i][j] == p[j][i] for i in range(6) for j in range(6))
    assert all(p[i][i] > 0 for i in range(6))


def test_sigmas_summarise_position_and_speed_uncertainty() -> None:
    _, p = fresh()
    assert kalman.position_sigma(p) == 10.0 and kalman.speed_sigma(p) == 5.0


# ---------------------------------------------------------------- measurement model


def test_polar_to_enu_agrees_with_the_sensor_geometry() -> None:
    truth = Truth("t", "rotary-small", 800.0, 1200.0, 150.0, 0.0, 0.0, 0.0)
    g = Geometry.between(ORIGIN, truth)
    x, y, z = polar_to_enu(ORIGIN, g.azimuth_deg, g.elevation_deg, g.slant_range_m)
    assert (x, y, z) == pytest.approx((800.0, 1200.0, 150.0), abs=1e-6)


def test_ray_is_a_unit_vector_along_the_bearing() -> None:
    e, n, u = ray(90.0, 0.0)
    assert (e, n, u) == pytest.approx((1.0, 0.0, 0.0), abs=1e-12)
    assert math.sqrt(sum(c * c for c in ray(37.0, 21.0))) == pytest.approx(1.0, abs=1e-12)


def test_a_perfect_report_has_zero_innovation_in_every_row() -> None:
    truth = Truth("t", "rotary-small", 800.0, 1200.0, 150.0, 5.0, 0.0, 0.0)
    g = Geometry.between(ORIGIN, truth)
    m = Measurement.from_view(
        view(
            azimuth_deg=g.azimuth_deg,
            elevation_deg=g.elevation_deg,
            range_m=g.slant_range_m,
            radial_speed_mps=g.radial_speed_mps,
        )
    )
    x = [800.0, 1200.0, 150.0, 5.0, 0.0, 0.0]
    rows = rows_for(m, ORIGIN, x, CFG)
    assert [r.kind for r in rows] == ["range", "azimuth", "elevation", "radial"]
    assert all(abs(r.innovation) < 1e-9 for r in rows)


def test_azimuth_innovations_wrap_across_north() -> None:
    x = [10.0, 1000.0, 6.0, 0, 0, 0]  # bearing about 0.57 degrees
    m = Measurement.from_view(view(azimuth_deg=359.5, range_m=None, radial_speed_mps=None))
    az = next(r for r in rows_for(m, ORIGIN, x, CFG) if r.kind == "azimuth")
    assert abs(az.innovation) < 0.03  # about 1 degree, not 359


def test_a_target_straight_above_has_no_azimuth_row() -> None:
    m = Measurement.from_view(view(range_m=None, radial_speed_mps=None))
    kinds = [r.kind for r in rows_for(m, ORIGIN, [0.0, 0.0, 500.0, 0, 0, 0], CFG)]
    assert kinds == ["elevation"]


def test_a_report_without_a_radial_sigma_uses_the_configured_one() -> None:
    m = Measurement.from_view(view(sigma_radial_mps=None))
    x = [800.0, 800.0, 100.0, 0, 0, 0]
    radial = next(r for r in rows_for(m, ORIGIN, x, CFG) if r.kind == "radial")
    assert radial.r == CFG.default_sigma_radial_mps**2


# ---------------------------------------------------------------- initiation and lifecycle


def test_a_range_report_starts_a_tentative_track_that_is_confirmed_after_three_hits() -> None:
    rig = lone_drone()
    rig.step(400)
    kinds = [k for _, k, _ in rig.events()]
    assert kinds[:2] == ["init", "confirm"]
    (_, _, track_id), (confirm_tick, _, _) = rig.events("init")[0], rig.events("confirm")[0]
    track = rig.tracker.tracks[track_id]
    assert track.status == "confirmed" and track.hit_ticks >= CFG.confirm_hits
    # radar updates every 1.2 s: init, then two more scans
    assert confirm_tick - rig.events("init")[0][0] == 48


def test_a_confirmed_track_follows_its_target_with_a_velocity_estimate() -> None:
    errors: list[float] = []
    speeds: list[float] = []
    for seed in (1, 2, 3, 4, 5):
        rig = Rig(lone_drone().spec, seed, [sensor("radar-1", radar_params(), ORIGIN)])
        for _ in range(70):
            rig.step(20)
            if rig.world.tick < 800:
                continue
            (track,) = rig.tracker.tracks.values()
            truth = rig.world.drones[0]
            errors.append(math.hypot(track.x[0] - truth.x, track.x[1] - truth.y))
            speeds.append(abs(track.x[3] - 15.0))
        assert rig.follows(track.id) == "alpha" and track.class_estimate()[0] == "rotary-small"
    # one radar at 1.5 km, 16 m cross-range noise per scan: tens of metres, a few m/s
    assert sum(errors) / len(errors) < 25.0
    assert sum(speeds) / len(speeds) < 3.0


def test_the_trainee_view_of_a_track_is_labelled_json_with_no_ground_truth() -> None:
    rig = lone_drone()
    rig.step(900)
    (v,) = rig.tracker.views(rig.world.tick)
    text = json.dumps(v)
    assert "alpha" not in text and "truth" not in text
    assert v["data_status"] == DATA_REFERENCE and v["status"] == "confirmed"
    assert v["id"] == v["label"] == "T001"
    assert set(v) >= {"position", "velocity", "speed_mps", "heading_deg", "sigma_position_m"}
    assert 80.0 < v["heading_deg"] < 100.0  # flying east


def test_data_status_is_sticky_reference_data() -> None:
    track = Track("T001", "T001", "tentative", 0, 0, 0, 0, [0.0] * 6, kalman.zeros(), {}, [])
    track.data_status = DATA_VERIFIED
    track.note_report(1, "s", None, DATA_VERIFIED)
    assert track.data_status == DATA_VERIFIED
    track.note_report(2, "s", "bird", DATA_REFERENCE)
    track.note_report(3, "s", "unknown", DATA_VERIFIED)
    assert track.data_status == DATA_REFERENCE
    assert track.votes == {"bird": 1} and track.class_estimate() == ("bird", 1.0)


def test_class_estimate_breaks_ties_by_name_and_is_none_without_votes() -> None:
    track = Track("T001", "T001", "tentative", 0, 0, 0, 0, [0.0] * 6, kalman.zeros(), {}, [])
    assert track.class_estimate() == (None, 0.0)
    track.votes = {"rotary-small": 2, "bird": 2, "unknown": 1}
    assert track.class_estimate() == ("bird", 0.4)


def test_a_track_coasts_through_a_short_outage_and_resumes_with_the_same_id() -> None:
    rig = lone_drone()
    rig.suite["radar-1"].inject(Degradation("radar-1", "outage", 900, 900 + 20 * 8))
    rig.step(1800)
    kinds = [(k, i) for _, k, i in rig.events()]
    assert kinds == [("init", "T001"), ("confirm", "T001"), ("coast", "T001"), ("resume", "T001")]
    assert list(rig.tracker.tracks) == ["T001"] and rig.follows("T001") == "alpha"
    assert rig.tracker.tracks["T001"].status == "confirmed"


def test_a_track_silent_for_too_long_is_dropped_as_lost() -> None:
    rig = lone_drone()
    rig.suite["radar-1"].inject(Degradation("radar-1", "outage", 900, 900 + 20 * 30))
    rig.step(1700)
    drops = [e for _, r in rig.history for e in r.events if e.kind == "drop"]
    assert [(e.track_id, e.payload["reason"]) for e in drops] == [("T001", "lost")]
    assert rig.tracker.graveyard["T001"]["reason"] == "lost"


def test_a_lone_clutter_plot_never_becomes_a_confirmed_track() -> None:
    rig = lone_drone()
    tracker = rig.tracker
    plot = Measurement.from_view(view(tick=0, range_m=900.0, radial_speed_mps=None))
    tracker.update(0, [plot], rig.rng)
    assert [t.status for t in tracker.tracks.values()] == ["tentative"]
    for tick in range(1, 200):
        tracker.update(tick, [], rig.rng)
    assert tracker.tracks == {}
    assert tracker.graveyard["T001"]["reason"] == "unconfirmed"


def test_a_tentative_track_must_be_confirmed_inside_its_window() -> None:
    tracker = Tracker(
        {"radar-1": ORIGIN}, config=TrackerConfig(confirm_window_s=1.0, tentative_drop_s=60)
    )
    rng = RngStreams(1)
    tracker.update(0, [Measurement.from_view(view(tick=0, range_m=900.0))], rng)
    for tick in range(1, 30):
        tracker.update(tick, [], rng)
    assert tracker.graveyard["T001"]["reason"] == "unconfirmed"


def test_association_under_clutter_keeps_the_real_track_on_the_real_target() -> None:
    noisy = radar_params(false_alarm_rate=(1.0, "count"), false_alarm_slots=(4, "count"))
    for seed in (1, 2, 3, 4, 5):
        spec = scenario(
            [drone("alpha", "rotary-small", (-600, 1500, 150), 90, 15, [(1500, 1500, 150)])]
        )
        rig = Rig(spec, seed, [sensor("radar-1", noisy, ORIGIN)])
        rig.step(1500)
        assert rig.history, seed
        real = [t for t in rig.tracker.tracks.values() if rig.follows(t.id) == "alpha"]
        assert len(real) == 1 and real[0].status == "confirmed", seed
        assert (
            math.hypot(real[0].x[0] - rig.world.drones[0].x, real[0].x[1] - rig.world.drones[0].y)
            < 60
        )
        # clutter did start tracks, so the test is not vacuous
        assert len(rig.events("init")) > 1, seed


def confirmed_at(tracker: Tracker, track_id: str, x: float, vx: float) -> Track:
    p = kalman.zeros()
    for i in range(3):
        p[i][i] = 100.0
        p[i + 3][i + 3] = 4.0
    track = Track(track_id, track_id, "confirmed", 0, 0, 0, 5, [x, 1500.0, 150.0, vx, 0.0, 0.0], p)
    tracker.insert(track)
    return track


def test_two_confirmed_tracks_that_stay_indistinguishable_are_folded_into_one() -> None:
    tracker = Tracker({"radar-1": ORIGIN}, config=TrackerConfig(duplicate_hold_s=1.0))
    rng = RngStreams(1)
    older, younger = tracker.allocate_id(), tracker.allocate_id()
    confirmed_at(tracker, older, 0.0, 15.0)
    confirmed_at(tracker, younger, 6.0, 15.5)
    events = [e for tick in range(40) for e in tracker.update(tick, [], rng).events]
    drops = [e for e in events if e.kind == "drop"]
    assert [(e.track_id, e.payload["reason"], e.payload["merged_into"]) for e in drops] == [
        (younger, "duplicate", older)
    ]
    assert drops[0].tick == 19  # the 20th consecutive tick at 20 Hz = one second


def test_crossing_tracks_are_not_folded_however_close_they_pass() -> None:
    tracker = Tracker({"radar-1": ORIGIN}, config=TrackerConfig(duplicate_hold_s=0.5))
    rng = RngStreams(1)
    confirmed_at(tracker, tracker.allocate_id(), 0.0, 15.0)
    confirmed_at(tracker, tracker.allocate_id(), 3.0, -15.0)  # same place, opposite velocity
    assert [e for tick in range(20) for e in tracker.update(tick, [], rng).events] == []


def test_a_pair_the_radar_cannot_resolve_is_one_track_not_two() -> None:
    # 8 m apart at 1.5 km with 16 m of cross-range noise: the second target's reports sit inside
    # the first track's gate, so no second track is started (the unresolved-pair case).
    spec = scenario(
        [
            drone("alpha", "rotary-small", (-600, 1500, 150), 90, 15, [(1500, 1500, 150)]),
            drone("bravo", "rotary-small", (-600, 1508, 150), 90, 15, [(1500, 1508, 150)]),
        ]
    )
    rig = Rig(spec, 3, [sensor("radar-1", radar_params(), ORIGIN)])
    rig.step(2400)
    assert [t.status for t in rig.tracker.tracks.values()] == ["confirmed"]
    assert sum(len(r.ambiguities) for _, r in rig.history) > 0


def test_a_lone_target_never_gets_a_second_track_from_a_gate_edge_outlier() -> None:
    for seed in range(1, 41):
        rig = Rig(lone_drone().spec, seed, [sensor("radar-1", radar_params(), ORIGIN)])
        rig.step(1500)
        assert len(rig.events("init")) == 1, seed


def test_an_outlier_outside_the_exclusion_zone_still_starts_a_track() -> None:
    tracker = Tracker({"radar-1": ORIGIN})
    rng = RngStreams(1)
    confirmed_at(tracker, tracker.allocate_id(), 0.0, 0.0)
    far = Measurement.from_view(view(tick=0, azimuth_deg=135.0, range_m=1200.0, elevation_deg=3.0))
    tracker.update(0, [far], rng)
    assert sorted(tracker.tracks) == ["T001", "T002"]


# ---------------------------------------------------------------- fusion across sensors


def test_bearing_only_sensors_fuse_into_a_radar_track() -> None:
    eo = profile("eo-generic-day", pixels_h=(8000, "px"), fov_wide=(60, "deg"))
    spec = scenario(
        [drone("alpha", "rotary-small", (-600, 1500, 150), 90, 15, [(1500, 1500, 150)])]
    )
    rig = Rig(
        spec,
        5,
        [
            sensor("radar-1", radar_params(), ORIGIN),
            sensor("eo-1", eo, Vec3(x=30.0, y=0.0, z=6.0), 0.0),
        ],
    )
    rig.step(1400)
    (track,) = rig.tracker.tracks.values()
    assert track.sensors == ["eo-1", "radar-1"]
    assert rig.follows(track.id) == "alpha" and track.status == "confirmed"


def test_bearing_only_sensors_alone_start_a_track_by_triangulation() -> None:
    eo = profile("eo-generic-day", pixels_h=(30000, "px"), fov_wide=(120, "deg"))
    spec = scenario([drone("alpha", "rotary-small", (-100, 600, 150), 90, 10, [(500, 600, 150)])])
    sensors = [
        sensor("eo-1", eo, Vec3(x=-400.0, y=0.0, z=6.0), 45.0),
        sensor("eo-2", eo, Vec3(x=400.0, y=0.0, z=6.0), 0.0),
    ]
    rig = Rig(spec, 4, sensors)
    rig.step(900)
    init = rig.events("init")
    assert init, "no track was triangulated"
    (track,) = [t for t in rig.tracker.tracks.values() if rig.follows(t.id) == "alpha"]
    assert track.status == "confirmed" and track.sensors == ["eo-1", "eo-2"]
    first = rig.history[next(i for i, (t, _) in enumerate(rig.history) if t == init[0][0])][1]
    assert {rig.truth[a.ref] for a in first.associations} == {"alpha"}  # both rays were its


def test_parallel_rays_are_never_triangulated() -> None:
    tracker = Tracker({"a": Vec3(x=0.0, y=0.0, z=0.0), "b": Vec3(x=1.0, y=0.0, z=0.0)})
    rng = RngStreams(1)
    a = Measurement.from_view(view(sensor_id="a", range_m=None, radial_speed_mps=None, tick=0))
    b = Measurement.from_view(view(sensor_id="b", range_m=None, radial_speed_mps=None, tick=0))
    tracker.update(0, [a, b], rng)
    assert tracker.tracks == {}


def test_two_bearings_from_one_sensor_are_not_a_fix() -> None:
    tracker = Tracker({"a": ORIGIN})
    rng = RngStreams(1)
    one = Measurement.from_view(view(sensor_id="a", range_m=None, radial_speed_mps=None, tick=0))
    two = Measurement.from_view(
        view(sensor_id="a", range_m=None, radial_speed_mps=None, tick=0, azimuth_deg=100.0)
    )
    tracker.update(0, [one, two], rng)
    assert tracker.tracks == {}


def test_skew_rays_that_miss_each_other_are_not_triangulated() -> None:
    tracker = Tracker({"a": Vec3(x=0.0, y=0.0, z=0.0), "b": Vec3(x=1000.0, y=0.0, z=0.0)})
    rng = RngStreams(1)
    a = Measurement.from_view(
        view(
            sensor_id="a",
            range_m=None,
            radial_speed_mps=None,
            tick=0,
            azimuth_deg=45,
            elevation_deg=0,
        )
    )
    b = Measurement.from_view(
        view(
            sensor_id="b",
            range_m=None,
            radial_speed_mps=None,
            tick=0,
            azimuth_deg=315,
            elevation_deg=40,
        )
    )
    tracker.update(0, [a, b], rng)
    assert tracker.tracks == {}


# ---------------------------------------------------------------- randomness, determinism, state


def test_exactly_one_tracking_draw_is_taken_per_report() -> None:
    rig = lone_drone()
    reports = 0
    for _ in range(600):
        found = [Measurement.from_view(d.trainee_view()) for d in rig.suite.detect(rig.world)]
        reports += len(found)
        rig.tracker.update(rig.world.tick, found, rig.world.rng)
        rig.world.step()
    assert reports > 3
    mirror = RngStreams(rig.seed)
    for _ in range(reports):
        mirror.uniform("tracking")
    assert rig.rng.state()["tracking"] == mirror.state()["tracking"]


def test_a_run_repeats_exactly_and_the_gate_table_is_the_chi_square_99_percent() -> None:
    def run() -> list[tuple[int, str, str]]:
        rig = lone_drone()
        rig.step(1500)
        return rig.events()

    assert run() == run() != []
    assert CHI2_GATE == {1: 6.635, 2: 9.21, 3: 11.345, 4: 13.277}


def test_restoring_tracker_and_world_streams_continues_exactly() -> None:
    first = lone_drone()
    first.step(800)
    saved = first.tracker.state()
    rng_state = first.rng.state()
    first.step(600)
    expected = first.tracker.state()

    second = lone_drone()
    second.step(800)
    second.tracker.restore(json.loads(json.dumps(saved)))
    second.rng.restore(rng_state)
    assert second.tracker.state() == saved
    second.step(600)
    assert second.tracker.state() == expected


def test_a_policy_that_pairs_outside_the_gate_is_refused() -> None:
    from sim.tracking import Component, Resolution

    class Bad:
        def resolve(self, component: Component, draw: float) -> Resolution:
            return Resolution("swap", (("T001", 99),))

    spec = scenario(
        [
            drone("alpha", "rotary-small", (-600, 1500, 150), 90, 15, [(1500, 1500, 150)]),
            drone("bravo", "rotary-small", (-600, 1512, 150), 90, 15, [(1500, 1512, 150)]),
        ]
    )
    rig = Rig(spec, 3, [sensor("radar-1", radar_params(), ORIGIN)], policy=Bad())
    with pytest.raises(ValueError, match="outside the gate"):
        rig.step(1400)


def test_ambiguity_is_reported_only_where_gates_overlap() -> None:
    def ambiguities(separation: float) -> int:
        spec = scenario(
            [
                drone("alpha", "rotary-small", (-600, 1500, 150), 90, 15, [(1500, 1500, 150)]),
                drone(
                    "bravo",
                    "rotary-small",
                    (-600, 1500 + separation, 150),
                    90,
                    15,
                    [(1500, 1500 + separation, 150)],
                ),
            ]
        )
        rig = Rig(spec, 3, [sensor("radar-1", radar_params(), ORIGIN)])
        rig.step(1000)
        return sum(len(r.ambiguities) for _, r in rig.history)

    assert ambiguities(30.0) > 0
    assert ambiguities(1200.0) == 0


def test_detmath_is_what_the_model_uses_for_angles() -> None:
    assert detmath.wrap180(359.5 - 0.57) < 0
