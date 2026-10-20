import { useEffect, useId, useRef, useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { useSearchParams } from 'react-router-dom'
import { PageHeader } from '../../layout/PageHeader'
import { viridis, VIRIDIS_STOPS } from './format'
import { Panel } from '../../ui/Panel'
import { Tabs, type TabItem } from '../../ui/Tabs'

/** A module page: header with breadcrumbs, then one tab per screen of the module. */
export function ModulePage({
  group,
  module,
  tabs,
  actions,
}: {
  group: string
  module: string
  tabs: TabItem[]
  actions?: ReactNode
}) {
  const { t } = useTranslation()
  const [params, setParams] = useSearchParams()
  return (
    <>
      <PageHeader
        title={t(`nav.module.${module}`)}
        crumbs={[t(`nav.group.${group}`), t(`nav.module.${module}`)]}
        actions={actions}
      />
      <Tabs
        label={t('m.common.screens', { module: t(`nav.module.${module}`) })}
        tabs={tabs}
        value={params.get('s') ?? undefined}
        onChange={(id) => setParams({ s: id }, { replace: true })}
      />
    </>
  )
}

/** Two- or three-column responsive grid used by every module screen. */
export function Grid({
  cols = 2,
  children,
  className = '',
}: {
  cols?: 1 | 2 | 3
  children: ReactNode
  className?: string
}) {
  const map = {
    1: 'grid-cols-1',
    2: 'grid-cols-1 xl:grid-cols-2',
    3: 'grid-cols-1 lg:grid-cols-2 xl:grid-cols-3',
  }
  return <div className={`grid gap-4 ${map[cols]} ${className}`}>{children}</div>
}

/** A definition list of label and value rows. */
export function Facts({ rows }: { rows: { label: string; value: ReactNode }[] }) {
  return (
    <dl className="m-0">
      {rows.map((row) => (
        <div
          key={row.label}
          className="grid min-h-7 grid-cols-[148px_1fr] items-center gap-2 border-b border-line py-0.5 last:border-b-0"
        >
          <dt className="text-sm text-ink-2">{row.label}</dt>
          <dd className="num m-0 text-sm">{row.value}</dd>
        </div>
      ))}
    </dl>
  )
}

// -- Charts -----------------------------------------------------------------------------------

export interface Series {
  id: string
  label: string
  points: { x: number; y: number }[]
  /** Stroke dash so series differ by more than colour. */
  dash?: string
  colour?: string
}

const SERIES_COLOURS = ['var(--accent)', 'var(--signal)', 'var(--track-friend)', 'var(--text-2)']
const SERIES_DASH = [undefined, '6 3', '2 3', '10 3 2 3']

const H = 220
const PAD = { left: 44, right: 64, top: 12, bottom: 40 }

/** The drawn width of an element, so a chart is laid out in real pixels and its text stays readable. */
function useWidth(fallback: number): [React.RefObject<HTMLElement>, number] {
  const ref = useRef<HTMLElement>(null)
  const [width, setWidth] = useState(fallback)
  useEffect(() => {
    const node = ref.current
    if (!node) return undefined
    const measure = () => setWidth(Math.max(240, Math.round(node.getBoundingClientRect().width)))
    measure()
    const observer = new ResizeObserver(measure)
    observer.observe(node)
    return () => observer.disconnect()
  }, [])
  return [ref, width]
}

export function LineChart({
  series,
  xTitle,
  yTitle,
  alt,
  yMin,
  yMax,
  xFormat = (x: number) => String(x),
  yFormat = (y: number) => String(y),
  tableLabel,
}: {
  series: Series[]
  xTitle: string
  yTitle: string
  alt: string
  yMin?: number
  yMax?: number
  xFormat?: (x: number) => string
  yFormat?: (y: number) => string
  tableLabel: string
}) {
  const [holder, W] = useWidth(520)
  const all = series.flatMap((s) => s.points)
  const xs = all.map((p) => p.x)
  const ys = all.map((p) => p.y)
  const x0 = Math.min(...xs)
  const x1 = Math.max(...xs)
  const lo = yMin ?? Math.floor(Math.min(...ys) * 0.9)
  const hi = yMax ?? Math.ceil(Math.max(...ys) * 1.08)
  const sx = (x: number) =>
    PAD.left + ((x - x0) / Math.max(1e-9, x1 - x0)) * (W - PAD.left - PAD.right)
  const sy = (y: number) =>
    H - PAD.bottom - ((y - lo) / Math.max(1e-9, hi - lo)) * (H - PAD.top - PAD.bottom)
  // Direct labels sit at the end of each line, pushed apart when two lines finish close together.
  const labelYs = (() => {
    const wanted = series.map((s, i) => ({ i, y: sy(s.points[s.points.length - 1]?.y ?? 0) }))
    const order = [...wanted].sort((a, b) => a.y - b.y)
    let floor = -Infinity
    const placed: number[] = []
    for (const item of order) {
      const y = Math.max(item.y, floor + 14)
      placed[item.i] = y
      floor = y
    }
    return placed
  })()
  const yTicks = [0, 1, 2, 3, 4].map((i) => lo + ((hi - lo) * i) / 4)
  const xTicks = [...new Set(xs)].sort((a, b) => a - b)
  return (
    <figure className="m-0" ref={holder}>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        width={W}
        height={H}
        role="img"
        aria-label={alt}
        className="block max-w-full"
      >
        {yTicks.map((v) => (
          <g key={v}>
            <line
              x1={PAD.left}
              x2={W - PAD.right}
              y1={sy(v)}
              y2={sy(v)}
              stroke="var(--border)"
              strokeWidth="1"
            />
            <text
              x={PAD.left - 6}
              y={sy(v) + 4}
              textAnchor="end"
              fontSize="11"
              fill="var(--text-2)"
              className="num"
            >
              {yFormat(Math.round(v * 10) / 10)}
            </text>
          </g>
        ))}
        {xTicks.map((v) => (
          <text
            key={v}
            x={sx(v)}
            y={H - PAD.bottom + 16}
            textAnchor="middle"
            fontSize="11"
            fill="var(--text-2)"
            className="num"
          >
            {xFormat(v)}
          </text>
        ))}
        <text
          x={(PAD.left + W - PAD.right) / 2}
          y={H - 6}
          textAnchor="middle"
          fontSize="11"
          fill="var(--text-2)"
        >
          {xTitle}
        </text>
        <text
          transform={`translate(12 ${(PAD.top + H - PAD.bottom) / 2}) rotate(-90)`}
          textAnchor="middle"
          fontSize="11"
          fill="var(--text-2)"
        >
          {yTitle}
        </text>
        {series.map((s, i) => {
          const labelY = labelYs[i] ?? 0
          const colour = s.colour ?? SERIES_COLOURS[i % SERIES_COLOURS.length]
          const dash = s.dash ?? SERIES_DASH[i % SERIES_DASH.length]
          const last = s.points[s.points.length - 1]
          return (
            <g key={s.id}>
              <polyline
                fill="none"
                stroke={colour}
                strokeWidth="2"
                strokeDasharray={dash}
                points={s.points.map((p) => `${sx(p.x)},${sy(p.y)}`).join(' ')}
              />
              {s.points.map((p) => (
                <rect
                  key={p.x}
                  x={sx(p.x) - 2.5}
                  y={sy(p.y) - 2.5}
                  width="5"
                  height="5"
                  fill={colour}
                />
              ))}
              {last && (
                <text x={sx(last.x) + 8} y={labelY + 4} fontSize="11" fill="var(--text)">
                  {s.label}
                </text>
              )}
            </g>
          )
        })}
      </svg>
      <details className="mt-1 text-xs text-ink-2">
        <summary className="cursor-pointer">{tableLabel}</summary>
        <table className="num mt-1 w-full border-collapse text-left text-xs">
          <caption className="sr-only">{alt}</caption>
          <thead>
            <tr className="border-b border-line">
              <th scope="col" className="h-6 pr-2 font-medium">
                {xTitle}
              </th>
              {series.map((s) => (
                <th key={s.id} scope="col" className="h-6 pr-2 font-medium">
                  {s.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {xTicks.map((x) => (
              <tr key={x} className="border-b border-line last:border-b-0">
                <th scope="row" className="h-6 pr-2 font-normal">
                  {xFormat(x)}
                </th>
                {series.map((s) => (
                  <td key={s.id} className="pr-2">
                    {yFormat(s.points.find((p) => p.x === x)?.y ?? 0)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </figure>
  )
}

/** A horizontal bar with its value printed; the bar is never the only carrier of the number. */
export function Bar({
  label,
  value,
  max = 1,
  text,
  tone = 'accent',
}: {
  label: ReactNode
  value: number
  max?: number
  text: string
  tone?: 'accent' | 'signal' | 'hostile'
}) {
  const colour =
    tone === 'signal'
      ? 'var(--signal)'
      : tone === 'hostile'
        ? 'var(--track-hostile)'
        : 'var(--accent)'
  const id = useId()
  return (
    <div className="grid grid-cols-[minmax(0,180px)_1fr_56px] items-center gap-3 py-0.5">
      <span id={id} className="truncate text-sm">
        {label}
      </span>
      <span
        role="meter"
        aria-labelledby={id}
        aria-valuemin={0}
        aria-valuemax={max}
        aria-valuenow={value}
        aria-valuetext={text}
        className="block h-2 bg-surface-2"
      >
        <span
          className="block h-2"
          style={{ width: `${Math.min(100, (value / max) * 100)}%`, background: colour }}
        />
      </span>
      <span className="num text-right text-sm">{text}</span>
    </div>
  )
}

// -- Matrix and heat map ------------------------------------------------------------------------

/** Confusion matrix: row-normalised single-hue shading with the count printed in every cell. */
export function Matrix({
  rowLabels,
  colLabels,
  values,
  caption,
  rowTitle,
  colTitle,
}: {
  rowLabels: string[]
  colLabels: string[]
  values: number[][]
  caption: string
  rowTitle: string
  colTitle: string
}) {
  return (
    <div className="overflow-x-auto">
      <table className="num w-full border-collapse text-center text-xs">
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr>
            <th scope="col" className="h-8 text-left font-medium text-ink-2">
              {rowTitle} ↓ · {colTitle} →
            </th>
            {colLabels.map((l) => (
              <th key={l} scope="col" className="h-8 px-1 align-bottom font-medium text-ink-2">
                <span className="block max-w-[64px] break-words leading-tight">{l}</span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {values.map((row, i) => {
            const total = row.reduce((a, b) => a + b, 0)
            return (
              <tr key={rowLabels[i]}>
                <th scope="row" className="h-7 pr-2 text-left font-normal">
                  {rowLabels[i]}
                </th>
                {row.map((v, j) => {
                  const share = total === 0 ? 0 : v / total
                  const diag = i === j
                  return (
                    <td
                      key={colLabels[j]}
                      className="h-7 border border-line"
                      style={{
                        background: `color-mix(in srgb, ${diag ? 'var(--accent)' : 'var(--signal)'} ${Math.round(share * (diag ? 38 : 42))}%, transparent)`,
                        outline: diag ? '1px solid var(--accent)' : undefined,
                        outlineOffset: -1,
                      }}
                    >
                      {v === 0 ? '·' : v}
                    </td>
                  )
                })}
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

/** Miss-zone heat map: bearing sectors by range ring around the site, with a perceptual colour ramp. */
export function MissZoneMap({
  data,
  alt,
  legend,
  ringLabel,
  tableLabel,
  sectorLabel,
}: {
  data: { rate: number; contacts: number }[][]
  alt: string
  legend: string
  ringLabel: (ring: number) => string
  tableLabel: string
  sectorLabel: (sector: number) => string
}) {
  const size = 280
  const c = size / 2
  const rings = data[0]?.length ?? 0
  const rIn = (r: number) => 18 + (r * (c - 22 - 18)) / rings
  const rOut = (r: number) => 18 + ((r + 1) * (c - 22 - 18)) / rings
  const sectors = data.length
  const arc = (s: number, r: number) => {
    const a0 = ((s * 360) / sectors - 90) * (Math.PI / 180)
    const a1 = (((s + 1) * 360) / sectors - 90) * (Math.PI / 180)
    const p = (rad: number, a: number) =>
      `${(c + rad * Math.cos(a)).toFixed(1)} ${(c + rad * Math.sin(a)).toFixed(1)}`
    return `M ${p(rIn(r), a0)} L ${p(rOut(r), a0)} A ${rOut(r)} ${rOut(r)} 0 0 1 ${p(rOut(r), a1)} L ${p(rIn(r), a1)} A ${rIn(r)} ${rIn(r)} 0 0 0 ${p(rIn(r), a0)} Z`
  }
  const max = Math.max(0.0001, ...data.flat().map((d) => d.rate))
  return (
    <figure className="m-0 flex flex-col items-start gap-2">
      <div className="flex flex-wrap items-center gap-4">
        <svg
          viewBox={`0 0 ${size} ${size}`}
          role="img"
          aria-label={alt}
          className="h-[280px] w-[280px] shrink-0"
        >
          {data.map((row, s) =>
            row.map((cell, r) => (
              <path
                key={`${s}-${r}`}
                d={arc(s, r)}
                fill={viridis(cell.rate / max)}
                stroke="var(--bg)"
                strokeWidth="1"
              />
            )),
          )}
          {['N', 'E', 'S', 'W'].map((l, i) => (
            <text
              key={l}
              x={c + (c - 8) * Math.sin((i * Math.PI) / 2)}
              y={c - (c - 8) * Math.cos((i * Math.PI) / 2) + 4}
              textAnchor="middle"
              fontSize="11"
              fill="var(--text-2)"
            >
              {l}
            </text>
          ))}
        </svg>
        <div className="text-xs text-ink-2">
          <p className="m-0 mb-1">{legend}</p>
          <div aria-hidden="true" className="flex h-2 w-[160px]">
            {VIRIDIS_STOPS.map((colour) => (
              <span key={colour} className="block h-2 flex-1" style={{ background: colour }} />
            ))}
          </div>
          <div className="num flex w-[160px] justify-between">
            <span>0%</span>
            <span>{Math.round(max * 100)}%</span>
          </div>
        </div>
      </div>
      <details className="w-full text-xs text-ink-2">
        <summary className="cursor-pointer">{tableLabel}</summary>
        <div className="overflow-x-auto">
          <table className="num mt-1 w-full border-collapse text-left text-xs">
            <caption className="sr-only">{alt}</caption>
            <thead>
              <tr className="border-b border-line">
                <th scope="col" className="h-6 pr-2 font-medium" />
                {Array.from({ length: rings }, (_, r) => (
                  <th key={r} scope="col" className="h-6 pr-2 font-medium">
                    {ringLabel(r)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.map((row, s) => (
                <tr key={s} className="border-b border-line last:border-b-0">
                  <th scope="row" className="h-6 pr-2 font-normal">
                    {sectorLabel(s)}
                  </th>
                  {row.map((cell, r) => (
                    <td key={r} className="pr-2">
                      {Math.round(cell.rate * 100)}%
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </figure>
  )
}

export function ChartPanel({
  title,
  children,
  actions,
}: {
  title: string
  children: ReactNode
  actions?: ReactNode
}) {
  return (
    <Panel title={title} actions={actions}>
      {children}
    </Panel>
  )
}

/** Small status mark: shape plus text, never colour alone. */
export function Mark({ ok, label }: { ok: boolean; label: string }) {
  return (
    <span className="inline-flex items-center gap-2">
      <span
        aria-hidden="true"
        className={`inline-block h-2 w-2 ${ok ? 'bg-track-neutral' : 'rotate-45 bg-track-suspect'}`}
      />
      {label}
    </span>
  )
}
