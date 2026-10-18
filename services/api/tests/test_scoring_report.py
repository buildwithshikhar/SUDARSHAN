"""Contact-report grading (docs/SCORING.md, "Contact report"), field by field.

The truth is one rotary drone 1000 m due north of the site, flying course 90, alone (see
`tests.scoring_support.truth`). A report from the site is a bearing and a range, so a range of
1000 + e on bearing 0 is exactly e metres out along the line to the drone.
"""

from typing import Any

import pytest

from app.contracts.score import FieldMark, ReportGrade

from .scoring_support import (
    CIVIL,
    QUAD,
    act,
    build,
    first_report,
    score,
    truth,
)

PERFECT: dict[str, Any] = {
    "class_id": "rotary-small",
    "bearing_deg": 0,
    "range_m": 1000,
    "count": 1,
    "heading_deg": 90,
    "confidence": 1.0,
}


def file(t: float = 50, *, tr: dict[str, Any] | None = None, **fields: Any) -> ReportGrade:
    """The grade of one report filed at `t` seconds (the first report of the drone was at 30 s)."""
    steps = [first_report(30, QUAD), act(t, "report", "T001", QUAD, truth=tr or truth(), **fields)]
    (threat,) = [x for x in score(steps).threats if x.threat_id == QUAD]
    assert threat.report is not None
    return threat.report


def marks(grade: ReportGrade) -> dict[str, FieldMark]:
    return {m.field: m for m in grade.fields}


# ------------------------------------------------------------------------- the worked example


WORKED: dict[str, Any] = {
    "class_id": "rotary-small",
    "bearing_deg": 0,
    "range_m": 1100,  # 100 m out, inside the 150 m tolerance
    "count": 2,  # off by one
    "heading_deg": 130,  # 40 degrees out
    "confidence": 0.8,
}


def test_the_worked_example_in_the_scoring_doc() -> None:
    grade = file(**WORKED)
    m = marks(grade)
    assert [m[f].score for f in ("what", "where", "count", "heading")] == [1.0, 1.0, 0.5, 0.5]
    # q = (0.30 + 0.25 + 0.15 x 0.5 + 0.15 x 0.5) / 0.85 = 0.8235; 1 - (0.8 - 0.8235)^2 = 0.9994
    assert m["calibration"].score == 0.9994
    assert m["calibration"].params == {"stated": 0.8, "achieved": 0.824}
    # 0.30 + 0.25 + 0.075 + 0.075 + 0.15 x 0.9994 = 0.8499
    assert grade.quality == 0.8499
    # filed 20 s after the first report: timeliness 1.0; report = 0.8 x 0.8499 + 0.2 x 1.0
    assert grade.timeliness == 1.0
    assert grade.score == 0.8799
    assert [m[f].reason for f in ("what", "where", "count", "heading", "calibration")] == [
        "report.what.ok",
        "report.where.ok",
        "report.count.partial",
        "report.heading.partial",
        "report.calibration.ok",
    ]
    assert grade.reason == "report.filed" and grade.reports_filed == 1


def test_scoring_the_same_log_again_gives_the_same_report_result_to_the_byte() -> None:
    steps = [first_report(30, QUAD), act(50, "report", "T001", QUAD, truth=truth(), **WORKED)]
    events = build(steps)
    first = score(events).model_dump_json()
    assert score(events).model_dump_json() == first
    assert score(build(steps)).model_dump_json() == first  # built afresh from the steps


# ------------------------------------------------------------------------------- field: what


def test_what_is_one_for_the_right_class_and_zero_for_any_other() -> None:
    right = marks(file(class_id="rotary-small"))["what"]
    assert (right.score, right.reason) == (1.0, "report.what.ok")
    for wrong_class in ("fixed-wing-small", "bird", "unknown"):
        wrong = marks(file(class_id=wrong_class))["what"]
        assert (wrong.score, wrong.reason) == (0.0, "report.what.wrong")
        assert wrong.params == {"given": wrong_class, "actual": "rotary-small"}


# ----------------------------------------------------------------------------- field: where


@pytest.mark.parametrize(
    ("error_m", "mark", "reason"),
    [
        (0, 1.0, "report.where.ok"),
        (100, 1.0, "report.where.ok"),
        (150, 1.0, "report.where.ok"),  # exactly the tolerance
        (151, 0.9967, "report.where.partial"),  # (450 - 151) / 300, just beyond
        (300, 0.5, "report.where.partial"),
        (449, 0.0033, "report.where.partial"),
        (450, 0.0, "report.where.wrong"),  # the zero point, 3 x tolerance
        (600, 0.0, "report.where.wrong"),
        (-150, 1.0, "report.where.ok"),  # short of the drone by the tolerance
        (-300, 0.5, "report.where.partial"),
    ],
)
def test_where_falls_linearly_from_the_tolerance_to_three_times_it(
    error_m: int, mark: float, reason: str
) -> None:
    where = marks(file(bearing_deg=0, range_m=1000 + error_m))["where"]
    assert (where.score, where.reason) == (mark, reason)
    assert where.params == {"error_m": abs(error_m), "tolerance_m": 150.0}


def test_where_uses_the_bearing_as_well_as_the_range() -> None:
    # bearing 10 degrees at the right range: 2 x 1000 x sin(5 degrees) = 174.4 m out
    off = marks(file(bearing_deg=10, range_m=1000))["where"]
    assert off.params["error_m"] == 174
    assert off.score == pytest.approx((450 - 174.4) / 300, abs=1e-3)
    assert marks(file(bearing_deg=90, range_m=1000))["where"].score == 0.0
    # 359 degrees is one degree the other side: 2 x 1000 x sin(0.5 degrees) = 17.45 m out
    assert marks(file(bearing_deg=359, range_m=1000))["where"].score == 1.0


def test_where_is_measured_from_the_first_defended_asset() -> None:
    # Harrier Field's asset is the origin, so a bearing 180 range 1000 is 2000 m from the drone.
    assert marks(file(bearing_deg=180, range_m=1000))["where"].params["error_m"] == 2000


# ---------------------------------------------------------------------------- field: heading


@pytest.mark.parametrize(
    ("given", "mark", "reason"),
    [
        (90, 1.0, "report.heading.ok"),
        (110, 1.0, "report.heading.ok"),  # 20 degrees, exactly the tolerance
        (70, 1.0, "report.heading.ok"),
        (111, 0.975, "report.heading.partial"),  # (60 - 21) / 40
        (130, 0.5, "report.heading.partial"),  # 40 degrees out
        (150, 0.0, "report.heading.wrong"),  # 60 degrees, the zero point
        (270, 0.0, "report.heading.wrong"),  # reversed
    ],
)
def test_heading_is_linear_between_the_tolerance_and_three_times_it(
    given: float, mark: float, reason: str
) -> None:
    heading = marks(file(heading_deg=given))["heading"]
    assert (heading.score, heading.reason) == (mark, reason)


@pytest.mark.parametrize(
    ("truth_heading", "given", "gap", "mark"),
    [
        (10, 350, 20, 1.0),  # across north: 20 degrees, not 340
        (350, 10, 20, 1.0),
        (0, 359.5, 0, 1.0),  # 0.5 degrees, rounds to 0
        (5, 345, 20, 1.0),
        (10, 330, 40, 0.5),
        (180, 0, 180, 0.0),
    ],
)
def test_heading_wraps_around_north(
    truth_heading: float, given: float, gap: int, mark: float
) -> None:
    heading = marks(file(tr=truth(heading_deg=truth_heading), heading_deg=given))["heading"]
    assert heading.params["error_deg"] == gap
    assert heading.score == mark


# ------------------------------------------------------------------------------ field: count


@pytest.mark.parametrize(
    ("given", "mark", "reason"),
    [
        (3, 1.0, "report.count.ok"),
        (2, 0.5, "report.count.partial"),
        (4, 0.5, "report.count.partial"),
        (1, 0.0, "report.count.wrong"),
        (5, 0.0, "report.count.wrong"),
        (30, 0.0, "report.count.wrong"),
    ],
)
def test_count_is_exact_off_by_one_or_wrong(given: int, mark: float, reason: str) -> None:
    count = marks(file(tr=truth(count=3), count=given))["count"]
    assert (count.score, count.reason) == (mark, reason)
    assert count.params == {"given": given, "actual": 3}


# --------------------------------------------------------------------------- missing fields


@pytest.mark.parametrize(
    ("omit", "field"),
    [
        ("class_id", "what"),
        ("bearing_deg", "where"),
        ("range_m", "where"),
        ("count", "count"),
        ("heading_deg", "heading"),
        ("confidence", "calibration"),
    ],
)
def test_a_missing_field_scores_zero_with_its_missing_reason(omit: str, field: str) -> None:
    m = marks(file(**{k: v for k, v in PERFECT.items() if k != omit}))
    assert (m[field].score, m[field].reason) == (0.0, f"report.{field}.missing")
    for other in [f for f in ("what", "where", "count", "heading") if f != field]:
        assert m[other].score == 1.0


def test_a_missing_graded_field_lowers_the_quality_the_calibration_is_judged_against() -> None:
    grade = file(**{k: v for k, v in PERFECT.items() if k != "heading_deg"})
    m = marks(grade)
    # q = (0.30 + 0.25 + 0.15) / 0.85 = 0.8235, stated 1.0: 1 - (1 - 0.8235)^2 = 0.9688
    assert m["calibration"].score == pytest.approx(0.9688, abs=1e-4)
    assert grade.quality == pytest.approx(0.70 + 0.15 * 0.9688, abs=1e-4)


def test_a_report_with_no_fields_at_all_scores_only_its_timeliness() -> None:
    grade = file()
    assert [m.reason for m in grade.fields] == [
        f"report.{f}.missing" for f in ("what", "where", "count", "heading", "calibration")
    ]
    assert grade.quality == 0.0 and grade.score == 0.2  # 0.8 x 0 + 0.2 x 1.0


def test_a_boolean_or_text_value_is_treated_as_missing() -> None:
    m = marks(file(**{**PERFECT, "count": True, "heading_deg": "north"}))
    assert m["count"].reason == "report.count.missing"
    assert m["heading"].reason == "report.heading.missing"


def test_a_report_with_no_truth_cannot_be_graded() -> None:
    steps = [first_report(30, QUAD), act(50, "report", "T001", QUAD, **PERFECT)]  # no truth
    (threat,) = [x for x in score(steps).threats if x.threat_id == QUAD]
    grade = threat.report
    assert grade is not None
    assert (grade.filed, grade.reason, grade.reports_filed) == (True, "report.no-truth", 1)
    assert grade.score == 0.0 and grade.quality == 0.0
    assert all(m.score == 0.0 and m.reason.endswith(".missing") for m in grade.fields)


def test_no_report_at_all_is_report_missing() -> None:
    (threat,) = [x for x in score([first_report(30, QUAD)]).threats if x.threat_id == QUAD]
    assert threat.report is not None
    assert (threat.report.filed, threat.report.reason, threat.report.score) == (
        False,
        "report.missing",
        0.0,
    )
    assert threat.report.fields == [] and threat.report.timeliness is None


# ----------------------------------------------------------------- several reports, timeliness


def test_the_last_report_is_graded_and_the_first_sets_the_timeliness() -> None:
    steps = [
        first_report(30, QUAD),
        act(40, "report", "T001", QUAD, truth=truth(), class_id="bird"),  # early and poor
        act(130, "report", "T001", QUAD, truth=truth(), **PERFECT),  # late and perfect
    ]
    (threat,) = [x for x in score(steps).threats if x.threat_id == QUAD]
    grade = threat.report
    assert grade is not None
    assert grade.reports_filed == 2
    assert marks(grade)["what"].reason == "report.what.ok"  # the last one
    assert grade.quality == 1.0
    assert grade.timeliness == 1.0  # the first, 10 s in
    assert grade.score == 1.0
    assert grade.params["seconds"] == 10.0


def test_the_last_report_can_be_worse_than_the_first() -> None:
    steps = [
        first_report(30, QUAD),
        act(40, "report", "T001", QUAD, truth=truth(), **PERFECT),
        act(60, "report", "T001", QUAD, truth=truth(), class_id="bird"),
    ]
    (threat,) = [x for x in score(steps).threats if x.threat_id == QUAD]
    assert threat.report is not None
    assert marks(threat.report)["what"].reason == "report.what.wrong"


@pytest.mark.parametrize(
    ("filed_at", "timeliness"),
    [(40, 1.0), (70, 1.0), (71, 0.75), (110, 0.75), (150, 0.5), (230, 0.25), (231, 0.0)],
)
def test_timeliness_follows_the_capped_bands_against_forty_seconds(
    filed_at: float, timeliness: float
) -> None:
    grade = file(filed_at, **PERFECT)
    assert grade.timeliness == timeliness
    assert grade.score == pytest.approx(0.8 * 1.0 + 0.2 * timeliness, abs=1e-4)


# --------------------------------------------------------------------------------- calibration


@pytest.mark.parametrize(
    ("stated", "mark", "reason"),
    [
        (1.0, 1.0, "report.calibration.ok"),
        (0.9, 0.99, "report.calibration.ok"),
        (0.7, 0.91, "report.calibration.ok"),
        (0.5, 0.75, "report.calibration.partial"),
        (0.0, 0.0, "report.calibration.wrong"),
    ],
)
def test_calibration_is_best_when_the_stated_confidence_equals_the_quality(
    stated: float, mark: float, reason: str
) -> None:
    c = marks(file(**{**PERFECT, "confidence": stated}))["calibration"]  # achieved q = 1.0
    assert (c.score, c.reason) == (mark, reason)


def test_calibration_peaks_at_the_achieved_quality_and_falls_either_side() -> None:
    q = 0.7 / 0.85  # the worked example's four graded fields
    scores = {
        s: marks(file(**{**WORKED, "confidence": s}))["calibration"].score
        for s in (0.0, 0.4, 0.8, 0.82, 0.9, 1.0)
    }
    assert scores[0.82] == max(scores.values())
    assert scores[0.8] == pytest.approx(1 - (0.8 - q) ** 2, abs=1e-4)
    assert scores[0.0] < scores[0.4] < scores[0.8] < scores[0.82]
    assert scores[0.82] > scores[0.9] > scores[1.0]


# ---------------------------------------------------------------------- non-hostile contacts


def test_a_report_on_a_non_hostile_contact_is_not_graded() -> None:
    steps = [
        first_report(8, CIVIL),
        act(12, "report", "T002", CIVIL, truth=truth(disposition="civil-permitted"), **PERFECT),
    ]
    result = score(steps)
    (civil,) = [x for x in result.threats if x.threat_id == CIVIL]
    assert civil.report is None
    assert result.report_score is None
    assert civil.score is not None and civil.worked  # the report counts as working the contact
    assert civil.nodes[0].reason == "detect.band"
    assert civil.nodes[0].params["first_action"] == "report"
