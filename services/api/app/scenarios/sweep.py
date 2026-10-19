"""A sweep: many generator requests spread over the whole request space, each generated and
checked again. Used by the solvability test (50 seeds on every push), the nightly job (1,000) and
`python -m app.cli scenario-sweep`.

Request `i` is a pure function of `i`: terrain, time of day and weather cycle, the five difficulty
axes and the threat mix come from keyed draws, so the same sweep runs the same requests on every
machine.
"""

from dataclasses import dataclass

from sim.behaviours import draws

from .generator import GeneratedScenario, generate
from .oracle import play
from .request import (
    ARCHETYPES,
    TERRAINS,
    TIMES_OF_DAY,
    WEATHERS,
    DifficultyVector,
    GeneratorRequest,
)
from .solvability import evaluate, solved


def _u(index: int, key: str) -> float:
    return draws.uniform(index, "sweep", key, 0, "s")


def sweep_request(index: int) -> GeneratorRequest:
    """The `index`-th request of the sweep."""
    mix = [a for a in ARCHETYPES if _u(index, f"mix-{a}") < 0.5]
    if not mix:
        mix = [ARCHETYPES[int(_u(index, "mix-one") * len(ARCHETYPES))]]
    return GeneratorRequest(
        seed=index,
        terrain=TERRAINS[index % len(TERRAINS)],
        time_of_day=TIMES_OF_DAY[(index // 3) % len(TIMES_OF_DAY)],
        weather=WEATHERS[(index // 12) % len(WEATHERS)],
        difficulty=DifficultyVector(
            threat_load=int(_u(index, "load") * 101),
            ambiguity=int(_u(index, "ambiguity") * 101),
            speed=int(_u(index, "speed") * 101),
            stealth=int(_u(index, "stealth") * 101),
            degradation=int(_u(index, "degradation") * 61),
        ),
        threat_mix=mix,
    )


@dataclass(frozen=True, slots=True)
class SweepResult:
    index: int
    ok: bool
    detail: str
    attempts: int
    relaxations: int


def check_one(index: int) -> SweepResult:
    """Generate request `index`, then check the stored spec again with a fresh oracle run."""
    request = sweep_request(index)
    try:
        made: GeneratedScenario = generate(request)
    except RuntimeError as error:
        return SweepResult(index, False, str(error), 0, 0)
    again = play(made.spec, made.spec.default_seed)
    checks = evaluate(made.spec, again, request.oracle_min_score)
    if not solved(checks):
        failed = ", ".join(c.name for c in checks if not c.passed)
        return SweepResult(
            index,
            False,
            f"the stored spec fails on a second run: {failed}",
            made.attempts,
            len(made.relaxations),
        )
    return SweepResult(index, True, made.spec.id, made.attempts, len(made.relaxations))


def run_sweep(count: int, start: int = 0, jobs: int = 1) -> list[SweepResult]:
    """Check requests `start` to `start + count - 1`, in `jobs` processes when more than one."""
    indexes = range(start, start + count)
    if jobs <= 1:
        return [check_one(i) for i in indexes]
    from concurrent.futures import ProcessPoolExecutor

    with ProcessPoolExecutor(max_workers=jobs) as pool:
        return list(pool.map(check_one, indexes, chunksize=1))
