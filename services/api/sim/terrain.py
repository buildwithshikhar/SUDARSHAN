"""Terrain for the sim core: ground height and line of sight over a baked terrain pack.

A pack (docs/TERRAIN_PACKS.md) holds a heightmap and building footprints. This module loads the
two files a sensor needs and answers one question: does the straight segment between two points
pass through the ground or through a building? Radar and EO/IR use it; acoustic does not need it.

Determinism: detections reach the event log, so every number here comes from `+ - * /`, `sqrt`
and `floor` only, in a fixed order (see `sim.detmath`). Heights are int16 decimetres times a
scale, which is exact. The building raster is built by a pure-Python point-in-polygon test.
"""

import hashlib
import json
import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt

from app.contracts.paths import packs_root
from app.contracts.scenario import FlatTerrain, PackTerrain

PACK_FORMAT = "terrain-pack.v1"
BUILDINGS_FORMAT = "terrain-buildings.v1"
#: Cell size of the building obstruction raster, and the spacing of samples along a ray.
OBSTRUCTION_CELL_M = 5.0
RAY_STEP_M = 5.0
#: A raster cell with no building. Finite, so it never poisons arithmetic.
NO_BUILDING = -1.0e9

FloatArray = npt.NDArray[np.float64]


class TerrainError(ValueError):
    """A terrain pack that is missing, malformed or does not match its manifest."""


@dataclass(frozen=True, slots=True)
class Terrain:
    pack_id: str
    version: str
    #: SHA-256 over the manifest's file hashes, so a log shows exactly which terrain it ran on.
    digest: str
    half_extent_m: float
    cell_m: float
    size: int
    #: Row-major, row 0 at the south edge; metres above the pack datum.
    heights: FloatArray
    #: Building roof elevation above the datum per obstruction cell, `NO_BUILDING` where none.
    roofs: FloatArray
    roof_cells: int

    # ------------------------------------------------------------------ ground

    def ground_m(self, x: float, y: float) -> float:
        """Bilinear terrain height at (x, y); outside the pack the nearest edge value."""
        return float(
            self._ground(np.asarray([x], dtype=np.float64), np.asarray([y], np.float64))[0]
        )

    def _ground(self, x: FloatArray, y: FloatArray) -> FloatArray:
        last = float(self.size - 1)
        u = np.minimum(np.maximum((x + self.half_extent_m) / self.cell_m, 0.0), last)
        v = np.minimum(np.maximum((y + self.half_extent_m) / self.cell_m, 0.0), last)
        i = np.minimum(np.floor(u), last - 1.0)
        j = np.minimum(np.floor(v), last - 1.0)
        fu, fv = u - i, v - j
        ii, jj = i.astype(np.int64), j.astype(np.int64)
        h = self.heights
        h00, h10 = h[jj, ii], h[jj, ii + 1]
        h01, h11 = h[jj + 1, ii], h[jj + 1, ii + 1]
        south = h00 + (h10 - h00) * fu
        north = h01 + (h11 - h01) * fu
        return np.asarray(south + (north - south) * fv, dtype=np.float64)

    def roof_m(self, x: float, y: float) -> float | None:
        """Roof elevation above the datum of the building at (x, y), or `None`."""
        value = float(self._roof(np.asarray([x], np.float64), np.asarray([y], np.float64))[0])
        return None if value == NO_BUILDING else value

    def _roof(self, x: FloatArray, y: FloatArray) -> FloatArray:
        n = self.roof_cells
        cx = np.floor((x + self.half_extent_m) / OBSTRUCTION_CELL_M)
        cy = np.floor((y + self.half_extent_m) / OBSTRUCTION_CELL_M)
        inside = (cx >= 0.0) & (cx < n) & (cy >= 0.0) & (cy < n)
        ix = np.where(inside, cx, 0.0).astype(np.int64)
        iy = np.where(inside, cy, 0.0).astype(np.int64)
        return np.where(inside, self.roofs[iy, ix], NO_BUILDING)

    # ------------------------------------------------------------------ line of sight

    def blocked(self, a: tuple[float, float, float], b: tuple[float, float, float]) -> bool:
        """True if the segment a -> b passes through the ground or a building.

        Samples every `RAY_STEP_M` along the segment, excluding both end points: a sensor on a
        roof or a mast is not blocked by what it stands on, and a target is not below ground.
        """
        dx, dy, dz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
        length = math.sqrt(dx * dx + dy * dy + dz * dz)
        steps = math.ceil(length / RAY_STEP_M)
        if steps < 2:
            return False
        t = np.arange(1, steps, dtype=np.float64) / float(steps)
        x, y, z = a[0] + dx * t, a[1] + dy * t, a[2] + dz * t
        if bool(np.any(z < self._ground(x, y))):
            return True
        return bool(np.any(z < self._roof(x, y)))


# ---------------------------------------------------------------------- loading


def _inside(px: float, py: float, ring: list[list[float]]) -> bool:
    """Even-odd rule: is the point inside the polygon?"""
    inside = False
    n = len(ring)
    for k in range(n):
        x1, y1 = ring[k]
        x2, y2 = ring[(k + 1) % n]
        if (y1 > py) != (y2 > py) and px < (x2 - x1) * (py - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


def _raster(buildings: list[dict[str, Any]], half: float) -> tuple[FloatArray, int]:
    n = math.ceil(2.0 * half / OBSTRUCTION_CELL_M)
    roofs = np.full((n, n), NO_BUILDING, dtype=np.float64)
    for b in buildings:
        ring = b["footprint"]
        roof = float(b["base_m"]) + float(b["height_m"])
        xs, ys = [p[0] for p in ring], [p[1] for p in ring]
        c0 = max(0, math.floor((min(xs) + half) / OBSTRUCTION_CELL_M))
        c1 = min(n - 1, math.floor((max(xs) + half) / OBSTRUCTION_CELL_M))
        r0 = max(0, math.floor((min(ys) + half) / OBSTRUCTION_CELL_M))
        r1 = min(n - 1, math.floor((max(ys) + half) / OBSTRUCTION_CELL_M))
        for r in range(r0, r1 + 1):
            py = -half + (r + 0.5) * OBSTRUCTION_CELL_M
            for c in range(c0, c1 + 1):
                px = -half + (c + 0.5) * OBSTRUCTION_CELL_M
                if _inside(px, py, ring) and roof > roofs[r, c]:
                    roofs[r, c] = roof
    return roofs, n


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pack_dir(pack_id: str) -> Path:
    return packs_root() / "terrain" / pack_id


@lru_cache(maxsize=8)
def load_pack(directory: Path) -> Terrain:
    """Load and verify a terrain pack. Cached: a pack is immutable."""
    try:
        manifest = json.loads((directory / "manifest.json").read_text())
    except (OSError, ValueError) as error:
        raise TerrainError(f"terrain pack {directory.name}: cannot read manifest.json") from error
    if manifest.get("format") != PACK_FORMAT:
        raise TerrainError(f"terrain pack {directory.name}: not a {PACK_FORMAT} manifest")
    hm = manifest["heightmap"]
    for name in (hm["file"], manifest["buildings"]["file"]):
        expected = manifest["files"].get(name)
        if expected is None or _sha256(directory / name) != expected:
            raise TerrainError(f"terrain pack {directory.name}: {name} does not match its hash")
    size = int(hm["size"])
    raw = np.frombuffer((directory / hm["file"]).read_bytes(), dtype="<i2")
    if raw.size != size * size:
        raise TerrainError(f"terrain pack {directory.name}: heightmap is not {size}x{size}")
    heights = raw.astype(np.float64).reshape(size, size) * float(hm["scale_m"])
    half = float(manifest["frame"]["half_extent_m"])
    doc = json.loads((directory / manifest["buildings"]["file"]).read_text())
    if doc.get("format") != BUILDINGS_FORMAT:
        raise TerrainError(f"terrain pack {directory.name}: not a {BUILDINGS_FORMAT} file")
    roofs, cells = _raster(doc["buildings"], half)
    digest = hashlib.sha256(
        json.dumps(manifest["files"], sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return Terrain(
        pack_id=manifest["id"],
        version=manifest["version"],
        digest=digest,
        half_extent_m=half,
        cell_m=float(hm["cell_m"]),
        size=size,
        heights=heights,
        roofs=roofs,
        roof_cells=cells,
    )


def terrain_for(spec: FlatTerrain | PackTerrain) -> Terrain | None:
    """The terrain a scenario names, or `None` for flat ground (nothing occludes)."""
    if isinstance(spec, FlatTerrain):
        return None
    terrain = load_pack(pack_dir(spec.id))
    if (terrain.pack_id, terrain.version) != (spec.id, spec.version):
        raise TerrainError(
            f"scenario wants terrain {spec.id} {spec.version}, the pack is "
            f"{terrain.pack_id} {terrain.version}"
        )
    return terrain
