"""The solved criterion: what a scenario must show in the oracle run to be "verified solvable by
test run" (docs/SCENARIO_ENGINE.md, ADR-025).

Four checks, each stored with its value so the validation panel and the debrief can show them:

- `hostile-presented`: every hostile contact was reported by a sensor;
- `hostile-answered`: every hostile contact was engaged under the rules of engagement;
- `no-failures`: no hard fail, blocked attempt, false engagement or unfixed track error;
- `oracle-score`: every hostile contact's score is at least `min_score` percent.

The wording is fixed: a scenario that passes is "verified solvable by test run". That is a practical
check of what the oracle exercises, not a proof, and it says nothing about how hard the scenario is
for a person.
"""

from dataclasses import dataclass

from app.contracts.scenario import ScenarioSpec

from .oracle import OracleResult

VERIFIED = "verified solvable by test run"
NOT_VERIFIED = "not verified solvable"
#: Findings that mean the oracle did not play cleanly.
FAILURES = ("hard-fail", "blocked-attempt", "false-engagement", "track-error")


@dataclass(frozen=True, slots=True)
class Check:
    name: str
    passed: bool
    #: A number or a short text: the measure the check looked at.
    value: float | str | None
    detail: str
    #: Stable key for the message catalogue.
    code: str


def evaluate(spec: ScenarioSpec, result: OracleResult, min_score: int) -> list[Check]:
    """The four checks for one oracle run."""
    hostile = [t for t in spec.threats if t.disposition == "hostile"]
    threats = {t.threat_id: t for t in result.score.threats}
    unreported = sorted(t.id for t in hostile if not threats[t.id].presented)
    answered = [t.id for t in hostile if t.id not in result.unanswered]
    failures = sorted(
        {
            f"{f.kind}:{t.threat_id}"
            for t in result.score.threats
            for f in t.findings
            if f.kind in FAILURES
        }
        | {f"{f.kind}:session" for f in result.score.findings if f.kind in FAILURES}
    )
    scores = {t.id: threats[t.id].score or 0.0 for t in hostile}
    lowest = min(scores.values(), default=0.0)
    bar = min_score / 100.0
    low = sorted(i for i, s in scores.items() if s < bar)
    return [
        Check(
            "hostile-presented",
            not unreported,
            len(hostile) - len(unreported),
            "every hostile contact was reported by a sensor"
            if not unreported
            else f"never reported by a sensor: {', '.join(unreported)}",
            "solvability.presented",
        ),
        Check(
            "hostile-answered",
            len(answered) == len(hostile),
            len(answered),
            "every hostile contact was engaged under the rules"
            if len(answered) == len(hostile)
            else f"not answered: {', '.join(result.unanswered)}",
            "solvability.answered",
        ),
        Check(
            "no-failures",
            not failures,
            len(failures),
            "no hard fail, blocked attempt, false engagement or unfixed track error"
            if not failures
            else f"failures: {', '.join(failures)}",
            "solvability.failures",
        ),
        Check(
            "oracle-score",
            not low and bool(hostile),
            round(lowest, 4),
            f"every hostile contact scored at least {min_score}%"
            if not low and hostile
            else ("no hostile contact" if not hostile else f"below {min_score}%: {', '.join(low)}"),
            "solvability.score",
        ),
    ]


def solved(checks: list[Check]) -> bool:
    return all(c.passed for c in checks)


def wording(checks: list[Check]) -> str:
    return VERIFIED if solved(checks) else NOT_VERIFIED
