import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useLive } from '../context'
import { wrap360 } from '../geometry'
import { useEoLook } from './eoLook'
import { reticleInk, type EoMode } from './eoMode'

const FOV_STEPS = [40, 20, 10, 5, 2.5, 1.25]
const FOV_TOP = 48
const FOV_BOTTOM = 1

/** Fraction down the ladder (0 at the widest) for a field of view, on a log scale. */
export function ladderPosition(fovDeg: number): number {
  const k =
    (Math.log(FOV_TOP) - Math.log(Math.min(FOV_TOP, Math.max(FOV_BOTTOM, fovDeg)))) /
    (Math.log(FOV_TOP) - Math.log(FOV_BOTTOM))
  return Math.min(1, Math.max(0, k))
}

/** Reticle tick spacing in degrees: the 1-2-5 step that puts ticks about 80 px apart. */
export function tickStepDeg(pxPerDeg: number): number {
  const steps = [0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10]
  return steps.find((s) => s * pxPerDeg >= 70) ?? 10
}

export function timeCode(timeS: number): string {
  const m = Math.floor(timeS / 60)
  const s = timeS - m * 60
  return `T+${String(m).padStart(2, '0')}:${s.toFixed(2).padStart(5, '0')}`
}

const pad3 = (deg: number) => String(Math.round(wrap360(deg)) % 360).padStart(3, '0')

/** SVG reticle and readouts over the EO picture: instrument furniture, not a decoration. */
export function EoHud({ sensorId, mode = 'day' }: { sensorId: string; mode?: EoMode }) {
  const { t } = useTranslation()
  const frame = useLive((s) => s.frame)
  const look = useEoLook()
  const ink = reticleInk(mode)
  const homeFov = useLive((s) => s.homeFov[sensorId])
  const box = useRef<HTMLDivElement>(null)
  const [size, setSize] = useState({ w: 800, h: 450 })

  useEffect(() => {
    const el = box.current
    if (!el) return
    const observer = new ResizeObserver(() => {
      const r = el.getBoundingClientRect()
      setSize({ w: Math.max(1, r.width), h: Math.max(1, r.height) })
    })
    observer.observe(el)
    return () => observer.disconnect()
  }, [])

  const sensor = frame?.sensors.find((s) => s.id === sensorId)
  const fov = sensor?.fov_deg ?? null
  const { w, h } = size
  const cx = w / 2
  const cy = h / 2
  const pxPerDeg = fov ? w / fov : 0
  const step = fov ? tickStepDeg(pxPerDeg) : 1
  const ticks: number[] = []
  if (fov) for (let d = step; d * pxPerDeg < w / 2 - 70; d += step) ticks.push(d)
  const zoom = fov && homeFov ? homeFov / fov : null
  const health = !sensor ? 'unknown' : sensor.outage ? 'outage' : sensor.cued ? 'cued' : 'ok'
  const ladderX = w - 34
  const ladderTop = 56
  const ladderH = Math.max(80, h - 150)

  const CHAR = 6.7
  const chip = (x: number, y: number, text: string, anchor: 'start' | 'end' = 'start') => {
    const width = text.length * CHAR + 14
    return (
      <g key={`${x}-${y}`}>
        <rect
          x={anchor === 'start' ? x - 6 : x - width + 6}
          y={y - 12}
          width={width}
          height={17}
          fill="var(--bg)"
          opacity="0.82"
        />
        <text x={x} y={y} textAnchor={anchor} fill="var(--text)" className="num" fontSize="11">
          {text}
        </text>
      </g>
    )
  }
  // Marks are drawn twice, a wide dark pass under a thin light one, so they read on sky and on ground.
  const halo = (draw: (stroke: string, width: number) => React.ReactNode) => (
    <>
      <g opacity="0.7">{draw(ink.halo, 3.5)}</g>
      <g>{draw(ink.stroke, 1)}</g>
    </>
  )
  const label = {
    fill: ink.label,
    fontSize: 10,
    stroke: ink.halo,
    strokeWidth: 3,
    paintOrder: 'stroke',
  } as const
  const first = ticks[0] ?? 0
  const modeText = mode === 'day' ? t('live.eo.modeTv').toUpperCase() : t(`live.eo.modeHud.${mode}`)
  // Gain readout: thermal shows how hard the picture is stretched and that it is a model.
  const measured = look.mode === mode
  const gainText =
    mode === 'night-vision'
      ? `${t('live.eo.gain')} ${measured ? `×${look.tubeGain.toFixed(1)}` : '—'}`
      : mode === 'day'
        ? null
        : `${t('live.eo.agc')} ${measured ? `${look.gainPct}%` : '—'}  ${t('live.eo.model')}`

  return (
    <div ref={box} className="pointer-events-none absolute inset-0">
      <svg
        width={w}
        height={h}
        aria-hidden="true"
        className="absolute inset-0 text-ink"
        fontFamily="var(--font-mono)"
      >
        {halo((stroke, width) => (
          <g stroke={stroke} strokeWidth={width} fill="none">
            <path d={`M12 34 V12 H34`} />
            <path d={`M${w - 12} 34 V12 H${w - 34}`} />
            <path d={`M12 ${h - 34} V${h - 12} H34`} />
            <path d={`M${w - 12} ${h - 34} V${h - 12} H${w - 34}`} />
          </g>
        ))}
        {/* reticle: gapped cross hair with an angular scale */}
        {halo((stroke, width) => (
          <g stroke={stroke} strokeWidth={width}>
            <line x1={cx - 70} y1={cy} x2={cx - 10} y2={cy} />
            <line x1={cx + 10} y1={cy} x2={cx + 70} y2={cy} />
            <line x1={cx} y1={cy - 70} x2={cx} y2={cy - 10} />
            <line x1={cx} y1={cy + 10} x2={cx} y2={cy + 70} />
            {ticks.map((d) => (
              <g key={d}>
                <line x1={cx + d * pxPerDeg} y1={cy - 4} x2={cx + d * pxPerDeg} y2={cy + 4} />
                <line x1={cx - d * pxPerDeg} y1={cy - 4} x2={cx - d * pxPerDeg} y2={cy + 4} />
                <line x1={cx - 4} y1={cy - d * pxPerDeg} x2={cx + 4} y2={cy - d * pxPerDeg} />
                <line x1={cx - 4} y1={cy + d * pxPerDeg} x2={cx + 4} y2={cy + d * pxPerDeg} />
              </g>
            ))}
          </g>
        ))}
        {ticks.length > 0 && (
          <text x={cx + first * pxPerDeg} y={cy + 18} textAnchor="middle" {...label}>
            {`${first}°`}
          </text>
        )}
        {/* zoom ladder */}
        {fov !== null && (
          <g>
            {halo((stroke, width) => (
              <g stroke={stroke} strokeWidth={width}>
                <line x1={ladderX} y1={ladderTop} x2={ladderX} y2={ladderTop + ladderH} />
                {FOV_STEPS.map((f) => {
                  const y = ladderTop + ladderPosition(f) * ladderH
                  return <line key={f} x1={ladderX - 5} y1={y} x2={ladderX} y2={y} />
                })}
              </g>
            ))}
            {FOV_STEPS.map((f) => (
              <text
                key={f}
                x={ladderX - 9}
                y={ladderTop + ladderPosition(f) * ladderH + 3}
                textAnchor="end"
                {...label}
              >
                {`${f}°`}
              </text>
            ))}
            {(() => {
              const y = ladderTop + ladderPosition(fov) * ladderH
              return (
                <g>
                  <path
                    d={`M${ladderX + 2} ${y} l9 -5 v10 z`}
                    fill="var(--accent)"
                    stroke="var(--bg)"
                    strokeWidth="1"
                  />
                  <text x={ladderX + 6} y={y + 22} textAnchor="middle" {...label}>
                    {fov.toFixed(1)}°
                  </text>
                </g>
              )
            })()}
          </g>
        )}
        {sensor && (
          <>
            {chip(
              22,
              30,
              `${t('live.eo.brg')} ${pad3(sensor.bearing_deg)}°  ${t('live.eo.el')} ${sensor.elevation_deg >= 0 ? '+' : '-'}${Math.abs(sensor.elevation_deg).toFixed(1).padStart(4, '0')}°`,
            )}
            {chip(
              w - 22,
              30,
              `${t('live.eo.fov')} ${fov === null ? '—' : fov.toFixed(1)}°  ${t('live.eo.zoom')} ${zoom === null ? '—' : `×${zoom.toFixed(1)}`}`,
              'end',
            )}
            {chip(22, h - 24, `${frame ? timeCode(frame.time_s) : '—'}  ${modeText}`)}
            {gainText !== null && chip(22, 54, gainText)}
            {chip(
              w - 22,
              h - 24,
              `${sensorId}  ${t(`live.eo.health.${health}`)}  ${t('live.eo.range')}`,
              'end',
            )}
          </>
        )}
      </svg>
      <p className="sr-only" aria-live="off">
        {sensor
          ? t('live.eo.summary', {
              sensor: sensorId,
              bearing: pad3(sensor.bearing_deg),
              elevation: sensor.elevation_deg.toFixed(1),
              fov: fov === null ? '—' : fov.toFixed(1),
              health: t(`live.eo.health.${health}`),
            })
          : ''}
      </p>
    </div>
  )
}
