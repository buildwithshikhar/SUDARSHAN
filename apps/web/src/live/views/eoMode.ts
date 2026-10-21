/**
 * The EO picture modes, which of them a sensor supports, and the rendering model behind the
 * thermal and night-vision looks. Pure: the scene and the tests share these definitions.
 *
 * Thermal here is a RENDERING MODEL, not radiometric: each surface class gets a 0..1 "apparent
 * temperature" from a simple day/night cycle, then the picture is normalised by an automatic
 * gain. There are no kelvin, no emissivity and no noise-equivalent figure (docs/SENSOR_MODELS.md,
 * data policy in CONTRIBUTING.md).
 */
import { clamp } from '../geometry'

export type EoMode = 'day' | 'night-vision' | 'thermal-white-hot' | 'thermal-black-hot'

export const EO_MODES: readonly EoMode[] = [
  'day',
  'night-vision',
  'thermal-white-hot',
  'thermal-black-hot',
]

export const isThermal = (mode: EoMode): boolean => mode.startsWith('thermal')

/** What the briefing says about a sensor site. */
export interface SensorSiteLike {
  modality?: string
  profile?: string
}

/**
 * The modes a sensor can show. A thermal camera offers both polarities, a night-vision sensor
 * its own phosphor picture, and any other EO sensor the daylight picture. Nothing is offered that
 * the sensor's profile does not support.
 */
export function availableModes(site: SensorSiteLike | null | undefined): EoMode[] {
  const profile = (site?.profile ?? '').toLowerCase()
  if (site?.modality === 'ir' || profile.includes('thermal')) {
    return ['thermal-white-hot', 'thermal-black-hot']
  }
  if (/(^|[-_])(nv|night)([-_]|$)/.test(profile)) return ['night-vision']
  return ['day']
}

/** The mode to show: the operator's pick if the sensor supports it, otherwise the first it does. */
export function resolveMode(
  wanted: EoMode | null | undefined,
  available: readonly EoMode[],
): EoMode {
  if (wanted && available.includes(wanted)) return wanted
  return available[0] ?? 'day'
}

/** The sensor the EO view shows: the first optical one, preferring visible-band, else thermal. */
export function pickEoSensor<T extends { id: string; modality: string }>(
  sensors: readonly T[],
): T | null {
  return (
    sensors.find((s) => s.modality === 'eo') ?? sensors.find((s) => s.modality === 'ir') ?? null
  )
}

// ---------------------------------------------------------------------- thermal model

export type ThermalClass =
  'terrain' | 'building' | 'vegetation' | 'water' | 'sky' | 'target' | 'metal'

const cycle = (hours: number, peakH: number) => Math.cos(((hours - peakH) / 24) * 2 * Math.PI)

/**
 * Apparent temperature 0..1 of a surface class at a solar time. Bare ground heats in the day and
 * cools at night; buildings run warmer and lag behind it; vegetation stays near the air
 * temperature; water barely moves; the cold sky is the floor; the target is warm.
 */
export function surfaceTemperature(cls: ThermalClass, hours: number, cloudCoverPct = 0): number {
  const cloud = clamp(cloudCoverPct / 100, 0, 1)
  switch (cls) {
    case 'terrain':
      return clamp(0.46 + (0.2 - 0.08 * cloud) * cycle(hours, 14.5), 0, 1)
    case 'building':
      return clamp(0.58 + (0.13 - 0.04 * cloud) * cycle(hours, 16.5), 0, 1)
    case 'vegetation':
      return clamp(0.36 + 0.07 * cycle(hours, 14), 0, 1)
    case 'water':
      return clamp(0.3 + 0.03 * cycle(hours, 17), 0, 1)
    case 'metal':
      return clamp(0.44 + 0.2 * cycle(hours, 14), 0, 1)
    case 'sky':
      return clamp(0.04 + 0.2 * cloud, 0, 1)
    case 'target':
      return 0.94
  }
}

// ---------------------------------------------------------------------- automatic gain

export interface GainRange {
  lo: number
  hi: number
  /** Mean luminance of the sample, 0..1. */
  mean: number
}

/** The sample is stored as sqrt(luminance) in 8 bits, which keeps precision in the dark. */
const decode = (byte: number): number => {
  const v = byte / 255
  return v * v
}

/**
 * Low and high luminance percentiles of a downsampled image (RGBA bytes, luminance in the red
 * channel stored as sqrt) by a 256-bin histogram. The range is never narrower than `minSpan`.
 */
export function lumaRange(
  rgba: ArrayLike<number>,
  lowPct = 0.02,
  highPct = 0.98,
  minSpan = 0.06,
): GainRange {
  const pixels = Math.floor(rgba.length / 4)
  if (pixels === 0) return { lo: 0, hi: 1, mean: 0.5 }
  const bins = new Uint32Array(256)
  let sum = 0
  for (let i = 0; i < pixels; i++) {
    const b = rgba[i * 4] ?? 0
    bins[b] = (bins[b] ?? 0) + 1
    sum += decode(b)
  }
  const at = (fraction: number): number => {
    const target = fraction * pixels
    let acc = 0
    for (let b = 0; b < 256; b++) {
      acc += bins[b] ?? 0
      if (acc >= target) return decode(b)
    }
    return 1
  }
  let lo = at(lowPct)
  let hi = at(highPct)
  if (hi - lo < minSpan) {
    const mid = (hi + lo) / 2
    lo = mid - minSpan / 2
    hi = mid + minSpan / 2
  }
  return { lo, hi, mean: sum / pixels }
}

/** Move a gain range towards a target: one-pole smoothing so the picture does not pump. */
export function easeRange(current: GainRange, target: GainRange, k: number): GainRange {
  return {
    lo: current.lo + (target.lo - current.lo) * k,
    hi: current.hi + (target.hi - current.hi) * k,
    mean: current.mean + (target.mean - current.mean) * k,
  }
}

/** Night-vision tube gain for a mean scene luminance: lifts a dark scene, eases off a bright one. */
export function nvGain(meanLuma: number): number {
  return clamp(0.22 / Math.max(meanLuma, 0.004), 0.6, 16)
}

/** The gain readout shown in the HUD, 0..100 %: how hard the picture is being stretched. */
export function gainPercent(range: GainRange): number {
  return Math.round(clamp(1 - (range.hi - range.lo), 0, 1) * 100)
}

// ---------------------------------------------------------------------- reticle ink

export interface ReticleInk {
  stroke: string
  halo: string
  label: string
}

/**
 * Reticle colours for each picture. White-hot is a bright reticle on a dark halo and black-hot
 * the reverse, so it reads against a cold sky of either polarity; night vision is bright
 * phosphor green on black; the day picture uses the theme tokens.
 */
export function reticleInk(mode: EoMode): ReticleInk {
  switch (mode) {
    case 'thermal-white-hot':
      return { stroke: '#f2f4f5', halo: '#050607', label: '#f2f4f5' }
    case 'thermal-black-hot':
      return { stroke: '#050607', halo: '#f2f4f5', label: '#050607' }
    case 'night-vision':
      return { stroke: '#b6ffc0', halo: '#001a06', label: '#b6ffc0' }
    case 'day':
      return { stroke: 'var(--text)', halo: 'var(--bg)', label: 'var(--text)' }
  }
}
