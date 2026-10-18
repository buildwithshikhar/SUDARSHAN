# Terrain packs

A terrain pack is a baked, read-only directory under `packs/terrain/<pack-id>/`. The offline bake in `tools/terrain/` makes it from a raw SRTM tile (register G01) and an OpenStreetMap extract (G02); the raw downloads live in `data/raw/`, which git ignores. Three consumers read a pack: the sim core (line of sight), the API (serves the files) and the web scene (draws them).

Everything in a pack is generic or fictionalised. Site names are fictional, no real place name is shown in the product, and the bake picks areas with no identifiable sensitive installation. The manifest labels the content **reference data**. OSM-derived heights that were not tagged are defaults and are counted in the manifest.

## Frame

- Local metric frame, metres: **x east, y north, z up**, origin at the pack centre. The pack covers the square `[-half_extent_m, +half_extent_m]` in x and y.
- Scenario `z` is height above the pack **datum** (`datum_m`: the lowest SRTM post in the pack, rounded down to 0.1 m, in metres above mean sea level). Every terrain height is therefore ≥ 0 and a scenario's `z` is never negative. The heightmap is stored relative to the datum, so terrain height at (x, y) is the interpolated heightmap value.
- Meshes (GLB) are written Y-up for three.js with the web client's mapping: `three = (x, z, -y)`.
- The projection is local equirectangular about the pack centre. It is exact enough over a few kilometres and is not a survey.

## Files

| File | Content |
|---|---|
| `manifest.json` | Identity, frame, file list with SHA-256, counts, sources, bake parameters |
| `heights.i16` | Terrain heights, **int16 little-endian, row-major**, `size × size` values. Row 0 is the south edge (`y = -half_extent_m`), column 0 the west edge. Metres above the datum = `value × scale_m`. Vertices sit on the grid: cell `i` is at `-half + i × cell_m`. |
| `buildings.json` | Building footprints for line of sight and rendering (below) |
| `vegetation.json` | Tree positions for instanced rendering (below) |
| `terrain.glb` | Terrain mesh with an embedded landcover texture (roads, fields, scrub, water) |
| `buildings.glb` | One merged mesh of extruded buildings, walls and roofs as separate primitives |
| `ATTRIBUTION.md` | Required notices: SRTM citation, "© OpenStreetMap contributors" and the ODbL terms for the derived data |

### `manifest.json`

```json
{
  "format": "terrain-pack.v1",
  "id": "heron-ridge",
  "version": "1.0.0",
  "name": "Heron Ridge",
  "kind": "rural",
  "label": "reference data · generic area",
  "frame": { "half_extent_m": 2000, "datum_m": 612.4 },
  "heightmap": {
    "file": "heights.i16", "size": 129, "cell_m": 31.25, "scale_m": 0.1,
    "min_m": -41.3, "max_m": 96.8
  },
  "buildings": {
    "file": "buildings.json", "count": 40,
    "height_source": { "tag": 3, "levels": 9, "default": 28 }
  },
  "vegetation": { "file": "vegetation.json", "count": 1800 },
  "meshes": { "terrain": "terrain.glb", "buildings": "buildings.glb" },
  "attribution": "ATTRIBUTION.md",
  "sources": [
    { "register_id": "G01", "name": "NASA SRTM GL1 v003", "licence": "public domain (citation requested)" },
    { "register_id": "G02", "name": "OpenStreetMap", "licence": "ODbL 1.0", "notice": "© OpenStreetMap contributors" }
  ],
  "bake": { "tool": "terrain-bake", "version": "1.0.0", "config": "areas.json#heron-ridge" },
  "files": { "heights.i16": "<sha256>", "buildings.json": "<sha256>" }
}
```

`files` lists the SHA-256 of every other file in the pack. The bake is **reproducible**: the same raw files and the same `areas.json` give byte-identical output (fixed seed for the only random step, the tree scatter; stable ordering; no timestamps).

### `buildings.json`

```json
{
  "format": "terrain-buildings.v1",
  "buildings": [
    { "id": "w123456", "footprint": [[x, y], ...], "base_m": 3.2, "height_m": 7.5, "height_source": "tag|levels|default" }
  ]
}
```

- `footprint`: outer ring in metres, counter-clockwise, **not closed** (last point differs from the first), coordinates rounded to 0.1 m, at least 3 points, simple (no self-intersection; invalid rings are dropped and counted in the bake report). Buildings are clipped to the pack square by dropping any building whose centroid is outside it.
- `base_m`: lowest terrain height under the footprint (from the heightmap), relative to the datum. `height_m`: roof above `base_m`. The roof is at `base_m + height_m`.
- Sorted by `id`.

### `vegetation.json`

```json
{ "format": "terrain-vegetation.v1", "trees": [[x, y, height_m], ...] }
```

Positions on the terrain surface (z is taken from the heightmap), capped at 4000, sorted by (y, x). Derived from OSM wood, orchard and tree tags plus a seeded scatter inside wooded areas.

## Line of sight in the sim

`sim/terrain.py` loads `heights.i16` and `buildings.json`, rasterises the buildings to a 5 m obstruction grid and answers `blocked(a, b)`: whether the straight segment between two points (x, y, z in the scenario frame) passes below the terrain surface (bilinear on the heightmap) or inside a building. It uses only the operations allowed by `sim.detmath`, so the answer is identical on every platform. Radar and EO/IR use it. Acoustic does not need line of sight. RF is not occluded in this wave (stated in `docs/SENSOR_MODELS.md`).

## Serving

`GET /api/v1/terrain/{pack_id}/{file}` (signed in) returns one pack file from an allow-list (the table above). The `briefing` of the live `welcome` message carries `terrain`: `{ "kind": "flat", "elevation_m": 0 }` or `{ "kind": "pack", "id": "heron-ridge", "version": "1.0.0" }`. The scenario contract's `terrain` accepts both forms.
