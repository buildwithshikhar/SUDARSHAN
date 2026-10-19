import { useRef, useState, type KeyboardEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { heatMapFor, tint, type HeatCell } from './heatModel'
import type { Archive } from './types'

const CELL_W = 76
const CELL_H = 44
const LEFT = 116
const TOP = 6
const BOTTOM = 34

interface Props {
  archive: Archive
  xAxis: number
  yAxis: number
}

const axisTitle = (t: (key: string, o?: Record<string, unknown>) => string, name: string) =>
  t(`scenarios.axis.${name}`, { defaultValue: name })

/**
 * The expressive-range heat map as an SVG grid: one pair of archive axes, the best quality over
 * the third. The number in each cell and the bar under it carry the value; the tint repeats it.
 * Arrow keys move between cells, and the cell under the focus is read out in a tooltip region.
 */
export function HeatMap({ archive, xAxis, yAxis }: Props) {
  const { t } = useTranslation()
  const map = heatMapFor(archive, xAxis, yAxis)
  const xa = archive.axes[xAxis]
  const ya = archive.axes[yAxis]
  const za = archive.axes.find((_, i) => i !== xAxis && i !== yAxis)
  const [active, setActive] = useState({ x: 0, y: 0 })
  const [tip, setTip] = useState<{ x: number; y: number } | null>(null)
  const refs = useRef(new Map<string, SVGGElement>())
  if (!xa || !ya) return null

  const xBins = xa.bins
  const yBins = ya.bins
  const width = LEFT + xBins * CELL_W + 4
  const height = TOP + yBins * CELL_H + BOTTOM
  const key = (x: number, y: number) => `${x}:${y}`
  const xName = axisTitle(t, xa.name)
  const yName = axisTitle(t, ya.name)
  const zName = za ? axisTitle(t, za.name) : ''

  const describe = (cell: HeatCell): string => {
    const where = `${xName} ${xa.labels[cell.x] ?? cell.x}, ${yName} ${ya.labels[cell.y] ?? cell.y}`
    return cell.quality === null
      ? t('scenarios.generator.heat.cellEmpty', { where })
      : t('scenarios.generator.heat.cell', {
          where,
          quality: cell.quality.toFixed(2),
          filled: cell.filled,
          total: za?.bins ?? 1,
          axis: zName,
          id: cell.scenarioId ?? '',
        })
  }

  const move = (event: KeyboardEvent, x: number, y: number) => {
    let nx = x
    let ny = y
    switch (event.key) {
      case 'ArrowLeft':
        nx = Math.max(0, x - 1)
        break
      case 'ArrowRight':
        nx = Math.min(xBins - 1, x + 1)
        break
      case 'ArrowUp':
        ny = Math.min(yBins - 1, y + 1)
        break
      case 'ArrowDown':
        ny = Math.max(0, y - 1)
        break
      case 'Home':
        nx = 0
        break
      case 'End':
        nx = xBins - 1
        break
      case 'PageUp':
        ny = yBins - 1
        break
      case 'PageDown':
        ny = 0
        break
      default:
        return
    }
    event.preventDefault()
    setActive({ x: nx, y: ny })
    setTip({ x: nx, y: ny })
    refs.current.get(key(nx, ny))?.focus()
  }

  const tipCell = tip ? map.cells[tip.y]?.[tip.x] : undefined

  return (
    <div>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        role="grid"
        aria-label={t('scenarios.generator.heat.label', { x: xName, y: yName, z: zName })}
        aria-describedby="heat-tip"
        className="block h-auto w-full max-w-[640px]"
        data-testid="heat-map"
      >
        {Array.from({ length: yBins }, (_, row) => {
          const y = yBins - 1 - row
          return (
            <g key={y} role="row">
              <text
                x={LEFT - 8}
                y={TOP + row * CELL_H + CELL_H / 2 + 4}
                textAnchor="end"
                fontSize="11"
                fill="var(--text-2)"
                aria-hidden="true"
              >
                {ya.labels[y] ?? y}
              </text>
              {Array.from({ length: xBins }, (_, x) => {
                const cell = map.cells[y]?.[x]
                if (!cell) return null
                const cx = LEFT + x * CELL_W
                const cy = TOP + row * CELL_H
                const isActive = active.x === x && active.y === y
                const focused = tip?.x === x && tip.y === y
                return (
                  <g
                    key={x}
                    role="gridcell"
                    ref={(node) => {
                      if (node) refs.current.set(key(x, y), node)
                      else refs.current.delete(key(x, y))
                    }}
                    tabIndex={isActive ? 0 : -1}
                    aria-label={describe(cell)}
                    data-x={x}
                    data-y={y}
                    data-quality={cell.quality ?? ''}
                    onKeyDown={(e) => move(e, x, y)}
                    onFocus={() => {
                      setActive({ x, y })
                      setTip({ x, y })
                    }}
                    onBlur={() => setTip(null)}
                    onMouseEnter={() => setTip({ x, y })}
                    onMouseLeave={() => setTip(null)}
                    style={{ outline: 'none' }}
                  >
                    <rect
                      x={cx + 1}
                      y={cy + 1}
                      width={CELL_W - 2}
                      height={CELL_H - 2}
                      fill={cell.quality === null ? 'none' : 'var(--accent)'}
                      fillOpacity={tint(cell.quality)}
                      stroke="var(--border)"
                      strokeDasharray={cell.quality === null ? '3 3' : undefined}
                    />
                    <text
                      x={cx + CELL_W / 2}
                      y={cy + CELL_H / 2 + 1}
                      textAnchor="middle"
                      fontSize="12"
                      fill={cell.quality === null ? 'var(--text-2)' : 'var(--text)'}
                      className="num"
                      aria-hidden="true"
                    >
                      {cell.quality === null ? '—' : cell.quality.toFixed(2)}
                    </text>
                    {cell.quality !== null && (
                      <rect
                        x={cx + 5}
                        y={cy + CELL_H - 10}
                        width={(CELL_W - 10) * cell.quality}
                        height={4}
                        fill="var(--accent)"
                      />
                    )}
                    {(focused || isActive) && (
                      <rect
                        x={cx + 2}
                        y={cy + 2}
                        width={CELL_W - 4}
                        height={CELL_H - 4}
                        fill="none"
                        stroke="var(--accent)"
                        strokeWidth={focused ? 2.5 : 0}
                        data-focus={focused ? 'true' : undefined}
                      />
                    )}
                  </g>
                )
              })}
            </g>
          )
        })}
        {Array.from({ length: xBins }, (_, x) => (
          <text
            key={x}
            x={LEFT + x * CELL_W + CELL_W / 2}
            y={TOP + yBins * CELL_H + 16}
            textAnchor="middle"
            fontSize="11"
            fill="var(--text-2)"
            aria-hidden="true"
          >
            {xa.labels[x] ?? x}
          </text>
        ))}
      </svg>
      <p className="m-0 mt-1 text-xs text-ink-2">
        {t('scenarios.generator.heat.axes', { x: xName, y: yName, z: zName })}
      </p>
      <div
        id="heat-tip"
        role="tooltip"
        data-testid="heat-tip"
        className="num mt-2 min-h-10 max-w-[640px] border border-line bg-surface-2 px-2 py-1 text-xs"
      >
        {tipCell ? describe(tipCell) : t('scenarios.generator.heat.prompt')}
      </div>
    </div>
  )
}

/** The numeric colour scale and the empty-cell mark. */
export function HeatLegend() {
  const { t } = useTranslation()
  const stops = [0, 0.25, 0.5, 0.75, 1]
  return (
    <ul
      className="m-0 flex list-none flex-wrap items-center gap-x-4 gap-y-1 p-0 text-xs text-ink-2"
      aria-label={t('scenarios.generator.heat.legend')}
      data-testid="heat-legend"
    >
      {stops.map((q) => (
        <li key={q} className="flex items-center gap-2">
          <svg width="28" height="16" aria-hidden="true">
            <rect
              x="0.5"
              y="0.5"
              width="27"
              height="15"
              fill="var(--accent)"
              fillOpacity={tint(q)}
              stroke="var(--border)"
            />
            <rect x="3" y="11" width={22 * q} height="3" fill="var(--accent)" />
          </svg>
          <span className="num">{q.toFixed(2)}</span>
        </li>
      ))}
      <li className="flex items-center gap-2">
        <svg width="28" height="16" aria-hidden="true">
          <rect
            x="0.5"
            y="0.5"
            width="27"
            height="15"
            fill="none"
            stroke="var(--border)"
            strokeDasharray="3 3"
          />
        </svg>
        {t('scenarios.generator.heat.empty')}
      </li>
    </ul>
  )
}
