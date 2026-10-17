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
    """Fictional, editable timing standards in seconds (no public doctrinal source; Q-12)."""

    detect_within_s: Annotated[float, Field(gt=0, le=600)]
    classify_within_s: Annotated[float, Field(gt=0, le=600)]
    report_within_s: Annotated[float, Field(gt=0, le=600)]


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
