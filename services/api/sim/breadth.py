"""The wave 8 breadth scene: a 24-drone swarm, a 30-bird flock, two kites and a balloon, with all
six sensor profiles watching, on either terrain pack.

It is one fixed, fictional scene used by two things: the integration tests (every behaviour, every
sensor and the terrain together) and the render benchmark, which plays the recorded positions of
the real behaviours instead of placeholder markers (`trajectory`). It is not a scenario for
trainees: no zone, no defended place, nothing to respond to.
"""

from typing import Any

from app.contracts import ScenarioSpec

from .behaviours.arrival import compose_members, formation_starts
from .catalogue import load_catalogue
from .recognition import recognition_class
from .terrain import load_pack, pack_dir
from .world import World

SWARM = 24
BIRDS = 30
KITES = 2
#: Seed of the composition (which swarm members are decoys or RF-silent) and of the run.
SEED = 8
#: The swarm circles this point; the flock circles another near it; both in view of the origin.
SWARM_CENTRE = (500.0, 100.0)
FLOCK_CENTRE = (430.0, -20.0)
HALF_EXTENT_M = 1200.0
FORMAT = "bench-scene.v1"

_SENSORS = (
    ("radar-1", "radar-generic-s", "0.3.0"),
    ("eo-1", "eo-generic-day", "0.2.0"),
    ("nv-1", "eo-generic-nv", "0.2.0"),
    ("ir-1", "ir-generic-thermal", "0.2.0"),
    ("rf-1", "rf-generic-passive", "1.1.0"),
    ("ac-1", "acoustic-generic-array", "1.1.0"),
)


def _text(en: str) -> dict[str, str]:
    return {"en": en, "hi": en}


def _point(x: float, y: float, z: float) -> dict[str, float]:
    return {"x": x, "y": y, "z": z}


def breadth_scenario(pack_id: str = "heron-ridge", *, sensors: bool = True) -> ScenarioSpec:
    catalogue = load_catalogue()
    terrain = load_pack(pack_dir(pack_id))

    def ground(x: float, y: float) -> float:
        return float(terrain.ground_m(x, y))

    # One height above the highest ground under each formation, so no member starts underground.
    swarm_z = (
        max(
            ground(SWARM_CENTRE[0] + dx, SWARM_CENTRE[1] + dy)
            for dx in (-250, 0, 250)
            for dy in (-250, 0, 250)
        )
        + 60.0
    )
    flock_z = (
        max(
            ground(FLOCK_CENTRE[0] + dx, FLOCK_CENTRE[1] + dy)
            for dx in (-150, 0, 150)
            for dy in (-150, 0, 150)
        )
        + 30.0
    )

    def member(
        name: str, class_id: str, x: float, y: float, z: float, heading: float, speed: float
    ) -> dict[str, Any]:
        cls = catalogue.get(class_id)
        return {
            "id": name,
            "class_id": class_id,
            "disposition": "clutter" if cls.category == "clutter" else cls.default_disposition,
            "label": _text(name),
            "spawn_s": 0.0,
            "start": _point(x, y, z),
            "start_heading_deg": heading,
            "start_speed_mps": speed,
            "limits": catalogue.limits_for(class_id).model_dump(mode="json"),
            "route": [{"position": _point(x, y, z), "speed_mps": 5.0}],
            "on_route_end": "loiter",
        }

    threats: list[dict[str, Any]] = []
    classes = compose_members("rotary-small", SWARM, 0.125, 0.125, SEED)
    # The leader is a plain quadcopter: a decoy or an RF-silent drone leading is a later scenario.
    first_plain = classes.index("rotary-small")
    classes[0], classes[first_plain] = classes[first_plain], classes[0]
    spots = formation_starts(SWARM, 20.0, (SWARM_CENTRE[0] - 120.0, SWARM_CENTRE[1]), 0.0, "loiter")
    swarm_ids = [f"swarm-{i:02d}" for i in range(SWARM)]
    for name, class_id, (x, y) in zip(swarm_ids, classes, spots, strict=True):
        threats.append(member(name, class_id, x, y, swarm_z, 0.0, 8.0))
    bird_ids = [f"bird-{i:02d}" for i in range(BIRDS)]
    bird_spots = formation_starts(
        BIRDS, 8.0, (FLOCK_CENTRE[0] - 60.0, FLOCK_CENTRE[1]), 0.0, "loiter"
    )
    for name, (x, y) in zip(bird_ids, bird_spots, strict=True):
        threats.append(member(name, "bird", x, y, flock_z, 0.0, 8.0))
    kite_anchors = ((250.0, -200.0), (300.0, -240.0))
    for i, (ax, ay) in enumerate(kite_anchors[:KITES]):
        anchor = _point(ax, ay, ground(ax, ay))
        kite = member(f"kite-{i}", "kite", ax, ay, anchor["z"] + 40.0, 0.0, 1.0)
        kite["motion"] = {
            "kind": "tether",
            "anchor": anchor,
            "length_m": 80.0,
            "sway_m": 20.0,
            "sway_period_s": 9.0 + 3.0 * i,
        }
        threats.append(kite)
    balloon = member("balloon-0", "balloon", 300.0, 200.0, ground(300.0, 200.0) + 40.0, 0.0, 0.5)
    balloon["motion"] = {"kind": "drift", "climb_mps": 0.5}
    threats.append(balloon)

    groups = [
        {
            "id": "swarm",
            "kind": "swarm",
            "members": swarm_ids,
            "topology": "leader-follower",
            "leader": swarm_ids[0],
            "intent": "loiter",
            "route": [{"position": _point(*SWARM_CENTRE, swarm_z), "speed_mps": 8.0}],
            "on_route_end": "loiter",
            "discipline": 0.9,
            "spacing_m": 20.0,
            "neighbour_radius_m": 80.0,
            "link_range_m": 400.0,
            "loiter_radius_m": 90.0,
        },
        {
            "id": "flock",
            "kind": "flock",
            "members": bird_ids,
            "topology": "leaderless",
            "intent": "loiter",
            "route": [{"position": _point(*FLOCK_CENTRE, flock_z), "speed_mps": 9.0}],
            "on_route_end": "loiter",
            "discipline": 0.7,
            "spacing_m": 8.0,
            "neighbour_radius_m": 60.0,
            "link_range_m": 200.0,
            "loiter_radius_m": 60.0,
        },
    ]
    placed = [
        {
            "id": sensor_id,
            "profile": {"id": profile, "version": version},
            "position": _point(-60.0 + 20.0 * i, 40.0, ground(-60.0 + 20.0 * i, 40.0) + 6.0),
            "boresight_deg": 75.0,
        }
        for i, (sensor_id, profile, version) in enumerate(_SENSORS)
    ]
    return ScenarioSpec.model_validate(
        {
            "contract": "scenario.v1",
            "id": f"breadth-{pack_id}",
            "version": "1.0.0",
            "title": _text("Threat breadth"),
            "summary": _text("A swarm, a flock, kites and a balloon, for tests and the benchmark."),
            "fictional": True,
            "default_seed": SEED,
            "duration_s": 120.0,
            "world": {
                "terrain": {"kind": "pack", "id": pack_id, "version": "1.0.0"},
                "half_extent_m": HALF_EXTENT_M,
                "start_time_of_day_h": 14.0,
                "weather": {
                    "condition": "clear",
                    "visibility_m": 20000,
                    "wind_speed_mps": 3.0,
                    "wind_from_deg": 250.0,
                    "gust_sigma_mps": 0.5,
                    "temperature_c": 22,
                    "cloud_cover_pct": 20,
                },
            },
            "rule_pack": {"id": "training-baseline", "version": "1.0.0"},
            "sensors": placed if sensors else [],
            "threats": threats,
            "groups": groups,
        }
    )


def trajectory(
    spec: ScenarioSpec, seed: int = SEED, *, duration_s: float = 60.0, hz: float = 4.0
) -> dict[str, Any]:
    """The positions of every contact over time, for the render benchmark.

    Runs the real behaviours in a bare world (no sensors needed) and samples the positions every
    `1 / hz` seconds, in decimetres as whole numbers so the file is small and identical on every
    platform. `shape` is the operator class the contact is drawn as.
    """
    world = World(spec, seed)
    every = round(20 / hz)
    frames: list[list[int]] = []
    world.step()  # the contacts spawn on the first tick; the first sample is after it
    for tick in range(round(duration_s * 20) + 1):
        if tick % every == 0:  # tick 0 is the world after its first step
            row: list[int] = []
            for d in world.drones:
                active = d.status == "active"
                row += [round(d.x * 10), round(d.y * 10), round(d.z * 10)] if active else [0, 0, 0]
            frames.append(row)
        world.step()
    return {
        "format": FORMAT,
        "pack": spec.world.terrain.id if spec.world.terrain.kind == "pack" else None,
        "hz": hz,
        "duration_s": duration_s,
        "unit": "dm",
        "members": [{"id": t.id, "shape": recognition_class(t.class_id)} for t in spec.threats],
        "frames": frames,
    }


def main(argv: list[str] | None = None) -> int:
    """`python -m sim.breadth PATH` writes the benchmark trajectory for the rural pack."""
    import json
    import sys
    from pathlib import Path

    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print("usage: python -m sim.breadth PATH", file=sys.stderr)
        return 2
    data = trajectory(breadth_scenario("heron-ridge", sensors=False), hz=2.0)
    Path(args[0]).write_text(json.dumps(data, separators=(",", ":")) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
