/**
 * Sun and moon for the EO scene, from the scenario clock (solar time in hours). Pure, so the
 * scene and its tests share one definition. Axes are three.js axes: x east, y up, -z north.
 *
 * The sun rises due east at 06:00, stands highest at 12:00 and sets due west at 18:00, as the
 * existing sky colours assume (`skyColours` in geometry.ts). The moon stands exactly opposite
 * the sun and is always drawn full: a fictional moon, not an ephemeris.
 */
import { clamp, DEG } from '../geometry'

export type Vec3Tuple = [number, number, number]

export interface Celestial {
  /** Unit vector towards the sun. Below the horizon (y < 0) at night. */
  sunDir: Vec3Tuple
  /** Unit vector towards the moon, opposite the sun. */
  moonDir: Vec3Tuple
  /** sin of the sun's elevation scaled to 1 at noon: the lighting driver (negative at night). */
  sunHeight: number
  moonHeight: number
  /** 0 by day, 1 in full night; twilight in between. */
  night: number
  /** Opacity of the stars, 0 by day. */
  stars: number
}

function direction(azimuthRad: number, elevationRad: number): Vec3Tuple {
  const c = Math.cos(elevationRad)
  return [Math.sin(azimuthRad) * c, Math.sin(elevationRad), -Math.cos(azimuthRad) * c]
}

export function celestial(hours: number, cloudCoverPct = 0): Celestial {
  const sunHeight = Math.sin(((hours - 6) / 12) * Math.PI)
  const azimuth = (90 + ((hours - 6) / 12) * 180) * DEG
  const elevation = sunHeight * (Math.PI / 2.2)
  const sunDir = direction(azimuth, elevation)
  const moonDir = direction(azimuth + Math.PI, -elevation)
  const night = clamp((0.08 - sunHeight) / 0.3, 0, 1)
  const clear = 1 - 0.85 * clamp(cloudCoverPct / 100, 0, 1)
  return {
    sunDir,
    moonDir,
    sunHeight,
    moonHeight: -sunHeight,
    night,
    stars: clamp((-sunHeight - 0.08) / 0.2, 0, 1) * clear,
  }
}

export interface Lighting {
  sunIntensity: number
  /** Warmth of the sun, 0 high and white, 1 low and orange. */
  sunWarmth: number
  ambientIntensity: number
  moonIntensity: number
  /** ACES filmic exposure. */
  exposure: number
}

/**
 * Light levels for a time of day and cloud cover. Intensities are in three.js physical units
 * (a Lambert surface under intensity π shows its albedo), tuned for ACES filmic tone mapping.
 */
export function lighting(hours: number, cloudCoverPct = 0): Lighting {
  const { sunHeight, moonHeight } = celestial(hours)
  const day = clamp(sunHeight, 0, 1)
  const cloud = clamp(cloudCoverPct / 100, 0, 1)
  const direct = 1 - 0.65 * cloud
  return {
    sunIntensity: (0.05 + 3.1 * Math.pow(day, 0.8)) * direct,
    sunWarmth: 1 - clamp(sunHeight * 2.2, 0, 1),
    ambientIntensity: 0.16 + 0.95 * day + 0.25 * cloud * day,
    moonIntensity: 0.26 * clamp(moonHeight * 1.6, 0, 1) * (1 - 0.7 * cloud),
    exposure: 1.0 + 0.55 * clamp(1 - sunHeight * 3, 0, 1),
  }
}
