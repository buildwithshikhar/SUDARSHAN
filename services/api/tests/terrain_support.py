"""Synthetic terrain packs for tests: small, exact and written the way the bake writes them."""

import hashlib
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt

HALF = 1000.0
SIZE = 41  # 50 m cells over 2 km


def ridge_heights(
    *, ridge_y: float = 0.0, ridge_m: float = 80.0, width_m: float = 100.0
) -> npt.NDArray[np.float64]:
    """A flat plain at the datum with an east-west ridge of `ridge_m` metres across y = ridge_y."""
    ys = -HALF + np.arange(SIZE) * (2 * HALF / (SIZE - 1))
    profile = np.maximum(0.0, ridge_m * (1.0 - np.abs(ys - ridge_y) / width_m))
    return np.repeat(profile[:, None], SIZE, axis=1)


def square(cx: float, cy: float, half: float) -> list[list[float]]:
    return [
        [cx - half, cy - half],
        [cx + half, cy - half],
        [cx + half, cy + half],
        [cx - half, cy + half],
    ]


def building(
    ident: str, footprint: Sequence[Sequence[float]], height_m: float, base_m: float = 0.0
) -> dict[str, Any]:
    return {
        "id": ident,
        "footprint": [list(p) for p in footprint],
        "base_m": base_m,
        "height_m": height_m,
        "height_source": "tag",
    }


def write_pack(
    root: Path,
    pack_id: str = "test-ridge",
    *,
    version: str = "1.0.0",
    heights_m: npt.NDArray[np.float64] | None = None,
    buildings: Sequence[dict[str, Any]] = (),
    half: float = HALF,
) -> Path:
    """Write `root/<pack_id>/` and return it."""
    directory = root / pack_id
    directory.mkdir(parents=True, exist_ok=True)
    grid = np.zeros((SIZE, SIZE)) if heights_m is None else heights_m
    raw = np.rint(grid / 0.1).astype("<i2")
    (directory / "heights.i16").write_bytes(raw.tobytes())
    (directory / "buildings.json").write_text(
        json.dumps({"format": "terrain-buildings.v1", "buildings": list(buildings)})
    )
    files = {
        name: hashlib.sha256((directory / name).read_bytes()).hexdigest()
        for name in ("heights.i16", "buildings.json")
    }
    manifest = {
        "format": "terrain-pack.v1",
        "id": pack_id,
        "version": version,
        "frame": {"half_extent_m": half, "datum_m": 100.0},
        "heightmap": {
            "file": "heights.i16",
            "size": SIZE,
            "cell_m": 2 * half / (SIZE - 1),
            "scale_m": 0.1,
        },
        "buildings": {"file": "buildings.json", "count": len(buildings)},
        "files": files,
    }
    (directory / "manifest.json").write_text(json.dumps(manifest))
    return directory
