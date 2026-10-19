"""The scenario library, the scenario tools and the generator (docs/SCENARIO_ENGINE.md, "API").

For instructors and administrators. Every result that says a scenario is solvable says "verified
solvable by test run": a headless oracle defender cleared it in the sim, which is a practical
check and not a proof.
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import Principal, get_db, require_roles
from app.contracts import ScenarioSpec
from app.live.catalog import ScenarioCatalog
from app.models import Role, TrainingSession
from app.scenarios import diversity as diversity_mod
from app.scenarios.archive import Archive
from app.scenarios.features import AXES, Features
from app.scenarios.generator import GeneratedScenario, GenerationFailed, generate
from app.scenarios.insights import Insights, Verdict, check_body, run_verdict, verdict_body
from app.scenarios.language import ValidationResult, to_yaml, validate_text
from app.scenarios.lint import LintItem, lint
from app.scenarios.preview import preview
from app.scenarios.request import GENERATOR_VERSION, GeneratorRequest
from app.scenarios.sharecode import ShareCodeError, decode, encode
from app.scenarios.solvability import Check, wording
from app.scenarios.store import Saved, ScenarioStore

log = logging.getLogger("app.scenarios")

router = APIRouter(prefix="/api/v1", tags=["scenarios"])

AUTHORS = (Role.instructor, Role.admin)
AUTHOR = require_roles(*AUTHORS)
#: Scenarios that may be generated in one batch call.
BATCH_MAX = 12
#: The largest scenario text the tools accept.
YAML_MAX = 400_000


def _catalog(request: Request) -> ScenarioCatalog:
    catalog: ScenarioCatalog = request.app.state.live.catalog
    return catalog


def _store(request: Request) -> ScenarioStore:
    store: ScenarioStore = request.app.state.scenario_store
    return store


def _insights(request: Request) -> Insights:
    insights: Insights = request.app.state.insights
    return insights


# ----------------------------------------------------------------------------- shapes


class YamlBody(BaseModel):
    yaml: str = Field(max_length=YAML_MAX)
    #: Preview: the seed to run with; absent means the scenario's own.
    seed: int | None = Field(default=None, ge=0, le=2**63 - 1)
    #: Check: the lowest hostile contact score (percent) the oracle may reach.
    min_score: int = Field(default=80, ge=50, le=100)


class SaveBody(BaseModel):
    yaml: str = Field(max_length=YAML_MAX)
    tags: list[str] | None = Field(default=None, max_length=12)


class GenerateBody(BaseModel):
    request: GeneratorRequest | None = None
    code: str | None = Field(default=None, max_length=200)
    save: bool = False

    @model_validator(mode="after")
    def _one_of(self) -> "GenerateBody":
        if (self.request is None) == (self.code is None):
            raise ValueError("give exactly one of request and code")
        return self


class BatchBody(BaseModel):
    request: GeneratorRequest
    count: int = Field(ge=1, le=BATCH_MAX)
    save: bool = False


class EncodeBody(BaseModel):
    request: GeneratorRequest


def _error_body(result: ValidationResult) -> list[dict[str, Any]]:
    return [
        {"line": e.line, "column": e.column, "path": e.path, "message": e.message, "code": e.code}
        for e in result.errors
    ]


def _lint_body(items: list[LintItem]) -> list[dict[str, Any]]:
    return [
        {
            "code": i.code,
            "severity": i.severity,
            "line": i.line,
            "column": i.column,
            "message": i.message,
            "params": i.params,
        }
        for i in items
    ]


def _time_of_day(hour: float) -> str:
    if 5.0 <= hour < 8.0:
        return "dawn"
    if 8.0 <= hour < 17.0:
        return "day"
    if 17.0 <= hour < 20.0:
        return "dusk"
    return "night"


def _terrain(spec: ScenarioSpec) -> str:
    t = spec.world.terrain
    return t.id if t.kind == "pack" else "flat"


def _summary(
    spec: ScenarioSpec,
    verdict: Verdict | None,
    *,
    saved: Saved | None,
    principal: Principal,
) -> dict[str, Any]:
    meta = spec.meta
    if saved is not None and verdict is None:
        verdict = _stored_verdict(saved)
    return {
        "id": spec.id,
        "version": spec.version,
        "title": spec.title.model_dump(),
        "summary": spec.summary.model_dump(),
        "origin": meta.origin if meta else "scripted",
        "playable": True if meta is None else meta.playable,
        "tags": [] if meta is None else list(meta.tags),
        "curriculum_order": None if meta is None else meta.curriculum_order,
        "difficulty": None if meta is None else meta.difficulty,
        "terrain": _terrain(spec),
        "time_of_day": _time_of_day(spec.world.start_time_of_day_h),
        "weather": spec.world.weather.condition,
        "duration_s": spec.duration_s,
        "hostile_count": sum(1 for t in spec.threats if t.disposition == "hostile"),
        "contact_count": len(spec.threats),
        "sensor_count": len(spec.sensors),
        "degraded": bool(spec.degradations),
        "group_count": len(spec.groups),
        "rule_pack": spec.rule_pack.model_dump(),
        "solvability": verdict_body(verdict),
        "can_delete": saved is not None
        and (principal.user.role is Role.admin or saved.owner_id == principal.user.id),
    }


def _stored_verdict(saved: Saved) -> Verdict | None:
    """The verdict a saved scenario was kept with, rebuilt from its stored checks."""
    if not saved.checks:
        return None
    checks = tuple(
        Check(c["name"], bool(c["passed"]), c["value"], str(c["detail"]), str(c["code"]))
        for c in saved.checks
        if str(c.get("code", "")).startswith("solvability.")
    )
    if len(checks) != 4:
        return None
    score = checks[3].value
    ok = all(c.passed for c in checks)
    return Verdict(
        ok,
        float(score) if isinstance(score, int | float) else None,
        checks,
        wording(list(checks)),
        0.0,
        "",
    )


def _find(request: Request, scenario_id: str) -> tuple[ScenarioSpec, Saved | None]:
    entry = _catalog(request).entries().get(scenario_id)
    if entry is not None:
        return entry.spec, None
    saved = _store(request).get(scenario_id)
    if saved is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such scenario")
    return saved.spec, saved


def _history(request: Request, db: Session, user_id: str) -> list[Features]:
    """The feature vectors of the scenarios this user has played."""
    rows = db.execute(
        select(TrainingSession.scenario_id, TrainingSession.scenario_version)
        .where(TrainingSession.user_id == user_id, TrainingSession.status != "lobby")
        .distinct()
        .order_by(TrainingSession.scenario_id, TrainingSession.scenario_version)
    ).all()
    out: list[Features] = []
    for scenario_id, version in rows:
        entry = _catalog(request).get(scenario_id, version)
        if entry is not None:
            out.append(_insights(request).features(entry.spec))
    return out


def _diversity_body(result: diversity_mod.DiversityResult) -> dict[str, Any]:
    return {
        "history_size": result.history_size,
        "novelty": result.novelty,
        "threshold": result.threshold,
        "passes": result.passes,
        "nearest": [{"scenario_id": str(i), "distance": d} for i, d in result.nearest],
    }


# ----------------------------------------------------------------------------- the library


@router.get("/scenario-library")
def library(request: Request, principal: Principal = Depends(AUTHOR)) -> list[dict[str, Any]]:
    insights = _insights(request)
    rows = [
        _summary(e.spec, insights.verdict_if_known(e.spec), saved=None, principal=principal)
        for e in _catalog(request).entries().values()
    ]
    packs = {r["id"] for r in rows}
    for saved in _store(request).all():
        if saved.spec.id in packs:
            continue
        rows.append(
            _summary(
                saved.spec, insights.verdict_if_known(saved.spec), saved=saved, principal=principal
            )
        )
    return sorted(
        rows,
        key=lambda r: (
            r["curriculum_order"] is None,
            r["curriculum_order"] or 0,
            r["origin"],
            r["id"],
        ),
    )


@router.get("/scenario-library/{scenario_id}")
def library_item(
    scenario_id: str, request: Request, principal: Principal = Depends(AUTHOR)
) -> dict[str, Any]:
    spec, saved = _find(request, scenario_id)
    insights = _insights(request)
    verdict = insights.verdict_if_known(spec) or (None if saved is None else _stored_verdict(saved))
    if verdict is None:
        verdict = insights.verdict(spec)
    text = saved.yaml if saved is not None and saved.yaml else to_yaml(spec)
    parsed = validate_text(text)
    items = lint(spec, parsed.lines)
    body = _summary(spec, verdict, saved=saved, principal=principal)
    body.update(
        {
            "spec": spec.model_dump(mode="json"),
            "yaml": text,
            "lint": _lint_body(items),
            "checks": [check_body(c) for c in verdict.checks],
            "solvability_wording": verdict.wording,
            "features": insights.features(spec).as_dict(),
            "code": None if saved is None else saved.code,
            "request": None if saved is None else saved.request,
        }
    )
    return body


@router.delete("/scenario-library/{scenario_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_scenario(
    scenario_id: str, request: Request, principal: Principal = Depends(AUTHOR)
) -> None:
    if scenario_id in _catalog(request).entries():
        raise HTTPException(status.HTTP_403_FORBIDDEN, "A shipped scenario cannot be deleted")
    saved = _store(request).get(scenario_id)
    if saved is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such scenario")
    if principal.user.role is not Role.admin and saved.owner_id != principal.user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only its owner or an administrator can")
    _store(request).delete(scenario_id)


@router.post("/scenario-library", status_code=status.HTTP_201_CREATED)
def save_scenario(
    body: SaveBody, request: Request, principal: Principal = Depends(AUTHOR)
) -> dict[str, Any]:
    result = validate_text(body.yaml)
    if not result.valid or result.spec is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            {"message": "The scenario has errors", "errors": _error_body(result)},
        )
    spec = result.spec
    errors = [i for i in lint(spec, result.lines) if i.severity == "error"]
    if errors:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            {"message": "The scenario fails the linter", "lint": _lint_body(errors)},
        )
    if spec.id.startswith("gen-"):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "gen- ids are the generator's")
    if spec.id in _catalog(request).entries():
        raise HTTPException(status.HTTP_409_CONFLICT, "A shipped scenario has that id")
    held = _store(request).get(spec.id)
    if (
        held is not None
        and held.owner_id != principal.user.id
        and principal.user.role is not Role.admin
    ):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Another author owns that id")
    data = spec.model_dump(mode="json")
    meta = data.get("meta") or {}
    data["meta"] = {
        "origin": "authored",
        "playable": meta.get("playable", True),
        "tags": body.tags if body.tags is not None else meta.get("tags", []),
        "curriculum_order": meta.get("curriculum_order"),
        "difficulty": meta.get("difficulty"),
        "generated": None,
    }
    final = ScenarioSpec.model_validate(data)
    verdict = run_verdict(final)
    insights = _insights(request)
    insights.remember(final, verdict)
    saved = _store(request).put(
        final,
        owner_id=principal.user.id,
        origin="authored",
        yaml=to_yaml(final),
        checks=[check_body(c) for c in verdict.checks],
        features=insights.features(final).as_dict(),
    )
    return _summary(final, verdict, saved=saved, principal=principal)


# ----------------------------------------------------------------------------- the tools


@router.post("/scenario-tools/validate")
def validate(body: YamlBody, principal: Principal = Depends(AUTHOR)) -> dict[str, Any]:
    result = validate_text(body.yaml)
    items = lint(result.spec, result.lines) if result.spec is not None else []
    return {
        "valid": result.valid,
        "errors": _error_body(result),
        "lint": _lint_body(items),
        "spec": None if result.spec is None else result.spec.model_dump(mode="json"),
    }


@router.post("/scenario-tools/check")
def check(
    body: YamlBody,
    request: Request,
    principal: Principal = Depends(AUTHOR),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    result = validate_text(body.yaml)
    if not result.valid or result.spec is None:
        return {
            "valid": False,
            "errors": _error_body(result),
            "lint": [],
            "solvability": {
                "ran": False,
                "solved": False,
                "oracle_score": None,
                "checks": [],
                "seconds": 0.0,
                "wording": "not verified solvable",
            },
            "diversity": _diversity_body(diversity_mod.check(Features((0.0,) * len(AXES)), [])),
            "features": {},
        }
    spec = result.spec
    verdict = run_verdict(spec, body.min_score)
    insights = _insights(request)
    features = insights.features(spec)
    history = _history(request, db, principal.user.id)
    return {
        "valid": True,
        "errors": [],
        "lint": _lint_body(lint(spec, result.lines)),
        "solvability": {
            "ran": True,
            "solved": verdict.solved,
            "oracle_score": verdict.oracle_score,
            "checks": [check_body(c) for c in verdict.checks],
            "seconds": verdict.seconds,
            "wording": verdict.wording,
        },
        "diversity": _diversity_body(diversity_mod.check(features, history)),
        "features": features.as_dict(),
    }


@router.post("/scenario-tools/preview")
def preview_run(body: YamlBody, principal: Principal = Depends(AUTHOR)) -> dict[str, Any]:
    result = validate_text(body.yaml)
    if not result.valid or result.spec is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            {"message": "The scenario has errors", "errors": _error_body(result)},
        )
    out, _ = preview(result.spec, body.seed)
    return out


# ----------------------------------------------------------------------------- the generator


def _generated_body(made: GeneratedScenario, saved: bool) -> dict[str, Any]:
    return {
        "id": made.spec.id,
        "spec": made.spec.model_dump(mode="json"),
        "yaml": to_yaml(made.spec),
        "code": made.code,
        "generator_version": made.generator_version,
        "request": made.request.model_dump(mode="json"),
        "attempts": made.attempts,
        "relaxations": list(made.relaxations),
        "checks": [check_body(c) for c in made.checks],
        "solvability_wording": made.wording,
        "oracle_score": made.oracle_score,
        "features": made.features.as_dict(),
        "diversity": _diversity_body(made.diversity),
        "spec_sha256": made.spec_sha256,
        "rejections": made.rejections,
        "saved": saved,
    }


def _keep(request: Request, made: GeneratedScenario, principal: Principal) -> None:
    checks = [check_body(c) for c in made.checks]
    _store(request).put(
        made.spec,
        owner_id=principal.user.id,
        origin="generated",
        yaml=to_yaml(made.spec),
        request=made.request.model_dump(mode="json"),
        code=made.code,
        checks=checks,
        features=made.features.as_dict(),
    )


def _resolve(body_request: GeneratorRequest | None, code: str | None) -> GeneratorRequest:
    if body_request is not None:
        return body_request
    assert code is not None
    try:
        return decode(code).request
    except ShareCodeError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(error)) from error


@router.post("/generator/generate")
def generate_one(
    body: GenerateBody,
    request: Request,
    principal: Principal = Depends(AUTHOR),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    spec_request = _resolve(body.request, body.code)
    history = _history(request, db, principal.user.id)
    try:
        made = generate(spec_request, history)
    except GenerationFailed as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(error)) from error
    if body.save:
        _keep(request, made, principal)
    return _generated_body(made, body.save)


@router.post("/generator/batch")
def generate_batch(
    body: BatchBody,
    request: Request,
    principal: Principal = Depends(AUTHOR),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    history = _history(request, db, principal.user.id)
    results: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for i in range(body.count):
        spec_request = body.request.model_copy(update={"seed": body.request.seed + i})
        try:
            made = generate(spec_request, history)
        except GenerationFailed as error:
            failures.append({"seed": spec_request.seed, "detail": str(error)})
            continue
        history = [*history, made.features]  # the next one must differ from this one too
        if body.save:
            _keep(request, made, principal)
        results.append(_generated_body(made, body.save))
    return {"scenarios": results, "failures": failures}


@router.get("/generator/archive")
def archive(
    request: Request,
    x: str = Query(default="threat_count"),
    y: str = Query(default="id_ambiguity"),
    principal: Principal = Depends(AUTHOR),
) -> dict[str, Any]:
    """The MAP-Elites archive of the scenarios the instance holds that are verified solvable by
    test run and whose result is known."""
    insights = _insights(request)
    found = Archive()
    specs = [e.spec for e in _catalog(request).entries().values()]
    saved = {s.spec.id: s for s in _store(request).all()}
    specs += [s.spec for s in saved.values() if s.spec.id not in {p.id for p in specs}]
    for spec in specs:
        verdict = insights.verdict_if_known(spec)
        if verdict is None and spec.id in saved:
            verdict = _stored_verdict(saved[spec.id])
        if verdict is not None and verdict.solved and verdict.oracle_score is not None:
            found.add(spec.id, insights.features(spec), verdict.oracle_score)
    try:
        return found.to_dict(x, y)
    except ValueError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(error)) from error


@router.get("/generator/code")
def decode_code(
    code: str = Query(max_length=200), principal: Principal = Depends(AUTHOR)
) -> dict[str, Any]:
    try:
        decoded = decode(code)
    except ShareCodeError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(error)) from error
    return {
        "request": decoded.request.model_dump(mode="json"),
        "generator_version": decoded.generator_version,
        "current_version": GENERATOR_VERSION,
        "matches": decoded.generator_version == GENERATOR_VERSION,
    }


@router.post("/generator/code")
def encode_request(body: EncodeBody, principal: Principal = Depends(AUTHOR)) -> dict[str, Any]:
    return {"code": encode(body.request), "generator_version": GENERATOR_VERSION}
