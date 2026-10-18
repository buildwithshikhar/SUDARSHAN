"""The rules-of-engagement check: which rule permits or blocks a response, and why."""

from pathlib import Path
from typing import Any

import pytest

from app.contracts.loader import load_pack
from app.contracts.rulepack import RulePack
from app.contracts.scenario import ScenarioSpec
from sim.roe import Context, RuleEngine, load_rule_engine
from tests.live_helpers import harrier_spec

REPO = Path(__file__).resolve().parents[3]


def _pack() -> RulePack:
    pack = load_pack(REPO / "packs" / "rule-packs" / "training-baseline.v1.yaml")
    assert isinstance(pack, RulePack)
    return pack


SPEC = harrier_spec()
PACK = _pack()
ENGINE = RuleEngine(PACK, SPEC)


def ctx(identity: str | None = None, zone: str | None = "outer", conf: float = 0.9) -> Context:
    return Context(
        identity=identity, classification="rotary-small", zone_role=zone, confidence=conf
    )


def test_a_hostile_in_the_outer_zone_may_receive_a_class_a_response() -> None:
    verdict = ENGINE.evaluate("engage", ctx("hostile"), "ec-a")
    assert verdict.permitted
    assert (verdict.code, verdict.rule_id) == ("permitted", "suspect-outer-zone")
    assert (verdict.pack_id, verdict.pack_version) == ("training-baseline", "1.0.0")
    assert verdict.rule_title is not None and verdict.rule_title["en"].startswith("Suspect contact")


def test_a_neutral_contact_cannot_be_engaged_and_the_closest_rule_says_why() -> None:
    verdict = ENGINE.evaluate("engage", ctx("neutral"), "ec-a")
    assert not verdict.permitted
    assert verdict.code == "conditions"
    assert verdict.rule_id == "suspect-outer-zone"
    [unmet] = verdict.detail["unmet"]
    assert unmet == {"field": "identity", "required": ["suspect", "hostile"], "actual": "neutral"}


def test_an_unassessed_track_counts_as_unknown() -> None:
    verdict = ENGINE.evaluate("engage", ctx(None), "ec-a")
    assert not verdict.permitted
    assert verdict.detail["unmet"][0]["actual"] is None


def test_low_confidence_is_reported_with_the_figures() -> None:
    verdict = ENGINE.evaluate("engage", ctx("hostile", conf=0.4), "ec-a")
    assert not verdict.permitted
    assert verdict.detail["unmet"] == [{"field": "confidence", "required": 0.6, "actual": 0.4}]


def test_outside_every_zone_blocks_a_response() -> None:
    verdict = ENGINE.evaluate("engage", ctx("hostile", zone=None), "ec-a")
    assert not verdict.permitted
    assert verdict.detail["unmet"][0]["field"] == "zone"


def test_an_effector_the_rule_does_not_list_is_blocked() -> None:
    verdict = ENGINE.evaluate("engage", ctx("hostile"), "ec-b")
    assert not verdict.permitted
    assert (verdict.code, verdict.rule_id) == ("effector", "suspect-outer-zone")
    assert verdict.detail == {"effector_class": "ec-b", "allowed": ["ec-a"]}


def test_a_commander_rule_is_blocked_for_a_single_operator_and_allowed_with_one() -> None:
    inner = ctx("hostile", zone="inner")
    blocked = ENGINE.evaluate("engage", inner, "ec-b")
    assert (blocked.permitted, blocked.code, blocked.rule_id) == (
        False,
        "authority",
        "hostile-inner-zone",
    )
    assert blocked.detail == {"required": "commander"}
    allowed = ENGINE.evaluate("engage", inner, "ec-b", commander=True)
    assert (allowed.permitted, allowed.rule_id) == (True, "hostile-inner-zone")


def test_the_operator_rule_is_preferred_in_the_inner_zone_for_class_a() -> None:
    verdict = ENGINE.evaluate("engage", ctx("hostile", zone="inner"), "ec-a")
    assert (verdict.permitted, verdict.rule_id) == (True, "suspect-outer-zone")


def test_hold_and_report_are_permitted_by_the_track_everything_rule() -> None:
    for action in ("hold", "report", "designate", "classify", "assess"):
        verdict = ENGINE.evaluate(action, ctx(None, zone=None, conf=0.0))
        assert (verdict.permitted, verdict.rule_id) == (True, "track-everything"), action


def _pack_without(rule_id: str) -> RulePack:
    data: dict[str, Any] = PACK.model_dump(mode="json")
    data["rules"] = [r for r in data["rules"] if r["id"] != rule_id]
    return RulePack.model_validate(data)


def test_hold_is_the_default_action_even_when_no_rule_mentions_it() -> None:
    engine = RuleEngine(_pack_without("track-everything"), SPEC)
    verdict = engine.evaluate("hold", ctx())
    assert (verdict.permitted, verdict.code, verdict.rule_id) == (True, "default-hold", None)


def test_an_action_no_rule_permits_has_no_rule_to_cite() -> None:
    engine = RuleEngine(_pack_without("track-everything"), SPEC)
    verdict = engine.evaluate("report", ctx())
    assert (verdict.permitted, verdict.code, verdict.rule_id) == (False, "no-rule", None)
    assert verdict.detail == {"action": "report"}


def test_engage_without_an_effector_class_is_blocked() -> None:
    verdict = ENGINE.evaluate("engage", ctx("hostile"), None)
    assert not verdict.permitted
    assert verdict.code == "effector"


def test_the_zone_of_a_point_is_the_smallest_zone_that_contains_it() -> None:
    assert ENGINE.zone_role(100, 100) == "inner"
    assert ENGINE.zone_role(2000, 0) == "outer"
    assert ENGINE.zone_role(5000, 0) is None


def test_the_summary_is_what_a_trainee_may_read() -> None:
    summary = ENGINE.summary()
    assert summary["id"] == "training-baseline"
    assert summary["version"] == "1.0.0"
    assert [r["id"] for r in summary["rules"]][0] == "track-everything"
    assert summary["rules"][1]["when"]["min_confidence"] == 0.6
    assert {e["id"] for e in summary["effector_classes"]} == {"ec-a", "ec-b"}


def test_the_engine_for_a_scenario_comes_from_the_pack_it_names() -> None:
    engine = load_rule_engine(SPEC)
    assert (engine.pack.id, engine.pack.version) == ("training-baseline", "1.0.0")


def test_a_scenario_that_names_a_missing_rule_pack_is_refused() -> None:
    data = SPEC.model_dump(mode="json")
    data["rule_pack"] = {"id": "training-baseline", "version": "9.9.9"}
    with pytest.raises(FileNotFoundError, match="9.9.9"):
        load_rule_engine(ScenarioSpec.model_validate(data))


def test_context_view_rounds_the_confidence() -> None:
    assert Context("hostile", "bird", "inner", 0.123456).view()["confidence"] == 0.123


def test_a_classification_condition_is_checked_and_reported() -> None:
    data: dict[str, Any] = PACK.model_dump(mode="json")
    data["rules"][1]["when"]["classification_in"] = ["rotary-small"]
    engine = RuleEngine(RulePack.model_validate(data), SPEC)
    good = engine.evaluate("engage", Context("hostile", "rotary-small", "outer", 0.9), "ec-a")
    assert good.permitted
    bad = engine.evaluate("engage", Context("hostile", "bird", "outer", 0.9), "ec-a")
    assert bad.detail["unmet"] == [
        {"field": "classification", "required": ["rotary-small"], "actual": "bird"}
    ]
