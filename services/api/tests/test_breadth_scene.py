"""The wave 8 breadth scene: swarm, flock, kites and balloon with all six sensors on both terrain
packs, and the benchmark trajectory recorded from it."""

import json
from pathlib import Path

import pytest

from app.contracts import ScenarioSpec
from sim import breadth
from sim.behaviours import metrics
from sim.catalogue import load_catalogue
from sim.sensors import build_sensors
from sim.tracking.picture import Picture
from sim.world import World

from .sim_cases import REPO

PACKS = ("heron-ridge", "osprey-town")
TICKS = 600
SCENE_FILE = REPO / "apps" / "web" / "public" / "scenes" / "bench-breadth.v1.json"


def fly(spec: ScenarioSpec, ticks: int = TICKS) -> World:
    world = World(spec, breadth.SEED, picture=Picture.build(spec, breadth.SEED))
    for _ in range(ticks):
        world.step()
    return world


def test_the_scene_has_the_contacts_the_benchmark_names() -> None:
    spec = breadth.breadth_scenario()
    ids = [t.id for t in spec.threats]
    assert sum(i.startswith("swarm-") for i in ids) == breadth.SWARM == 24
    assert sum(i.startswith("bird-") for i in ids) == breadth.BIRDS == 30
    assert {g.id for g in spec.groups} == {"swarm", "flock"}
    swarm_classes = {t.class_id for t in spec.threats if t.id.startswith("swarm-")}
    assert swarm_classes == {"rotary-small", "decoy-small", "autonomous-small"}
    assert load_catalogue().check_scenario(spec) == []


@pytest.mark.parametrize("pack_id", PACKS)
def test_the_scene_flies_with_every_sensor_on_both_packs_and_repeats_exactly(pack_id: str) -> None:
    spec = breadth.breadth_scenario(pack_id)
    first, second = fly(spec), fly(spec)
    assert first.state_hash() == second.state_hash()
    active = [d for d in first.drones if d.status == "active"]
    assert len(active) == len(spec.threats)
    assert sum(r.type == "group.formed" for r in first.log.records) == 2
    swarm = [d for d in active if d.id.startswith("swarm-")]
    flock = [d for d in active if d.id.startswith("bird-")]
    assert metrics.radius_of_gyration([d.x for d in swarm], [d.y for d in swarm]) < 120.0
    assert metrics.radius_of_gyration([d.x for d in flock], [d.y for d in flock]) < 60.0
    assert any(r.type == "track.confirm" for r in first.log.records)


def test_the_rf_receiver_never_hears_a_silent_decoy_a_bird_a_kite_or_a_balloon() -> None:
    spec = breadth.breadth_scenario()
    world = World(spec, breadth.SEED)
    rf = next(s for s in build_sensors(spec).sensors if s.id == "rf-1")
    classes = {t.id: t.class_id for t in spec.threats}
    heard: set[str] = set()
    for _ in range(TICKS):
        world.step()
        heard |= {
            d.truth_id for d in rf.detect(world, world.tick, world.rng) if d.truth_id is not None
        }
    assert heard, "the receiver heard nothing"
    assert {classes[i] for i in heard} == {"rotary-small"}


def test_the_benchmark_trajectory_is_the_recorded_run_of_the_real_behaviours() -> None:
    recorded = json.loads(SCENE_FILE.read_text("utf-8"))
    again = breadth.trajectory(breadth.breadth_scenario(sensors=False), hz=2.0)
    assert recorded == again, "regenerate with: python -m sim.breadth <the file>"
    assert recorded["format"] == breadth.FORMAT and recorded["pack"] == "heron-ridge"
    assert len(recorded["frames"]) == 121
    assert all(len(row) == 3 * len(recorded["members"]) for row in recorded["frames"])
    shapes = [m["shape"] for m in recorded["members"]]
    assert shapes.count("bird") == 30 and shapes.count("rotary-small") == 24
    assert {"kite", "balloon"} <= set(shapes)


def test_the_command_writes_the_file_and_refuses_a_missing_path(
    tmp_path: pytest.TempPathFactory,
) -> None:
    target = tmp_path / "scene.json"  # type: ignore[operator]
    assert breadth.main([str(target)]) == 0
    assert json.loads(target.read_text("utf-8")) == json.loads(SCENE_FILE.read_text("utf-8"))
    assert breadth.main([]) == 2
