import type { HeightField } from './types'

/**
 * Terrain height in metres above the pack datum at (x, y) in the pack frame, by bilinear
 * interpolation of the heightmap (docs/TERRAIN_PACKS.md: int16, row 0 = south edge, vertices on
 * the grid at `-half + i × cell`). Points outside the square take the nearest edge value.
 */
export function heightAt(field: HeightField, x: number, y: number): number {
  const { heights, size, halfExtentM, scaleM } = field
  if (size < 2) return (heights[0] ?? 0) * scaleM
  const cell = (2 * halfExtentM) / (size - 1)
  const u = Math.min(size - 1, Math.max(0, (x + halfExtentM) / cell))
  const v = Math.min(size - 1, Math.max(0, (y + halfExtentM) / cell))
  const i0 = Math.min(size - 2, Math.floor(u))
  const j0 = Math.min(size - 2, Math.floor(v))
  const fx = u - i0
  const fy = v - j0
  const h00 = heights[j0 * size + i0] ?? 0
  const h10 = heights[j0 * size + i0 + 1] ?? 0
  const h01 = heights[(j0 + 1) * size + i0] ?? 0
  const h11 = heights[(j0 + 1) * size + i0 + 1] ?? 0
  const south = h00 + (h10 - h00) * fx
  const north = h01 + (h11 - h01) * fx
  return (south + (north - south) * fy) * scaleM
}
