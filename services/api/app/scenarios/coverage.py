"""Which sensors can see a threat, and from when: the planning view of coverage.

For each point of a threat's route (`routes.sample_route`) a sensor is said to cover it when the
point is inside the sensor's field of view and elevation limits and its model's own probability of
detection is at least one half, with the scenario's weather and time of day. Terrain and buildings
are tested with the sim's own line-of-sight check. The model is the one the sim uses, so the numbers
are the profile's, not a second opinion. It ignores noise, false alarms and degradations: it
says where detection is likely, and the oracle run is what decides whether a scenario is solvable.
"""

from dataclasses import dataclass

from app.contracts.scenario import ScenarioSpec, Threat
from sim.sensors import Draws, build_sensors
from sim.sensors.base import Observation, Sensor
from sim.sensors.degradation import Effects
from sim.sensors.geometry import Environment, Geometry, Truth, daylight_at
from sim.terrain import Terrain, terrain_for

from .routes import RoutePoint, sample_route

#: A point counts as covered at this probability of detection or better.
COVER_PD = 0.5
_NO_NOISE = Draws(0.5, 0.5, (0.0, 0.0, 0.0, 0.0))


@dataclass(frozen=True, slots=True)
class Coverage:
    """When and by which sensors a threat is likely detectable."""

    #: Scenario time of the first covered point; `None` if no sensor ever covers it.
    first_s: float | None
    last_s: float | None
    sensors: tuple[str, ...]


def environment(spec: ScenarioSpec, t: float) -> Environment:
    w = spec.world.weather
    hour = (spec.world.start_time_of_day_h + t / 3600.0) % 24.0
    return Environment(
        condition=w.condition,
        visibility_m=w.visibility_m,
        wind_speed_mps=w.wind_speed_mps,
        temperature_c=w.temperature_c,
        cloud_cover_pct=w.cloud_cover_pct,
        time_of_day_h=hour,
        daylight=daylight_at(hour),
    )


def covers(
    sensor: Sensor, spec: ScenarioSpec, threat: Threat, p: RoutePoint, terrain: Terrain | None
) -> bool:
    truth = Truth("plan", threat.class_id, p.x, p.y, p.z, p.vx, p.vy, p.vz)
    geometry = Geometry.between(sensor.position, truth)
    if not sensor.in_coverage(geometry, Effects()):
        return False
    obs = Observation(0, truth, geometry, environment(spec, p.t), Effects(), _NO_NOISE)
    if sensor.p_detect(obs) < COVER_PD:
        return False
    if terrain is not None and sensor.needs_line_of_sight:
        s = sensor.position
        if terrain.blocked((s.x, s.y, s.z), (p.x, p.y, p.z)):
            return False
    return True


def coverage_of(
    spec: ScenarioSpec, threat: Threat, sensors: list[Sensor] | None = None
) -> Coverage:
    """Coverage of one threat over its route and, if it loiters, until the scenario ends."""
    live = build_sensors(spec).sensors if sensors is None else sensors
    terrain = terrain_for(spec.world.terrain)
    first = last = None
    seen: set[str] = set()
    for p in sample_route(threat, 1.0, spec.duration_s):
        if p.t >= spec.duration_s:
            break
        hit = [s.id for s in live if covers(s, spec, threat, p, terrain)]
        if hit:
            first = p.t if first is None else first
            last = p.t
            seen.update(hit)
    return Coverage(first, last, tuple(sorted(seen)))
