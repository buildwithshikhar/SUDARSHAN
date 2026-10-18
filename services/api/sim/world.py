"""World state and the fixed 20 Hz tick.

One call to `World.step` advances one tick, always in this order:

1. apply the actions recorded for this tick, in log order;
2. spawn threats whose spawn tick has come, in scenario order;
2b. if the world has a picture: sensors report, the tracker updates, the ledger and assist run;
3. advance the wind gust (the `weather` RNG stream);
4. move every active drone, in scenario order, then retire drones that left the play area;
5. increment the tick counter.

Events carry the tick being processed. Nothing reads the wall clock, iterates a set, or depends
on dictionary order that was not fixed by the scenario.
"""

import math
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any, get_args

from pydantic import ValidationError

from app.contracts import TICK_HZ, ActionRecord, EventRecord
from app.contracts.common import PackRef
from app.contracts.events import Payload, TrackAction
from app.contracts.scenario import ScenarioSpec, Weather

from . import detmath
from .canonical import sha256_hex
from .constants import DT, GUST_TAU_S
from .entity import Drone
from .eventlog import EventLog
from .kinematics import Envelope, position, step
from .rng import RngStreams

if TYPE_CHECKING:
    from .tracking.picture import Picture

SNAPSHOT_FORMAT = "sim-snapshot.v1"
TRACK_ACTIONS: tuple[str, ...] = get_args(TrackAction)
TRAINEE_ACTIONS = ("designate", "classify", "assess", "engage", "hold", "report")
IDENTITIES = ("hostile", "suspect", "unknown", "neutral", "friend")


@dataclass(slots=True)
class WeatherState:
    condition: str
    visibility_m: float
    wind_speed_mps: float
    wind_from_deg: float
    gust_sigma_mps: float
    temperature_c: float
    cloud_cover_pct: float
    gust_x: float = 0.0
    gust_y: float = 0.0

    @classmethod
    def of(cls, weather: Weather) -> "WeatherState":
        return cls(**weather.model_dump())

    def contract_fields(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if k not in ("gust_x", "gust_y")}


def spawn_tick(spawn_s: float) -> int:
    """First tick at or after spawn_s, robust to binary rounding (0.15 s is tick 3, not 4)."""
    return math.ceil(round(spawn_s * TICK_HZ, 6))


class ActionError(ValueError):
    pass


class World:
    def __init__(
        self,
        spec: ScenarioSpec,
        seed: int,
        *,
        picture: "Picture | None" = None,
        _log: EventLog | None = None,
    ) -> None:
        self.spec = spec
        self.seed = seed
        #: The sensors, tracker, ground-truth ledger and AI assist of this session (wave 4b), or
        #: `None` for a bare world. When present, its state is part of `state()` and its hash.
        self.picture = picture
        if picture is not None and picture.seed != seed:
            raise ValueError("the picture was built for a different seed")
        self.tick = 0
        self.rng = RngStreams(seed)
        self.weather = WeatherState.of(spec.world.weather)
        self.drones = [Drone.pending(t) for t in spec.threats]
        self._envelopes = [Envelope.of(t.limits) for t in spec.threats]
        self._spawn_ticks = [spawn_tick(t.spawn_s) for t in spec.threats]
        if _log is not None:
            self.log = _log
        else:
            self.log = EventLog(TICK_HZ)
            self.log.append(
                0,
                "session.start",
                "sim",
                {"scenario": spec.id, "version": spec.version, "seed": seed},
            )

    # ------------------------------------------------------------------ time

    @property
    def time_s(self) -> float:
        return self.tick / TICK_HZ

    @property
    def time_of_day_h(self) -> float:
        return (self.spec.world.start_time_of_day_h + self.time_s / 3600.0) % 24.0

    # ------------------------------------------------------------------ tick

    def step(self, actions: Sequence[ActionRecord] = ()) -> None:
        for action in actions:
            if action.tick != self.tick:
                raise ActionError(f"action for tick {action.tick} applied at tick {self.tick}")
            self._apply(action)
        for i, drone in enumerate(self.drones):
            if drone.status == "pending" and self._spawn_ticks[i] <= self.tick:
                drone.status = "active"
                self._emit(
                    "threat.spawn",
                    {"id": drone.id, "class_id": self.spec.threats[i].class_id, **position(drone)},
                )
        if self.picture is not None:
            self.picture.update(self)
        self._advance_gust()
        wind = self.wind()
        half = self.spec.world.half_extent_m
        for i, drone in enumerate(self.drones):
            if drone.status != "active":
                continue
            for kind, payload in step(drone, self.spec.threats[i], self._envelopes[i], wind):
                self._emit(kind, payload)
            if drone.status == "active" and (abs(drone.x) > half or abs(drone.y) > half):
                drone.status = "despawned"
                self._emit(
                    "threat.despawn", {"id": drone.id, "reason": "left-area", **position(drone)}
                )
        self.tick += 1

    def wind(self) -> tuple[float, float]:
        """Wind vector (east, north) in m/s: mean wind plus the current gust."""
        w = self.weather
        to_x, to_y = detmath.heading_vector(w.wind_from_deg + 180.0)
        return to_x * w.wind_speed_mps + w.gust_x, to_y * w.wind_speed_mps + w.gust_y

    def _advance_gust(self) -> None:
        # first-order Gauss-Markov: g += -g * dt / tau + sigma * sqrt(2 dt / tau) * n
        w = self.weather
        decay = DT / GUST_TAU_S
        scale = w.gust_sigma_mps * math.sqrt(2.0 * decay)
        w.gust_x += -w.gust_x * decay + scale * self.rng.normalish("weather")
        w.gust_y += -w.gust_y * decay + scale * self.rng.normalish("weather")

    def _emit(self, kind: str, payload: Payload, actor: str = "sim") -> EventRecord:
        return self.log.append(self.tick, kind, actor, payload)

    def emit(self, kind: str, payload: Payload, actor: str = "sim") -> EventRecord:
        """Append an event at the current tick; for subsystems attached to the world."""
        return self._emit(kind, payload, actor)

    # ------------------------------------------------------------------ actions

    def _apply(self, action: ActionRecord) -> None:
        try:
            if action.action == "set-weather":
                self._set_weather(action)
            elif action.action in TRACK_ACTIONS:
                if self.picture is None:
                    raise ActionError("this session has no sensor picture")
                self.picture.apply(self, action)
            else:
                self._trainee_action(action)
        except ActionError as error:
            self._emit(
                "action.rejected",
                {"action": action.action, "reason": str(error), "payload": action.payload},
                action.actor,
            )

    def _set_weather(self, action: ActionRecord) -> None:
        if not action.actor.startswith("instructor:"):
            raise ActionError("only an instructor can change the weather")
        merged = self.weather.contract_fields() | action.payload
        try:
            weather = Weather.model_validate(merged)
        except ValidationError as error:
            raise ActionError(f"invalid weather: {error.errors()[0]['msg']}") from None
        gust = (self.weather.gust_x, self.weather.gust_y)
        self.weather = WeatherState.of(weather)
        self.weather.gust_x, self.weather.gust_y = gust
        self._emit("weather.set", dict(action.payload), action.actor)

    def _trainee_action(self, action: ActionRecord) -> None:
        payload = action.payload
        target = payload.get("target")
        drone = next((d for d in self.drones if d.id == target), None)
        if action.action in ("hold", "report") and target is None:
            drone = None
        elif drone is None or drone.status != "active":
            raise ActionError(f"no active contact {target!r}")
        if action.action == "designate" and drone is not None:
            drone.designated = True
        elif action.action == "classify" and drone is not None:
            label = payload.get("class_id")
            if not isinstance(label, str) or not label:
                raise ActionError("classify needs a class_id")
            drone.assigned_class = label
        elif action.action == "assess" and drone is not None:
            identity = payload.get("identity")
            if identity not in IDENTITIES:
                raise ActionError(f"assess needs an identity, one of {', '.join(IDENTITIES)}")
            drone.assigned_identity = str(identity)
        elif action.action == "engage" and not isinstance(payload.get("effector_class"), str):
            # the outcome of a response is resolved by the rule pack in a later wave
            raise ActionError("engage needs an effector_class")
        self._emit(f"action.{action.action}", dict(payload), action.actor)

    # ------------------------------------------------------------------ state

    def state(self) -> dict[str, Any]:
        """Everything that determines the future, as plain JSON values."""
        state: dict[str, Any] = {
            "format": SNAPSHOT_FORMAT,
            "scenario": {"id": self.spec.id, "version": self.spec.version},
            "seed": self.seed,
            "tick": self.tick,
            "weather": asdict(self.weather),
            "rng": self.rng.state(),
            "drones": [d.to_state() for d in self.drones],
            "event_count": len(self.log),
            "event_head": self.log.head,
        }
        if self.picture is not None:
            # Only present when a picture is attached, so a bare world hashes as it always did.
            state["picture"] = self.picture.state()
        return state

    def state_hash(self) -> str:
        return sha256_hex(self.state())

    def snapshot(self) -> dict[str, Any]:
        """State plus the event log so far; `World.restore` continues it exactly."""
        return self.state() | {"events": [r.model_dump(mode="json") for r in self.log.records]}

    @classmethod
    def restore(
        cls, spec: ScenarioSpec, snapshot: dict[str, Any], *, picture: "Picture | None" = None
    ) -> "World":
        if snapshot.get("format") != SNAPSHOT_FORMAT:
            raise ValueError(f"not a {SNAPSHOT_FORMAT} snapshot")
        ref = PackRef.model_validate(snapshot["scenario"])
        if (ref.id, ref.version) != (spec.id, spec.version):
            raise ValueError(
                f"snapshot is for {ref.id} {ref.version}, not {spec.id} {spec.version}"
            )
        log = EventLog.from_records(snapshot["events"], TICK_HZ)
        if log.head != snapshot["event_head"] or len(log) != snapshot["event_count"]:
            raise ValueError("snapshot events do not match its recorded head")
        if ("picture" in snapshot) != (picture is not None):
            raise ValueError(
                "the snapshot has a sensor picture but none was given"
                if "picture" in snapshot
                else "a sensor picture was given but the snapshot has none"
            )
        world = cls(spec, int(snapshot["seed"]), picture=picture, _log=log)
        world.tick = int(snapshot["tick"])
        world.weather = WeatherState(**snapshot["weather"])
        world.rng.restore(snapshot["rng"])
        world.drones = [Drone.from_state(d) for d in snapshot["drones"]]
        if [d.id for d in world.drones] != [t.id for t in spec.threats]:
            raise ValueError("snapshot drones do not match the scenario threats")
        if picture is not None:
            picture.restore(snapshot["picture"])
        return world
