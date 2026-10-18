import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { InlineAlert } from '../../ui/InlineAlert'
import { EmptyState } from '../../ui/States'
import { useLive, useLiveSession } from '../context'
import { qualityStore, useQuality } from '../qualityStore'
import { sensorPose } from '../store'
import { useTerrain } from '../terrain/loader'
import { terrainOf, type TerrainState } from '../terrain/types'
import { EoHud } from './EoHud'
import { ReportHold } from './eoHold'
import { publishLook, resetLook } from './eoLook'
import type { EoMode } from './eoMode'
import { EoScene } from './eoScene'
import { webglAvailable } from './webgl'

/**
 * The EO sensor's picture: a three.js scene drawn from the sensor's pointing, its field of view
 * and its EO/IR reports only. The terrain pack named in the briefing loads in the background; if
 * it cannot, the view keeps the flat ground and says so. If WebGL is missing the view says so
 * instead of failing silently.
 */
export function EoView({ sensorId, mode = 'day' }: { sensorId: string | null; mode?: EoMode }) {
  const { t } = useTranslation()
  const session = useLiveSession()
  const welcome = useLive((s) => s.welcome)
  const box = useRef<HTMLDivElement>(null)
  const [unavailable, setUnavailable] = useState(() => !webglAvailable())
  const quality = useQuality()
  const terrain = useTerrain(terrainOf(welcome?.briefing))

  // The scene lives in an effect keyed on the session; the latest mode, tier and terrain are
  // read from refs so a change of any of them does not rebuild it.
  const sceneRef = useRef<EoScene | null>(null)
  const latest = useRef({ mode, tier: quality.tier, terrain })
  useEffect(() => {
    latest.current = { mode, tier: quality.tier, terrain }
  })

  useEffect(() => {
    const wrap = box.current
    if (!wrap || !sensorId || !welcome || unavailable) return
    // A fresh canvas per scene: a lost context cannot be reused (React's strict mode remounts).
    const el = document.createElement('canvas')
    el.setAttribute('aria-hidden', 'true')
    el.className = 'absolute inset-0 h-full w-full'
    wrap.prepend(el)
    let scene: EoScene
    try {
      scene = new EoScene(el, { tier: latest.current.tier, onLook: publishLook })
    } catch {
      el.remove()
      queueMicrotask(() => setUnavailable(true))
      return
    }
    sceneRef.current = scene
    scene.setWeather(welcome.briefing.weather)
    scene.setSite(welcome.briefing)
    scene.setMode(latest.current.mode)
    const ground = latest.current.terrain
    if (ground.status === 'ready') void scene.setTerrain(ground.pack)
    const hold = new ReportHold()
    let lastTick = -1
    let raf = 0
    let running = true

    const observer = new ResizeObserver(() => {
      const r = wrap.getBoundingClientRect()
      scene.resize(r.width, r.height)
    })
    observer.observe(wrap)
    const r = wrap.getBoundingClientRect()
    scene.resize(r.width, r.height)

    // Reports are taken as each frame arrives, not when a paint happens to run, so none is skipped.
    const ingest = () => {
      const frame = session.store.getState().frame
      if (!frame || frame.tick === lastTick) return
      lastTick = frame.tick
      const fovBySensor: Record<string, number | null> = {}
      const pixelsBySensor: Record<string, number | null | undefined> = {}
      for (const s of frame.sensors) {
        fovBySensor[s.id] = s.fov_deg
        pixelsBySensor[s.id] = s.pixels_h
      }
      hold.ingest(frame.reports, fovBySensor, performance.now(), pixelsBySensor)
    }
    const unsubscribe = session.store.subscribe(ingest)
    ingest()

    const loop = (now: number) => {
      if (!running) return
      raf = requestAnimationFrame(loop)
      const state = session.store.getState()
      const frame = state.frame
      if (!frame) return
      const status = frame.sensors.find((s) => s.id === sensorId)
      const pose = sensorPose(state, sensorId, now)
      if (!status || !pose || pose.fovDeg === null) return
      scene.setTimeOfDay(frame.time_of_day_h)
      scene.update({
        position: status.position,
        bearingDeg: pose.bearingDeg,
        elevationDeg: pose.elevationDeg,
        fovDeg: pose.fovDeg,
        reports: hold.active(now),
        nowMs: now,
      })
      scene.render(now)
      // Frame times feed the tier controller; it may step the tier down or up once.
      const change = qualityStore.frame(now)
      if (change) scene.setQuality(change.tier)
    }
    raf = requestAnimationFrame(loop)

    // No drawing while the tab is hidden.
    const onVisibility = () => {
      if (document.hidden) {
        running = false
        cancelAnimationFrame(raf)
      } else if (!running) {
        running = true
        raf = requestAnimationFrame(loop)
      }
    }
    document.addEventListener('visibilitychange', onVisibility)
    return () => {
      running = false
      cancelAnimationFrame(raf)
      document.removeEventListener('visibilitychange', onVisibility)
      unsubscribe()
      observer.disconnect()
      sceneRef.current = null
      scene.dispose()
      el.remove()
      resetLook()
    }
  }, [session, sensorId, welcome, unavailable])

  useEffect(() => {
    sceneRef.current?.setMode(mode)
    if (mode === 'day') resetLook()
  }, [mode])

  useEffect(() => {
    sceneRef.current?.setQuality(quality.tier)
  }, [quality.tier])

  const packKey = terrain.status === 'ready' ? (terrain.pack?.id ?? 'flat') : terrain.status
  useEffect(() => {
    if (terrain.status === 'ready') void sceneRef.current?.setTerrain(terrain.pack)
    // the pack object is identified by its id
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [packKey])

  if (!sensorId) {
    return (
      <div className="p-3">
        <EmptyState title={t('live.eo.noSensor')} description={t('live.eo.noSensorBody')} />
      </div>
    )
  }
  if (unavailable) {
    return (
      <div
        role="alert"
        className="flex h-full flex-col items-start justify-center gap-2 bg-surface-2 p-6"
      >
        <p className="m-0 text-md font-semibold">{t('live.eo.noWebgl')}</p>
        <p className="m-0 max-w-[520px] text-sm text-ink-2">{t('live.eo.noWebglBody')}</p>
      </div>
    )
  }
  return (
    <div
      ref={box}
      className="relative h-full min-h-0 w-full overflow-hidden bg-bg"
      data-terrain={terrainAttribute(terrain)}
      data-mode={mode}
      data-tier={quality.tier}
    >
      <EoHud sensorId={sensorId} mode={mode} />
      <TerrainNotice terrain={terrain} />
    </div>
  )
}

function terrainAttribute(state: TerrainState): string {
  if (state.status !== 'ready') return state.status
  return state.pack ? 'pack' : 'flat'
}

/** Terrain status, kept small: a failure never blocks the session, and the notice says what is drawn. */
function TerrainNotice({ terrain }: { terrain: TerrainState }) {
  const { t } = useTranslation()
  if (terrain.status === 'error') {
    return (
      <div
        className="absolute inset-x-3 bottom-12 flex justify-center"
        data-testid="terrain-notice"
      >
        <div className="pointer-events-auto max-w-[520px]">
          <InlineAlert tone="warning">
            <p className="m-0 font-semibold">{t('live.eo.terrain.error')}</p>
            <p className="m-0 mt-1 text-ink-2">{t('live.eo.terrain.errorBody')}</p>
            <p className="num m-0 mt-1 text-2xs text-ink-2">{terrain.message}</p>
          </InlineAlert>
        </div>
      </div>
    )
  }
  if (terrain.status === 'loading') {
    return (
      <p
        role="status"
        data-testid="terrain-loading"
        className="num absolute bottom-12 left-1/2 m-0 -translate-x-1/2 border border-line bg-surface-1 px-2 py-1 text-xs text-ink-2"
      >
        {t('live.eo.terrain.loading')}
      </p>
    )
  }
  if (terrain.pack) {
    return (
      <p
        data-testid="terrain-label"
        className="num pointer-events-none absolute bottom-12 left-1/2 m-0 -translate-x-1/2 bg-bg/80 px-2 py-0.5 text-2xs text-ink-2"
      >
        {t('live.eo.terrain.label', { name: terrain.pack.name })}
      </p>
    )
  }
  return null
}
