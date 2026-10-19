/**
 * REST calls for the scenario screens (docs/SCENARIO_ENGINE.md, "API"). Authoring needs the
 * instructor or admin role; writes carry the CSRF header through `api()`.
 *
 * `?mock=1` serves the scripted fixtures in the dev server only: `import.meta.env.DEV` is a
 * build-time constant, so the branch and the mock module are removed from production builds
 * (tests/live/prodBuild.test.ts proves it for the live mock; tests/scenarios/prodBuild.test.ts
 * for this one).
 */
import { api } from '../lib/api'
import type {
  Archive,
  BatchBody,
  CheckResponse,
  GenerateBody,
  GeneratedScenario,
  GeneratorRequest,
  PreviewResponse,
  SaveScenarioBody,
  ScenarioDetail,
  ScenarioSummary,
  ValidateResponse,
} from './types'

const ROOT = '/api/v1'

export interface DecodedCode {
  request: GeneratorRequest
  /** Set when the code was made by another generator version (the spec will differ). */
  warning?: string
  generator_version?: string
}

export interface ScenarioApi {
  list(signal?: AbortSignal): Promise<ScenarioSummary[]>
  get(id: string, signal?: AbortSignal): Promise<ScenarioDetail>
  validate(yaml: string, signal?: AbortSignal): Promise<ValidateResponse>
  check(yaml: string, seed?: number, signal?: AbortSignal): Promise<CheckResponse>
  preview(yaml: string, seed?: number, signal?: AbortSignal): Promise<PreviewResponse>
  save(body: SaveScenarioBody): Promise<ScenarioSummary>
  remove(id: string): Promise<void>
  generate(body: GenerateBody): Promise<GeneratedScenario>
  batch(body: BatchBody): Promise<GeneratedScenario[]>
  archive(signal?: AbortSignal): Promise<Archive>
  decode(code: string): Promise<DecodedCode>
  encode(request: GeneratorRequest): Promise<string>
}

type Wrapped<T, K extends string> = T | { [key in K]: T }

/** Accepts the bare value or an object that wraps it under `key`. */
function unwrap<T>(value: Wrapped<T, string>, key: string): T {
  if (value && typeof value === 'object' && !Array.isArray(value) && key in value) {
    return (value as Record<string, T>)[key] as T
  }
  return value as T
}

const real: ScenarioApi = {
  list: (signal) =>
    api<Wrapped<ScenarioSummary[], 'scenarios'>>(`${ROOT}/scenario-library`, { signal }).then((r) =>
      unwrap(r, 'scenarios'),
    ),
  get: (id, signal) =>
    api<ScenarioDetail>(`${ROOT}/scenario-library/${encodeURIComponent(id)}`, { signal }),
  validate: (yaml, signal) =>
    api<ValidateResponse>(`${ROOT}/scenario-tools/validate`, {
      method: 'POST',
      body: { yaml },
      signal,
    }),
  check: (yaml, seed, signal) =>
    api<CheckResponse>(`${ROOT}/scenario-tools/check`, {
      method: 'POST',
      body: seed === undefined ? { yaml } : { yaml, seed },
      signal,
    }),
  preview: (yaml, seed, signal) =>
    api<PreviewResponse>(`${ROOT}/scenario-tools/preview`, {
      method: 'POST',
      body: seed === undefined ? { yaml } : { yaml, seed },
      signal,
    }),
  save: (body) => api<ScenarioSummary>(`${ROOT}/scenario-library`, { method: 'POST', body }),
  remove: (id) =>
    api<void>(`${ROOT}/scenario-library/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  generate: (body) =>
    api<GeneratedScenario>(`${ROOT}/generator/generate`, { method: 'POST', body }),
  batch: (body) =>
    api<Wrapped<GeneratedScenario[], 'scenarios'>>(`${ROOT}/generator/batch`, {
      method: 'POST',
      body,
    }).then((r) => unwrap(r, 'scenarios')),
  archive: (signal) => api<Archive>(`${ROOT}/generator/archive`, { signal }),
  decode: (code) =>
    api<GeneratorRequest | DecodedCode>(
      `${ROOT}/generator/code?code=${encodeURIComponent(code)}`,
    ).then((r) => ('request' in r ? r : { request: r })),
  encode: (request) =>
    api<string | { code: string }>(`${ROOT}/generator/code`, {
      method: 'POST',
      body: { request },
    }).then((r) => (typeof r === 'string' ? r : r.code)),
}

/**
 * The client for the current page. In the dev server `?mock=1` swaps in the scripted fixtures,
 * with `&scn=empty|error|offline|slow` to show the other states.
 */
export function scenarioApi(search: string = window.location.search): ScenarioApi {
  if (import.meta.env.DEV && new URLSearchParams(search).get('mock') === '1') {
    return lazyMock(search)
  }
  return real
}

function lazyMock(search: string): ScenarioApi {
  const backend = import('./mock').then((m) => m.mockBackend(search))
  const call =
    <K extends keyof ScenarioApi>(name: K) =>
    async (...args: Parameters<ScenarioApi[K]>) => {
      const impl = (await backend)[name] as (...a: unknown[]) => Promise<unknown>
      return impl(...args)
    }
  return {
    list: call('list'),
    get: call('get'),
    validate: call('validate'),
    check: call('check'),
    preview: call('preview'),
    save: call('save'),
    remove: call('remove'),
    generate: call('generate'),
    batch: call('batch'),
    archive: call('archive'),
    decode: call('decode'),
    encode: call('encode'),
  } as ScenarioApi
}
