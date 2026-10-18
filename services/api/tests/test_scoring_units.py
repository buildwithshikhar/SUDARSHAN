"""Unit tests for the evaluator's parts: timing bands, the log reader and the lessons."""

from typing import Any

import pytest

from app.contracts.rulepack import TimingBand
from app.scoring.bands import band
from app.scoring.facts import ACTION_TYPES, WORKING_ACTIONS, read_log
from app.scoring.lessons import LESSON_COUNT, MIN_COST

from .scoring_support import (
    BIRDS,
    CIVIL,
    OPERATOR,
    QUAD,
    TICK_HZ,
    Step,
    act,
    baseline,
    build,
    first_report,
    merge,
    noise,
    pack_with,
    restored,
    score,
    split,
    swap,
)

BANDS = baseline().scoring.timing_bands


# ------------------------------------------------------------------------------------- bands


@pytest.mark.parametrize(
    ("elapsed", "mark"),
    [
        (0, 1.0),
        (6, 1.0),
        (12, 1.0),  # factor exactly 1.0: first band, and nothing earns more
        (12.01, 0.75),
        (24, 0.75),  # exactly 2.0
        (24.01, 0.5),
        (36, 0.5),  # exactly 3.0
        (36.01, 0.25),
        (60, 0.25),  # exactly 5.0
        (60.01, 0.0),
        (10_000, 0.0),
    ],
)
def test_bands_against_a_twelve_second_standard(elapsed: float, mark: float) -> None:
    assert band(elapsed, 12, BANDS) == mark


def test_faster_than_the_standard_never_earns_more_than_the_standard() -> None:
    assert band(0.0, 12, BANDS) == band(12, 12, BANDS) == 1.0
    assert band(-5.0, 12, BANDS) == 1.0  # a negative interval is treated as zero


def test_bands_are_read_by_factor_not_by_list_order() -> None:
    shuffled = [BANDS[2], BANDS[0], BANDS[3], BANDS[1]]
    for elapsed in (3, 20, 30, 50, 90):
        assert band(elapsed, 10, shuffled) == band(elapsed, 10, BANDS)


def test_no_bands_earns_nothing_and_a_custom_pack_changes_the_marks() -> None:
    assert band(1, 10, []) == 0.0
    custom = [TimingBand(max_factor=1.0, score=0.9), TimingBand(max_factor=2.0, score=0.1)]
    assert [band(t, 10, custom) for t in (5, 10, 15, 20, 21)] == [0.9, 0.9, 0.1, 0.1, 0.0]


def test_the_standard_scales_the_bands() -> None:
    assert band(25, 25, BANDS) == 1.0 and band(50, 25, BANDS) == 0.75
    assert band(100, 45, BANDS) == 0.5  # factor 2.22


# -------------------------------------------------------------------------------------- facts


def test_a_log_of_unrelated_events_holds_no_facts() -> None:
    facts = read_log(
        build(
            [
                noise(1, "sim.started"),
                noise(2, "track.update", id="T001"),
                noise(3, "action.rejected", reason="no live track"),
                noise(4, "assist.assess", track="T001"),
            ]
        )
    )
    assert (facts.first_report, facts.calls, facts.verdicts, facts.errors) == ({}, [], [], {})


def test_action_events_become_calls_with_their_track_target_and_payload() -> None:
    facts = read_log(
        build(
            [
                act(10, "classify", "T001", QUAD, class_id="bird"),
                act(11, "assess", "T009", None, identity="hostile"),
            ]
        )
    )
    first, second = facts.calls
    assert (first.action, first.track, first.target, first.t) == ("classify", "T001", QUAD, 10.0)
    assert first.payload["class_id"] == "bird"
    assert (second.action, second.track, second.target) == ("assess", "T009", None)
    assert facts.calls_on(QUAD) == [first]
    assert facts.calls_on(QUAD, "assess") == []
    assert facts.calls_on(QUAD, "assess", "classify") == [first]
    assert facts.calls_on("contact-civil") == []


def test_an_action_without_a_target_key_is_a_call_on_no_real_drone() -> None:
    from sim.eventlog import EventLog

    log = EventLog(TICK_HZ)
    log.append(200, "action.hold", OPERATOR, {"track": "T001"})  # an old log: no target at all
    log.append(220, "action.engage", OPERATOR, {"track": "T001", "effector_class": "ec-a"})
    facts = read_log(log.records)
    assert [(c.action, c.target) for c in facts.calls] == [("hold", None), ("engage", None)]
    assert facts.calls_on(QUAD) == []


PAYLOADS: dict[str, dict[str, Any]] = {
    "classify": {"class_id": "bird"},
    "assess": {"identity": "hostile"},
    "engage": {"effector_class": "ec-a"},
}


def test_every_working_action_is_read_and_a_track_command_is_not() -> None:
    assert {f"action.{a}" for a in WORKING_ACTIONS} == ACTION_TYPES
    steps = [noise(5, "action.track_relabel", track="T001", label="T002")]
    steps += [
        act(10 + i, a, "T001", QUAD, **PAYLOADS.get(a, {})) for i, a in enumerate(WORKING_ACTIONS)
    ]
    facts = read_log(build(steps))
    assert [c.action for c in facts.calls] == list(WORKING_ACTIONS)


def test_a_blocked_response_is_a_verdict_with_no_action() -> None:
    facts = read_log(
        build(
            [
                act(
                    10, "engage", "T001", QUAD, permitted=False, effector_class="ec-a", rule_id="r"
                ),
            ]
        )
    )
    assert facts.calls == []
    (verdict,) = facts.verdicts
    assert (verdict.action, verdict.track, verdict.target) == ("engage", "T001", QUAD)
    assert verdict.permitted is False and verdict.effector_class == "ec-a"
    assert verdict.rule_id == "r"
    assert facts.verdicts_on(QUAD, "engage") == [verdict]
    assert facts.verdicts_on(QUAD, "hold") == []
    assert facts.verdicts_on(CIVIL, "engage") == []


def test_a_verdict_keeps_its_context_and_a_missing_one_reads_as_empty() -> None:
    from sim.eventlog import EventLog

    log = EventLog(TICK_HZ)
    log.append(
        20,
        "roe.verdict",
        OPERATOR,
        {"action": "hold", "track": "T001", "target": None, "permitted": True},
    )
    (bare,) = read_log(log.records).verdicts
    assert bare.context == {} and bare.effector_class is None and bare.rule_id is None
    assert bare.target is None
    (full,) = read_log(
        build([act(10, "classify", "T001", QUAD, class_id="bird", context={"zone_role": "inner"})])
    ).verdicts
    assert full.context == {
        "identity": None,
        "classification": None,
        "zone_role": "inner",
        "confidence": 0.9,
    }


def test_the_verdict_for_an_action_is_the_last_one_before_it_on_that_track_and_action() -> None:
    facts = read_log(
        build(
            [
                act(10, "engage", "T001", QUAD, permitted=False, effector_class="ec-a"),
                act(20, "assess", "T001", QUAD, identity="hostile"),
                act(30, "engage", "T001", QUAD, effector_class="ec-a"),
                act(40, "engage", "T002", CIVIL, permitted=False, effector_class="ec-a"),
            ]
        )
    )
    (engage,) = [c for c in facts.calls if c.action == "engage"]
    verdict = facts.verdict_before(engage)
    assert verdict is not None and verdict.t == 30.0 and verdict.permitted
    assert verdict.context["identity"] == "hostile"
    (assess,) = [c for c in facts.calls if c.action == "assess"]
    verdict = facts.verdict_before(assess)
    assert verdict is not None and verdict.action == "assess"


def test_an_action_with_no_verdict_before_it_has_none() -> None:
    from sim.eventlog import EventLog

    log = EventLog(TICK_HZ)
    log.append(200, "action.engage", OPERATOR, {"track": "T001", "target": QUAD})
    (call,) = read_log(log.records).calls
    assert read_log(log.records).verdict_before(call) is None


def test_the_first_report_of_a_drone_is_kept_and_a_later_one_ignored() -> None:
    facts = read_log(
        build(
            [first_report(30, QUAD), first_report(35, QUAD, "ir-1", "ir"), first_report(8, CIVIL)]
        )
    )
    assert facts.first_report == {QUAD: 30.0, CIVIL: 8.0}


def test_track_errors_are_read_and_a_restore_marks_the_one_it_names() -> None:
    facts = read_log(
        build(
            [
                swap(10, 1, QUAD, CIVIL),
                split(11, 2, QUAD),
                merge(12, 3, CIVIL, QUAD),
                restored(20, 2, "split"),
                restored(21, 99),  # an error the log never opened: ignored
            ]
        )
    )
    assert sorted(facts.errors) == [1, 2, 3]
    swap_error, split_error, merge_error = (facts.errors[i] for i in (1, 2, 3))
    assert (swap_error.kind, swap_error.threats, swap_error.restored_t) == (
        "swap",
        [CIVIL, QUAD],
        None,
    )
    assert (split_error.kind, split_error.threats, split_error.restored_t) == (
        "split",
        [QUAD],
        20.0,
    )
    assert (merge_error.kind, merge_error.threats) == ("merge", [CIVIL, QUAD])


def test_a_track_error_that_names_no_real_drone_touches_no_contact() -> None:
    from sim.eventlog import EventLog

    log = EventLog(TICK_HZ)
    log.append(20, "ledger.swap", "sim", {"error_id": 1, "from_truth": None, "to_truth": QUAD})
    log.append(21, "ledger.split", "sim", {"error_id": 2})
    log.append(
        22, "ledger.merge", "sim", {"error_id": 3, "truth_dropped": QUAD, "truth_survivor": QUAD}
    )
    errors = read_log(log.records).errors
    assert errors[1].threats == [QUAD]
    assert errors[2].threats == []
    assert errors[3].threats == [QUAD]  # the same drone twice counts once


# ------------------------------------------------------------------------------------ lessons

STEM = [
    first_report(30, QUAD),
    act(35, "classify", "T001", QUAD, class_id="rotary-small"),
    act(37, "assess", "T001", QUAD, identity="hostile"),
]


def test_a_perfect_run_has_no_lessons() -> None:
    from .scoring_support import truth

    steps = [
        *STEM,
        act(
            50,
            "report",
            "T001",
            QUAD,
            truth=truth(),
            class_id="rotary-small",
            bearing_deg=0,
            range_m=1000,
            count=1,
            heading_deg=90,
            confidence=1.0,
        ),
        act(60, "engage", "T001", QUAD, effector_class="ec-a"),
    ]
    result = score(steps)
    assert result.score == 1.0 and result.lessons == []


def test_nothing_presented_has_no_lessons() -> None:
    assert score([]).lessons == []


def test_at_most_three_lessons_the_costliest_first() -> None:
    result = score([first_report(30, QUAD)])  # nothing done: five nodes and a report all lost
    assert LESSON_COUNT == 3 and len(result.lessons) == 3
    costs = [lesson.cost for lesson in result.lessons]
    assert costs == sorted(costs, reverse=True) == [0.25, 0.25, 0.2]
    assert [lesson.key for lesson in result.lessons] == [
        "lesson.detect.missed",
        "lesson.classify.missing",
        "lesson.respond.none",
    ]


def test_ties_go_to_the_earlier_contact_then_the_earlier_node() -> None:
    steps = [
        first_report(5, BIRDS[0]),
        first_report(6, BIRDS[1]),
        act(8, "assess", "T011", BIRDS[0], identity="neutral"),  # classify missing on both
        act(9, "assess", "T012", BIRDS[1], identity="neutral"),
    ]
    result = score(steps)
    keys = [(lesson.key, lesson.threat_id) for lesson in result.lessons]
    assert keys == [
        ("lesson.classify.missing", BIRDS[0]),
        ("lesson.classify.missing", BIRDS[1]),
    ]
    assert result.lessons[0].cost == result.lessons[1].cost == pytest.approx(0.25 / 0.85, abs=1e-4)


def test_a_lesson_carries_the_contacts_label_and_the_nodes_parameters() -> None:
    result = score([*STEM[:2], act(40, "assess", "T001", QUAD, identity="suspect")])
    lesson = next(x for x in result.lessons if x.key == "lesson.respond.none")
    assert lesson.threat_id == QUAD
    assert lesson.params["threat"] == {"en": "Contact quad", "hi": "संपर्क क्वाड"}
    assert lesson.params["blocked_attempts"] == 0


def test_a_loss_below_the_floor_is_not_a_lesson() -> None:
    assert MIN_COST == 0.005
    pack = pack_with(respond_timing_share=0.05)  # an engage in the 0.75 band now loses 0.0025
    steps = [*STEM, act(120, "engage", "T001", QUAD, effector_class="ec-a")]
    keys = {x.key for x in score(steps, pack=pack).lessons}
    assert "lesson.respond.engage" not in keys
    assert "lesson.respond.engage" in {x.key for x in score(steps).lessons}  # 0.015 at 0.3


def test_a_correct_but_slow_class_is_a_lesson_and_an_exact_assess_never_is() -> None:
    from .scoring_support import truth

    report = act(
        100,
        "report",
        "T001",
        QUAD,
        truth=truth(),
        class_id="rotary-small",
        bearing_deg=0,
        range_m=1000,
        count=1,
        heading_deg=90,
        confidence=1.0,
    )
    steps = [
        first_report(30, QUAD),
        act(35, "designate", "T001", QUAD),
        act(92.5, "classify", "T001", QUAD, class_id="rotary-small"),  # 62.5 s: band 0.5
        act(93, "assess", "T001", QUAD, identity="hostile"),
        report,
        act(100, "engage", "T001", QUAD, effector_class="ec-a"),
    ]
    lessons = score(steps).lessons
    assert not any(x.key in ("lesson.assess.exact", "lesson.respond.hold-fire") for x in lessons)
    lesson = next(x for x in lessons if x.key == "lesson.classify.correct")
    assert lesson.cost == 0.0375  # (1 - 0.85) x 0.25
    assert lesson.params["timing"] == 0.5


def test_a_hard_fail_is_one_lesson_and_its_nodes_are_not() -> None:
    steps = [
        first_report(8, CIVIL),
        act(12, "classify", "T002", CIVIL, class_id="fixed-wing-small"),  # also wrong
        act(14, "assess", "T002", CIVIL, identity="hostile"),
        act(20, "engage", "T002", CIVIL, effector_class="ec-a"),
    ]
    result = score(steps)
    assert [x.key for x in result.lessons] == ["lesson.hard-fail.engaged-non-hostile"]
    (lesson,) = result.lessons
    assert lesson.params["track"] == "T002" and lesson.params["t"] == 20.0
    assert lesson.cost == 0.2941  # what the contact would have scored without the breach


def test_a_track_error_is_a_lesson_and_a_fixed_one_is_not() -> None:
    steps = [*STEM, act(60, "engage", "T001", QUAD, effector_class="ec-a")]

    def keys(extra: list[Step]) -> list[str]:
        return [x.key for x in score([*steps, *extra]).lessons]

    assert "lesson.track-error" in keys([swap(45, 1, QUAD, CIVIL)])
    assert "lesson.track-error" not in keys([swap(45, 1, QUAD, CIVIL), restored(50, 1)])


def test_the_session_level_false_engagement_has_no_contact_and_no_label() -> None:
    steps = [*STEM, act(60, "engage", "T001", QUAD, effector_class="ec-a")]
    steps += [act(90, "engage", "T009", None, effector_class="ec-a")]
    lessons = score(steps).lessons
    fe = next(x for x in lessons if x.key == "lesson.false-engagement")
    assert fe.threat_id is None and "threat" not in fe.params
    assert fe.params == {"t": 90.0, "track": "T009"} and fe.cost == 0.15


def test_a_blocked_attempt_on_a_civil_contact_is_a_lesson() -> None:
    steps = [
        first_report(8, CIVIL),
        act(12, "classify", "T002", CIVIL, class_id="rotary-small"),
        act(14, "assess", "T002", CIVIL, identity="neutral"),
        act(20, "engage", "T002", CIVIL, permitted=False, effector_class="ec-a"),
    ]
    lesson = next(x for x in score(steps).lessons if x.key == "lesson.blocked-attempt")
    assert lesson.params["attempts"] == 1 and lesson.threat_id == CIVIL


def test_a_blocked_attempt_on_a_hostile_contact_is_counted_once_in_the_respond_lesson() -> None:
    steps = [*STEM, act(50, "engage", "T001", QUAD, permitted=False, effector_class="ec-a")]
    steps += [act(60, "engage", "T001", QUAD, effector_class="ec-a")]
    keys = [x.key for x in score(steps).lessons]
    assert "lesson.blocked-attempt" not in keys  # the loss is already in the Respond node
