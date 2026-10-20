import { at, clamp, mulberry32, round } from './rng'

/** The skills the adaptive model tracks. Labels live under `m.skill.*` in the translations. */
export const SKILLS = [
  'detect-radar',
  'detect-eo',
  'detect-rf',
  'detect-acoustic',
  'classify-rotary',
  'classify-fixed-wing',
  'classify-fpv',
  'classify-clutter',
  'assess-intent',
  'respond-roe',
  'hold-fire-civil',
  'handover',
] as const
export type SkillId = (typeof SKILLS)[number]

/** The nine recognition classes, in the order the classify list uses (labels: `live.class.*`). */
export const CLASSES = [
  'rotary-small',
  'fixed-wing-small',
  'bird',
  'unknown',
  'fpv-small',
  'fixed-wing-medium',
  'fixed-wing-large',
  'kite',
  'balloon',
] as const
export type ClassId = (typeof CLASSES)[number]

export interface SessionRecord {
  id: string
  traineeId: string
  scenarioId: string
  /** ISO date of the session. */
  date: string
  mode: 'assessed' | 'practice'
  /** Whole-session score, 0 to 100. */
  score: number
  detectTimeS: number
  classifyTimeS: number
  reactionTimeS: number
  /** Share of contacts classified correctly, 0 to 1. */
  classifyAccuracy: number
  falseAlarms: number
  /** Share of responses permitted by the rule pack, 0 to 1. */
  roeCompliance: number
  contacts: number
}

export interface Trainee {
  id: string
  name: string
  callSign: string
  cohortId: string
  unitId: string
  sessions: SessionRecord[]
  /** Proficiency per skill after each of the four sessions, 0 to 1. */
  skills: Record<SkillId, number[]>
  notes: { date: string; author: string; text: string }[]
}

export interface Unit {
  id: string
  name: string
  location: string
  members: number
}

export interface Cohort {
  id: string
  name: string
  unitId: string
  curriculumId: string
  traineeIds: string[]
  start: string
  instructor: string
}

export const UNITS: Unit[] = [
  { id: 'u-kestrel', name: 'Kestrel Detachment', location: 'Heron Ridge range', members: 14 },
  { id: 'u-osprey', name: 'Osprey Detachment', location: 'Osprey Town range', members: 11 },
  { id: 'u-merlin', name: 'Merlin Training Wing', location: 'Merlin Pass school', members: 9 },
]

export const COHORTS: Cohort[] = [
  {
    id: 'co-kestrel',
    name: 'Kestrel · Course 26-1',
    unitId: 'u-kestrel',
    curriculumId: 'cu-core',
    traineeIds: ['t01', 't02', 't03', 't04', 't05', 't06'],
    start: '2026-09-08',
    instructor: 'Maj. Ritu Banerjee',
  },
  {
    id: 'co-osprey',
    name: 'Osprey · Course 26-1',
    unitId: 'u-osprey',
    curriculumId: 'cu-core',
    traineeIds: ['t07', 't08', 't09', 't10', 't11', 't12'],
    start: '2026-09-15',
    instructor: 'Capt. Sandeep Rao',
  },
]

const PEOPLE: { name: string; callSign: string }[] = [
  { name: 'Arjun Rawat', callSign: 'Falcon 1' },
  { name: 'Meera Nair', callSign: 'Falcon 2' },
  { name: 'Karan Bhatia', callSign: 'Falcon 3' },
  { name: 'Sunita Yadav', callSign: 'Falcon 4' },
  { name: 'Rohit Chauhan', callSign: 'Falcon 5' },
  { name: 'Ananya Iyer', callSign: 'Falcon 6' },
  { name: 'Vikram Sandhu', callSign: 'Lapwing 1' },
  { name: 'Pooja Menon', callSign: 'Lapwing 2' },
  { name: 'Imran Qureshi', callSign: 'Lapwing 3' },
  { name: 'Deepak Joshi', callSign: 'Lapwing 4' },
  { name: 'Harpreet Gill', callSign: 'Lapwing 5' },
  { name: 'Lakshmi Pillai', callSign: 'Lapwing 6' },
]

/** Scenario pool the four sessions of a trainee are drawn from (see scenarios.ts for the list). */
const SESSION_SCENARIOS = ['sc-01', 'sc-05', 'sc-09', 'sc-13']
const SESSION_DATES = ['2026-09-21', '2026-09-28', '2026-10-05', '2026-10-12']

function buildTrainee(index: number): Trainee {
  const rng = mulberry32(7000 + index * 131)
  const person = at(PEOPLE, index)
  const cohort = index < 6 ? COHORTS[0] : COHORTS[1]
  const ability = 50 + rng() * 22
  const gain = 4.2 + rng() * 5.4
  const sessions: SessionRecord[] = SESSION_DATES.map((date, s) => {
    const score = clamp(ability + gain * s + (rng() - 0.5) * 6, 38, 97)
    const quality = (score - 38) / 59
    return {
      id: `s-${String(index + 1).padStart(2, '0')}-${s + 1}`,
      traineeId: `t${String(index + 1).padStart(2, '0')}`,
      scenarioId: at(SESSION_SCENARIOS, s),
      date,
      mode: s === 0 ? 'practice' : 'assessed',
      score: round(score, 1),
      detectTimeS: round(clamp(19.4 - quality * 11.2 + (rng() - 0.5) * 2.2, 4.1, 22), 1),
      classifyTimeS: round(clamp(31 - quality * 16 + (rng() - 0.5) * 3, 8, 36), 1),
      reactionTimeS: round(clamp(8.6 - quality * 4.4 + (rng() - 0.5) * 1.1, 2.1, 9.8), 1),
      classifyAccuracy: round(clamp(0.46 + quality * 0.46 + (rng() - 0.5) * 0.06, 0.4, 0.98), 2),
      falseAlarms: Math.max(0, Math.round(5.6 - quality * 4.8 + (rng() - 0.5) * 1.6)),
      roeCompliance: round(clamp(0.62 + quality * 0.34 + (rng() - 0.5) * 0.05, 0.5, 1), 2),
      contacts: 9 + Math.round(rng() * 6),
    }
  })
  const skills = Object.fromEntries(
    SKILLS.map((skill, k) => {
      const start = clamp(
        0.28 + (ability - 50) / 90 + (rng() - 0.5) * 0.22 - (k % 5) * 0.015,
        0.1,
        0.8,
      )
      const step = 0.035 + rng() * 0.07
      return [
        skill,
        [0, 1, 2, 3].map((s) =>
          round(clamp(start + step * s + (rng() - 0.5) * 0.03, 0.05, 0.97), 2),
        ),
      ]
    }),
  ) as Record<SkillId, number[]>
  return {
    id: `t${String(index + 1).padStart(2, '0')}`,
    name: person.name,
    callSign: person.callSign,
    cohortId: cohort?.id ?? 'co-kestrel',
    unitId: cohort?.unitId ?? 'u-kestrel',
    sessions,
    skills,
    notes:
      index % 3 === 0
        ? [
            {
              date: '2026-10-06',
              author: cohort?.instructor ?? '',
              text: 'Strong on radar handoffs. Hesitates before committing a classification on RF-only contacts.',
            },
          ]
        : index % 3 === 1
          ? [
              {
                date: '2026-09-29',
                author: cohort?.instructor ?? '',
                text: 'Holds fire correctly on civil traffic. Needs more repetitions on FPV versus small rotary.',
              },
            ]
          : [],
  }
}

export const TRAINEES: Trainee[] = Array.from({ length: 12 }, (_, i) => buildTrainee(i))

export const traineeById = (id: string): Trainee => {
  const found = TRAINEES.find((t) => t.id === id)
  if (!found) throw new Error(`unknown trainee ${id}`)
  return found
}

export const lastSession = (trainee: Trainee): SessionRecord => at(trainee.sessions, 3)

export const mean = (values: number[]): number =>
  values.length === 0 ? 0 : values.reduce((a, b) => a + b, 0) / values.length

/** Mean of a session metric across a set of trainees, per session number (0 to 3). */
export function curveFor(
  trainees: Trainee[],
  pick: (s: SessionRecord) => number,
): { x: number; y: number }[] {
  return [0, 1, 2, 3].map((s) => ({
    x: s + 1,
    y: round(mean(trainees.map((t) => pick(at(t.sessions, s)))), 2),
  }))
}

export interface Ranking {
  rank: number
  trainee: Trainee
  score: number
  delta: number
  accuracy: number
  detectTimeS: number
}

/** Unit ranking by the latest session score, with the change from the first session. */
export function rankings(trainees: Trainee[]): Ranking[] {
  return trainees
    .map((trainee) => ({
      trainee,
      score: lastSession(trainee).score,
      delta: round(lastSession(trainee).score - at(trainee.sessions, 0).score, 1),
      accuracy: lastSession(trainee).classifyAccuracy,
      detectTimeS: lastSession(trainee).detectTimeS,
    }))
    .sort((a, b) => b.score - a.score)
    .map((row, i) => ({ ...row, rank: i + 1 }))
}

/** Latest proficiency of one skill across a set of trainees. */
export const latestSkill = (trainees: Trainee[], skill: SkillId): number =>
  round(mean(trainees.map((t) => at(t.skills[skill], 3))), 2)
