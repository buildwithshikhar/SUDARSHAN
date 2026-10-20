import { SKILLS, scenarioById, traineeById, at, type SkillId, type Trainee } from '../../mock'

export const pct = (share: number, digits = 0): string => `${(share * 100).toFixed(digits)}%`

export const shortDate = (iso: string): string => iso.slice(0, 10)

export const shortTime = (iso: string): string => iso.slice(0, 19).replace('T', ' ')

export const VIRIDIS_STOPS = ['#440154', '#3b528b', '#21908d', '#5dc863', '#fde725']

export function viridis(t: number): string {
  const x = Math.min(1, Math.max(0, t)) * (VIRIDIS_STOPS.length - 1)
  const i = Math.min(VIRIDIS_STOPS.length - 2, Math.floor(x))
  const f = x - i
  const a = VIRIDIS_STOPS[i] ?? '#000000'
  const b = VIRIDIS_STOPS[i + 1] ?? '#ffffff'
  const mix = (k: number) =>
    Math.round(parseInt(a.slice(k, k + 2), 16) * (1 - f) + parseInt(b.slice(k, k + 2), 16) * f)
  return `rgb(${mix(1)} ${mix(3)} ${mix(5)})`
}

export const fmtClock = (s: number): string => {
  const m = Math.floor(s / 60)
  const r = Math.floor(s % 60)
  return `${String(m).padStart(2, '0')}:${String(r).padStart(2, '0')}`
}

export function csvFor(trainees: Trainee[]): string {
  const head = [
    'trainee',
    'call_sign',
    'session',
    'date',
    'scenario',
    'mode',
    'score',
    'detect_time_s',
    'classify_time_s',
    'reaction_time_s',
    'classify_accuracy',
    'false_alarms',
    'roe_compliance',
  ]
  const lines = trainees.flatMap((t) =>
    t.sessions.map((s, i) =>
      [
        t.name,
        t.callSign,
        i + 1,
        s.date,
        scenarioById(s.scenarioId).name,
        s.mode,
        s.score,
        s.detectTimeS,
        s.classifyTimeS,
        s.reactionTimeS,
        s.classifyAccuracy,
        s.falseAlarms,
        s.roeCompliance,
      ]
        .map((v) => `"${String(v).replace(/"/g, '""')}"`)
        .join(','),
    ),
  )
  return [head.join(','), ...lines].join('\n')
}

/** The signed-in trainee in the seeded roster. */
export const ME = traineeById('t01')

export const skillVector = (skills: Record<SkillId, number[]>): Record<SkillId, number> =>
  Object.fromEntries(SKILLS.map((k) => [k, at(skills[k], 3)])) as Record<SkillId, number>
