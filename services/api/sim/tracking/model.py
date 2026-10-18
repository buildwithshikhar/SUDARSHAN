"""The measurement model: what a track predicts a sensor would report, and the scalar rows.

A report is turned into up to four scalar measurements of the predicted track state: range,
azimuth, elevation and radial speed, each linearised about the prediction. Azimuth and elevation
innovations are in radians. Everything uses `sim.detmath`, so results are platform-independent.
"""

import math
from dataclasses import dataclass

from app.contracts.common import Vec3

from .. import detmath
from .config import TrackerConfig
from .measurement import Measurement

DEG = detmath.DEG
#: Below this horizontal distance (m) the azimuth of a target is undefined and not used.
MIN_HORIZONTAL_M = 1.0
MIN_RANGE_M = 1.0


@dataclass(frozen=True, slots=True)
class Row:
    kind: str
    h: list[float]
    innovation: float
    r: float


def polar_to_enu(
    origin: Vec3, azimuth_deg: float, elevation_deg: float, range_m: float
) -> list[float]:
    """Position of a point at compass azimuth, elevation and slant range from `origin`."""
    az, el = azimuth_deg * DEG, elevation_deg * DEG
    horizontal = range_m * detmath.cos(el)
    return [
        origin.x + horizontal * detmath.sin(az),
        origin.y + horizontal * detmath.cos(az),
        origin.z + range_m * detmath.sin(el),
    ]


def ray(azimuth_deg: float, elevation_deg: float) -> tuple[float, float, float]:
    """Unit vector (east, north, up) along a bearing."""
    az, el = azimuth_deg * DEG, elevation_deg * DEG
    c = detmath.cos(el)
    return detmath.sin(az) * c, detmath.cos(az) * c, detmath.sin(el)


def rows_for(m: Measurement, origin: Vec3, x: list[float], cfg: TrackerConfig) -> list[Row]:
    """Scalar measurement rows of report `m` against predicted state `x`."""
    dx, dy, dz = x[0] - origin.x, x[1] - origin.y, x[2] - origin.z
    rh = math.sqrt(dx * dx + dy * dy)
    r = max(math.sqrt(rh * rh + dz * dz), MIN_RANGE_M)
    r2 = r * r
    out: list[Row] = []
    if m.has_range:
        assert m.range_m is not None and m.sigma_range_m is not None
        sigma = max(m.sigma_range_m, cfg.min_sigma_range_m)
        out.append(
            Row("range", [dx / r, dy / r, dz / r, 0.0, 0.0, 0.0], m.range_m - r, sigma * sigma)
        )
    if rh >= MIN_HORIZONTAL_M:
        az_pred = detmath.wrap360(detmath.atan2(dx, dy) / DEG)
        sigma = max(m.sigma_azimuth_deg, cfg.min_sigma_angle_deg) * DEG
        out.append(
            Row(
                "azimuth",
                [dy / (rh * rh), -dx / (rh * rh), 0.0, 0.0, 0.0, 0.0],
                detmath.wrap180(m.azimuth_deg - az_pred) * DEG,
                sigma * sigma,
            )
        )
    el_pred = detmath.atan2(dz, rh) / DEG
    sigma = max(m.sigma_elevation_deg, cfg.min_sigma_angle_deg) * DEG
    h_el = (
        [-dz * dx / (r2 * max(rh, MIN_HORIZONTAL_M)), -dz * dy / (r2 * max(rh, MIN_HORIZONTAL_M))]
        if rh >= MIN_HORIZONTAL_M
        else [0.0, 0.0]
    )
    out.append(
        Row(
            "elevation",
            [h_el[0], h_el[1], max(rh, MIN_HORIZONTAL_M) / r2, 0.0, 0.0, 0.0],
            (m.elevation_deg - el_pred) * DEG,
            sigma * sigma,
        )
    )
    if m.radial_speed_mps is not None:
        ux, uy, uz = dx / r, dy / r, dz / r
        vr = ux * x[3] + uy * x[4] + uz * x[5]
        s = m.sigma_radial_mps if m.sigma_radial_mps is not None else cfg.default_sigma_radial_mps
        out.append(
            Row(
                "radial",
                [
                    (x[3] - vr * ux) / r,
                    (x[4] - vr * uy) / r,
                    (x[5] - vr * uz) / r,
                    ux,
                    uy,
                    uz,
                ],
                m.radial_speed_mps - vr,
                s * s,
            )
        )
    return out
