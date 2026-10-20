import { CLASSES, SKILLS, type ClassId, type SkillId } from './people'
import { at, mulberry32, round } from './rng'

export type TimeOfDay = 'dawn' | 'day' | 'dusk' | 'night'
export type Weather = 'clear' | 'haze' | 'rain' | 'fog' | 'dust'

export interface ScenarioItem {
  id: string
  name: string
  site: string
  terrain: 'Heron Ridge' | 'Osprey Town'
  timeOfDay: TimeOfDay
  weather: Weather
  /** 1 (introductory) to 5 (advanced). */
  difficulty: 1 | 2 | 3 | 4 | 5
  mix: Partial<Record<ClassId, number>>
  durationS: number
  seed: number
  origin: 'scripted' | 'generated'
  /** Oracle-defender score from the headless solvability run, 0 to 100. */
  oracleScore: number
  /** Distance to the nearest scenario in the feature space, 0 to 1. */
  diversity: number
  version: string
  tags: string[]
  focus: SkillId[]
}

const rows: [string, string, ScenarioItem['terrain'], TimeOfDay, Weather, 1 | 2 | 3 | 4 | 5][] = [
  ['Harrier Field: afternoon watch', 'Harrier Field', 'Heron Ridge', 'day', 'clear', 1],
  ['Harrier Field: dusk approach', 'Harrier Field', 'Heron Ridge', 'dusk', 'haze', 2],
  ['Heron Ridge: dawn survey', 'Heron Ridge', 'Heron Ridge', 'dawn', 'fog', 2],
  ['Heron Ridge: ridge line crossing', 'Heron Ridge', 'Heron Ridge', 'day', 'clear', 3],
  ['Osprey Town: market hours', 'Osprey Town', 'Osprey Town', 'day', 'haze', 2],
  ['Osprey Town: rooftop clutter', 'Osprey Town', 'Osprey Town', 'day', 'clear', 3],
  ['Osprey Town: night patrol', 'Osprey Town', 'Osprey Town', 'night', 'clear', 3],
  ['Kestrel Depot: perimeter watch', 'Kestrel Depot', 'Heron Ridge', 'night', 'clear', 3],
  ['Kestrel Depot: crosswind drift', 'Kestrel Depot', 'Heron Ridge', 'day', 'dust', 3],
  ['Merlin Pass: low cloud', 'Merlin Pass', 'Heron Ridge', 'dawn', 'fog', 4],
  ['Merlin Pass: two-axis approach', 'Merlin Pass', 'Heron Ridge', 'day', 'clear', 4],
  ['Lapwing Yard: shift change', 'Lapwing Yard', 'Osprey Town', 'dusk', 'rain', 4],
  ['Lapwing Yard: RF-quiet contact', 'Lapwing Yard', 'Osprey Town', 'night', 'haze', 4],
  ['Teal Basin: decoy and kite', 'Teal Basin', 'Heron Ridge', 'day', 'clear', 3],
  ['Teal Basin: evening flock', 'Teal Basin', 'Heron Ridge', 'dusk', 'clear', 2],
  ['Swift Junction: staggered group', 'Swift Junction', 'Osprey Town', 'day', 'haze', 5],
  ['Swift Junction: sensor outage', 'Swift Junction', 'Osprey Town', 'night', 'rain', 5],
  ['Heron Ridge: saturation lanes', 'Heron Ridge', 'Heron Ridge', 'day', 'clear', 5],
  ['Osprey Town: balloon release', 'Osprey Town', 'Osprey Town', 'dawn', 'clear', 1],
  ['Harrier Field: mixed civil traffic', 'Harrier Field', 'Heron Ridge', 'day', 'haze', 2],
]

const focusFor = (difficulty: number, tod: TimeOfDay): SkillId[] => {
  const base: SkillId[] = ['classify-rotary', 'respond-roe']
  if (difficulty >= 3) base.push('assess-intent', 'classify-fpv')
  if (tod === 'night') base.push('detect-eo')
  if (difficulty >= 4) base.push('handover')
  return base
}

export const SCENARIOS: ScenarioItem[] = rows.map(
  ([name, site, terrain, timeOfDay, weather, difficulty], i) => {
    const rng = mulberry32(9100 + i * 17)
    const mix: ScenarioItem['mix'] = { 'rotary-small': 1 + (i % 3) }
    if (difficulty >= 3) mix['fpv-small'] = 1 + (i % 2)
    if (i % 4 === 1) mix['fixed-wing-medium'] = 1
    mix.bird = 1 + (i % 4)
    if (i % 5 === 3) mix.kite = 1
    if (i % 7 === 4) mix.balloon = 1
    if (difficulty === 5) mix['rotary-small'] = 6 + (i % 4)
    return {
      id: `sc-${String(i + 1).padStart(2, '0')}`,
      name,
      site,
      terrain,
      timeOfDay,
      weather,
      difficulty,
      mix,
      durationS: 240 + difficulty * 60 + (i % 3) * 30,
      seed: 240000 + i * 937,
      origin: i % 4 === 3 || i >= 15 ? 'generated' : 'scripted',
      oracleScore: round(93.5 + rng() * 6.2, 1),
      diversity: round(0.38 + rng() * 0.5, 2),
      version: `1.${i % 4}.${i % 3}`,
      tags: [terrain === 'Heron Ridge' ? 'rural' : 'urban', timeOfDay, weather],
      focus: focusFor(difficulty, timeOfDay),
    }
  },
)

export const scenarioById = (id: string): ScenarioItem => {
  const found = SCENARIOS.find((s) => s.id === id)
  if (!found) throw new Error(`unknown scenario ${id}`)
  return found
}

/** Total contacts in a scenario's threat and clutter mix. */
export const contactCount = (scenario: ScenarioItem): number =>
  Object.values(scenario.mix).reduce((a, b) => a + (b ?? 0), 0)

export interface Curriculum {
  id: string
  name: string
  stages: { id: string; scenarioIds: string[]; gate: { minScore: number; minAccuracy: number } }[]
}

export const CURRICULA: Curriculum[] = [
  {
    id: 'cu-core',
    name: 'Core recognition course',
    stages: [
      {
        id: 'st-1',
        scenarioIds: ['sc-01', 'sc-19', 'sc-20'],
        gate: { minScore: 55, minAccuracy: 0.6 },
      },
      {
        id: 'st-2',
        scenarioIds: ['sc-02', 'sc-03', 'sc-05', 'sc-15'],
        gate: { minScore: 62, minAccuracy: 0.7 },
      },
      {
        id: 'st-3',
        scenarioIds: ['sc-04', 'sc-06', 'sc-07', 'sc-08', 'sc-09'],
        gate: { minScore: 70, minAccuracy: 0.78 },
      },
      {
        id: 'st-4',
        scenarioIds: ['sc-10', 'sc-11', 'sc-13', 'sc-14'],
        gate: { minScore: 76, minAccuracy: 0.84 },
      },
    ],
  },
  {
    id: 'cu-night',
    name: 'Night and low-visibility block',
    stages: [
      { id: 'st-1', scenarioIds: ['sc-03', 'sc-07'], gate: { minScore: 60, minAccuracy: 0.68 } },
      {
        id: 'st-2',
        scenarioIds: ['sc-08', 'sc-13', 'sc-17'],
        gate: { minScore: 72, minAccuracy: 0.8 },
      },
    ],
  },
  {
    id: 'cu-team',
    name: 'Team command exercise',
    stages: [
      { id: 'st-1', scenarioIds: ['sc-11', 'sc-12'], gate: { minScore: 68, minAccuracy: 0.75 } },
      { id: 'st-2', scenarioIds: ['sc-16', 'sc-18'], gate: { minScore: 78, minAccuracy: 0.85 } },
    ],
  },
]

/** The next-scenario recommendation for a skill vector: the scenario aimed at the weakest skills. */
export function recommend(
  skills: Record<SkillId, number>,
  exclude: string[] = [],
): { scenario: ScenarioItem; focus: SkillId[]; predicted: number }[] {
  const weakest = [...SKILLS].sort((a, b) => skills[a] - skills[b]).slice(0, 3)
  return SCENARIOS.filter((s) => !exclude.includes(s.id))
    .map((scenario) => {
      const hit = scenario.focus.filter((f) => weakest.includes(f)).length
      const level = (SKILLS.reduce((a, k) => a + skills[k], 0) / SKILLS.length) * 5
      const stretch = Math.abs(scenario.difficulty - level)
      return {
        scenario,
        focus: scenario.focus.filter((f) => weakest.includes(f)),
        predicted: round(
          Math.min(0.97, Math.max(0.35, 0.95 - stretch * 0.11 - (scenario.difficulty - 1) * 0.02)),
          2,
        ),
        rank: hit * 2 - stretch,
      }
    })
    .sort((a, b) => b.rank - a.rank)
    .slice(0, 4)
    .map(({ scenario, focus, predicted }) => ({ scenario, focus, predicted }))
}

/** Candidates for the batch generator table: seeds, difficulty, solvability and diversity. */
export function batchCandidates(seed: number, difficulty: number, count = 8) {
  const rng = mulberry32(seed)
  return Array.from({ length: count }, (_, i) => {
    const oracle = round(88 + rng() * 11.6, 1)
    const diversity = round(0.22 + rng() * 0.7, 2)
    return {
      id: `g-${seed}-${i + 1}`,
      seed: seed + i * 211,
      difficulty,
      terrain: at(['Heron Ridge', 'Osprey Town'], i + (rng() > 0.5 ? 1 : 0)),
      contacts: 5 + Math.round(rng() * 9),
      oracle,
      diversity,
      solvable: oracle >= 92,
      distinct: diversity >= 0.35,
    }
  })
}

export const CLASS_LIST = CLASSES
