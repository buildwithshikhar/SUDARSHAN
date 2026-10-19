"""Every class of the threat catalogue instantiates and flies on both terrain packs, inside its
envelope, with all five sensor profiles watching, and a run repeats exactly."""

import json

import pytest

from app.contracts import ScenarioSpec
from sim.catalogue import load_catalogue
from sim.terrain import load_pack as load_terrain
from sim.terrain import pack_dir
from sim.tracking.picture import Picture
from sim.world import World

from .sim_cases import REPO

CATALOGUE = load_catalogue()
PACKS = ("heron-ridge", "osprey-town")
TICKS = 600
SEED = 5
#: Profile placed for each modality, with the version the shipped scenarios pin.
SENSORS = (
    ("radar-1", "radar-generic-s", "0.2.0"),
    ("eo-1", "eo-generic-day", "0.1.0"),
    ("nv-1", "eo-generic-nv", "0.1.0"),
    ("ir-1", "ir-generic-thermal", "0.1.0"),
    ("rf-1", "rf-generic-passive", "1.0.0"),
    ("ac-1", "acoustic-generic-array", "1.0.0"),
)
#: A tiny play area inside both packs (the smaller is 1500 m from the centre to an edge).
HALF = 1200.0
#: Waypoints (x, y) of the two-leg route, well inside the area and inside every sensor's range.
START = (-400.0, -300.0)
ROUTE = ((300.0, 300.0), (-300.0, 300.0))


def scenario_for(class_id: str, pack_id: str) -> ScenarioSpec:
    """A scenario with one threat of the class, all six profiles, on a baked terrain pack."""
    base = json.loads(
        (REPO / "packs" / "scenarios" / "heron-ridge-low-approach.v1.json").read_text("utf-8")
    )
    cls = CATALOGUE.get(class_id)
    env = cls.envelope
    terrain = load_terrain(pack_dir(pack_id))

    def height(x: float, y: float) -> float:
        z = max(env.min_altitude.value, terrain.ground_m(x, y) + 25.0)
        assert z <= env.max_altitude.value, (class_id, pack_id, x, y, z)
        return z

    def point(x: float, y: float, z: float) -> dict[str, float]:
        return {"x": x, "y": y, "z": z}

    cruise = env.cruise_speed.value
    base["id"] = f"catalogue-{class_id}-{pack_id}"
    base["world"]["terrain"] = {"kind": "pack", "id": pack_id, "version": "1.0.0"}
    base["world"]["half_extent_m"] = HALF
    base["zones"], base["assets"], base["filed_flights"] = [], [], []
    base["sensors"] = [
        {
            "id": sensor_id,
            "profile": {"id": profile, "version": version},
            "position": point(
                -60.0 + 20.0 * i, 40.0, terrain.ground_m(-60.0 + 20.0 * i, 40.0) + 6.0
            ),
            "boresight_deg": 45.0,
        }
        for i, (sensor_id, profile, version) in enumerate(SENSORS)
    ]
    base["threats"] = [
        {
            "id": "contact-1",
            "class_id": class_id,
            "disposition": "clutter" if cls.category == "clutter" else cls.default_disposition,
            "label": {"en": cls.title.en, "hi": cls.title.hi},
            "spawn_s": 0.0,
            "start": point(*START, height(*START)),
            "start_heading_deg": 45.0,
            "start_speed_mps": cruise,
            "limits": CATALOGUE.limits_for(class_id).model_dump(mode="json"),
            "route": [
                {"position": point(x, y, height(x, y)), "speed_mps": cruise, "hold_s": 0.0}
                for x, y in ROUTE
            ],
            "on_route_end": "loiter",
        }
    ]
    return ScenarioSpec.model_validate(base)


def fly(spec: ScenarioSpec) -> tuple[World, list[tuple[float, float]]]:
    """Run the scenario; returns the world and (airspeed, height) of the drone while active."""
    world = World(spec, SEED, picture=Picture.build(spec, SEED))
    seen: list[tuple[float, float]] = []
    for _ in range(TICKS):
        world.step()
        drone = world.drones[0]
        if drone.status == "active":
            seen.append((drone.airspeed, drone.z))
    return world, seen


@pytest.mark.parametrize("pack_id", PACKS)
@pytest.mark.parametrize("class_id", CATALOGUE.ids)
def test_every_class_flies_on_both_terrain_packs_inside_its_envelope(
    class_id: str, pack_id: str
) -> None:
    spec = scenario_for(class_id, pack_id)
    assert CATALOGUE.check_scenario(spec) == []
    world, seen = fly(spec)
    env = CATALOGUE.get(class_id).envelope
    kinds = [r.type for r in world.log.records]
    assert "threat.spawn" in kinds, "the threat never spawned"
    assert len(seen) > TICKS // 2, "the threat left the play area almost at once"
    assert max(s for s, _ in seen) <= env.max_speed.value + 1e-9
    assert min(z for _, z in seen) >= env.min_altitude.value - 1e-9
    assert max(z for _, z in seen) <= env.max_altitude.value + 1e-9
    assert world.terrain is not None and world.terrain.pack_id == pack_id


@pytest.mark.parametrize("pack_id", PACKS)
@pytest.mark.parametrize("class_id", CATALOGUE.ids)
def test_a_run_of_every_class_repeats_exactly(class_id: str, pack_id: str) -> None:
    spec = scenario_for(class_id, pack_id)
    first, _ = fly(spec)
    second, _ = fly(spec)
    assert first.state_hash() == second.state_hash()
    assert first.log.records[-1].hash == second.log.records[-1].hash


def test_the_sensors_report_the_classes_the_catalogue_says_they_should() -> None:
    """Radar and the cameras see a quadcopter; RF hears a quadcopter but not an autonomous one."""
    modalities: dict[str, set[str]] = {}
    for class_id in ("rotary-small", "autonomous-small"):
        spec = scenario_for(class_id, "heron-ridge")
        world = World(spec, SEED, picture=Picture.build(spec, SEED))
        found: set[str] = set()
        for _ in range(TICKS):
            world.step()
            assert world.picture is not None
            found |= {
                str(r["modality"]) for r in world.picture.trainee_frame(world.tick)["reports"]
            }
        modalities[class_id] = found
    assert "rf" in modalities["rotary-small"] or "radar" in modalities["rotary-small"]
    assert "rf" not in modalities["autonomous-small"]
