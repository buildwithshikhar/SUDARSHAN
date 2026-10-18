/**
 * The gain readout of the thermal and night-vision pictures, published by the scene a few times a
 * second and read by the HUD. A module-level store so the scene (plain TypeScript) and the HUD
 * (React) need no shared parent.
 */
import { useSyncExternalStore } from 'react'
import type { EoMode } from './eoMode'

export interface EoLook {
  mode: EoMode
  /** How hard the thermal picture is stretched, 0..100. */
  gainPct: number
  /** Night-vision tube gain, as a multiple. */
  tubeGain: number
}

const NONE: EoLook = { mode: 'day', gainPct: 0, tubeGain: 1 }

let current: EoLook = NONE
const listeners = new Set<() => void>()

export function publishLook(next: EoLook): void {
  if (
    next.mode === current.mode &&
    next.gainPct === current.gainPct &&
    Math.abs(next.tubeGain - current.tubeGain) < 0.05
  ) {
    return
  }
  current = next
  listeners.forEach((l) => l())
}

export function resetLook(): void {
  if (current === NONE) return
  current = NONE
  listeners.forEach((l) => l())
}

export function useEoLook(): EoLook {
  return useSyncExternalStore(
    (listener) => {
      listeners.add(listener)
      return () => listeners.delete(listener)
    },
    () => current,
    () => NONE,
  )
}
