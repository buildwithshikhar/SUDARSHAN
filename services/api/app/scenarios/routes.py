"""Where a scripted threat is, and when, if it flies its route as written.

A planning estimate for the linter and the generator, not the simulation: straight legs at the
waypoint speeds (limited by the class's top speed), holds honoured, no turning radius, no wind. The
sim core is the authority; this says roughly where to look and how long a route takes.
"""

import math
from dataclasses import dataclass

from app.contracts.scenario import Threat


@dataclass(frozen=True, slots=True)
class RoutePoint:
    t: float
    x: float
    y: float
    z: float
    vx: float
    vy: float
    vz: float


def leg_time_s(distance_m: float, speed_mps: float, max_speed_mps: float) -> float:
    """Seconds to fly `distance_m` at the leg speed, never faster than the class allows."""
    return distance_m / max(min(speed_mps, max_speed_mps), 0.1)


def route_end_s(threat: Threat) -> float:
    """Scenario time at which the threat reaches its last waypoint (after any hold there)."""
    t = threat.spawn_s
    x, y, z = threat.start.x, threat.start.y, threat.start.z
    for w in threat.route:
        d = math.dist((x, y, z), (w.position.x, w.position.y, w.position.z))
        t += leg_time_s(d, w.speed_mps, threat.limits.max_speed_mps) + w.hold_s
        x, y, z = w.position.x, w.position.y, w.position.z
    return t


def sample_route(
    threat: Threat, step_s: float = 1.0, until_s: float | None = None
) -> list[RoutePoint]:
    """The threat's position every `step_s` from its spawn until its route ends (then it holds at
    the last waypoint until `until_s`, if given)."""
    points: list[RoutePoint] = []
    t = threat.spawn_s
    x, y, z = threat.start.x, threat.start.y, threat.start.z
    legs: list[tuple[float, float, float, float, float, float, float, float]] = []
    clock = t
    for w in threat.route:
        d = math.dist((x, y, z), (w.position.x, w.position.y, w.position.z))
        flight = leg_time_s(d, w.speed_mps, threat.limits.max_speed_mps)
        legs.append((clock, flight, x, y, z, w.position.x, w.position.y, w.position.z))
        clock += flight
        if w.hold_s > 0:
            legs.append(
                (clock, w.hold_s, w.position.x, w.position.y, w.position.z)
                + (w.position.x, w.position.y, w.position.z)
            )
            clock += w.hold_s
        x, y, z = w.position.x, w.position.y, w.position.z
    end = clock if until_s is None else max(clock, until_s)
    k = 0
    while True:
        now = threat.spawn_s + k * step_s
        if now > end + 1e-9:
            break
        k += 1
        for start_t, flight, x0, y0, z0, x1, y1, z1 in legs:
            if now <= start_t + flight + 1e-9:
                f = 0.0 if flight <= 0 else min(max((now - start_t) / flight, 0.0), 1.0)
                vx = 0.0 if flight <= 0 else (x1 - x0) / flight
                vy = 0.0 if flight <= 0 else (y1 - y0) / flight
                vz = 0.0 if flight <= 0 else (z1 - z0) / flight
                points.append(
                    RoutePoint(
                        now, x0 + (x1 - x0) * f, y0 + (y1 - y0) * f, z0 + (z1 - z0) * f, vx, vy, vz
                    )
                )
                break
        else:
            last = threat.route[-1].position
            points.append(RoutePoint(now, last.x, last.y, last.z, 0.0, 0.0, 0.0))
    return points
