import { render } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { vi } from 'vitest'
import brand from '../../../brand.json'
import { AppRoutes } from '../src/App'
import { AuthProvider, type User } from '../src/lib/auth'
import { VersionProvider } from '../src/lib/version'

export const version = (env = 'demo') => ({
  productName: brand.productName,
  descriptor: brand.descriptor,
  version: '0.1.0',
  gitSha: 'abc1234',
  buildTime: '2026-01-01T00:00:00Z',
  env,
})

export const makeUser = (role: User['role'], extra: Partial<User> = {}): User => ({
  id: `id-${role}`,
  email: `${role}@unit.example`,
  role,
  language: 'en',
  theme: 'dark',
  ...extra,
})

type Reply = { status?: number; body?: unknown; headers?: Record<string, string> } | 'network-error'
type Handler = Reply | ((init: RequestInit | undefined) => Reply)

export interface Call {
  key: string
  init: RequestInit | undefined
}

/** Replaces fetch with a table of "METHOD /path" handlers; unknown routes fail the test. */
export function mockApi(routes: Record<string, Handler>) {
  const calls: Call[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const key = `${init?.method ?? 'GET'} ${String(input)}`
      calls.push({ key, init })
      const handler = routes[key]
      if (!handler) throw new Error(`unmocked request: ${key}`)
      const reply = typeof handler === 'function' ? handler(init) : handler
      if (reply === 'network-error') return Promise.reject(new TypeError('failed to fetch'))
      const status = reply.status ?? 200
      return Promise.resolve(
        new Response(status === 204 ? null : JSON.stringify(reply.body ?? {}), {
          status,
          headers: reply.headers,
        }),
      )
    }),
  )
  return calls
}

export function session(user: User, csrf = 'csrf-token-1') {
  return { user, csrf, expiresAt: '2026-01-01T12:00:00+00:00' }
}

export function renderApp(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <VersionProvider>
        <AuthProvider>
          <AppRoutes />
        </AuthProvider>
      </VersionProvider>
    </MemoryRouter>,
  )
}
