"""Property tests for the evaluator (hypothesis).

A *plan* is what an operator did on one contact: when, which class, which identity, whether a
report, which response. `steps_for` turns it into an event log (the verdict context is built the
way the world builds it, from the operator's own earlier calls), so the properties run on arbitrary
sessions without the simulator. `breached` is an independent model of the ROE hard-fail rule,
written from docs/SCORING.md and not from the evaluator.
"""

from dataclasses import dataclass
from typing import Any

import pytest
from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st

from app.contracts.rulepack import TimingBand
from app.contracts.score import SessionScore, ThreatScore
from app.scoring.bands import band

from .scoring_support import (
    CIVIL,
    QUAD,
    Step,
    act,
    baseline,
    build,
    first_report,
    merge,
    restored,
    score,
    split,
    swap,
    truth,
)

PROFILE = settings(
    max_examples=120,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much],
)

FIRST = 30.0  # when the hostile was first reported
SEC = st.integers(0, 2400).map(lambda k: k / 20)  # a delay in seconds, on the 20 Hz tick grid
CLASSES = st.sampled_from(["rotary-small", "fixed-wing-small", "bird", "unknown"])
IDENTITIES = st.sampled_from(["hostile", "suspect", "unknown", "neutral", "friend"])
POSITIVE = ("hostile", "suspect")


@dataclass(frozen=True)
class Plan:
    class_id: str | None
    class_at: float
    identity: str | None
    identity_at: float
    report: dict[str, Any] | None
    report_at: float
    response: str  # engage-a | engage-b | hold | none
    response_at: float
    designate_at: float | None = None


def steps_for(
    plan: Plan,
    *,
    target: str = QUAD,
    track: str = "T001",
    first: float = FIRST,
    civil: bool = False,
) -> list[Step]:
    steps: list[Step] = [first_report(first, target)]
    if plan.designate_at is not None:
        steps.append(act(first + plan.designate_at, "designate", track, target))
    if plan.class_id is not None:
        steps.append(act(first + plan.class_at, "classify", track, target, class_id=plan.class_id))
    if plan.identity is not None:
        steps.append(act(first + plan.identity_at, "assess", track, target, identity=plan.identity))
    if plan.report is not None:
        t = truth(disposition="civil-permitted") if civil else truth()
        steps.append(act(first + plan.report_at, "report", track, target, truth=t, **plan.report))
    when = first + plan.response_at
    if plan.response in ("engage-a", "engage-b"):
        effector = "ec-a" if plan.response == "engage-a" else "ec-b"
        steps.append(act(when, "engage", track, target, effector_class=effector))
    elif plan.response == "hold":
        steps.append(act(when, "hold", track, target))
    return steps


def breached(steps: list[Step]) -> bool:
    """Independent model of the hard-fail rule for a hostile contact: some executed engagement
    came when the track was not both classified (not unknown) and assessed hostile or suspect."""
    identity: str | None = None
    classification: str | None = None
    for step in sorted(steps, key=lambda s: s["t"]):
        if step["op"] != "act" or step.get("permitted", True) is False:
            continue
        if step["action"] == "classify":
            classification = step["payload"]["class_id"]
        elif step["action"] == "assess":
            identity = step["payload"]["identity"]
        elif step["action"] == "engage" and (
            classification in (None, "unknown") or identity not in POSITIVE
        ):
            return True
    return False


REPORTS = st.none() | st.fixed_dictionaries(
    {},
    optional={
        "class_id": CLASSES,
        "bearing_deg": st.floats(0, 359.9, allow_nan=False),
        "range_m": st.floats(0, 50_000, allow_nan=False),
        "count": st.integers(1, 99),
        "heading_deg": st.floats(0, 359.9, allow_nan=False),
        "confidence": st.floats(0, 1, allow_nan=False),
    },
)


@st.composite
def plans(draw: st.DrawFn) -> Plan:
    return Plan(
        class_id=draw(st.none() | CLASSES),
        class_at=draw(SEC),
        identity=draw(st.none() | IDENTITIES),
        identity_at=draw(SEC),
        report=draw(REPORTS),
        report_at=draw(SEC),
        response=draw(st.sampled_from(["engage-a", "engage-b", "hold", "none"])),
        response_at=draw(SEC),
        designate_at=draw(st.none() | SEC),
    )


def quad_of(result: SessionScore) -> ThreatScore:
    return next(t for t in result.threats if t.threat_id == QUAD)


def quad_score(steps: list[Step]) -> float:
    value = quad_of(score(steps)).score
    assert value is not None
    return value


# ---------------------------------------------------------------- the ROE breach never pays


@PROFILE
@given(plans())
def test_a_hard_fail_is_exactly_an_engagement_without_a_positive_id(plan: Plan) -> None:
    steps = steps_for(plan)
    threat = quad_of(score(steps))
    assert threat.hard_fail == breached(steps)
    if threat.hard_fail:
        assert threat.score == 0.0
        assert threat.findings[0].reason == "finding.hard-fail.no-positive-id"
    else:
        assert not any(f.kind == "hard-fail" for f in threat.findings)


@PROFILE
@given(plans())
def test_any_engagement_on_a_civil_contact_scores_zero_and_holding_does_not(plan: Plan) -> None:
    steps = steps_for(plan, target=CIVIL, track="T002", first=8.0, civil=True)
    (threat,) = [t for t in score(steps).threats if t.threat_id == CIVIL and t.presented]
    engaged = plan.response.startswith("engage")
    assert threat.hard_fail == engaged
    if engaged:
        assert threat.score == 0.0
        assert threat.findings[0].reason == "finding.hard-fail.engaged-non-hostile"
    elif threat.score is not None:
        assert threat.score >= 0.0


def ticks(low: int, high: int) -> st.SearchStrategy[float]:
    return st.integers(low, high).map(lambda k: k / 20)


@st.composite
def breach_and_compliant(draw: st.DrawFn) -> tuple[Plan, Plan]:
    """A rushed breach and a compliant response given strictly later."""
    rushed_at = draw(ticks(0, 600))
    kind = draw(st.sampled_from(["no-class", "unknown-class", "no-identity", "weak-identity"]))
    known = st.sampled_from(["rotary-small", "fixed-wing-small", "bird"])
    class_id = {"no-class": None, "unknown-class": "unknown"}.get(kind) or draw(known)
    identity = {"no-identity": None}.get(kind, draw(st.sampled_from(POSITIVE)))
    if kind == "weak-identity":
        identity = draw(st.sampled_from(["unknown", "neutral", "friend"]))
    top = round(rushed_at * 20)
    breach = Plan(
        class_id=class_id if kind != "no-class" else None,
        class_at=draw(ticks(0, top)),
        identity=identity,
        identity_at=draw(ticks(0, top)),
        report=draw(REPORTS),
        report_at=draw(SEC),
        response=draw(st.sampled_from(["engage-a", "engage-b"])),
        response_at=rushed_at,
    )
    later = rushed_at + draw(st.integers(1, 1200)) / 20
    limit = round(later * 20)
    compliant = Plan(
        class_id=draw(known),
        class_at=draw(ticks(0, limit)),
        identity=draw(st.sampled_from(POSITIVE)),
        identity_at=draw(ticks(0, limit)),
        report=draw(REPORTS),
        report_at=draw(SEC),
        response=draw(st.sampled_from(["engage-a", "engage-b", "hold", "none"])),
        response_at=later,
    )
    return breach, compliant


@PROFILE
@given(breach_and_compliant())
def test_a_rushed_roe_breach_never_beats_a_slower_compliant_response(
    pair: tuple[Plan, Plan],
) -> None:
    breach, compliant = pair
    a, b = steps_for(breach), steps_for(compliant)
    assert breached(a) and not breached(b)  # the generators do what they say
    result_a, result_b = score(a), score(b)
    threat_a, threat_b = quad_of(result_a), quad_of(result_b)
    assert threat_a.hard_fail and not threat_b.hard_fail
    assert threat_a.score == 0.0
    assert threat_a.score <= threat_b.score  # type: ignore[operator]
    assert result_a.score is not None and result_b.score is not None
    assert result_a.score <= result_b.score
    assert result_a.decision_score == 0.0  # the decision of a hard-failed contact counts as 0


@PROFILE
@given(plans(), st.integers(1, 1200).map(lambda k: k / 20))
def test_a_breach_is_not_redeemed_by_a_compliant_engagement_afterwards(
    plan: Plan, lag: float
) -> None:
    assume(breached(steps_for(plan)))
    steps = steps_for(plan)
    steps += [
        act(FIRST + plan.response_at + lag, "classify", "T001", QUAD, class_id="rotary-small"),
        act(FIRST + plan.response_at + lag + 1, "assess", "T001", QUAD, identity="hostile"),
        act(FIRST + plan.response_at + lag + 2, "engage", "T001", QUAD, effector_class="ec-a"),
    ]
    assert quad_of(score(steps)).score == 0.0


# --------------------------------------------------------------------------- ranges and bounds


def walk_numbers(value: Any, path: str = "") -> list[tuple[str, float]]:
    out: list[tuple[str, float]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            out += walk_numbers(item, f"{path}.{key}")
    elif isinstance(value, list):
        for i, item in enumerate(value):
            out += walk_numbers(item, f"{path}[{i}]")
    elif isinstance(value, float) and not isinstance(value, bool):
        out.append((path, value))
    return out


@st.composite
def messy_sessions(draw: st.DrawFn) -> list[Step]:
    """A hostile plan, a civil plan, a bird, false tracks, blocked tries and track errors."""
    steps = steps_for(draw(plans()))
    steps += steps_for(draw(plans()), target=CIVIL, track="T002", first=8.0, civil=True)
    steps += steps_for(draw(plans()), target="contact-bird-1", track="T011", first=5.0)
    for i in range(draw(st.integers(0, 3))):
        t = draw(SEC) + 10
        if draw(st.booleans()):
            steps.append(act(t, "assess", f"T09{i}", None, identity="hostile"))
        else:
            steps.append(act(t, "engage", f"T09{i}", None, effector_class="ec-a"))
    for _ in range(draw(st.integers(0, 3))):
        steps.append(
            act(draw(SEC) + 10, "engage", "T001", QUAD, permitted=False, effector_class="ec-a")
        )
    for i, kind in enumerate(
        draw(st.lists(st.sampled_from(["swap", "split", "merge"]), max_size=4))
    ):
        t = draw(SEC) + 10
        if kind == "swap":
            steps.append(swap(t, i + 1, QUAD, CIVIL))
        elif kind == "split":
            steps.append(split(t, i + 1, QUAD))
        else:
            steps.append(merge(t, i + 1, CIVIL, QUAD))
        if draw(st.booleans()):
            steps.append(restored(t + 5, i + 1, kind))
    return steps


@PROFILE
@given(messy_sessions())
def test_every_mark_is_a_fraction_and_the_session_is_consistent(steps: list[Step]) -> None:
    result = score(steps)
    for path, value in walk_numbers(result.model_dump(mode="json")):
        if any(path.endswith(s) for s in (".seconds", ".duration_s", ".first_report_s", ".t")):
            continue
        if path.split(".")[-1] in (
            "standard",
            "tolerance_m",
            "tolerance_deg",
            "error_m",
            "error_deg",
            "d_prime",
            "criterion",
            "weight",
        ):
            continue
        assert 0.0 <= value <= 1.0, path
    scored = [t.score for t in result.threats if t.score is not None]
    if scored:
        assert result.score is not None and 0.0 <= result.score <= max(scored)
    else:
        assert result.score is None
    assert len(result.lessons) <= 3
    for threat in result.threats:
        if threat.hard_fail:
            assert threat.score == 0.0
        if threat.score is not None:
            assert threat.presented and 0.0 <= threat.score <= 1.0


@PROFILE
@given(messy_sessions())
def test_scoring_a_log_twice_gives_byte_identical_json(steps: list[Step]) -> None:
    events = build(steps)
    first = score(events).model_dump_json()
    assert score(events).model_dump_json() == first
    assert score(build(steps)).model_dump_json() == first  # a fresh build of the same steps


# ----------------------------------------------------------------------- timing never pays


BANDS = st.lists(
    st.tuples(st.floats(0.1, 20, allow_nan=False), st.floats(0, 1, allow_nan=False)),
    min_size=1,
    max_size=6,
).map(
    lambda rows: [
        TimingBand(max_factor=f, score=s)
        for f, s in zip(
            sorted(f for f, _ in rows), sorted((s for _, s in rows), reverse=True), strict=True
        )
    ]
)


@PROFILE
@given(BANDS, st.floats(0, 500, allow_nan=False), st.floats(0, 500, allow_nan=False))
def test_a_slower_time_never_earns_a_higher_band_mark(
    bands: list[TimingBand], a: float, b: float
) -> None:
    fast, slow = sorted((a, b))
    assert band(slow, 10, bands) <= band(fast, 10, bands)
    assert 0.0 <= band(fast, 10, bands) <= max(x.score for x in bands)


@PROFILE
@given(st.floats(0, 12, allow_nan=False), st.floats(0, 500, allow_nan=False))
def test_faster_than_the_standard_earns_exactly_what_the_standard_earns(
    fast: float, slow: float
) -> None:
    bands = baseline().scoring.timing_bands
    assert band(fast, 12, bands) == band(12, 12, bands) == 1.0
    assert band(max(slow, 12), 12, bands) <= band(fast, 12, bands)


def _detect(delay: float) -> list[Step]:
    return [first_report(FIRST, QUAD), act(FIRST + delay, "designate", "T001", QUAD)]


def _classify(delay: float) -> list[Step]:
    return [
        first_report(FIRST, QUAD),
        act(FIRST + 1, "designate", "T001", QUAD),
        act(FIRST + delay, "classify", "T001", QUAD, class_id="rotary-small"),
    ]


def _respond(delay: float) -> list[Step]:
    return [
        first_report(FIRST, QUAD),
        act(FIRST + 1, "classify", "T001", QUAD, class_id="rotary-small"),
        act(FIRST + 2, "assess", "T001", QUAD, identity="hostile"),
        act(FIRST + 2 + delay, "engage", "T001", QUAD, effector_class="ec-a"),
    ]


def _report(delay: float) -> list[Step]:
    fields: dict[str, Any] = {
        "class_id": "rotary-small",
        "bearing_deg": 0,
        "range_m": 1000,
        "count": 1,
        "heading_deg": 90,
        "confidence": 1.0,
    }
    return [
        first_report(FIRST, QUAD),
        act(FIRST + 1, "classify", "T001", QUAD, class_id="rotary-small"),
        act(FIRST + 2, "assess", "T001", QUAD, identity="hostile"),
        act(FIRST + 2 + 0.05, "engage", "T001", QUAD, effector_class="ec-a"),
        act(FIRST + delay, "report", "T001", QUAD, truth=truth(), **fields),
    ]


#: (steps for a delay, the standard in seconds, the earliest delay that is still compliant)
TIMINGS = {
    "detect": (_detect, 12.0, 0.0),
    "classify": (_classify, 25.0, 1.0),
    "respond": (_respond, 45.0, 0.05),
    "report": (_report, 40.0, 2.1),
}


LONG = st.integers(0, 6000).map(lambda k: k / 20)


@PROFILE
@given(st.sampled_from(sorted(TIMINGS)), LONG, LONG)
def test_a_contact_never_scores_more_for_being_slower_and_never_more_for_being_faster_than_the_standard(
    name: str, a: float, b: float
) -> None:
    make, standard, earliest = TIMINGS[name]
    fast, slow = sorted((max(a, earliest), max(b, earliest)))
    quick, late = quad_score(make(fast)), quad_score(make(slow))
    assert late <= quick
    if slow + (2 if name == "respond" else 0) <= standard:
        assert late == quick  # inside the standard, fast and slow earn the same


# ---------------------------------------------------------- penalties never raise a score


@PROFILE
@given(
    plans(), st.integers(0, 4000).map(lambda k: k / 20), st.sampled_from(["swap", "split", "merge"])
)
def test_an_unfixed_track_error_never_raises_a_score_and_a_fixed_one_changes_nothing(
    plan: Plan, when: float, kind: str
) -> None:
    base = steps_for(plan)
    error = {
        "swap": swap(when, 1, QUAD, CIVIL),
        "split": split(when, 1, QUAD),
        "merge": merge(when, 1, CIVIL, QUAD),
    }[kind]
    before, unfixed = score(base), score([*base, error])
    fixed = score([*base, error, restored(when + 1, 1, kind)])
    assert quad_of(unfixed).score is not None and quad_of(before).score is not None
    assert quad_of(unfixed).score <= quad_of(before).score  # type: ignore[operator]
    assert unfixed.score is not None and before.score is not None
    assert unfixed.score <= before.score
    assert fixed.model_dump(exclude={"event_head"}) == before.model_dump(exclude={"event_head"})


@PROFILE
@given(plans(), st.lists(st.integers(0, 4000).map(lambda k: k / 20), min_size=1, max_size=6))
def test_unfixed_track_errors_cost_at_most_the_cap(plan: Plan, times: list[float]) -> None:
    base = steps_for(plan)
    errors = [swap(t, i + 1, QUAD, CIVIL) for i, t in enumerate(times)]
    before = quad_of(score(base)).score
    after = quad_of(score([*base, *errors])).score
    assert before is not None and after is not None
    assert before - after <= baseline().scoring.track_error_cap + 1e-4


@PROFILE
@given(plans(), st.lists(st.integers(0, 4000).map(lambda k: k / 20), min_size=1, max_size=5))
def test_a_blocked_attempt_never_raises_a_score_and_is_never_a_hard_fail(
    plan: Plan, times: list[float]
) -> None:
    base = steps_for(plan)
    blocked = [
        act(FIRST + t, "engage", "T001", QUAD, permitted=False, effector_class="ec-a")
        for t in times
    ]
    before, after = score(base), score([*base, *blocked])
    threat_before, threat_after = quad_of(before), quad_of(after)
    assert threat_after.hard_fail == threat_before.hard_fail  # a blocked response is no breach
    assert threat_after.score is not None and threat_before.score is not None
    assert threat_after.score <= threat_before.score
    for node_before, node_after in zip(threat_before.nodes, threat_after.nodes, strict=True):
        assert node_after.score <= node_before.score
    assert after.score is not None and before.score is not None
    assert after.score <= before.score
    if not threat_after.hard_fail:
        assert any(f.kind == "blocked-attempt" for f in threat_after.findings)


@PROFILE
@given(plans(), st.integers(0, 400).map(lambda k: k / 20))
def test_an_engagement_on_a_false_track_never_raises_the_session_score(
    plan: Plan, when: float
) -> None:
    base = steps_for(plan)
    extra = [act(FIRST + when, "engage", "T099", None, effector_class="ec-a")]
    before, after = score(base), score([*base, *extra])
    assert before.score is not None and after.score is not None
    assert after.score <= before.score
    assert quad_of(after).score == quad_of(before).score  # the contact itself is untouched


@pytest.mark.parametrize("seed", [1, 2])
def test_the_seed_and_ticks_are_recorded_not_scored(seed: int) -> None:
    steps = steps_for(Plan("rotary-small", 5, "hostile", 7, None, 0, "engage-a", 20))
    a, b = score(steps, seed=seed, ticks=1000), score(steps, seed=3, ticks=2000)
    assert (a.seed, a.ticks, a.duration_s) == (seed, 1000, 50.0)
    assert quad_of(a).score == quad_of(b).score
