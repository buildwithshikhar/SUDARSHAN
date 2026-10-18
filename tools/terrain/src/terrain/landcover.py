"""Landcover classes from OSM tags and the baked landcover texture."""

from __future__ import annotations

import io
from collections.abc import Sequence

import numpy as np
from numpy.typing import NDArray
from PIL import Image, ImageDraw

from .buildings import XY, Building

# Painting order, lowest first. Muted, desaturated colours.
LANDCOVER_ORDER = ("meadow", "farm", "orchard", "scrub", "forest", "built", "wetland", "water")
COLOURS: dict[str, tuple[int, int, int]] = {
    "base": (156, 150, 106),
    "farm": (162, 154, 108),
    "meadow": (134, 148, 98),
    "orchard": (112, 134, 84),
    "scrub": (98, 120, 78),
    "forest": (64, 94, 62),
    "built": (152, 144, 130),
    "wetland": (108, 130, 118),
    "water": (104, 128, 142),
    "building": (124, 116, 106),
}
ROAD_COLOUR = (212, 206, 188)
ROAD_CASING = (126, 120, 108)
# Road width in metres by highway class; classes not listed are not drawn.
ROAD_WIDTH_M: dict[str, float] = {
    "motorway": 9.0, "trunk": 9.0, "primary": 8.0, "secondary": 7.0, "tertiary": 6.0,
    "unclassified": 4.5, "residential": 4.5, "living_street": 4.0, "service": 3.0,
    "track": 2.5, "path": 1.5, "footway": 1.5, "pedestrian": 3.0,
    "motorway_link": 6.0, "trunk_link": 6.0, "primary_link": 5.0, "secondary_link": 5.0,
    "tertiary_link": 4.0,
}  # fmt: skip


def landcover_class(tags: dict[str, str]) -> str | None:
    """Landcover class for a polygon's tags, or None when it does not paint the ground."""
    natural = tags.get("natural")
    landuse = tags.get("landuse")
    if natural == "water" or "water" in tags or landuse in ("reservoir", "basin"):
        return "water"
    if tags.get("waterway") == "riverbank":
        return "water"
    if natural == "wetland":
        return "wetland"
    if natural == "wood" or landuse == "forest":
        return "forest"
    if natural in ("scrub", "heath"):
        return "scrub"
    if landuse in ("orchard", "vineyard", "plantation"):
        return "orchard"
    if landuse in ("farmland", "farmyard", "greenhouse_horticulture", "paddy"):
        return "farm"
    if (
        landuse in ("meadow", "grass", "village_green", "recreation_ground")
        or natural == "grassland"
    ):
        return "meadow"
    if tags.get("leisure") in ("park", "garden", "pitch", "playground", "golf_course"):
        return "meadow"
    if landuse in ("residential", "commercial", "retail", "industrial", "construction", "railway"):
        return "built"
    return None


def _noise_field(rng: np.random.Generator, size: int, coarse: int) -> NDArray[np.float32]:
    small = rng.standard_normal((coarse, coarse)).astype(np.float32)
    img = Image.fromarray(small, mode="F").resize((size, size), Image.Resampling.BICUBIC)
    return np.asarray(img, dtype=np.float32)


def render_landcover(
    areas: Sequence[tuple[str, list[XY]]],
    roads: Sequence[tuple[str, list[XY]]],
    buildings: Sequence[Building],
    half_extent_m: float,
    px: int,
    seed: int,
) -> bytes:
    """Rasterise the landcover texture (north at the top) and return PNG bytes."""
    ss = 2
    side = px * ss
    scale = side / (2.0 * half_extent_m)  # supersampled pixels per metre

    def to_px(pts: Sequence[XY]) -> list[tuple[float, float]]:
        return [((x + half_extent_m) * scale, (half_extent_m - y) * scale) for x, y in pts]

    img = Image.new("RGB", (side, side), COLOURS["base"])
    draw = ImageDraw.Draw(img)
    rank = {c: i for i, c in enumerate(LANDCOVER_ORDER)}
    for cls, ring in sorted(areas, key=lambda a: rank.get(a[0], 0)):
        if len(ring) >= 3:
            draw.polygon(to_px(ring), fill=COLOURS[cls])
    for b in buildings:
        draw.polygon(to_px(b.footprint), fill=COLOURS["building"])

    drawn = [(h, p) for h, p in roads if h in ROAD_WIDTH_M and len(p) >= 2]
    drawn.sort(key=lambda r: -ROAD_WIDTH_M[r[0]])  # minor roads on top of major at junctions
    for colour, extra_px in ((ROAD_CASING, 2), (ROAD_COLOUR, 0)):
        for hw, pts in drawn:
            w = max(2, round(ROAD_WIDTH_M[hw] * scale)) + extra_px
            draw.line(to_px(pts), fill=colour, width=w, joint="curve")
    img = img.resize((px, px), Image.Resampling.BOX)

    rng = np.random.default_rng(seed)
    arr = np.asarray(img, dtype=np.float32)
    low = _noise_field(rng, px, 24)
    grain = rng.standard_normal((px, px)).astype(np.float32)
    shade = 1.0 + 0.025 * low[..., None]
    arr = arr * shade + 1.6 * grain[..., None]
    out = Image.fromarray(np.clip(np.rint(arr), 0, 255).astype(np.uint8), mode="RGB")
    buf = io.BytesIO()
    out.save(buf, format="PNG", optimize=False, compress_level=9)
    return buf.getvalue()
