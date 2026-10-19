"""Flocking terms: Reynolds boids with Vicsek noise and a consensus alignment step.

Pure functions on plain tuples. A heading is a unit vector (east, north). Only `+ - * /`, `sqrt`
and the polynomials in `sim/detmath.py` are used, so results are identical on every platform.

Model basis (docs/02-research.md section 3): separation, alignment and cohesion after Reynolds'
boids; the noise on the heading after Vicsek (discipline 1 is no noise, 0 is the largest); the
alignment step is the consensus update u_i += eps * sum_j (u_j - u_i) over linked neighbours
(Olfati-Saber, Fax and Murray). These are the models the behaviour is built on and they are not
validation of it: every weight and gain is a project-authored fictional value (register F01).
"""

import math
from collections.abc import Sequence

from .. import detmath

Vec = tuple[float, float]

#: Largest length of the separation vector, so a crowd cannot overpower the other terms.
SEPARATION_CAP = 2.0
#: Cohesion starts when the neighbours' centroid is further than this many spacings away, so a
#: member inside a crowd is not squeezed by the pull of its own edge.
COHESION_DEADBAND = 1.5


def _clip(x: float, y: float, limit: float) -> Vec:
    n = math.sqrt(x * x + y * y)
    if n > limit:
        return x / n * limit, y / n * limit
    return x, y


def separation(
    px: float,
    py: float,
    ux: float,
    uy: float,
    near: Sequence[tuple[float, float, float]],
    spacing: float,
) -> Vec:
    """Push away from every neighbour closer than `spacing`, harder the closer it is.

    `near` holds (x, y, tie) for each other member within reach; `tie` is +1 or -1 and only
    decides the side to step to when two members share a position."""
    sx = sy = 0.0
    for x, y, tie in near:
        dx, dy = px - x, py - y
        d = math.sqrt(dx * dx + dy * dy)
        if d >= spacing:
            continue
        if d == 0.0:
            sx += -uy * tie
            sy += ux * tie
            continue
        k = (spacing - d) / spacing / d
        sx += dx * k
        sy += dy * k
    return _clip(sx, sy, SEPARATION_CAP)


def alignment(ux: float, uy: float, headings: Sequence[Vec]) -> Vec:
    """The consensus step u + eps * sum(u_j - u) with eps = 1 / k: the mean of the neighbours'
    headings. With no linked neighbour the heading is unchanged."""
    k = len(headings)
    if k == 0:
        return ux, uy
    eps = 1.0 / k
    sx = sy = 0.0
    for hx, hy in headings:
        sx += hx - ux
        sy += hy - uy
    return ux + eps * sx, uy + eps * sy


def cohesion(px: float, py: float, near: Sequence[Vec], spacing: float) -> Vec:
    """Steer towards the centroid of the linked neighbours, fading in beyond 1.5 spacings and at
    full strength from 2.5 spacings."""
    k = len(near)
    if k == 0:
        return 0.0, 0.0
    cx = cy = 0.0
    for x, y in near:
        cx += x
        cy += y
    dx, dy = cx / k - px, cy / k - py
    d = math.sqrt(dx * dx + dy * dy)
    if d == 0.0:
        return 0.0, 0.0
    f = detmath.clamp((d - COHESION_DEADBAND * spacing) / spacing, 0.0, 1.0)
    return dx / d * f, dy / d * f


def goal(px: float, py: float, gx: float, gy: float, gux: float, guy: float, ramp: float) -> Vec:
    """Head for the guide point (gx, gy) when far from it, and fly the guide's heading
    (gux, guy) when within `ramp` metres of it."""
    dx, dy = gx - px, gy - py
    d = math.sqrt(dx * dx + dy * dy)
    r = detmath.clamp(d / ramp, 0.0, 1.0)
    if d == 0.0:
        return gux, guy
    return r * dx / d + (1.0 - r) * gux, r * dy / d + (1.0 - r) * guy


def noise_rotate(ux: float, uy: float, discipline: float, xi: float) -> Vec:
    """Vicsek noise: rotate the heading by (1 - discipline) * pi * xi, with xi in [-1, 1]."""
    if discipline >= 1.0:
        return ux, uy
    phi = (1.0 - discipline) * detmath.PI * xi
    c, s = detmath.cos(phi), detmath.sin(phi)
    return ux * c - uy * s, ux * s + uy * c


def blend(
    ux: float,
    uy: float,
    align: Vec,
    sep: Vec,
    coh: Vec,
    aim: Vec,
    weights: tuple[float, float, float, float],
) -> Vec:
    """The weighted heading: a unit vector from w_a * alignment + w_s * separation + w_c *
    cohesion + w_g * goal. `weights` is (separation, alignment, cohesion, goal). A sum of zero
    keeps the current heading."""
    ws, wa, wc, wg = weights
    vx = wa * align[0] + ws * sep[0] + wc * coh[0] + wg * aim[0]
    vy = wa * align[1] + ws * sep[1] + wc * coh[1] + wg * aim[1]
    if vx * vx + vy * vy < 1e-18:
        return ux, uy
    return detmath.unit(vx, vy)
