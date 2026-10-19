"""One group's steering: who leads, where the guide is, what each member is told to do this tick.

`GroupController.plan` is a pure function of the controller's own state, the tick, the wind and
the members' positions. It returns, for every active member, a `Command` (a unit heading, an
airspeed and an altitude), plus the ground-truth events of the tick. It never moves anything
itself: the world flies each member with its own class envelope (`kinematics.step_steered`).

A member goes only where its own group takes it. The inputs are the group's authored route, the
guide that flies it, and the group-mates' positions and headings. Nothing else is read.

Control modes:

- `leader`: a leader flies the guide route; followers hold slots in its frame, or flock with
  their linked neighbours when out of link with it.
- `hold`: the leader is gone; followers keep their last formation heading and speed.
- `free`: no leader. A virtual guide point flies the route; members flock towards it (or, for
  saturation, take lanes across its track).
- `loiter`: every member circles the point where the group was when the leader was lost.

Tick order inside `plan`: formation check, link epoch, group speed, leader-loss state machine,
then the guide and the members' commands.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from app.contracts.scenario import Group

from .. import detmath
from ..constants import ARRIVAL_RADIUS_MIN_M, DT
from ..kinematics import orbit_direction
from . import boids, intents, leaderfollower, links
from .draws import Draws

Event = tuple[str, dict[str, Any]]
Vec = tuple[float, float]

#: A group flies at this share of its slowest active member's top speed, leaving the others
#: room to close up on their slots.
SPEED_MARGIN = 0.85
#: The Vicsek noise draw of a member is held for this many ticks (one second).
NOISE_HOLD_TICKS = 20
#: The virtual guide turns no faster than this, and no faster than half the slowest member.
GUIDE_TURN_DPS = 20.0
#: Speed correction in m/s per metre the guide is ahead of a member along its track.
SPEED_GAIN_PER_S = 0.5
#: Separation push in a slot formation, as a share of the group speed.
SEPARATION_SPEED_SHARE = 0.5
#: Largest speed correction towards a slot, as a share of the group speed.
CORRECTION_SHARE = 0.5


@dataclass(frozen=True, slots=True)
class MemberView:
    """What the group may know about a member: where it is and what it can do."""

    id: str
    status: str
    x: float
    y: float
    z: float
    ux: float
    uy: float
    airspeed: float
    max_speed: float
    turn_rate: float  # rad/s


@dataclass(frozen=True, slots=True)
class Command:
    """A unit heading, an airspeed and an altitude for one tick; the member's own envelope
    limits what it can do about it."""

    ux: float
    uy: float
    speed: float
    altitude: float


@dataclass(slots=True)
class Plan:
    commands: dict[str, Command] = field(default_factory=dict)
    events: list[Event] = field(default_factory=list)
    #: Members that leave because the group's route ended with `despawn`.
    despawn: list[str] = field(default_factory=list)


class GroupController:
    def __init__(self, group: Group, seed: int) -> None:
        self.group = group
        self.draws = Draws(seed, group.id)
        self.params = intents.IntentParams(
            group.intent,
            group.on_route_end,
            group.loiter_radius_m,
            group.probe_standoff_m,
            group.probe_cycles,
        )
        self.route: list[intents.Leg] = [
            (w.position.x, w.position.y, w.position.z, w.speed_mps) for w in group.route
        ]
        w = group.weights
        self.weights = (w.separation, w.alignment, w.cohesion, w.goal)
        self.formation = leaderfollower.formation_for(group.intent)
        self.epoch_ticks = round(group.link_epoch_s / DT)
        self.hold_ticks = round(group.leader_loss_hold_s / DT)
        self.formed = False
        self.control = "leader" if group.topology == "leader-follower" else "free"
        self.leader: str | None = group.leader
        self.leader_seen = False
        self.hold_left = 0
        self.centre: Vec | None = None
        self.cursor = intents.Cursor()
        self.guide_ready = False
        self.gx = self.gy = 0.0
        self.gux, self.guy = 0.0, 1.0
        self.link_epoch = -1
        self.link_pairs: list[links.Pair] = []
        self.last: dict[str, tuple[float, float, float]] = {}
        #: Memo of each member's noise draw for its noise epoch. A pure function of the key, so
        #: it is not state: a restored controller simply draws again.
        self._xi: dict[str, tuple[int, float]] = {}
        #: Active members at the last plan, in scenario order (for the metrics).
        self.active_ids: list[str] = []

    # ------------------------------------------------------------------ state

    def state(self) -> dict[str, Any]:
        return {
            "formed": self.formed,
            "control": self.control,
            "leader": self.leader,
            "leader_seen": self.leader_seen,
            "hold_left": self.hold_left,
            "centre": None if self.centre is None else [self.centre[0], self.centre[1]],
            "cursor": self.cursor.to_state(),
            "guide": {
                "ready": self.guide_ready,
                "x": self.gx,
                "y": self.gy,
                "ux": self.gux,
                "uy": self.guy,
            },
            "links": {"epoch": self.link_epoch, "pairs": [[a, b] for a, b in self.link_pairs]},
            "last": {k: [v[0], v[1], v[2]] for k, v in sorted(self.last.items())},
        }

    def restore(self, state: dict[str, Any]) -> None:
        self.formed = bool(state["formed"])
        self.control = str(state["control"])
        self.leader = None if state["leader"] is None else str(state["leader"])
        self.leader_seen = bool(state["leader_seen"])
        self.hold_left = int(state["hold_left"])
        centre = state["centre"]
        self.centre = None if centre is None else (float(centre[0]), float(centre[1]))
        self.cursor = intents.Cursor.from_state(state["cursor"])
        guide = state["guide"]
        self.guide_ready = bool(guide["ready"])
        self.gx, self.gy = float(guide["x"]), float(guide["y"])
        self.gux, self.guy = float(guide["ux"]), float(guide["uy"])
        self.link_epoch = int(state["links"]["epoch"])
        self.link_pairs = [(str(a), str(b)) for a, b in state["links"]["pairs"]]
        self.last = {k: (float(v[0]), float(v[1]), float(v[2])) for k, v in state["last"].items()}

    # ------------------------------------------------------------------ the tick

    def plan(self, tick: int, wind: Vec, views: Sequence[MemberView]) -> Plan:
        plan = Plan()
        if not self.formed and all(v.status != "pending" for v in views):
            self.formed = True
            plan.events.append(("group.formed", {"group": self.group.id, "members": len(views)}))
        active = [v for v in views if v.status == "active"]
        self.active_ids = [v.id for v in active]
        if not active:
            return plan
        self._update_links(tick, active)
        cap = SPEED_MARGIN * min(v.max_speed for v in active)
        if self.control == "leader":
            by_id = {v.id: v for v in active}
            if self.leader in by_id:
                self.leader_seen = True
            elif self.leader_seen:
                plan.events.append(
                    (
                        "group.leader_lost",
                        {
                            "group": self.group.id,
                            "leader": self.leader,
                            "hold_s": self.group.leader_loss_hold_s,
                        },
                    )
                )
                self.control = "hold"
                self.hold_left = self.hold_ticks
        if self.control == "hold":
            if self.hold_left > 0:
                self.hold_left -= 1
                self._hold(active, plan)
                return plan
            self._resolve(active, plan)
        if self.control == "leader":
            self._plan_leader(tick, wind, active, cap, plan)
        elif self.control == "loiter":
            self._plan_loiter(active, cap, plan)
        else:
            self._plan_free(tick, wind, active, cap, plan)
        return plan

    # ------------------------------------------------------------------ links

    def _update_links(self, tick: int, active: Sequence[MemberView]) -> None:
        epoch = tick // self.epoch_ticks
        if epoch == self.link_epoch:
            return
        self.link_epoch = epoch

        def down(pair: links.Pair) -> float:
            return self.draws.uniform(f"{pair[0]}:{pair[1]}", epoch, "link")

        self.link_pairs = links.rebuild(
            [v.id for v in active],
            [v.x for v in active],
            [v.y for v in active],
            self.group.link_range_m,
            self.group.link_loss,
            down,
        )

    def graph(self) -> links.Graph:
        """The communication graph among the members active at the last plan."""
        return links.Graph(self.active_ids, self.link_pairs)

    # ------------------------------------------------------------------ leader loss

    def _hold(self, active: Sequence[MemberView], plan: Plan) -> None:
        for v in active:
            ux, uy, speed = self.last.get(v.id, (v.ux, v.uy, v.airspeed))
            plan.commands[v.id] = Command(ux, uy, speed, v.z)

    def _resolve(self, active: Sequence[MemberView], plan: Plan) -> None:
        """The hold is over: elect, disperse or loiter, as the group is set to."""
        mode = self.group.leader_loss
        if mode == "elect":
            previous = self.leader
            self.leader = min(v.id for v in active)
            self.leader_seen = True
            self.control = "leader"
            self.last.pop(self.leader, None)
            plan.events.append(
                (
                    "group.leader_elected",
                    {"group": self.group.id, "leader": self.leader, "previous": previous},
                )
            )
            return
        cx, cy = self._centroid(active)
        if mode == "disperse":
            self.control = "free"
            self.guide_ready = False
        else:
            self.control = "loiter"
            self.centre = (cx, cy)

    @staticmethod
    def _centroid(active: Sequence[MemberView]) -> Vec:
        sx = sy = 0.0
        for v in active:
            sx += v.x
            sy += v.y
        return sx / len(active), sy / len(active)

    # ------------------------------------------------------------------ leader and followers

    def _plan_leader(
        self, tick: int, wind: Vec, active: Sequence[MemberView], cap: float, plan: Plan
    ) -> None:
        leader = next((v for v in active if v.id == self.leader), None)
        if leader is None:  # the leader has not appeared yet: keep flying as you are
            for v in active:
                plan.commands[v.id] = Command(v.ux, v.uy, v.airspeed, v.z)
            return
        reach = max(ARRIVAL_RADIUS_MIN_M, leader.airspeed / leader.turn_rate)
        aim = intents.guide(self.params, self.route, self.cursor, leader.x, leader.y, reach)
        if self._route_events(aim, active, plan):
            return
        if aim.orbit > 0.0:
            want = orbit_direction(
                leader.x, leader.y, leader.ux, leader.uy, aim.x, aim.y, aim.orbit
            )
        else:
            want = detmath.unit(aim.x - leader.x, aim.y - leader.y)
        plan.commands[leader.id] = Command(want[0], want[1], min(aim.speed, cap), aim.z)

        followers = [v for v in active if v.id != leader.id]
        slots = self._slot_offsets(followers)
        graph = self.graph()
        near = self._neighbourhoods(active)
        index = {v.id: i for i, v in enumerate(active)}
        sep_speed = SEPARATION_SPEED_SHARE * cap
        # a follower hears the leader through any chain of links: it is in the leader's component
        in_link = {m: True for c in graph.components() if leader.id in c for m in c}
        for v in followers:
            i = index[v.id]
            sep = self._separation(active, near[i], i)
            if v.id in in_link:
                sx, sy = leaderfollower.to_world(
                    leader.x, leader.y, leader.ux, leader.uy, slots[v.id]
                )
                vx, vy = leaderfollower.follow(
                    v.x,
                    v.y,
                    sx,
                    sy,
                    leader.ux * leader.airspeed,
                    leader.uy * leader.airspeed,
                    sep,
                    sep_speed,
                    CORRECTION_SHARE * cap,
                )
                (hx, hy), speed = leaderfollower.heading_and_speed(vx, vy, (leader.ux, leader.uy))
                self.last[v.id] = (hx, hy, speed)
                nx, ny = self._noise(v.id, tick, hx, hy)
                plan.commands[v.id] = Command(nx, ny, speed, leader.z)
            else:
                plan.commands[v.id] = self._flock_without_leader(
                    tick, v, active, near[i], i, graph, sep, leader.z
                )

    def _slot_offsets(self, followers: Sequence[MemberView]) -> dict[str, leaderfollower.Offset]:
        """Each follower's slot in the leader's frame, by rank (so the slots close up)."""
        out: dict[str, leaderfollower.Offset] = {}
        line = self.formation == "line"
        spacing = self.group.lane_spacing_m if line else self.group.spacing_m
        table = leaderfollower.offsets(self.formation, len(followers) + 1, spacing)
        for rank, fid in enumerate(sorted(v.id for v in followers)):
            out[fid] = table[rank + 1]
        return out

    def _flock_without_leader(
        self,
        tick: int,
        v: MemberView,
        active: Sequence[MemberView],
        near: Sequence[int],
        i: int,
        graph: links.Graph,
        sep: Vec,
        altitude: float,
    ) -> Command:
        """A follower out of link with its leader: it holds its last formation heading and
        speed, and flocks with the neighbours it is linked to, matching their mean speed (none:
        it just holds)."""
        hold_x, hold_y, speed = self.last.get(v.id, (v.ux, v.uy, v.airspeed))
        mates = [j for j in near if graph.linked(v.id, active[j].id)]
        if not mates:
            return Command(hold_x, hold_y, speed, altitude)
        total = 0.0
        for j in mates:
            total += active[j].airspeed
        speed = total / len(mates)
        align = boids.alignment(v.ux, v.uy, [(active[j].ux, active[j].uy) for j in mates])
        coh = boids.cohesion(
            v.x, v.y, [(active[j].x, active[j].y) for j in mates], self.group.spacing_m
        )
        hx, hy = boids.blend(v.ux, v.uy, align, sep, coh, (hold_x, hold_y), self.weights)
        nx, ny = self._noise(v.id, tick, hx, hy)
        return Command(nx, ny, speed, altitude)

    # ------------------------------------------------------------------ loiter after loss

    def _plan_loiter(self, active: Sequence[MemberView], cap: float, plan: Plan) -> None:
        assert self.centre is not None
        for v in active:
            want = orbit_direction(
                v.x, v.y, v.ux, v.uy, self.centre[0], self.centre[1], self.group.loiter_radius_m
            )
            plan.commands[v.id] = Command(want[0], want[1], cap, v.z)

    # ------------------------------------------------------------------ no leader

    def _plan_free(
        self, tick: int, wind: Vec, active: Sequence[MemberView], cap: float, plan: Plan
    ) -> None:
        if not self.guide_ready:
            cx, cy = self._centroid(active)
            sx = sy = 0.0
            for v in active:
                sx += v.ux
                sy += v.uy
            self.gx, self.gy = cx, cy
            self.gux, self.guy = detmath.unit(sx, sy)
            self.guide_ready = True
        slowest_turn = min(v.turn_rate for v in active)
        turn = min(0.5 * slowest_turn, GUIDE_TURN_DPS * detmath.DEG)
        speed = min(self.cursor_speed(), cap)
        reach = max(ARRIVAL_RADIUS_MIN_M, speed / turn)
        aim = intents.guide(self.params, self.route, self.cursor, self.gx, self.gy, reach)
        if self._route_events(aim, active, plan):
            return
        speed = min(aim.speed, cap)
        if aim.orbit > 0.0:
            want = orbit_direction(self.gx, self.gy, self.gux, self.guy, aim.x, aim.y, aim.orbit)
        else:
            want = detmath.unit(aim.x - self.gx, aim.y - self.gy)
        self.gux, self.guy = detmath.rotate_towards(
            (self.gux, self.guy), want, detmath.cos(turn * DT), detmath.sin(turn * DT)
        )
        cx, cy = self._centroid(active)
        leash = 2.0 * self.group.spacing_m * math.sqrt(len(active)) + 50.0
        if links.distance(cx, cy, self.gx, self.gy) <= leash:
            self.gx += self.gux * speed * DT
            self.gy += self.guy * speed * DT
        if self.params.intent == "saturation":
            self._plan_lanes(tick, wind, active, cap, speed, aim.z, plan)
        else:
            self._plan_flock(tick, active, speed, aim.z, plan)

    def cursor_speed(self) -> float:
        """The route speed at the cursor, before the group's cap."""
        return self.route[min(self.cursor.leg, len(self.route) - 1)][3]

    def _plan_flock(
        self, tick: int, active: Sequence[MemberView], speed: float, altitude: float, plan: Plan
    ) -> None:
        graph = self.graph()
        near = self._neighbourhoods(active)
        # inside the group's own extent the goal is the guide's heading, not a pull to its centre
        extent = 1.5 * self.group.spacing_m * math.sqrt(len(active))
        ramp = max(self.group.neighbour_radius_m, extent)
        for i, v in enumerate(active):
            mates = [j for j in near[i] if graph.linked(v.id, active[j].id)]
            sep = self._separation(active, near[i], i)
            align = boids.alignment(v.ux, v.uy, [(active[j].ux, active[j].uy) for j in mates])
            coh = boids.cohesion(
                v.x, v.y, [(active[j].x, active[j].y) for j in mates], self.group.spacing_m
            )
            aim = boids.goal(v.x, v.y, self.gx, self.gy, self.gux, self.guy, ramp)
            hx, hy = boids.blend(v.ux, v.uy, align, sep, coh, aim, self.weights)
            nx, ny = self._noise(v.id, tick, hx, hy)
            along = (self.gx - v.x) * self.gux + (self.gy - v.y) * self.guy
            wanted = detmath.clamp(speed + SPEED_GAIN_PER_S * along, 0.3 * speed, 1.5 * speed)
            plan.commands[v.id] = Command(nx, ny, wanted, altitude)

    def _plan_lanes(
        self,
        tick: int,
        wind: Vec,
        active: Sequence[MemberView],
        cap: float,
        speed: float,
        altitude: float,
        plan: Plan,
    ) -> None:
        """Saturation without a leader: parallel lanes across the guide's track, abreast."""
        ranked = sorted(v.id for v in active)
        near = self._neighbourhoods(active)
        sep_speed = SEPARATION_SPEED_SHARE * cap
        gvx, gvy = self.gux * speed - wind[0], self.guy * speed - wind[1]
        for i, v in enumerate(active):
            off = leaderfollower.lane_offset(
                ranked.index(v.id), len(ranked), self.group.lane_spacing_m
            )
            sx, sy = leaderfollower.to_world(self.gx, self.gy, self.gux, self.guy, (0.0, off))
            sep = self._separation(active, near[i], i)
            vx, vy = leaderfollower.follow(
                v.x, v.y, sx, sy, gvx, gvy, sep, sep_speed, CORRECTION_SHARE * cap
            )
            (hx, hy), spd = leaderfollower.heading_and_speed(vx, vy, (self.gux, self.guy))
            nx, ny = self._noise(v.id, tick, hx, hy)
            plan.commands[v.id] = Command(nx, ny, spd, altitude)

    # ------------------------------------------------------------------ shared helpers

    def _route_events(self, aim: intents.Aim, active: Sequence[MemberView], plan: Plan) -> bool:
        """Report the end of the route; True when the members leave and need no command."""
        if aim.ended:
            plan.events.append(
                ("group.route_end", {"group": self.group.id, "then": self.group.on_route_end})
            )
        if aim.despawn:
            plan.despawn = [v.id for v in active]
        return aim.despawn

    def _neighbourhoods(self, active: Sequence[MemberView]) -> list[list[int]]:
        """For each member, the indices of the others within the neighbour radius."""
        limit = self.group.neighbour_radius_m * self.group.neighbour_radius_m
        near: list[list[int]] = [[] for _ in active]
        for i in range(len(active)):
            for j in range(i + 1, len(active)):
                dx, dy = active[i].x - active[j].x, active[i].y - active[j].y
                if dx * dx + dy * dy <= limit:
                    near[i].append(j)
                    near[j].append(i)
        for entry in near:
            entry.sort()
        return near

    def _separation(self, active: Sequence[MemberView], near: Sequence[int], i: int) -> Vec:
        me = active[i]
        others = [(active[j].x, active[j].y, 1.0 if me.id < active[j].id else -1.0) for j in near]
        return boids.separation(me.x, me.y, me.ux, me.uy, others, self.group.spacing_m)

    def _noise(self, member: str, tick: int, hx: float, hy: float) -> Vec:
        """Vicsek noise on a desired heading. The draw is keyed on the member and the noise
        epoch (one second), so it costs one hash draw per member per second."""
        if self.group.discipline >= 1.0:
            return hx, hy
        epoch = tick // NOISE_HOLD_TICKS
        held = self._xi.get(member)
        if held is None or held[0] != epoch:
            held = (epoch, self.draws.signed(member, epoch, "noise"))
            self._xi[member] = held
        xi = held[1]
        return boids.noise_rotate(hx, hy, self.group.discipline, xi)
