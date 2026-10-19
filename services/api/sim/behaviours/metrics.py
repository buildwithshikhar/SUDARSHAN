"""Cohesion metrics of a group, for the tests and for the after-action review.

Each takes plain sequences, uses only `+ - * /` and `sqrt` in a fixed order, and so gives the same
numbers on every platform. A heading is a unit vector (east, north).
"""

import math
from collections.abc import Sequence

from . import links


def polarisation(ux: Sequence[float], uy: Sequence[float]) -> float:
    """The Vicsek order parameter: the length of the mean unit heading. 1 is a perfectly aligned
    group; about 1/sqrt(n) is a random one."""
    n = len(ux)
    sx = sy = 0.0
    for a, b in zip(ux, uy, strict=True):
        sx += a
        sy += b
    return math.sqrt(sx * sx + sy * sy) / n


def centroid(xs: Sequence[float], ys: Sequence[float]) -> tuple[float, float]:
    n = len(xs)
    sx = sy = 0.0
    for a, b in zip(xs, ys, strict=True):
        sx += a
        sy += b
    return sx / n, sy / n


def radius_of_gyration(xs: Sequence[float], ys: Sequence[float]) -> float:
    """Root-mean-square distance of the members from their centroid (metres)."""
    cx, cy = centroid(xs, ys)
    total = 0.0
    for a, b in zip(xs, ys, strict=True):
        total += (a - cx) * (a - cx) + (b - cy) * (b - cy)
    return math.sqrt(total / len(xs))


def mean_nearest_neighbour(xs: Sequence[float], ys: Sequence[float]) -> float:
    """Mean over the members of the distance to the nearest other member (metres)."""
    n = len(xs)
    total = 0.0
    for i in range(n):
        best = math.inf
        for j in range(n):
            if i != j:
                d = links.distance(xs[i], ys[i], xs[j], ys[j])
                best = d if d < best else best
        total += best
    return total / n


def cohesion_index(xs: Sequence[float], ys: Sequence[float], radius: float) -> float:
    """The share of the group in its largest cluster, where members closer than `radius` metres
    are chained into one cluster. 1 is a single connected group."""
    n = len(xs)
    ids = [f"{i:04d}" for i in range(n)]
    pairs = [
        (ids[i], ids[j])
        for i in range(n)
        for j in range(i + 1, n)
        if links.distance(xs[i], ys[i], xs[j], ys[j]) <= radius
    ]
    parts = links.Graph(ids, pairs).components()
    return max(len(p) for p in parts) / n


def component_count(ids: Sequence[str], pairs: Sequence[links.Pair]) -> int:
    """Connected components of the communication graph."""
    return links.component_count(ids, pairs)
