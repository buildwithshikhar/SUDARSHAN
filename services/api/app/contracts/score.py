"""Scoring result, contract `score-result.v1`.

What the evaluator (`app/scoring/`) returns for one finished session: a node-by-node path for each
contact, the contact-report grade, signal-detection metrics and the lessons that cost the most
marks. Every explanation is a reason key plus parameters, rendered into English or Hindi by the
console from its message catalogue; nothing here is free text.

A score holds ground truth (the real class and disposition of each contact), so it is only ever
given to a trainee after the session has ended. Marks are fractions from 0 to 1, rounded to four
places so a re-score is byte-identical. Timing standards and every weight come from the rule pack
the scenario names, which is fictional and editable; the pack and scenario versions are recorded.
"""

from typing import Annotated, Literal

from pydantic import BeforeValidator, Field, FiniteFloat, JsonValue

from .common import Contract, PackRef, Seed, Sha256Hex, Slug, Text


def _tidy(value: object) -> object:
    """Round a mark to four places and absorb float noise at the ends of the range, so a
    re-score is byte-identical and a perfect sum of weights is not 1.0000000000000002."""
    if isinstance(value, float) and value == value:
        if -1e-9 < value < 0:
            value = 0.0
        elif 1 < value < 1 + 1e-9:
            value = 1.0
        return round(value, 4)
    return value


Mark = Annotated[float, BeforeValidator(_tidy), Field(ge=0, le=1, allow_inf_nan=False)]
Params = dict[str, JsonValue]

Node = Literal["detect", "classify", "assess", "respond"]
ReportField = Literal["what", "where", "count", "heading", "calibration"]


class NodeResult(Contract):
    node: Node
    score: Mark
    #: The pack's weight for this node (not renormalised).
    weight: Mark
    #: Message key, for example `detect.band`; the console renders it with `params`.
    reason: str
    params: Params = {}


class FieldMark(Contract):
    field: ReportField
    score: Mark
    weight: Mark
    reason: str
    params: Params = {}


class ReportGrade(Contract):
    #: False when no report was filed for this contact.
    filed: bool
    fields: list[FieldMark] = []
    #: Weighted marks of the five fields.
    quality: Mark = 0.0
    #: Credit for how soon the (first) report came, from the pack's timing bands.
    timeliness: Mark | None = None
    #: Quality and timeliness together, by the pack's timeliness weight.
    score: Mark = 0.0
    reports_filed: int = 0
    reason: str = "report.missing"
    params: Params = {}


class Finding(Contract):
    """Something that cost marks or deserves a plain statement: a hard fail, an unfixed track
    error, a blocked response, a false alarm."""

    kind: Literal[
        "hard-fail",
        "track-error",
        "blocked-attempt",
        "false-alarm",
        "false-engagement",
        "not-presented",
        "not-worked",
    ]
    reason: str
    params: Params = {}
    #: Marks lost to this finding (0 when it is only a statement).
    cost: Mark = 0.0


class ThreatScore(Contract):
    """The path of one scenario contact through Detect, Classify, Assess and Respond."""

    threat_id: Slug
    label: Text
    class_id: Slug
    disposition: Literal["hostile", "civil-permitted", "clutter"]
    #: False if no sensor ever reported the contact: it cannot be scored and is left out.
    presented: bool
    #: False for a clutter or civil contact the operator never acted on: leaving it alone is the
    #: right call, so it is neither marked nor counted against the operator, and is left out.
    worked: bool = True
    first_report_s: FiniteFloat | None = None
    nodes: list[NodeResult] = []
    #: Weighted marks of the four nodes, renormalised over their weights.
    decision: Mark | None = None
    #: Contact-report grade; present only where a report was expected (hostile contacts).
    report: ReportGrade | None = None
    hard_fail: bool = False
    findings: list[Finding] = []
    #: The contact's score: decision and report by the pack weights, less penalties; 0 on a hard
    #: fail; `None` when it was not presented or not worked.
    score: Mark | None = None


class Sdt(Contract):
    """Signal-detection metrics for the session's threat-or-not calls."""

    signal_trials: int
    noise_trials: int
    hits: int
    misses: int
    false_alarms: int
    correct_rejections: int
    hit_rate: Mark | None
    false_alarm_rate: Mark | None
    #: True when a rate was 0 or 1 and the log-linear correction was applied to both.
    corrected: bool
    hit_rate_used: Mark | None
    false_alarm_rate_used: Mark | None
    d_prime: FiniteFloat | None
    criterion: FiniteFloat | None


class Lesson(Contract):
    """One of the first lessons: where the most marks were lost."""

    key: str
    params: Params = {}
    #: The contact it is about, when there is one.
    threat_id: Slug | None = None
    cost: Mark


class SessionScore(Contract):
    contract: Literal["score-result.v1"]
    scenario: PackRef
    scenario_title: Text
    rule_pack: PackRef
    seed: Seed
    ticks: int
    duration_s: FiniteFloat
    #: Chain head of the event log this score was computed from.
    event_head: Sha256Hex
    #: The pack's weight for the contact report, which the contact rows do not carry.
    report_weight: Mark
    threats: list[ThreatScore]
    sdt: Sdt
    #: Findings about the session rather than one contact (an engagement on a false track).
    findings: list[Finding] = []
    #: Mean of the presented contacts' scores, less session penalties; `None` if nothing was
    #: presented.
    score: Mark | None
    #: Mean decision marks (0 for a contact that hard-failed) over the presented contacts, and mean
    #: report marks over the presented hostile contacts.
    decision_score: Mark | None
    report_score: Mark | None
    lessons: list[Lesson] = []
