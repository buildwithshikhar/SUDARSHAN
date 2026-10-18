import { useEffect, useMemo, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { useLive, useLiveSession } from '../context'
import { useLatest } from '../useLatest'
import { DEG, ppiProjectEnu, sweepBearingDeg, sweepPassed, type PpiFrame } from '../geometry'
import type { Briefing } from '../protocol'
import { simTimeNow, trackPoses, sensorPose } from '../store'
import { buildRings, drawPpi, type PpiPlot, type PpiScene } from './ppiDraw'
import { affiliationOf, prefersReducedMotion, watchTokens } from './theme'

/** One sweep per radar update interval: a plot is painted when the beam passes its bearing. */
export const RADAR_PERIOD_S = 1.2
/** Phosphor time constant in seconds. */
const DECAY_S = 1.5
const PLOT_LIFE_S = 5
const LEADER_S = 30

/** Maximum range on the scope: the outermost zone plus a quarter, in steps of 500 m. */
export function ppiRangeMax(briefing: Briefing): number {
  const outer = Math.max(1000, ...briefing.zones.map((z) => z.radius_m))
  return Math.ceil((outer * 1.25) / 500) * 500
}

interface PlotRecord {
  bearing: number
  rangeM: number
  tick: number
  litAt: number | null
}

export function PpiView({ lang }: { lang: 'en' | 'hi' }) {
  const { t } = useTranslation()
  const session = useLiveSession()
  const wrap = useRef<HTMLDivElement>(null)
  const canvas = useRef<HTMLCanvasElement>(null)
  const size = useRef({ w: 0, h: 0, dpr: 1 })
  const langRef = useLatest(lang)
  const hit = useRef<{ id: string; x: number; y: number }[]>([])

  const welcome = useLive((s) => s.welcome)
  const rangeMax = useMemo(() => (welcome ? ppiRangeMax(welcome.briefing) : 4000), [welcome])

  useEffect(() => {
    const el = canvas.current
    const box = wrap.current
    if (!el || !box) return
    const ctx = el.getContext('2d')
    if (!ctx) return
    const tokens = watchTokens()
    const reduced = prefersReducedMotion()
    const mono = '"IBM Plex Mono", ui-monospace, Menlo, Consolas, monospace'
    const plots: PlotRecord[] = []
    let lastTick = -1
    let lastSweep = 0
    let raf = 0
    let running = true

    const resize = () => {
      const rect = box.getBoundingClientRect()
      const dpr = Math.min(window.devicePixelRatio || 1, 2)
      size.current = { w: Math.max(1, rect.width), h: Math.max(1, rect.height), dpr }
      el.width = Math.round(size.current.w * dpr)
      el.height = Math.round(size.current.h * dpr)
    }
    const observer = new ResizeObserver(resize)
    observer.observe(box)
    resize()

    // Radar plots are taken as each frame arrives, not when a paint happens to run.
    const collect = () => {
      const frame = session.store.getState().frame
      if (!frame || frame.tick === lastTick) return
      lastTick = frame.tick
      for (const r of frame.reports) {
        if (r.modality !== 'radar' || r.range_m === null) continue
        plots.push({
          bearing: r.azimuth_deg,
          rangeM: r.range_m * Math.cos(r.elevation_deg * DEG),
          tick: frame.tick,
          litAt: null,
        })
      }
      // A hidden tab stops painting but not receiving: keep the backlog bounded.
      if (plots.length > 240) plots.splice(0, plots.length - 240)
    }
    const unsubscribe = session.store.subscribe(collect)
    collect()

    const draw = (nowMs: number) => {
      if (!running) return
      raf = requestAnimationFrame(draw)
      const state = session.store.getState()
      const frame = state.frame
      const briefing = state.welcome?.briefing
      const { w, h, dpr } = size.current
      if (!frame || !briefing || w < 10) return
      const radar = frame.sensors.find((s) => s.modality === 'radar')
      const origin = radar?.position ?? { x: 0, y: 0, z: 0 }
      const R = Math.max(40, Math.min(w, h) / 2 - 26)
      const geometry: PpiFrame = {
        cx: w / 2,
        cy: h / 2,
        radiusPx: R,
        rangeMaxM: ppiRangeMax(briefing),
      }

      const simNow = simTimeNow(state, nowMs)
      const sweep = sweepBearingDeg(simNow, RADAR_PERIOD_S)
      for (const p of plots) {
        if (
          p.litAt === null &&
          (sweepPassed(lastSweep, sweep, p.bearing) ||
            (frame.tick - p.tick) / 20 > RADAR_PERIOD_S * 1.05)
        )
          p.litAt = nowMs
      }
      lastSweep = sweep
      for (let i = plots.length - 1; i >= 0; i--) {
        const p = plots[i]
        if (p && p.litAt !== null && (nowMs - p.litAt) / 1000 > PLOT_LIFE_S) plots.splice(i, 1)
      }

      const lit: PpiPlot[] = []
      for (const p of plots) {
        if (p.litAt === null) continue
        const age = (nowMs - p.litAt) / 1000
        const a = p.bearing * DEG
        const r = (p.rangeM / geometry.rangeMaxM) * R
        lit.push({
          x: geometry.cx + r * Math.sin(a),
          y: geometry.cy - r * Math.cos(a),
          alpha: Math.exp(-age / DECAY_S),
        })
      }

      const poses = trackPoses(state, nowMs)
      hit.current = []
      const tracks = poses.map((pose) => {
        const p = ppiProjectEnu(origin, pose.at, geometry)
        const tip = ppiProjectEnu(
          origin,
          {
            x: pose.at.x + pose.velocity.x * LEADER_S,
            y: pose.at.y + pose.velocity.y * LEADER_S,
            z: 0,
          },
          geometry,
        )
        hit.current.push({ id: pose.id, x: p.x, y: p.y })
        return {
          id: pose.id,
          label: pose.label,
          affiliation: affiliationOf(state.assessments[pose.id]),
          status: pose.status,
          x: p.x,
          y: p.y,
          lx: tip.x,
          ly: tip.y,
          selected: state.selected === pose.id,
          trail: (state.trails[pose.id] ?? []).map((tp) =>
            ppiProjectEnu(origin, { x: tp.x, y: tp.y, z: 0 }, geometry),
          ),
        }
      })

      const sensors = frame.sensors.map((s) => {
        const p = ppiProjectEnu(origin, s.position, geometry)
        const pose = sensorPose(state, s.id, nowMs)
        let wedge = null
        if (pose && pose.fovDeg !== null && s.modality !== 'radar') {
          const edge = (bearing: number) =>
            ppiProjectEnu(
              origin,
              {
                x: s.position.x + Math.sin(bearing * DEG) * geometry.rangeMaxM,
                y: s.position.y + Math.cos(bearing * DEG) * geometry.rangeMaxM,
                z: 0,
              },
              geometry,
            )
          const a = edge(pose.bearingDeg - pose.fovDeg / 2)
          const b = edge(pose.bearingDeg + pose.fovDeg / 2)
          wedge = { x1: a.x, y1: a.y, x2: b.x, y2: b.y }
        }
        return { id: s.id, modality: s.modality, x: p.x, y: p.y, wedge }
      })

      const zones = briefing.zones.map((z) => {
        const c = ppiProjectEnu(origin, z.center, geometry)
        return {
          x: c.x,
          y: c.y,
          radiusPx: (z.radius_m / geometry.rangeMaxM) * R,
          label: `${z.label[langRef.current]} ${(z.radius_m / 1000).toFixed(1)} km`,
        }
      })

      const scene: PpiScene = {
        width: w,
        height: h,
        frame: geometry,
        tokens: tokens.get(),
        sweepDeg: sweep,
        sweepTrail: !reduced,
        plots: lit,
        tracks,
        zones,
        sensors,
        rings: buildRings(geometry),
        mono,
      }
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      drawPpi(ctx, scene)
    }
    raf = requestAnimationFrame(draw)

    const onVisibility = () => {
      if (document.hidden) {
        running = false
        cancelAnimationFrame(raf)
      } else if (!running) {
        running = true
        raf = requestAnimationFrame(draw)
      }
    }
    document.addEventListener('visibilitychange', onVisibility)
    return () => {
      running = false
      cancelAnimationFrame(raf)
      document.removeEventListener('visibilitychange', onVisibility)
      unsubscribe()
      observer.disconnect()
      tokens.dispose()
    }
  }, [session, langRef])

  const onPointer = (event: React.PointerEvent<HTMLCanvasElement>) => {
    const rect = event.currentTarget.getBoundingClientRect()
    const x = event.clientX - rect.left
    const y = event.clientY - rect.top
    let best: { id: string; d: number } | null = null
    for (const h of hit.current) {
      const d = Math.hypot(h.x - x, h.y - y)
      if (d < 18 && (!best || d < best.d)) best = { id: h.id, d }
    }
    if (best) session.store.dispatch({ type: 'select', id: best.id })
  }

  return (
    <div ref={wrap} className="relative h-full min-h-0 w-full bg-surface-1">
      <canvas
        ref={canvas}
        role="img"
        aria-label={t('live.ppi.aria', { range: (rangeMax / 1000).toFixed(1) })}
        onPointerDown={onPointer}
        className="absolute inset-0 h-full w-full"
      />
    </div>
  )
}
