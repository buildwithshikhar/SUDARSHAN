import { TRAINEES, type ClassId } from './people'
import { at, clamp, mulberry32, round } from './rng'
import type { Identity } from './replay'

export const SECTOR_IDS = ['north', 'east', 'south', 'west'] as const
export type SectorId = (typeof SECTOR_IDS)[number]

export interface TeamMember {
  id: string
  name: string
  callSign: string
  role: 'operator' | 'commander'
}

export const TEAM: TeamMember[] = [
  { id: 't01', name: 'Arjun Rawat', callSign: 'Falcon 1', role: 'commander' },
  { id: 't02', name: 'Meera Nair', callSign: 'Falcon 2', role: 'operator' },
  { id: 't03', name: 'Karan Bhatia', callSign: 'Falcon 3', role: 'operator' },
]

export interface TeamTrack {
  id: string
  cls: ClassId
  identity: Identity
  rangeM: number
  bearing: number
  owner: string
  /** Handover state against the receiving role. */
  handover: 'none' | 'offered' | 'accepted'
  history: number
}

/** Sector a bearing falls in: north covers 315 to 45 degrees, and so on clockwise. */
export function sectorOf(bearing: number): SectorId {
  const b = ((bearing % 360) + 360) % 360
  if (b >= 315 || b < 45) return 'north'
  if (b < 135) return 'east'
  if (b < 225) return 'south'
  return 'west'
}

export const INITIAL_ASSIGNMENT: Record<SectorId, string> = {
  north: 't02',
  east: 't02',
  south: 't03',
  west: 't03',
}

export const INITIAL_TRACKS: TeamTrack[] = [
  {
    id: 'T-101',
    cls: 'rotary-small',
    identity: 'hostile',
    rangeM: 1420,
    bearing: 38,
    owner: 't02',
    handover: 'none',
    history: 14,
  },
  {
    id: 'T-102',
    cls: 'bird',
    identity: 'neutral',
    rangeM: 2210,
    bearing: 72,
    owner: 't02',
    handover: 'none',
    history: 9,
  },
  {
    id: 'T-103',
    cls: 'fixed-wing-small',
    identity: 'neutral',
    rangeM: 1870,
    bearing: 161,
    owner: 't03',
    handover: 'none',
    history: 22,
  },
  {
    id: 'T-104',
    cls: 'fpv-small',
    identity: 'suspect',
    rangeM: 960,
    bearing: 214,
    owner: 't03',
    handover: 'none',
    history: 6,
  },
  {
    id: 'T-105',
    cls: 'unknown',
    identity: 'unknown',
    rangeM: 2480,
    bearing: 289,
    owner: 't03',
    handover: 'none',
    history: 3,
  },
  {
    id: 'T-106',
    cls: 'kite',
    identity: 'neutral',
    rangeM: 740,
    bearing: 332,
    owner: 't02',
    handover: 'none',
    history: 17,
  },
]

export const TEAM_SCORE = {
  total: 81.4,
  parts: [
    { id: 'coverage', score: 88.2 },
    { id: 'handover', score: 76.5 },
    { id: 'roe', score: 91.0 },
    { id: 'tempo', score: 72.8 },
  ],
  roles: [
    { id: 't01', role: 'commander', score: 83.7, detect: 0, classify: 0, handoverS: 6.2 },
    { id: 't02', role: 'operator', score: 82.9, detect: 8.4, classify: 17.1, handoverS: 7.9 },
    { id: 't03', role: 'operator', score: 77.6, detect: 10.2, classify: 21.3, handoverS: 11.4 },
  ],
}

export interface MonitorRow {
  id: string
  name: string
  callSign: string
  stage: 'detect' | 'classify' | 'assess' | 'respond'
  tracks: number
  score: number
  attention: boolean
  elapsedS: number
}

const STAGES = ['detect', 'classify', 'assess', 'respond'] as const

/** The running class at a given clock: deterministic in `tick`, so the grid moves but never jumps. */
export function monitorRows(tick: number, scenarioDurationS = 360): MonitorRow[] {
  return TRAINEES.slice(0, 8).map((t, i) => {
    const rng = mulberry32(400 + i)
    const offset = Math.round(rng() * 40)
    const elapsed = clamp(tick + offset - i * 3, 0, scenarioDurationS)
    const stage = at(STAGES, Math.floor((elapsed / scenarioDurationS) * 4 + i * 0.3))
    const skill = (t.sessions[3]?.score ?? 60) / 100
    return {
      id: t.id,
      name: t.name,
      callSign: t.callSign,
      stage,
      tracks: 2 + ((i + Math.floor(elapsed / 60)) % 5),
      score: round(
        clamp(skill * Math.min(1, elapsed / 140) * 100 + Math.sin(elapsed / 20 + i) * 2, 0, 100),
        1,
      ),
      attention: skill < 0.7 && elapsed > 90,
      elapsedS: elapsed,
    }
  })
}

export const INJECTIONS = ['contact', 'degrade', 'weather', 'comms'] as const
export type InjectionId = (typeof INJECTIONS)[number]
