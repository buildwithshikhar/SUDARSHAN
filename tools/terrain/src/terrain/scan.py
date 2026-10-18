"""Candidate-centre scan: building count, relief and sensitive-feature count per square."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from .buildings import sensitive_reason
from .geo import Projection
from .osm import read_osm
from .srtm import SrtmTile


@dataclass(frozen=True)
class Candidate:
    lat: float
    lon: float
    buildings: int
    relief_m: float
    sensitive: int
    wooded: int


def _count(a: NDArray[np.float64], b: tuple[float, float, float, float]) -> int:
    if a.size == 0:
        return 0
    inside = (a[:, 0] >= b[0]) & (a[:, 0] <= b[2]) & (a[:, 1] >= b[1]) & (a[:, 1] <= b[3])
    return int(inside.sum())


def scan_candidates(
    tile: SrtmTile,
    osm_path: Path,
    half_extent_m: float,
    step_m: float = 500.0,
    around: tuple[float, float] | None = None,
    max_dist_km: float = 15.0,
) -> list[Candidate]:
    """Score squares of the given size on a regular grid inside the tile."""
    bbox = (tile.lon_sw, tile.lat_sw, tile.lon_sw + 1.0, tile.lat_sw + 1.0)
    data = read_osm(osm_path, bbox)
    b_pts: list[tuple[float, float]] = []
    s_pts: list[tuple[float, float]] = []
    w_pts: list[tuple[float, float]] = []
    for p in data.polygons:
        lon = sum(q[0] for q in p.ring) / len(p.ring)
        lat = sum(q[1] for q in p.ring) / len(p.ring)
        if sensitive_reason(p.tags):
            s_pts.append((lon, lat))
        elif "building" in p.tags:
            b_pts.append((lon, lat))
        elif p.tags.get("natural") in ("wood", "scrub") or p.tags.get("landuse") == "forest":
            w_pts.append((lon, lat))
    barr, sarr, warr = (np.array(a).reshape(-1, 2) for a in (b_pts, s_pts, w_pts))

    out: list[Candidate] = []
    lat_c = tile.lat_sw + 0.5
    proj0 = Projection(lat_c, tile.lon_sw + 0.5)
    dlat = step_m / proj0.m_per_deg_lat
    dlon = step_m / proj0.m_per_deg_lon
    margin_lat = (half_extent_m + 60) / proj0.m_per_deg_lat
    margin_lon = (half_extent_m + 60) / proj0.m_per_deg_lon
    lats = np.arange(tile.lat_sw + margin_lat, tile.lat_sw + 1 - margin_lat, dlat)
    lons = np.arange(tile.lon_sw + margin_lon, tile.lon_sw + 1 - margin_lon, dlon)
    for lat in lats:
        for lon in lons:
            proj = Projection(float(lat), float(lon))
            if around is not None:
                ax, ay = proj.forward(around[1], around[0])
                if float(np.hypot(ax, ay)) > max_dist_km * 1000.0:
                    continue
            box = proj.bbox(half_extent_m)
            lo_lon, lo_lat, hi_lon, hi_lat = box

            gl = np.linspace(lo_lat, hi_lat, 17)
            gn = np.linspace(lo_lon, hi_lon, 17)
            glon, glat = np.meshgrid(gn, gl)
            elev = tile.sample(glat, glon)
            out.append(
                Candidate(
                    float(lat),
                    float(lon),
                    _count(barr, box),
                    float(np.max(elev) - np.min(elev)),
                    _count(sarr, box),
                    _count(warr, box),
                )
            )
    return out
