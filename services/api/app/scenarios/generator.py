"""The scenario generator: a request in, a scenario "verified solvable by test run" out.

Seeded sample, hard constraints by rejection, a headless oracle-defender run, a feature vector and a
diversity check against the trainee's history, then the spec, its hash and every check result.
The whole call is a pure function of the request, the generator version and the history: the same
request and version give a byte-identical spec (docs/SCENARIO_ENGINE.md, ADR-025).

Retry budget. `max_attempts` candidates are tried at the requested constraint set. If none passes,
the softest constraint is relaxed and logged, and another `max_attempts` are tried; the stages are
in `STAGES`, softest first. The hard constraints, and every solved check but the oracle's score bar,
are never relaxed, and nothing unsolved is ever returned.
"""

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass, field

from app.contracts import ScenarioSpec
from sim.canonical import canonical_json
from sim.catalogue import Catalogue, load_catalogue

from . import diversity as diversity_mod
from .constraints import hard_constraints
from .features import Features, features_of
from .oracle import play
from .request import GENERATOR_VERSION, DifficultyVector, GeneratorRequest
from .sampler import Sampler, scenario_id
from .solvability import Check, evaluate, solved, wording

#: Realised feature axes held to the request, with the tolerance of the first stage.
FIDELITY_TOLERANCE = 0.30
#: The lowest oracle bar a relaxation may reach, in percent.
FLOOR_ORACLE_PERCENT = 50


class GenerationFailed(RuntimeError):
    """No candidate passed within the budget, even after every relaxation."""

    def __init__(self, request: GeneratorRequest, attempts: int, rejections: dict[str, int]):
        reasons = ", ".join(
            f"{k} x{v}" for k, v in sorted(rejections.items(), key=lambda kv: -kv[1])
        )
        super().__init__(
            f"no scenario for seed {request.seed} in {attempts} attempts; rejected for: {reasons}"
        )
        self.request, self.attempts, self.rejections = request, attempts, rejections


@dataclass(frozen=True, slots=True)
class Stage:
    """One step of the relaxation ladder."""

    name: str
    #: Multiplies the diversity threshold; `None` drops the filter.
    diversity: float | None
    tolerance: float
    #: Points taken off threat load, ambiguity, stealth and degradation.
    ease: int
    #: Replaces the threat mix with a single drone.
    single_only: bool = False


STAGES: tuple[Stage, ...] = (
    Stage("requested", 1.0, FIDELITY_TOLERANCE, 0),
    Stage("diversity-halved", 0.5, FIDELITY_TOLERANCE, 0),
    Stage("diversity-dropped", None, FIDELITY_TOLERANCE, 0),
    Stage("targets-widened", None, 0.45, 0),
    Stage("eased-25", None, 0.60, 25),
    Stage("eased-50", None, 0.75, 50),
    Stage("single-drone", None, 1.0, 100, single_only=True),
)


@dataclass(frozen=True, slots=True)
class GeneratedScenario:
    """A generated scenario and everything that was checked about it."""

    spec: ScenarioSpec
    request: GeneratorRequest
    code: str
    generator_version: str
    #: Candidates tried, counting the accepted one.
    attempts: int
    #: What was relaxed to get here, in order; empty when nothing was.
    relaxations: tuple[str, ...]
    checks: tuple[Check, ...]
    features: Features
    diversity: diversity_mod.DiversityResult
    #: The lowest hostile contact score the oracle reached, 0 to 1.
    oracle_score: float
    spec_sha256: str
    #: Why candidates were thrown away, by reason, across all attempts.
    rejections: dict[str, int] = field(default_factory=dict)

    @property
    def wording(self) -> str:
        """The four solved checks decide it; the diversity and target checks do not."""
        return wording([c for c in self.checks if c.code.startswith("solvability.")])

    def spec_json(self) -> bytes:
        """The spec's canonical JSON: the same bytes for the same request and version."""
        return canonical_json(self.spec.model_dump(mode="json"))


def _eased(request: GeneratorRequest, stage: Stage) -> GeneratorRequest:
    """The request the sampler is given at a stage: the same, with the hard axes eased."""
    if stage.ease == 0:
        return request
    d = request.difficulty
    easier = DifficultyVector(
        threat_load=max(5 if stage.single_only else 0, d.threat_load - stage.ease),
        ambiguity=max(0, d.ambiguity - stage.ease),
        speed=d.speed,
        stealth=max(0, d.stealth - stage.ease),
        degradation=max(0, d.degradation - stage.ease),
    )
    mix = ["single"] if stage.single_only else request.threat_mix
    return request.model_copy(update={"difficulty": easier, "threat_mix": mix})


def _describe(stage: Stage, request: GeneratorRequest, used: GeneratorRequest) -> str:
    if stage.name == "diversity-halved":
        return "the diversity threshold was halved"
    if stage.name == "diversity-dropped":
        return "the diversity filter was dropped"
    if stage.name == "targets-widened":
        return f"the difficulty targets were widened to {stage.tolerance:.2f}"
    if stage.single_only:
        return "the request was eased to a single drone at low load"
    a, b = request.difficulty, used.difficulty
    return (
        f"threat load {a.threat_load} to {b.threat_load}, ambiguity {a.ambiguity} to "
        f"{b.ambiguity}, stealth {a.stealth} to {b.stealth}, degradation {a.degradation} to "
        f"{b.degradation}"
    )


def _fidelity(requested: GeneratorRequest, features: Features, tolerance: float) -> Check:
    """The realised threat count and ambiguity against what was asked for (the other axes are
    realised by class choice and are not held to a number)."""
    d = requested.difficulty
    gaps = {
        "threat_count": abs(features["threat_count"] - d.threat_load / 100.0),
        "id_ambiguity": abs(features["id_ambiguity"] - d.ambiguity / 100.0),
    }
    worst = max(gaps.values())
    ok = worst <= tolerance
    return Check(
        "difficulty-targets",
        ok,
        round(worst, 4),
        f"threat count and ambiguity within {tolerance:.2f} of the request"
        if ok
        else "off the request by "
        + ", ".join(f"{k} {v:.2f}" for k, v in gaps.items() if v > tolerance),
        "generator.targets",
    )


def _lint_problems(spec: ScenarioSpec) -> list[str]:
    """Linter errors for a candidate (the same linter the editor shows)."""
    from .lint import lint

    return [f"{i.code}: {i.message}" for i in lint(spec) if i.severity == "error"]


def _finish(spec: ScenarioSpec, request: GeneratorRequest, code: str) -> ScenarioSpec:
    """Put the id, version, metadata and difficulty into the accepted candidate."""
    d = request.difficulty
    tags = [
        "generated",
        request.terrain,
        request.time_of_day,
        request.weather,
        *(request.threat_mix if len(request.threat_mix) < 6 else []),
    ]
    data = spec.model_dump(mode="json")
    data["id"] = scenario_id(request)
    data["meta"] = {
        "origin": "generated",
        "playable": True,
        "tags": tags,
        "difficulty": round(
            (d.threat_load + d.ambiguity + d.speed + d.stealth + d.degradation) / 5
        ),
        "generated": {"generator_version": GENERATOR_VERSION, "code": code},
    }
    return ScenarioSpec.model_validate(data)


def generate(
    request: GeneratorRequest,
    history: Sequence[Features] = (),
    *,
    threshold: float = diversity_mod.THRESHOLD,
    catalogue: Catalogue | None = None,
) -> GeneratedScenario:
    """Generate one scenario for `request`, diverse against `history`.

    Raises `GenerationFailed` when nothing passes within the budget at any stage.
    """
    from .sharecode import encode

    cat = load_catalogue() if catalogue is None else catalogue
    code = encode(request)
    rejections: dict[str, int] = {}
    relaxations: list[str] = []
    tried = 0

    def reject(reason: str) -> None:
        rejections[reason] = rejections.get(reason, 0) + 1

    for index, stage in enumerate(STAGES):
        used = _eased(request, stage)
        if (
            stage.diversity != 1.0
            and not history
            and stage.ease == 0
            and stage.tolerance == FIDELITY_TOLERANCE
        ):
            continue  # with no history the filter never rejects, so there is nothing to relax
        if index > 0:
            relaxations.append(_describe(stage, request, used))
        bar = request.oracle_min_score
        for k in range(request.max_attempts):
            attempt = index * request.max_attempts + k
            tried += 1
            try:
                candidate = Sampler(used, attempt, cat).build()
            except ValueError:
                reject("contract")
                continue
            if bad := hard_constraints(candidate, cat):
                reject(bad[0].reason)
                continue
            if problems := _lint_problems(candidate):
                reject(problems[0].split(":", 1)[0])
                continue
            features = features_of(candidate)
            fidelity = _fidelity(request, features, stage.tolerance)
            if not fidelity.passed:
                reject("difficulty-targets")
                continue
            result = play(candidate, candidate.default_seed)
            checks = evaluate(candidate, result, bar)
            if not solved(checks):
                reject("oracle:" + next(c.name for c in checks if not c.passed))
                continue
            limit = None if stage.diversity is None else threshold * stage.diversity
            novelty = diversity_mod.check(
                features, history, diversity_mod.THRESHOLD if limit is None else limit
            )
            if limit is not None and novelty.passes is False:
                reject("diversity")
                continue
            spec = _finish(candidate, request, code)
            sha = hashlib.sha256(canonical_json(spec.model_dump(mode="json"))).hexdigest()
            score = checks[3].value
            below = novelty.passes is False
            diversity_check = Check(
                "diversity",
                not below,
                novelty.novelty,
                "no history to compare with"
                if novelty.novelty is None
                else f"novelty {novelty.novelty:.2f} against {novelty.history_size} played"
                + (" (below the threshold; the filter was relaxed)" if below else ""),
                "generator.diversity",
            )
            return GeneratedScenario(
                spec=spec,
                request=request,
                code=code,
                generator_version=GENERATOR_VERSION,
                attempts=tried,
                relaxations=tuple(relaxations),
                checks=(*checks, fidelity, diversity_check),
                features=features,
                diversity=novelty,
                oracle_score=float(score) if isinstance(score, int | float) else 0.0,
                spec_sha256=sha,
                rejections=dict(rejections),
            )
    raise GenerationFailed(request, tried, rejections)


__all__ = [
    "GENERATOR_VERSION",
    "STAGES",
    "GeneratedScenario",
    "GenerationFailed",
    "generate",
]
