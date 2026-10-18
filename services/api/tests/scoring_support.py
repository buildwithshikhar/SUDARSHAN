"""Build event logs for the scoring tests from compact steps.

The evaluator (`app.scoring`) is a pure function of the event log, so most scoring tests never run
the simulator. A *step* is a small JSON-friendly dict (so the golden fixtures can store them);
`build` turns steps into a valid hash-chained list of `EventRecord`s with `sim.eventlog.EventLog`,
logging an operator action the way `sim/world.py::_operator_action` does:

* the `roe.verdict` comes first, with `target`, the track's `context` (identity and classification
  from the operator's own earlier accepted calls on that track, `zone_role`, `confidence`),
  `permitted` and `rule_id`;
* only a permitted action then gets its `action.<name>` event, carrying `target` (and, for a
  report, the `truth` it is graded against). A blocked response is the verdict alone.

The scenario is Harrier Field (`contact-quad` hostile, `contact-civil` civil-permitted,
`contact-bird-1..3` clutter, site at the origin) and the rule pack is the training baseline.
"""

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from app.contracts import EventRecord, ScenarioSpec
from app.contracts.loader import load_pack
from app.contracts.rulepack import RulePack
from app.contracts.score import SessionScore
from app.scoring import score_events
from sim.eventlog import EventLog

REPO = Path(__file__).resolve().parents[3]
HARRIER_PATH = REPO / "packs" / "scenarios" / "harrier-morning-watch.v1.json"
BASELINE_PATH = REPO / "packs" / "rule-packs" / "training-baseline.v1.yaml"
OPERATOR = "trainee:op-1"
TICK_HZ = 20
#: The scenario's length (420 s), used as the session's tick count unless a test says otherwise.
SESSION_TICKS = 420 * TICK_HZ

QUAD = "contact-quad"
CIVIL = "contact-civil"
BIRDS = ("contact-bird-1", "contact-bird-2", "contact-bird-3")

Step = dict[str, Any]


def harrier() -> ScenarioSpec:
    spec = load_pack(HARRIER_PATH)
    assert isinstance(spec, ScenarioSpec)
    return spec


def baseline() -> RulePack:
    pack = load_pack(BASELINE_PATH)
    assert isinstance(pack, RulePack)
    return pack


def pack_with(**scoring: Any) -> RulePack:
    """The baseline pack with some `scoring` values replaced (the models are frozen)."""
    data = baseline().model_dump(mode="json")
    data["scoring"].update(scoring)
    return RulePack.model_validate(data)


# --------------------------------------------------------------------------------------- steps


def first_report(t: float, drone: str, sensor: str = "radar-1", modality: str = "radar") -> Step:
    """The first time any sensor reported `drone` (every timing standard starts here)."""
    return {"op": "first_report", "t": t, "drone": drone, "sensor": sensor, "modality": modality}


def truth(**over: Any) -> dict[str, Any]:
    """What a report on the Harrier hostile is graded against: one rotary drone 1000 m due north
    of the site, flying east (course 90 degrees)."""
    base: dict[str, Any] = {
        "class_id": "rotary-small",
        "disposition": "hostile",
        "x": 0.0,
        "y": 1000.0,
        "z": 120.0,
        "heading_deg": 90.0,
        "count": 1,
    }
    return {**base, **over}


def act(
    t: float,
    action: str,
    track: str,
    target: str | None,
    *,
    permitted: bool = True,
    rule_id: str | None = None,
    context: dict[str, Any] | None = None,
    truth: dict[str, Any] | None = None,
    **payload: Any,
) -> Step:
    """An operator action on `track` (really `target`, or None for a false track) at `t` seconds.

    `context` overrides fields of the logged verdict context; `permitted=False` logs the verdict
    alone. Everything else is the action's payload (`class_id`, `identity`, `effector_class`, or
    the report fields).
    """
    step: Step = {"op": "act", "t": t, "action": action, "track": track, "target": target}
    if payload:
        step["payload"] = payload
    if not permitted:
        step["permitted"] = False
    if rule_id is not None:
        step["rule_id"] = rule_id
    if context:
        step["context"] = context
    if truth is not None:
        step["truth"] = truth
    return step


def swap(t: float, error_id: int, from_truth: str, to_truth: str) -> Step:
    return {
        "op": "swap",
        "t": t,
        "error_id": error_id,
        "from_truth": from_truth,
        "to_truth": to_truth,
    }


def split(t: float, error_id: int, truth_id: str) -> Step:
    return {"op": "split", "t": t, "error_id": error_id, "truth": truth_id}


def merge(t: float, error_id: int, dropped: str, survivor: str) -> Step:
    return {
        "op": "merge",
        "t": t,
        "error_id": error_id,
        "truth_dropped": dropped,
        "truth_survivor": survivor,
    }


def restored(t: float, error_id: int, kind: str = "swap") -> Step:
    return {"op": "restored", "t": t, "error_id": error_id, "error_kind": kind}


def noise(t: float, kind: str = "track.update", **payload: Any) -> Step:
    """An event the evaluator has no use for (a track update, a sensor frame, ...)."""
    return {"op": "other", "t": t, "type": kind, "payload": payload}


# ---------------------------------------------------------------------------------------- build


def _default_rule(action: str, effector: Any, permitted: bool) -> str:
    if action != "engage":
        return "track-everything"
    return "hostile-inner-zone" if permitted and effector == "ec-b" else "suspect-outer-zone"


def build(steps: list[Step]) -> list[EventRecord]:
    """A valid hash-chained event log from steps (stable-sorted by time, as a real log is)."""
    log = EventLog(TICK_HZ)
    operator: dict[str, dict[str, Any]] = {}
    for step in sorted(steps, key=lambda s: s["t"]):
        tick = round(step["t"] * TICK_HZ)
        op = step["op"]
        if op == "first_report":
            log.append(
                tick,
                "ledger.first_report",
                "sim",
                {k: step[k] for k in ("drone", "sensor", "modality")},
            )
        elif op == "act":
            _act(log, operator, tick, step)
        elif op == "swap":
            payload = {k: v for k, v in step.items() if k not in ("op", "t")}
            log.append(tick, "ledger.swap", "sim", {**payload, "tick": tick})
        elif op == "split":
            payload = {k: v for k, v in step.items() if k not in ("op", "t")}
            log.append(tick, "ledger.split", "sim", {**payload, "tick": tick})
        elif op == "merge":
            payload = {k: v for k, v in step.items() if k not in ("op", "t")}
            log.append(tick, "ledger.merge", "sim", {**payload, "tick": tick})
        elif op == "restored":
            payload = {k: v for k, v in step.items() if k not in ("op", "t")}
            log.append(tick, "ledger.restored", "sim", {**payload, "tick": tick})
        elif op == "other":
            log.append(tick, step["type"], "sim", dict(step.get("payload", {})))
        else:  # pragma: no cover - a typo in a test
            raise ValueError(f"unknown step {op!r}")
    return list(log.records)


def _act(log: EventLog, operator: dict[str, dict[str, Any]], tick: int, step: Step) -> None:
    action, track, target = step["action"], step["track"], step["target"]
    payload: dict[str, Any] = dict(step.get("payload", {}))
    permitted = step.get("permitted", True)
    mine = operator.setdefault(track, {})
    context = {
        "identity": mine.get("identity"),
        "classification": mine.get("class_id"),
        "zone_role": "outer",
        "confidence": 0.9,
        **step.get("context", {}),
    }
    effector = payload.get("effector_class") if action == "engage" else None
    rule_id = step.get("rule_id") or _default_rule(action, effector, permitted)
    log.append(
        tick,
        "roe.verdict",
        OPERATOR,
        {
            "action": action,
            "track": track,
            "target": target,
            "effector_class": effector,
            "context": context,
            "permitted": permitted,
            "code": "permitted" if permitted else "conditions",
            "rule_id": rule_id,
            "rule_title": rule_id,
            "pack_id": "training-baseline",
            "pack_version": "1.0.0",
            "authority": "operator",
            "detail": {},
        },
    )
    if not permitted:
        return
    if action == "classify":
        mine["class_id"] = payload["class_id"]
    elif action == "assess":
        mine["identity"] = payload["identity"]
    logged: dict[str, Any] = {**payload, "track": track, "target": target}
    if action == "report" and "truth" in step:
        logged["truth"] = step["truth"]
    log.append(tick, f"action.{action}", OPERATOR, logged)


def score(
    log: Sequence[Step | EventRecord],
    *,
    spec: ScenarioSpec | None = None,
    pack: RulePack | None = None,
    seed: int = 1,
    ticks: int = SESSION_TICKS,
) -> SessionScore:
    """Score a log: steps are built into events first, events are used as they are."""
    if all(isinstance(item, dict) for item in log):
        events = build([item for item in log if isinstance(item, dict)])
    else:
        events = [item for item in log if isinstance(item, EventRecord)]
    head = events[-1].hash if events else "0" * 64
    return score_events(
        spec or harrier(), pack or baseline(), events, seed=seed, ticks=ticks, event_head=head
    )
