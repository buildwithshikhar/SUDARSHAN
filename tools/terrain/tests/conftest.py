"""Shared synthetic fixtures: a small SRTM-like tile and an OSM-like input. No raw data needed."""

from __future__ import annotations

import numpy as np
import pytest

from terrain.geo import Projection
from terrain.osm import Line, OsmData, Point, Polygon
from terrain.pack import Area
from terrain.srtm import SrtmTile

LAT0 = 17.5
LON0 = 74.5


def make_tile(n: int = 101) -> SrtmTile:
    """A 1x1 degree tile (N17E074) with a tilted plane plus a smooth bump."""
    r, c = np.mgrid[0:n, 0:n]
    lat = 18.0 - r / (n - 1)
    lon = 74.0 + c / (n - 1)
    elev = 500.0 + 300.0 * (lon - 74.0) + 100.0 * (lat - 17.0)
    elev += 40.0 * np.exp(-(((lat - LAT0) / 0.02) ** 2 + ((lon - LON0 - 0.01) / 0.02) ** 2))
    return SrtmTile(17, 74, np.rint(elev).astype(np.int16))


def rect_ll(x: float, y: float, w: float, h: float) -> list[tuple[float, float]]:
    """A closed w x h metre rectangle with SW corner at metre offset (x, y), as lon/lat."""
    p = Projection(LAT0, LON0)
    pts = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
    out: list[tuple[float, float]] = []
    for px, py in [*pts, pts[0]]:
        lo, la = p.inverse(px, py)
        out.append((float(lo), float(la)))
    return out


@pytest.fixture
def tile() -> SrtmTile:
    return make_tile()


@pytest.fixture
def area() -> Area:
    return Area(
        id="test-area",
        name="Test Area",
        kind="rural",
        half_extent_m=500.0,
        cell_m=31.25,
        lat=LAT0,
        lon=LON0,
        seed=7,
        texture_px=64,
    )


@pytest.fixture
def osm_data() -> OsmData:
    road = [rect_ll(-500, 0, 1, 1)[0], rect_ll(499, 0, 1, 1)[0]]
    return OsmData(
        polygons=[
            Polygon("w1", {"building": "yes", "height": "12 m"}, rect_ll(0, 0, 20, 10)),
            Polygon("w2", {"building": "house", "building:levels": "2"}, rect_ll(50, 50, 12, 12)),
            Polygon("w3", {"building": "yes"}, rect_ll(-100, 120, 15, 8)),
            Polygon("w4", {"building": "military"}, rect_ll(200, -200, 10, 10)),
            Polygon("w5", {"building": "yes"}, rect_ll(-450, 330, 20, 20)),  # inside w902
            Polygon("w6", {"building": "yes"}, rect_ll(480, 0, 40, 10)),  # crosses the edge
            Polygon("w900", {"natural": "wood"}, rect_ll(-400, -400, 300, 300)),
            Polygon("w901", {"natural": "water"}, rect_ll(100, 100, 200, 100)),
            Polygon("w902", {"landuse": "military"}, rect_ll(-480, 300, 150, 150)),
        ],
        lines=[Line("w50", {"highway": "primary"}, road)],
        points=[Point("n1", {"natural": "tree", "height": "9"}, LON0, LAT0 + 0.0005)],
    )
