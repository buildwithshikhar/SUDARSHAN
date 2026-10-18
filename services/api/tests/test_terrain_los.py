"""Terrain in the sim core: ground height, line of sight, loading and the sensors that use it."""

import json
import math
from pathlib import Path

import numpy as np
import pytest

from app.contracts import ScenarioSpec
from app.contracts.common import Vec3
from app.contracts.scenario import FlatTerrain, PackTerrain
from sim import terrain as terrain_module
from sim.rng import RngStreams
from sim.sensors.eoir import EoIrSensor
from sim.sensors.geometry import truths
from sim.sensors.radar import RadarSensor
from sim.terrain import NO_BUILDING, Terrain, TerrainError, load_pack, terrain_for
from sim.world import World

from .sensor_toy import AlwaysDetects, ToySensor, make, scene
from .sim_cases import kestrel
from .terrain_support import HALF, SIZE, building, ridge_heights, square, write_pack


@pytest.fixture
def plain(tmp_path: Path) -> Terrain:
    return load_pack(write_pack(tmp_path, "plain"))


@pytest.fixture
def ridge(tmp_path: Path) -> Terrain:
    return load_pack(write_pack(tmp_path, "ridge", heights_m=ridge_heights()))


@pytest.fixture
def town(tmp_path: Path) -> Terrain:
    houses = [
        building("w1", square(300, 0, 10), 12.0),
        building("w2", square(-300, 200, 8), 30.0, 5.0),
    ]
    return load_pack(write_pack(tmp_path, "town", buildings=houses))


# ---------------------------------------------------------------------- ground height


def test_ground_is_bilinear_between_grid_points(ridge: Terrain) -> None:
    assert ridge.ground_m(0.0, 0.0) == pytest.approx(80.0, abs=0.06)
    assert ridge.ground_m(0.0, 50.0) == pytest.approx(40.0, abs=0.06)  # half way down a 100 m slope
    assert ridge.ground_m(0.0, 100.0) == 0.0
    assert ridge.ground_m(500.0, -500.0) == 0.0


def test_ground_is_clamped_outside_the_pack(ridge: Terrain) -> None:
    assert ridge.ground_m(HALF + 5000.0, 0.0) == ridge.ground_m(HALF, 0.0)
    assert ridge.ground_m(0.0, -HALF - 1.0) == ridge.ground_m(0.0, -HALF)


def test_roofs_are_rasterised_inside_footprints_only(town: Terrain) -> None:
    assert town.roof_m(300.0, 0.0) == 12.0
    assert town.roof_m(-300.0, 200.0) == 35.0  # base 5 m + 30 m
    assert town.roof_m(300.0, 30.0) is None
    assert town.roof_m(5 * HALF, 0.0) is None
    assert town.roofs.min() == NO_BUILDING


def test_an_l_shaped_building_leaves_its_notch_open(tmp_path: Path) -> None:
    ell = [[0, 0], [40, 0], [40, 10], [10, 10], [10, 40], [0, 40]]
    t = load_pack(write_pack(tmp_path, "ell", buildings=[building("w1", ell, 9.0)]))
    assert t.roof_m(5.0, 30.0) == 9.0 and t.roof_m(30.0, 5.0) == 9.0
    assert t.roof_m(30.0, 30.0) is None


# ---------------------------------------------------------------------- line of sight


def test_nothing_is_blocked_over_flat_ground(plain: Terrain) -> None:
    assert not plain.blocked((-900, 0, 3), (900, 0, 3))
    assert not plain.blocked((-900, -900, 10), (900, 900, 200))


def test_a_ridge_blocks_a_low_ray_and_not_a_high_one(ridge: Terrain) -> None:
    assert ridge.blocked((0, -600, 5), (0, 600, 5))
    assert ridge.blocked((0, -600, 5), (0, 600, 70))  # still below the 80 m crest
    assert not ridge.blocked((0, -600, 5), (0, 600, 200))
    assert not ridge.blocked((0, -600, 5), (0, -100, 5))  # both on the near side
    assert not ridge.blocked((-900, -500, 5), (900, -500, 5))  # along the ridge, on the plain


def test_the_ray_clears_the_crest_by_the_geometry_not_by_luck(ridge: Terrain) -> None:
    # From 5 m at y=-600 to z at y=+600: the ray is at z = 5 + (z1-5)/2 over the crest at y=0.
    assert ridge.blocked((0, -600, 5), (0, 600, 150))  # 77.5 m over an 80 m crest
    assert not ridge.blocked((0, -600, 5), (0, 600, 160))  # 82.5 m


def test_a_building_blocks_below_its_roof_only(town: Terrain) -> None:
    assert town.blocked((0, 0, 5), (600, 0, 5))
    assert not town.blocked((0, 0, 14), (600, 0, 14))
    assert not town.blocked((0, 40, 5), (600, 40, 5))  # passes beside it
    assert town.blocked((-300, 0, 5), (-300, 600, 20))  # into the 35 m tower from the south


def test_a_sensor_on_a_roof_is_not_blocked_by_its_own_building(town: Terrain) -> None:
    assert not town.blocked((300, 0, 12.5), (900, 0, 12.5))


def test_a_short_segment_is_never_blocked(ridge: Terrain) -> None:
    assert not ridge.blocked((0, 0, 1), (3, 0, 1))
    assert not ridge.blocked((0, 0, 1), (0, 0, 1))


def test_blocked_is_symmetric(ridge: Terrain, town: Terrain) -> None:
    for t, a, b in ((ridge, (0, -600, 5), (0, 600, 70)), (town, (0, 0, 5), (600, 0, 5))):
        assert t.blocked(a, b) is t.blocked(b, a)


def test_the_answer_does_not_depend_on_the_array_layout(ridge: Terrain) -> None:
    # Same result from a copy with different memory order: the arithmetic is elementwise.
    clone = Terrain(
        ridge.pack_id,
        ridge.version,
        ridge.digest,
        ridge.half_extent_m,
        ridge.cell_m,
        ridge.size,
        np.asfortranarray(ridge.heights),
        np.asfortranarray(ridge.roofs),
        ridge.roof_cells,
    )
    rng = np.random.default_rng(3)
    for _ in range(200):
        a = tuple(float(v) for v in rng.uniform([-900, -900, 1], [900, 900, 120]))
        b = tuple(float(v) for v in rng.uniform([-900, -900, 1], [900, 900, 120]))
        assert ridge.blocked(a, b) is clone.blocked(a, b)  # type: ignore[arg-type]


# ---------------------------------------------------------------------- loading


def test_a_pack_is_cached_and_immutable(tmp_path: Path) -> None:
    directory = write_pack(tmp_path, "cached")
    assert load_pack(directory) is load_pack(directory)
    with pytest.raises(AttributeError):
        load_pack(directory).version = "9.9.9"  # type: ignore[misc]


def test_a_changed_file_fails_its_hash(tmp_path: Path) -> None:
    directory = write_pack(tmp_path, "tampered", heights_m=ridge_heights())
    raw = bytearray((directory / "heights.i16").read_bytes())
    raw[0] ^= 0x01
    (directory / "heights.i16").write_bytes(bytes(raw))
    with pytest.raises(TerrainError, match="does not match its hash"):
        load_pack(directory)


def test_a_missing_or_foreign_manifest_is_refused(tmp_path: Path) -> None:
    with pytest.raises(TerrainError, match="cannot read manifest"):
        load_pack(tmp_path / "nowhere")
    directory = write_pack(tmp_path, "foreign")
    manifest = json.loads((directory / "manifest.json").read_text())
    manifest["format"] = "terrain-pack.v9"
    (directory / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(TerrainError, match="not a terrain-pack.v1"):
        load_pack(directory)


def test_a_wrong_sized_heightmap_is_refused(tmp_path: Path) -> None:
    directory = write_pack(tmp_path, "short")
    manifest = json.loads((directory / "manifest.json").read_text())
    manifest["heightmap"]["size"] = SIZE + 1
    (directory / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(TerrainError, match="heightmap is not"):
        load_pack(directory)


def test_a_foreign_buildings_file_is_refused(tmp_path: Path) -> None:
    directory = write_pack(tmp_path, "oddbuildings")
    (directory / "buildings.json").write_text(json.dumps({"format": "other", "buildings": []}))
    manifest = json.loads((directory / "manifest.json").read_text())
    import hashlib

    manifest["files"]["buildings.json"] = hashlib.sha256(
        (directory / "buildings.json").read_bytes()
    ).hexdigest()
    (directory / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(TerrainError, match="not a terrain-buildings.v1"):
        load_pack(directory)


def test_flat_terrain_loads_nothing_and_a_pack_is_found_by_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert terrain_for(FlatTerrain(kind="flat")) is None
    write_pack(tmp_path, "named", version="2.1.0")
    monkeypatch.setattr(terrain_module, "pack_dir", lambda pack_id: tmp_path / pack_id)
    found = terrain_for(PackTerrain(kind="pack", id="named", version="2.1.0"))
    assert found is not None and found.pack_id == "named"
    with pytest.raises(TerrainError, match="wants terrain named 2.0.0"):
        terrain_for(PackTerrain(kind="pack", id="named", version="2.0.0"))


# ---------------------------------------------------------------------- in the world


def pack_world(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pack_half: float | None = None
) -> World:
    """Kestrel on a pack of half extent `pack_half` (default: exactly the play area)."""
    data = kestrel().model_dump(mode="json")
    play = data["world"]["half_extent_m"]
    write_pack(tmp_path, "worldpack", heights_m=ridge_heights(), half=pack_half or play)
    monkeypatch.setattr(terrain_module, "pack_dir", lambda pack_id: tmp_path / pack_id)
    data["world"]["terrain"] = {"kind": "pack", "id": "worldpack", "version": "1.0.0"}
    return World(ScenarioSpec.model_validate(data), 7)


def test_the_session_log_names_the_terrain_it_ran_on(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    world = pack_world(tmp_path, monkeypatch)
    start = world.log.records[0].payload
    assert world.terrain is not None
    assert start["terrain"] == {
        "id": "worldpack",
        "version": "1.0.0",
        "sha256": world.terrain.digest,
    }
    assert "terrain" not in World(kestrel(), 7).log.records[0].payload  # flat logs are unchanged


def test_a_play_area_bigger_than_the_pack_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with pytest.raises(TerrainError, match="larger than terrain pack"):
        pack_world(tmp_path, monkeypatch, pack_half=1000.0)


def test_flat_scenarios_have_no_terrain() -> None:
    assert World(kestrel(), 7).terrain is None


# ---------------------------------------------------------------------- in the sensors


class LosToy(AlwaysDetects):
    needs_line_of_sight = True


def behind_the_ridge(
    ridge: Terrain, extra_z: float = 0.0, cls: type[ToySensor] = LosToy
) -> tuple[World, ToySensor, RngStreams]:
    world, truth = scene(tick=200)
    world.terrain = ridge
    # Put the contact on the far side of the ridge and the sensor on the near side, same bearing.
    moved = world.drones[[t.id for t in truths(world)].index(truth.id)]
    moved.x, moved.y, moved.z = 0.0, 300.0, 30.0 + extra_z
    sensor = make(cls, truths(world)[0], distance=900.0)
    sensor.position = Vec3(x=0.0, y=-600.0, z=6.0)
    return world, sensor, RngStreams(11)


def test_a_los_sensor_does_not_detect_a_target_behind_a_ridge(ridge: Terrain) -> None:
    world, sensor, rng = behind_the_ridge(ridge)
    assert sensor.detect(world, world.tick, rng) == []


def test_the_same_target_is_detected_over_flat_ground_and_above_the_ridge(
    plain: Terrain, ridge: Terrain
) -> None:
    world, sensor, rng = behind_the_ridge(plain)
    assert len(sensor.detect(world, world.tick, rng)) == 1
    world, sensor, rng = behind_the_ridge(ridge, extra_z=120.0)
    assert len(sensor.detect(world, world.tick, rng)) == 1


def test_a_sensor_that_does_not_need_line_of_sight_still_sees_it(ridge: Terrain) -> None:
    world, sensor, rng = behind_the_ridge(ridge, cls=AlwaysDetects)
    assert len(sensor.detect(world, world.tick, rng)) == 1


def test_hiding_a_target_does_not_shift_the_random_streams(ridge: Terrain, plain: Terrain) -> None:
    hidden_world, hidden, rng_a = behind_the_ridge(ridge)
    open_world, seen, rng_b = behind_the_ridge(plain)
    hidden.detect(hidden_world, hidden_world.tick, rng_a)
    seen.detect(open_world, open_world.tick, rng_b)
    assert rng_a.state() == rng_b.state()


def test_radar_and_eo_need_line_of_sight_and_the_others_do_not() -> None:
    from sim.sensors.acoustic import AcousticSensor
    from sim.sensors.rf import RfSensor

    assert RadarSensor.needs_line_of_sight and EoIrSensor.needs_line_of_sight
    assert not AcousticSensor.needs_line_of_sight and not RfSensor.needs_line_of_sight


def test_distance_helper_is_consistent() -> None:
    assert math.isclose(math.hypot(3, 4), 5)


# ---------------------------------------------------------------------- the shipped packs


@pytest.mark.parametrize("pack_id", ["heron-ridge", "osprey-town"])
def test_a_shipped_pack_loads_and_a_real_building_hides_a_low_target(pack_id: str) -> None:
    pack = load_pack(terrain_module.pack_dir(pack_id))
    doc = json.loads((terrain_module.pack_dir(pack_id) / "buildings.json").read_text())
    assert pack.heights.min() == 0.0 and pack.digest
    house = doc["buildings"][0]
    cx = sum(p[0] for p in house["footprint"]) / len(house["footprint"])
    cy = sum(p[1] for p in house["footprint"]) / len(house["footprint"])
    roof = house["base_m"] + house["height_m"]
    assert pack.roof_m(cx, cy) is not None  # the rasterised cell under its centre
    # Through the building 1 m below the roof, from 60 m either side of it: blocked; 5 m above: clear.
    low = pack.blocked((cx - 60, cy, roof - 1), (cx + 60, cy, roof - 1))
    high = pack.blocked(
        (cx - 60, cy, roof + 30 + pack.ground_m(cx - 60, cy)),
        (cx + 60, cy, roof + 30 + pack.ground_m(cx + 60, cy)),
    )
    assert low and not high
