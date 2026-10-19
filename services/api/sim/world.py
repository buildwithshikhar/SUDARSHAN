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
from collections.abc import Mapping, Sequence
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
from .recognition import recognition_class
from .rng import RngStreams
from .roe import OPERATOR_CLASSES, Context, RuleEngine
from .terrain import Terrain, TerrainError, terrain_for

if TYPE_CHECKING:
    from .tracking.picture import Picture

SNAPSHOT_FORMAT = "sim-snapshot.v1"
TRACK_ACTIONS: tuple[str, ...] = get_args(TrackAction)
TRAINEE_ACTIONS = ("designate", "classify", "assess", "engage", "hold", "report")
IDENTITIES = ("hostile", "suspect", "unknown", "neutral", "friend")
#: Optional fields of a structured contact report (`report` on a track).
REPORT_FIELDS = frozenset(
    {"class_id", "count", "bearing_deg", "range_m", "heading_deg", "confidence"}
)


def _number(
    payload: Mapping[str, Any], key: str, low: float, high: float, upper_open: bool
) -> None:
    value = payload.get(key)
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value != value:
        raise ActionError(f"report {key} must be a number")
    if value < low or value > high or (upper_open and value >= high):
        raise ActionError(f"report {key} must be from {low:g} to {high:g}")


def _check_report(payload: Mapping[str, Any]) -> None:
    """A report may carry any of its fields; each present one must be well formed."""
    if payload.get("class_id") is not None and payload["class_id"] not in OPERATOR_CLASSES:
        raise ActionError(f"report class_id must be one of {', '.join(OPERATOR_CLASSES)}")
    count = payload.get("count")
    if count is not None and (
        isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= 99
    ):
        raise ActionError("report count must be a whole number from 1 to 99")
    _number(payload, "bearing_deg", 0, 360, True)
    _number(payload, "heading_deg", 0, 360, True)
    _number(payload, "range_m", 0, 50_000, False)
    _number(payload, "confidence", 0, 1, False)


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
        roe: RuleEngine | None = None,
        _log: EventLog | None = None,
    ) -> None:
        self.spec = spec
        self.seed = seed
        #: Ground and buildings that can hide a target from a line-of-sight sensor, or `None` for
        #: flat ground, where nothing does.
        self.terrain: Terrain | None = terrain_for(spec.world.terrain)
        if self.terrain is not None and spec.world.half_extent_m > self.terrain.half_extent_m:
            raise TerrainError(
                f"play area (half extent {spec.world.half_extent_m:g} m) is larger than terrain "
                f"pack {self.terrain.pack_id} ({self.terrain.half_extent_m:g} m)"
            )
        #: The sensors, tracker, ground-truth ledger and AI assist of this session (wave 4b), or
        #: `None` for a bare world. When present, its state is part of `state()` and its hash.
        self.picture = picture
        if picture is not None and picture.seed != seed:
            raise ValueError("the picture was built for a different seed")
        #: Rules of engagement for operator actions on tracks (wave 5). With a rule engine the
        #: world also keeps the operator's assessment of each track, and hashes it.
        self.roe = roe
        if roe is not None and picture is None:
            raise ValueError("rules of engagement apply to tracks, which need a sensor picture")
        self.operator: dict[str, dict[str, Any]] = {}
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
                {
                    "scenario": spec.id,
                    "version": spec.version,
                    "seed": seed,
                    # Only with a terrain pack, so flat-ground logs are unchanged.
                    **(
                        {}
                        if self.terrain is None
                        else {
                            "terrain": {
                                "id": self.terrain.pack_id,
                                "version": self.terrain.version,
                                "sha256": self.terrain.digest,
                            }
                        }
                    ),
                },
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
        if isinstance(payload.get("track"), str):
            self._operator_action(action)
            return
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

    def _operator_action(self, action: ActionRecord) -> None:
        """An operator action on a track the tracker shows (not on a drone id).

        The ROE verdict is logged first (`roe.verdict`); only a permitted action takes effect and
        is logged as `action.<name>`. `target`, the real drone behind the track, is added to the
        logged action for scoring and is never sent to a trainee (`sim.audience`).
        """
        picture = self.picture
        if picture is None:
            raise ActionError("this session has no sensor picture")
        payload, name = action.payload, action.action
        track_id = str(payload["track"])
        track = picture.tracker.tracks.get(track_id)
        if track is None:
            raise ActionError(f"no live track {track_id!r}")
        known = {"track"} | ({"class_id"} if name == "classify" else set())
        known |= {"identity"} if name == "assess" else set()
        known |= {"effector_class"} if name == "engage" else set()
        known |= REPORT_FIELDS if name == "report" else set()
        extra = sorted(set(payload) - known)
        if extra:
            raise ActionError(f"{name} does not take {', '.join(extra)}")
        mine = self.operator.get(track_id, {})
        if name == "classify" and payload.get("class_id") not in OPERATOR_CLASSES:
            raise ActionError(f"classify needs a class_id, one of {', '.join(OPERATOR_CLASSES)}")
        if name == "assess" and payload.get("identity") not in IDENTITIES:
            raise ActionError(f"assess needs an identity, one of {', '.join(IDENTITIES)}")
        if name == "report":
            _check_report(payload)
        effector = payload.get("effector_class")
        if name == "engage" and not isinstance(effector, str):
            raise ActionError("engage needs an effector_class")
        if name == "engage" and self.roe is not None and effector not in self.roe.effectors:
            raise ActionError(f"no effector class {effector!r} in the rule pack")
        if self.roe is not None:
            view = track.view(self.tick, TICK_HZ)
            _, support = track.class_estimate()
            ctx = Context(
                identity=mine.get("identity"),
                classification=mine.get("class_id"),
                zone_role=self.roe.zone_role(view["position"]["x"], view["position"]["y"]),
                confidence=support,
            )
            chosen = effector if name == "engage" and isinstance(effector, str) else None
            verdict = self.roe.evaluate(name, ctx, chosen)
            self._emit(
                "roe.verdict",
                {
                    "action": name,
                    "track": track_id,
                    "target": picture.ledger.identity_of(track_id),
                    "effector_class": chosen,
                    "context": ctx.view(),
                    **verdict.payload(),
                },
            )
            if not verdict.permitted:
                return
        # an assessment outlives neither its track nor a refusal
        self.operator = {k: v for k, v in self.operator.items() if k in picture.tracker.tracks}
        mine = self.operator.setdefault(track_id, {})
        if name == "designate":
            mine["designated"] = True
        elif name == "classify":
            mine["class_id"] = payload["class_id"]
        elif name == "assess":
            mine["identity"] = payload["identity"]
        elif name == "hold":
            mine["held"] = True
        target = picture.ledger.identity_of(track_id)
        drone = next((d for d in self.drones if d.id == target and d.status == "active"), None)
        if drone is not None:
            if name == "designate":
                drone.designated = True
            elif name == "classify":
                drone.assigned_class = str(payload["class_id"])
            elif name == "assess":
                drone.assigned_identity = str(payload["identity"])
        logged: dict[str, Any] = {**payload, "target": target}
        if name == "report" and drone is not None:
            logged["truth"] = self._report_truth(drone)
        self._emit(f"action.{name}", logged, action.actor)

    def _report_truth(self, drone: Drone) -> dict[str, Any]:
        """What a contact report is graded against: the real class, disposition, position, ground
        course and the number of same-class contacts around it. Ground truth: logged for scoring,
        never sent to a trainee."""
        index = next(i for i, d in enumerate(self.drones) if d.id == drone.id)
        threat = self.spec.threats[index]
        radius = self.roe.pack.scoring.report.count_radius_m if self.roe is not None else 250.0
        wx, wy = self.wind()
        vx, vy = drone.ux * drone.airspeed + wx, drone.uy * drone.airspeed + wy
        course = detmath.wrap360(detmath.atan2(vx, vy) / detmath.DEG)
        count = 0
        for j, other in enumerate(self.drones):
            if other.status != "active" or (
                recognition_class(self.spec.threats[j].class_id)
                != recognition_class(threat.class_id)
            ):
                continue
            if math.sqrt((other.x - drone.x) ** 2 + (other.y - drone.y) ** 2) <= radius:
                count += 1
        return {
            "class_id": recognition_class(threat.class_id),
            "disposition": threat.disposition,
            "x": round(drone.x, 3),
            "y": round(drone.y, 3),
            "z": round(drone.z, 3),
            "heading_deg": round(course, 3),
            "count": count,
        }

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
        if self.roe is not None:
            state["operator"] = {
                k: dict(sorted(v.items())) for k, v in sorted(self.operator.items())
            }
        return state

    def state_hash(self) -> str:
        return sha256_hex(self.state())

    def snapshot(self) -> dict[str, Any]:
        """State plus the event log so far; `World.restore` continues it exactly."""
        return self.state() | {"events": [r.model_dump(mode="json") for r in self.log.records]}

    @classmethod
    def restore(
        cls,
        spec: ScenarioSpec,
        snapshot: dict[str, Any],
        *,
        picture: "Picture | None" = None,
        roe: RuleEngine | None = None,
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
        if ("operator" in snapshot) != (roe is not None):
            raise ValueError(
                "the snapshot has operator state but no rule engine was given"
                if "operator" in snapshot
                else "a rule engine was given but the snapshot has no operator state"
            )
        world = cls(spec, int(snapshot["seed"]), picture=picture, roe=roe, _log=log)
        world.operator = {k: dict(v) for k, v in snapshot.get("operator", {}).items()}
        world.tick = int(snapshot["tick"])
        world.weather = WeatherState(**snapshot["weather"])
        world.rng.restore(snapshot["rng"])
        world.drones = [Drone.from_state(d) for d in snapshot["drones"]]
        if [d.id for d in world.drones] != [t.id for t in spec.threats]:
            raise ValueError("snapshot drones do not match the scenario threats")
        if picture is not None:
            picture.restore(snapshot["picture"])
        return world
