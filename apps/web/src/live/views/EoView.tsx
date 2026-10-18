import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { EmptyState } from '../../ui/States'
import { useLive, useLiveSession } from '../context'
import { sensorPose } from '../store'
import { EoHud } from './EoHud'
import { ReportHold } from './eoHold'
import { EoScene } from './eoScene'
import { webglAvailable } from './webgl'

/**
 * The EO sensor's picture: a three.js scene drawn from the sensor's pointing, its field of view
 * and its EO/IR reports only. If WebGL is missing the view says so instead of failing silently.
 */
export function EoView({ sensorId }: { sensorId: string | null }) {
  const { t } = useTranslation()
  const session = useLiveSession()
  const welcome = useLive((s) => s.welcome)
  const box = useRef<HTMLDivElement>(null)
  const [unavailable, setUnavailable] = useState(() => !webglAvailable())

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
      scene = new EoScene(el)
    } catch {
      el.remove()
      queueMicrotask(() => setUnavailable(true))
      return
    }
    scene.setSite(welcome.briefing)
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
      scene.setTimeOfDay(frame.time_of_day_h, welcome.briefing.weather.visibility_m)
      scene.update({
        position: status.position,
        bearingDeg: pose.bearingDeg,
        elevationDeg: pose.elevationDeg,
        fovDeg: pose.fovDeg,
        reports: hold.active(now),
        nowMs: now,
      })
      scene.render(now)
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
      scene.dispose()
      el.remove()
    }
  }, [session, sensorId, welcome, unavailable])

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
    <div ref={box} className="relative h-full min-h-0 w-full overflow-hidden bg-bg">
      <EoHud sensorId={sensorId} />
    </div>
  )
}
