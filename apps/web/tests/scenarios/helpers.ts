import { vi } from 'vitest'
import { ApiError, NetworkError } from '../../src/lib/api'
import { createMockBackend, type Variant } from '../../src/scenarios/mock'
import type { ScenarioApi } from '../../src/scenarios/api'
import { makeUser, session, version } from '../utils'

export interface Seen {
  method: string
  path: string
  body: unknown
  csrf: string | null
}

const json = (body: unknown, status = 200) =>
  new Response(status === 204 ? null : JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })

/**
 * Replaces fetch with the scripted scenario backend behind the real REST paths, so the screens
 * run through the real client (CSRF header, error handling) without a server.
 */
export function installScenarioFetch(
  options: {
    role?: 'trainee' | 'instructor' | 'admin'
    language?: string
    variant?: Variant
    /** Hold every scenario call until this resolves. */
    gate?: Promise<void>
    override?: Partial<Record<string, (body: unknown) => Response | Promise<Response>>>
  } = {},
) {
  const backend: ScenarioApi = createMockBackend(options.variant ?? 'ok', 0)
  const seen: Seen[] = []
  const user = makeUser(options.role ?? 'instructor', { language: options.language ?? 'en' })
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = new URL(String(input), 'http://localhost')
      const path = url.pathname.replace('/api/v1', '')
      const method = init?.method ?? 'GET'
      const body = init?.body
        ? (JSON.parse(String(init.body)) as Record<string, unknown>)
        : undefined
      const csrf = (init?.headers as Record<string, string> | undefined)?.['X-CSRF-Token'] ?? null
      seen.push({ method, path: path + url.search, body, csrf })
      if (path === '/version') return json(version())
      if (path === '/auth/me') return json(session(user))
      if (path === '/sessions' && method === 'POST')
        return json({
          id: 'sess-1',
          scenario_id: String((body as { scenario_id?: string }).scenario_id),
          scenario_version: '1',
          seed: 1,
          status: 'lobby',
          created_at: '2026-10-18T09:00:00+00:00',
          started_at: null,
          ended_at: null,
          ticks: 0,
        })
      const key = `${method} ${path}`
      const override = options.override?.[key]
      if (override) return override(body)
      if (options.gate) await options.gate
      try {
        const yaml = String(body?.yaml ?? '')
        const seed = body?.seed as number | undefined
        if (key === 'GET /scenario-library') return json(await backend.list())
        if (method === 'GET' && path.startsWith('/scenario-library/'))
          return json(await backend.get(decodeURIComponent(path.split('/')[2] ?? '')))
        if (key === 'POST /scenario-tools/validate') return json(await backend.validate(yaml))
        if (key === 'POST /scenario-tools/check') return json(await backend.check(yaml, seed))
        if (key === 'POST /scenario-tools/preview') return json(await backend.preview(yaml))
        if (key === 'POST /scenario-library')
          return json(await backend.save(body as { yaml: string; tags?: string[] }))
        if (method === 'DELETE' && path.startsWith('/scenario-library/')) {
          await backend.remove(decodeURIComponent(path.split('/')[2] ?? ''))
          return json(null, 204)
        }
        if (key === 'POST /generator/generate') return json(await backend.generate(body as never))
        if (key === 'POST /generator/batch') return json(await backend.batch(body as never))
        if (key === 'GET /generator/archive') return json(await backend.archive())
        if (key === 'GET /generator/code')
          return json((await backend.decode(url.searchParams.get('code') ?? '')).request)
        if (key === 'POST /generator/code')
          return json({ code: await backend.encode((body as { request: never }).request) })
      } catch (error) {
        if (error instanceof NetworkError) throw new TypeError('failed to fetch', { cause: error })
        if (error instanceof ApiError) return json({ detail: error.message }, error.status)
        throw error
      }
      throw new Error(`unmocked request: ${key}`)
    }),
  )
  return { seen, backend }
}
