"""The sensor picture of one session: sensors, tracker, ground-truth ledger and AI assist together.

`World.step` calls `Picture.update` once per tick, after the tick's actions and spawns and before
anything moves, and `Picture.apply` for track and cue actions. The picture never changes the
world; it reports into the event log and keeps its own state, which `World.state()` includes.

Two audiences, kept apart on purpose:

* the trainee gets `trainee_frame()`: this tick's reports (`Detection.trainee_view()`), the track
  views and the assist's views, each carrying `data_status`; and the events in
  `TRAINEE_EVENT_TYPES`, which hold no ground truth;
* the instructor and scoring get everything else in the log: `ledger.*` events name the true
  identities, and `assist.assess` records whether the assist was right.

Wave 5's transport must send a trainee only the allow-listed events and frames (a test pins that
this module's own output respects it).
"""

from collections import deque
from pathlib import Path
from typing import TYPE_CHECKING, Any

from app.contracts.scenario import ScenarioSpec

from ..sensors import SensorSuite, build_sensors
from .ambiguity import ErrorModel, ErrorPolicy
from .assist import AiAssist, AssistConfig, TruthRef
from .commands import apply as apply_command
from .config import TrackerConfig
from .cueing import apply_cue
from .ledger import LedgerEvent, TruthLedger
from .measurement import Measurement
from .tracker import Tracker

if TYPE_CHECKING:
    from app.contracts import ActionRecord

    from ..world import World

#: Events a trainee's console may receive: tracker lifecycle and the operator's own commands.
#: None of them names a drone or a class from the scenario.
TRAINEE_EVENT_TYPES = frozenset(
    {
        "track.init",
        "track.confirm",
        "track.coast",
        "track.resume",
        "track.drop",
        "track.relabel",
        "track.merge",
        "track.split",
        "sensor.cue",
    }
)
#: Events that carry ground truth: instructor, scoring and the after-action review only.
TRUTH_EVENT_TYPES = frozenset(
    {
        "ledger.swap",
        "ledger.split",
        "ledger.merge",
        "ledger.restored",
        "ledger.first_report",
        "assist.assess",
    }
)

#: How long (s) a report's ground-truth reference is kept, long enough for triangulation.
TRUTH_KEEP_S = 2.0
DATA_NOTICE = "Reference data: fictional sensor parameters, not verified (Q-20)."


class Picture:
    def __init__(
        self,
        spec: ScenarioSpec,
        seed: int,
        suite: SensorSuite,
        tracker: Tracker,
        ledger: TruthLedger,
        assist: AiAssist,
    ) -> None:
        self.spec = spec
        self.seed = seed
        self.suite = suite
        self.tracker = tracker
        self.ledger = ledger
        self.assist = assist
        self._class_of = {t.id: t.class_id for t in spec.threats}
        self._ref = 0
        #: Report reference -> the drone that caused it. Never leaves the picture.
        self._truth: dict[int, str | None] = {}
        self._recent: deque[tuple[int, list[int]]] = deque()
        #: This tick's reports as a trainee sees them.
        self._reports: list[dict[str, Any]] = []
        self._latest: dict[str, dict[str, Any]] = {}
        #: Drones a sensor has reported at least once: the "first detectable moment" for scoring.
        self._first_seen: set[str] = set()

    @classmethod
    def build(
        cls,
        spec: ScenarioSpec,
        seed: int,
        *,
        profile_dir: Path | None = None,
        register: frozenset[str] | None = None,
        tracker_config: TrackerConfig | None = None,
        error_model: ErrorModel | None = None,
        assist_config: AssistConfig | None = None,
    ) -> "Picture":
        suite = build_sensors(spec, profile_dir, register=register)
        tracker = Tracker(
            {s.id: s.position for s in suite.sensors},
            config=tracker_config,
            policy=ErrorPolicy(error_model or ErrorModel()),
        )
        return cls(spec, seed, suite, tracker, TruthLedger(), AiAssist(seed, assist_config))

    # ------------------------------------------------------------------ the tick

    def update(self, world: "World") -> None:
        tick = world.tick
        refs: list[int] = []
        measurements: list[Measurement] = []
        self._reports = []
        firsts: list[tuple[str, str, str]] = []
        for detection in self.suite.detect(world):
            if detection.truth_id is not None and detection.truth_id not in self._first_seen:
                self._first_seen.add(detection.truth_id)
                firsts.append((detection.truth_id, detection.sensor_id, detection.modality))
            view = detection.trainee_view()
            measurements.append(Measurement.from_view(view, self._ref))
            self._reports.append(view)
            self._truth[self._ref] = detection.truth_id
            refs.append(self._ref)
            self._ref += 1
        result = self.tracker.update(tick, measurements, world.rng)
        self._recent.append((tick, refs))
        self._forget_old_truth(tick)
        for drone, sensor, modality in firsts:
            world.emit(
                "ledger.first_report", {"drone": drone, "sensor": sensor, "modality": modality}
            )
        for event in result.events:
            world.emit(f"track.{event.kind}", event.payload)
        self._emit_ledger(world, self.ledger.observe(tick, result, self._truth))
        self._assess(world)

    def _forget_old_truth(self, tick: int) -> None:
        keep_from = tick - round(TRUTH_KEEP_S * self.tracker.tick_hz)
        while self._recent and self._recent[0][0] < keep_from:
            for ref in self._recent.popleft()[1]:
                del self._truth[ref]

    def _emit_ledger(self, world: "World", events: list[LedgerEvent]) -> None:
        for event in events:
            world.emit(f"ledger.{event.kind}", event.payload)

    def _assess(self, world: "World") -> None:
        tick = world.tick
        for track in self.tracker.tracks.values():
            identity = self.ledger.identity_of(track.id)
            truth = TruthRef(self._class_of.get(identity) if identity is not None else None)
            assessment = self.assist.assess(track.view(tick, self.tracker.tick_hz), truth, tick)
            if assessment is not None:
                self._latest[track.id] = assessment.view()
                world.emit("assist.assess", assessment.record())
        for gone in sorted(set(self._latest) - set(self.tracker.tracks)):
            del self._latest[gone]
            self.assist.forget(gone)

    # ------------------------------------------------------------------ actions

    def apply(self, world: "World", action: "ActionRecord") -> None:
        """Run a track command or sensor cue; raise `ActionError` to log it as rejected."""
        from ..world import ActionError

        name = action.action
        if name == "sensor-cue":
            cue = apply_cue(self.tracker, self.suite, world.tick, action.payload)
            if not cue.ok:
                raise ActionError(cue.reason or "the sensor refused the cue")
            target = self.ledger.identity_of(str(action.payload.get("track")))
            world.emit("action.sensor_cue", {**action.payload, "target": target}, action.actor)
            world.emit("sensor.cue", cue.payload, action.actor)
            return
        outcome = apply_command(self.tracker, world.tick, name, action.payload)
        if not outcome.ok:
            raise ActionError(outcome.reason or "the command was refused")
        world.emit("action." + name.replace("-", "_"), dict(action.payload), action.actor)
        for kind, payload in outcome.events:
            world.emit(kind, payload, action.actor)
        self._emit_ledger(world, self.ledger.on_effects(world.tick, outcome.effects))

    # ------------------------------------------------------------------ what the trainee sees

    def trainee_frame(self, tick: int) -> dict[str, Any]:
        """Reports, tracks and assist views for a trainee's console: no ground truth."""
        return {
            "tick": tick,
            "reports": [dict(r) for r in self._reports],
            "tracks": self.tracker.views(tick),
            "assist": [self._latest[k] for k in sorted(self._latest)],
            "sensors": [sensor.view(tick) for sensor in self.suite.sensors],
            "data_notice": DATA_NOTICE,
        }

    # ------------------------------------------------------------------ snapshot

    def state(self) -> dict[str, Any]:
        return {
            "suite": self.suite.state(),
            "tracker": self.tracker.state(),
            "ledger": self.ledger.state(),
            "assist": self.assist.state(),
            "ref": self._ref,
            "truth": {str(k): v for k, v in sorted(self._truth.items())},
            "recent": [[t, list(r)] for t, r in self._recent],
            "first_seen": sorted(self._first_seen),
            "latest": {k: dict(v) for k, v in sorted(self._latest.items())},
        }

    def restore(self, state: dict[str, Any]) -> None:
        self.suite.restore(state["suite"])
        self.tracker.restore(state["tracker"])
        self.ledger.restore(state["ledger"])
        self.assist.restore(state["assist"])
        self._ref = int(state["ref"])
        self._truth = {int(k): v for k, v in state["truth"].items()}
        self._recent = deque((int(t), [int(x) for x in r]) for t, r in state["recent"])
        self._first_seen = set(state.get("first_seen", []))
        self._latest = {k: dict(v) for k, v in state["latest"].items()}
        self._reports = []
