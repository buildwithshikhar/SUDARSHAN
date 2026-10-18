"""Tree positions: mapped trees plus a seeded scatter inside wooded polygons."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
from numpy.typing import NDArray

from .buildings import XY
from .osm import Point

MAX_TREES = 4000
# Trees per square metre and (min, max) height in metres, by landcover class.
SCATTER: dict[str, tuple[float, float, float]] = {
    "forest": (1.0 / 220.0, 7.0, 14.0),
    "orchard": (1.0 / 90.0, 5.0, 8.0),
    "scrub": (1.0 / 700.0, 5.0, 8.0),
}


def points_in_ring(
    xs: NDArray[np.float64], ys: NDArray[np.float64], ring: Sequence[XY]
) -> NDArray[np.bool_]:
    """Vectorised even-odd point-in-polygon test."""
    inside = np.zeros(xs.shape, dtype=bool)
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if yi != yj:
            cond = (yi > ys) != (yj > ys)
            xcross = (xj - xi) * (ys - yi) / (yj - yi) + xi
            inside ^= cond & (xs < xcross)
        j = i
    return inside


def scatter_trees(
    areas: Sequence[tuple[str, str, list[XY]]],
    mapped: Sequence[tuple[float, float, float | None]],
    half_extent_m: float,
    seed: int,
) -> list[tuple[float, float, float]]:
    """Return trees (x, y, height_m) sorted by (y, x), at most ``MAX_TREES``.

    ``areas`` holds (osm_id, class, ring) for forest, orchard and scrub polygons;
    ``mapped`` holds individually mapped trees. Mapped trees are always kept.
    """
    rng = np.random.default_rng(seed)
    trees: list[tuple[float, float, float]] = []
    for x, y, h in mapped:
        if abs(x) <= half_extent_m and abs(y) <= half_extent_m:
            height = h if h is not None and 3.0 <= h <= 30.0 else float(rng.uniform(5.0, 14.0))
            trees.append((round(x, 1), round(y, 1), round(height, 1)))
    scattered: list[tuple[float, float, float]] = []
    for _oid, cls, ring in sorted(areas, key=lambda a: a[0]):
        if cls not in SCATTER or len(ring) < 3:
            continue
        density, h_lo, h_hi = SCATTER[cls]
        x0 = max(min(p[0] for p in ring), -half_extent_m)
        x1 = min(max(p[0] for p in ring), half_extent_m)
        y0 = max(min(p[1] for p in ring), -half_extent_m)
        y1 = min(max(p[1] for p in ring), half_extent_m)
        if x1 <= x0 or y1 <= y0:
            continue
        n = int(np.ceil((x1 - x0) * (y1 - y0) * density))
        cx = rng.uniform(x0, x1, n)
        cy = rng.uniform(y0, y1, n)
        ch = rng.uniform(h_lo, h_hi, n)
        keep = points_in_ring(cx, cy, ring)
        for x, y, h in zip(cx[keep], cy[keep], ch[keep], strict=True):
            scattered.append((round(float(x), 1), round(float(y), 1), round(float(h), 1)))
    room = max(MAX_TREES - len(trees), 0)
    if len(scattered) > room:
        pick = np.sort(rng.choice(len(scattered), size=room, replace=False))
        scattered = [scattered[int(i)] for i in pick]
    trees.extend(scattered)
    trees.sort(key=lambda t: (t[1], t[0], t[2]))
    return trees[:MAX_TREES]


def mapped_tree_points(
    points: Sequence[Point], project: tuple[NDArray[np.float64], NDArray[np.float64]]
) -> list[tuple[float, float, float | None]]:
    """Pair projected coordinates with the optional ``height`` tag of each mapped tree."""
    out: list[tuple[float, float, float | None]] = []
    xs, ys = project
    for p, x, y in zip(points, xs, ys, strict=True):
        h: float | None
        try:
            h = float(p.tags["height"].split()[0]) if "height" in p.tags else None
        except ValueError:
            h = None
        out.append((float(x), float(y), h))
    return out


def vegetation_json(trees: Sequence[tuple[float, float, float]]) -> dict[str, object]:
    return {"format": "terrain-vegetation.v1", "trees": [[x, y, h] for x, y, h in trees]}
