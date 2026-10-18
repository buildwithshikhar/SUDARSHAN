"""Bake one terrain pack from an SRTM tile and an OSM extract; manifest; verification."""

from __future__ import annotations

import hashlib
import json
import math
import struct
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from . import __version__
from .buildings import (
    BuildingReport,
    buildings_json,
    filter_sensitive,
    make_buildings,
    signed_area,
)
from .geo import HeightField, Projection
from .glb import GlbBuilder, Material, parse_glb
from .landcover import landcover_class, render_landcover
from .meshes import building_primitives, terrain_primitive
from .osm import OsmData, read_osm
from .srtm import SrtmTile
from .vegetation import mapped_tree_points, scatter_trees, vegetation_json

HEIGHT_SCALE_M = 0.1
PACK_VERSION = "1.0.0"
PACK_LABEL = "reference data · generic area"
FILE_ORDER = (
    "heights.i16",
    "buildings.json",
    "vegetation.json",
    "terrain.glb",
    "buildings.glb",
    "ATTRIBUTION.md",
)


@dataclass(frozen=True)
class Area:
    id: str
    name: str
    kind: str
    half_extent_m: float
    cell_m: float
    lat: float
    lon: float
    seed: int
    texture_px: int = 1024
    building_cap: int = 2500


def load_areas(path: Path) -> list[Area]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    out: list[Area] = []
    for a in doc["areas"]:
        out.append(
            Area(
                id=a["id"],
                name=a["name"],
                kind=a["kind"],
                half_extent_m=float(a["half_extent_m"]),
                cell_m=float(a["cell_m"]),
                lat=float(a["centre"]["lat"]),
                lon=float(a["centre"]["lon"]),
                seed=int(a["seed"]),
                texture_px=int(a.get("texture_px", 1024)),
                building_cap=int(a.get("building_cap", 2500)),
            )
        )
    return out


@dataclass
class BakeReport:
    heights_min_m: float = 0.0
    heights_max_m: float = 0.0
    datum_m: float = 0.0
    buildings: BuildingReport = field(default_factory=BuildingReport)
    sensitive_areas_dropped: int = 0
    trees: int = 0
    notes: list[str] = field(default_factory=list)


def _json_bytes(obj: object, indent: int | None = None) -> bytes:
    sep = (",", ": ") if indent else (",", ":")
    return (json.dumps(obj, indent=indent, separators=sep, ensure_ascii=True) + "\n").encode(
        "ascii"
    )


def attribution_text(area: Area) -> str:
    return f"""# Attribution: terrain pack "{area.name}"

This terrain pack is built from open research datasets and published specifications, in a
fictional scenario. "{area.name}" is a fictional name. The pack does not represent any real
site, installation or operational situation.

## Elevation

NASA Shuttle Radar Topography Mission, SRTM GL1 (1 arc-second) Global, version 003.
NASA JPL (2013). NASA Shuttle Radar Topography Mission Global 1 arc second [Data set].
NASA EOSDIS Land Processes DAAC. https://doi.org/10.5067/MEaSUREs/SRTM/SRTMGL1.003
The data are shared without restriction; citation is requested. The heightmap in this pack is a
bilinear resample of that tile, with voids filled by interpolation.

## Map features

Building outlines, land cover, roads and trees are derived from OpenStreetMap data.

© OpenStreetMap contributors. https://www.openstreetmap.org/copyright

OpenStreetMap data is available under the Open Database License (ODbL) 1.0,
https://opendatacommons.org/licenses/odbl/1-0/.

This pack is a Derivative Database of OpenStreetMap data and is offered under the ODbL 1.0.
Anyone who uses, redistributes or adapts the pack's data files (buildings.json, vegetation.json,
the landcover texture in terrain.glb and the building shapes in buildings.glb) must keep this
notice, credit OpenStreetMap contributors and share adaptations under the same licence.
Building heights that were not tagged in OpenStreetMap are defaults chosen by the bake tool and
are counted in manifest.json; they are not surveyed values.

## Bake

Produced by the terrain-bake tool, version {__version__}, from areas.json#{area.id}. The bake is
reproducible: the same inputs give byte-identical files, listed with SHA-256 in manifest.json.
"""


def build_files(area: Area, tile: SrtmTile, osm_path: Path) -> tuple[dict[str, bytes], BakeReport]:
    """Run the whole bake for one area and return the pack files (without the manifest)."""
    rep = BakeReport()
    proj = Projection(area.lat, area.lon)
    half = area.half_extent_m
    size = int(round(2 * half / area.cell_m)) + 1

    # Heightmap
    axis = -half + np.arange(size) * area.cell_m
    gx, gy = np.meshgrid(axis, axis)  # gy varies with row: row 0 = south
    lon_g, lat_g = proj.inverse(gx, gy)
    elev = tile.sample(lat_g, lon_g)
    # The datum is the lowest post in the pack, rounded down to 0.1 m, so every height is >= 0
    # and a scenario's z (metres above the datum) is never negative.
    datum = math.floor(float(np.min(elev)) * 10.0) / 10.0
    q = np.clip(np.rint((elev - datum) / HEIGHT_SCALE_M), -32768, 32767).astype("<i2")
    heights = q.astype(np.float64) * HEIGHT_SCALE_M
    hf = HeightField(heights, half, area.cell_m)
    rep.datum_m = datum
    rep.heights_min_m = round(float(q.min()) * HEIGHT_SCALE_M, 1)
    rep.heights_max_m = round(float(q.max()) * HEIGHT_SCALE_M, 1)

    # OSM
    osm: OsmData = read_osm(osm_path, proj.bbox(half, margin_m=150.0))
    kept_polys, dropped_polys, reasons = filter_sensitive(osm.polygons)
    rep.sensitive_areas_dropped = len(dropped_polys)
    exclusions = []
    for dp in dropped_polys:
        px_, py_ = proj.forward(
            np.array([p[0] for p in dp.ring]), np.array([p[1] for p in dp.ring])
        )
        exclusions.append([(float(a), float(b)) for a, b in zip(px_, py_, strict=True)])
    buildings, brep = make_buildings(kept_polys, proj, hf, half, exclusions)
    dropped_building_polys = sum(1 for p in dropped_polys if "building" in p.tags)
    brep.dropped_sensitive += dropped_building_polys
    brep.sensitive_reasons.update(reasons)
    if len(buildings) > area.building_cap:
        buildings.sort(key=lambda b: (-abs(signed_area(b.footprint)), b.id))
        brep.dropped_over_cap = len(buildings) - area.building_cap
        for b in buildings[area.building_cap :]:
            brep.height_source[b.height_source] -= 1
        buildings = sorted(buildings[: area.building_cap], key=lambda b: b.id)
        brep.kept = len(buildings)
    rep.buildings = brep

    # Landcover areas, roads, trees
    areas_xy: list[tuple[str, list[tuple[float, float]]]] = []
    veg_areas: list[tuple[str, str, list[tuple[float, float]]]] = []
    for poly in kept_polys:
        cls = landcover_class(poly.tags)
        if cls is None or "building" in poly.tags:
            continue
        xs, ys = proj.forward(
            np.array([p[0] for p in poly.ring]), np.array([p[1] for p in poly.ring])
        )
        ring = [(float(a), float(b)) for a, b in zip(xs, ys, strict=True)]
        areas_xy.append((cls, ring))
        if cls in ("forest", "orchard", "scrub"):
            veg_areas.append((poly.osm_id, cls, ring))
    roads_xy: list[tuple[str, list[tuple[float, float]]]] = []
    for line in osm.lines:
        xs, ys = proj.forward(
            np.array([p[0] for p in line.points]), np.array([p[1] for p in line.points])
        )
        roads_xy.append(
            (line.tags["highway"], [(float(a), float(b)) for a, b in zip(xs, ys, strict=True)])
        )
    tx, ty = proj.forward(
        np.array([p.lon for p in osm.points]), np.array([p.lat for p in osm.points])
    )
    mapped = mapped_tree_points(osm.points, (tx, ty))
    trees = scatter_trees(veg_areas, mapped, half, area.seed)
    rep.trees = len(trees)

    # Meshes
    png = render_landcover(areas_xy, roads_xy, buildings, half, area.texture_px, area.seed + 1)
    tg = GlbBuilder()
    img = tg.add_image(png)
    mat = tg.add_material(Material("landcover", texture=img, roughness=0.95))
    tg.add_mesh("terrain", [terrain_primitive(heights, half, mat)])
    bg = GlbBuilder()
    wall = bg.add_material(Material("wall", (0.64, 0.60, 0.54, 1.0), 0.92))
    roof = bg.add_material(Material("roof", (0.44, 0.38, 0.35, 1.0), 0.85))
    walls, roofs = building_primitives(buildings, wall, roof)
    bg.add_mesh("buildings", [walls, roofs])

    files = {
        "heights.i16": q.astype("<i2").tobytes(),
        "buildings.json": _json_bytes(buildings_json(buildings)),
        "vegetation.json": _json_bytes(vegetation_json(trees)),
        "terrain.glb": tg.build(),
        "buildings.glb": bg.build(),
        "ATTRIBUTION.md": attribution_text(area).encode("utf-8"),
    }
    return files, rep


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def make_manifest(
    area: Area, files: dict[str, bytes], rep: BakeReport, reproducible: bool
) -> dict[str, Any]:
    size = int(round(2 * area.half_extent_m / area.cell_m)) + 1
    src = rep.buildings.height_source
    dropped = {
        "invalid_footprint": rep.buildings.dropped_invalid,
        "outside_square": rep.buildings.dropped_outside,
        "sensitive_feature": rep.buildings.dropped_sensitive,
        "over_building_cap": rep.buildings.dropped_over_cap,
    }
    return {
        "format": "terrain-pack.v1",
        "id": area.id,
        "version": PACK_VERSION,
        "name": area.name,
        "kind": area.kind,
        "label": PACK_LABEL,
        "frame": {"half_extent_m": _num(area.half_extent_m), "datum_m": rep.datum_m},
        "heightmap": {
            "file": "heights.i16",
            "size": size,
            "cell_m": area.cell_m,
            "scale_m": HEIGHT_SCALE_M,
            "min_m": rep.heights_min_m,
            "max_m": rep.heights_max_m,
        },
        "buildings": {
            "file": "buildings.json",
            "count": rep.buildings.kept,
            "height_source": {k: int(src.get(k, 0)) for k in ("tag", "levels", "default")},
        },
        "vegetation": {"file": "vegetation.json", "count": rep.trees},
        "meshes": {"terrain": "terrain.glb", "buildings": "buildings.glb"},
        "attribution": "ATTRIBUTION.md",
        "sources": [
            {
                "register_id": "G01",
                "name": "NASA SRTM GL1 v003",
                "licence": "public domain (citation requested)",
            },
            {
                "register_id": "G02",
                "name": "OpenStreetMap",
                "licence": "ODbL 1.0",
                "notice": "© OpenStreetMap contributors",
            },
        ],
        "bake": {
            "tool": "terrain-bake",
            "version": __version__,
            "config": f"areas.json#{area.id}",
            "reproducible": reproducible,
            "dropped_buildings": dropped,
            "dropped_sensitive_areas": rep.sensitive_areas_dropped,
        },
        "files": {name: sha256(files[name]) for name in FILE_ORDER},
    }


def _num(v: float) -> float | int:
    return int(v) if float(v).is_integer() else v


def bake_area(area: Area, tile: SrtmTile, osm_path: Path) -> tuple[dict[str, bytes], BakeReport]:
    """Bake twice from scratch, compare every byte, and return files including the manifest."""
    files_a, rep = build_files(area, tile, osm_path)
    files_b, _ = build_files(area, tile, osm_path)
    reproducible = files_a == files_b
    manifest = make_manifest(area, files_a, rep, reproducible)
    out = dict(files_a)
    out["manifest.json"] = _json_bytes(manifest, indent=2)
    return out, rep


def write_pack(out_dir: Path, files: dict[str, bytes]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, data in files.items():
        (out_dir / name).write_bytes(data)


def verify_pack(pack_dir: Path) -> list[str]:
    """Re-hash every file against the manifest and run structural checks. Empty = OK."""
    errors: list[str] = []
    mpath = pack_dir / "manifest.json"
    if not mpath.is_file():
        return [f"{pack_dir}: manifest.json missing"]
    m = json.loads(mpath.read_text(encoding="utf-8"))
    if m.get("format") != "terrain-pack.v1":
        errors.append("manifest format is not terrain-pack.v1")
    listed: dict[str, str] = m.get("files", {})
    for name, digest in listed.items():
        p = pack_dir / name
        if not p.is_file():
            errors.append(f"{name}: listed in manifest but missing")
        elif sha256(p.read_bytes()) != digest:
            errors.append(f"{name}: SHA-256 does not match the manifest")
    present = {p.name for p in pack_dir.iterdir() if p.is_file() and p.name != "manifest.json"}
    for extra in sorted(present - set(listed)):
        errors.append(f"{extra}: present but not listed in the manifest")
    if errors:
        return errors
    hm = m["heightmap"]
    raw = (pack_dir / hm["file"]).read_bytes()
    if len(raw) != hm["size"] ** 2 * 2:
        errors.append("heights.i16 size does not match size x size int16")
    else:
        q = np.frombuffer(raw, dtype="<i2")
        if round(float(q.min()) * hm["scale_m"], 1) != hm["min_m"]:
            errors.append("heightmap min_m does not match the data")
        if round(float(q.max()) * hm["scale_m"], 1) != hm["max_m"]:
            errors.append("heightmap max_m does not match the data")
    b = json.loads((pack_dir / m["buildings"]["file"]).read_text(encoding="utf-8"))
    if len(b["buildings"]) != m["buildings"]["count"]:
        errors.append("buildings count does not match the manifest")
    counts: Counter[str] = Counter(x["height_source"] for x in b["buildings"])
    for k, v in m["buildings"]["height_source"].items():
        if counts.get(k, 0) != v:
            errors.append(f"height_source {k} count does not match the manifest")
    v = json.loads((pack_dir / m["vegetation"]["file"]).read_text(encoding="utf-8"))
    if len(v["trees"]) != m["vegetation"]["count"]:
        errors.append("vegetation count does not match the manifest")
    for key in ("terrain", "buildings"):
        try:
            doc, _ = parse_glb((pack_dir / m["meshes"][key]).read_bytes())
            if not doc["meshes"]:
                errors.append(f"{key} mesh file has no meshes")
        except (ValueError, struct.error) as exc:
            errors.append(f"{key} mesh is not a valid GLB: {exc}")
    return errors
