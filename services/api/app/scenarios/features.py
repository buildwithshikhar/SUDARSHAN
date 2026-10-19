"""A scenario's feature vector: eight axes, each 0 to 1, computed from the spec alone.

The same function describes a scripted, a generated and an authored scenario, so they can be
compared for diversity (`diversity.py`) and placed in the MAP-Elites archive (`archive.py`). The
axes are heuristics for "how different does this feel to play", not measures of difficulty for a
person (docs/SCENARIO_ENGINE.md).
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass

from app.contracts.scenario import ScenarioSpec, Threat
from sim.sensors import build_sensors
from sim.sensors.base import Sensor
from sim.terrain import terrain_for

from .coverage import coverage_of
from .routes import sample_route

AXES: tuple[str, ...] = (
    "threat_count",
    "id_ambiguity",
    "approach_speed",
    "bearing_spread",
    "clutter_density",
    "degradation_load",
    "timing_tightness",
    "stealth",
)
#: Hostile contacts at which `threat_count` reaches 1 (log scale).
COUNT_FULL = 24
#: Hostile cruise speed at which `approach_speed` reaches 1.
SPEED_FULL_MPS = 40.0
#: Clutter contacts at which `clutter_density` reaches 1.
CLUTTER_FULL = 20
#: Reaction window at which `timing_tightness` is 0.
WINDOW_FULL_S = 300.0
#: Below this height above the ground a contact counts as low-flying for `stealth`.
LOW_M = 40.0
SILENT_OR_FAINT = frozenset({"autonomous-small", "decoy-small"})


@dataclass(frozen=True, slots=True)
class Features:
    """The eight axes in `AXES` order."""

    values: tuple[float, ...]

    def __post_init__(self) -> None:
        if len(self.values) != len(AXES):
            raise ValueError(f"a feature vector has {len(AXES)} values")

    def as_dict(self) -> dict[str, float]:
        return dict(zip(AXES, self.values, strict=True))

    def __getitem__(self, axis: str) -> float:
        return self.values[AXES.index(axis)]

    @classmethod
    def from_dict(cls, data: dict[str, float]) -> "Features":
        return cls(tuple(float(data[a]) for a in AXES))


def _clip(x: float) -> float:
    return round(min(1.0, max(0.0, x)), 6)


def _group_speeds(spec: ScenarioSpec) -> dict[str, float]:
    """A group member flies its group's route, not its own, so its speed is the group's."""
    out: dict[str, float] = {}
    for g in spec.groups:
        speed = sum(w.speed_mps for w in g.route) / len(g.route)
        for m in g.members:
            out[m] = speed
    return out


def _mean_speed(threat: Threat, grouped: dict[str, float]) -> float:
    if threat.id in grouped:
        return min(grouped[threat.id], threat.limits.max_speed_mps)
    legs = [min(w.speed_mps, threat.limits.max_speed_mps) for w in threat.route]
    return sum(legs) / len(legs)


def _site(spec: ScenarioSpec) -> tuple[float, float]:
    if spec.assets:
        return spec.assets[0].position.x, spec.assets[0].position.y
    return 0.0, 0.0


def _spread(spec: ScenarioSpec, hostile: Sequence[Threat]) -> float:
    """One minus the length of the mean unit vector of the bearings the hostile contacts start
    on: 0 when they all come from one direction, towards 1 when they come from all round."""
    if len(hostile) < 2:
        return 0.0
    sx, sy = _site(spec)
    x = y = 0.0
    for t in hostile:
        dx, dy = t.start.x - sx, t.start.y - sy
        norm = math.hypot(dx, dy)
        if norm > 0.0:
            x, y = x + dx / norm, y + dy / norm
    return 1.0 - math.hypot(x, y) / len(hostile)


def _degradation(spec: ScenarioSpec) -> float:
    if not spec.degradations or not spec.sensors:
        return 0.0
    total = 0.0
    for d in spec.degradations:
        end = spec.duration_s if d.to_s is None else min(d.to_s, spec.duration_s)
        weight = 1.0 if d.kind in ("outage", "sector-outage") else d.severity
        total += max(end - d.from_s, 0.0) / spec.duration_s * weight
    return total / len(spec.sensors)


def reaction_windows(
    spec: ScenarioSpec, hostile: Sequence[Threat], sensors: list[Sensor] | None = None
) -> dict[str, float | None]:
    """Seconds from a hostile contact first being covered by a sensor to its first point inside the
    inner zone (to the scenario's end if it never enters one); `None` if never covered."""
    live = build_sensors(spec).sensors if sensors is None else sensors
    inner = sorted((z for z in spec.zones if z.role == "inner"), key=lambda z: z.radius_m)
    out: dict[str, float | None] = {}
    cache: dict[tuple[object, ...], float | None] = {}
    for threat in hostile:
        key = (
            threat.class_id,
            threat.spawn_s,
            (threat.start.x, threat.start.y, threat.start.z),
            tuple((w.position.x, w.position.y, w.position.z, w.speed_mps) for w in threat.route),
        )
        if key not in cache:
            first = coverage_of(spec, threat, live).first_s
            entry = spec.duration_s
            if inner:
                zone = inner[0]
                for p in sample_route(threat, 1.0, spec.duration_s):
                    if math.hypot(p.x - zone.center.x, p.y - zone.center.y) <= zone.radius_m:
                        entry = p.t
                        break
            cache[key] = None if first is None else entry - first
        out[threat.id] = cache[key]
    return out


def features_of(spec: ScenarioSpec) -> Features:
    """The scenario's eight axes."""
    hostile = [t for t in spec.threats if t.disposition == "hostile"]
    others = [t for t in spec.threats if t.disposition != "hostile"]
    grouped = _group_speeds(spec)
    decoys = [t for t in hostile if t.class_id == "decoy-small"]
    total = len(spec.threats)
    clutter = [t for t in spec.threats if t.disposition == "clutter"]
    terrain = terrain_for(spec.world.terrain)

    def faint(t: Threat) -> bool:
        if t.class_id in SILENT_OR_FAINT:
            return True
        ground = 0.0 if terrain is None else terrain.ground_m(t.start.x, t.start.y)
        return t.start.z - ground < LOW_M

    windows = [w for w in reaction_windows(spec, hostile).values() if w is not None]
    values = (
        _clip(math.log(1 + len(hostile)) / math.log(1 + COUNT_FULL)),
        _clip((len(others) + len(decoys)) / total if total else 0.0),
        _clip(
            sum(_mean_speed(t, grouped) for t in hostile) / len(hostile) / SPEED_FULL_MPS
            if hostile
            else 0.0
        ),
        _clip(_spread(spec, hostile)),
        _clip(len(clutter) / CLUTTER_FULL),
        _clip(_degradation(spec)),
        _clip(1.0 - min(windows) / WINDOW_FULL_S if windows else 1.0),
        _clip(sum(1 for t in hostile if faint(t)) / len(hostile) if hostile else 0.0),
    )
    return Features(values)
