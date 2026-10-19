/**
 * Shapes of the scenario-engine API (docs/SCENARIO_ENGINE.md, "Shapes"), written by hand.
 * Server text for people is {en, hi} where it comes from a pack; where the engine writes it
 * there is an English `message` and a stable `code` that the web app renders through its catalogue.
 */
import type { ScenarioSpec } from '../contracts/scenario.v1'

export type { ScenarioSpec }

export interface LocalisedText {
  en: string
  hi: string
}

export type Origin = 'scripted' | 'generated' | 'authored' | 'example'
export const ORIGINS: readonly Origin[] = ['scripted', 'generated', 'authored', 'example']

export type TerrainId = 'flat' | 'heron-ridge' | 'osprey-town'
export const TERRAINS: readonly TerrainId[] = ['flat', 'heron-ridge', 'osprey-town']

export type TimeOfDay = 'dawn' | 'day' | 'dusk' | 'night'
export const TIMES_OF_DAY: readonly TimeOfDay[] = ['dawn', 'day', 'dusk', 'night']

export const WEATHERS = ['clear', 'haze', 'rain', 'fog', 'dust'] as const
export type WeatherId = (typeof WEATHERS)[number]

export type SolvabilityStatus = 'verified' | 'failed' | 'unchecked'

export interface ScenarioSummary {
  id: string
  version: string
  title: LocalisedText
  summary: LocalisedText
  origin: Origin
  playable: boolean
  tags: string[]
  curriculum_order: number | null
  difficulty: number | null
  terrain: TerrainId
  time_of_day: TimeOfDay
  weather: string
  duration_s: number
  hostile_count: number
  contact_count: number
  sensor_count: number
  degraded: boolean
  group_count: number
  rule_pack: { id: string; version: string }
  solvability: {
    status: SolvabilityStatus
    /** Lowest hostile contact score, 0..1. */
    oracle_score: number | null
    checked_at_run: string | null
  }
  /** Saved scenarios only. */
  can_delete: boolean
}

/** One scenario of the library with its text, as `GET /scenario-library/{id}` returns it. */
export interface ScenarioDetail extends ScenarioSummary {
  spec: ScenarioSpec
  yaml: string
  lint: LintItem[]
  checks: Check[]
}

export interface Check {
  name: string
  passed: boolean
  value: number | string | null
  detail: string
  /** solvability.presented | solvability.answered | solvability.failures | solvability.score */
  code: string
}

export type Severity = 'error' | 'warning'

export interface LintItem {
  code: string
  severity: Severity
  line: number
  column: number
  /** English text written by the engine; the web app prefers its own catalogue entry for `code`. */
  message: string
  params: Record<string, string | number | boolean | null>
}

export interface ValidationError {
  line: number
  column: number
  path: string
  message: string
  code: string
}

export interface ValidateResponse {
  valid: boolean
  errors: ValidationError[]
  lint: LintItem[]
  spec: ScenarioSpec | null
}

export type SolvabilityWording = 'verified solvable by test run' | 'not verified solvable'

export interface DiversityResult {
  history_size: number
  novelty: number | null
  threshold: number
  passes: boolean | null
  nearest: { scenario_id: string; distance: number }[]
}

export type FeatureVector = Record<string, number>

export interface CheckResponse {
  valid: boolean
  errors: ValidationError[]
  lint: LintItem[]
  solvability: {
    ran: boolean
    solved: boolean
    oracle_score: number | null
    checks: Check[]
    seconds: number
    wording: SolvabilityWording
  }
  diversity: DiversityResult
  features: FeatureVector
}

export interface PreviewContact {
  id: string
  label: string
  disposition: string
  class_id: string
  first_report_s: number | null
  answered_s: number | null
  score: number | null
}

export interface PreviewResponse {
  ok: boolean
  finished_s: number
  oracle_score: number | null
  contacts: PreviewContact[]
  /** Truth positions, instructor only. */
  path: { step_s: number; threats: { id: string; points: [number, number, number][] }[] }
  coverage: { threat_id: string; first_s: number | null; sensors: string[] }[]
}

export const THREAT_MIXES = [
  'single',
  'swarm',
  'fast-mover',
  'fixed-wing',
  'decoy-mix',
  'silent-raid',
] as const
export type ThreatMix = (typeof THREAT_MIXES)[number]

export const DIFFICULTY_AXES = [
  'threat_load',
  'ambiguity',
  'speed',
  'stealth',
  'degradation',
] as const
export type DifficultyAxis = (typeof DIFFICULTY_AXES)[number]

export interface GeneratorRequest {
  seed: number
  terrain: TerrainId
  time_of_day: TimeOfDay
  weather: string
  difficulty: Record<DifficultyAxis, number>
  threat_mix: ThreatMix[]
  oracle_min_score: number
  max_attempts: number
}

export interface GeneratedScenario {
  id: string
  spec: ScenarioSpec
  yaml: string
  code: string
  generator_version: string
  request: GeneratorRequest
  attempts: number
  relaxations: string[]
  checks: Check[]
  solvability_wording: 'verified solvable by test run'
  features: FeatureVector
  diversity: {
    history_size: number
    novelty: number | null
    threshold: number
    passes: boolean | null
  }
  spec_sha256: string
  saved: boolean
}

export interface ArchiveAxis {
  name: string
  bins: number
  labels: string[]
}

export interface ArchiveCell {
  index: [number, number, number]
  quality: number
  scenario_id: string
}

export interface Archive {
  axes: ArchiveAxis[]
  cells: ArchiveCell[]
  metrics: {
    coverage: number
    qd_score: number
    mean_pairwise_distance: number
    filled: number
    total: number
  }
  heatmap: { x_axis: string; y_axis: string; values: (number | null)[][] }
}

export interface SaveScenarioBody {
  yaml: string
  tags?: string[]
}

export interface GenerateBody {
  request?: GeneratorRequest
  code?: string
  save?: boolean
}

export interface BatchBody {
  request: GeneratorRequest
  count: number
  save?: boolean
}
