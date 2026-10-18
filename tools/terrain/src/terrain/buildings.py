"""Building footprints: sensitive-feature filter, heights, ring validity and orientation."""

from __future__ import annotations

import re
import zlib
from collections import Counter
from dataclasses import dataclass, field

import numpy as np

from .geo import HeightField, Projection
from .osm import Polygon

XY = tuple[float, float]

LEVEL_HEIGHT_M = 3.0
MAX_RING_POINTS = 200
MIN_AREA_M2 = 4.0

# (key, values) pairs that mark a feature as sensitive. Values None = any value.
_SENSITIVE_RULES: tuple[tuple[str, frozenset[str] | None], ...] = (
    ("military", None),
    ("landuse", frozenset({"military"})),
    ("building", frozenset({"military", "bunker", "barracks", "prison"})),
    ("amenity", frozenset({"prison", "police", "courthouse"})),
    ("power", frozenset({"plant", "substation", "generator", "transformer"})),
    ("man_made", frozenset({"surveillance", "antenna", "mast", "tower", "communications_tower"})),
    ("aeroway", None),
    ("government", frozenset({"military", "police", "prosecutor", "intelligence", "security"})),
    ("office", frozenset({"military"})),
)


def sensitive_reason(tags: dict[str, str]) -> str | None:
    """Return a short reason label when the tags mark a sensitive feature, else None."""
    for key, values in _SENSITIVE_RULES:
        v = tags.get(key)
        if v is None:
            continue
        if values is None or v in values:
            return f"{key}={v}"
    return None


_NUM = re.compile(r"^\s*(\d+(?:[.,]\d+)?)\s*(m|meters|metres|ft|feet|')?\s*$", re.IGNORECASE)


def parse_height_tag(value: str | None) -> float | None:
    """Metres from an OSM ``height`` value, or None when missing, unparseable or implausible."""
    if value is None:
        return None
    m = _NUM.match(value)
    if not m:
        return None
    h = float(m.group(1).replace(",", "."))
    if (m.group(2) or "").lower() in ("ft", "feet", "'"):
        h *= 0.3048
    return round(h, 1) if 1.0 <= h <= 250.0 else None


def parse_levels_tag(value: str | None) -> int | None:
    if value is None:
        return None
    m = re.match(r"^\s*(\d+)(?:\.\d+)?\s*$", value)
    if not m:
        return None
    n = int(m.group(1))
    return n if 1 <= n <= 80 else None


def default_height_m(osm_id: str) -> float:
    """Deterministic 5.0 to 8.5 m from a hash of the OSM id."""
    return round(5.0 + 0.1 * (zlib.crc32(osm_id.encode("ascii")) % 36), 1)


def building_height(tags: dict[str, str], osm_id: str) -> tuple[float, str]:
    h = parse_height_tag(tags.get("height"))
    if h is not None:
        return h, "tag"
    lv = parse_levels_tag(tags.get("building:levels"))
    if lv is not None:
        return round(lv * LEVEL_HEIGHT_M, 1), "levels"
    return default_height_m(osm_id), "default"


def signed_area(ring: list[XY]) -> float:
    s = 0.0
    n = len(ring)
    for i in range(n):
        x0, y0 = ring[i]
        x1, y1 = ring[(i + 1) % n]
        s += x0 * y1 - x1 * y0
    return s / 2.0


def centroid(ring: list[XY]) -> XY:
    a = signed_area(ring)
    n = len(ring)
    if abs(a) < 1e-9:
        return (sum(p[0] for p in ring) / n, sum(p[1] for p in ring) / n)
    cx = cy = 0.0
    for i in range(n):
        x0, y0 = ring[i]
        x1, y1 = ring[(i + 1) % n]
        f = x0 * y1 - x1 * y0
        cx += (x0 + x1) * f
        cy += (y0 + y1) * f
    return (cx / (6 * a), cy / (6 * a))


def _cross(o: XY, a: XY, b: XY) -> float:
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def _segments_intersect(p1: XY, p2: XY, p3: XY, p4: XY) -> bool:
    """Proper or touching intersection of segments p1p2 and p3p4."""
    d1 = _cross(p3, p4, p1)
    d2 = _cross(p3, p4, p2)
    d3 = _cross(p1, p2, p3)
    d4 = _cross(p1, p2, p4)
    if ((d1 > 0 > d2) or (d1 < 0 < d2)) and ((d3 > 0 > d4) or (d3 < 0 < d4)):
        return True

    def on_seg(a: XY, b: XY, c: XY) -> bool:
        return min(a[0], b[0]) <= c[0] <= max(a[0], b[0]) and min(a[1], b[1]) <= c[1] <= max(
            a[1], b[1]
        )

    return (
        (d1 == 0 and on_seg(p3, p4, p1))
        or (d2 == 0 and on_seg(p3, p4, p2))
        or (d3 == 0 and on_seg(p1, p2, p3))
        or (d4 == 0 and on_seg(p1, p2, p4))
    )


def is_simple(ring: list[XY]) -> bool:
    """True when no two non-adjacent edges of the (open) ring touch or cross."""
    n = len(ring)
    for i in range(n):
        a, b = ring[i], ring[(i + 1) % n]
        for j in range(i + 1, n):
            if j == i or (j + 1) % n == i or (i + 1) % n == j:
                continue
            c, d = ring[j], ring[(j + 1) % n]
            if _segments_intersect(a, b, c, d):
                return False
    return True


def clean_ring(points: list[XY]) -> list[XY] | None:
    """Round to 0.1 m, drop the closing point and consecutive duplicates. None if degenerate."""
    pts = [(round(x, 1), round(y, 1)) for x, y in points]
    out: list[XY] = []
    for p in pts:
        if not out or p != out[-1]:
            out.append(p)
    if len(out) > 1 and out[0] == out[-1]:
        out.pop()
    return out if len(out) >= 3 else None


@dataclass
class Building:
    id: str
    footprint: list[XY]
    base_m: float
    height_m: float
    height_source: str


@dataclass
class BuildingReport:
    kept: int = 0
    dropped_invalid: int = 0
    dropped_outside: int = 0
    dropped_sensitive: int = 0
    sensitive_reasons: Counter[str] = field(default_factory=Counter)
    height_source: Counter[str] = field(default_factory=Counter)
    dropped_over_cap: int = 0


def filter_sensitive(polygons: list[Polygon]) -> tuple[list[Polygon], list[Polygon], Counter[str]]:
    """Split polygons into (kept, dropped) by the sensitive-feature rules; count reasons."""
    kept: list[Polygon] = []
    dropped: list[Polygon] = []
    reasons: Counter[str] = Counter()
    for poly in polygons:
        reason = sensitive_reason(poly.tags)
        if reason:
            dropped.append(poly)
            reasons[reason] += 1
        else:
            kept.append(poly)
    return kept, dropped, reasons


def point_in_ring(x: float, y: float, ring: list[XY]) -> bool:
    """Even-odd point-in-polygon test."""
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def make_buildings(
    polygons: list[Polygon],
    proj: Projection,
    hf: HeightField,
    half_extent_m: float,
    exclusion_rings: list[list[XY]] | None = None,
) -> tuple[list[Building], BuildingReport]:
    """Turn OSM building polygons into validated, CCW, terrain-based buildings.

    ``exclusion_rings`` are projected rings of dropped sensitive areas; a building whose
    centroid falls inside one is dropped and counted as sensitive.
    """
    rep = BuildingReport()
    out: list[Building] = []
    seen: set[str] = set()
    exclusions = exclusion_rings or []
    for poly in polygons:
        if "building" not in poly.tags or poly.tags["building"] == "no":
            continue
        if poly.osm_id in seen:
            continue
        seen.add(poly.osm_id)
        lon = np.array([p[0] for p in poly.ring])
        lat = np.array([p[1] for p in poly.ring])
        xs, ys = proj.forward(lon, lat)
        ring = clean_ring([(float(x), float(y)) for x, y in zip(xs, ys, strict=True)])
        if (
            ring is None
            or len(ring) > MAX_RING_POINTS
            or abs(signed_area(ring)) < MIN_AREA_M2
            or not is_simple(ring)
        ):
            rep.dropped_invalid += 1
            continue
        if any(abs(x) > half_extent_m or abs(y) > half_extent_m for x, y in ring):
            rep.dropped_outside += 1
            continue
        if signed_area(ring) < 0:
            ring.reverse()
        cx, cy = centroid(ring)
        if any(point_in_ring(cx, cy, ex) for ex in exclusions):
            rep.dropped_sensitive += 1
            rep.sensitive_reasons["inside sensitive area"] += 1
            continue
        px = np.array([p[0] for p in ring] + [cx])
        py = np.array([p[1] for p in ring] + [cy])
        base = round(float(np.min(hf.sample(px, py))), 1)
        height, src = building_height(poly.tags, poly.osm_id)
        out.append(Building(poly.osm_id, ring, base, height, src))
        rep.height_source[src] += 1
    out.sort(key=lambda b: b.id)
    rep.kept = len(out)
    return out, rep


def buildings_json(buildings: list[Building]) -> dict[str, object]:
    return {
        "format": "terrain-buildings.v1",
        "buildings": [
            {
                "id": b.id,
                "footprint": [[x, y] for x, y in b.footprint],
                "base_m": b.base_m,
                "height_m": b.height_m,
                "height_source": b.height_source,
            }
            for b in buildings
        ],
    }
