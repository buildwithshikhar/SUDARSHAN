"""The sensor picture inside a World: determinism, replay, snapshots, actions and who sees what."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import JsonValue

from app.contracts import ActionRecord, ScenarioSpec
from app.contracts.common import Vec3
from sim import replay
from sim.sensors import SensorSuite
from sim.tracking import AiAssist, ErrorPolicy, Tracker, TruthLedger
from sim.tracking.picture import (
    DATA_NOTICE,
    TRAINEE_EVENT_TYPES,
    TRUTH_EVENT_TYPES,
    Picture,
)
from sim.world import World

from .sim_cases import act, kestrel
from .test_sensor_models_together import suite_and_world
from .tracking_cases import crossing_threats
from .tracking_rig import profile, radar_params, scenario, sensor

API = Path(__file__).resolve().parents[1]
#: Documented swap through the World path (radar only, no false alarms, default ErrorPolicy):
#: seed 195, tick 624, T001 and T002 exchange drones; the filter undoes it on its own at tick 696.
SWAP_SEED = 195
SWAP_TICK = 624
OPERATOR = "trainee:op-1"


def crossing(seed: int, *, with_ir: bool = False) -> tuple[ScenarioSpec, World]:
    spec = scenario(crossing_threats())
    sensors = [sensor("radar-1", radar_params(), Vec3(x=0, y=0, z=6))]
    if with_ir:
        sensors.append(sensor("ir-1", profile("ir-generic-thermal"), Vec3(x=20, y=0, z=6)))
    picture = Picture(
        spec,
        seed,
        SensorSuite(sensors),
        Tracker({s.id: s.position for s in sensors}, policy=ErrorPolicy()),
        TruthLedger(),
        AiAssist(seed),
    )
    return spec, World(spec, seed, picture=picture)


def run(world: World, ticks: int, actions: list[ActionRecord] | None = None) -> World:
    return replay.advance(world, ticks, actions or [])


def kestrel_with_sensors() -> ScenarioSpec:
    return suite_and_world()[1].spec


# ---------------------------------------------------------------- the world without a picture


def test_a_bare_world_has_no_picture_and_hashes_as_before() -> None:
    world = World(kestrel(), 3)
    assert world.picture is None and "picture" not in world.state()


def test_a_track_action_without_a_picture_is_rejected_and_logged() -> None:
    world = World(kestrel(), 3)
    world.step()
    world.step([act(1, OPERATOR, "track-drop", track="T001")])
    rejected = [r for r in world.log.records if r.type == "action.rejected"]
    assert rejected and "no sensor picture" in str(rejected[0].payload["reason"])


def test_the_picture_must_be_built_for_the_same_seed() -> None:
    spec = kestrel_with_sensors()
    with pytest.raises(ValueError, match="different seed"):
        World(spec, 4, picture=Picture.build(spec, 5))


# ---------------------------------------------------------------- determinism, replay, snapshot


def test_a_session_with_a_picture_repeats_exactly() -> None:
    first = run(crossing(7)[1], 1500)
    second = run(crossing(7)[1], 1500)
    assert first.state_hash() == second.state_hash()
    assert first.log.head == second.log.head and "picture" in first.state()
    assert run(crossing(8)[1], 1500).state_hash() != first.state_hash()


def test_the_hash_is_the_same_in_another_process_with_another_hash_salt() -> None:
    code = (
        "from tests.test_tracking_wiring import crossing, run\n"
        "print(run(crossing(7)[1], 1500).state_hash())"
    )
    hashes = set()
    for salt in ("0", "12345"):
        env = {**os.environ, "PYTHONHASHSEED": salt, "PYTHONPATH": str(API)}
        out = subprocess.run(  # noqa: S603
            [sys.executable, "-c", code],
            cwd=API,
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )
        hashes.add(out.stdout.strip())
    assert hashes == {run(crossing(7)[1], 1500).state_hash()}


def test_replay_reproduces_a_session_with_a_picture_and_notices_one_without() -> None:
    spec = kestrel_with_sensors()
    actions = [act(60, OPERATOR, "designate", target="contact-a")]
    _, record = replay.run(spec, 11, actions, 1200, picture=True)
    assert replay.replay(spec, record, picture=True).matches
    assert not replay.replay(spec, record).matches


def test_restoring_a_snapshot_continues_exactly() -> None:
    spec, straight = crossing(SWAP_SEED)
    actions = [act(640, OPERATOR, "track-relabel", track="T001", label="T002", exchange=True)]
    run(straight, 900, actions)

    _, world = crossing(SWAP_SEED)
    run(world, 500)
    snapshot = json.loads(json.dumps(world.snapshot()))
    _, fresh = crossing(SWAP_SEED)
    resumed = World.restore(spec, snapshot, picture=fresh.picture)
    assert resumed.state_hash() == world.state_hash()
    run(resumed, 900, actions)
    assert resumed.state_hash() == straight.state_hash()
    assert resumed.log.head == straight.log.head


def test_a_snapshot_and_a_picture_must_agree_about_having_one() -> None:
    spec, world = crossing(SWAP_SEED)
    run(world, 40)
    with pytest.raises(ValueError, match="has a sensor picture but none was given"):
        World.restore(spec, world.snapshot())
    bare = World(spec, SWAP_SEED)
    with pytest.raises(ValueError, match="none"):
        World.restore(spec, bare.snapshot(), picture=crossing(SWAP_SEED)[1].picture)


# ---------------------------------------------------------------- the documented swap and its fix


def swaps(world: World) -> list[tuple[int, str, JsonValue]]:
    return [
        (int(str(r.payload["tick"])), str(r.payload["track"]), r.payload["partner"])
        for r in world.log.records
        if r.type == "ledger.swap"
    ]


def test_the_seeded_crossing_swaps_at_the_documented_tick() -> None:
    world = run(crossing(SWAP_SEED)[1], 660)
    assert swaps(world) == [(SWAP_TICK, "T001", "T002"), (SWAP_TICK, "T002", "T001")]
    assert world.picture is not None
    assert [e["kind"] for e in world.picture.ledger.open_errors()] == ["swap"]  # unfixed: scored
    assert swaps(run(crossing(1)[1], 700)) == []  # not every seed swaps
    # left alone, the filter's own memory pulls the tracks back to their drones at tick 696
    later = run(crossing(SWAP_SEED)[1], 700)
    assert later.picture is not None and later.picture.ledger.open_errors() == []


def test_a_relabel_logged_as_an_action_restores_the_true_identity_in_the_log() -> None:
    fix = act(SWAP_TICK + 16, OPERATOR, "track-relabel", track="T001", label="T002", exchange=True)
    world = run(crossing(SWAP_SEED)[1], 660, [fix])
    by_type = {t: [r for r in world.log.records if r.type == t] for t in ("ledger.restored",)}
    (restored,) = by_type["ledger.restored"]
    assert restored.payload["tick"] == SWAP_TICK + 16 and restored.payload["error_kind"] == "swap"
    assert restored.payload["truths"] == ["alpha", "bravo"]
    types = [r.type for r in world.log.records if r.seq >= restored.seq - 3]
    assert "action.track_relabel" in types and "track.relabel" in types
    assert world.picture is not None and world.picture.ledger.consistent("T001")
    _, record = replay.run(crossing(SWAP_SEED)[0], SWAP_SEED, [fix], 700, picture=False)
    assert record.actions[0].action == "track-relabel"  # it is an ordinary logged input


# ---------------------------------------------------------------- the track actions


def test_merge_split_and_drop_run_through_the_action_log() -> None:
    _, world = crossing(5)
    run(world, 400)
    assert world.picture is not None
    tracker = world.picture.tracker
    first = next(iter(tracker.tracks))
    actions = [
        act(400, OPERATOR, "track-split", track=first),
        act(420, OPERATOR, "track-relabel", track=first, label="ALPHA"),
    ]
    run(world, 440, actions)
    assert tracker.tracks[first].label == "ALPHA"
    clone = [t for t in tracker.tracks if t not in (first,) and tracker.tracks[t].born == 400]
    assert clone
    run(world, 480, [act(440, OPERATOR, "track-merge", tracks=[first, clone[0]])])
    assert clone[0] not in tracker.tracks and tracker.graveyard[clone[0]]["merged_into"] == first
    run(world, 500, [act(480, OPERATOR, "track-drop", track=first)])
    assert first not in tracker.tracks and tracker.graveyard[first]["reason"] == "operator"
    types = {r.type for r in world.log.records}
    assert {"track.split", "track.merge", "track.drop", "track.relabel"} <= types


def test_a_bad_track_command_is_rejected_with_its_reason() -> None:
    _, world = crossing(5)
    run(world, 100, [act(50, OPERATOR, "track-drop", track="T404")])
    (rejected,) = [r for r in world.log.records if r.type == "action.rejected"]
    assert rejected.payload["action"] == "track-drop" and "T404" in str(rejected.payload["reason"])


def test_a_cue_points_a_cueable_sensor_at_a_track_and_a_radar_refuses() -> None:
    _, world = crossing(5, with_ir=True)
    run(world, 400)
    assert world.picture is not None
    track = next(iter(world.picture.tracker.tracks))
    wide = world.picture.suite["ir-1"].pointing.fov_deg
    run(world, 410, [act(400, OPERATOR, "sensor-cue", sensor="ir-1", track=track)])
    pointing = world.picture.suite["ir-1"].pointing
    assert pointing.fov_deg is not None and wide is not None and pointing.fov_deg < wide
    run(world, 420, [act(410, OPERATOR, "sensor-cue", sensor="radar-1", track=track)])
    types = [r.type for r in world.log.records]
    assert "sensor.cue" in types and "action.sensor_cue" in types
    rejected = [r for r in world.log.records if r.type == "action.rejected"]
    assert len(rejected) == 1 and "cannot be cued" in str(rejected[0].payload["reason"])


# ---------------------------------------------------------------- who sees what


def test_trainee_events_and_frames_carry_no_ground_truth() -> None:
    spec = kestrel_with_sensors()
    world = World(spec, 11, picture=Picture.build(spec, 11))
    forbidden = [t.id for t in spec.threats] + [t.class_id for t in spec.threats]
    frames = []
    while world.tick < 3200:
        world.step()
        if (world.tick - 1) % 24 == 0:  # frames just after a radar scan
            assert world.picture is not None
            frames.append(world.picture.trainee_frame(world.tick))
    seen = {r.type for r in world.log.records}
    safe = [r for r in world.log.records if r.type in TRAINEE_EVENT_TYPES]
    assert safe and {r.type for r in safe} >= {"track.init", "track.confirm"}
    for r in safe:
        text = json.dumps(r.payload)
        assert not any(word in text for word in forbidden), (r.type, text)
    text = json.dumps(frames)  # reported classes are what sensors say, not the truth
    assert not any(t.id in text for t in spec.threats) and "truth" not in text
    assert any(f["tracks"] for f in frames) and any(f["reports"] for f in frames)
    # truth events exist, are listed as truth events, and every other type is a plain sim event
    assert seen & TRUTH_EVENT_TYPES
    plain = {"session.start", "threat.spawn", "threat.waypoint", "threat.route_end"}
    assert seen <= TRAINEE_EVENT_TYPES | TRUTH_EVENT_TYPES | plain | {"threat.despawn"}


def test_everything_a_trainee_is_shown_is_labelled_reference_data() -> None:
    spec = kestrel_with_sensors()
    world = World(spec, 11, picture=Picture.build(spec, 11))
    shown = 0
    assert world.picture is not None
    while world.tick < 3200:
        world.step()
        frame = world.picture.trainee_frame(world.tick)
        assert frame["data_notice"] == DATA_NOTICE
        for item in [*frame["reports"], *frame["tracks"], *frame["assist"]]:
            assert item["data_status"] == "reference"
            shown += 1
    assert shown > 20


def test_the_ground_truth_reference_of_reports_is_not_kept_forever() -> None:
    _, world = crossing(5)
    run(world, 2400)
    assert world.picture is not None
    assert len(world.picture.state()["truth"]) < 60


def test_assist_records_are_instructor_events_and_views_are_what_the_trainee_gets() -> None:
    world = run(crossing(5)[1], 1500)
    assert world.picture is not None
    records = [r for r in world.log.records if r.type == "assist.assess"]
    assert records and "true_class" in records[0].payload
    frame = world.picture.trainee_frame(world.tick)
    assert frame["assist"] and all("true_class" not in v for v in frame["assist"])
