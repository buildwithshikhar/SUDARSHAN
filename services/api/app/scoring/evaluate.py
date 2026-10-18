"""Score a finished session: a pure function of the scenario, the rule pack and the event log.

`score_session` reads the stored events (`facts.read_log`), walks each contact through the
decision tree (`nodes`), grades contact reports (`report`), applies the hard-fail gate and the
penalties, and adds the session's signal-detection metrics (`sdt`) and first lessons (`lessons`).
Nothing is random and nothing reads the clock, so scoring the same log again gives the same bytes.

For one contact the score is built like this (docs/SCORING.md has the worked example):

1. Each node earns a mark from 0 to 1 (`nodes`). Weights come from the pack.
2. `decision` is the weighted mean of the four nodes. A hostile contact also has a report, graded
   separately; its score is `decision x (1 - w_report) + report x w_report`. Any other contact has
   no report and its score is its decision.
3. ROE hard-fail gate: an engagement that went ahead on a contact that was not hostile, or without
   a positive ID (the track classified and assessed hostile or suspect), fails the contact: its
   score is 0 whatever the nodes earned. A response the rules blocked is not a breach; it costs
   marks in Respond.
4. Each unfixed swap, split or merge that touched the contact costs `track_error_penalty` (capped).
   One that was fixed costs nothing.
5. The session score is the mean of the scored contacts' scores, less a penalty for each
   engagement on a track that followed nothing real.

A contact no sensor ever reported cannot be scored and is left out (`presented` is false). A
clutter or civil contact the operator never acted on is left out too (`worked` is false): leaving
it alone was the right call. A hostile contact never worked on scores 0.
"""

from app.contracts import SessionRecord
from app.contracts.rulepack import RulePack
from app.contracts.scenario import ScenarioSpec, Threat
from app.contracts.score import Finding, SessionScore, ThreatScore

from . import nodes
from . import report as report_grading
from .facts import POSITIVE_IDENTITIES, Call, LogFacts, read_log
from .lessons import lessons
from .sdt import metrics


def _site(spec: ScenarioSpec) -> tuple[float, float]:
    """Where bearings and ranges in a report are measured from: the first defended asset, else
    the origin."""
    if spec.assets:
        return spec.assets[0].position.x, spec.assets[0].position.y
    return 0.0, 0.0


def _hard_fail(threat: Threat, facts: LogFacts) -> Finding | None:
    """The first executed engagement that broke the rules of engagement, if any."""
    for call in nodes.executed_engagements(threat, facts):
        verdict = facts.verdict_before(call)
        if threat.disposition != "hostile":
            return Finding(
                kind="hard-fail",
                reason="finding.hard-fail.engaged-non-hostile",
                params={"t": round(call.t, 1), "track": call.track, "actual": threat.disposition},
                cost=0.0,
            )
        if not nodes.positive_id(verdict):
            return Finding(
                kind="hard-fail",
                reason="finding.hard-fail.no-positive-id",
                params={"t": round(call.t, 1), "track": call.track},
                cost=0.0,
            )
    return None


def _score_threat(
    threat: Threat, facts: LogFacts, pack: RulePack, site: tuple[float, float]
) -> ThreatScore:
    base = {
        "threat_id": threat.id,
        "label": threat.label,
        "class_id": threat.class_id,
        "disposition": threat.disposition,
    }
    first_t = facts.first_report.get(threat.id)
    if first_t is None:
        return ThreatScore(
            **base,
            presented=False,
            findings=[Finding(kind="not-presented", reason="finding.not-presented")],
        )
    hostile = threat.disposition == "hostile"
    if not hostile and not facts.calls_on(threat.id) and not nodes.blocked_attempts(threat, facts):
        return ThreatScore(
            **base,
            presented=True,
            worked=False,
            first_report_s=first_t,
            findings=[Finding(kind="not-worked", reason="finding.not-worked")],
        )
    results = [
        nodes.detect(threat, facts, pack, first_t),
        nodes.classify(threat, facts, pack, first_t),
        nodes.assess(threat, facts, pack),
        nodes.respond(threat, facts, pack, first_t),
    ]
    node_weight = sum(n.weight for n in results)
    decision = sum(n.score * n.weight for n in results) / node_weight
    grade = report_grading.grade(threat, facts, pack, first_t, site) if hostile else None
    total = decision
    if grade is not None:
        total = decision * node_weight + grade.score * pack.weights.report
    findings: list[Finding] = []

    attempts = len(nodes.blocked_attempts(threat, facts))
    if attempts:
        findings.append(
            Finding(
                kind="blocked-attempt",
                reason="finding.blocked-attempt",
                params={"attempts": attempts},
                cost=min(1.0, attempts * pack.scoring.blocked_attempt_penalty),
            )
        )
    classes = facts.calls_on(threat.id, "classify")
    if (
        threat.disposition == "clutter"
        and classes
        and classes[-1].payload.get("class_id") in nodes.DRONE_CLASSES
    ):
        findings.append(
            Finding(
                kind="false-alarm",
                reason="finding.false-alarm",
                params={
                    "given": str(classes[-1].payload.get("class_id")),
                    "actual": threat.class_id,
                },
            )
        )
    penalty = 0.0
    unfixed = [e for e in facts.errors.values() if e.restored_t is None and threat.id in e.threats]
    for error in unfixed:
        findings.append(
            Finding(
                kind="track-error",
                reason=f"finding.track-error.{error.kind}",
                params={"error_id": error.error_id, "t": round(error.t, 1)},
                cost=pack.scoring.track_error_penalty,
            )
        )
        penalty += pack.scoring.track_error_penalty
    penalty = min(penalty, pack.scoring.track_error_cap)

    fail = _hard_fail(threat, facts)
    if fail is not None:
        # validated again so the cost is rounded like every other mark (model_copy skips validation)
        cost = min(1.0, max(0.0, total))
        findings.insert(0, Finding.model_validate({**fail.model_dump(), "cost": cost}))
        score = 0.0
    else:
        score = max(0.0, total - penalty)
    return ThreatScore(
        **base,
        presented=True,
        first_report_s=first_t,
        nodes=results,
        decision=decision,
        report=grade,
        hard_fail=fail is not None,
        findings=findings,
        score=score,
    )


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _is_positive(calls: list[Call]) -> bool:
    assessed = [c for c in calls if c.action == "assess"]
    return bool(assessed) and assessed[-1].payload.get("identity") in POSITIVE_IDENTITIES


def _session_sdt(spec: ScenarioSpec, facts: LogFacts, presented: set[str]):  # type: ignore[no-untyped-def]
    hits = signals = false_alarms = noise = 0
    for threat in spec.threats:
        if threat.id not in presented:
            continue
        positive = _is_positive(facts.calls_on(threat.id))
        if threat.disposition == "hostile":
            signals += 1
            hits += positive
        else:
            noise += 1
            false_alarms += positive
    false_tracks: dict[str, list[Call]] = {}
    for call in facts.calls:
        if call.target is None and call.action == "assess":
            false_tracks.setdefault(call.track, []).append(call)
    for calls in false_tracks.values():
        noise += 1
        false_alarms += _is_positive(calls)
    return metrics(hits, signals, false_alarms, noise)


def score_events(
    spec: ScenarioSpec,
    pack: RulePack,
    events: list,  # type: ignore[type-arg]
    *,
    seed: int,
    ticks: int,
    event_head: str,
) -> SessionScore:
    if (pack.id, pack.version) != (spec.rule_pack.id, spec.rule_pack.version):
        raise ValueError("the rule pack is not the one the scenario names")
    facts = read_log(events)
    site = _site(spec)
    threats = [_score_threat(t, facts, pack, site) for t in spec.threats]
    presented = {t.threat_id for t in threats if t.presented}

    session_findings: list[Finding] = []
    false_engagements = [c for c in facts.calls if c.action == "engage" and c.target is None]
    penalty = 0.0
    for call in false_engagements:
        session_findings.append(
            Finding(
                kind="false-engagement",
                reason="finding.false-engagement",
                params={"t": round(call.t, 1), "track": call.track},
                cost=pack.scoring.false_engagement_penalty,
            )
        )
        penalty += pack.scoring.false_engagement_penalty
    penalty = min(penalty, pack.scoring.false_engagement_cap)

    scored = [t.score for t in threats if t.presented and t.score is not None]
    mean = _mean(scored)
    decisions = [
        0.0 if t.hard_fail else (t.decision or 0.0) for t in threats if t.score is not None
    ]
    reports = [t.report.score for t in threats if t.presented and t.report is not None]
    return SessionScore(
        contract="score-result.v1",
        scenario={"id": spec.id, "version": spec.version},
        rule_pack={"id": pack.id, "version": pack.version},
        seed=seed,
        ticks=ticks,
        duration_s=ticks / spec.tick_hz,
        event_head=event_head,
        threats=threats,
        sdt=_session_sdt(spec, facts, presented),
        findings=session_findings,
        score=None if mean is None else max(0.0, mean - penalty),
        decision_score=_mean(decisions),
        report_score=_mean(reports),
        lessons=lessons(threats, session_findings, pack.weights.report),
    )


def score_session(spec: ScenarioSpec, pack: RulePack, record: SessionRecord) -> SessionScore:
    if (record.scenario.id, record.scenario.version) != (spec.id, spec.version):
        raise ValueError("the session record is for a different scenario or version")
    head = record.events[-1].hash if record.events else "0" * 64
    return score_events(
        spec, pack, list(record.events), seed=record.seed, ticks=record.ticks, event_head=head
    )
