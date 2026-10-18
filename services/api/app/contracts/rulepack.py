"""Rule pack, contract `rulepack.v1` (authored as YAML).

Rules of engagement, scoring weights and timing thresholds for training. Every rule pack is a
fictional, editable rule set; effectors are generic classes with fictional figures.
"""

from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from .common import Contract, Quantity, SemVer, Slug, Text, unique

Action = Literal["designate", "classify", "assess", "engage", "hold", "report"]
Identity = Literal["hostile", "suspect", "unknown", "neutral", "friend"]
ZoneRole = Literal["inner", "outer", "restricted"]


class EffectorClass(Contract):
    """A generic, fictional response class. No real system names or performance figures."""

    id: Slug
    label: Text
    description: Text
    max_range: Quantity


class Condition(Contract):
    """All present fields must hold for a rule to apply; an absent field matches anything."""

    identity_in: list[Identity] | None = None
    classification_in: list[Slug] | None = None
    zone_role_in: list[ZoneRole] | None = None
    min_confidence: Annotated[float, Field(ge=0, le=1)] | None = None


class Rule(Contract):
    id: Slug
    title: Text
    when: Condition
    permits: Annotated[list[Action], Field(min_length=1)]
    authority: Literal["operator", "commander"]
    effector_classes: list[Slug] = []

    @model_validator(mode="after")
    def _engage_needs_effector(self) -> Self:
        if ("engage" in self.permits) != bool(self.effector_classes):
            raise ValueError(f"rule {self.id}: engage and effector_classes go together")
        return self


class Weights(Contract):
    detect: Annotated[float, Field(ge=0, le=1)]
    classify: Annotated[float, Field(ge=0, le=1)]
    assess: Annotated[float, Field(ge=0, le=1)]
    respond: Annotated[float, Field(ge=0, le=1)]
    report: Annotated[float, Field(ge=0, le=1)]

    @model_validator(mode="after")
    def _sum_to_one(self) -> Self:
        total = self.detect + self.classify + self.assess + self.respond + self.report
        if abs(total - 1.0) > 1e-9:
            raise ValueError(f"weights must sum to 1, got {total}")
        return self


class Thresholds(Contract):
    """Fictional, editable timing standards in seconds (no public doctrinal source; Q-12).

    Each is measured from the first moment a sensor reported the contact."""

    detect_within_s: Annotated[float, Field(gt=0, le=600)]
    classify_within_s: Annotated[float, Field(gt=0, le=600)]
    report_within_s: Annotated[float, Field(gt=0, le=600)]
    respond_within_s: Annotated[float, Field(gt=0, le=600)] = 45.0


Unit01 = Annotated[float, Field(ge=0, le=1)]
Identity5 = Literal["hostile", "suspect", "unknown", "neutral", "friend"]
Disposition3 = Literal["hostile", "civil-permitted", "clutter"]


class TimingBand(Contract):
    """Credit for a response that took up to `max_factor` times the standard."""

    max_factor: Annotated[float, Field(gt=0, le=100)]
    score: Unit01


class ReportWeights(Contract):
    """How the five report fields add up to the report-quality score (sum to 1)."""

    what: Unit01 = 0.30
    where: Unit01 = 0.25
    count: Unit01 = 0.15
    heading: Unit01 = 0.15
    calibration: Unit01 = 0.15

    @model_validator(mode="after")
    def _sum_to_one(self) -> Self:
        total = self.what + self.where + self.count + self.heading + self.calibration
        if abs(total - 1.0) > 1e-9:
            raise ValueError(f"report weights must sum to 1, got {total}")
        return self


class ReportGrading(Contract):
    """Tolerances and marks for the structured contact report (fictional, editable)."""

    #: Position (bearing and range from the site) within this many metres of the truth: full marks.
    position_tolerance_m: Annotated[float, Field(gt=0, le=10_000)] = 150.0
    #: Marks fall linearly to zero at this many times the tolerance.
    position_zero_factor: Annotated[float, Field(gt=1, le=20)] = 3.0
    heading_tolerance_deg: Annotated[float, Field(gt=0, le=90)] = 20.0
    heading_zero_factor: Annotated[float, Field(gt=1, le=20)] = 3.0
    #: Marks for a count that is off by one; two or more off earns nothing.
    count_off_by_one_score: Unit01 = 0.5
    #: Contacts of the same class within this distance of the reported one are counted together.
    count_radius_m: Annotated[float, Field(gt=0, le=10_000)] = 250.0
    weights: ReportWeights = ReportWeights()
    #: Share of the report score that depends on how soon it was filed.
    timeliness_weight: Unit01 = 0.2


class Scoring(Contract):
    """How the decision tree turns what the operator did into marks. All fictional and editable."""

    #: Credit by how long the operator took, as a multiple of the standard. Faster than the
    #: standard earns no more than the first band, so rushing never pays; slower than the last band
    #: earns nothing.
    timing_bands: Annotated[list[TimingBand], Field(min_length=1, max_length=8)] = [
        TimingBand(max_factor=1.0, score=1.0),
        TimingBand(max_factor=2.0, score=0.75),
        TimingBand(max_factor=3.0, score=0.5),
        TimingBand(max_factor=5.0, score=0.25),
    ]
    #: Share of the Classify node for the class being right (the rest is timing).
    classify_correct_share: Unit01 = 0.7
    #: Credit for the operator's final assessment, by what the contact really was.
    assess_credit: dict[Disposition3, dict[Identity5, Unit01]] = {
        "hostile": {"hostile": 1.0, "suspect": 0.5, "unknown": 0.1, "neutral": 0.0, "friend": 0.0},
        "civil-permitted": {
            "neutral": 1.0,
            "friend": 0.5,
            "unknown": 0.25,
            "suspect": 0.0,
            "hostile": 0.0,
        },
        "clutter": {
            "neutral": 1.0,
            "unknown": 0.25,
            "friend": 0.25,
            "suspect": 0.0,
            "hostile": 0.0,
        },
    }
    #: Credit for the best response given to a hostile contact.
    respond_credit: dict[Literal["engage", "report", "hold", "none"], Unit01] = {
        "engage": 1.0,
        "report": 0.6,
        "hold": 0.25,
        "none": 0.0,
    }
    #: A permitted effector class other than the first the rule pack lists for it is a more
    #: escalatory choice; its credit is multiplied by this.
    effector_higher_factor: Unit01 = 0.7
    #: Share of the Respond node that depends on how soon the response came.
    respond_timing_share: Unit01 = 0.3
    #: Deducted from Respond for each response the rules blocked on a contact.
    blocked_attempt_penalty: Unit01 = 0.15
    #: Deducted from a threat's score for each unfixed swap, split or merge that touched it.
    track_error_penalty: Unit01 = 0.15
    track_error_cap: Unit01 = 0.30
    #: Deducted from the session score for each engagement on a track that followed nothing real.
    false_engagement_penalty: Unit01 = 0.15
    false_engagement_cap: Unit01 = 0.45
    report: ReportGrading = ReportGrading()

    @model_validator(mode="after")
    def _bands_never_reward_slowness(self) -> Self:
        ordered = sorted(self.timing_bands, key=lambda b: b.max_factor)
        for earlier, later in zip(ordered, ordered[1:], strict=False):
            if later.score > earlier.score:
                raise ValueError("a slower timing band may not earn more than a faster one")
        if len({b.max_factor for b in ordered}) != len(ordered):
            raise ValueError("timing bands must have different factors")
        return self


class RulePack(Contract):
    contract: Literal["rulepack.v1"]
    id: Slug
    version: SemVer
    title: Text
    fictional: Literal[True]
    default_action: Literal["hold"]
    effector_classes: Annotated[list[EffectorClass], Field(max_length=16)]
    rules: Annotated[list[Rule], Field(min_length=1, max_length=64)]
    weights: Weights
    thresholds: Thresholds
    #: Marks and penalties for the decision tree and the contact report (wave 6).
    scoring: Scoring = Scoring()

    @model_validator(mode="after")
    def _references(self) -> Self:
        unique([e.id for e in self.effector_classes], "effector class")
        unique([r.id for r in self.rules], "rule")
        known = {e.id for e in self.effector_classes}
        for rule in self.rules:
            missing = [e for e in rule.effector_classes if e not in known]
            if missing:
                raise ValueError(f"rule {rule.id}: unknown effector class {missing[0]!r}")
        return self
