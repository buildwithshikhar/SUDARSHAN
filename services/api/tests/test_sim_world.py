"""World tick, actions, determinism across processes, replay, tampering and snapshot/restore."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from app.contracts import SessionRecord
from sim.eventlog import ChainError, verify
from sim.replay import advance, finish, replay, run
from sim.world import ActionError, World, spawn_tick

from .sim_cases import KESTREL_ACTIONS, act, kestrel

API_DIR = Path(__file__).resolve().parents[1]


def types(world: World) -> list[str]:
    return [r.type for r in world.log.records]


# ---------------------------------------------------------------------------- tick model


def test_tick_and_time_of_day() -> None:
    world = World(kestrel(), 1)
    assert (world.tick, world.time_s) == (0, 0.0)
    advance(world, 30)
    assert world.time_s == 1.5
    assert world.time_of_day_h == pytest.approx(5.75 + 1.5 / 3600)
    assert spawn_tick(0.15) == 3 and spawn_tick(8) == 160 and spawn_tick(8.01) == 161


def test_the_scenario_plays_out_as_scripted() -> None:
    world, _ = run(kestrel(), 240117, [], 8400)
    spawns = [r for r in world.log.records if r.type == "threat.spawn"]
    assert [(r.payload["id"], r.t) for r in spawns] == [("contact-a", 8.0), ("contact-b", 95.0)]
    a = [r.payload.get("index") for r in world.log.records if r.payload.get("id") == "contact-a"]
    assert a[1:4] == [0, 1, 2]  # every waypoint reached in order
    assert world.drones[0].mode == "loiter" and world.drones[0].status == "active"
    assert world.drones[1].status == "despawned"
    assert types(world)[0] == "session.start" and types(world)[-1] == "session.end"


# ---------------------------------------------------------------------------- actions


def test_actions_change_annotations_and_log_events() -> None:
    world, _ = run(kestrel(), 240117, KESTREL_ACTIONS, 6000)
    a, b = world.drones
    assert a.designated and a.assigned_class == "rotary-small" and a.assigned_identity == "suspect"
    assert b.designated and b.assigned_class is None
    rejected = [r.payload["reason"] for r in world.log.records if r.type == "action.rejected"]
    assert rejected == [
        "no active contact 'contact-b'",
        "only an instructor can change the weather",
    ]
    assert world.weather.condition == "fog" and world.weather.wind_speed_mps == 7.5
    weather = [r for r in world.log.records if r.type == "weather.set"]
    assert [r.actor for r in weather] == ["instructor:lead", "instructor:lead"]


@pytest.mark.parametrize(
    ("action", "reason"),
    [
        (act(200, "trainee:op-1", "classify", target="contact-a"), "classify needs a class_id"),
        (act(200, "trainee:op-1", "assess", target="contact-a", identity="x"), "needs an identity"),
        (act(200, "trainee:op-1", "engage", target="contact-a"), "needs an effector_class"),
        (act(200, "trainee:op-1", "designate", target="nobody"), "no active contact"),
        (act(200, "instructor:a", "set-weather", visibility_m=-5), "invalid weather"),
    ],
)
def test_invalid_actions_are_rejected_not_raised(action: object, reason: str) -> None:
    world, _ = run(kestrel(), 3, [action], 201)  # type: ignore[list-item]
    rejected = [r for r in world.log.records if r.type == "action.rejected"]
    assert len(rejected) == 1 and reason in str(rejected[0].payload["reason"])


def test_actions_must_match_the_tick() -> None:
    world = World(kestrel(), 3)
    with pytest.raises(ActionError, match="applied at tick 0"):
        world.step([act(5, "trainee:op-1", "hold")])
    with pytest.raises(ActionError, match="at or after tick 10"):
        advance(World(kestrel(), 3), 10, [act(10, "trainee:op-1", "hold")])


def test_actions_change_the_state_hash() -> None:
    plain, _ = run(kestrel(), 5, [], 1000)
    acted, _ = run(kestrel(), 5, [act(500, "trainee:op-1", "designate", target="contact-a")], 1000)
    assert plain.state_hash() != acted.state_hash()


# ---------------------------------------------------------------------------- determinism

SCRIPT = """
import sys
sys.path.insert(0, {tests!r})
from sim.replay import run
from sim_cases import KESTREL_ACTIONS, kestrel
world, record = run(kestrel(), 240117, KESTREL_ACTIONS, 10_000)
print(record.final_state_hash, world.log.head)
"""


def test_same_inputs_give_the_same_hash_after_10000_ticks_in_two_processes() -> None:
    script = SCRIPT.format(tests=str(API_DIR / "tests"))
    outputs = []
    for hash_seed in ("1", "2"):  # different str-hash salts: dict and set order cannot leak in
        env = os.environ | {"PYTHONHASHSEED": hash_seed}
        done = subprocess.run(  # noqa: S603 - fixed interpreter and script
            [sys.executable, "-c", script],
            cwd=API_DIR,
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )
        outputs.append(done.stdout.split())
    world, record = run(kestrel(), 240117, KESTREL_ACTIONS, 10_000)
    assert outputs[0] == outputs[1] == [record.final_state_hash, world.log.head]


def test_a_different_seed_gives_a_different_run() -> None:
    assert (
        run(kestrel(), 1, [], 2000)[1].final_state_hash
        != run(kestrel(), 2, [], 2000)[1].final_state_hash
    )


# ---------------------------------------------------------------------------- replay


def test_replay_reproduces_every_event_and_the_final_state() -> None:
    _, record = run(kestrel(), 240117, KESTREL_ACTIONS, 8400)
    stored = SessionRecord.model_validate_json(record.model_dump_json())  # through JSON and back
    result = replay(kestrel(), stored)
    assert result.matches and result.first_divergent_seq is None
    assert result.final_state_hash == record.final_state_hash
    assert verify(stored.events, expected_head=stored.events[-1].hash) is None


def test_replay_names_the_first_divergent_event() -> None:
    _, record = run(kestrel(), 240117, KESTREL_ACTIONS, 6000)
    k = 7
    events = list(record.events)
    events[k] = events[k].model_copy(update={"payload": {"id": "contact-z"}})
    result = replay(kestrel(), record.model_copy(update={"events": events}))
    assert not result.matches and result.first_divergent_seq == k
    shorter = replay(kestrel(), record.model_copy(update={"events": list(record.events)[:-1]}))
    assert shorter.first_divergent_seq == len(record.events) - 1
    wrong_hash = replay(kestrel(), record.model_copy(update={"final_state_hash": "0" * 64}))
    assert not wrong_hash.matches and wrong_hash.first_divergent_seq is None


def test_replay_refuses_another_scenario() -> None:
    _, record = run(kestrel(), 1, [], 10)
    other = kestrel().model_copy(update={"version": "1.0.1"})
    with pytest.raises(ValueError, match="different scenario"):
        replay(other, record)


@pytest.mark.parametrize("k", [0, 1, 5, 12, -1])
def test_tampering_with_any_recorded_event_breaks_the_chain_there(k: int) -> None:
    _, record = run(kestrel(), 240117, KESTREL_ACTIONS, 6000)
    rows = [e.model_dump(mode="json") for e in record.events]
    k = k % len(rows)
    rows[k]["payload"]["tampered"] = True
    assert verify(rows) == k
    with pytest.raises(ChainError) as caught:
        World.restore(
            kestrel(), {**World(kestrel(), 1).snapshot(), "events": rows, "event_count": len(rows)}
        )
    assert caught.value.seq == k


# ---------------------------------------------------------------------------- snapshot / restore


@pytest.mark.parametrize("n", [0, 1, 159, 160, 700, 1900, 5999])
def test_restoring_a_snapshot_at_n_and_running_to_m_matches_a_straight_run(n: int) -> None:
    m = 6000
    straight = advance(World(kestrel(), 240117), m, KESTREL_ACTIONS)
    first = advance(World(kestrel(), 240117), n, [a for a in KESTREL_ACTIONS if a.tick < n])
    stored = json.loads(json.dumps(first.snapshot()))  # snapshots survive plain JSON storage
    resumed = advance(
        World.restore(kestrel(), stored), m, [a for a in KESTREL_ACTIONS if a.tick >= n]
    )
    assert resumed.state_hash() == straight.state_hash()
    assert resumed.log.records == straight.log.records
    assert finish(resumed) == finish(straight)


def test_branching_from_a_snapshot_leaves_the_original_untouched() -> None:
    world = advance(World(kestrel(), 240117), 1000)
    snap = world.snapshot()
    branch = World.restore(kestrel(), snap)
    advance(branch, 1500, [act(1200, "instructor:lead", "set-weather", wind_speed_mps=20)])
    advance(world, 1500)
    assert branch.state_hash() != world.state_hash()
    assert (
        World.restore(kestrel(), snap).state_hash() == World.restore(kestrel(), snap).state_hash()
    )


def test_restore_refuses_snapshots_that_do_not_fit() -> None:
    spec = kestrel()
    snap = advance(World(spec, 1), 300).snapshot()
    with pytest.raises(ValueError, match="not a sim-snapshot.v1"):
        World.restore(spec, snap | {"format": "other"})
    with pytest.raises(ValueError, match="snapshot is for"):
        World.restore(spec.model_copy(update={"version": "2.0.0"}), snap)
    with pytest.raises(ValueError, match="recorded head"):
        World.restore(spec, snap | {"event_head": "f" * 64})
    with pytest.raises(ValueError, match="do not match the scenario"):
        World.restore(spec, snap | {"drones": snap["drones"][:1]})


def test_a_drone_blown_out_of_the_play_area_is_retired() -> None:
    gale = act(200, "instructor:lead", "set-weather", wind_speed_mps=40, wind_from_deg=225)
    world, _ = run(kestrel(), 7, [gale], 8400)
    exits = [r for r in world.log.records if r.payload.get("reason") == "left-area"]
    assert exits and exits[0].payload["id"] == "contact-a"
    gone = world.drones[0]
    assert gone.status == "despawned" and max(abs(gone.x), abs(gone.y)) > 6000
