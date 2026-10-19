"""The generator's hard constraints, checked on a candidate before the oracle runs.

Cheap and geometric. A candidate that fails one is thrown away; none of them is ever relaxed
(docs/SCENARIO_ENGINE.md). The linter (`lint.py`) adds the domain checks on timing, coverage and
the rules of engagement.
"""

import math
from dataclasses import dataclass

from app.contracts.scenario import Group, ScenarioSpec
from sim.catalogue import Catalogue

from .routes import sample_route
from .sampler import ORBIT_M, STANDOFF_M


@dataclass(frozen=True, slots=True)
class Rejection:
    reason: str
    detail: str


def _site(spec: ScenarioSpec) -> tuple[float, float]:
    if spec.assets:
        return spec.assets[0].position.x, spec.assets[0].position.y
    return 0.0, 0.0


def _formation_radius(spec: ScenarioSpec, group: Group) -> float:
    """The farthest a member starts from the formation's centroid."""
    by_id = {t.id: t for t in spec.threats}
    xs = [by_id[m].start.x for m in group.members]
    ys = [by_id[m].start.y for m in group.members]
    cx, cy = sum(xs) / len(xs), sum(ys) / len(ys)
    return max(math.hypot(x - cx, y - cy) for x, y in zip(xs, ys, strict=True))


def standoff_m(spec: ScenarioSpec) -> float | None:
    """The smallest conservative distance between the defended place and any hostile contact on
    its authored route: the nearest route point, less the orbit it flies at the end of a loiter
    and, for a group, less the radius of its formation. `None` when no hostile contact flies."""
    sx, sy = _site(spec)
    by_id = {t.id: t for t in spec.threats}
    in_group = {m: g for g in spec.groups for m in g.members}
    nearest: list[float] = []
    done_groups: set[str] = set()
    for t in spec.threats:
        if t.disposition != "hostile":
            continue
        group = in_group.get(t.id)
        if group is None:
            points = sample_route(t, 5.0)
            reach = min(math.hypot(p.x - sx, p.y - sy) for p in points)
            if t.on_route_end == "loiter":
                reach -= ORBIT_M
            nearest.append(reach)
        elif group.id not in done_groups:
            done_groups.add(group.id)
            leader = by_id[group.leader or group.members[0]]
            guide = leader.model_copy(update={"route": list(group.route)})
            reach = min(math.hypot(p.x - sx, p.y - sy) for p in sample_route(guide, 5.0))
            if group.intent == "loiter":
                reach = math.hypot(group.route[0].position.x - sx, group.route[0].position.y - sy)
            nearest.append(reach - _formation_radius(spec, group) - group.loiter_radius_m)
    return min(nearest) if nearest else None


def link_range_problems(spec: ScenarioSpec) -> list[str]:
    """Groups whose `link_range_m` does not cover their formation: a follower out of range of the
    leader's component falls back to flocking (docs/SIM_CORE.md)."""
    out: list[str] = []
    for g in spec.groups:
        if g.topology != "leader-follower":
            continue
        need = 2.0 * _formation_radius(spec, g) + g.spacing_m
        if g.link_range_m < need:
            out.append(f"group {g.id}: link range {g.link_range_m:g} m is below {need:g} m")
    return out


def hard_constraints(spec: ScenarioSpec, catalogue: Catalogue) -> list[Rejection]:
    """Everything that makes a candidate unfit before it is run."""
    out = [Rejection("catalogue", p) for p in catalogue.check_scenario(spec)]
    reach = standoff_m(spec)
    if reach is not None and reach < STANDOFF_M:
        out.append(
            Rejection("standoff", f"a route comes within {reach:.0f} m of the defended place")
        )
    out += [Rejection("link-range", p) for p in link_range_problems(spec)]
    return out
