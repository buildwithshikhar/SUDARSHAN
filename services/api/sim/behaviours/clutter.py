"""Prescribed motion of airborne clutter: a kite on a tether and a drifting balloon.

Neither is a flight model. A kite rides downwind of its anchor at about 50 degrees elevation, held
on a line of fixed length, and sways across the wind; a balloon is carried by the wind and climbs
slowly. Both return the drone's air heading and airspeed so that `air velocity + wind` is exactly
the ground velocity that the displacement implies, which is what the sensors read from the truth
state (`ux * airspeed + wind`). The shapes and numbers are fictional and project-authored
(register F01, verified: false).
"""

import math
from dataclasses import dataclass

from app.contracts.scenario import TETHER_SIN_ELEVATION

from .. import detmath
from ..constants import DT

#: cos of the 50 degree elevation of a kite on its line (the sine is in the scenario contract).
TETHER_COS_ELEVATION = 0.6427876096865394
#: Below this wind speed (m/s) a kite has no downwind direction and keeps its bearing.
CALM_MPS = 0.2


@dataclass(frozen=True, slots=True)
class Moved:
    """A clutter drone's new position, air heading, airspeed and climb rate."""

    x: float
    y: float
    z: float
    ux: float
    uy: float
    airspeed: float
    vz: float


@dataclass(frozen=True, slots=True)
class Band:
    """The class limits a prescribed motion still respects."""

    max_speed: float
    max_climb: float
    max_descent: float
    min_alt: float
    max_alt: float


def _result(
    x: float,
    y: float,
    z: float,
    nx: float,
    ny: float,
    nz: float,
    wind: tuple[float, float],
    ux: float,
    uy: float,
) -> Moved:
    ax, ay = (nx - x) / DT - wind[0], (ny - y) / DT - wind[1]
    airspeed = math.sqrt(ax * ax + ay * ay)
    if airspeed > 1e-9:
        ux, uy = ax / airspeed, ay / airspeed
    return Moved(nx, ny, nz, ux, uy, airspeed, (nz - z) / DT)


def tether_step(
    x: float,
    y: float,
    z: float,
    ux: float,
    uy: float,
    t: float,
    anchor: tuple[float, float, float],
    length: float,
    sway: float,
    sway_period: float,
    wind: tuple[float, float],
    band: Band,
) -> Moved:
    """One tick of a kite. It moves towards its station (downwind of the anchor, 50 degrees up,
    swaying across the wind) no faster than the class allows, and is never further than `length`
    from the anchor."""
    ax, ay, az = anchor
    wind_speed = math.sqrt(wind[0] * wind[0] + wind[1] * wind[1])
    if wind_speed >= CALM_MPS:
        dx, dy = wind[0] / wind_speed, wind[1] / wind_speed
    else:
        dx, dy = detmath.unit(x - ax, y - ay)
    lateral = sway * detmath.sin(2.0 * detmath.PI * t / sway_period)
    reach = length * TETHER_COS_ELEVATION
    gx, gy = ax + dx * reach - dy * lateral, ay + dy * reach + dx * lateral
    gz = az + length * TETHER_SIN_ELEVATION
    # move towards the station within the class speed and climb limits
    mx, my = gx - x, gy - y
    step = math.sqrt(mx * mx + my * my)
    limit = band.max_speed * DT
    if step > limit:
        mx, my = mx / step * limit, my / step * limit
    mz = detmath.clamp(gz - z, -band.max_descent * DT, band.max_climb * DT)
    nx, ny, nz = x + mx, y + my, z + mz
    # the line holds it inside the tether radius
    rx, ry, rz = nx - ax, ny - ay, nz - az
    dist = math.sqrt(rx * rx + ry * ry + rz * rz)
    if dist > length:
        k = length / dist
        nx, ny, nz = ax + rx * k, ay + ry * k, az + rz * k
    nz = detmath.clamp(nz, band.min_alt, band.max_alt)
    return _result(x, y, z, nx, ny, nz, wind, ux, uy)


def drift_step(
    x: float,
    y: float,
    z: float,
    ux: float,
    uy: float,
    climb: float,
    wind: tuple[float, float],
    band: Band,
) -> Moved:
    """One tick of a balloon: carried by the wind (mean plus gust), climbing at `climb` m/s until
    the top of its altitude band. Its airspeed is zero."""
    nz = detmath.clamp(z + climb * DT, band.min_alt, band.max_alt)
    return Moved(x + wind[0] * DT, y + wind[1] * DT, nz, ux, uy, 0.0, (nz - z) / DT)
