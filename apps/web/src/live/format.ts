import { useTranslation } from 'react-i18next'
import { wrap360 } from './geometry'
import type { Briefing, Vec3 } from './protocol'
import type { Lang } from './roe'

/** Interface language, narrowed to the two the protocol carries text for. */
export function useLang(): Lang {
  const { i18n } = useTranslation()
  return i18n.language === 'hi' ? 'hi' : 'en'
}

export const fmtBearing = (deg: number): string =>
  `${String(Math.round(wrap360(deg)) % 360).padStart(3, '0')}°`

export function fmtRange(m: number): string {
  return m >= 1000 ? `${(m / 1000).toFixed(2)} km` : `${Math.round(m)} m`
}

export const fmtSpeed = (mps: number): string => mps.toFixed(1)

export function fmtHours(hours: number): string {
  const total = Math.round((((hours % 24) + 24) % 24) * 60)
  return `${String(Math.floor(total / 60) % 24).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`
}

/** Scenario elapsed time as mm:ss.s. */
export function fmtElapsed(timeS: number): string {
  const m = Math.floor(timeS / 60)
  return `${String(m).padStart(2, '0')}:${(timeS - m * 60).toFixed(1).padStart(4, '0')}`
}

export function fmtUtc(date: Date): string {
  return date.toISOString().slice(11, 19)
}

export const fmtPercent = (share: number): string => `${Math.round(share * 100)}%`

/** The protected site the bearings and ranges are quoted from: the first asset, else the first zone. */
export function sitePosition(briefing: Briefing): Vec3 {
  return briefing.assets[0]?.position ?? briefing.zones[0]?.center ?? { x: 0, y: 0, z: 0 }
}

/** Short sensor codes for the track table. */
export function sensorCode(id: string): string {
  const prefix = id.split('-')[0] ?? id
  switch (prefix) {
    case 'radar':
      return 'RDR'
    case 'eo':
      return 'EO'
    case 'ir':
      return 'IR'
    case 'rf':
      return 'RF'
    case 'acoustic':
      return 'AC'
    default:
      return prefix.slice(0, 3).toUpperCase()
  }
}
