"""Scenario specification, contract `scenario.v1`.

Threat behaviour is kinematics only: a route of waypoints flown inside class limits. There is no
guidance, terminal or targeting logic, and the contract has no field that could carry one.
"""

from typing import Annotated, Literal, Self

from pydantic import Field, FiniteFloat, model_validator

from .common import Contract, Heading, PackRef, Seed, SemVer, Slug, Text, Vec3, unique

TICK_HZ: Literal[20] = 20


class Terrain(Contract):
    kind: Literal["flat"]
    elevation_m: FiniteFloat = 0.0


class Weather(Contract):
    """Modelled weather at session start. Wind blows from `wind_from_deg` (0 = north)."""

    condition: Literal["clear", "haze", "rain", "fog", "dust"]
    visibility_m: Annotated[float, Field(gt=0, le=100_000)]
    wind_speed_mps: Annotated[float, Field(ge=0, le=40)]
    wind_from_deg: Heading
    gust_sigma_mps: Annotated[float, Field(ge=0, le=10)]
    temperature_c: Annotated[float, Field(ge=-40, le=55)]
    cloud_cover_pct: Annotated[float, Field(ge=0, le=100)]


class World(Contract):
    terrain: Terrain
    #: Half-width of the square play area centred on the origin, in metres.
    half_extent_m: Annotated[float, Field(gt=0, le=50_000)]
    start_time_of_day_h: Annotated[float, Field(ge=0, lt=24)]
    weather: Weather


class KinematicLimits(Contract):
    """Envelope of a threat class. Airspeed, not ground speed, is limited."""

    max_speed_mps: Annotated[float, Field(gt=0, le=120)]
    max_accel_mps2: Annotated[float, Field(gt=0, le=30)]
    max_climb_mps: Annotated[float, Field(gt=0, le=30)]
    max_descent_mps: Annotated[float, Field(gt=0, le=30)]
    max_turn_rate_dps: Annotated[float, Field(gt=0, le=360)]
    min_altitude_m: Annotated[float, Field(ge=0, le=10_000)]
    max_altitude_m: Annotated[float, Field(gt=0, le=10_000)]

    @model_validator(mode="after")
    def _band(self) -> Self:
        if self.max_altitude_m <= self.min_altitude_m:
            raise ValueError("max_altitude_m must be above min_altitude_m")
        return self


class Waypoint(Contract):
    position: Vec3
    speed_mps: Annotated[float, Field(gt=0, le=120)]
    hold_s: Annotated[float, Field(ge=0, le=3600)] = 0.0


#: What a contact really is. Ground truth: never sent to a trainee during a session; scoring
#: (wave 6) and the instructor use it.
Disposition = Literal["hostile", "civil-permitted", "clutter"]


class Threat(Contract):
    id: Slug
    class_id: Slug
    #: Defaults to hostile so a scenario written before this field existed reads as before.
    disposition: Disposition = "hostile"
    label: Text
    spawn_s: Annotated[float, Field(ge=0)]
    start: Vec3
    start_heading_deg: Heading
    start_speed_mps: Annotated[float, Field(ge=0, le=120)]
    limits: KinematicLimits
    route: Annotated[list[Waypoint], Field(min_length=1, max_length=200)]
    on_route_end: Literal["loiter", "loop", "despawn"]

    @model_validator(mode="after")
    def _inside_limits(self) -> Self:
        lim = self.limits
        if self.start_speed_mps > lim.max_speed_mps:
            raise ValueError(f"threat {self.id}: start speed above class max speed")
        points = [("start", self.start)] + [
            (f"waypoint {i}", w.position) for i, w in enumerate(self.route)
        ]
        for name, p in points:
            if not lim.min_altitude_m <= p.z <= lim.max_altitude_m:
                raise ValueError(f"threat {self.id}: {name} altitude outside the class band")
        for i, w in enumerate(self.route):
            if w.speed_mps > lim.max_speed_mps:
                raise ValueError(f"threat {self.id}: waypoint {i} speed above class max speed")
        return self


class Zone(Contract):
    """Circular zone on the ground plane around a centre point."""

    id: Slug
    role: Literal["inner", "outer", "restricted"]
    label: Text
    center: Vec3
    radius_m: Annotated[float, Field(gt=0, le=50_000)]


class DefendedAsset(Contract):
    id: Slug
    label: Text
    position: Vec3


class FiledFlight(Contract):
    """A civil flight plan the trainee is told about: an area and a time window, nothing more.

    It does not name the contact that flies it; matching a track to a plan is the trainee's job.
    """

    id: Slug
    label: Text
    from_s: Annotated[float, Field(ge=0)]
    to_s: Annotated[float, Field(gt=0)]
    center: Vec3
    radius_m: Annotated[float, Field(gt=0, le=50_000)]

    @model_validator(mode="after")
    def _window(self) -> Self:
        if self.to_s <= self.from_s:
            raise ValueError(f"filed flight {self.id}: the window must end after it starts")
        return self


class SensorPlacement(Contract):
    id: Slug
    profile: PackRef
    position: Vec3
    boresight_deg: Heading


class ScenarioSpec(Contract):
    contract: Literal["scenario.v1"]
    id: Slug
    version: SemVer
    title: Text
    summary: Text
    fictional: Literal[True]
    tick_hz: Literal[20] = TICK_HZ
    default_seed: Seed
    duration_s: Annotated[float, Field(gt=0, le=7200)]
    world: World
    rule_pack: PackRef
    zones: Annotated[list[Zone], Field(max_length=32)] = []
    assets: Annotated[list[DefendedAsset], Field(max_length=32)] = []
    sensors: Annotated[list[SensorPlacement], Field(max_length=32)] = []
    filed_flights: Annotated[list[FiledFlight], Field(max_length=32)] = []
    threats: Annotated[list[Threat], Field(min_length=1, max_length=256)]

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        unique([z.id for z in self.zones], "zone")
        unique([a.id for a in self.assets], "asset")
        unique([s.id for s in self.sensors], "sensor")
        unique([f.id for f in self.filed_flights], "filed flight")
        unique([t.id for t in self.threats], "threat")
        h = self.world.half_extent_m
        for t in self.threats:
            if t.spawn_s >= self.duration_s:
                raise ValueError(f"threat {t.id}: spawns after the scenario ends")
            for p in [t.start, *(w.position for w in t.route)]:
                if abs(p.x) > h or abs(p.y) > h:
                    raise ValueError(f"threat {t.id}: route leaves the play area")
        for p in [*(a.position for a in self.assets), *(s.position for s in self.sensors)]:
            if abs(p.x) > h or abs(p.y) > h:
                raise ValueError("asset or sensor outside the play area")
        return self
