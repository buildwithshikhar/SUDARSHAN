"""The oracle defender: a perfect-policy agent that plays a scenario headlessly.

It runs the same sim core, sensors, tracker and rules of engagement a trainee session runs, and
sends the same operator actions, so a scenario it clears is one the scoring can award its maximum
for. It is a test agent, not a model of a person: it reads ground truth (which real drone a track
follows, the true class and course) to make the calls a perfect operator would make, and it never
breaks a rule. A scenario is "verified solvable by test run" when this agent reaches the maximum
score in time, and every hostile contact was presented and answered. That checks what the oracle
exercises; it is not a proof (ADR-008).

Policy, once per tick, for every confirmed track that follows a real drone:

- classify it as its true recognition class and assess it by its true disposition (hostile,
  neutral for a civil or clutter contact);
- a hostile contact is reported at once, with every field taken from the truth the scoring grades
  against and a stated confidence equal to the report's own quality, so calibration is perfect;
- a hostile contact is then engaged with the first effector class the permitting rule lists, as
  soon as the rules of engagement permit it (checked first, so a blocked attempt is never made);
- a track the tracker has mixed up is repaired by relabelling it back to the label of the drone it
  follows, so no unfixed track error costs marks.

It stops early once every hostile contact has been answered, a few seconds have passed and no
track error is open.
"""

from collections.abc import Callable
from dataclasses import dataclass, field

from app.contracts import ActionRecord, ScenarioSpec, SessionRecord
from app.contracts.common import PackRef
from app.contracts.rulepack import RulePack
from app.contracts.score import SessionScore
from app.scoring import score_session
from sim import detmath, replay
from sim.provenance import used_versions
from sim.recognition import recognition_class
from sim.roe import load_rule_engine
from sim.tracking.picture import Picture
from sim.world import ActionError, World

ACTOR = "trainee:oracle"
#: Seconds the oracle keeps playing after its last answer, so late events are in the log.
TAIL_S = 4.0
IDENTITY = {"hostile": "hostile", "civil-permitted": "neutral", "clutter": "neutral"}


@dataclass(slots=True)
class _Track:
    classified: bool = False
    assessed: bool = False
    reported: bool = False
    engaged: bool = False


@dataclass(frozen=True, slots=True)
class OracleResult:
    """What the oracle did and how it scored."""

    record: SessionRecord
    score: SessionScore
    #: Hostile contacts no sensor ever reported, or that were never answered.
    unanswered: tuple[str, ...]
    #: Scenario seconds at which the oracle stopped.
    finished_s: float
    actions: tuple[ActionRecord, ...] = field(default=())
    #: Track errors still open when the run ended, as `kind:error_id:tracks`.
    open_errors: tuple[str, ...] = field(default=())


def _site(spec: ScenarioSpec) -> tuple[float, float]:
    if spec.assets:
        return spec.assets[0].position.x, spec.assets[0].position.y
    return 0.0, 0.0


def _action(world: World, name: str, **payload: object) -> ActionRecord:
    return ActionRecord(tick=world.tick, actor=ACTOR, action=name, payload=payload)


def _report(world: World, track_id: str, drone_id: str, site: tuple[float, float]) -> ActionRecord:
    drone = next(d for d in world.drones if d.id == drone_id)
    truth = world.report_truth(drone)
    dx, dy = truth["x"] - site[0], truth["y"] - site[1]
    return _action(
        world,
        "report",
        track=track_id,
        class_id=truth["class_id"],
        bearing_deg=round(detmath.wrap360(detmath.atan2(dx, dy) / detmath.DEG), 3) % 360.0,
        range_m=round((dx * dx + dy * dy) ** 0.5, 3),
        count=truth["count"],
        heading_deg=truth["heading_deg"] % 360.0,
        confidence=1.0,
    )


def play(
    spec: ScenarioSpec,
    seed: int,
    *,
    max_ticks: int | None = None,
    pack: RulePack | None = None,
    on_step: Callable[[World], None] | None = None,
) -> OracleResult:
    """Run the oracle defender through `spec` with `seed` and score what it did. `on_step`, if
    given, is called with the world after every tick (the preview samples positions with it)."""
    engine = load_rule_engine(spec)
    pack = engine.pack if pack is None else pack
    world = World(spec, seed, picture=Picture.build(spec, seed), roe=engine)
    assert world.picture is not None
    site = _site(spec)
    ticks = round(spec.duration_s * spec.tick_hz) if max_ticks is None else max_ticks
    hostile = {t.id for t in spec.threats if t.disposition == "hostile"}
    first_effector = _first_effectors(pack)
    state: dict[str, _Track] = {}
    answered: set[str] = set()
    actions: list[ActionRecord] = []
    last_answer: int | None = None
    while world.tick < ticks:
        todo: list[ActionRecord] = []
        picture = world.picture
        for track_id in sorted(picture.tracker.tracks):
            drone_id = picture.ledger.identity_of(track_id)
            if drone_id is None:
                continue
            threat = next(t for t in spec.threats if t.id == drone_id)
            mine = state.setdefault(f"{track_id}:{drone_id}", _Track())
            if not mine.classified:
                label = recognition_class(threat.class_id)
                todo.append(_action(world, "classify", track=track_id, class_id=label))
                mine.classified = True
            if not mine.assessed:
                todo.append(
                    _action(world, "assess", track=track_id, identity=IDENTITY[threat.disposition])
                )
                mine.assessed = True
            if threat.disposition != "hostile":
                continue
            if not mine.reported:
                todo.append(_report(world, track_id, drone_id, site))
                mine.reported = True
            if not mine.engaged and mine.assessed and _permitted(world, track_id, first_effector):
                todo.append(_action(world, "engage", track=track_id, effector_class=first_effector))
                mine.engaged = True
                answered.add(drone_id)
                last_answer = world.tick
        todo.extend(_repairs(world))
        _apply(world, todo, actions)
        if on_step is not None:
            on_step(world)
        if (
            last_answer is not None
            and answered >= hostile
            and world.tick - last_answer >= round(TAIL_S * spec.tick_hz)
            and not picture.ledger.open_errors()
        ):
            break
    final_tick = world.tick
    final_hash = replay.finish(world)
    versions = used_versions(spec)
    record = SessionRecord(
        contract="session-record.v1",
        scenario=PackRef(id=spec.id, version=spec.version),
        seed=seed,
        ticks=final_tick,
        actions=replay.ordered(actions),
        events=list(world.log.records),
        final_state_hash=final_hash,
        picture=True,
        roe=True,
        profiles=list(versions.profiles),
        threat_classes=list(versions.threat_classes),
    )
    score = score_session(spec, pack, record)
    presented = {t.threat_id for t in score.threats if t.presented}
    unanswered = tuple(sorted(hostile - (answered & presented)))
    leftover = tuple(
        f"{e['kind']}:{e['id']}:{','.join(e['tracks'])}" for e in world.picture.ledger.open_errors()
    )
    return OracleResult(
        record, score, unanswered, final_tick / spec.tick_hz, tuple(actions), leftover
    )


def _repairs(world: World) -> list[ActionRecord]:
    """Commands that put right the track errors the tracker has made, so none goes unfixed.

    A swap: a track that follows drone D under a label that is not D's takes the label of the
    track now wearing D's label (exchanging the two), or D's label if nobody wears it; a track that
    follows nothing known is dropped. A split: the second confirmed track on a drone is merged into
    the first. A merge error clears itself when the tracker finds both drones again.
    """
    picture = world.picture
    assert picture is not None
    ledger, tracks = picture.ledger, picture.tracker.tracks
    out: list[ActionRecord] = []
    touched: set[str] = set()
    for error in ledger.open_errors():
        if error["kind"] == "swap":
            for track_id in error["tracks"]:
                if track_id not in tracks or track_id in touched or ledger.consistent(track_id):
                    continue
                drone = ledger.identity_of(track_id)
                bound = [] if drone is None else ledger.bound_labels(drone)
                wearer = next(
                    (u for u in sorted(tracks) if u != track_id and ledger.label_of(u) in bound),
                    None,
                )
                if wearer is not None:
                    label = ledger.label_of(wearer)
                    out.append(
                        _action(world, "track-relabel", track=track_id, label=label, exchange=True)
                    )
                    touched |= {track_id, wearer}
                elif bound:
                    out.append(_action(world, "track-relabel", track=track_id, label=bound[0]))
                    touched.add(track_id)
                else:
                    out.append(_action(world, "track-drop", track=track_id))
                    touched.add(track_id)
        elif error["kind"] == "split":
            followers = [t for t in ledger.followers_of(error["truths"][0]) if t not in touched]
            if len(followers) >= 2:
                out.append(_action(world, "track-merge", tracks=followers[:2]))
                touched |= set(followers[:2])
    return out


def _apply(world: World, todo: list[ActionRecord], actions: list[ActionRecord]) -> None:
    actions.extend(todo)
    world.step(todo)


def _first_effectors(pack: RulePack) -> str:
    """The lowest-escalation effector class: the first one the first engage rule lists."""
    for rule in pack.rules:
        if "engage" in rule.permits and rule.effector_classes:
            return rule.effector_classes[0]
    raise ActionError("the rule pack has no rule that permits an engagement")


def _permitted(world: World, track_id: str, effector: str) -> bool:
    assert world.roe is not None
    return world.roe.evaluate("engage", world.operator_context(track_id), effector).permitted
