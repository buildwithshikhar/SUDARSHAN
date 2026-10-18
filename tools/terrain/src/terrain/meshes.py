"""Terrain and building meshes in the Y-up three.js frame: three = (x, z, -y)."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from .buildings import XY, Building
from .geo import FloatArray
from .glb import Primitive


def terrain_primitive(heights: FloatArray, half_extent_m: float, material: int) -> Primitive:
    """Indexed grid mesh of the heightmap. ``heights[row, col]``, row 0 = south edge."""
    n = heights.shape[0]
    cell = 2.0 * half_extent_m / (n - 1)
    cols, rows = np.meshgrid(np.arange(n), np.arange(n))
    x = -half_extent_m + cols * cell
    y = -half_extent_m + rows * cell
    pos = np.stack([x, heights, -y], axis=-1).reshape(-1, 3).astype(np.float32)

    # Normal from central differences in the map frame, then mapped to Y-up.
    gy, gx = np.gradient(heights, cell)
    nx, ny, nz = -gx, -gy, np.ones_like(heights)
    length = np.sqrt(nx * nx + ny * ny + nz * nz)
    nrm = np.stack([nx / length, nz / length, -ny / length], axis=-1).reshape(-1, 3)

    u = (cols / (n - 1)).astype(np.float32)
    v = (1.0 - rows / (n - 1)).astype(np.float32)  # image row 0 is the north edge
    uv = np.stack([u, v], axis=-1).reshape(-1, 2)

    a = (rows[:-1, :-1] * n + cols[:-1, :-1]).ravel()  # SW
    b = a + 1  # SE
    c = a + n + 1  # NE
    d = a + n  # NW
    idx = np.stack([a, b, c, a, c, d], axis=-1).reshape(-1)
    return Primitive(pos, nrm.astype(np.float32), idx.astype(np.uint32), material, uv)


def _cross(o: XY, a: XY, b: XY) -> float:
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def _in_triangle(p: XY, a: XY, b: XY, c: XY) -> bool:
    return _cross(a, b, p) >= 0 and _cross(b, c, p) >= 0 and _cross(c, a, p) >= 0


def triangulate(ring: list[XY]) -> list[tuple[int, int, int]]:
    """Ear clipping of a simple counter-clockwise ring into index triples."""
    idx = list(range(len(ring)))
    tris: list[tuple[int, int, int]] = []
    while len(idx) > 3:
        found = False
        for k in range(len(idx)):
            i0, i1, i2 = idx[k - 1], idx[k], idx[(k + 1) % len(idx)]
            a, b, c = ring[i0], ring[i1], ring[i2]
            if _cross(a, b, c) <= 1e-9:
                continue
            if any(
                _in_triangle(ring[j], a, b, c)
                for j in idx
                if j not in (i0, i1, i2) and ring[j] not in (a, b, c)
            ):
                continue
            tris.append((i0, i1, i2))
            idx.pop(k)
            found = True
            break
        if not found:
            # Degenerate remainder (collinear run): drop the flattest vertex without a triangle.
            flat = min(
                range(len(idx)),
                key=lambda k: abs(
                    _cross(ring[idx[k - 1]], ring[idx[k]], ring[idx[(k + 1) % len(idx)]])
                ),
            )
            idx.pop(flat)
    if len(idx) == 3 and _cross(ring[idx[0]], ring[idx[1]], ring[idx[2]]) > 1e-9:
        tris.append((idx[0], idx[1], idx[2]))
    return tris


def building_primitives(
    buildings: list[Building], wall_material: int, roof_material: int
) -> tuple[Primitive, Primitive]:
    """One merged wall primitive and one merged roof primitive for all buildings."""
    w_pos: list[list[float]] = []
    w_nrm: list[list[float]] = []
    w_idx: list[int] = []
    r_pos: list[list[float]] = []
    r_idx: list[int] = []
    for b in buildings:
        ring = b.footprint
        z0 = b.base_m
        z1 = b.base_m + b.height_m
        n = len(ring)
        for i in range(n):
            (x0, y0), (x1, y1) = ring[i], ring[(i + 1) % n]
            dx, dy = x1 - x0, y1 - y0
            ln = (dx * dx + dy * dy) ** 0.5
            if ln < 1e-6:
                continue
            # Outward map normal is (dy, -dx) for a CCW ring; Y-up three = (nx, nz, -ny).
            nrm = [dy / ln, 0.0, dx / ln]
            base = len(w_pos)
            w_pos += [[x0, z0, -y0], [x1, z0, -y1], [x1, z1, -y1], [x0, z1, -y0]]
            w_nrm += [nrm] * 4
            w_idx += [base, base + 1, base + 2, base, base + 2, base + 3]
        rbase = len(r_pos)
        r_pos += [[x, z1, -y] for x, y in ring]
        for t in triangulate(ring):
            r_idx += [rbase + t[0], rbase + t[1], rbase + t[2]]
    walls = Primitive(
        _f32(w_pos, 3), _f32(w_nrm, 3), np.asarray(w_idx, dtype=np.uint32), wall_material
    )
    roof_n = np.tile(np.array([[0.0, 1.0, 0.0]], dtype=np.float32), (len(r_pos), 1))
    roofs = Primitive(_f32(r_pos, 3), roof_n, np.asarray(r_idx, dtype=np.uint32), roof_material)
    return walls, roofs


def _f32(rows: list[list[float]], width: int) -> NDArray[np.float32]:
    if not rows:
        return np.zeros((0, width), dtype=np.float32)
    return np.asarray(rows, dtype=np.float32)
