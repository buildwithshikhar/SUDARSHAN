"""Every reason and lesson key the evaluator can emit.

The console renders a key and its parameters into English or Hindi from its message catalogue
(`scoring.*` in the web i18n files). `tests/test_scoring_keys.py` checks that every key listed here
exists in both languages, so an explanation can never be missing a translation.
"""

NODE_REASONS = (
    "detect.band",
    "detect.missed",
    "classify.correct",
    "classify.wrong",
    "classify.unknown",
    "classify.missing",
    "assess.exact",
    "assess.partial",
    "assess.wrong",
    "assess.missing",
    "respond.engage",
    "respond.engage-higher",
    "respond.report-only",
    "respond.hold-only",
    "respond.none",
    "respond.hold-fire",
    "respond.breach",
)

REPORT_FIELDS = ("what", "where", "count", "heading", "calibration")
REPORT_OUTCOMES = ("ok", "partial", "wrong", "missing")
REPORT_REASONS = (
    "report.missing",
    "report.filed",
    "report.no-truth",
    *(f"report.{field}.{outcome}" for field in REPORT_FIELDS for outcome in REPORT_OUTCOMES),
)

FINDING_REASONS = (
    "finding.hard-fail.engaged-non-hostile",
    "finding.hard-fail.no-positive-id",
    "finding.track-error.swap",
    "finding.track-error.split",
    "finding.track-error.merge",
    "finding.blocked-attempt",
    "finding.false-alarm",
    "finding.false-engagement",
    "finding.not-presented",
    "finding.not-worked",
)

#: A lesson is written for the node or finding that lost the most marks.
LESSON_KEYS = (
    "lesson.detect.band",
    "lesson.detect.missed",
    "lesson.classify.correct",
    "lesson.classify.wrong",
    "lesson.classify.unknown",
    "lesson.classify.missing",
    "lesson.assess.partial",
    "lesson.assess.wrong",
    "lesson.assess.missing",
    "lesson.respond.engage-higher",
    "lesson.respond.report-only",
    "lesson.respond.hold-only",
    "lesson.respond.none",
    "lesson.respond.engage",
    "lesson.report.missing",
    "lesson.report.filed",
    "lesson.hard-fail.engaged-non-hostile",
    "lesson.hard-fail.no-positive-id",
    "lesson.track-error",
    "lesson.blocked-attempt",
    "lesson.false-engagement",
)

ALL_KEYS = (*NODE_REASONS, *REPORT_REASONS, *FINDING_REASONS, *LESSON_KEYS)
