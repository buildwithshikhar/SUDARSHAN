"""Golden event-log fixtures for the evaluator: `tests/golden/scoring/*.json`.

Each file is one case: `steps` (a compact event log, see `tests/scoring_support.py`) and `expect`,
the result worked out by hand from docs/SCORING.md and the baseline rule pack before the evaluator
was run. A mismatch prints a unified diff of expected against actual. If a change is intended
(a deliberate scoring change), regenerate the `expect` blocks and read the diff before committing:

    UPDATE_GOLDEN=1 uv run pytest tests/test_scoring_golden.py

`expect` lists the presented contacts (an unlisted contact must be unpresented), node by node
(mark, reason key, parameters), the decision, the report grade, hard fail, findings and score; then
the session findings and score, the signal-detection block and the lessons.
"""

import difflib
import json
import os
from pathlib import Path
from typing import Any

import pytest

from app.contracts.score import ReportGrade, SessionScore, ThreatScore

from .scoring_support import score

GOLDEN_DIR = Path(__file__).resolve().parent / "golden" / "scoring"
CASES = sorted(GOLDEN_DIR.glob("*.json"))

SDT_FIELDS = (
    "signal_trials",
    "noise_trials",
    "hits",
    "misses",
    "false_alarms",
    "correct_rejections",
    "hit_rate",
    "false_alarm_rate",
    "corrected",
    "hit_rate_used",
    "false_alarm_rate_used",
    "d_prime",
    "criterion",
)


def _findings(items: list[Any]) -> list[dict[str, Any]]:
    return [{"reason": f.reason, "params": f.params, "cost": f.cost} for f in items]


def _report(grade: ReportGrade | None) -> dict[str, Any] | None:
    if grade is None:
        return None
    return {
        "filed": grade.filed,
        "reports_filed": grade.reports_filed,
        "reason": grade.reason,
        "params": grade.params,
        "quality": grade.quality,
        "timeliness": grade.timeliness,
        "score": grade.score,
        "fields": [
            {"field": f.field, "score": f.score, "reason": f.reason, "params": f.params}
            for f in grade.fields
        ],
    }


def _threat(t: ThreatScore) -> dict[str, Any]:
    out: dict[str, Any] = {"worked": t.worked}
    if t.nodes:
        out["nodes"] = {
            n.node: {"score": n.score, "reason": n.reason, "params": n.params} for n in t.nodes
        }
    out.update(
        decision=t.decision,
        report=_report(t.report),
        hard_fail=t.hard_fail,
        findings=_findings(t.findings),
        score=t.score,
    )
    return out


def project(result: SessionScore) -> dict[str, Any]:
    """The part of a score a golden file pins, in the shape of `expect`."""
    return {
        "threats": {t.threat_id: _threat(t) for t in result.threats if t.presented},
        "not_presented": [t.threat_id for t in result.threats if not t.presented],
        "session": {
            "score": result.score,
            "decision_score": result.decision_score,
            "report_score": result.report_score,
            "findings": _findings(result.findings),
        },
        "sdt": {name: getattr(result.sdt, name) for name in SDT_FIELDS},
        "lessons": [
            {
                "key": lesson.key,
                "threat_id": lesson.threat_id,
                "cost": lesson.cost,
                "params": {k: v for k, v in lesson.params.items() if k != "threat"},
            }
            for lesson in result.lessons
        ],
    }


def render(doc: dict[str, Any]) -> str:
    """The file text: description, one step per line, then the pretty-printed expectation."""
    steps = ",\n".join("    " + json.dumps(s, ensure_ascii=False) for s in doc["steps"])
    expect = json.dumps(doc["expect"], indent=2, ensure_ascii=False)
    expect = expect.replace("\n", "\n  ")
    return (
        "{\n"
        f'  "description": {json.dumps(doc["description"], ensure_ascii=False)},\n'
        f'  "steps": [\n{steps}\n  ],\n'
        f'  "expect": {expect}\n'
        "}\n"
    )


def _dump(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False)


@pytest.mark.parametrize("path", CASES, ids=[p.stem for p in CASES])
def test_golden_case(path: Path) -> None:
    doc = json.loads(path.read_text(encoding="utf-8"))
    actual = project(score(doc["steps"]))
    if os.environ.get("UPDATE_GOLDEN") == "1":
        path.write_text(render({**doc, "expect": actual}), encoding="utf-8")
        return
    expected = json.loads(json.dumps(doc["expect"]))
    if expected != actual:
        diff = difflib.unified_diff(
            _dump(expected).splitlines(),
            _dump(actual).splitlines(),
            f"golden/scoring/{path.name} (expected)",
            "evaluator (actual)",
            n=2,
            lineterm="",
        )
        lines = list(diff)
        shown = "\n".join(lines[:100]) + (
            f"\n... {len(lines) - 100} more lines" if len(lines) > 100 else ""
        )
        pytest.fail(f"scoring changed for {path.stem}:\n{shown}", pytrace=False)


def test_there_are_at_least_twelve_golden_cases() -> None:
    assert len(CASES) >= 12


def test_every_golden_file_is_in_its_canonical_form() -> None:
    for path in CASES:
        doc = json.loads(path.read_text(encoding="utf-8"))
        assert path.read_text(encoding="utf-8") == render(doc), path.name


def test_a_hard_fail_findings_cost_is_rounded_to_four_places() -> None:
    from .scoring_support import CIVIL, act, first_report

    result = score(
        [
            first_report(8, CIVIL),
            act(12, "classify", "T002", CIVIL, class_id="rotary-small"),
            act(14, "assess", "T002", CIVIL, identity="hostile"),
            act(20, "engage", "T002", CIVIL, effector_class="ec-a"),
        ]
    )
    (civil,) = [t for t in result.threats if t.threat_id == CIVIL]
    cost = civil.findings[0].cost
    assert cost == round(cost, 4) == 0.8235
    assert result.model_dump_json().count("0.8235294") == 0
