"""Track errors through the real simulation: a seeded crossing, an operator, the evaluator.

Two drones (`alpha`, `bravo`, both hostile rotary-small, in the Kestrel-based crossing scenario of
`tests/test_tracking_wiring.py`) cross 1500 m north of the radar. With seed 195 the tracker swaps
their tracks at tick 624 (T001 now follows bravo and T002 alpha); the filter undoes it by itself at
tick 696. The operator classifies, assesses and reports both tracks before the swap. Scoring the
finished log must charge the unfixed swap to both drones, charge nothing when the operator fixed
it (a relabel at tick 640) or the filter did, and give the same answer every time.
"""

from functools import cache

import pytest

from app.contracts import ActionRecord, EventRecord
from app.contracts.rulepack import RulePack
from app.contracts.score import SessionScore, ThreatScore
from app.scoring import score_events
from sim import replay
from sim.roe import load_rule_engine
from sim.world import World

from .scoring_support import baseline
from .sim_cases import act
from .test_tracking_wiring import OPERATOR, SWAP_SEED, SWAP_TICK, crossing

PENALTY = 0.15
OPERATOR_ACTIONS: list[ActionRecord] = [
    act(300, OPERATOR, "classify", track="T001", class_id="rotary-small"),
    act(310, OPERATOR, "classify", track="T002", class_id="rotary-small"),
    act(320, OPERATOR, "assess", track="T001", identity="hostile"),
    act(330, OPERATOR, "assess", track="T002", identity="hostile"),
    act(340, OPERATOR, "report", track="T001", class_id="rotary-small", count=1, confidence=0.6),
    act(350, OPERATOR, "report", track="T002", class_id="rotary-small", count=1, confidence=0.6),
]
RELABEL = act(SWAP_TICK + 16, OPERATOR, "track-relabel", track="T001", label="T002", exchange=True)


def run_session(ticks: int, extra: tuple[ActionRecord, ...] = ()) -> tuple[World, SessionScore]:
    spec, bare = crossing(SWAP_SEED)
    world = World(spec, SWAP_SEED, picture=bare.picture, roe=load_rule_engine(spec))
    replay.advance(world, ticks, [*OPERATOR_ACTIONS, *extra])
    return world, score_world(world)


def score_world(world: World) -> SessionScore:
    pack = baseline()
    assert isinstance(pack, RulePack)
    return score_events(
        world.spec,
        pack,
        list(world.log.records),
        seed=world.seed,
        ticks=world.tick,
        event_head=world.log.head,
    )


@cache
def unfixed() -> tuple[tuple[EventRecord, ...], SessionScore]:
    """Scored at tick 660: the swap (624) is open, the filter's own repair (696) has not happened."""
    world, result = run_session(660)
    return tuple(world.log.records), result


@cache
def fixed_by_operator() -> SessionScore:
    return run_session(660, (RELABEL,))[1]


def threat(result: SessionScore, threat_id: str) -> ThreatScore:
    return next(t for t in result.threats if t.threat_id == threat_id)


def swap_findings(t: ThreatScore) -> list[str]:
    return [f.reason for f in t.findings if f.kind == "track-error"]


# ---------------------------------------------------------------------------------- the setup


def test_the_log_holds_an_open_swap_between_the_two_drones() -> None:
    events, _ = unfixed()
    swaps = [e for e in events if e.type == "ledger.swap"]
    assert {e.payload["from_truth"] for e in swaps} == {"alpha", "bravo"}
    assert all(e.payload["tick"] == SWAP_TICK for e in swaps)
    assert not [e for e in events if e.type == "ledger.restored"]


def test_before_the_swap_the_operator_worked_both_real_drones() -> None:
    events, _ = unfixed()
    targets = {
        (e.payload["track"], e.payload["target"]) for e in events if e.type == "action.classify"
    }
    assert targets == {("T001", "alpha"), ("T002", "bravo")}


# ------------------------------------------------------------------------- unfixed versus fixed


def test_an_unfixed_swap_is_a_finding_on_both_drones_and_costs_each_015() -> None:
    _, result = unfixed()
    fixed = fixed_by_operator()
    for drone in ("alpha", "bravo"):
        bad, good = threat(result, drone), threat(fixed, drone)
        assert swap_findings(bad) == ["finding.track-error.swap"]
        assert swap_findings(good) == []
        assert bad.score is not None and good.score is not None
        assert good.score - bad.score == pytest.approx(PENALTY, abs=1e-4)
        assert bad.decision == good.decision  # the nodes are the same; only the penalty differs
        (finding,) = [f for f in bad.findings if f.kind == "track-error"]
        assert finding.cost == PENALTY and finding.params["t"] == SWAP_TICK / 20


def test_the_session_score_falls_by_the_same_penalty() -> None:
    _, result = unfixed()
    fixed = fixed_by_operator()
    assert result.score is not None and fixed.score is not None
    assert fixed.score - result.score == pytest.approx(PENALTY, abs=1e-4)
    assert result.decision_score == fixed.decision_score
    assert result.report_score == fixed.report_score


def test_the_operator_fix_is_logged_and_nothing_is_charged() -> None:
    world, fixed = run_session(660, (RELABEL,))
    restored = [e for e in world.log.records if e.type == "ledger.restored"]
    assert len(restored) == 1 and restored[0].payload["tick"] == SWAP_TICK + 16
    for drone in ("alpha", "bravo"):
        assert fixed.threats and not [
            f for f in threat(fixed, drone).findings if f.kind == "track-error"
        ]


def test_a_swap_the_filter_repairs_by_itself_is_not_charged_either() -> None:
    world, result = run_session(700)  # past the filter's own repair at tick 696
    assert [e.payload["tick"] for e in world.log.records if e.type == "ledger.restored"] == [696]
    for drone in ("alpha", "bravo"):
        assert swap_findings(threat(result, drone)) == []


def test_the_penalty_shows_up_as_a_lesson() -> None:
    _, result = unfixed()
    assert "lesson.track-error" in {lesson.key for lesson in result.lessons}
    assert "lesson.track-error" not in {lesson.key for lesson in fixed_by_operator().lessons}


# --------------------------------------------------------------------------------- determinism


def test_scoring_the_same_session_again_gives_the_same_bytes() -> None:
    events, result = unfixed()
    again = score_events(
        crossing(SWAP_SEED)[0],
        baseline(),
        list(events),
        seed=SWAP_SEED,
        ticks=660,
        event_head=events[-1].hash,
    )
    assert again.model_dump_json() == result.model_dump_json()


def test_running_the_session_again_scores_identically() -> None:
    _, first = run_session(660)
    _, second = run_session(660)
    assert first.model_dump_json() == second.model_dump_json()
    assert first.event_head == unfixed()[1].event_head
