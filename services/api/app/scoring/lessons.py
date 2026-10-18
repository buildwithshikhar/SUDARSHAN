"""The first three lessons: where the most marks were lost.

Each mark lost has a cost in the units of the contact's own score: a node's shortfall times its
share of the weights (a hostile contact's four nodes and its report share one total of 1; any other
contact's nodes share it alone), a penalty, or a hard fail's whole score. The three costliest, ties
broken by contact order and then by node order, become lessons. A lesson is a key and the parameters
of the node or finding it comes from, plus the contact's label.
"""

from typing import Any

from app.contracts.score import Finding, Lesson, NodeResult, ThreatScore

MIN_COST = 0.005
LESSON_COUNT = 3
_NODE_ORDER = {"detect": 0, "classify": 1, "assess": 2, "respond": 3}
#: Reasons that lost nothing by their nature, so they are never a lesson.
_NO_LESSON = ("assess.exact",)


def _finding_key(finding: Finding) -> str:
    if finding.kind == "hard-fail":
        return finding.reason.replace("finding.hard-fail", "lesson.hard-fail")
    if finding.kind == "track-error":
        return "lesson.track-error"
    return "lesson.false-engagement"


def _node_key(node: NodeResult) -> str | None:
    """The lesson for a node that lost marks, or none where the loss is the lesson of a finding
    (a hard fail) or the node cannot lose by its nature."""
    if node.reason == "respond.hold-fire":
        # The only way to lose marks holding fire is to have tried to engage and been blocked.
        return "lesson.blocked-attempt" if node.params.get("blocked_attempts") else None
    if node.reason == "respond.breach":
        return None
    if node.reason == "classify.correct":
        return "lesson.classify.correct"
    return None if node.reason in _NO_LESSON else f"lesson.{node.reason}"


def _lesson(key: str, threat: ThreatScore, params: dict[str, Any], cost: float) -> Lesson:
    return Lesson(
        key=key,
        params={"threat": threat.label.model_dump(), **params},
        threat_id=threat.threat_id,
        cost=cost,
    )


def lessons(
    threats: list[ThreatScore], session_findings: list[Finding], report_weight: float
) -> list[Lesson]:
    found: list[tuple[float, int, int, Lesson]] = []
    for index, threat in enumerate(threats):
        if not threat.presented or threat.score is None:
            continue
        node_weight = sum(n.weight for n in threat.nodes)
        hostile = threat.report is not None
        norm = 1.0 if hostile else node_weight
        if threat.hard_fail:
            for finding in threat.findings:
                if finding.kind == "hard-fail":
                    found.append(
                        (
                            finding.cost,
                            index,
                            0,
                            _lesson(_finding_key(finding), threat, finding.params, finding.cost),
                        )
                    )
        else:
            for node in threat.nodes:
                cost = round((1.0 - node.score) * node.weight / norm, 6)
                key = _node_key(node)
                params = node.params
                if key == "lesson.blocked-attempt":
                    params = {"attempts": node.params["blocked_attempts"]}
                if key is not None and cost >= MIN_COST:
                    found.append(
                        (cost, index, _NODE_ORDER[node.node], _lesson(key, threat, params, cost))
                    )
            if threat.report is not None:
                cost = (1.0 - threat.report.score) * report_weight
                key = "lesson.report.filed" if threat.report.filed else "lesson.report.missing"
                if cost >= MIN_COST:
                    found.append((cost, index, 4, _lesson(key, threat, threat.report.params, cost)))
        for finding in threat.findings:
            if finding.kind == "track-error" and finding.cost >= MIN_COST:
                found.append(
                    (
                        finding.cost,
                        index,
                        5,
                        _lesson(_finding_key(finding), threat, finding.params, finding.cost),
                    )
                )
    for finding in session_findings:
        if finding.kind == "false-engagement" and finding.cost >= MIN_COST:
            found.append(
                (
                    finding.cost,
                    len(threats),
                    6,
                    Lesson(key=_finding_key(finding), params=finding.params, cost=finding.cost),
                )
            )
    found.sort(key=lambda c: (-round(c[0], 6), c[1], c[2]))
    return [c[3] for c in found[:LESSON_COUNT]]
