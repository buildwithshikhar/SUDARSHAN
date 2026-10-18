"""The first three lessons: where the most marks were lost.

Each mark lost has a cost in the units of the contact's own score: a node's shortfall times its
share of the weights (a hostile contact's four nodes and its report share one total of 1; any other
contact's nodes share it alone), a penalty, or a hard fail's whole score. The three costliest, ties
broken by contact order and then by node order, become lessons. A lesson is a key and the parameters
of the node or finding it comes from, plus the contact's label.
"""

from typing import Any

from app.contracts.score import Finding, Lesson, ThreatScore

MIN_COST = 0.005
LESSON_COUNT = 3
_NODE_ORDER = {"detect": 0, "classify": 1, "assess": 2, "respond": 3}
#: Reasons that lost nothing by their nature, so they are never a lesson.
_NO_LESSON = ("assess.exact", "respond.hold-fire")


def _finding_key(finding: Finding) -> str:
    if finding.kind == "hard-fail":
        return finding.reason.replace("finding.hard-fail", "lesson.hard-fail")
    if finding.kind == "track-error":
        return "lesson.track-error"
    if finding.kind == "blocked-attempt":
        return "lesson.blocked-attempt"
    return "lesson.false-engagement"


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
                cost = (1.0 - node.score) * node.weight / norm
                lossy_correct = node.reason == "classify.correct" and node.score < 1.0
                if cost >= MIN_COST and (lossy_correct or node.reason not in _NO_LESSON):
                    found.append(
                        (
                            cost,
                            index,
                            _NODE_ORDER[node.node],
                            _lesson(f"lesson.{node.reason}", threat, node.params, cost),
                        )
                    )
            if threat.report is not None:
                cost = (1.0 - threat.report.score) * report_weight
                key = "lesson.report.filed" if threat.report.filed else "lesson.report.missing"
                if cost >= MIN_COST:
                    found.append((cost, index, 4, _lesson(key, threat, threat.report.params, cost)))
        for finding in threat.findings:
            if finding.kind in ("track-error", "blocked-attempt") and finding.cost >= MIN_COST:
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
    found.sort(key=lambda c: (-c[0], c[1], c[2]))
    return [c[3] for c in found[:LESSON_COUNT]]
