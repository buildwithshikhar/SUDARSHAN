"""OSM extract reader. Yields plain dataclasses so the baker never touches osmium types."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

LonLat = tuple[float, float]
BBox = tuple[float, float, float, float]  # lon_min, lat_min, lon_max, lat_max

# Tag keys the bake looks at; everything else is dropped on read.
AREA_KEYS = (
    "building", "landuse", "natural", "leisure", "water", "waterway", "amenity",
    "military", "power", "man_made", "aeroway", "government", "office", "landcover",
)  # fmt: skip
KEEP_KEYS = (*AREA_KEYS, "height", "building:levels", "highway", "railway", "barrier", "wood")


@dataclass(frozen=True)
class Polygon:
    """An outer ring (closed: first point repeated at the end, as in OSM)."""

    osm_id: str
    tags: dict[str, str]
    ring: list[LonLat]


@dataclass(frozen=True)
class Line:
    osm_id: str
    tags: dict[str, str]
    points: list[LonLat]


@dataclass(frozen=True)
class Point:
    osm_id: str
    tags: dict[str, str]
    lon: float
    lat: float


@dataclass
class OsmData:
    polygons: list[Polygon] = field(default_factory=list)
    lines: list[Line] = field(default_factory=list)
    points: list[Point] = field(default_factory=list)


def in_bbox(lon: float, lat: float, bbox: BBox) -> bool:
    return bbox[0] <= lon <= bbox[2] and bbox[1] <= lat <= bbox[3]


def ring_touches_bbox(ring: list[LonLat], bbox: BBox) -> bool:
    """True when the ring's bounding box intersects ``bbox``."""
    lons = [p[0] for p in ring]
    lats = [p[1] for p in ring]
    return not (
        max(lons) < bbox[0] or min(lons) > bbox[2] or max(lats) < bbox[1] or min(lats) > bbox[3]
    )


def _kept_tags(tags: object) -> dict[str, str]:
    out: dict[str, str] = {}
    for k in KEEP_KEYS:
        v = tags.get(k)  # type: ignore[attr-defined]
        if v is not None:
            out[k] = str(v)
    return out


def read_osm(path: Path, bbox: BBox) -> OsmData:
    """Read buildings, landuse polygons, highways and trees that touch ``bbox``.

    Areas come from osmium's area assembler, so closed ways and multipolygon relations
    are both handled; each outer ring becomes one polygon (inner rings are ignored).
    """
    import osmium

    data = OsmData()
    fp = osmium.FileProcessor(str(path)).with_locations().with_areas()
    for item in fp:
        obj: Any = item
        if obj.is_area():
            tags = _kept_tags(obj.tags)
            if not any(k in tags for k in AREA_KEYS):
                continue
            from_way = obj.from_way()
            prefix = "w" if from_way else "r"
            base = obj.orig_id()
            for n, outer in enumerate(obj.outer_rings()):
                ring = [(float(nd.lon), float(nd.lat)) for nd in outer]
                if len(ring) < 4 or not ring_touches_bbox(ring, bbox):
                    continue
                oid = f"{prefix}{base}" if n == 0 else f"{prefix}{base}-{n}"
                data.polygons.append(Polygon(oid, tags, ring))
        elif obj.is_way():
            if "highway" not in obj.tags:
                continue
            pts = [(float(nd.lon), float(nd.lat)) for nd in obj.nodes if nd.location.valid()]
            if len(pts) >= 2 and ring_touches_bbox(pts, bbox):
                data.lines.append(Line(f"w{obj.id}", _kept_tags(obj.tags), pts))
        elif obj.is_node():
            if obj.tags.get("natural") == "tree" and in_bbox(
                obj.location.lon, obj.location.lat, bbox
            ):
                data.points.append(
                    Point(f"n{obj.id}", _kept_tags(obj.tags), obj.location.lon, obj.location.lat)
                )
    data.polygons.sort(key=lambda p: p.osm_id)
    data.lines.sort(key=lambda p: p.osm_id)
    data.points.sort(key=lambda p: p.osm_id)
    return data
