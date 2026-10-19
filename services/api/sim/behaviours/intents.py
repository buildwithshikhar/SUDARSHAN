"""The group's guide behaviour at kinematics level: where the guide goes next.

The guide is whatever flies the group's own route: the leader of a leader-follower group, or the
virtual guide point of a leaderless one. Each call moves a small cursor through the route and
returns where to fly now. The only places the guide goes are the group's own authored waypoints
and the points derived from them. Intents:

- transit: fly the route; at its end do `on_route_end`.
- loiter: orbit the first waypoint at the loiter radius.
- probe: fly the route out to a point `probe_standoff_m` short of the final waypoint, turn back to
  the start of the final leg, and repeat `probe_cycles` times; then do `on_route_end` there.
- saturation: fly the route like transit; the lanes across the track are the members' business
  (see leaderfollower.lane_offset) and the line ends like any route.

The loiter radius, standoff and cycle count are fictional, project-authored values.
"""

import math
from dataclasses import dataclass
from typing import Any

#: A route point: x, y, z (metres) and speed (m/s).
Leg = tuple[float, float, float, float]


@dataclass(frozen=True, slots=True)
class IntentParams:
    intent: str
    on_route_end: str
    loiter_radius: float
    probe_standoff: float
    probe_cycles: int


@dataclass(slots=True)
class Cursor:
    leg: int = 0
    #: run (along the route), out and back (probe), orbit (waiting at the end), done.
    phase: str = "run"
    cycle: int = 0
    #: Where the guide started: the start of the final leg of a one-point probe route.
    ox: float | None = None
    oy: float | None = None
    #: Centre of the orbit flown after the route has ended.
    cx: float = 0.0
    cy: float = 0.0

    def to_state(self) -> dict[str, Any]:
        return {
            "leg": self.leg,
            "phase": self.phase,
            "cycle": self.cycle,
            "origin": None if self.ox is None else [self.ox, self.oy],
            "centre": [self.cx, self.cy],
        }

    @classmethod
    def from_state(cls, state: dict[str, Any]) -> "Cursor":
        origin = state["origin"]
        return cls(
            leg=int(state["leg"]),
            phase=str(state["phase"]),
            cycle=int(state["cycle"]),
            ox=None if origin is None else float(origin[0]),
            oy=None if origin is None else float(origin[1]),
            cx=float(state["centre"][0]),
            cy=float(state["centre"][1]),
        )


@dataclass(frozen=True, slots=True)
class Aim:
    """Where to fly: a point, or an orbit of `orbit` metres around it when `orbit` is positive."""

    x: float
    y: float
    z: float
    speed: float
    orbit: float = 0.0
    #: The route ended on this call (the group's `route_end`).
    ended: bool = False
    #: The route ended with `despawn`: the members leave.
    despawn: bool = False


def _near(px: float, py: float, x: float, y: float, reach: float) -> bool:
    dx, dy = x - px, y - py
    return dx * dx + dy * dy <= reach * reach


def probe_points(route: list[Leg], cur: Cursor, standoff: float) -> tuple[Leg, Leg]:
    """The start of the final leg and the turn-back point, `standoff` short of the final
    waypoint (never closer than a tenth of the leg to the start)."""
    fx, fy, fz, fs = route[-1]
    if len(route) >= 2:
        sx, sy = route[-2][0], route[-2][1]
    else:
        sx, sy = (cur.ox if cur.ox is not None else fx), (cur.oy if cur.oy is not None else fy)
    dx, dy = fx - sx, fy - sy
    length = math.sqrt(dx * dx + dy * dy)
    start: Leg = (sx, sy, fz, fs)
    if length == 0.0:
        return start, start
    stand = min(standoff, 0.9 * length)
    return start, (fx - dx / length * stand, fy - dy / length * stand, fz, fs)


def _finish(params: IntentParams, cur: Cursor, route: list[Leg], x: float, y: float) -> None:
    """The route has ended at (x, y): do `on_route_end`."""
    if params.on_route_end == "loop":
        cur.leg = 0
        cur.cycle = 0
        cur.phase = "out" if params.intent == "probe" and len(route) == 1 else "run"
    elif params.on_route_end == "loiter":
        cur.phase = "orbit"
        cur.cx, cur.cy = x, y
    else:
        cur.phase = "done"


def guide(
    params: IntentParams, route: list[Leg], cur: Cursor, px: float, py: float, reach: float
) -> Aim:
    """Move the cursor if the guide at (px, py) has reached its point, and say where to fly."""
    n = len(route)
    if params.intent == "loiter":
        x, y, z, s = route[0]
        return Aim(x, y, z, s, orbit=params.loiter_radius)
    if cur.ox is None:
        cur.ox, cur.oy = px, py
        if params.intent == "probe" and n == 1:
            cur.phase = "out"
    ended = False
    if cur.phase == "run":
        x, y, z, s = route[cur.leg]
        if _near(px, py, x, y, reach):
            cur.leg += 1
            if cur.leg >= n:
                _finish(params, cur, route, x, y)
                ended = True
            elif params.intent == "probe" and cur.leg == n - 1:
                cur.phase = "out"
    elif cur.phase in ("out", "back"):
        start, turn = probe_points(route, cur, params.probe_standoff)
        point = turn if cur.phase == "out" else start
        if _near(px, py, point[0], point[1], reach):
            if cur.phase == "out":
                cur.cycle += 1
                cur.phase = "back"
            elif cur.cycle >= params.probe_cycles:
                _finish(params, cur, route, start[0], start[1])
                ended = True
            else:
                cur.phase = "out"
    return _aim(params, route, cur, ended)


def _aim(params: IntentParams, route: list[Leg], cur: Cursor, ended: bool) -> Aim:
    last = route[-1]
    if cur.phase == "done":
        return Aim(last[0], last[1], last[2], last[3], ended=ended, despawn=True)
    if cur.phase == "orbit":
        return Aim(cur.cx, cur.cy, last[2], last[3], orbit=params.loiter_radius, ended=ended)
    if cur.phase in ("out", "back"):
        start, turn = probe_points(route, cur, params.probe_standoff)
        x, y, z, s = turn if cur.phase == "out" else start
        return Aim(x, y, z, s, ended=ended)
    x, y, z, s = route[cur.leg]
    return Aim(x, y, z, s, ended=ended)
