import { useTranslation } from 'react-i18next'
import type { PreviewResponse, ScenarioSpec } from './types'

type Threat = ScenarioSpec['threats'][number]

/** Disposition drawn three ways: solid for hostile, dashed for civil, dotted for clutter. */
interface Stroke {
  colour: string
  dash: string | undefined
  width: number
}
const HOSTILE: Stroke = { colour: 'var(--track-hostile)', dash: undefined, width: 2.5 }
const STROKES: Record<string, Stroke> = {
  hostile: HOSTILE,
  'civil-permitted': { colour: 'var(--track-neutral)', dash: '7 4', width: 2 },
  clutter: { colour: 'var(--text-2)', dash: '2 4', width: 2 },
}
const strokeOf = (disposition: string | undefined) => STROKES[disposition ?? 'hostile'] ?? HOSTILE

/** Seconds a threat needs to fly its route at the waypoint speeds, holds included. */
export function flightTimeS(threat: Threat): number {
  let total = 0
  for (const [i, here] of threat.route.entries()) {
    total += here.hold_s ?? 0
    const next = threat.route[i + 1]
    if (!next) break
    const d = Math.hypot(
      next.position.x - here.position.x,
      next.position.y - here.position.y,
      next.position.z - here.position.z,
    )
    const v = Math.max(0.1, (here.speed_mps + next.speed_mps) / 2)
    total += d / v
  }
  return total
}

const W = 640
const LEFT = 104
const RIGHT = 16
const ROW = 28
const TOP = 4

/** A time strip per threat from its spawn: a bar from spawn to the end of its route. */
export function TimeStrip({ spec }: { spec: ScenarioSpec }) {
  const { t } = useTranslation()
  const rows = spec.threats
  const height = TOP + rows.length * ROW + 28
  const x = (s: number) =>
    LEFT + (Math.min(s, spec.duration_s) / spec.duration_s) * (W - LEFT - RIGHT)
  const step = spec.duration_s > 600 ? 120 : 60
  const ticks: number[] = []
  for (let s = 0; s <= spec.duration_s; s += step) ticks.push(s)
  return (
    <svg
      viewBox={`0 0 ${W} ${height}`}
      role="img"
      aria-label={t('scenarios.editor.timeline.alt', {
        count: rows.length,
        duration: spec.duration_s,
      })}
      className="block h-auto w-full"
      data-testid="time-strip"
    >
      {ticks.map((s) => (
        <g key={s}>
          <line x1={x(s)} x2={x(s)} y1={TOP} y2={TOP + rows.length * ROW} stroke="var(--border)" />
          <text
            x={x(s)}
            y={TOP + rows.length * ROW + 16}
            textAnchor="middle"
            fontSize="11"
            fill="var(--text-2)"
            className="num"
          >
            {Math.floor(s / 60)}:{String(s % 60).padStart(2, '0')}
          </text>
        </g>
      ))}
      {rows.map((threat, i) => {
        const y = TOP + i * ROW
        const stroke = strokeOf(threat.disposition)
        const start = x(threat.spawn_s)
        const end = x(threat.spawn_s + flightTimeS(threat))
        const hostile = threat.disposition === 'hostile'
        return (
          <g key={threat.id} data-threat={threat.id}>
            <text
              x={LEFT - 8}
              y={y + ROW / 2 + 4}
              textAnchor="end"
              fontSize="11"
              fill="var(--text)"
              className="num"
            >
              {threat.id}
            </text>
            <line
              x1={LEFT}
              x2={W - RIGHT}
              y1={y + ROW / 2}
              y2={y + ROW / 2}
              stroke="var(--border)"
              strokeDasharray="1 3"
            />
            <rect
              x={start}
              y={y + 7}
              width={Math.max(3, end - start)}
              height={ROW - 14}
              fill={hostile ? stroke.colour : 'none'}
              fillOpacity={hostile ? 0.85 : 0}
              stroke={stroke.colour}
              strokeWidth={1.5}
              strokeDasharray={stroke.dash}
            />
            <line
              x1={start}
              x2={start}
              y1={y + 3}
              y2={y + ROW - 3}
              stroke="var(--text)"
              strokeWidth="2"
            />
          </g>
        )
      })}
    </svg>
  )
}

const MAP = 480

/** Top-down map of the zones, sensors, assets and (after a preview) the threat paths. */
export function PreviewMap({
  spec,
  preview,
}: {
  spec: ScenarioSpec | null
  preview: PreviewResponse | null
}) {
  const { t } = useTranslation()
  let extent = spec?.world.half_extent_m ?? 0
  if (extent === 0 && preview) {
    for (const threat of preview.path.threats)
      for (const [px, py] of threat.points) extent = Math.max(extent, Math.abs(px), Math.abs(py))
    extent *= 1.1
  }
  if (extent === 0) extent = 2000
  const margin = 28
  const inner = MAP - margin * 2
  const px = (v: number) => margin + ((v + extent) / (2 * extent)) * inner
  const py = (v: number) => margin + ((extent - v) / (2 * extent)) * inner
  const r = (m: number) => (m / (2 * extent)) * inner
  const step = extent > 2500 ? 1000 : 500
  const lines: number[] = []
  for (let v = -Math.floor(extent / step) * step; v <= extent; v += step) lines.push(v)
  const dispositionOf = (id: string) =>
    preview?.contacts.find((c) => c.id === id)?.disposition ??
    spec?.threats.find((x) => x.id === id)?.disposition

  return (
    <svg
      viewBox={`0 0 ${MAP} ${MAP}`}
      role="img"
      aria-label={t('scenarios.editor.preview.mapAlt', {
        zones: spec?.zones?.length ?? 0,
        sensors: spec?.sensors?.length ?? 0,
        paths: preview?.path.threats.length ?? 0,
      })}
      className="block h-auto w-full max-w-[520px]"
      data-testid="preview-map"
    >
      <rect
        x={margin}
        y={margin}
        width={inner}
        height={inner}
        fill="var(--bg)"
        stroke="var(--border)"
      />
      {lines.map((v) => (
        <g key={v}>
          <line
            x1={px(v)}
            x2={px(v)}
            y1={margin}
            y2={margin + inner}
            stroke="var(--border)"
            strokeWidth="0.5"
          />
          <line
            x1={margin}
            x2={margin + inner}
            y1={py(v)}
            y2={py(v)}
            stroke="var(--border)"
            strokeWidth="0.5"
          />
          <text
            x={px(v)}
            y={MAP - 10}
            textAnchor="middle"
            fontSize="10"
            fill="var(--text-2)"
            className="num"
          >
            {v / 1000}
          </text>
          <text
            x={margin - 5}
            y={py(v) + 3}
            textAnchor="end"
            fontSize="10"
            fill="var(--text-2)"
            className="num"
          >
            {v / 1000}
          </text>
        </g>
      ))}
      <text x={MAP - 6} y={MAP - 10} textAnchor="end" fontSize="10" fill="var(--text-2)">
        km
      </text>
      <text x={margin + 4} y={margin + 12} fontSize="11" fill="var(--text)">
        N
      </text>
      <path
        d={`M ${margin + 20} ${margin + 14} l 0 -10 l -3 4 m 3 -4 l 3 4`}
        fill="none"
        stroke="var(--text)"
      />
      {(spec?.zones ?? []).map((zone) => (
        <circle
          key={zone.id}
          cx={px(zone.center.x)}
          cy={py(zone.center.y)}
          r={r(zone.radius_m)}
          fill="none"
          stroke="var(--accent)"
          strokeWidth={zone.role === 'inner' ? 1.5 : 1}
          strokeDasharray={
            zone.role === 'inner' ? undefined : zone.role === 'outer' ? '8 4' : '2 3'
          }
        />
      ))}
      {(spec?.assets ?? []).map((asset) => (
        <rect
          key={asset.id}
          x={px(asset.position.x) - 4}
          y={py(asset.position.y) - 4}
          width={8}
          height={8}
          fill="var(--text)"
        />
      ))}
      {(spec?.sensors ?? []).map((sensor) => {
        const cx = px(sensor.position.x)
        const cy = py(sensor.position.y)
        return (
          <g key={sensor.id}>
            <path
              d={`M ${cx} ${cy - 5} L ${cx + 5} ${cy + 4} L ${cx - 5} ${cy + 4} Z`}
              fill="var(--accent)"
            />
            <text
              x={cx + 8}
              y={cy + 3}
              fontSize="10"
              fill="var(--text)"
              stroke="var(--bg)"
              strokeWidth="3"
              paintOrder="stroke"
              className="num"
            >
              {sensor.id}
            </text>
          </g>
        )
      })}
      {(preview?.path.threats ?? []).map((threat) => {
        const stroke = strokeOf(dispositionOf(threat.id))
        const pts = threat.points.map(([x, y]) => `${px(x).toFixed(1)},${py(y).toFixed(1)}`)
        const first = threat.points[0]
        const last = threat.points[threat.points.length - 1]
        const prev = threat.points[threat.points.length - 2]
        if (!first || !last) return null
        const angle = prev ? Math.atan2(-(last[1] - prev[1]), last[0] - prev[0]) : 0
        const ax = px(last[0])
        const ay = py(last[1])
        return (
          <g key={threat.id} data-path={threat.id}>
            <polyline
              points={pts.join(' ')}
              fill="none"
              stroke={stroke.colour}
              strokeWidth={stroke.width}
              strokeDasharray={stroke.dash}
            />
            <circle cx={px(first[0])} cy={py(first[1])} r={3.5} fill={stroke.colour} />
            <path
              d="M 0 -4 L 9 0 L 0 4 Z"
              fill={stroke.colour}
              transform={`translate(${ax} ${ay}) rotate(${(angle * 180) / Math.PI})`}
            />
            <text
              x={px(first[0]) + 6}
              y={py(first[1]) - 6}
              fontSize="10"
              fill="var(--text)"
              stroke="var(--bg)"
              strokeWidth="3"
              paintOrder="stroke"
              className="num"
            >
              {threat.id}
            </text>
          </g>
        )
      })}
    </svg>
  )
}

/** Legend swatches for the map: the line style repeats what the table says in words. */
export function MapLegend() {
  const { t } = useTranslation()
  const entry = (key: string, disposition: string) => {
    const s = strokeOf(disposition)
    return (
      <li key={key} className="flex items-center gap-2">
        <svg width="36" height="8" aria-hidden="true">
          <line
            x1="0"
            x2="36"
            y1="4"
            y2="4"
            stroke={s.colour}
            strokeWidth={s.width}
            strokeDasharray={s.dash}
          />
        </svg>
        {t(`scenarios.editor.preview.legend.${key}`)}
      </li>
    )
  }
  return (
    <ul className="m-0 flex list-none flex-wrap gap-x-4 gap-y-1 p-0 text-xs text-ink-2">
      {entry('hostile', 'hostile')}
      {entry('civil', 'civil-permitted')}
      {entry('clutter', 'clutter')}
      <li className="flex items-center gap-2">
        <svg width="36" height="8" aria-hidden="true">
          <line x1="0" x2="36" y1="4" y2="4" stroke="var(--accent)" strokeDasharray="8 4" />
        </svg>
        {t('scenarios.editor.preview.legend.zone')}
      </li>
      <li className="flex items-center gap-2">
        <svg width="12" height="10" aria-hidden="true">
          <path d="M 6 1 L 11 9 L 1 9 Z" fill="var(--accent)" />
        </svg>
        {t('scenarios.editor.preview.legend.sensor')}
      </li>
      <li className="flex items-center gap-2">
        <svg width="10" height="10" aria-hidden="true">
          <rect x="1" y="1" width="8" height="8" fill="var(--text)" />
        </svg>
        {t('scenarios.editor.preview.legend.asset')}
      </li>
    </ul>
  )
}
