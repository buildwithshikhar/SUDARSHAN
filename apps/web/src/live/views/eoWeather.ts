/**
 * What the briefing's weather does to the EO picture: fog density, rain streaks and the wind that
 * moves them and the trees. The frame carries no weather, so the briefing's static figures are
 * the source; a missing figure falls back to a constant breeze. Everything here is "modelled".
 */
import { clamp, DEG } from '../geometry'

export interface WeatherLike {
  condition?: string
  visibility_m?: number
  wind_speed_mps?: number
  wind_from_deg?: number
  cloud_cover_pct?: number
}

/** The breeze used when the briefing gives no wind: light, from the west. */
export const BREEZE = { speedMps: 2.5, fromDeg: 270 } as const

export interface Wind {
  /** Where the air is going, in three.js axes (x east, -z north); not normalised. */
  x: number
  z: number
  speedMps: number
}

/** The wind vector: speed along the bearing opposite to where it blows from. */
export function windOf(weather: WeatherLike | null | undefined): Wind {
  const speed =
    typeof weather?.wind_speed_mps === 'number' && weather.wind_speed_mps >= 0
      ? weather.wind_speed_mps
      : BREEZE.speedMps
  const from = typeof weather?.wind_from_deg === 'number' ? weather.wind_from_deg : BREEZE.fromDeg
  const toward = (from + 180) * DEG
  return { x: Math.sin(toward) * speed, z: -Math.cos(toward) * speed, speedMps: speed }
}

/** Tree sway strength, 0 in still air to 1 at a strong wind (about 14 m/s). */
export function swayStrength(windSpeedMps: number): number {
  return clamp(windSpeedMps / 14, 0.06, 1)
}

/**
 * Exponential fog density for FogExp2 so that a dark object loses 98 % of its contrast at the
 * visibility (Koschmieder): density = sqrt(-ln 0.02) / V.
 */
export function fogDensity(visibilityM: number | undefined): number {
  const v = clamp(typeof visibilityM === 'number' ? visibilityM : 10_000, 150, 60_000)
  return Math.sqrt(-Math.log(0.02)) / v
}

/** Rain share of the particle budget, 0 when it is not raining. Heavier as the visibility closes. */
export function rainIntensity(weather: WeatherLike | null | undefined): number {
  if (weather?.condition !== 'rain') return 0
  const vis = typeof weather.visibility_m === 'number' ? weather.visibility_m : 6000
  return clamp(0.35 + (1 - vis / 10_000) * 0.65, 0.35, 1)
}

export interface FogShape {
  /** Extra density near the ground, as a multiple of the base. */
  groundBoost: number
  /** Height (m) over which that extra density fades out. */
  scaleM: number
  /** Warm tint mixed into the fog colour, 0..1 (dust). */
  tint: number
}

export function fogShape(weather: WeatherLike | null | undefined): FogShape {
  switch (weather?.condition) {
    case 'fog':
      return { groundBoost: 2.4, scaleM: 45, tint: 0 }
    case 'haze':
      return { groundBoost: 1.1, scaleM: 90, tint: 0.1 }
    case 'dust':
      return { groundBoost: 1.3, scaleM: 70, tint: 0.45 }
    case 'rain':
      return { groundBoost: 0.9, scaleM: 60, tint: 0 }
    default:
      return { groundBoost: 0.8, scaleM: 70, tint: 0 }
  }
}
