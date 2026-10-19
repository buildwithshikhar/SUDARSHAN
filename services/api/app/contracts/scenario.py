"""Scenario specification, contract `scenario.v1`.

Threat behaviour is kinematics only: a route of waypoints flown inside class limits. There is no
guidance, terminal or targeting logic, and the contract has no field that could carry one.
"""

from typing import Annotated, Literal, Self

from pydantic import Field, FiniteFloat, model_validator

from .common import Contract, Heading, PackRef, Seed, SemVer, Slug, Text, Vec3, unique

TICK_HZ: Literal[20] = 20


class FlatTerrain(Contract):
    kind: Literal["flat"]
    elevation_m: FiniteFloat = 0.0


class PackTerrain(Contract):
    """A baked terrain pack (`packs/terrain/<id>/`, docs/TERRAIN_PACKS.md). Positions in the
    scenario are metres above the pack datum, in the pack's local frame."""

    kind: Literal["pack"]
    id: Slug
    version: SemVer


Terrain = Annotated[FlatTerrain | PackTerrain, Field(discriminator="kind")]


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


class Tether(Contract):
    """Clutter motion: a kite held on a line from a fixed anchor. It rides downwind of the anchor
    at about 50 degrees elevation, swaying across the wind; the route is ignored."""

    kind: Literal["tether"]
    anchor: Vec3
    length_m: Annotated[float, Field(ge=5, le=300)]
    sway_m: Annotated[float, Field(ge=0, le=100)]
    sway_period_s: Annotated[float, Field(ge=2, le=60)]


class Drift(Contract):
    """Clutter motion: a free balloon carried by the wind (mean wind plus gust), climbing at
    `climb_mps` until the top of its altitude band; the route is ignored."""

    kind: Literal["drift"]
    climb_mps: Annotated[float, Field(ge=0, le=3)]


Motion = Annotated[Tether | Drift, Field(discriminator="kind")]

#: Sine of the elevation (50 degrees) at which a tethered kite rides above its anchor.
TETHER_SIN_ELEVATION = 0.766044443118978

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
    #: Prescribed clutter motion (kite on a tether, drifting balloon). A threat with a motion
    #: ignores its `route` but still obeys its class altitude band.
    motion: Motion | None = None

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
        if isinstance(self.motion, Tether):
            height = self.motion.anchor.z + self.motion.length_m * TETHER_SIN_ELEVATION
            if not lim.min_altitude_m <= height <= lim.max_altitude_m:
                raise ValueError(
                    f"threat {self.id}: the tethered flying height ({height:.1f} m) is outside "
                    "the class band"
                )
        return self


Intent = Literal["transit", "loiter", "probe", "saturation"]


class GroupWeights(Contract):
    """Weights of the four flocking terms (Reynolds boids). Project-authored (register F01,
    verified: false)."""

    separation: Annotated[float, Field(ge=0, le=5)] = 1.0
    alignment: Annotated[float, Field(ge=0, le=5)] = 1.5
    cohesion: Annotated[float, Field(ge=0, le=5)] = 0.6
    goal: Annotated[float, Field(ge=0, le=5)] = 1.0


class Group(Contract):
    """Members of a group are ordinary threats (own class, limits, spawn and start); the group
    decides where they steer, and each member stays inside its own class envelope. Behaviour is
    kinematics only: a member goes where the group's own route and its group-mates take it.

    Every numeric value is project-authored (register F01, verified: false); the model basis is
    Reynolds boids, Vicsek noise, consensus with link loss and leader-follower, cited as the model
    and never as validation (docs/02-research.md section 3).
    """

    id: Slug
    kind: Literal["swarm", "flock"] = "swarm"
    members: Annotated[list[Slug], Field(min_length=2, max_length=64)]
    topology: Literal["leader-follower", "leaderless"] = "leaderless"
    #: Required with `leader-follower`, refused otherwise.
    leader: Slug | None = None
    intent: Intent = "transit"
    #: The group's guide path, in the scenario's local metres.
    route: Annotated[list[Waypoint], Field(min_length=1, max_length=200)]
    on_route_end: Literal["loiter", "loop", "despawn"] = "loiter"
    #: 1 = perfectly ordered, 0 = disordered (the Vicsek noise knob).
    discipline: Annotated[float, Field(ge=0, le=1)] = 0.9
    #: Desired distance between neighbours.
    spacing_m: Annotated[float, Field(ge=3, le=200)] = 20.0
    #: How far a member looks for neighbours to align with and stay close to.
    neighbour_radius_m: Annotated[float, Field(ge=5, le=1000)] = 80.0
    #: Pairs closer than this share a communication link.
    link_range_m: Annotated[float, Field(ge=10, le=5000)] = 150.0
    #: Probability that a link is down during one link epoch.
    link_loss: Annotated[float, Field(ge=0, le=1)] = 0.0
    link_epoch_s: Annotated[float, Field(ge=0.5, le=60)] = 1.0
    leader_loss: Literal["elect", "disperse", "loiter"] = "elect"
    leader_loss_hold_s: Annotated[float, Field(ge=0, le=30)] = 4.0
    probe_standoff_m: Annotated[float, Field(ge=10, le=5000)] = 200.0
    probe_cycles: Annotated[int, Field(ge=1, le=10)] = 2
    lane_spacing_m: Annotated[float, Field(ge=3, le=200)] = 30.0
    loiter_radius_m: Annotated[float, Field(ge=20, le=5000)] = 120.0
    weights: GroupWeights = Field(default_factory=GroupWeights)

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        unique(self.members, f"group {self.id} member")
        if self.topology == "leader-follower":
            if self.leader is None:
                raise ValueError(f"group {self.id}: a leader-follower group needs a leader")
            if self.leader not in self.members:
                raise ValueError(f"group {self.id}: the leader must be one of the members")
        elif self.leader is not None:
            raise ValueError(f"group {self.id}: a leaderless group has no leader")
        if self.neighbour_radius_m < self.spacing_m:
            raise ValueError(f"group {self.id}: neighbour_radius_m must be at least spacing_m")
        if any(w.hold_s > 0 for w in self.route):
            raise ValueError(f"group {self.id}: a group route cannot hold at a waypoint")
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


DEGRADATION_KINDS = (
    "outage",
    "sector-outage",
    "clutter",
    "haze",
    "glare",
    "interference",
    "wind-noise",
)


class SensorDegradation(Contract):
    """A time-limited condition that makes one of the scenario's sensors worse (docs/SIM_CORE.md,
    "Sensor framework"): the same data an instructor inject carries (wave 10b)."""

    sensor: Slug
    kind: Literal[
        "outage", "sector-outage", "clutter", "haze", "glare", "interference", "wind-noise"
    ]
    from_s: Annotated[float, Field(ge=0)]
    #: When it ends; absent means it lasts to the end of the scenario.
    to_s: Annotated[float, Field(gt=0)] | None = None
    #: 0 (no effect) to 1 (worst the sensor model represents). `outage` kinds ignore it.
    severity: Annotated[float, Field(ge=0, le=1)] = 1.0
    #: Clockwise sector blocked by `sector-outage`, compass degrees.
    sector_from_deg: Heading | None = None
    sector_to_deg: Heading | None = None

    @model_validator(mode="after")
    def _window(self) -> Self:
        if self.to_s is not None and self.to_s <= self.from_s:
            raise ValueError(f"degradation on {self.sensor}: the window must end after it starts")
        has_sector = self.sector_from_deg is not None and self.sector_to_deg is not None
        if (self.sector_from_deg is None) != (self.sector_to_deg is None):
            raise ValueError(f"degradation on {self.sensor}: a sector needs both ends")
        if (self.kind == "sector-outage") != has_sector:
            raise ValueError(
                f"degradation on {self.sensor}: a sector is required for sector-outage and only "
                "for sector-outage"
            )
        return self


class GeneratedFrom(Contract):
    """Where a generated scenario came from: enough to make it again (docs/SCENARIO_ENGINE.md)."""

    generator_version: SemVer
    #: The seed-share code carrying the request and the seed.
    code: Annotated[str, Field(min_length=8, max_length=96, pattern=r"^[A-Z0-9-]+$")]


class ScenarioMeta(Contract):
    """What the scenario library shows and filters on. Optional, and never read by the sim."""

    origin: Literal["scripted", "generated", "authored", "example"] = "scripted"
    #: False hides the scenario from the session lobby (it stays in the library).
    playable: bool = True
    tags: Annotated[list[Slug], Field(max_length=12)] = []
    #: Position in the curriculum, from 1; absent for a scenario outside the curriculum.
    curriculum_order: Annotated[int, Field(ge=1, le=999)] | None = None
    #: A rough 0 to 100 difficulty for the library; the generator fills it from its request.
    difficulty: Annotated[int, Field(ge=0, le=100)] | None = None
    generated: GeneratedFrom | None = None


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
    groups: Annotated[list[Group], Field(max_length=32)] = []
    degradations: Annotated[list[SensorDegradation], Field(max_length=64)] = []
    meta: ScenarioMeta | None = None

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
        for t in self.threats:
            if isinstance(t.motion, Tether) and (
                abs(t.motion.anchor.x) > h or abs(t.motion.anchor.y) > h
            ):
                raise ValueError(f"threat {t.id}: tether anchor outside the play area")
        self._check_groups()
        sensors = {s.id for s in self.sensors}
        for d in self.degradations:
            if d.sensor not in sensors:
                raise ValueError(f"degradation: no sensor {d.sensor!r} in this scenario")
            if d.from_s >= self.duration_s:
                raise ValueError(f"degradation on {d.sensor}: starts after the scenario ends")
        return self

    def _check_groups(self) -> None:
        unique([g.id for g in self.groups], "group")
        by_id = {t.id: t for t in self.threats}
        h = self.world.half_extent_m
        claimed: dict[str, str] = {}
        for g in self.groups:
            for m in g.members:
                if m not in by_id:
                    raise ValueError(f"group {g.id}: member {m} is not a threat")
                if m in claimed:
                    raise ValueError(f"threat {m} is in groups {claimed[m]} and {g.id}")
                claimed[m] = g.id
                member = by_id[m]
                if member.motion is not None:
                    raise ValueError(f"group {g.id}: member {m} has its own motion")
                if (member.disposition == "clutter") != (g.kind == "flock"):
                    raise ValueError(
                        f"group {g.id}: a {g.kind} is made of "
                        f"{'clutter' if g.kind == 'flock' else 'non-clutter'} threats"
                    )
            low = max(by_id[m].limits.min_altitude_m for m in g.members)
            high = min(by_id[m].limits.max_altitude_m for m in g.members)
            for i, w in enumerate(g.route):
                if abs(w.position.x) > h or abs(w.position.y) > h:
                    raise ValueError(f"group {g.id}: route waypoint {i} leaves the play area")
                if not low <= w.position.z <= high:
                    raise ValueError(
                        f"group {g.id}: route waypoint {i} altitude is outside the band "
                        "every member can fly"
                    )
