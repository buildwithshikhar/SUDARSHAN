"""Diversity against a trainee's history: the anti-rote filter.

A candidate is compared with the feature vectors of the scenarios the trainee has already played.
Its novelty is the mean distance to its `k` nearest history vectors (Euclidean over the eight axes,
divided by the square root of eight so it lies between 0 and 1). A candidate closer than the
threshold is rejected, so a trainee does not meet the same scenario in different clothes. An empty
history never rejects.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass

from .features import AXES, Features

#: Nearest history vectors averaged into the novelty.
K = 3
#: A candidate with a novelty below this is rejected.
THRESHOLD = 0.15
_SCALE = math.sqrt(len(AXES))


@dataclass(frozen=True, slots=True)
class DiversityResult:
    history_size: int
    #: Mean distance to the `k` nearest history vectors; `None` when there is no history.
    novelty: float | None
    threshold: float
    #: `None` when there is no history to compare with.
    passes: bool | None
    #: The nearest history entries as (index in the history, distance), nearest first.
    nearest: tuple[tuple[int, float], ...]


def distance(a: Features, b: Features) -> float:
    """Distance between two scenarios, 0 (identical) to 1 (opposite corners of the cube)."""
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a.values, b.values, strict=True))) / _SCALE


def check(
    candidate: Features,
    history: Sequence[Features],
    threshold: float = THRESHOLD,
    k: int = K,
) -> DiversityResult:
    """Compare a candidate with a history; `passes` is false when its novelty is below
    `threshold`."""
    if not history:
        return DiversityResult(0, None, threshold, None, ())
    ranked = sorted(
        ((i, round(distance(candidate, h), 6)) for i, h in enumerate(history)),
        key=lambda pair: (pair[1], pair[0]),
    )
    nearest = ranked[:k]
    novelty = round(sum(d for _, d in nearest) / len(nearest), 6)
    return DiversityResult(len(history), novelty, threshold, novelty >= threshold, tuple(nearest))
