"""Waypoint-following kinematics inside class limits.

Kinematics only: the drone flies its scripted route at the scripted speeds, limited by the class
envelope. There is no guidance, pursuit of a defended asset, or terminal behaviour (locked rule 2).

Per tick, in this order: waypoint arrival and mode changes, heading (turn-rate limited), airspeed
(acceleration limited), altitude (climb and descent limited, clamped to the altitude band), then
position from the air velocity plus the wind.
"""

import math
from dataclasses import dataclass
from typing import Any

from app.contracts.scenario import KinematicLimits, Threat

from . import detmath
from .constants import (
    ARRIVAL_RADIUS_MIN_M,
    CLIMB_GAIN_PER_S,
    DT,
    ORBIT_GAIN,
    ORBIT_RADIUS_M,
    PAYLOAD_DECIMALS,
)
from .entity import Drone

Event = tuple[str, dict[str, Any]]


@dataclass(frozen=True, slots=True)
class Envelope:
    """Per-tick form of a class's kinematic limits."""

    max_speed: float
    accel_step: float
    max_climb: float
    max_descent: float
    turn_rate: float  # rad/s
    cos_turn: float  # cos and sin of the largest heading change in one tick
    sin_turn: float
    min_alt: float
    max_alt: float

    @classmethod
    def of(cls, limits: KinematicLimits) -> "Envelope":
        turn_rate = limits.max_turn_rate_dps * detmath.DEG
        return cls(
            max_speed=limits.max_speed_mps,
            accel_step=limits.max_accel_mps2 * DT,
            max_climb=limits.max_climb_mps,
            max_descent=limits.max_descent_mps,
            turn_rate=turn_rate,
            cos_turn=detmath.cos(turn_rate * DT),
            sin_turn=detmath.sin(turn_rate * DT),
            min_alt=limits.min_altitude_m,
            max_alt=limits.max_altitude_m,
        )


def position(d: Drone) -> dict[str, float]:
    return {k: round(v, PAYLOAD_DECIMALS) for k, v in (("x", d.x), ("y", d.y), ("z", d.z))}


def _next_leg(d: Drone, threat: Threat, events: list[Event]) -> None:
    if d.leg + 1 < len(threat.route):
        d.leg += 1
        d.mode = "route"
        return
    events.append(("threat.route_end", {"id": d.id, "then": threat.on_route_end}))
    if threat.on_route_end == "loop":
        d.leg = 0
        d.mode = "route"
    elif threat.on_route_end == "loiter":
        d.mode = "loiter"
    else:
        d.status = "despawned"
        events.append(("threat.despawn", {"id": d.id, "reason": "route-end", **position(d)}))


def orbit_direction(
    x: float, y: float, ux: float, uy: float, cx: float, cy: float, radius: float
) -> tuple[float, float]:
    """Clockwise orbit of the given radius around (cx, cy), pulling back onto the circle.

    (ux, uy) is the current heading, returned unchanged when the point sits on the centre."""
    rx, ry = x - cx, y - cy
    dist = math.sqrt(rx * rx + ry * ry)
    if dist == 0.0:
        return ux, uy
    rx, ry = rx / dist, ry / dist
    pull = detmath.clamp((dist - radius) / radius * ORBIT_GAIN, -1.0, 4.0)
    return detmath.unit(ry - pull * rx, -rx - pull * ry)


def _orbit_direction(d: Drone, cx: float, cy: float) -> tuple[float, float]:
    """Clockwise orbit of radius ORBIT_RADIUS_M around (cx, cy), pulling back onto the circle."""
    return orbit_direction(d.x, d.y, d.ux, d.uy, cx, cy, ORBIT_RADIUS_M)


def step(d: Drone, threat: Threat, env: Envelope, wind: tuple[float, float]) -> list[Event]:
    """Advance one active drone by one tick; returns the events it produced."""
    events: list[Event] = []

    # 1. arrival and mode changes
    wp = threat.route[d.leg]
    if d.mode == "route":
        dx, dy = wp.position.x - d.x, wp.position.y - d.y
        reach = max(ARRIVAL_RADIUS_MIN_M, d.airspeed / env.turn_rate)
        if dx * dx + dy * dy <= reach * reach:
            events.append(("threat.waypoint", {"id": d.id, "index": d.leg, **position(d)}))
            if wp.hold_s > 0:
                d.mode = "hold"
                d.hold_ticks_left = round(wp.hold_s / DT)
            else:
                _next_leg(d, threat, events)
    elif d.mode == "hold":
        d.hold_ticks_left -= 1
        if d.hold_ticks_left <= 0:
            d.hold_ticks_left = 0
            _next_leg(d, threat, events)
    if d.status != "active":
        return events
    wp = threat.route[d.leg]

    if d.mode == "route":
        want = detmath.unit(wp.position.x - d.x, wp.position.y - d.y)
    else:
        want = _orbit_direction(d, wp.position.x, wp.position.y)
    step_steered(d, env, wind, want, wp.speed_mps, wp.position.z)
    return events


def step_steered(
    d: Drone,
    env: Envelope,
    wind: tuple[float, float],
    want: tuple[float, float],
    speed: float,
    altitude: float,
) -> None:
    """Steps 2-5 of a tick for a drone told which way, how fast and how high to fly.

    The drone is limited by its own class envelope exactly like a route follower: heading turns
    at most one tick's turn rate, airspeed changes at most one tick's acceleration and stays
    within the class maximum, altitude changes at the climb or descent limit and is clamped to
    the altitude band. `want` is a unit vector (east, north).
    """
    # 2. heading
    d.ux, d.uy = detmath.rotate_towards((d.ux, d.uy), want, env.cos_turn, env.sin_turn)

    # 3. airspeed
    change = detmath.clamp(speed - d.airspeed, -env.accel_step, env.accel_step)
    d.airspeed = detmath.clamp(d.airspeed + change, 0.0, env.max_speed)

    # 4. altitude
    vz = detmath.clamp((altitude - d.z) * CLIMB_GAIN_PER_S, -env.max_descent, env.max_climb)
    z = detmath.clamp(d.z + vz * DT, env.min_alt, env.max_alt)
    d.vz = (z - d.z) / DT
    d.z = z

    # 5. position: air velocity plus wind
    d.x += (d.ux * d.airspeed + wind[0]) * DT
    d.y += (d.uy * d.airspeed + wind[1]) * DT
