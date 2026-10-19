"""The scenario linter: domain checks a valid `scenario.v1` document can still fail.

The contract says a scenario is well formed; the linter says whether it can be played well: a
hostile contact must be seen and must leave the trainee time to answer, the rules of engagement
must be able to permit an engagement in a zone the scenario has, and routes must stay where the
class and the terrain allow. Each finding has a stable `code`, a severity, the line and column of
the offending node (when the text's `LineMap` is given) and the numbers behind it in `params`.

It runs as a hard constraint inside the generator, so it is built to be fast: one sensor suite is
built once and shared by every coverage query. Planning estimates (`routes`, `coverage`) are used,
not the simulation, so a clean lint is not a promise: the oracle run decides solvability.
"""

import math
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Literal

from app.contracts.rulepack import RulePack
from app.contracts.scenario import Group, ScenarioSpec, Threat
from sim.catalogue import Catalogue, load_catalogue
from sim.roe import load_rule_engine
from sim.sensors import build_sensors
from sim.sensors.base import Sensor
from sim.terrain import Terrain, terrain_for

from .coverage import coverage_of
from .language import LineMap
from .routes import route_end_s, sample_route

Severity = Literal["error", "warning"]

#: Every code the linter can report, with its severity (kept in step with the table in
#: docs/SCENARIO_ENGINE.md by a test).
LINT_CODES: dict[str, Severity] = {
    "timing.reaction-window": "error",
    "coverage.none": "error",
    "coverage.late": "warning",
    "roe.no-engage-rule": "error",
    "roe.zone-missing": "warning",
    "roe.pack-missing": "error",
    "route.leaves-area": "error",
    "route.below-envelope": "error",
    "route.above-envelope": "error",
    "route.speed": "error",
    "route.unreachable": "error",
    "route.underground": "error",
    "catalogue.limits": "error",
    "group.link-range": "warning",
    "sensor.profile": "error",
    "world.terrain-missing": "error",
}

Path = tuple[str | int, ...]


@dataclass(frozen=True, slots=True)
class LintItem:
    code: str
    severity: Severity
    #: 1-based position of the offending node in the YAML text; 0 when no text was given.
    line: int
    column: int
    #: Plain English; the web app renders `code` and `params` through its own catalogue.
    message: str
    params: dict[str, object]


@lru_cache(maxsize=1)
def _default_catalogue() -> Catalogue:
    return load_catalogue()


class _Linter:
    def __init__(self, spec: ScenarioSpec, lines: LineMap | None, catalogue: Catalogue) -> None:
        self.spec = spec
        self.lines = lines
        self.catalogue = catalogue
        self.items: list[LintItem] = []

    # ------------------------------------------------------------------------------ helpers
    def add(self, code: str, path: Path, message: str, **params: object) -> None:
        line, column = (0, 0) if self.lines is None else self.lines.lookup(path)
        self.items.append(LintItem(code, LINT_CODES[code], line, column, message, params))

    def hostile(self) -> list[tuple[int, Threat]]:
        return [(i, t) for i, t in enumerate(self.spec.threats) if t.disposition == "hostile"]

    # ------------------------------------------------------------------------------- runner
    def run(self) -> list[LintItem]:
        pack = self.rules()
        if pack is not None:
            self.zones(pack)
        terrain, terrain_ok = self.terrain()
        suite = self.sensors() if terrain_ok else None
        self.routes(terrain)
        self.catalogue_limits()
        self.groups()
        if suite is not None:
            self.coverage_and_timing(suite, pack)
        return sorted(self.items, key=lambda item: (item.line, item.code))

    # ----------------------------------------------------------------------------- the world
    def terrain(self) -> tuple[Terrain | None, bool]:
        try:
            return terrain_for(self.spec.world.terrain), True
        except Exception as error:  # noqa: BLE001 - any unreadable pack is a finding, not a crash
            self.add(
                "world.terrain-missing",
                ("world", "terrain"),
                f"the terrain pack cannot be loaded: {error}",
            )
            return None, False

    def sensors(self) -> list[Sensor] | None:
        """The sensors, built once; `None` (and a finding for each one that fails) if they fail."""
        try:
            return build_sensors(self.spec).sensors
        except Exception:  # noqa: BLE001 - find which placement fails
            self.explain_sensor_failure()
            return None

    def explain_sensor_failure(self) -> None:
        failed = False
        for i, placement in enumerate(self.spec.sensors):
            alone = self.spec.model_copy(update={"sensors": [placement], "degradations": []})
            try:
                build_sensors(alone)
            except Exception as error:  # noqa: BLE001
                failed = True
                self.add(
                    "sensor.profile",
                    ("sensors", i, "profile"),
                    f"sensor {placement.id}: its profile cannot be used ({error})",
                    sensor=placement.id,
                    profile=f"{placement.profile.id} {placement.profile.version}",
                )
        if not failed:
            self.add("sensor.profile", ("sensors",), "the sensors cannot be built together")

    # ----------------------------------------------------------------------- rules of engagement
    def rules(self) -> RulePack | None:
        try:
            return load_rule_engine(self.spec).pack
        except Exception as error:  # noqa: BLE001
            ref = self.spec.rule_pack
            self.add(
                "roe.pack-missing",
                ("rule_pack",),
                f"rule pack {ref.id} {ref.version} cannot be loaded ({error})",
                pack=ref.id,
                version=ref.version,
            )
            return None

    def zones(self, pack: RulePack) -> None:
        roles = {z.role for z in self.spec.zones}
        engage = [r for r in pack.rules if "engage" in r.permits]
        usable = [
            r
            for r in engage
            if r.when.zone_role_in is None or roles.intersection(r.when.zone_role_in)
        ]
        where: Path = ("rule_pack",)
        if not usable:
            self.add(
                "roe.no-engage-rule",
                where,
                f"no rule of {pack.id} permits an engagement in a zone this scenario defines"
                + (f" (it has {', '.join(sorted(roles))} zones)" if roles else " (it has no zone)"),
                pack=pack.id,
                zone_roles=sorted(roles),
            )
        zones_at: Path = ("zones",) if self.spec.zones else where
        for rule in pack.rules:
            for role in rule.when.zone_role_in or []:
                if role not in roles:
                    self.add(
                        "roe.zone-missing",
                        zones_at,
                        f"rule {rule.id} names the {role} zone and this scenario has none",
                        rule=rule.id,
                        zone_role=role,
                    )

    # ------------------------------------------------------------------------------- routes
    def routes(self, terrain: Terrain | None) -> None:
        half = self.spec.world.half_extent_m
        for i, threat in enumerate(self.spec.threats):
            if threat.motion is not None:
                continue
            low, high, fastest = self.envelope(threat)
            for j, w in enumerate(threat.route):
                at: Path = ("threats", i, "route", j)
                p = w.position
                if abs(p.x) > half or abs(p.y) > half:
                    self.add(
                        "route.leaves-area",
                        (*at, "position"),
                        f"threat {threat.id}: waypoint {j} is outside the play area "
                        f"(half extent {half:g} m)",
                        threat=threat.id,
                        waypoint=j,
                        half_extent_m=half,
                    )
                if p.z < low:
                    self.add(
                        "route.below-envelope",
                        (*at, "position", "z"),
                        f"threat {threat.id}: waypoint {j} is at {p.z:g} m, below the "
                        f"{low:g} m the class may fly",
                        threat=threat.id,
                        waypoint=j,
                        z_m=p.z,
                        minimum_m=low,
                    )
                if p.z > high:
                    self.add(
                        "route.above-envelope",
                        (*at, "position", "z"),
                        f"threat {threat.id}: waypoint {j} is at {p.z:g} m, above the "
                        f"{high:g} m the class may fly",
                        threat=threat.id,
                        waypoint=j,
                        z_m=p.z,
                        maximum_m=high,
                    )
                if w.speed_mps > fastest:
                    self.add(
                        "route.speed",
                        (*at, "speed_mps"),
                        f"threat {threat.id}: waypoint {j} asks {w.speed_mps:g} m/s, above the "
                        f"{fastest:g} m/s the class may fly",
                        threat=threat.id,
                        waypoint=j,
                        speed_mps=w.speed_mps,
                        maximum_mps=fastest,
                    )
                if terrain is not None:
                    ground = terrain.ground_m(p.x, p.y)
                    if p.z < ground:
                        self.add(
                            "route.underground",
                            (*at, "position", "z"),
                            f"threat {threat.id}: waypoint {j} is at {p.z:g} m, below the "
                            f"ground ({ground:.1f} m) there",
                            threat=threat.id,
                            waypoint=j,
                            z_m=p.z,
                            ground_m=round(ground, 1),
                        )
            end = route_end_s(threat)
            must_finish = threat.disposition == "hostile" and threat.on_route_end != "loop"
            if must_finish and end > self.spec.duration_s:
                self.add(
                    "route.unreachable",
                    ("threats", i, "route"),
                    f"threat {threat.id}: its route ends at {end:.0f} s, after the "
                    f"scenario ({self.spec.duration_s:g} s)",
                    threat=threat.id,
                    route_end_s=round(end, 1),
                    duration_s=self.spec.duration_s,
                )

    def envelope(self, threat: Threat) -> tuple[float, float, float]:
        """Lowest and highest altitude and top speed: the narrower of the threat's own limits and
        its catalogue class's."""
        own = threat.limits
        low, high, fastest = own.min_altitude_m, own.max_altitude_m, own.max_speed_mps
        if threat.class_id in self.catalogue:
            cls = self.catalogue.limits_for(threat.class_id)
            low = max(low, cls.min_altitude_m)
            high = min(high, cls.max_altitude_m)
            fastest = min(fastest, cls.max_speed_mps)
        return low, high, fastest

    # ----------------------------------------------------------------------------- catalogue
    def catalogue_limits(self) -> None:
        ids = [t.id for t in self.spec.threats]
        for problem in self.catalogue.check_scenario(self.spec):
            named = re.match(r"threat ([a-z0-9-]+):", problem)
            index = ids.index(named.group(1)) if named and named.group(1) in ids else None
            path: Path = ("threats",) if index is None else ("threats", index)
            self.add(
                "catalogue.limits",
                path,
                problem,
                threat=None if index is None else ids[index],
            )

    # ------------------------------------------------------------------------------- groups
    def groups(self) -> None:
        by_id = {t.id: t for t in self.spec.threats}
        for k, group in enumerate(self.spec.groups):
            need = self.formation_span(group, by_id) + group.spacing_m
            if group.link_range_m < need:
                self.add(
                    "group.link-range",
                    ("groups", k, "link_range_m"),
                    f"group {group.id}: link range {group.link_range_m:g} m is less than the "
                    f"formation needs ({need:.0f} m); a follower out of range falls back to "
                    "flocking",
                    group=group.id,
                    link_range_m=group.link_range_m,
                    needed_m=round(need, 1),
                )

    @staticmethod
    def formation_span(group: Group, by_id: dict[str, Threat]) -> float:
        """Diameter of the circle about the members' centroid that holds all their start points."""
        points = [(by_id[m].start.x, by_id[m].start.y) for m in group.members if m in by_id]
        cx = sum(x for x, _ in points) / len(points)
        cy = sum(y for _, y in points) / len(points)
        return 2.0 * max(math.hypot(x - cx, y - cy) for x, y in points)

    # ------------------------------------------------------------------- coverage and timing
    def coverage_and_timing(self, sensors: list[Sensor], pack: RulePack | None) -> None:
        inner = min(
            (z for z in self.spec.zones if z.role == "inner"),
            key=lambda z: (z.radius_m, z.id),
            default=None,
        )
        duration = self.spec.duration_s
        for i, threat in self.hostile():
            first = coverage_of(self.spec, threat, sensors).first_s
            if first is None:
                self.add(
                    "coverage.none",
                    ("threats", i, "id"),
                    f"threat {threat.id}: no sensor covers it at any point of its route",
                    threat=threat.id,
                )
                continue
            if first > duration / 2:
                self.add(
                    "coverage.late",
                    ("threats", i, "id"),
                    f"threat {threat.id}: first covered at {first:.0f} s, after half the scenario",
                    threat=threat.id,
                    first_s=round(first, 1),
                    duration_s=duration,
                )
            if pack is None:
                continue
            minimum = pack.thresholds.respond_within_s
            entry = duration
            if inner is not None:
                for p in sample_route(threat, 1.0, duration):
                    if math.hypot(p.x - inner.center.x, p.y - inner.center.y) <= inner.radius_m:
                        entry = p.t
                        break
            window = entry - first
            if window < minimum:
                self.add(
                    "timing.reaction-window",
                    ("threats", i, "spawn_s"),
                    f"threat {threat.id}: {window:.0f} s from first coverage to the inner zone, "
                    f"less than the {minimum:g} s the rules allow to respond",
                    threat=threat.id,
                    window_s=round(window, 1),
                    minimum_s=minimum,
                )


def lint(
    spec: ScenarioSpec, lines: LineMap | None = None, catalogue: Catalogue | None = None
) -> list[LintItem]:
    """Every finding for a valid scenario, sorted by line then code.

    With `lines` (from `validate_text`) each item carries the 1-based line and column of the node
    it concerns; without it they are 0."""
    return _Linter(spec, lines, catalogue or _default_catalogue()).run()
