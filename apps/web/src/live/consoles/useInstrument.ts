import { useCallback, useEffect, useRef } from 'react'
import { useLatest } from '../useLatest'
import { prefersReducedMotion } from '../views/theme'

/** Under reduced motion the picture is redrawn at most this often. */
export const REDUCED_MOTION_INTERVAL_MS = 1000

export interface InstrumentOptions {
  /** Draw one picture. Called with the context already scaled to CSS pixels. */
  paint: (ctx: CanvasRenderingContext2D, width: number, height: number) => void
  /** A counter that changes whenever the model behind the picture changed. */
  modelVersion: () => number
}

/**
 * A 2D canvas that fills its box and redraws only when something changed: the model's counter, a
 * resize, or `invalidate()`. The requestAnimationFrame loop runs only while the component is
 * mounted (the console tab is showing) and the document is visible, and under reduced motion it
 * draws at most once a second. Nothing is allocated per frame.
 */
export function useInstrument({ paint, modelVersion }: InstrumentOptions) {
  const wrapRef = useRef<HTMLDivElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const dirty = useRef(true)
  /** An operator input (a cursor key) is never held back by the reduced-motion interval. */
  const urgent = useRef(false)
  const paintRef = useLatest(paint)
  const versionRef = useLatest(modelVersion)

  const invalidate = useCallback(() => {
    dirty.current = true
    urgent.current = true
  }, [])

  useEffect(() => {
    const el = canvasRef.current
    const box = wrapRef.current
    if (!el || !box) return
    const ctx = el.getContext('2d')
    // jsdom has no canvas: the surrounding text and tables still render.
    if (!ctx) return
    const reduced = prefersReducedMotion()
    let w = 1
    let h = 1
    let dpr = 1
    let seen = -1
    let lastDraw = -Infinity
    let raf = 0
    let running = !document.hidden

    const resize = () => {
      const rect = box.getBoundingClientRect()
      dpr = Math.min(window.devicePixelRatio || 1, 2)
      w = Math.max(1, rect.width)
      h = Math.max(1, rect.height)
      el.width = Math.round(w * dpr)
      el.height = Math.round(h * dpr)
      dirty.current = true
    }
    const observer = new ResizeObserver(resize)
    observer.observe(box)
    resize()

    const frame = (now: number) => {
      if (!running) return
      raf = requestAnimationFrame(frame)
      if (reduced && !urgent.current && now - lastDraw < REDUCED_MOTION_INTERVAL_MS) return
      const v = versionRef.current()
      if (!dirty.current && v === seen) return
      if (w < 10 || h < 10) return
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      paintRef.current(ctx, w, h)
      seen = v
      dirty.current = false
      urgent.current = false
      lastDraw = now
    }
    if (running) raf = requestAnimationFrame(frame)

    const onVisibility = () => {
      if (document.hidden) {
        running = false
        cancelAnimationFrame(raf)
      } else if (!running) {
        running = true
        dirty.current = true
        raf = requestAnimationFrame(frame)
      }
    }
    document.addEventListener('visibilitychange', onVisibility)
    return () => {
      running = false
      cancelAnimationFrame(raf)
      document.removeEventListener('visibilitychange', onVisibility)
      observer.disconnect()
    }
  }, [paintRef, versionRef])

  return { wrapRef, canvasRef, invalidate }
}
