/**
 * Geometry shared by the radar PPI, the EO view and the track table.
 * Frame: local east-north-up in metres (x east, y north, z up); bearings are compass degrees
 * clockwise from north; elevation is degrees above the horizontal.
 */
import type { Vec3 } from './protocol'

export const DEG = Math.PI / 180

/** Wrap to [0, 360). */
export function wrap360(deg: number): number {
  return ((deg % 360) + 360) % 360
}

/** Wrap to [-180, 180). */
export function wrap180(deg: number): number {
  return wrap360(deg + 180) - 180
}

/** Interpolate between two bearings along the short way round. */
export function lerpAngleDeg(from: number, to: number, k: number): number {
  return wrap360(from + wrap180(to - from) * k)
}

export function lerp(a: number, b: number, k: number): number {
  return a + (b - a) * k
}

export function clamp(value: number, lo: number, hi: number): number {
  return Math.min(hi, Math.max(lo, value))
}

export interface Polar {
  bearingDeg: number
  /** Horizontal distance in metres. */
  rangeM: number
  slantM: number
  elevationDeg: number
}

/** Bearing, ground range, slant range and elevation of `to` as seen from `from`. */
export function polarFrom(from: Vec3, to: Vec3): Polar {
  const dx = to.x - from.x
  const dy = to.y - from.y
  const dz = to.z - from.z
  const rangeM = Math.hypot(dx, dy)
  return {
    bearingDeg: wrap360(Math.atan2(dx, dy) / DEG),
    rangeM,
    slantM: Math.hypot(rangeM, dz),
    elevationDeg: Math.atan2(dz, rangeM) / DEG,
  }
}

/** Dead-reckon a position along its velocity, clamped so a stalled link cannot fling it away. */
export function extrapolate(position: Vec3, velocity: Vec3, dtS: number, maxDtS = 0.25): Vec3 {
  const dt = clamp(dtS, 0, maxDtS)
  return {
    x: position.x + velocity.x * dt,
    y: position.y + velocity.y * dt,
    z: position.z + velocity.z * dt,
  }
}

// ---------------------------------------------------------------------- PPI

export interface PpiFrame {
  cx: number
  cy: number
  /** Radius of the outermost ring in pixels. */
  radiusPx: number
  rangeMaxM: number
}

/** Bearing and ground range to canvas pixels: north up, bearing clockwise, range linear. */
export function ppiProject(bearingDeg: number, rangeM: number, frame: PpiFrame) {
  const r = (rangeM / frame.rangeMaxM) * frame.radiusPx
  const a = bearingDeg * DEG
  return { x: frame.cx + r * Math.sin(a), y: frame.cy - r * Math.cos(a) }
}

/** Canvas pixels back to bearing and ground range (for hit-testing a click). */
export function ppiUnproject(x: number, y: number, frame: PpiFrame) {
  const dx = x - frame.cx
  const dy = frame.cy - y
  return {
    bearingDeg: wrap360(Math.atan2(dx, dy) / DEG),
    rangeM: (Math.hypot(dx, dy) / frame.radiusPx) * frame.rangeMaxM,
  }
}

/** East and north offsets from the PPI centre (the radar) to canvas pixels. */
export function ppiProjectEnu(origin: Vec3, p: Vec3, frame: PpiFrame) {
  const polar = polarFrom(origin, p)
  return ppiProject(polar.bearingDeg, polar.rangeM, frame)
}

/** The sweep's bearing at time `timeS` for a beam that makes one turn per `periodS`. */
export function sweepBearingDeg(timeS: number, periodS: number): number {
  return wrap360((timeS / periodS) * 360)
}

/** Did the sweep, moving clockwise from `prevDeg` to `nowDeg`, pass `bearingDeg`? */
export function sweepPassed(prevDeg: number, nowDeg: number, bearingDeg: number): boolean {
  const travelled = wrap360(nowDeg - prevDeg)
  if (travelled === 0) return false
  const to = wrap360(bearingDeg - prevDeg)
  return to > 0 && to <= travelled
}

/** A range ring step that gives 3 to 6 rings, from a 1-2-5 series (in metres). */
export function ringStepM(rangeMaxM: number): number {
  const target = rangeMaxM / 4
  const pow = 10 ** Math.floor(Math.log10(target))
  const base = [1, 2, 5, 10].map((m) => m * pow)
  return base.reduce((best, step) =>
    Math.abs(step - target) < Math.abs(best - target) ? step : best,
  )
}

// ---------------------------------------------------------------------- EO

/** The EO camera image is 1920 px wide at every zoom (the protocol carries no pixel count). */
export const EO_PIXELS_H = 1920

/** Angle subtended by one pixel at a field of view of `fovDeg`. */
export function pixelAngleDeg(fovDeg: number, pixelsH = EO_PIXELS_H): number {
  return fovDeg / pixelsH
}

/** Angular size of a report: apparent pixels times the pixel angle. Never a range. */
export function angularSizeDeg(apparentPx: number, fovDeg: number, pixelsH = EO_PIXELS_H): number {
  return apparentPx * pixelAngleDeg(fovDeg, pixelsH)
}

/** Unit vector for a compass bearing and elevation, in three.js axes (x east, y up, -z north). */
export function directionThree(bearingDeg: number, elevationDeg: number): [number, number, number] {
  const az = bearingDeg * DEG
  const el = elevationDeg * DEG
  return [Math.sin(az) * Math.cos(el), Math.sin(el), -Math.cos(az) * Math.cos(el)]
}

/** Vertical field of view for a horizontal one at the given aspect (width / height). */
export function verticalFovDeg(horizontalFovDeg: number, aspect: number): number {
  return (2 * Math.atan(Math.tan((horizontalFovDeg * DEG) / 2) / aspect)) / DEG
}

/** Sky colour stops (zenith, horizon) for a solar time of day in hours; plain linear mixing. */
export function skyColours(timeOfDayH: number): {
  zenith: [number, number, number]
  horizon: [number, number, number]
} {
  // Elevation of the sun, simplified: noon high, 06:00 and 18:00 on the horizon.
  const sun = Math.sin(((timeOfDayH - 6) / 12) * Math.PI)
  const day = clamp((sun + 0.12) / 0.5, 0, 1)
  const dusk = clamp(1 - Math.abs(sun) / 0.25, 0, 1) * (sun > -0.25 ? 1 : 0)
  const mix = (a: number[], b: number[], k: number): [number, number, number] => [
    lerp(a[0] ?? 0, b[0] ?? 0, k),
    lerp(a[1] ?? 0, b[1] ?? 0, k),
    lerp(a[2] ?? 0, b[2] ?? 0, k),
  ]
  const nightZ = [0.02, 0.03, 0.06]
  const nightH = [0.05, 0.06, 0.1]
  const dayZ = [0.2, 0.42, 0.7]
  const dayH = [0.66, 0.78, 0.88]
  const duskH = [0.82, 0.58, 0.42]
  const zenith = mix(nightZ, dayZ, day)
  const horizon = mix(mix(nightH, dayH, day), duskH, dusk * 0.7)
  return { zenith, horizon }
}
