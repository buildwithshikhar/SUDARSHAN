/**
 * Terrain packs as the browser sees them. The binding format is docs/TERRAIN_PACKS.md: a local
 * metric frame (x east, y north, z up, origin at the pack centre), heights relative to a datum,
 * meshes written Y-up for three.js with three = (x, z, -y).
 *
 * The descriptor is the generated contract's `Briefing['terrain']`; `terrainOf` is the one
 * tolerant accessor (a missing field from an older server means flat ground).
 */
import type { Briefing } from '../protocol'

export type TerrainDescriptor = Briefing['terrain']

export const FLAT_GROUND: TerrainDescriptor = { kind: 'flat', elevation_m: 0 }

/** The briefing's terrain; a missing or malformed field means flat ground, as before packs existed. */
export function terrainOf(briefing: unknown): TerrainDescriptor {
  const raw = (briefing as { terrain?: unknown } | null | undefined)?.terrain
  if (typeof raw !== 'object' || raw === null) return FLAT_GROUND
  const t = raw as Record<string, unknown>
  if (t.kind === 'pack' && typeof t.id === 'string' && t.id !== '') {
    return { kind: 'pack', id: t.id, version: typeof t.version === 'string' ? t.version : '' }
  }
  if (t.kind === 'flat') {
    return { kind: 'flat', elevation_m: typeof t.elevation_m === 'number' ? t.elevation_m : 0 }
  }
  return FLAT_GROUND
}

export interface TerrainManifest {
  format: 'terrain-pack.v1'
  id: string
  version: string
  name: string
  kind: string
  label: string
  frame: { half_extent_m: number; datum_m: number }
  heightmap: {
    file: string
    size: number
    cell_m: number
    scale_m: number
    min_m: number
    max_m: number
  }
  buildings: {
    file: string
    count: number
    /** How many building heights came from an OSM height tag, from levels, or are a default. */
    height_source?: { tag?: number; levels?: number; default?: number }
  }
  vegetation: { file: string; count: number }
  meshes?: { terrain?: string; buildings?: string }
  attribution?: string
}

/**
 * How many building heights in the pack are generic defaults (the source had no height), or null
 * when the manifest does not say.
 */
export function defaultHeightCount(manifest: TerrainManifest): number | null {
  const n = manifest.buildings.height_source?.default
  return typeof n === 'number' && Number.isInteger(n) && n >= 0 ? n : null
}

export interface TerrainBuilding {
  id: string
  /** Outer ring in metres, counter-clockwise, not closed. */
  footprint: [number, number][]
  /** Lowest terrain height under the footprint, above the datum. */
  base_m: number
  /** Roof above `base_m`. */
  height_m: number
}

/** What `heightAt` needs from a pack: a square grid of int16 heights. */
export interface HeightField {
  /** `size × size` values, row-major, row 0 at the south edge, column 0 at the west edge. */
  heights: Int16Array
  size: number
  halfExtentM: number
  /** Metres per stored unit. */
  scaleM: number
}

export interface TerrainPack extends HeightField {
  id: string
  version: string
  name: string
  /** The manifest's own wording: "reference data · generic area". */
  label: string
  manifest: TerrainManifest
  cellM: number
  datumM: number
  minM: number
  maxM: number
  buildings: TerrainBuilding[]
  /** Flat triples `x, y, height_m`, sorted by (y, x) as baked. */
  trees: Float32Array
  /** Raw GLB files; null when the pack has none or one failed to download. */
  terrainGlb: ArrayBuffer | null
  buildingsGlb: ArrayBuffer | null
}

export type TerrainState =
  | { status: 'loading' }
  /** `pack` is null for flat ground, which needs no download. */
  | { status: 'ready'; pack: TerrainPack | null; elevationM: number }
  | { status: 'error'; message: string }
