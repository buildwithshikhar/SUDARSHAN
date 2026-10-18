"""What the event log says about each contact: a pure reading of the log, nothing computed.

The evaluator never looks at the simulation. It reads the stored events, which carry the ground
truth the scorer needs beside what the operator did: `ledger.first_report` (the first moment a
sensor reported a drone), `target` on each operator action and rules verdict (the real drone behind
the track at that moment, or `None` for a false track), `truth` on a filed report, and the
`ledger.swap|split|merge|restored` events.
"""

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from app.contracts import EventRecord

#: Operator actions that count as working a contact ("designating" it) when first taken.
WORKING_ACTIONS = ("designate", "sensor_cue", "classify", "assess", "hold", "report", "engage")
#: The operator's accepted action events: the log names them `action.<name>`.
ACTION_TYPES = frozenset(f"action.{name}" for name in WORKING_ACTIONS)
POSITIVE_IDENTITIES = ("hostile", "suspect")


@dataclass(frozen=True, slots=True)
class Call:
    """One accepted operator action, with the real drone behind its track at that moment."""

    seq: int
    t: float
    action: str
    track: str
    target: str | None
    payload: dict[str, Any]


@dataclass(frozen=True, slots=True)
class Verdict:
    seq: int
    t: float
    action: str
    track: str
    target: str | None
    permitted: bool
    effector_class: str | None
    rule_id: str | None
    context: dict[str, Any]


@dataclass(slots=True)
class TrackError:
    error_id: int
    kind: str
    t: float
    threats: list[str]
    restored_t: float | None = None


@dataclass(slots=True)
class LogFacts:
    first_report: dict[str, float] = field(default_factory=dict)
    calls: list[Call] = field(default_factory=list)
    verdicts: list[Verdict] = field(default_factory=list)
    errors: dict[int, TrackError] = field(default_factory=dict)

    def calls_on(self, threat_id: str, *actions: str) -> list[Call]:
        return [
            c for c in self.calls if c.target == threat_id and (not actions or c.action in actions)
        ]

    def verdicts_on(self, threat_id: str, action: str) -> list[Verdict]:
        return [v for v in self.verdicts if v.target == threat_id and v.action == action]

    def verdict_before(self, call: Call) -> Verdict | None:
        """The rules verdict logged for this action: the last one for its track and action
        before it."""
        found = None
        for verdict in self.verdicts:
            if (
                verdict.seq < call.seq
                and verdict.track == call.track
                and verdict.action == call.action
            ):
                found = verdict
        return found


def _threats_of(kind: str, payload: dict[str, Any]) -> list[str]:
    if kind == "swap":
        names = [payload.get("from_truth"), payload.get("to_truth")]
    elif kind == "split":
        names = [payload.get("truth")]
    else:
        names = [payload.get("truth_dropped"), payload.get("truth_survivor")]
    return sorted({str(n) for n in names if n})


def read_log(events: Iterable[EventRecord]) -> LogFacts:
    facts = LogFacts()
    for record in events:
        kind, payload = record.type, dict(record.payload)
        if kind == "ledger.first_report":
            facts.first_report.setdefault(str(payload["drone"]), record.t)
        elif kind in ACTION_TYPES:
            target = payload.get("target")
            facts.calls.append(
                Call(
                    record.seq,
                    record.t,
                    kind.removeprefix("action."),
                    str(payload.get("track", "")),
                    None if target is None else str(target),
                    payload,
                )
            )
        elif kind == "roe.verdict":
            target = payload.get("target")
            context = payload.get("context")
            effector = payload.get("effector_class")
            rule = payload.get("rule_id")
            facts.verdicts.append(
                Verdict(
                    record.seq,
                    record.t,
                    str(payload.get("action")),
                    str(payload.get("track")),
                    None if target is None else str(target),
                    bool(payload.get("permitted")),
                    None if effector is None else str(effector),
                    None if rule is None else str(rule),
                    dict(context) if isinstance(context, dict) else {},
                )
            )
        elif kind in ("ledger.swap", "ledger.split", "ledger.merge"):
            error_id = int(str(payload["error_id"]))
            facts.errors[error_id] = TrackError(
                error_id,
                kind.removeprefix("ledger."),
                record.t,
                _threats_of(kind.removeprefix("ledger."), payload),
            )
        elif kind == "ledger.restored":
            error = facts.errors.get(int(str(payload["error_id"])))
            if error is not None:
                error.restored_t = record.t
    return facts
