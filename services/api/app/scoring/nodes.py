"""The four nodes of the decision tree for one contact: Detect, Classify, Assess, Respond.

Each function reads what the operator did on the contact (`LogFacts`) against what the contact
really was (the scenario's threat) and returns a `NodeResult`: a mark from 0 to 1, the pack's
weight, a reason key and the parameters that explain it. All marks, bands and credits come from
the rule pack's `scoring` section; timing standards from its `thresholds`.
"""

from app.contracts.rulepack import RulePack
from app.contracts.scenario import Threat
from app.contracts.score import NodeResult

from .bands import band
from .facts import POSITIVE_IDENTITIES, LogFacts, Verdict

DRONE_CLASSES = ("rotary-small", "fixed-wing-small")


def secs(value: float) -> float:
    return round(value, 1)


def detect(threat: Threat, facts: LogFacts, pack: RulePack, first_t: float) -> NodeResult:
    weight = pack.weights.detect
    calls = facts.calls_on(threat.id)
    if not calls:
        return NodeResult(
            node="detect",
            score=0.0,
            weight=weight,
            reason="detect.missed",
            params={"standard": pack.thresholds.detect_within_s},
        )
    first = calls[0]
    elapsed = first.t - first_t
    standard = pack.thresholds.detect_within_s
    score = band(elapsed, standard, pack.scoring.timing_bands)
    return NodeResult(
        node="detect",
        score=score,
        weight=weight,
        reason="detect.band",
        params={
            "seconds": secs(elapsed),
            "standard": standard,
            "first_action": first.action,
            "track": first.track,
        },
    )


def classify(threat: Threat, facts: LogFacts, pack: RulePack, first_t: float) -> NodeResult:
    weight = pack.weights.classify
    calls = facts.calls_on(threat.id, "classify")
    if not calls:
        return NodeResult(node="classify", score=0.0, weight=weight, reason="classify.missing")
    final = str(calls[-1].payload.get("class_id"))
    actual = threat.class_id
    if final == "unknown":
        return NodeResult(
            node="classify",
            score=0.0,
            weight=weight,
            reason="classify.unknown",
            params={"actual": actual},
        )
    if final != actual:
        return NodeResult(
            node="classify",
            score=0.0,
            weight=weight,
            reason="classify.wrong",
            params={"given": final, "actual": actual},
        )
    committed = next(c for c in calls if c.payload.get("class_id") == final)
    elapsed = committed.t - first_t
    standard = pack.thresholds.classify_within_s
    timing = band(elapsed, standard, pack.scoring.timing_bands)
    share = pack.scoring.classify_correct_share
    return NodeResult(
        node="classify",
        score=share + (1 - share) * timing,
        weight=weight,
        reason="classify.correct",
        params={
            "class": actual,
            "seconds": secs(elapsed),
            "standard": standard,
            "timing": timing,
            "changes": len({c.payload.get("class_id") for c in calls}) - 1,
        },
    )


def assess(threat: Threat, facts: LogFacts, pack: RulePack) -> NodeResult:
    weight = pack.weights.assess
    calls = facts.calls_on(threat.id, "assess")
    if not calls:
        return NodeResult(node="assess", score=0.0, weight=weight, reason="assess.missing")
    final = str(calls[-1].payload.get("identity"))
    credit = pack.scoring.assess_credit.get(threat.disposition, {}).get(final, 0.0)  # type: ignore[call-overload]
    reason = "assess.exact" if credit >= 1.0 else "assess.partial" if credit > 0 else "assess.wrong"
    return NodeResult(
        node="assess",
        score=credit,
        weight=weight,
        reason=reason,
        params={"given": final, "actual": threat.disposition},
    )


# --------------------------------------------------------------------------- respond


def executed_engagements(threat: Threat, facts: LogFacts) -> list:  # type: ignore[type-arg]
    return facts.calls_on(threat.id, "engage")


def blocked_attempts(threat: Threat, facts: LogFacts) -> list[Verdict]:
    return [v for v in facts.verdicts_on(threat.id, "engage") if not v.permitted]


def respond(
    threat: Threat, facts: LogFacts, pack: RulePack, first_t: float, *, breach: bool = False
) -> NodeResult:
    """Respond: for a hostile contact the best response given, its effector and its timing; for any
    other contact, holding fire. A blocked attempt costs marks either way. An engagement that broke
    the rules of engagement (`breach`, the hard-fail gate) earns nothing here."""
    weight = pack.weights.respond
    sc = pack.scoring
    attempts = len(blocked_attempts(threat, facts))
    penalty = attempts * sc.blocked_attempt_penalty
    if breach:
        return NodeResult(
            node="respond",
            score=0.0,
            weight=weight,
            reason="respond.breach",
            params={
                "engagements": len(executed_engagements(threat, facts)),
                "blocked_attempts": attempts,
            },
        )
    if threat.disposition != "hostile":
        return NodeResult(
            node="respond",
            score=max(0.0, 1.0 - penalty),
            weight=weight,
            reason="respond.hold-fire",
            params={"blocked_attempts": attempts},
        )
    engages = executed_engagements(threat, facts)
    reports = facts.calls_on(threat.id, "report")
    holds = facts.calls_on(threat.id, "hold")
    effector_factor = 1.0
    if engages:
        credit, first, reason = sc.respond_credit["engage"], engages[0], "respond.engage"
        effector = str(first.payload.get("effector_class"))
        verdict = facts.verdict_before(first)
        rule = next((r for r in pack.rules if verdict and r.id == verdict.rule_id), None)
        if rule is not None and rule.effector_classes and effector != rule.effector_classes[0]:
            effector_factor, reason = sc.effector_higher_factor, "respond.engage-higher"
        extra: dict[str, object] = {"effector": effector}
    elif reports:
        credit, first, reason = sc.respond_credit["report"], reports[0], "respond.report-only"
        extra = {}
    elif holds:
        credit, first, reason = sc.respond_credit["hold"], holds[0], "respond.hold-only"
        extra = {}
    else:
        return NodeResult(
            node="respond",
            score=0.0,
            weight=weight,
            reason="respond.none",
            params={"blocked_attempts": attempts},
        )
    elapsed = first.t - first_t
    standard = pack.thresholds.respond_within_s
    timing = band(elapsed, standard, sc.timing_bands)
    timing_factor = 1 - sc.respond_timing_share * (1 - timing)
    score = max(0.0, credit * effector_factor * timing_factor - penalty)
    return NodeResult(
        node="respond",
        score=score,
        weight=weight,
        reason=reason,
        params={
            "seconds": secs(elapsed),
            "standard": standard,
            "timing": timing,
            "blocked_attempts": attempts,
            **extra,
        },
    )


def positive_id(verdict: Verdict | None) -> bool:
    """Whether the operator had a positive ID when an engagement was permitted: the track
    classified and assessed hostile or suspect (as logged in the verdict's context)."""
    if verdict is None:
        return False
    context = verdict.context
    return (
        context.get("classification") not in (None, "unknown")
        and context.get("identity") in POSITIVE_IDENTITIES
    )
