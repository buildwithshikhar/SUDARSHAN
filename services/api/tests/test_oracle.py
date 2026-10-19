"""The oracle defender and the solved criterion (docs/SCENARIO_ENGINE.md)."""

from collections import Counter
from types import SimpleNamespace
from typing import Any

import pytest

from app.contracts import ScenarioSpec
from app.contracts.loader import load_pack
from app.contracts.paths import packs_root
from app.contracts.rulepack import RulePack
from app.contracts.score import Finding
from app.scenarios import oracle
from app.scenarios.oracle import ACTOR, OracleResult, play
from app.scenarios.solvability import (
    FAILURES,
    NOT_VERIFIED,
    VERIFIED,
    evaluate,
    solved,
    wording,
)
from sim import replay
from sim.world import ActionError

from .live_helpers import harrier_spec
from .scoring_support import baseline


def pack_scenario(name: str) -> ScenarioSpec:
    spec = load_pack(packs_root() / "scenarios" / f"{name}.v1.json")
    assert isinstance(spec, ScenarioSpec)
    return spec


@pytest.fixture(scope="module")
def harrier_run() -> OracleResult:
    spec = harrier_spec()
    return play(spec, spec.default_seed)


def test_the_oracle_answers_the_hostile_contact_and_the_record_replays(
    harrier_run: OracleResult,
) -> None:
    spec = harrier_spec()
    assert harrier_run.unanswered == ()
    assert replay.replay(spec, harrier_run.record).matches
    assert harrier_run.record.picture and harrier_run.record.roe
    assert {a.actor for a in harrier_run.actions} == {ACTOR}
    assert harrier_run.finished_s < spec.duration_s  # it stops once the last answer is in


def test_it_engages_with_the_lowest_escalation_effector_and_is_never_blocked(
    harrier_run: OracleResult,
) -> None:
    engages = [a for a in harrier_run.actions if a.action == "engage"]
    assert [a.payload["effector_class"] for a in engages] == ["ec-a"]
    verdicts = [e.payload for e in harrier_run.record.events if e.type == "roe.verdict"]
    assert all(v["permitted"] for v in verdicts)
    assert {v["action"] for v in verdicts} >= {"classify", "assess", "report", "engage"}


def test_it_calls_each_contact_by_its_true_class_and_disposition(harrier_run: OracleResult) -> None:
    calls = [e.payload for e in harrier_run.record.events if e.type.startswith("action.")]
    by_target: dict[object, list[dict[str, Any]]] = {}
    for c in calls:
        by_target.setdefault(c.get("target"), []).append(c)
    quad = by_target["contact-quad"]
    assert {c["class_id"] for c in quad if "class_id" in c} == {"rotary-small"}
    assert {c["identity"] for c in quad if "identity" in c} == {"hostile"}
    civil = by_target["contact-civil"]
    assert {c["identity"] for c in civil if "identity" in c} == {"neutral"}
    assert not any(c.get("effector_class") for c in civil), "never engages a civil contact"
    assert all(
        "effector_class" not in c for t, cs in by_target.items() if t != "contact-quad" for c in cs
    )


def test_a_perfect_report_is_graded_perfectly(harrier_run: OracleResult) -> None:
    quad = next(t for t in harrier_run.score.threats if t.threat_id == "contact-quad")
    assert quad.report is not None and quad.report.quality == 1.0
    assert all(f.score == 1.0 for f in quad.report.fields)
    assert [n.score for n in quad.nodes if n.node in ("assess", "respond")] == [1.0, 1.0]


def test_the_run_is_deterministic(harrier_run: OracleResult) -> None:
    spec = harrier_spec()
    again = play(spec, spec.default_seed)
    assert again.record.final_state_hash == harrier_run.record.final_state_hash
    assert again.actions == harrier_run.actions
    assert again.score.model_dump_json() == harrier_run.score.model_dump_json()


def test_the_run_records_the_versions_it_used(harrier_run: OracleResult) -> None:
    assert harrier_run.record.profiles and harrier_run.score.profiles == harrier_run.record.profiles
    assert {r.id for r in harrier_run.record.threat_classes} == {"bird", "rotary-small"}


def test_track_errors_are_repaired_so_none_costs_marks() -> None:
    spec = pack_scenario("heron-ridge-low-approach")
    result = play(spec, spec.default_seed)
    kinds = Counter(a.action for a in result.actions)
    assert kinds["track-relabel"] >= 1 and kinds["track-merge"] >= 1
    types = Counter(e.type for e in result.record.events)
    assert types["ledger.swap"] >= 1 and types["ledger.split"] >= 1
    assert types["ledger.restored"] >= 2
    findings = [f.kind for t in result.score.threats for f in t.findings]
    assert "track-error" not in findings
    assert solved(evaluate(spec, result, 80))


def test_the_criterion_is_met_by_a_clean_run_and_names_what_it_checked(
    harrier_run: OracleResult,
) -> None:
    checks = evaluate(harrier_spec(), harrier_run, 80)
    assert [c.name for c in checks] == [
        "hostile-presented",
        "hostile-answered",
        "no-failures",
        "oracle-score",
    ]
    assert all(c.passed for c in checks) and wording(checks) == VERIFIED
    assert checks[3].value == 0.8563
    assert all(c.code.startswith("solvability.") for c in checks)


def test_the_score_bar_is_the_requests(harrier_run: OracleResult) -> None:
    spec = harrier_spec()
    assert solved(evaluate(spec, harrier_run, 85))
    strict = evaluate(spec, harrier_run, 90)
    assert not solved(strict) and wording(strict) == NOT_VERIFIED
    assert "below 90%: contact-quad" in strict[3].detail
    assert [c.passed for c in strict[:3]] == [True, True, True]


def test_a_sensor_limited_scenario_is_not_verified_at_the_default_bar() -> None:
    spec = pack_scenario("kestrel-dawn-approach")
    result = play(spec, spec.default_seed)
    checks = evaluate(spec, result, 80)
    assert not solved(checks) and not checks[3].passed
    assert solved(evaluate(spec, result, 60))


def test_a_hostile_no_sensor_reports_fails_the_presented_check() -> None:
    spec = harrier_spec().model_copy(
        update={"sensors": [s for s in harrier_spec().sensors if s.id == "eo-1"]}
    )
    spec = ScenarioSpec.model_validate(
        {
            **spec.model_dump(mode="json"),
            "sensors": [s for s in spec.model_dump(mode="json")["sensors"]],
        }
    )
    result = play(spec, spec.default_seed, max_ticks=400)
    checks = evaluate(spec, result, 80)
    assert not checks[0].passed and "contact-quad" in checks[0].detail
    assert not checks[1].passed and wording(checks) == NOT_VERIFIED


def test_a_hostile_the_rules_never_let_it_engage_is_unanswered() -> None:
    data = harrier_spec().model_dump(mode="json")
    data["zones"] = []
    spec = ScenarioSpec.model_validate(data)
    result = play(spec, spec.default_seed, max_ticks=3000)
    assert result.unanswered == ("contact-quad",)
    checks = evaluate(spec, result, 80)
    assert checks[0].passed and not checks[1].passed
    assert "not answered: contact-quad" in checks[1].detail


def test_a_failure_finding_fails_the_no_failures_check(harrier_run: OracleResult) -> None:
    assert FAILURES == ("hard-fail", "blocked-attempt", "false-engagement", "track-error")
    spec = harrier_spec()
    threat = harrier_run.score.threats[3]
    flagged = threat.model_copy(
        update={"findings": [Finding(kind="blocked-attempt", reason="finding.blocked-attempt")]}
    )
    threats = [*harrier_run.score.threats[:3], flagged, *harrier_run.score.threats[4:]]
    session = Finding(kind="false-engagement", reason="finding.false-engagement")
    score = harrier_run.score.model_copy(update={"threats": threats, "findings": [session]})
    bad = OracleResult(harrier_run.record, score, harrier_run.unanswered, harrier_run.finished_s)
    checks = evaluate(spec, bad, 80)
    assert not checks[2].passed
    assert "blocked-attempt:contact-quad" in checks[2].detail
    assert "false-engagement:session" in checks[2].detail
    assert checks[2].value == 2


def test_a_scenario_with_no_hostile_contact_is_not_solved() -> None:
    data = harrier_spec().model_dump(mode="json")
    for t in data["threats"]:
        t["disposition"] = "civil-permitted" if t["class_id"] == "rotary-small" else "clutter"
    spec = ScenarioSpec.model_validate(data)
    result = play(spec, spec.default_seed, max_ticks=600)
    checks = evaluate(spec, result, 80)
    assert not checks[3].passed and checks[3].detail == "no hostile contact"


def test_the_run_stops_at_max_ticks() -> None:
    spec = harrier_spec()
    result = play(spec, spec.default_seed, max_ticks=100)
    assert result.record.ticks == 100 and result.finished_s == 5.0


def test_a_rule_pack_with_no_engage_rule_is_refused() -> None:
    pack = baseline()
    bare = RulePack.model_validate(
        {
            **pack.model_dump(mode="json"),
            "rules": [
                r for r in pack.model_dump(mode="json")["rules"] if "engage" not in r["permits"]
            ],
        }
    )
    with pytest.raises(ActionError, match="no rule that permits an engagement"):
        oracle._first_effectors(bare)


def test_a_split_error_is_repaired_by_merging_the_duplicate() -> None:
    world = SimpleNamespace(
        tick=7,
        picture=SimpleNamespace(
            ledger=SimpleNamespace(
                open_errors=lambda: [{"kind": "split", "tracks": ["T001", "T002", "T003"]}]
            ),
            tracker=SimpleNamespace(tracks={"T001": object(), "T002": object()}),
        ),
    )
    (action,) = oracle._repairs(world)  # type: ignore[arg-type]
    assert (action.action, action.payload, action.tick) == (
        "track-merge",
        {"tracks": ["T001", "T002"]},
        7,
    )


def test_a_swap_with_no_label_to_exchange_is_left_alone() -> None:
    ledger: Any = SimpleNamespace(
        open_errors=lambda: [{"kind": "swap", "tracks": ["T001", "T009"]}],
        identity_of=lambda t: "drone-a" if t == "T001" else None,
        consistent=lambda t: False,
        bound_labels=lambda d: ["LOST"],
        label_of=lambda t: t,
    )
    world = SimpleNamespace(
        tick=1,
        picture=SimpleNamespace(ledger=ledger, tracker=SimpleNamespace(tracks={"T001": 1})),
    )
    assert oracle._repairs(world) == []  # type: ignore[arg-type]
    ledger.consistent = lambda t: True
    assert oracle._repairs(world) == []  # type: ignore[arg-type]
