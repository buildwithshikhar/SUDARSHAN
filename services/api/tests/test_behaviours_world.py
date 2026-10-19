"""Groups and clutter motion inside the world: determinism, cohesion, leader loss, intents,
clutter, envelope respect, cost, and who may see the events."""

import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pytest

from sim import audience
from sim.behaviours import metrics
from sim.constants import DT
from sim.entity import Drone
from sim.replay import replay
from sim.replay import run as run_session
from sim.world import World
from tests.behaviour_support import (
    active,
    group,
    member,
    run,
    scenario,
    swarm_scenario,
    wp,
)
from tests.sim_cases import act, kestrel

API_DIR = Path(__file__).resolve().parents[1]


def gstate(world: World) -> dict[str, Any]:
    state: dict[str, Any] = world.state()["groups"]["g1"]
    return state


def remove(world: World, member_id: str) -> None:
    next(d for d in world.drones if d.id == member_id).status = "despawned"


def events(world: World, kind: str) -> list[Any]:
    return [r for r in world.log.records if r.type == kind]


def order(world: World) -> tuple[float, float]:
    a = active(world)
    return (
        metrics.polarisation([d.ux for d in a], [d.uy for d in a]),
        metrics.radius_of_gyration([d.x for d in a], [d.y for d in a]),
    )


def mean_order(world: World, ticks: int = 300) -> tuple[float, float]:
    """Polarisation and radius of gyration averaged over the next `ticks` ticks."""
    p = r = 0.0
    samples = ticks // 10
    for _ in range(samples):
        run(world, 10)
        po, ro = order(world)
        p, r = p + po, r + ro
    return p / samples, r / samples


def lf(n: int = 8, **kw: Any) -> Any:
    options: dict[str, Any] = {
        "topology": "leader-follower",
        "leader": "m00",
        "route": [wp(8000.0, 0.0, 60.0, 10.0)],
        "discipline": 1.0,
        "link_range_m": 400.0,
        "leader_loss_hold_s": 3.0,
    }
    return swarm_scenario(n, **(options | kw))


# ---------------------------------------------------------------------------- state and hashing


def test_a_scenario_without_groups_has_no_groups_key_and_hashes_as_before() -> None:
    world = World(kestrel(), 240117)
    run(world, 50)
    assert "groups" not in world.state() and world.groups is None


def test_a_scenario_with_groups_keeps_their_state_in_the_hash() -> None:
    world = World(lf(), 1)
    run(world, 40)
    state = gstate(world)
    assert state["control"] == "leader" and state["leader"] == "m00" and state["formed"]
    before = world.state_hash()
    world.groups.controllers[0].gx += 1.0  # type: ignore[union-attr]
    # the guide is not used by a leader-follower group in control, but all of it is hashed
    assert world.state_hash() != before


# ---------------------------------------------------------------------------- determinism

SCRIPT = """
import sys
sys.path.insert(0, {root!r})
from tests.behaviour_support import swarm_scenario, run
from sim.world import World
spec = swarm_scenario(16, scatter=True, discipline=0.6, link_loss=0.3, intent="probe",
                      topology="leader-follower", leader="m00", link_range_m=300.0)
world = World(spec, 11)
run(world, 700)
print(world.state_hash(), world.log.head)
"""


def noisy(**kw: Any) -> Any:
    return swarm_scenario(
        16,
        scatter=True,
        discipline=0.6,
        link_loss=0.3,
        intent="probe",
        topology="leader-follower",
        leader="m00",
        link_range_m=300.0,
        **kw,
    )


def test_the_same_seed_twice_gives_the_same_state_hash() -> None:
    a, b = World(noisy(), 11), World(noisy(), 11)
    run(a, 700)
    run(b, 700)
    assert a.state_hash() == b.state_hash() and a.log.head == b.log.head


def test_two_processes_with_different_hash_salts_agree() -> None:
    script = SCRIPT.format(root=str(API_DIR))
    outputs = []
    for salt in ("1", "2"):
        env = os.environ | {"PYTHONHASHSEED": salt}
        done = subprocess.run(  # noqa: S603 - fixed interpreter and script
            [sys.executable, "-c", script],
            cwd=API_DIR,
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )
        outputs.append(done.stdout.split())
    world = World(noisy(), 11)
    run(world, 700)
    assert outputs[0] == outputs[1] == [world.state_hash(), world.log.head]


def test_different_seeds_differ_when_the_noise_is_on_and_agree_when_it_is_off() -> None:
    a, b = World(noisy(), 1), World(noisy(), 2)
    run(a, 400)
    run(b, 400)
    assert a.state_hash() != b.state_hash()
    # with no noise and no link loss no draw is taken, so the groups' own state is identical
    quiet: dict[str, Any] = {"discipline": 1.0, "link_loss": 0.0}
    c = World(swarm_scenario(8, scatter=True, **quiet), 1)
    d = World(swarm_scenario(8, scatter=True, **quiet), 2)
    run(c, 400)
    run(d, 400)
    assert c.state()["groups"] == d.state()["groups"]


def test_a_snapshot_mid_run_restores_to_the_straight_run() -> None:
    straight = World(noisy(), 11)
    run(straight, 900)
    first = World(noisy(), 11)
    run(first, 431)  # mid link epoch, mid noise epoch
    stored = json.loads(json.dumps(first.snapshot()))
    resumed = World.restore(noisy(), stored)
    run(resumed, 900 - 431)
    assert resumed.state_hash() == straight.state_hash()
    assert resumed.log.records == straight.log.records


def test_a_snapshot_restores_through_a_leader_loss() -> None:
    def play(world: World, ticks: int) -> None:
        for _ in range(ticks):
            if world.tick == 300:
                remove(world, "m00")
            world.step()

    spec = lf(leader_loss_hold_s=2.0)
    straight = World(spec, 3)
    play(straight, 600)
    for cut in (299, 310, 340, 360, 420):  # before, in the hold, at the election, after
        first = World(spec, 3)
        play(first, cut)
        resumed = World.restore(spec, json.loads(json.dumps(first.snapshot())))
        play(resumed, 600 - cut)
        assert resumed.state_hash() == straight.state_hash(), cut


def test_a_recorded_session_with_groups_replays_exactly() -> None:
    actions = [
        act(100, "trainee:op-1", "designate", target="m03"),
        act(200, "instructor:lead", "set-weather", wind_speed_mps=5.0, wind_from_deg=200),
    ]
    spec = noisy()
    _, record = run_session(spec, 11, actions, 800)
    result = replay(spec, record)
    assert result.matches and result.first_divergent_seq is None
    assert any(r.type == "group.formed" for r in record.events)
    assert any(r.type == "action.designate" for r in record.events)


def test_restore_refuses_groups_that_do_not_fit_the_scenario() -> None:
    spec = lf()
    snap = World(spec, 1).snapshot()
    plain = scenario([member("m0", 0.0, 0.0)])
    with pytest.raises(ValueError, match="groups do not match"):
        World.restore(plain, World(plain, 1).snapshot() | {"groups": snap["groups"]})
    bare = {k: v for k, v in snap.items() if k != "groups"}
    with pytest.raises(ValueError, match="groups do not match"):
        World.restore(spec, bare)
    with pytest.raises(ValueError, match="do not match the scenario groups"):
        World.restore(spec, snap | {"groups": {"other": snap["groups"]["g1"]}})


# ---------------------------------------------------------------------------- cohesion

FLOCK = {"scatter": True, "route": [wp(8000.0, 0.0, 60.0, 10.0)]}


def test_a_disciplined_swarm_aligns_and_stays_together() -> None:
    world = World(swarm_scenario(24, discipline=1.0, **FLOCK), 5)  # type: ignore[arg-type]
    run(world, 1200)
    polarisation, radius = mean_order(world)
    assert polarisation >= 0.95
    assert radius < 80.0  # 24 members at 20 m spacing fill a disc of about 35 m rms radius


def test_a_disordered_swarm_does_not_align() -> None:
    world = World(swarm_scenario(24, discipline=0.0, **FLOCK), 5)  # type: ignore[arg-type]
    run(world, 1200)
    polarisation, _ = mean_order(world)
    assert polarisation < 0.35


def test_total_link_loss_splits_the_swarm_and_spreads_it() -> None:
    results = {}
    for loss in (0.0, 1.0):
        world = World(swarm_scenario(24, discipline=0.75, link_loss=loss, **FLOCK), 5)  # type: ignore[arg-type]
        run(world, 1500)
        controller = world.groups.controllers[0]  # type: ignore[union-attr]
        results[loss] = (
            metrics.radius_of_gyration([d.x for d in active(world)], [d.y for d in active(world)]),
            metrics.component_count(controller.active_ids, controller.link_pairs),
            len(controller.graph().components()),
        )
    assert results[0.0][1] == 1 and results[1.0][1] == 24 == results[1.0][2]
    assert results[1.0][0] > 1.5 * results[0.0][0]


def test_more_discipline_never_lowers_polarisation_across_a_sweep() -> None:
    means = []
    for discipline in (0.0, 0.25, 0.5, 0.75, 1.0):
        world = World(swarm_scenario(24, discipline=discipline, **FLOCK), 5)  # type: ignore[arg-type]
        run(world, 1200)
        means.append(mean_order(world)[0])
    assert all(b >= a for a, b in zip(means, means[1:], strict=False)), means


# ---------------------------------------------------------------------------- leader loss


def follower_headings(world: World) -> list[tuple[float, float, float]]:
    return [(d.ux, d.uy, d.airspeed) for d in world.drones if d.id != "m00"]


def lose_the_leader(mode: str, hold_s: float = 3.0, **kw: Any) -> tuple[World, int]:
    world = World(lf(leader_loss=mode, leader_loss_hold_s=hold_s, **kw), 4)
    run(world, 400)
    t0 = world.tick
    remove(world, "m00")
    return world, t0


def test_the_loss_of_the_leader_is_reported_on_the_tick_it_is_noticed() -> None:
    world, t0 = lose_the_leader("elect")
    world.step()
    lost = events(world, "group.leader_lost")
    assert len(lost) == 1 and lost[0].t == t0 / 20
    assert lost[0].payload == {"group": "g1", "leader": "m00", "hold_s": 3.0}
    assert gstate(world)["control"] == "hold"


def test_followers_hold_their_heading_and_speed_for_the_hold_time() -> None:
    world, t0 = lose_the_leader("elect")
    samples = []
    for k in range(60):
        world.step()
        if k >= 10:
            samples.append(follower_headings(world))
    assert gstate(world)["control"] == "hold"
    for later in samples[1:]:
        for a, b in zip(samples[0], later, strict=True):
            assert a == pytest.approx(b, abs=1e-9)


def test_with_elect_the_lowest_id_takes_over_after_the_hold() -> None:
    world, t0 = lose_the_leader("elect")
    leg_before = gstate(world)["cursor"]["leg"]
    run(world, 60)  # ticks t0 .. t0 + 59: the 3 s hold
    assert events(world, "group.leader_elected") == []
    world.step()  # tick t0 + 60
    elected = events(world, "group.leader_elected")
    assert len(elected) == 1 and elected[0].t == (t0 + 60) / 20
    assert elected[0].payload == {"group": "g1", "leader": "m01", "previous": "m00"}
    assert gstate(world)["leader"] == "m01" and gstate(world)["control"] == "leader"
    assert gstate(world)["cursor"]["leg"] == leg_before  # takes the route over from the same leg
    run(world, 700)
    leader = next(d for d in world.drones if d.id == "m01")
    assert leader.ux == pytest.approx(1.0, abs=1e-3)  # flying the route east again
    second = next(d for d in world.drones if d.id == "m02")
    assert math.hypot(second.x - leader.x, second.y - leader.y) == pytest.approx(20.0, abs=3.0)


def test_a_second_loss_starts_another_hold_and_another_election() -> None:
    world, _ = lose_the_leader("elect", hold_s=1.0)
    run(world, 200)
    assert gstate(world)["leader"] == "m01"
    remove(world, "m01")
    run(world, 40)
    assert len(events(world, "group.leader_lost")) == 2
    elected = events(world, "group.leader_elected")
    assert [e.payload["leader"] for e in elected] == ["m01", "m02"]


def test_with_zero_hold_the_election_is_on_the_same_tick() -> None:
    world, t0 = lose_the_leader("elect", hold_s=0.0)
    world.step()
    assert events(world, "group.leader_lost")[0].t == events(world, "group.leader_elected")[0].t


def test_with_disperse_the_group_flocks_on_towards_the_next_waypoint() -> None:
    world, _ = lose_the_leader("disperse")
    run(world, 61)
    assert events(world, "group.leader_elected") == []
    state = gstate(world)
    assert state["control"] == "free" and state["guide"]["ready"]
    x0 = metrics.centroid([d.x for d in active(world)], [d.y for d in active(world)])[0]
    run(world, 600)
    polarisation, _ = order(world)
    x1 = metrics.centroid([d.x for d in active(world)], [d.y for d in active(world)])[0]
    assert x1 > x0 + 100.0 and polarisation > 0.9


def test_with_loiter_every_member_circles_the_centroid_at_the_loiter_radius() -> None:
    world, _ = lose_the_leader("loiter", loiter_radius_m=150.0)
    run(world, 61)
    state = gstate(world)
    assert state["control"] == "loiter" and state["centre"] is not None
    cx, cy = state["centre"]
    run(world, 900)
    radii = [math.hypot(d.x - cx, d.y - cy) for d in active(world)]
    assert all(120.0 <= r <= 190.0 for r in radii), radii
    assert gstate(world)["centre"] == [cx, cy]  # the centre is fixed when the loiter starts


def test_a_leaderless_group_is_not_changed_by_losing_a_member_but_a_led_one_is() -> None:
    def build(topology: str) -> World:
        kw: dict[str, Any] = (
            {"topology": "leader-follower", "leader": "m00"} if topology == "led" else {}
        )
        spec = swarm_scenario(
            8,
            discipline=1.0,
            route=[wp(8000.0, 0.0, 60.0, 10.0)],
            link_range_m=400.0,
            leader_loss_hold_s=3.0,
            **kw,
        )
        return World(spec, 4)

    # leaderless: losing m00 changes nothing structural
    kept, lost = build("free"), build("free")
    run(kept, 400)
    run(lost, 400)
    remove(lost, "m00")
    run(kept, 400)
    run(lost, 400)
    assert not [r for r in lost.log.records if r.type.startswith("group.") and r.t > 20]
    assert gstate(lost)["control"] == "free" == gstate(kept)["control"]
    assert gstate(lost)["guide"] == gstate(kept)["guide"]  # the guide flew on exactly as before
    assert order(lost)[0] >= 0.95
    # led: the same loss of the leader hesitates, then re-forms around another
    led = build("led")
    run(led, 400)
    remove(led, "m00")
    run(led, 2)
    assert gstate(led)["control"] == "hold"
    run(led, 400)
    assert len(events(led, "group.leader_lost")) == 1
    assert len(events(led, "group.leader_elected")) == 1


def test_a_lost_follower_closes_the_slots_up() -> None:
    world = World(lf(8, intent="transit"), 4)
    run(world, 400)
    remove(world, "m02")
    run(world, 600)
    xs = {d.id: d.x for d in active(world)}
    ordered = [xs[k] for k in ("m00", "m01", "m03", "m04", "m05", "m06", "m07")]
    gaps = [a - b for a, b in zip(ordered, ordered[1:], strict=False)]
    assert all(g == pytest.approx(20.0, abs=3.0) for g in gaps), gaps


def test_followers_out_of_link_hold_their_formation_and_flock_with_whoever_they_hear() -> None:
    # a link range shorter than the formation and heavy loss: the group fragments into parts
    spec = lf(12, link_loss=0.6, link_range_m=45.0, discipline=1.0)
    world = World(spec, 8)
    run(world, 800)
    controller = world.groups.controllers[0]  # type: ignore[union-attr]
    assert len(controller.graph().components()) > 1
    assert all(d.airspeed >= 0.0 for d in active(world))
    # with every link down each follower holds its last heading and speed
    dead = World(lf(8, link_loss=1.0), 8)
    run(dead, 300)
    leader = next(d for d in dead.drones if d.id == "m00")
    held = [(d.ux, d.uy, d.airspeed) for d in dead.drones if d.id != "m00"]
    run(dead, 100)
    assert [(d.ux, d.uy, d.airspeed) for d in dead.drones if d.id != "m00"] == pytest.approx(held)
    assert leader.x > -1500.0


def test_a_leader_that_has_not_spawned_yet_is_not_a_lost_leader() -> None:
    names = [f"m{i:02d}" for i in range(4)]
    threats = [
        member(n, -1500.0 + 20.0 * i, 0.0, spawn_s=0.0 if i else 5.0) for i, n in enumerate(names)
    ]
    spec = scenario(
        threats,
        [
            group(
                names,
                [wp(3000.0, 0.0)],
                topology="leader-follower",
                leader="m00",
                discipline=1.0,
                link_range_m=400.0,
            )
        ],
    )
    world = World(spec, 1)
    run(world, 99)  # the followers fly straight on without a leader
    assert events(world, "group.formed") == [] and events(world, "group.leader_lost") == []
    assert all(d.ux == pytest.approx(d.ux) for d in active(world))
    run(world, 20)  # the leader spawns at 5 s
    assert len(events(world, "group.formed")) == 1
    assert events(world, "group.formed")[0].t == 5.0
    assert gstate(world)["leader_seen"] and events(world, "group.leader_lost") == []


# ---------------------------------------------------------------------------- intents


def test_a_probe_turns_back_at_the_standoff_exactly_probe_cycles_times() -> None:
    spec = lf(
        6,
        intent="probe",
        route=[wp(-1000.0, 0.0, 60.0, 10.0), wp(-400.0, 0.0, 60.0, 10.0)],
        probe_standoff_m=200.0,
        probe_cycles=3,
        on_route_end="despawn",
    )
    world = World(spec, 2)
    leader = world.drones[0]
    dist: list[float] = []
    while leader.status != "despawned" and world.tick < 20000:
        world.step()
        if leader.status == "active":
            dist.append(abs(-400.0 - leader.x))
    minima = [
        dist[i]
        for i in range(1, len(dist) - 1)
        if dist[i] < dist[i - 1] and dist[i] <= dist[i + 1] and dist[i] < 400.0
    ]
    assert leader.status == "despawned"
    assert len(minima) == 3
    assert all(180.0 <= m <= 240.0 for m in minima), minima  # turned back about 200 m short
    assert events(world, "group.route_end")[0].payload == {"group": "g1", "then": "despawn"}
    assert [d.status for d in world.drones] == ["despawned"] * 6


def test_a_leaderless_probe_counts_its_cycles_in_the_guide_cursor() -> None:
    spec = swarm_scenario(
        6,
        intent="probe",
        route=[wp(-1000.0, 0.0, 60.0, 10.0), wp(-600.0, 0.0, 60.0, 10.0)],
        probe_standoff_m=150.0,
        probe_cycles=2,
        on_route_end="loiter",
        discipline=1.0,
        link_range_m=400.0,
    )
    world = World(spec, 2)
    cycles = set()
    for _ in range(7000):
        world.step()
        cycles.add(gstate(world)["cursor"]["cycle"])
    assert cycles == {0, 1, 2}
    assert gstate(world)["cursor"]["phase"] == "orbit"


def test_saturation_lanes_are_evenly_spaced_and_the_line_arrives_together() -> None:
    spec = swarm_scenario(
        9,
        intent="saturation",
        route=[wp(1500.0, 0.0, 60.0, 10.0)],
        discipline=1.0,
        lane_spacing_m=40.0,
        link_range_m=500.0,
        on_route_end="despawn",
        wind=3.0,
    )
    world = World(spec, 3)
    arrival: dict[str, int] = {}
    lanes: list[float] = []
    abreast = 0.0
    world.step()
    while any(d.status == "active" for d in world.drones) and world.tick < 6000:
        world.step()
        for d in world.drones:
            if d.status == "active" and d.id not in arrival and d.x > 1300.0:
                arrival[d.id] = world.tick
        if world.tick == 1400:
            ys = sorted(d.y for d in active(world))
            lanes = [b - a for a, b in zip(ys, ys[1:], strict=False)]
            abreast = max(d.x for d in active(world)) - min(d.x for d in active(world))
    assert len(lanes) == 8 and all(g == pytest.approx(40.0, abs=2.0) for g in lanes), lanes
    assert abreast < 6.0  # a line abreast: all level along the track
    spread = (max(arrival.values()) - min(arrival.values())) / 20.0
    assert len(arrival) == 9 and spread <= 2.0  # arrives within 2 s of itself


def test_a_led_saturation_line_is_abreast_with_even_lanes() -> None:
    world = World(lf(7, intent="saturation", lane_spacing_m=35.0, link_range_m=500.0), 3)
    run(world, 1200)
    ys = sorted(d.y for d in active(world))
    assert all(b - a == pytest.approx(35.0, abs=2.0) for a, b in zip(ys, ys[1:], strict=False))
    assert max(d.x for d in active(world)) - min(d.x for d in active(world)) < 6.0


def test_a_loitering_leader_orbits_at_the_loiter_radius() -> None:
    world = World(
        lf(6, intent="loiter", route=[wp(0.0, 0.0, 60.0, 10.0)], loiter_radius_m=300.0), 3
    )
    run(world, 5000)
    leader = world.drones[0]
    radii = []
    for _ in range(600):
        world.step()
        radii.append(math.hypot(leader.x, leader.y))
    assert all(285.0 <= r <= 315.0 for r in radii), (min(radii), max(radii))


def test_a_leaderless_loiter_guide_orbits_the_first_waypoint() -> None:
    spec = swarm_scenario(
        6,
        intent="loiter",
        route=[wp(0.0, 0.0, 60.0, 10.0)],
        loiter_radius_m=300.0,
        discipline=1.0,
        link_range_m=400.0,
    )
    world = World(spec, 3)
    run(world, 5000)
    radii = []
    for _ in range(600):
        world.step()
        guide = gstate(world)["guide"]
        radii.append(math.hypot(guide["x"], guide["y"]))
    assert all(285.0 <= r <= 315.0 for r in radii), (min(radii), max(radii))


@pytest.mark.parametrize("topology", ["led", "free"])
def test_a_route_that_ends_in_a_loop_starts_again(topology: str) -> None:
    kw: dict[str, Any] = (
        {"topology": "leader-follower", "leader": "m00"} if topology == "led" else {}
    )
    spec = swarm_scenario(
        4,
        route=[wp(-1200.0, 0.0, 60.0, 10.0), wp(-1500.0, 0.0, 60.0, 10.0)],
        on_route_end="loop",
        discipline=1.0,
        link_range_m=400.0,
        **kw,
    )
    world = World(spec, 3)
    run(world, 2500)
    assert len(events(world, "group.route_end")) >= 1
    assert events(world, "group.route_end")[0].payload["then"] == "loop"
    assert all(d.status == "active" for d in world.drones)


def test_a_leaderless_group_that_despawns_at_the_end_of_its_route_leaves_together() -> None:
    spec = swarm_scenario(
        5,
        route=[wp(-1000.0, 0.0, 60.0, 10.0)],
        on_route_end="despawn",
        discipline=1.0,
        link_range_m=400.0,
    )
    world = World(spec, 3)
    run(world, 2000)
    despawns = events(world, "threat.despawn")
    assert [r.payload["reason"] for r in despawns] == ["route-end"] * 5
    assert len({r.t for r in despawns}) == 1
    assert all(d.status == "despawned" for d in world.drones)
    run(world, 5)  # a finished group plans nothing


def test_the_guide_waits_for_a_group_that_lags_far_behind() -> None:
    spec = swarm_scenario(
        6, discipline=1.0, route=[wp(8000.0, 0.0, 60.0, 10.0)], link_range_m=400.0
    )
    world = World(spec, 3)
    run(world, 40)
    for d in world.drones:  # throw the whole group far behind its guide
        d.x -= 3000.0
    held = gstate(world)["guide"]["x"]
    run(world, 20)
    assert gstate(world)["guide"]["x"] == pytest.approx(held)
    for d in world.drones:
        d.x += 3000.0
    run(world, 20)
    assert gstate(world)["guide"]["x"] > held


def test_members_that_spawn_later_join_the_flock() -> None:
    names = [f"m{i:02d}" for i in range(6)]
    threats = [member(n, -1500.0 + 20.0 * i, 0.0, spawn_s=2.0 * i) for i, n in enumerate(names)]
    spec = scenario(threats, [group(names, [wp(3000.0, 0.0)], discipline=1.0, link_range_m=400.0)])
    world = World(spec, 1)
    run(world, 240)
    assert len(events(world, "group.formed")) == 1
    assert events(world, "group.formed")[0].t == 10.0
    assert all(d.status == "active" for d in world.drones)


# ---------------------------------------------------------------------------- clutter in the world


def clutter_scenario(
    motion: dict[str, Any], class_id: str, *, wind: float = 4.0, **limits: float
) -> Any:
    t = member("c1", 0.0, 0.0, class_id=class_id, z=60.0, speed=1.0)
    t["motion"] = motion
    t["limits"] = t["limits"] | limits
    t["route"] = [wp(2500.0, 2500.0, 60.0, 5.0)]  # ignored
    return scenario([t], wind=wind, wind_from=270.0, gust=0.8, half=3000.0)


KITE = {
    "kind": "tether",
    "anchor": {"x": 0, "y": 0, "z": 0},
    "length_m": 100,
    "sway_m": 25,
    "sway_period_s": 10,
}


def test_a_kite_stays_on_its_line_and_the_truth_velocity_adds_up() -> None:
    world = World(clutter_scenario(KITE, "kite"), 1)
    drone = world.drones[0]
    moved = False
    for _ in range(4000):
        before = (drone.x, drone.y, drone.z)
        world.step()
        if drone.status != "active":
            continue
        d3 = math.sqrt(drone.x**2 + drone.y**2 + drone.z**2)
        assert d3 <= 100.0 + 1e-9
        assert 10.0 <= drone.z <= 150.0
        wx, wy = world.wind()
        assert drone.ux * drone.airspeed + wx == pytest.approx((drone.x - before[0]) / DT, abs=1e-9)
        assert drone.uy * drone.airspeed + wy == pytest.approx((drone.y - before[1]) / DT, abs=1e-9)
        moved = moved or drone.x != before[0]
    assert moved and drone.x > 20.0  # downwind (the wind blows east)
    assert abs(drone.x - 2500.0) > 1000.0 and abs(drone.y - 2500.0) > 1000.0  # route ignored


def test_a_balloon_drifts_with_the_wind_and_stops_at_the_class_ceiling() -> None:
    world = World(
        clutter_scenario(
            {"kind": "drift", "climb_mps": 2.0}, "balloon", wind=3.0, max_altitude_m=90.0
        ),
        1,
    )
    drone = world.drones[0]
    world.step()
    z_prev = drone.z
    carried = world.wind()[0] * DT  # the first step
    for _ in range(600):
        before = (drone.x, drone.y)
        world.step()
        wx, wy = world.wind()
        carried += wx * DT
        assert drone.airspeed == 0.0
        assert drone.x - before[0] == pytest.approx(wx * DT) and drone.y - before[
            1
        ] == pytest.approx(wy * DT)
        assert drone.z <= 90.0 and drone.z >= z_prev - 1e-12
        z_prev = drone.z
    assert drone.z == 90.0 and drone.vz == 0.0
    assert drone.x == pytest.approx(carried, abs=1e-9)  # carried by the wind alone


def test_a_balloon_carried_out_of_the_play_area_is_retired() -> None:
    spec = clutter_scenario({"kind": "drift", "climb_mps": 0.0}, "balloon", wind=30.0)
    world = World(spec, 1)
    run(world, 3000)
    assert world.drones[0].status == "despawned"
    assert events(world, "threat.despawn")[0].payload["reason"] == "left-area"


# ---------------------------------------------------------------------------- envelopes


def angle_between(a: Drone, ux: float, uy: float) -> float:
    return abs(math.atan2(a.ux * uy - a.uy * ux, a.ux * ux + a.uy * uy))


def test_every_member_keeps_to_its_own_class_envelope_at_every_tick() -> None:
    classes = ["rotary-small", "fpv-small", "decoy-small", "autonomous-small"]
    for topology in ("leader-follower", "leaderless"):
        names = [f"m{i:02d}" for i in range(12)]
        threats = [
            member(
                n,
                -1500.0 + 25.0 * (i % 4),
                30.0 * (i // 4),
                class_id=classes[i % 4],
                heading=(i * 77.0) % 360.0,
                speed=5.0,
            )
            for i, n in enumerate(names)
        ]
        kw = {"topology": topology, "leader": "m00"} if topology == "leader-follower" else {}
        spec = scenario(
            threats,
            [
                group(
                    names,
                    [wp(2000.0, 600.0, 80.0, 14.0), wp(0.0, 1500.0, 40.0, 9.0)],
                    discipline=0.3,
                    link_loss=0.3,
                    link_range_m=200.0,
                    **kw,
                )
            ],
            wind=4.0,
            gust=1.0,
        )
        world = World(spec, 6)
        envelopes = [t.limits for t in spec.threats]
        previous = [(d.ux, d.uy, d.airspeed, d.z) for d in world.drones]
        for _ in range(900):
            world.step()
            for i, d in enumerate(world.drones):
                lim = envelopes[i]
                if d.status != "active":
                    continue
                px, py, ps, pz = previous[i]
                assert d.airspeed <= lim.max_speed_mps + 1e-9 and d.airspeed >= 0.0
                assert abs(d.airspeed - ps) <= lim.max_accel_mps2 * DT + 1e-9 or world.tick == 1
                assert angle_between(d, px, py) <= lim.max_turn_rate_dps * math.pi / 180 * DT + 1e-9
                assert lim.min_altitude_m - 1e-9 <= d.z <= lim.max_altitude_m + 1e-9
                assert -lim.max_descent_mps - 1e-9 <= d.vz <= lim.max_climb_mps + 1e-9
            previous = [(d.ux, d.uy, d.airspeed, d.z) for d in world.drones]


def test_a_group_flies_no_faster_than_its_slowest_member_allows() -> None:
    names = ["a", "b", "c", "d"]
    classes = ["rotary-small", "rotary-small", "decoy-small", "rotary-small"]
    threats = [
        member(n, -1500.0 + 20.0 * i, 0.0, class_id=c, speed=5.0)
        for i, (n, c) in enumerate(zip(names, classes, strict=True))
    ]
    spec = scenario(
        threats,
        [group(names, [wp(5000.0, 0.0, 60.0, 17.0)], discipline=1.0, link_range_m=400.0)],
    )
    world = World(spec, 1)
    run(world, 600)
    # the decoy's top speed is 12 m/s; the group flies at 85% of it, whatever the route says
    assert max(d.airspeed for d in world.drones) <= 0.85 * 12.0 * 1.5 + 1e-9
    leader_speed = sum(d.airspeed for d in world.drones) / 4
    assert leader_speed <= 12.0


# ---------------------------------------------------------------------------- cost


def test_the_cost_of_a_swarm_is_bounded_and_links_are_drawn_per_epoch_not_per_tick() -> None:
    for n, ticks in ((24, 600), (64, 200)):
        spec = swarm_scenario(
            n, scatter=True, discipline=0.7, link_loss=0.2, route=[wp(9000.0, 0.0, 60.0, 10.0)]
        )
        world = World(spec, 2)
        started = time.process_time()
        run(world, ticks)
        cpu = time.process_time() - started
        draws = world.groups.controllers[0].draws.count  # type: ignore[union-attr]
        epochs = ticks // 20 + 1
        pairs = n * (n - 1) // 2
        print(f"{n} members x {ticks} ticks: {cpu:.2f} s CPU, {draws} hash draws")  # noqa: T201
        # noise: one draw per member per second; links: one per pair in range per epoch
        assert draws <= n * epochs + pairs * epochs
        # a draw per pair per tick would be 20 times as many
        assert draws < pairs * ticks / 5


def test_a_quiet_group_takes_no_draws_at_all() -> None:
    world = World(swarm_scenario(16, scatter=True, discipline=1.0, link_loss=0.0), 2)
    run(world, 200)
    assert world.groups.controllers[0].draws.count == 0  # type: ignore[union-attr]


# ---------------------------------------------------------------------------- who sees what


def test_group_events_are_ground_truth_and_never_reach_a_trainee() -> None:
    world, _ = lose_the_leader("elect", hold_s=1.0)
    run(world, 80)
    kinds = {r.type for r in world.log.records}
    assert {"group.formed", "group.leader_lost", "group.leader_elected"} <= kinds
    for record in world.log.records:
        if record.type.startswith("group."):
            assert audience.trainee_event(record) is None
    assert not any(t.startswith("group.") for t in audience.TRAINEE_EVENTS)


def test_the_route_end_event_is_ground_truth_too() -> None:
    spec = swarm_scenario(4, route=[wp(-1000.0, 0.0)], on_route_end="loiter", discipline=1.0)
    world = World(spec, 1)
    run(world, 2000)
    ends = events(world, "group.route_end")
    assert ends and audience.trainee_event(ends[0]) is None
