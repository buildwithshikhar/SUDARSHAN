"""Scenarios for the group and clutter behaviour tests: a flat play area with no defended places,
no zones and no sensors, members of the catalogue's classes, and a group around them."""

from typing import Any

from app.contracts import ScenarioSpec
from sim.catalogue import load_catalogue
from sim.world import World

CATALOGUE = load_catalogue()


def text(en: str) -> dict[str, str]:
    return {"en": en, "hi": en}


def limits(class_id: str) -> dict[str, float]:
    lim = CATALOGUE.limits_for(class_id)
    return lim.model_dump()


def wp(x: float, y: float, z: float = 60.0, speed: float = 10.0) -> dict[str, Any]:
    return {"position": {"x": x, "y": y, "z": z}, "speed_mps": speed}


def member(
    name: str,
    x: float,
    y: float,
    *,
    class_id: str = "rotary-small",
    z: float = 60.0,
    heading: float = 90.0,
    speed: float = 8.0,
    spawn_s: float = 0.0,
    disposition: str | None = None,
) -> dict[str, Any]:
    default = CATALOGUE.get(class_id).default_disposition
    return {
        "id": name,
        "class_id": class_id,
        "disposition": disposition or default,
        "label": text(name),
        "spawn_s": spawn_s,
        "start": {"x": x, "y": y, "z": z},
        "start_heading_deg": heading,
        "start_speed_mps": speed,
        "limits": limits(class_id),
        "route": [{"position": {"x": x, "y": y, "z": z}, "speed_mps": 5.0}],
        "on_route_end": "loiter",
    }


def scenario(
    threats: list[dict[str, Any]],
    groups: list[dict[str, Any]] | None = None,
    *,
    wind: float = 0.0,
    wind_from: float = 270.0,
    gust: float = 0.0,
    duration_s: float = 600.0,
    half: float = 20000.0,
) -> ScenarioSpec:
    return ScenarioSpec.model_validate(
        {
            "contract": "scenario.v1",
            "id": "behaviour-test",
            "version": "1.0.0",
            "title": text("Behaviour test"),
            "summary": text("A scenario for the group behaviour tests."),
            "fictional": True,
            "default_seed": 7,
            "duration_s": duration_s,
            "world": {
                "terrain": {"kind": "flat", "elevation_m": 0},
                "half_extent_m": half,
                "start_time_of_day_h": 9.0,
                "weather": {
                    "condition": "clear",
                    "visibility_m": 20000,
                    "wind_speed_mps": wind,
                    "wind_from_deg": wind_from,
                    "gust_sigma_mps": gust,
                    "temperature_c": 20,
                    "cloud_cover_pct": 10,
                },
            },
            "rule_pack": {"id": "training-baseline", "version": "1.0.0"},
            "threats": threats,
            "groups": groups or [],
        }
    )


def group(members: list[str], route: list[dict[str, Any]], **kw: Any) -> dict[str, Any]:
    return {"id": "g1", "members": members, "route": route, **kw}


def swarm_scenario(
    n: int = 12,
    *,
    class_id: str = "rotary-small",
    route: list[dict[str, Any]] | None = None,
    intent: str = "transit",
    spacing: float = 20.0,
    start_heading: float = 90.0,
    scatter: bool = False,
    wind: float = 0.0,
    **group_kw: Any,
) -> ScenarioSpec:
    """`n` members in the formation the intent implies, heading east along y = 0 by default. With
    `scatter` the start headings are spread round the compass so alignment has work to do."""
    from sim.behaviours.arrival import formation_starts

    names = [f"m{i:02d}" for i in range(n)]
    spots = formation_starts(n, spacing, (-1500.0, 0.0), start_heading, intent)
    threats = [
        member(
            name,
            x,
            y,
            class_id=class_id,
            heading=(i * 137.5) % 360.0 if scatter else start_heading,
        )
        for i, (name, (x, y)) in enumerate(zip(names, spots, strict=True))
    ]
    path = route or [wp(1500.0, 0.0, 60.0, 10.0)]
    groups = [
        group(
            names,
            path,
            intent=intent,
            spacing_m=spacing,
            **group_kw,
        )
    ]
    return scenario(threats, groups, wind=wind)


def run(world: World, ticks: int) -> None:
    for _ in range(ticks):
        world.step()


def active(world: World) -> list[Any]:
    return [d for d in world.drones if d.status == "active"]
