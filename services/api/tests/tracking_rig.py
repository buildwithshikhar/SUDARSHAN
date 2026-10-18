"""A small rig for the tracking tests: drones, sensors, a world and a tracker wired together.

`scenario` builds a Kestrel-based spec with the threats you give it; `Rig` steps the world, runs
the sensors, feeds `Detection.trainee_view()` to the tracker as `Measurement`s and keeps the
ground-truth reference of every report on the side (`rig.truth`), the way the truth ledger gets it.
"""

from dataclasses import dataclass, field
from typing import Any

from app.contracts import ScenarioSpec
from app.contracts.common import PackRef, Quantity, Vec3
from app.contracts.scenario import SensorPlacement
from sim.rng import RngStreams
from sim.sensors import MODELS, Sensor, SensorParams, SensorSuite, default_profile_dir
from sim.sensors.profile import load_sensor_profile
from sim.tracking import AmbiguityPolicy, Measurement, Tracker, TrackerConfig, UpdateResult
from sim.world import World

from .sim_cases import kestrel


def drone(
    ident: str,
    class_id: str,
    start: tuple[float, float, float],
    heading_deg: float,
    speed: float,
    route: list[tuple[float, float, float]],
    *,
    spawn_s: float = 0.0,
) -> dict[str, Any]:
    """A threat with the Kestrel rotary limits flying a straight scripted route."""
    base = kestrel().threats[0].model_dump(mode="json")
    base.update(
        id=ident,
        class_id=class_id,
        label={"en": ident, "hi": ident},
        spawn_s=spawn_s,
        start={"x": start[0], "y": start[1], "z": start[2]},
        start_heading_deg=heading_deg,
        start_speed_mps=speed,
        route=[
            {"position": {"x": x, "y": y, "z": z}, "speed_mps": speed} for (x, y, z) in route
        ],
        on_route_end="loiter",
    )
    return base


def scenario(threats: list[dict[str, Any]], *, clear: bool = True) -> ScenarioSpec:
    data = kestrel().model_dump(mode="json")
    data["threats"] = threats
    data["sensors"] = []
    data["duration_s"] = 600
    if clear:
        data["world"]["weather"].update(
            condition="clear", visibility_m=20000, wind_speed_mps=0, gust_sigma_mps=0
        )
        data["world"]["start_time_of_day_h"] = 12.0
    return ScenarioSpec.model_validate(data)


def profile(name: str, **overrides: tuple[float, str] | None) -> SensorParams:
    """A shipped sensor profile with some parameters replaced `(value, unit)` or removed (None)."""
    params = load_sensor_profile(default_profile_dir() / f"{name}.v1.yaml")
    changed = dict(params.profile.parameters)
    for key, value in overrides.items():
        if value is None:
            changed.pop(key, None)
        else:
            changed[key] = Quantity(value=value[0], unit=value[1], source_id="F01", verified=False)
    return SensorParams(params.profile.model_copy(update={"parameters": changed}))


def radar_params(**overrides: tuple[float, str] | None) -> SensorParams:
    """The shipped radar without false alarms unless the caller asks for them."""
    merged: dict[str, tuple[float, str] | None] = {"false_alarm_rate": (0.0, "count")}
    merged.update(overrides)
    return profile("radar-generic-s", **merged)


def sensor(ident: str, params: SensorParams, at: Vec3, boresight: float = 0.0) -> Sensor:
    placement = SensorPlacement(
        id=ident,
        profile=PackRef(id=params.id, version=params.version),
        position=at,
        boresight_deg=boresight,
    )
    return MODELS[params.modality](placement, params)


@dataclass
class Rig:
    spec: ScenarioSpec
    seed: int
    sensors: list[Sensor]
    config: TrackerConfig | None = None
    policy: AmbiguityPolicy | None = None
    world: World = field(init=False)
    suite: SensorSuite = field(init=False)
    tracker: Tracker = field(init=False)
    #: Reference number of every report -> the drone that caused it (None: a false alarm).
    truth: dict[int, str | None] = field(init=False, default_factory=dict)
    #: (tick, result) for every tick.
    history: list[tuple[int, UpdateResult]] = field(init=False, default_factory=list)
    _ref: int = field(init=False, default=0)

    def __post_init__(self) -> None:
        self.world = World(self.spec, self.seed)
        self.suite = SensorSuite(self.sensors)
        self.tracker = Tracker(
            {s.id: s.position for s in self.sensors}, config=self.config, policy=self.policy
        )

    @property
    def rng(self) -> RngStreams:
        return self.world.rng

    def step(self, ticks: int = 1) -> UpdateResult:
        result = UpdateResult()
        for _ in range(ticks):
            measurements: list[Measurement] = []
            for d in self.suite.detect(self.world):
                measurements.append(Measurement.from_view(d.trainee_view(), self._ref))
                self.truth[self._ref] = d.truth_id
                self._ref += 1
            result = self.tracker.update(self.world.tick, measurements, self.world.rng)
            self.history.append((self.world.tick, result))
            self.world.step()
        return result

    def run_to(self, tick: int) -> None:
        self.step(max(0, tick - self.world.tick))

    def events(self, kind: str | None = None) -> list[tuple[int, str, str]]:
        return [
            (tick, e.kind, e.track_id)
            for tick, r in self.history
            for e in r.events
            if kind is None or e.kind == kind
        ]

    def follows(self, track_id: str, window: int = 8) -> str | None:
        """The drone a track's last `window` reports mostly came from (test-side truth)."""
        votes: dict[str | None, int] = {}
        recent = [
            self.truth[a.ref]
            for _, r in self.history[-400:]
            for a in r.associations
            if a.track_id == track_id
        ][-window:]
        for t in recent:
            votes[t] = votes.get(t, 0) + 1
        if not votes:
            return None
        return sorted(votes.items(), key=lambda kv: (-kv[1], str(kv[0])))[0][0]
