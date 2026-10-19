"""What the application remembers about scenarios, per process: their oracle result, their feature
vector and the history of what a trainee has played.

Running the oracle takes a second or more, so a scenario's result is computed once for its content
(its id and hash) and kept. Packs are checked in a background thread after start-up; until then the
library says "not yet checked". Everything here is a cache of a pure function: losing it loses
nothing.
"""

import logging
import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.contracts import ScenarioSpec
from sim.canonical import canonical_json

from .features import Features, features_of
from .oracle import play
from .solvability import Check, evaluate, solved, wording

log = logging.getLogger("app.scenarios")
#: The bar the library and the editor judge a scenario against, in percent.
DEFAULT_BAR = 80


@dataclass(frozen=True, slots=True)
class Verdict:
    """The oracle's result for one scenario content."""

    solved: bool
    #: The lowest hostile contact score, 0 to 1; `None` when there is no hostile contact.
    oracle_score: float | None
    checks: tuple[Check, ...]
    wording: str
    seconds: float
    at: str


def content_key(spec: ScenarioSpec) -> tuple[str, str]:
    import hashlib

    return spec.id, hashlib.sha256(canonical_json(spec.model_dump(mode="json"))).hexdigest()


def run_verdict(spec: ScenarioSpec, bar: int = DEFAULT_BAR) -> Verdict:
    started = time.perf_counter()
    result = play(spec, spec.default_seed)
    checks = evaluate(spec, result, bar)
    score = checks[3].value
    return Verdict(
        solved(checks),
        float(score) if isinstance(score, int | float) else None,
        tuple(checks),
        wording(checks),
        round(time.perf_counter() - started, 2),
        datetime.now(UTC).isoformat(timespec="seconds"),
    )


class Insights:
    """Thread-safe caches of verdicts and feature vectors."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._verdicts: dict[tuple[str, str], Verdict] = {}
        self._features: dict[tuple[str, str], Features] = {}

    def verdict_if_known(self, spec: ScenarioSpec) -> Verdict | None:
        with self._lock:
            return self._verdicts.get(content_key(spec))

    def verdict(self, spec: ScenarioSpec, bar: int = DEFAULT_BAR) -> Verdict:
        """The scenario's verdict, computing it (a second or more) if it is not known."""
        key = content_key(spec)
        known = self.verdict_if_known(spec)
        if known is not None:
            return known
        fresh = run_verdict(spec, bar)
        with self._lock:
            self._verdicts[key] = fresh
        return fresh

    def remember(self, spec: ScenarioSpec, verdict: Verdict) -> None:
        with self._lock:
            self._verdicts[content_key(spec)] = verdict

    def features(self, spec: ScenarioSpec) -> Features:
        key = content_key(spec)
        with self._lock:
            known = self._features.get(key)
        if known is not None:
            return known
        fresh = features_of(spec)
        with self._lock:
            self._features[key] = fresh
        return fresh

    def warm(self, specs: list[ScenarioSpec]) -> None:
        """Compute the verdicts of `specs` one after another (run in a background thread)."""
        for spec in specs:
            try:
                self.verdict(spec)
            except Exception:  # noqa: BLE001 - one bad scenario never stops the rest
                log.exception("could not check scenario %s", spec.id)


def verdict_body(verdict: Verdict | None) -> dict[str, Any]:
    """The `solvability` object of a library row."""
    if verdict is None:
        return {"status": "unchecked", "oracle_score": None, "checked_at_run": None}
    return {
        "status": "verified" if verdict.solved else "failed",
        "oracle_score": verdict.oracle_score,
        "checked_at_run": verdict.at,
    }


def check_body(check: Check) -> dict[str, Any]:
    return {
        "name": check.name,
        "passed": check.passed,
        "value": check.value,
        "detail": check.detail,
        "code": check.code,
    }
