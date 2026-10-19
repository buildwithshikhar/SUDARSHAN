"""A preview run: play a scenario with the oracle defender and say what happened.

For the instructor only: it carries ground truth (where every threat really flew, when it was first
reported, when it was answered), none of which a trainee ever sees.
"""

from typing import Any

from app.contracts import ScenarioSpec
from app.scoring.facts import read_log
from sim.world import World

from .coverage import coverage_of
from .oracle import OracleResult, play

#: Seconds between sampled positions in the path.
PATH_STEP_S = 2.0


def preview(spec: ScenarioSpec, seed: int | None = None) -> tuple[dict[str, Any], OracleResult]:
    """Run `spec` and return the preview body and the oracle's result."""
    every = round(PATH_STEP_S * spec.tick_hz)
    track: dict[str, list[list[float]]] = {t.id: [] for t in spec.threats}

    def sample(world: World) -> None:
        if world.tick % every:
            return
        for d in world.drones:
            if d.status == "active":
                track[d.id].append([round(d.x, 1), round(d.y, 1), round(d.z, 1)])

    result = play(spec, spec.default_seed if seed is None else seed, on_step=sample)
    facts = read_log(list(result.record.events))
    answered: dict[str, float] = {}
    for call in facts.calls:
        if call.action == "engage" and call.target is not None:
            answered.setdefault(call.target, call.t)
    scores = {t.threat_id: t.score for t in result.score.threats}
    contacts = [
        {
            "id": t.id,
            "label": t.label.model_dump(),
            "disposition": t.disposition,
            "class_id": t.class_id,
            "first_report_s": facts.first_report.get(t.id),
            "answered_s": answered.get(t.id),
            "score": scores.get(t.id),
        }
        for t in spec.threats
    ]
    sensors = None
    coverage = []
    for t in spec.threats:
        if t.disposition != "hostile":
            continue
        cov = coverage_of(spec, t, sensors)
        coverage.append({"threat_id": t.id, "first_s": cov.first_s, "sensors": list(cov.sensors)})
    body = {
        "ok": True,
        "finished_s": result.finished_s,
        "oracle_score": result.score.score,
        "contacts": contacts,
        "path": {
            "step_s": PATH_STEP_S,
            "threats": [{"id": i, "points": pts} for i, pts in track.items()],
        },
        "coverage": coverage,
    }
    return body, result
