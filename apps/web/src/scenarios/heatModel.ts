import type { Archive, ArchiveCell } from './types'

/** One cell of an expressive-range heat map: best quality over the axis not shown. */
export interface HeatCell {
  x: number
  y: number
  /** Null when no scenario fell in the cell. */
  quality: number | null
  /** How many archive cells (over the hidden axis) hold a scenario. */
  filled: number
  scenarioId: string | null
}

export interface HeatMapData {
  xAxis: number
  yAxis: number
  /** Rows are the y bins, columns the x bins. */
  cells: HeatCell[][]
  max: number
}

/**
 * The heat map for a pair of the three archive axes, taken from the archive cells: for each pair
 * of bins the best quality over the third axis (docs/SCENARIO_ENGINE.md, "MAP-Elites archive").
 */
export function heatMapFor(archive: Archive, xAxis: number, yAxis: number): HeatMapData {
  const xBins = archive.axes[xAxis]?.bins ?? 0
  const yBins = archive.axes[yAxis]?.bins ?? 0
  const cells: HeatCell[][] = Array.from({ length: yBins }, (_, y) =>
    Array.from({ length: xBins }, (_, x) => ({
      x,
      y,
      quality: null,
      filled: 0,
      scenarioId: null,
    })),
  )
  let max = 0
  for (const cell of archive.cells as ArchiveCell[]) {
    const yi = cell.index[yAxis]
    const xi = cell.index[xAxis]
    if (yi === undefined || xi === undefined) continue
    const target = cells[yi]?.[xi]
    if (!target) continue
    target.filled += 1
    if (target.quality === null || cell.quality > target.quality) {
      target.quality = cell.quality
      target.scenarioId = cell.scenario_id
    }
    max = Math.max(max, cell.quality)
  }
  return { xAxis, yAxis, cells, max }
}

/** Fill opacity of a cell: a tint only, so the number printed in the cell keeps its contrast. */
export const tint = (quality: number | null): number =>
  quality === null ? 0 : 0.08 + 0.3 * Math.min(1, Math.max(0, quality))
