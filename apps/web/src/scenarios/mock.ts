/**
 * Scripted scenario API for the dev server (`?mock=1`) and the mock specs. Deterministic fixtures,
 * no network, no clock. Nothing here is imported by production code except through the guarded
 * dynamic import in api.ts, so it is removed from production builds.
 *
 * This is a stand-in, not the engine: it recognises a handful of line patterns in the YAML text
 * (see `validateText`) and answers with fixed parsed specs. Names, sites and numbers are fictional
 * reference data.
 */
import { ApiError, NetworkError } from '../lib/api'
import type { DecodedCode, ScenarioApi } from './api'
import { heatMapFor } from './heatmap'
import {
  DIFFICULTY_AXES,
  THREAT_MIXES,
  TERRAINS,
  TIMES_OF_DAY,
  WEATHERS,
  type Archive,
  type ArchiveCell,
  type Check,
  type CheckResponse,
  type GeneratedScenario,
  type GeneratorRequest,
  type LintItem,
  type PreviewResponse,
  type ScenarioDetail,
  type ScenarioSpec,
  type ScenarioSummary,
  type ValidateResponse,
  type ValidationError,
} from './types'

// ---------------------------------------------------------------------------------------------
// The sample scenario: a YAML text and the spec the engine would parse from it.

export const SAMPLE_ID = 'marlin-hill-evening-picket'

export const SAMPLE_YAML = `contract: scenario.v1
id: ${SAMPLE_ID}
version: 1.0.0
title:
  en: "Marlin Hill: evening picket"
  hi: "मार्लिन हिल: शाम की चौकी"
summary:
  en: Two small rotary contacts close on the depot from the west while a bird flock works the north fields and a civil survey flight is filed to the south.
  hi: दो छोटे रोटरी संपर्क पश्चिम से डिपो की ओर आते हैं, जबकि उत्तर के खेतों में पक्षियों का झुंड है और दक्षिण में एक नागरिक सर्वे उड़ान दर्ज है।
fictional: true
default_seed: 260311
duration_s: 360
world:
  terrain: {kind: pack, id: heron-ridge, version: 1.0.0}
  half_extent_m: 2000
  start_time_of_day_h: 17.5
  weather: {condition: haze, visibility_m: 6200, wind_speed_mps: 4.1, wind_from_deg: 270, gust_sigma_mps: 0.8, temperature_c: 27, cloud_cover_pct: 40}
rule_pack: {id: training-baseline, version: 1.0.0}
zones:
  - {id: inner, role: inner, label: {en: Inner zone, hi: आंतरिक क्षेत्र}, center: {x: 0, y: 0, z: 34.5}, radius_m: 500}
  - {id: outer, role: outer, label: {en: Outer zone, hi: बाहरी क्षेत्र}, center: {x: 0, y: 0, z: 34.5}, radius_m: 1500}
assets:
  - {id: marlin-hill-depot, label: {en: Marlin Hill depot, hi: मार्लिन हिल डिपो}, position: {x: 0, y: 0, z: 34.5}}
sensors:
  - {id: radar-1, profile: {id: radar-generic-s, version: 0.2.0}, position: {x: -60, y: 40, z: 40.1}, boresight_deg: 0}
  - {id: eo-1, profile: {id: eo-generic-day, version: 0.1.0}, position: {x: -55, y: 45, z: 42.1}, boresight_deg: 270}
  - {id: rf-1, profile: {id: rf-generic-passive, version: 1.0.0}, position: {x: 70, y: -30, z: 37.4}, boresight_deg: 0}
groups:
  - id: grp-pair
    members: [th-quad-a, th-quad-b]
    kind: swarm
    topology: leader-follower
    leader: th-quad-a
    link_range_m: 140
    spacing_m: 40
    route:
      - {position: {x: -1500, y: 140, z: 90}, speed_mps: 13}
      - {position: {x: -420, y: 40, z: 70}, speed_mps: 11}
threats:
  - id: th-quad-a
    label: {en: Contact quad A, hi: संपर्क क्वाड A}
    class_id: autonomous-small
    disposition: hostile
    spawn_s: 46
    start: {x: -1500, y: 140, z: 90}
    start_heading_deg: 90
    start_speed_mps: 12
    on_route_end: loiter
    limits: {max_speed_mps: 18, max_accel_mps2: 4, max_turn_rate_dps: 90, max_climb_mps: 5, max_descent_mps: 5, min_altitude_m: 10, max_altitude_m: 120}
    route:
      - {position: {x: -1500, y: 140, z: 90}, speed_mps: 13}
      - {position: {x: -420, y: 40, z: 70}, speed_mps: 11}
  - id: th-quad-b
    label: {en: Contact quad B, hi: संपर्क क्वाड B}
    class_id: autonomous-small
    disposition: hostile
    spawn_s: 52
    start: {x: -1540, y: 100, z: 88}
    start_heading_deg: 90
    start_speed_mps: 12
    on_route_end: loiter
    limits: {max_speed_mps: 18, max_accel_mps2: 4, max_turn_rate_dps: 90, max_climb_mps: 5, max_descent_mps: 5, min_altitude_m: 10, max_altitude_m: 120}
    route:
      - {position: {x: -1540, y: 100, z: 88}, speed_mps: 13}
      - {position: {x: -460, y: 0, z: 70}, speed_mps: 11}
  - id: th-flock
    label: {en: Contact flock, hi: संपर्क झुंड}
    class_id: bird
    disposition: clutter
    spawn_s: 0
    start: {x: 300, y: 1100, z: 60}
    start_heading_deg: 200
    start_speed_mps: 9
    on_route_end: loop
    limits: {max_speed_mps: 14, max_accel_mps2: 6, max_turn_rate_dps: 120, max_climb_mps: 4, max_descent_mps: 6, min_altitude_m: 15, max_altitude_m: 150}
    route:
      - {position: {x: 300, y: 1100, z: 60}, speed_mps: 9}
      - {position: {x: 700, y: 900, z: 70}, speed_mps: 9}
  - id: th-survey
    label: {en: Contact survey, hi: संपर्क सर्वे}
    class_id: civil-drone
    disposition: civil-permitted
    spawn_s: 24
    start: {x: 100, y: -1300, z: 80}
    start_heading_deg: 0
    start_speed_mps: 8
    on_route_end: despawn
    limits: {max_speed_mps: 15, max_accel_mps2: 3, max_turn_rate_dps: 60, max_climb_mps: 4, max_descent_mps: 4, min_altitude_m: 20, max_altitude_m: 110}
    route:
      - {position: {x: 100, y: -1300, z: 80}, speed_mps: 8}
      - {position: {x: -200, y: -900, z: 80}, speed_mps: 8}
`

const vec = (x: number, y: number, z: number) => ({ x, y, z })
const text = (en: string, hi: string) => ({ en, hi })
const limits = (
  speed: number,
  accel: number,
  turn: number,
  climb: number,
  descent: number,
  low: number,
  high: number,
) => ({
  max_speed_mps: speed,
  max_accel_mps2: accel,
  max_turn_rate_dps: turn,
  max_climb_mps: climb,
  max_descent_mps: descent,
  min_altitude_m: low,
  max_altitude_m: high,
})

export const SAMPLE_SPEC: ScenarioSpec = {
  contract: 'scenario.v1',
  id: SAMPLE_ID,
  version: '1.0.0',
  title: text('Marlin Hill: evening picket', 'मार्लिन हिल: शाम की चौकी'),
  summary: text(
    'Two small rotary contacts close on the depot from the west while a bird flock works the north fields and a civil survey flight is filed to the south.',
    'दो छोटे रोटरी संपर्क पश्चिम से डिपो की ओर आते हैं, जबकि उत्तर के खेतों में पक्षियों का झुंड है और दक्षिण में एक नागरिक सर्वे उड़ान दर्ज है।',
  ),
  fictional: true,
  default_seed: 260311,
  duration_s: 360,
  world: {
    terrain: { kind: 'pack', id: 'heron-ridge', version: '1.0.0' },
    half_extent_m: 2000,
    start_time_of_day_h: 17.5,
    weather: {
      condition: 'haze',
      visibility_m: 6200,
      wind_speed_mps: 4.1,
      wind_from_deg: 270,
      gust_sigma_mps: 0.8,
      temperature_c: 27,
      cloud_cover_pct: 40,
    },
  },
  rule_pack: { id: 'training-baseline', version: '1.0.0' },
  zones: [
    {
      id: 'inner',
      role: 'inner',
      label: text('Inner zone', 'आंतरिक क्षेत्र'),
      center: vec(0, 0, 34.5),
      radius_m: 500,
    },
    {
      id: 'outer',
      role: 'outer',
      label: text('Outer zone', 'बाहरी क्षेत्र'),
      center: vec(0, 0, 34.5),
      radius_m: 1500,
    },
  ],
  assets: [
    {
      id: 'marlin-hill-depot',
      label: text('Marlin Hill depot', 'मार्लिन हिल डिपो'),
      position: vec(0, 0, 34.5),
    },
  ],
  sensors: [
    {
      id: 'radar-1',
      profile: { id: 'radar-generic-s', version: '0.2.0' },
      position: vec(-60, 40, 40.1),
      boresight_deg: 0,
    },
    {
      id: 'eo-1',
      profile: { id: 'eo-generic-day', version: '0.1.0' },
      position: vec(-55, 45, 42.1),
      boresight_deg: 270,
    },
    {
      id: 'rf-1',
      profile: { id: 'rf-generic-passive', version: '1.0.0' },
      position: vec(70, -30, 37.4),
      boresight_deg: 0,
    },
  ],
  groups: [
    {
      id: 'grp-pair',
      members: ['th-quad-a', 'th-quad-b'],
      kind: 'swarm',
      topology: 'leader-follower',
      leader: 'th-quad-a',
      link_range_m: 140,
      spacing_m: 40,
      route: [
        { position: vec(-1500, 140, 90), speed_mps: 13 },
        { position: vec(-420, 40, 70), speed_mps: 11 },
      ],
    },
  ],
  threats: [
    {
      id: 'th-quad-a',
      label: text('Contact quad A', 'संपर्क क्वाड A'),
      class_id: 'autonomous-small',
      disposition: 'hostile',
      spawn_s: 46,
      start: vec(-1500, 140, 90),
      start_heading_deg: 90,
      start_speed_mps: 12,
      on_route_end: 'loiter',
      limits: limits(18, 4, 90, 5, 5, 10, 120),
      route: [
        { position: vec(-1500, 140, 90), speed_mps: 13 },
        { position: vec(-420, 40, 70), speed_mps: 11 },
      ],
    },
    {
      id: 'th-quad-b',
      label: text('Contact quad B', 'संपर्क क्वाड B'),
      class_id: 'autonomous-small',
      disposition: 'hostile',
      spawn_s: 52,
      start: vec(-1540, 100, 88),
      start_heading_deg: 90,
      start_speed_mps: 12,
      on_route_end: 'loiter',
      limits: limits(18, 4, 90, 5, 5, 10, 120),
      route: [
        { position: vec(-1540, 100, 88), speed_mps: 13 },
        { position: vec(-460, 0, 70), speed_mps: 11 },
      ],
    },
    {
      id: 'th-flock',
      label: text('Contact flock', 'संपर्क झुंड'),
      class_id: 'bird',
      disposition: 'clutter',
      spawn_s: 0,
      start: vec(300, 1100, 60),
      start_heading_deg: 200,
      start_speed_mps: 9,
      on_route_end: 'loop',
      limits: limits(14, 6, 120, 4, 6, 15, 150),
      route: [
        { position: vec(300, 1100, 60), speed_mps: 9 },
        { position: vec(700, 900, 70), speed_mps: 9 },
      ],
    },
    {
      id: 'th-survey',
      label: text('Contact survey', 'संपर्क सर्वे'),
      class_id: 'civil-drone',
      disposition: 'civil-permitted',
      spawn_s: 24,
      start: vec(100, -1300, 80),
      start_heading_deg: 0,
      start_speed_mps: 8,
      on_route_end: 'despawn',
      limits: limits(15, 3, 60, 4, 4, 20, 110),
      route: [
        { position: vec(100, -1300, 80), speed_mps: 8 },
        { position: vec(-200, -900, 80), speed_mps: 8 },
      ],
    },
  ],
}

/** The sample with two errors the contract reports, each on its own line. */
export const SAMPLE_YAML_ERRORS = SAMPLE_YAML.replace(
  'duration_s: 360',
  'duration_s: soon',
).replace('  - id: th-quad-b\n', '\t- id: th-quad-b\n')

/** The sample with a threat timed before the reaction window and a group link too short. */
export const SAMPLE_YAML_LINT = SAMPLE_YAML.replace('spawn_s: 46', 'spawn_s: 12').replace(
  'link_range_m: 140',
  'link_range_m: 30',
)

const MIN_REACTION_S = 20

/** Mock of validate: the contract and lint rules the fixtures need, found by line pattern. */
export function validateText(yaml: string): ValidateResponse {
  const lines = yaml.split('\n')
  const errors: ValidationError[] = []
  if (yaml.trim() === '') {
    return {
      valid: false,
      errors: [
        {
          line: 1,
          column: 1,
          path: '',
          message: 'The document is empty.',
          code: 'yaml.empty',
        },
      ],
      lint: [],
      spec: null,
    }
  }
  lines.forEach((line, i) => {
    if (/^\t/.test(line)) {
      errors.push({
        line: i + 1,
        column: 1,
        path: '',
        message: 'Found a tab character where indentation is expected.',
        code: 'yaml.tab',
      })
    }
  })
  const contract = lines.findIndex((line) => /^contract:/.test(line))
  if (contract < 0) {
    errors.push({
      line: 1,
      column: 1,
      path: 'contract',
      message: 'Field required: contract.',
      code: 'contract.missing',
    })
  } else if (!/^contract:\s*scenario\.v1\s*$/.test(lines[contract] ?? '')) {
    errors.push({
      line: contract + 1,
      column: 11,
      path: 'contract',
      message: "Input should be 'scenario.v1'.",
      code: 'contract.version',
    })
  }
  const duration = lines.findIndex((line) => /^duration_s:/.test(line))
  if (duration >= 0 && !/^duration_s:\s*\d+(\.\d+)?\s*$/.test(lines[duration] ?? '')) {
    errors.push({
      line: duration + 1,
      column: 13,
      path: 'duration_s',
      message: 'Input should be a valid number.',
      code: 'schema.type',
    })
  }
  errors.sort((a, b) => a.line - b.line)
  if (errors.length > 0) return { valid: false, errors, lint: [], spec: null }

  const lint: LintItem[] = []
  lines.forEach((line, i) => {
    const spawn = /^\s*spawn_s:\s*(\d+(?:\.\d+)?)/.exec(line)
    const spawnS = spawn ? Number(spawn[1]) : null
    if (spawnS !== null && spawnS > 0 && spawnS < MIN_REACTION_S) {
      lint.push({
        code: 'timing.reaction-window',
        severity: 'error',
        line: i + 1,
        column: line.indexOf('spawn_s') + 1,
        message: `Threat reaches the inner zone ${spawnS} s after it can be detected; the rule pack needs ${MIN_REACTION_S} s.`,
        params: { spawn_s: spawnS, minimum_s: MIN_REACTION_S },
      })
    }
    const link = /^\s*link_range_m:\s*(\d+(?:\.\d+)?)/.exec(line)
    if (link && Number(link[1]) < 80) {
      lint.push({
        code: 'group.link-range',
        severity: 'warning',
        line: i + 1,
        column: line.indexOf('link_range_m') + 1,
        message: `Group link range ${link[1]} m does not cover the 40 m formation spacing of the whole group.`,
        params: { link_range_m: Number(link[1]) },
      })
    }
  })
  return { valid: true, errors: [], lint, spec: structuredClone(SAMPLE_SPEC) }
}

// ---------------------------------------------------------------------------------------------
// Library fixtures: 14 rows, every origin, solvability status, terrain and time of day.

interface RowSeed {
  id: string
  en: string
  hi: string
  origin: ScenarioSummary['origin']
  order?: number
  difficulty: number | null
  terrain: ScenarioSummary['terrain']
  time: ScenarioSummary['time_of_day']
  weather: string
  duration: number
  hostile: number
  contacts: number
  sensors: number
  degraded?: boolean
  groups?: number
  tags: string[]
  status: ScenarioSummary['solvability']['status']
  score: number | null
}

const SEEDS: RowSeed[] = [
  {
    id: 'curriculum-01-first-light',
    en: 'First light: one rotary, two sensors',
    hi: 'पहली किरण: एक रोटरी, दो सेंसर',
    origin: 'scripted',
    order: 1,
    difficulty: 1,
    terrain: 'flat',
    time: 'dawn',
    weather: 'clear',
    duration: 288,
    hostile: 1,
    contacts: 1,
    sensors: 2,
    tags: ['curriculum', 'single', 'day-night'],
    status: 'verified',
    score: 0.97,
  },
  {
    id: 'curriculum-02-bird-or-drone',
    en: 'Bird or drone: telling the flock apart',
    hi: 'पक्षी या ड्रोन: झुंड से अंतर',
    origin: 'scripted',
    order: 2,
    difficulty: 2,
    terrain: 'flat',
    time: 'day',
    weather: 'clear',
    duration: 342,
    hostile: 1,
    contacts: 3,
    sensors: 3,
    tags: ['curriculum', 'single', 'clutter'],
    status: 'verified',
    score: 0.94,
  },
  {
    id: 'curriculum-03-ridge-low-approach',
    en: 'Ridge shadow: low approach from the south-west',
    hi: 'रिज की ओट: दक्षिण-पश्चिम से नीची उड़ान',
    origin: 'scripted',
    order: 3,
    difficulty: 3,
    terrain: 'heron-ridge',
    time: 'dusk',
    weather: 'haze',
    duration: 411,
    hostile: 1,
    contacts: 4,
    sensors: 3,
    tags: ['curriculum', 'rural', 'single'],
    status: 'verified',
    score: 0.91,
  },
  {
    id: 'curriculum-04-night-with-a-dead-radar',
    en: 'Night watch with the radar in outage',
    hi: 'रात की निगरानी, रडार बंद',
    origin: 'scripted',
    order: 4,
    difficulty: 4,
    terrain: 'flat',
    time: 'night',
    weather: 'clear',
    duration: 377,
    hostile: 2,
    contacts: 5,
    sensors: 3,
    degraded: true,
    tags: ['curriculum', 'night', 'degraded'],
    status: 'verified',
    score: 0.88,
  },
  {
    id: 'curriculum-05-town-edge-swarm',
    en: 'Town edge: a swarm of eight in rain',
    hi: 'शहर का किनारा: वर्षा में आठ का झुंड',
    origin: 'scripted',
    order: 5,
    difficulty: 5,
    terrain: 'osprey-town',
    time: 'day',
    weather: 'rain',
    duration: 468,
    hostile: 8,
    contacts: 11,
    sensors: 4,
    degraded: true,
    groups: 1,
    tags: ['curriculum', 'urban', 'swarm'],
    status: 'verified',
    score: 0.84,
  },
  {
    id: 'gen-48213907-a1f3c2',
    en: 'Generated 48213907: ridge, mid-day, three contacts',
    hi: 'उत्पन्न 48213907: रिज, दोपहर, तीन संपर्क',
    origin: 'generated',
    difficulty: 3,
    terrain: 'heron-ridge',
    time: 'day',
    weather: 'clear',
    duration: 396,
    hostile: 3,
    contacts: 5,
    sensors: 4,
    tags: ['generated'],
    status: 'verified',
    score: 0.92,
  },
  {
    id: 'gen-77120045-9be4d0',
    en: 'Generated 77120045: town, night fog, silent raid',
    hi: 'उत्पन्न 77120045: शहर, रात का कोहरा, मौन हमला',
    origin: 'generated',
    difficulty: 6,
    terrain: 'osprey-town',
    time: 'night',
    weather: 'fog',
    duration: 433,
    hostile: 6,
    contacts: 9,
    sensors: 4,
    degraded: true,
    groups: 2,
    tags: ['generated', 'night'],
    status: 'verified',
    score: 0.81,
  },
  {
    id: 'gen-90814422-d27e18',
    en: 'Generated 90814422: dawn haze, decoys among twelve',
    hi: 'उत्पन्न 90814422: भोर की धुंध, बारह में डिकॉय',
    origin: 'generated',
    difficulty: 7,
    terrain: 'heron-ridge',
    time: 'dawn',
    weather: 'haze',
    duration: 452,
    hostile: 12,
    contacts: 17,
    sensors: 4,
    degraded: true,
    groups: 2,
    tags: ['generated', 'swarm'],
    status: 'verified',
    score: 0.79,
  },
  {
    id: 'gen-30561188-0c7a55',
    en: 'Generated 30561188: dusk dust, fast mover',
    hi: 'उत्पन्न 30561188: साँझ की धूल, तेज़ संपर्क',
    origin: 'generated',
    difficulty: 4,
    terrain: 'flat',
    time: 'dusk',
    weather: 'dust',
    duration: 301,
    hostile: 2,
    contacts: 3,
    sensors: 3,
    tags: ['generated'],
    status: 'verified',
    score: 0.9,
  },
  {
    id: 'auth-ridge-picket-drill',
    en: 'Ridge picket drill (instructor draft)',
    hi: 'रिज पिकेट अभ्यास (प्रशिक्षक का मसौदा)',
    origin: 'authored',
    difficulty: 3,
    terrain: 'heron-ridge',
    time: 'day',
    weather: 'clear',
    duration: 322,
    hostile: 2,
    contacts: 4,
    sensors: 2,
    tags: ['draft', 'rural'],
    status: 'failed',
    score: 0.38,
  },
  {
    id: 'auth-depot-night-fpv',
    en: 'Depot night, fast FPV pass',
    hi: 'डिपो की रात, तेज़ एफपीवी उड़ान',
    origin: 'authored',
    difficulty: null,
    terrain: 'flat',
    time: 'night',
    weather: 'clear',
    duration: 264,
    hostile: 1,
    contacts: 2,
    sensors: 3,
    tags: ['draft', 'night'],
    status: 'unchecked',
    score: null,
  },
  {
    id: SAMPLE_ID,
    en: 'Marlin Hill: evening picket',
    hi: 'मार्लिन हिल: शाम की चौकी',
    origin: 'authored',
    difficulty: 4,
    terrain: 'heron-ridge',
    time: 'dusk',
    weather: 'haze',
    duration: 360,
    hostile: 2,
    contacts: 4,
    sensors: 3,
    groups: 1,
    tags: ['rural', 'pair'],
    status: 'verified',
    score: 0.92,
  },
  {
    id: 'example-minimal-single',
    en: 'Example: the smallest valid scenario',
    hi: 'उदाहरण: सबसे छोटा मान्य परिदृश्य',
    origin: 'example',
    difficulty: 1,
    terrain: 'flat',
    time: 'day',
    weather: 'clear',
    duration: 180,
    hostile: 1,
    contacts: 1,
    sensors: 1,
    tags: ['example'],
    status: 'verified',
    score: 0.96,
  },
  {
    id: 'example-two-sensor-night',
    en: 'Example: two sensors at night in fog',
    hi: 'उदाहरण: कोहरे में रात को दो सेंसर',
    origin: 'example',
    difficulty: 2,
    terrain: 'flat',
    time: 'night',
    weather: 'fog',
    duration: 240,
    hostile: 1,
    contacts: 2,
    sensors: 2,
    degraded: true,
    tags: ['example', 'night'],
    status: 'unchecked',
    score: null,
  },
]

const summaryOf = (seed: RowSeed): ScenarioSummary => ({
  id: seed.id,
  version: '1.0.0',
  title: { en: seed.en, hi: seed.hi },
  summary: {
    en: `${seed.en}. Fictional site, reference data.`,
    hi: `${seed.hi}। काल्पनिक स्थल, संदर्भ डेटा।`,
  },
  origin: seed.origin,
  playable: true,
  tags: seed.tags,
  curriculum_order: seed.order ?? null,
  difficulty: seed.difficulty,
  terrain: seed.terrain,
  time_of_day: seed.time,
  weather: seed.weather,
  duration_s: seed.duration,
  hostile_count: seed.hostile,
  contact_count: seed.contacts,
  sensor_count: seed.sensors,
  degraded: seed.degraded ?? false,
  group_count: seed.groups ?? 0,
  rule_pack: { id: 'training-baseline', version: '1.0.0' },
  solvability: {
    status: seed.status,
    oracle_score: seed.score,
    checked_at_run: seed.status === 'unchecked' ? null : 'oracle-defender run, 2026-10-14',
  },
  can_delete: seed.origin === 'generated' || seed.origin === 'authored',
})

export const MOCK_LIBRARY: ScenarioSummary[] = SEEDS.map(summaryOf)

// ---------------------------------------------------------------------------------------------
// Checks, diversity, features, preview

export const SOLVED_CHECKS: Check[] = [
  {
    name: 'hostile-presented',
    passed: true,
    value: '2 of 2',
    detail: 'Every hostile contact was reported by a sensor.',
    code: 'solvability.presented',
  },
  {
    name: 'hostile-answered',
    passed: true,
    value: '2 of 2',
    detail: 'Every hostile contact was engaged under the rules.',
    code: 'solvability.answered',
  },
  {
    name: 'no-failures',
    passed: true,
    value: 0,
    detail: 'No hard fail, blocked attempt, false engagement or unfixed track error.',
    code: 'solvability.failures',
  },
  {
    name: 'oracle-score',
    passed: true,
    value: 0.92,
    detail: 'Lowest hostile contact score 92.0%, bar 80%.',
    code: 'solvability.score',
  },
]

export const FAILED_CHECKS: Check[] = SOLVED_CHECKS.map((check) =>
  check.name === 'hostile-answered'
    ? {
        ...check,
        passed: false,
        value: '1 of 2',
        detail: 'One hostile contact was never engaged under the rules.',
      }
    : check.name === 'oracle-score'
      ? {
          ...check,
          passed: false,
          value: 0.38,
          detail: 'Lowest hostile contact score 38.0%, bar 80%.',
        }
      : check,
)

const FEATURES = {
  threat_count: 0.3,
  id_ambiguity: 0.5,
  approach_speed: 0.31,
  bearing_spread: 0.12,
  clutter_density: 0.05,
  degradation_load: 0.18,
  timing_tightness: 0.84,
  stealth: 0,
}

export function checkText(yaml: string, seed?: number): CheckResponse {
  const v = validateText(yaml)
  const blocked = !v.valid || v.lint.some((item) => item.severity === 'error')
  const solvedChecks = seed !== undefined && seed % 7 === 0 ? FAILED_CHECKS : SOLVED_CHECKS
  const solved = !blocked && solvedChecks === SOLVED_CHECKS
  return {
    valid: v.valid,
    errors: v.errors,
    lint: v.lint,
    solvability: {
      ran: !blocked,
      solved,
      oracle_score: blocked ? null : solved ? 0.92 : 0.38,
      checks: blocked ? [] : structuredClone(solvedChecks),
      seconds: blocked ? 0 : 0.64,
      wording: solved ? 'verified solvable by test run' : 'not verified solvable',
    },
    diversity: {
      history_size: blocked ? 0 : 7,
      novelty: blocked ? null : 0.31,
      threshold: 0.15,
      passes: blocked ? null : true,
      nearest: blocked
        ? []
        : [
            { scenario_id: 'curriculum-03-ridge-low-approach', distance: 0.31 },
            { scenario_id: 'gen-48213907-a1f3c2', distance: 0.37 },
            { scenario_id: 'curriculum-02-bird-or-drone', distance: 0.44 },
          ],
    },
    features: blocked ? {} : { ...FEATURES },
  }
}

function pathFor(
  route: { x: number; y: number; z: number }[],
  steps: number,
): [number, number, number][] {
  const out: [number, number, number][] = []
  const first = route[0]
  const last = route[route.length - 1]
  if (!first || !last) return out
  for (let i = 0; i < steps; i++) {
    const f = i / (steps - 1)
    const bend = Math.sin(f * Math.PI) * 38
    out.push([
      Math.round((first.x + (last.x - first.x) * f) * 10) / 10,
      Math.round((first.y + (last.y - first.y) * f + bend) * 10) / 10,
      Math.round((first.z + (last.z - first.z) * f) * 10) / 10,
    ])
  }
  return out
}

export function previewText(yaml: string): PreviewResponse {
  const v = validateText(yaml)
  const spec = v.spec
  if (!v.valid || !spec) {
    return {
      ok: false,
      finished_s: 0,
      oracle_score: null,
      contacts: [],
      path: { step_s: 2, threats: [] },
      coverage: [],
    }
  }
  const moving = spec.threats.filter((t) => t.disposition !== 'clutter')
  return {
    ok: true,
    finished_s: 214.5,
    oracle_score: 0.92,
    contacts: [
      {
        id: 'th-quad-a',
        label: 'Contact quad A',
        disposition: 'hostile',
        class_id: 'autonomous-small',
        first_report_s: 61.4,
        answered_s: 118.2,
        score: 0.95,
      },
      {
        id: 'th-quad-b',
        label: 'Contact quad B',
        disposition: 'hostile',
        class_id: 'autonomous-small',
        first_report_s: 66.8,
        answered_s: 124.6,
        score: 0.92,
      },
      {
        id: 'th-survey',
        label: 'Contact survey',
        disposition: 'civil-permitted',
        class_id: 'civil-drone',
        first_report_s: 31.2,
        answered_s: null,
        score: null,
      },
    ],
    path: {
      step_s: 2,
      threats: moving.map((threat) => ({
        id: threat.id,
        points: pathFor(
          threat.route.map((w) => w.position),
          threat.disposition === 'hostile' ? 48 : 24,
        ),
      })),
    },
    coverage: [
      { threat_id: 'th-quad-a', first_s: 61.4, sensors: ['radar-1', 'eo-1', 'rf-1'] },
      { threat_id: 'th-quad-b', first_s: 66.8, sensors: ['radar-1', 'rf-1'] },
      { threat_id: 'th-survey', first_s: 31.2, sensors: ['radar-1'] },
    ],
  }
}

// ---------------------------------------------------------------------------------------------
// Share codes: reversible, 4-character groups after the version tag. Not the engine's format.

const B36 = (n: number, width: number) => n.toString(36).toUpperCase().padStart(width, '0')

export function encodeRequest(request: GeneratorRequest): string {
  const mix = THREAT_MIXES.reduce(
    (m, id, i) => (request.threat_mix.includes(id) ? m | (1 << i) : m),
    0,
  )
  const body =
    B36(request.seed, 7) +
    B36(TERRAINS.indexOf(request.terrain), 1) +
    B36(TIMES_OF_DAY.indexOf(request.time_of_day), 1) +
    B36(WEATHERS.indexOf(request.weather as (typeof WEATHERS)[number]), 1) +
    DIFFICULTY_AXES.map((axis) => B36(request.difficulty[axis], 2)).join('') +
    B36(mix, 2) +
    B36(request.oracle_min_score, 2) +
    B36(request.max_attempts, 2)
  return `SD1-${body.match(/.{1,4}/g)?.join('-') ?? body}`
}

export function decodeCode(code: string): DecodedCode {
  const match = /^SD1-([0-9A-Z-]+)$/.exec(code.trim().toUpperCase())
  const body = match?.[1]?.replaceAll('-', '') ?? ''
  if (body.length !== 7 + 3 + 10 + 6) throw new ApiError(422, 'The share code is not valid.')
  let at = 0
  const take = (n: number) => parseInt(body.slice(at, (at += n)), 36)
  const seed = take(7)
  const terrain = TERRAINS[take(1)]
  const time = TIMES_OF_DAY[take(1)]
  const weather = WEATHERS[take(1)]
  const difficulty = Object.fromEntries(DIFFICULTY_AXES.map((axis) => [axis, take(2)])) as Record<
    (typeof DIFFICULTY_AXES)[number],
    number
  >
  const mix = take(2)
  const oracle = take(2)
  const attempts = take(2)
  if (!terrain || !time || !weather) throw new ApiError(422, 'The share code is not valid.')
  return {
    request: {
      seed,
      terrain,
      time_of_day: time,
      weather,
      difficulty,
      threat_mix: THREAT_MIXES.filter((_, i) => (mix & (1 << i)) !== 0),
      oracle_min_score: oracle,
      max_attempts: attempts,
    },
    generator_version: '1.0.0',
  }
}

// ---------------------------------------------------------------------------------------------
// Generator

const hex = (n: number, width: number) => (n >>> 0).toString(16).padStart(width, '0').slice(-width)

function hashOf(text: string): number {
  let h = 2166136261
  for (let i = 0; i < text.length; i++) h = Math.imul(h ^ text.charCodeAt(i), 16777619)
  return h >>> 0
}

export function generateFrom(request: GeneratorRequest, save: boolean): GeneratedScenario {
  const h = hashOf(JSON.stringify(request))
  const id = `gen-${request.seed}-${hex(h, 6)}`
  const d = request.difficulty
  const mean = (d.threat_load + d.ambiguity + d.speed + d.stealth + d.degradation) / 500
  const relaxed = request.oracle_min_score > 90 && request.seed % 2 === 1
  const score = Math.min(0.99, Math.max(request.oracle_min_score / 100, 0.78 + (h % 17) / 100))
  const checks = structuredClone(SOLVED_CHECKS).map((check) =>
    check.name === 'oracle-score'
      ? {
          ...check,
          value: Math.round(score * 1000) / 1000,
          detail: `Lowest hostile contact score ${(score * 100).toFixed(1)}%, bar ${request.oracle_min_score}%.`,
        }
      : check,
  )
  const spec: ScenarioSpec = {
    ...structuredClone(SAMPLE_SPEC),
    id,
    title: text(`Generated ${request.seed}`, `उत्पन्न ${request.seed}`),
    default_seed: request.seed,
  }
  return {
    id,
    spec,
    yaml: SAMPLE_YAML.replace(`id: ${SAMPLE_ID}`, `id: ${id}`),
    code: encodeRequest(request),
    generator_version: '1.0.0',
    request,
    attempts: relaxed ? 14 : 1 + (h % 4),
    relaxations: relaxed ? ['diversity threshold halved after 12 attempts'] : [],
    checks,
    solvability_wording: 'verified solvable by test run',
    features: {
      threat_count: Math.min(1, 0.1 + d.threat_load / 140),
      id_ambiguity: Math.min(1, d.ambiguity / 120),
      approach_speed: Math.min(1, 0.2 + d.speed / 160),
      bearing_spread: 0.12 + mean / 2,
      clutter_density: d.ambiguity / 400,
      degradation_load: d.degradation / 160,
      timing_tightness: 0.55 + mean / 3,
      stealth: d.stealth / 130,
    },
    diversity: {
      history_size: 7,
      novelty: Math.round((0.18 + ((h >>> 8) % 40) / 100) * 100) / 100,
      threshold: relaxed ? 0.075 : 0.15,
      passes: true,
    },
    spec_sha256: hex(h, 8).repeat(8),
    saved: save,
  }
}

// ---------------------------------------------------------------------------------------------
// Archive: a plausible filled 6 x 6 x 4 grid. Quality is the oracle's lowest hostile score.

const AXES = [
  {
    name: 'threat_count',
    bins: 6,
    labels: ['1', '2', '3 to 4', '5 to 8', '9 to 15', '16 or more'],
  },
  {
    name: 'id_ambiguity',
    bins: 6,
    labels: ['under 10%', '10 to 25%', '25 to 40%', '40 to 55%', '55 to 70%', '70% or more'],
  },
  {
    name: 'approach_speed',
    bins: 4,
    labels: ['under 10 m/s', '10 to 20 m/s', '20 to 30 m/s', '30 m/s or more'],
  },
]

export function mockArchive(): Archive {
  const cells: ArchiveCell[] = []
  for (let i = 0; i < 6; i++)
    for (let j = 0; j < 6; j++)
      for (let k = 0; k < 4; k++) {
        const h = hashOf(`cell-${i}-${j}-${k}`)
        // The archive fills toward few threats and low ambiguity first, as a real run would.
        const reach = 0.95 - (i * 0.1 + j * 0.07 + k * 0.05)
        if ((h % 100) / 100 > reach) continue
        cells.push({
          index: [i, j, k],
          quality: Math.round((0.62 + ((h >>> 7) % 37) / 100) * 1000) / 1000,
          scenario_id: `gen-${10000000 + (h % 89999999)}-${hex(h, 6)}`,
        })
      }
  const filled = cells.length
  const qd = cells.reduce((sum, cell) => sum + cell.quality, 0)
  let pair = 0
  let pairs = 0
  const centre = (cell: ArchiveCell) => cell.index.map((v, a) => (v + 0.5) / (AXES[a]?.bins ?? 1))
  for (let a = 0; a < cells.length; a++)
    for (let b = a + 1; b < cells.length; b++) {
      const ca = centre(cells[a]!)
      const cb = centre(cells[b]!)
      pair += Math.hypot(...ca.map((v, n) => v - (cb[n] ?? 0))) / Math.sqrt(8)
      pairs += 1
    }
  const archive: Archive = {
    axes: AXES,
    cells,
    metrics: {
      coverage: filled / 144,
      qd_score: Math.round(qd * 1000) / 1000,
      mean_pairwise_distance: pairs === 0 ? 0 : Math.round((pair / pairs) * 1000) / 1000,
      filled,
      total: 144,
    },
    heatmap: { x_axis: 'threat_count', y_axis: 'id_ambiguity', values: [] },
  }
  archive.heatmap.values = heatMapFor(archive, 0, 1).cells.map((row) => row.map((c) => c.quality))
  return archive
}

export function emptyArchive(): Archive {
  const archive: Archive = {
    axes: AXES,
    cells: [],
    metrics: { coverage: 0, qd_score: 0, mean_pairwise_distance: 0, filled: 0, total: 144 },
    heatmap: { x_axis: 'threat_count', y_axis: 'id_ambiguity', values: [] },
  }
  archive.heatmap.values = heatMapFor(archive, 0, 1).cells.map((row) => row.map((c) => c.quality))
  return archive
}

// ---------------------------------------------------------------------------------------------
// The backend

export type Variant = 'ok' | 'empty' | 'error' | 'offline' | 'slow'

export const variantOf = (search: string): Variant => {
  const value = new URLSearchParams(search).get('scn')
  return value === 'empty' || value === 'error' || value === 'offline' || value === 'slow'
    ? value
    : 'ok'
}

const delay = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms))

export function createMockBackend(variant: Variant = 'ok', slowMs = 3000): ScenarioApi {
  let library = variant === 'empty' ? [] : structuredClone(MOCK_LIBRARY)
  const saved = new Map<string, string>()
  const guard = async () => {
    if (variant === 'offline') throw new NetworkError('server unreachable')
    if (variant === 'error') throw new ApiError(500, 'Internal Server Error')
    if (variant === 'slow') await delay(slowMs)
  }
  return {
    async list() {
      await guard()
      return structuredClone(library)
    },
    async get(id) {
      await guard()
      const row = library.find((r) => r.id === id)
      if (!row) throw new ApiError(404, 'scenario not found')
      const yaml = saved.get(id) ?? SAMPLE_YAML.replace(`id: ${SAMPLE_ID}`, `id: ${id}`)
      const spec = { ...structuredClone(SAMPLE_SPEC), id }
      return {
        ...structuredClone(row),
        spec,
        yaml,
        lint: validateText(yaml).lint,
        checks:
          row.solvability.status === 'failed'
            ? FAILED_CHECKS
            : row.solvability.status === 'verified'
              ? SOLVED_CHECKS
              : [],
      } satisfies ScenarioDetail
    },
    async validate(yaml) {
      await guard()
      return validateText(yaml)
    },
    async check(yaml, seed) {
      await guard()
      return checkText(yaml, seed)
    },
    async preview(yaml) {
      await guard()
      return previewText(yaml)
    },
    async save(body) {
      await guard()
      const v = validateText(body.yaml)
      if (!v.valid || !v.spec) throw new ApiError(422, 'The scenario does not validate.')
      const id = /^id:\s*(\S+)/m.exec(body.yaml)?.[1] ?? SAMPLE_ID
      const row: ScenarioSummary = {
        ...summaryOf({
          ...(SEEDS.find((s) => s.id === SAMPLE_ID) as RowSeed),
          id,
          status: 'unchecked',
          score: null,
          tags: body.tags ?? [],
        }),
        title: v.spec.title,
      }
      library = [row, ...library.filter((r) => r.id !== id)]
      saved.set(id, body.yaml)
      return structuredClone(row)
    },
    async remove(id) {
      await guard()
      const row = library.find((r) => r.id === id)
      if (!row) throw new ApiError(404, 'scenario not found')
      if (!row.can_delete) throw new ApiError(403, 'only saved scenarios can be deleted')
      library = library.filter((r) => r.id !== id)
    },
    async generate(body) {
      await guard()
      const request = body.code ? decodeCode(body.code).request : body.request
      if (!request) throw new ApiError(422, 'send a request or a code')
      return generateFrom(request, body.save === true)
    },
    async batch(body) {
      await guard()
      return Array.from({ length: Math.max(1, Math.min(12, body.count)) }, (_, i) =>
        generateFrom({ ...body.request, seed: body.request.seed + i }, body.save === true),
      )
    },
    async archive() {
      await guard()
      return variant === 'empty' ? emptyArchive() : mockArchive()
    },
    async decode(code) {
      await guard()
      return decodeCode(code)
    },
    async encode(request) {
      await guard()
      return encodeRequest(request)
    },
  }
}

const backends = new Map<Variant, ScenarioApi>()

/** One backend per variant for the page's lifetime, so a save or delete survives navigation. */
export function mockBackend(search: string): ScenarioApi {
  const variant = variantOf(search)
  let backend = backends.get(variant)
  if (!backend) {
    backend = createMockBackend(variant)
    backends.set(variant, backend)
  }
  return backend
}
