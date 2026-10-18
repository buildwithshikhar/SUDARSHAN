/** REST calls for the live-session screens (docs/LIVE_SESSION.md). */
import type { SessionScore } from '../contracts/score-result.v1'
import { api } from '../lib/api'
import type { Briefing } from './protocol'

type Localised = string | { en: string; hi: string }

export interface ScenarioItem {
  id: string
  version: string
  title: Localised
  summary: Localised
  duration_s: number
  default_seed: number
  start_time_of_day_h: number
  weather_condition: string
  /** Optional: the full briefing, when the server includes it in the list. */
  briefing?: Briefing
  /** Optional: the rule pack the scenario names. */
  rule_pack?: { id: string; version: string; title?: Localised }
}

export interface SessionRow {
  id: string
  scenario_id: string
  scenario_version: string
  seed: number
  status: 'lobby' | 'running' | 'ended' | 'abandoned'
  created_at: string
  started_at: string | null
  ended_at: string | null
  ticks: number
}

export interface SessionLog {
  verified: boolean
  first_bad_seq: number | null
  event_count: number
  head: string
  final_state_hash: string
  events: unknown[]
}

export const listScenarios = (signal?: AbortSignal) =>
  api<ScenarioItem[] | { scenarios: ScenarioItem[] }>('/api/v1/scenarios', { signal }).then((r) =>
    Array.isArray(r) ? r : r.scenarios,
  )

export const createSession = (scenarioId: string, seed?: number) =>
  api<SessionRow>('/api/v1/sessions', {
    method: 'POST',
    body: seed === undefined ? { scenario_id: scenarioId } : { scenario_id: scenarioId, seed },
  })

export const getSession = (id: string, signal?: AbortSignal) =>
  api<SessionRow>(`/api/v1/sessions/${encodeURIComponent(id)}`, { signal })

export const getSessionLog = (id: string, signal?: AbortSignal) =>
  api<SessionLog>(`/api/v1/sessions/${encodeURIComponent(id)}/log`, { signal })

/**
 * The scored debrief of an ended session. `?mock=1` serves the scripted record in the dev server
 * only: `import.meta.env.DEV` is a build-time constant, so the branch and the mock module are
 * removed from production builds (tests/live/prodBuild.test.ts proves it).
 */
export async function getScore(
  id: string,
  signal?: AbortSignal,
  search: string = window.location.search,
): Promise<SessionScore> {
  if (import.meta.env.DEV && new URLSearchParams(search).get('mock') === '1') {
    const { MOCK_SCORE } = await import('./mockScore')
    return MOCK_SCORE
  }
  return api<SessionScore>(`/api/v1/sessions/${encodeURIComponent(id)}/score`, { signal })
}

/** Text in either interface language; a plain string is shown as is. */
export const localised = (text: Localised | undefined, lang: 'en' | 'hi'): string =>
  text === undefined ? '' : typeof text === 'string' ? text : text[lang]
