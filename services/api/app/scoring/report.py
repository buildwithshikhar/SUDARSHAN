"""Grading a structured contact report against the ground truth logged with it.

A report has five fields. Four are checked against the truth, each with a tolerance from the rule
pack's `scoring.report`; the fifth, the operator's stated confidence, is checked for calibration.

* what: the class. Right is 1, anything else (or missing) is 0.
* where: bearing and range from the site, turned into a position and compared with the contact's
  real position when the report was filed. Within the tolerance is 1; marks fall linearly to 0 at
  `position_zero_factor` times the tolerance.
* how many: exact is 1, off by one earns `count_off_by_one_score`, more earns 0.
* heading: within the tolerance is 1; marks fall linearly to 0 at `heading_zero_factor` times it.
  With the baseline pack (20 degrees, factor 3) a heading 40 degrees out earns 0.5.
* calibration: `1 - (confidence - q)^2`, where q is the weighted mean of the four graded fields.
  Saying 80 percent about a report that was 80 percent right is the best a report can do.

The report-quality score is the weighted sum of the five fields (`report.weights`). The report
score adds timeliness, how soon the first report came measured with the same capped bands as the
decision tree, by `timeliness_weight`. The last report filed for a contact is the one graded.
"""

import math
from typing import Any

from app.contracts.rulepack import RulePack
from app.contracts.scenario import Threat
from app.contracts.score import FieldMark, ReportGrade

from .bands import band
from .facts import Call, LogFacts

_FIELDS = ("what", "where", "count", "heading")


def _linear(error: float, tolerance: float, zero_factor: float) -> float:
    if error <= tolerance:
        return 1.0
    zero = tolerance * zero_factor
    return max(0.0, (zero - error) / (zero - tolerance))


def _angle_gap(a: float, b: float) -> float:
    gap = abs(a - b) % 360.0
    return min(gap, 360.0 - gap)


def _number(payload: dict[str, Any], key: str) -> float | None:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)


def _missing(field: str, weight: float) -> FieldMark:
    return FieldMark(field=field, score=0.0, weight=weight, reason=f"report.{field}.missing")


def _outcome(score: float) -> str:
    return "ok" if score >= 1.0 else "partial" if score > 0.0 else "wrong"


def _calibration_outcome(score: float) -> str:
    return "ok" if score >= 0.9 else "partial" if score > 0.0 else "wrong"


def grade(
    threat: Threat,
    facts: LogFacts,
    pack: RulePack,
    first_t: float,
    site: tuple[float, float],
) -> ReportGrade:
    reports: list[Call] = facts.calls_on(threat.id, "report")
    if not reports:
        return ReportGrade(filed=False, reason="report.missing")
    spec = pack.scoring.report
    weights = spec.weights
    last = reports[-1]
    payload = last.payload
    truth = payload.get("truth")
    if not isinstance(truth, dict):
        return ReportGrade(
            filed=True,
            reports_filed=len(reports),
            reason="report.no-truth",
            fields=[_missing(f, getattr(weights, f)) for f in (*_FIELDS, "calibration")],
        )
    marks: dict[str, FieldMark] = {}

    given_class = payload.get("class_id")
    if given_class is None:
        marks["what"] = _missing("what", weights.what)
    else:
        right = given_class == truth.get("class_id")
        marks["what"] = FieldMark(
            field="what",
            score=1.0 if right else 0.0,
            weight=weights.what,
            reason=f"report.what.{'ok' if right else 'wrong'}",
            params={"given": str(given_class), "actual": str(truth.get("class_id"))},
        )

    bearing, range_m = _number(payload, "bearing_deg"), _number(payload, "range_m")
    if bearing is None or range_m is None:
        marks["where"] = _missing("where", weights.where)
    else:
        rad = math.radians(bearing)
        x, y = site[0] + range_m * math.sin(rad), site[1] + range_m * math.cos(rad)
        error = math.hypot(x - float(truth["x"]), y - float(truth["y"]))
        score = _linear(error, spec.position_tolerance_m, spec.position_zero_factor)
        marks["where"] = FieldMark(
            field="where",
            score=score,
            weight=weights.where,
            reason=f"report.where.{_outcome(score)}",
            params={"error_m": round(error), "tolerance_m": spec.position_tolerance_m},
        )

    count = _number(payload, "count")
    if count is None:
        marks["count"] = _missing("count", weights.count)
    else:
        off = abs(int(count) - int(truth["count"]))
        score = 1.0 if off == 0 else spec.count_off_by_one_score if off == 1 else 0.0
        marks["count"] = FieldMark(
            field="count",
            score=score,
            weight=weights.count,
            reason=f"report.count.{_outcome(score)}",
            params={"given": int(count), "actual": int(truth["count"])},
        )

    heading = _number(payload, "heading_deg")
    if heading is None:
        marks["heading"] = _missing("heading", weights.heading)
    else:
        error = _angle_gap(heading, float(truth["heading_deg"]))
        score = _linear(error, spec.heading_tolerance_deg, spec.heading_zero_factor)
        marks["heading"] = FieldMark(
            field="heading",
            score=score,
            weight=weights.heading,
            reason=f"report.heading.{_outcome(score)}",
            params={"error_deg": round(error), "tolerance_deg": spec.heading_tolerance_deg},
        )

    graded_weight = weights.what + weights.where + weights.count + weights.heading
    q = sum(marks[f].score * marks[f].weight for f in _FIELDS) / graded_weight
    confidence = _number(payload, "confidence")
    if confidence is None:
        marks["calibration"] = _missing("calibration", weights.calibration)
    else:
        score = 1.0 - (confidence - q) ** 2
        marks["calibration"] = FieldMark(
            field="calibration",
            score=score,
            weight=weights.calibration,
            reason=f"report.calibration.{_calibration_outcome(score)}",
            params={"stated": round(confidence, 3), "achieved": round(q, 3)},
        )

    quality = sum(m.score * m.weight for m in marks.values())
    elapsed = reports[0].t - first_t
    timeliness = band(elapsed, pack.thresholds.report_within_s, pack.scoring.timing_bands)
    share = spec.timeliness_weight
    return ReportGrade(
        filed=True,
        fields=[marks[f] for f in (*_FIELDS, "calibration")],
        quality=quality,
        timeliness=timeliness,
        score=(1 - share) * quality + share * timeliness,
        reports_filed=len(reports),
        reason="report.filed",
        params={
            "worst_field": max(
                _FIELDS + ("calibration",), key=lambda f: (1 - marks[f].score) * marks[f].weight
            ),
            "seconds": round(elapsed, 1),
            "standard": pack.thresholds.report_within_s,
            "timeliness": timeliness,
        },
    )
