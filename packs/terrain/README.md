# terrain

Terrain packs: baked heightmaps, building meshes and landcover textures of generic or fictionalised areas. The format is specified in [docs/TERRAIN_PACKS.md](../../docs/TERRAIN_PACKS.md).

Everything in this directory is fictional / uses open-source parameters. Nothing here represents a real site, system or operational figure. The packs are built from open research datasets and published specifications, in fictional scenarios, and are labelled **reference data**.

## Packs

| Pack | Name | Kind | Extent | Heightmap | Buildings | Trees |
|---|---|---|---|---|---|---|
| `heron-ridge` | Heron Ridge | rural | 4 km x 4 km | 129 x 129, 31.25 m cells, about 141 m of relief | 41 | 704 |
| `osprey-town` | Osprey Town | urban | 3 km x 3 km | 97 x 97, 31.25 m cells, about 122 m of relief | 1125 | 45 |

Each pack directory holds `manifest.json`, `heights.i16`, `buildings.json`, `vegetation.json`, `terrain.glb`, `buildings.glb` and `ATTRIBUTION.md`. About 1.9 MB and 2.6 MB on disk.

- Elevation: NASA SRTM GL1 v003 (register G01), bilinearly resampled, voids filled by interpolation.
- Map features: OpenStreetMap (register G02), `© OpenStreetMap contributors`, ODbL 1.0. Each pack is a Derivative Database offered under the ODbL; keep `ATTRIBUTION.md` with it.
- Building heights come from the OSM `height` tag, else `building:levels` x 3 m, else a deterministic default of 5.0 to 8.5 m. The manifest counts each source; untagged heights are defaults, not surveyed values.
- Features tagged military, prison, police, power plant or substation, aeroway and similar are dropped when baking, and the manifest counts them.
- The real coordinates the areas were cut from live only in `tools/terrain/areas.json`. The pack names are fictional and no pack file carries a real place name.

## Rebuilding

The packs are produced by the offline bake in [tools/terrain](../../tools/terrain). The raw SRTM tile and OSM extract are not in git (`data/raw/` is ignored).

```sh
make terrain                       # bake all areas from data/raw
make terrain TERRAIN_RAW=/path/to/raw
cd tools/terrain && uv run python -m terrain verify ../../packs/terrain/*
```

The bake is reproducible: the same raw files and the same `areas.json` give byte-identical files, and `verify` re-hashes every file against its manifest.
