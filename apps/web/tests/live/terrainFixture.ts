import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const root = resolve(import.meta.dirname, '../fixtures/terrain')

/** A fetch that serves `/api/v1/terrain/{id}/{file}` from the checked-in fixture packs. */
export function fixtureFetch(
  overrides: Record<string, () => Response | Promise<Response>> = {},
): typeof fetch & { calls: string[] } {
  const calls: string[] = []
  const fn = (async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input)
    calls.push(url)
    if (init?.signal?.aborted) throw new DOMException('aborted', 'AbortError')
    const match = /\/api\/v1\/terrain\/([^/]+)\/([^/?]+)$/.exec(url)
    const file = match?.[2]
    const override = file ? overrides[file] : undefined
    if (override) return override()
    if (!match || !file) return new Response('nope', { status: 404 })
    try {
      const body = readFileSync(resolve(root, decodeURIComponent(match[1] ?? ''), file))
      return new Response(body, { status: 200 })
    } catch {
      return new Response('missing', { status: 404 })
    }
  }) as typeof fetch & { calls: string[] }
  fn.calls = calls
  return fn
}
