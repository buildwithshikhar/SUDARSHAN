"""The terrain-pack scenario: it names a pack that exists, terrain changes what is seen, and the
hostile contact is still tracked well before the inner zone (not an oracle-defender solve)."""

import math
from pathlib import Path

from app.contracts import ScenarioSpec
from app.contracts.loader import load_pack
from app.contracts.scenario import PackTerrain
from sim.roe import load_rule_engine
from sim.terrain import load_pack as load_terrain
from sim.terrain import pack_dir
from sim.tracking.picture import Picture
from sim.world import World

from .sim_cases import REPO

PATH = REPO / "packs" / "scenarios" / "heron-ridge-low-approach.v1.json"


def spec() -> ScenarioSpec:
    loaded = load_pack(PATH)
    assert isinstance(loaded, ScenarioSpec)
    return loaded


def flat(source: ScenarioSpec) -> ScenarioSpec:
    data = source.model_dump(mode="json")
    data["world"]["terrain"] = {"kind": "flat", "elevation_m": 0}
    return ScenarioSpec.model_validate(data)


def confirm_quad(source: ScenarioSpec) -> tuple[float, float]:
    """(time in s, distance from the depot in m) when a confirmed track follows the hostile."""
    world = World(
        source,
        source.default_seed,
        picture=Picture.build(source, source.default_seed),
        roe=load_rule_engine(source),
    )
    assert world.picture is not None
    quad = next(d for d in world.drones if d.id == "contact-quad")
    for _ in range(20 * 300):
        world.step()
        for track_id, track in world.picture.tracker.tracks.items():
            if (
                track.status == "confirmed"
                and world.picture.ledger.identity_of(track_id) == "contact-quad"
            ):
                return world.time_s, math.hypot(quad.x, quad.y)
    raise AssertionError("the hostile contact was never tracked")


def test_the_scenario_names_a_shipped_pack_and_fits_inside_it() -> None:
    s = spec()
    assert isinstance(s.world.terrain, PackTerrain) and s.fictional
    terrain = load_terrain(pack_dir(s.world.terrain.id))
    assert (terrain.pack_id, terrain.version) == (s.world.terrain.id, s.world.terrain.version)
    assert s.world.half_extent_m <= terrain.half_extent_m
    for sensor in s.sensors:  # on the ground of this pack, not floating or buried
        agl = sensor.position.z - terrain.ground_m(sensor.position.x, sensor.position.y)
        assert 2.0 <= agl <= 12.0, (sensor.id, agl)


def test_every_threat_flies_above_the_ground_of_the_pack() -> None:
    s = spec()
    assert isinstance(s.world.terrain, PackTerrain)
    terrain = load_terrain(pack_dir(s.world.terrain.id))
    for threat in s.threats:
        for p in [threat.start, *(w.position for w in threat.route)]:
            agl = p.z - terrain.ground_m(p.x, p.y)
            assert agl >= 5.0, (threat.id, p, agl)
            assert abs(p.x) <= s.world.half_extent_m and abs(p.y) <= s.world.half_extent_m


def test_every_text_has_english_and_hindi() -> None:
    s = spec()
    for text in (s.title, s.summary, *(t.label for t in s.threats), *(a.label for a in s.assets)):
        assert text.en.strip() and text.hi.strip()


def test_terrain_delays_the_hostile_track_but_it_is_confirmed_before_the_inner_zone() -> None:
    s = spec()
    inner = next(z.radius_m for z in s.zones if z.role == "inner")
    t_pack, r_pack = confirm_quad(s)
    t_flat, r_flat = confirm_quad(flat(s))
    assert t_pack > t_flat + 10.0, (t_pack, t_flat)  # the village hides it for a while
    assert r_pack < r_flat
    assert r_pack > 2.0 * inner  # and it is still tracked far outside the inner zone


def test_the_log_names_the_pack_it_ran_on() -> None:
    s = spec()
    world = World(s, s.default_seed)
    terrain = world.log.records[0].payload["terrain"]
    assert isinstance(terrain, dict) and terrain["id"] == "heron-ridge"
    assert Path(pack_dir("heron-ridge") / "manifest.json").is_file()
