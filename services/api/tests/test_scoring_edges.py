"""Edges of the evaluator's entry points: pack and scenario checks, a scenario with no asset, a log
that lacks a verdict, and a penalty too small to be a lesson."""

from typing import Any

import pytest

from app.contracts import SessionRecord
from app.contracts.common import PackRef
from app.scoring import score_events, score_session
from sim.eventlog import EventLog

from .scoring_support import (
    OPERATOR,
    QUAD,
    TICK_HZ,
    act,
    baseline,
    build,
    first_report,
    harrier,
    pack_with,
    score,
    truth,
)

FIELDS: dict[str, Any] = {
    "class_id": "rotary-small",
    "bearing_deg": 0,
    "range_m": 1000,
    "count": 1,
    "heading_deg": 90,
    "confidence": 1.0,
}


def test_a_pack_other_than_the_one_the_scenario_names_is_refused() -> None:
    other = baseline().model_copy(update={"id": "other-pack"})
    with pytest.raises(ValueError, match="not the one the scenario names"):
        score([first_report(30, QUAD)], pack=other)
    newer = baseline().model_copy(update={"version": "2.0.0"})
    with pytest.raises(ValueError, match="not the one the scenario names"):
        score([first_report(30, QUAD)], pack=newer)


def test_without_a_defended_asset_reports_are_measured_from_the_origin() -> None:
    spec = harrier().model_copy(update={"assets": []})
    steps = [first_report(30, QUAD), act(50, "report", "T001", QUAD, truth=truth(), **FIELDS)]
    (threat,) = [t for t in score(steps, spec=spec).threats if t.threat_id == QUAD]
    assert threat.report is not None and threat.report.quality == 1.0


def test_an_engagement_with_no_verdict_in_the_log_has_no_positive_id() -> None:
    log = EventLog(TICK_HZ)
    log.append(
        600, "ledger.first_report", "sim", {"drone": QUAD, "sensor": "r", "modality": "radar"}
    )
    log.append(
        1200,
        "action.engage",
        OPERATOR,
        {"track": "T001", "target": QUAD, "effector_class": "ec-a"},
    )
    (threat,) = [t for t in score(list(log.records)).threats if t.threat_id == QUAD]
    assert threat.hard_fail and threat.score == 0.0
    assert threat.findings[0].reason == "finding.hard-fail.no-positive-id"


def test_a_false_engagement_too_small_to_matter_is_not_a_lesson() -> None:
    steps = [
        first_report(30, QUAD),
        act(35, "classify", "T001", QUAD, class_id="rotary-small"),
        act(37, "assess", "T001", QUAD, identity="hostile"),
        act(50, "report", "T001", QUAD, truth=truth(), **FIELDS),
        act(60, "engage", "T001", QUAD, effector_class="ec-a"),
        act(70, "engage", "T099", None, effector_class="ec-a"),
    ]
    tiny = score(steps, pack=pack_with(false_engagement_penalty=0.001))
    assert [x.key for x in tiny.lessons if x.key == "lesson.false-engagement"] == []
    assert [f.cost for f in tiny.findings] == [0.001]
    assert "lesson.false-engagement" in {x.key for x in score(steps).lessons}


def record_for(steps: list, **over: object) -> SessionRecord:  # type: ignore[type-arg]
    events = build(steps)
    data: dict[str, object] = {
        "contract": "session-record.v1",
        "scenario": PackRef(id="harrier-morning-watch", version="1.0.0"),
        "seed": 7,
        "ticks": 600,
        "actions": [],
        "events": events,
        "final_state_hash": "a" * 64,
    }
    data.update(over)
    return SessionRecord.model_validate(data)


def test_score_session_scores_the_stored_events_with_the_records_seed_ticks_and_head() -> None:
    steps = [first_report(30, QUAD), act(35, "classify", "T001", QUAD, class_id="rotary-small")]
    record = record_for(steps)
    result = score_session(harrier(), baseline(), record)
    assert (result.seed, result.ticks, result.event_head) == (7, 600, record.events[-1].hash)
    direct = score_events(
        harrier(), baseline(), list(record.events), seed=7, ticks=600, event_head=result.event_head
    )
    assert result.model_dump_json() == direct.model_dump_json()


def test_score_session_of_an_empty_log_scores_nothing() -> None:
    result = score_session(harrier(), baseline(), record_for([]))
    assert result.event_head == "0" * 64 and result.score is None


def test_score_session_refuses_a_record_for_another_scenario() -> None:
    record = record_for([], scenario=PackRef(id="kestrel-dawn-approach", version="1.0.0"))
    with pytest.raises(ValueError, match="different scenario"):
        score_session(harrier(), baseline(), record)
    stale = record_for([], scenario=PackRef(id="harrier-morning-watch", version="0.9.0"))
    with pytest.raises(ValueError, match="different scenario"):
        score_session(harrier(), baseline(), stale)
