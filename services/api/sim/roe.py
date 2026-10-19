"""Rules-of-engagement check for operator actions: a pure function of the rule pack and the
context of one track.

The rule pack is a fictional, editable training rule set (locked rule 2). Rules only *permit*;
anything no rule permits is held, which is the pack's `default_action`. A verdict always names the
rule it rests on, with the pack version, so the decision panel can show why:

* permitted: the first rule, in pack order, that permits the action, whose conditions all hold,
  whose authority the session has and, for `engage`, that lists the chosen effector class;
* blocked: the *closest* rule that would permit the action, with what is missing (unmet
  conditions, authority, effector class), or "no rule" when the pack has none for this action.

`hold` is always permitted: holding fire is the default action, and a rule that permits it is cited
when one matches. Nothing here reads ground truth: the context is what the operator has assessed
and what the tracker shows.

A track's zone is the role of the smallest zone that contains it (so a track in the inner zone is
"inner", not "outer"); outside every zone it has no zone. All comparisons use plain floats and
`sqrt`, so a verdict is the same on every platform.
"""

import math
from dataclasses import dataclass, field
from typing import Any

from app.contracts.loader import load_pack
from app.contracts.paths import packs_root
from app.contracts.rulepack import Condition, Rule, RulePack
from app.contracts.scenario import ScenarioSpec

#: Class names an operator may assign: the catalogue's recognition classes plus "unknown". The
#: first four keep the positions they had before wave 8, so the decision panel's number keys
#: still mean the same thing; there are nine, which is what keys 1 to 9 can reach.
OPERATOR_CLASSES = (
    "rotary-small",
    "fixed-wing-small",
    "bird",
    "unknown",
    "fpv-small",
    "fixed-wing-medium",
    "fixed-wing-large",
    "kite",
    "balloon",
)
#: Responses: the actions the decision panel's Respond step offers.
RESPONSES = ("engage", "hold", "report")


@dataclass(frozen=True, slots=True)
class Context:
    """What the rules are asked about: the operator's own assessment plus the track's picture."""

    identity: str | None = None
    classification: str | None = None
    zone_role: str | None = None
    confidence: float = 0.0

    def view(self) -> dict[str, Any]:
        return {
            "identity": self.identity,
            "classification": self.classification,
            "zone_role": self.zone_role,
            "confidence": round(self.confidence, 3),
        }


@dataclass(frozen=True, slots=True)
class Verdict:
    permitted: bool
    #: `permitted`, `default-hold`, `no-rule`, `conditions`, `effector` or `authority`.
    code: str
    rule_id: str | None
    rule_title: dict[str, str] | None
    pack_id: str
    pack_version: str
    authority: str | None = None
    #: Machine-readable detail for the console to render in either language.
    detail: dict[str, Any] = field(default_factory=dict)

    def payload(self) -> dict[str, Any]:
        return {
            "permitted": self.permitted,
            "code": self.code,
            "rule_id": self.rule_id,
            "rule_title": self.rule_title,
            "pack_id": self.pack_id,
            "pack_version": self.pack_version,
            "authority": self.authority,
            "detail": self.detail,
        }


def _unmet(when: Condition, ctx: Context) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if when.identity_in is not None and (ctx.identity or "unknown") not in when.identity_in:
        out.append(
            {"field": "identity", "required": list(when.identity_in), "actual": ctx.identity}
        )
    if when.classification_in is not None and ctx.classification not in when.classification_in:
        out.append(
            {
                "field": "classification",
                "required": list(when.classification_in),
                "actual": ctx.classification,
            }
        )
    if when.zone_role_in is not None and ctx.zone_role not in when.zone_role_in:
        out.append({"field": "zone", "required": list(when.zone_role_in), "actual": ctx.zone_role})
    if when.min_confidence is not None and ctx.confidence < when.min_confidence:
        out.append(
            {
                "field": "confidence",
                "required": when.min_confidence,
                "actual": round(ctx.confidence, 3),
            }
        )
    return out


class RuleEngine:
    def __init__(self, pack: RulePack, spec: ScenarioSpec) -> None:
        self.pack = pack
        self.rule_texts = {r.id: r.title.model_dump() for r in pack.rules}
        self.effectors = {e.id: e for e in pack.effector_classes}
        # Smallest zone first, so the first hit is the innermost containing zone.
        self._zones = sorted(spec.zones, key=lambda z: (z.radius_m, z.id))

    def zone_role(self, x: float, y: float) -> str | None:
        for zone in self._zones:
            dx, dy = x - zone.center.x, y - zone.center.y
            if math.sqrt(dx * dx + dy * dy) <= zone.radius_m:
                return zone.role
        return None

    def summary(self) -> dict[str, Any]:
        """The rule set as a trainee may read it before and during a session."""
        return {
            "id": self.pack.id,
            "version": self.pack.version,
            "title": self.pack.title.model_dump(),
            "default_action": self.pack.default_action,
            "effector_classes": [
                {
                    "id": e.id,
                    "label": e.label.model_dump(),
                    "description": e.description.model_dump(),
                }
                for e in self.pack.effector_classes
            ],
            "rules": [
                {
                    "id": r.id,
                    "title": r.title.model_dump(),
                    "permits": list(r.permits),
                    "authority": r.authority,
                    "effector_classes": list(r.effector_classes),
                    "when": r.when.model_dump(exclude_none=True),
                }
                for r in self.pack.rules
            ],
        }

    def evaluate(
        self,
        action: str,
        ctx: Context,
        effector: str | None = None,
        *,
        commander: bool = False,
    ) -> Verdict:
        pack = self.pack
        candidates = [r for r in pack.rules if action in r.permits]

        def verdict(permitted: bool, code: str, rule: Rule | None, **detail: Any) -> Verdict:
            return Verdict(
                permitted,
                code,
                rule.id if rule else None,
                rule.title.model_dump() if rule else None,
                pack.id,
                pack.version,
                rule.authority if rule else None,
                detail,
            )

        gaps: list[tuple[int, int, Rule, list[dict[str, Any]], bool, bool]] = []
        for index, rule in enumerate(candidates):
            unmet = _unmet(rule.when, ctx)
            effector_ok = action != "engage" or (
                effector is not None and effector in rule.effector_classes
            )
            authority_ok = rule.authority == "operator" or commander
            if not unmet and effector_ok and authority_ok:
                return verdict(True, "permitted", rule, effector_class=effector)
            # The effector is the operator's own choice, so a rule that lists it is closer than one
            # that does not: a mismatch counts double.
            distance = len(unmet) + 2 * (not effector_ok) + (not authority_ok)
            gaps.append((distance, index, rule, unmet, effector_ok, authority_ok))
        if action == "hold":
            return verdict(True, "default-hold", None)
        if not gaps:
            return verdict(False, "no-rule", None, action=action)
        _, _, rule, unmet, effector_ok, authority_ok = min(gaps, key=lambda g: (g[0], g[1]))
        if unmet:
            return verdict(False, "conditions", rule, unmet=unmet)
        if not effector_ok:
            return verdict(
                False,
                "effector",
                rule,
                effector_class=effector,
                allowed=list(rule.effector_classes),
            )
        return verdict(False, "authority", rule, required=rule.authority)


def load_rule_engine(spec: ScenarioSpec) -> RuleEngine:
    """The engine for the rule pack a scenario names (id and version), from `packs/rule-packs`."""
    ref = spec.rule_pack
    for path in sorted((packs_root() / "rule-packs").glob("*.yaml")):
        pack = load_pack(path)
        if isinstance(pack, RulePack) and (pack.id, pack.version) == (ref.id, ref.version):
            return RuleEngine(pack, spec)
    raise FileNotFoundError(f"rule pack {ref.id} {ref.version} not found under packs/rule-packs")
