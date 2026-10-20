import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

const unauth = { status: 401, body: { detail: 'Not signed in' } }

/** The flag is read when the app is loaded, so each test loads a fresh copy of it. */
async function load(flag: string | undefined) {
  vi.resetModules()
  if (flag === undefined) vi.stubEnv('VITE_EVALUATION_MODE', '')
  else vi.stubEnv('VITE_EVALUATION_MODE', flag)
  window.localStorage.clear()
  return import('./utils')
}

afterEach(() => vi.unstubAllEnvs())

describe('evaluation mode off (the default)', () => {
  it('shows no evaluation entry, even in demo mode', async () => {
    const { mockApi, renderApp, version } = await load(undefined)
    const calls = mockApi({
      'GET /api/v1/version': { body: version('demo') },
      'GET /api/v1/auth/me': unauth,
    })
    renderApp('/sign-in')
    await screen.findByRole('heading', { name: 'Sign in', level: 1 })
    expect(screen.queryByRole('heading', { name: 'Enter the evaluation' })).not.toBeInTheDocument()
    expect(calls.some((c) => c.key.includes('evaluation-login'))).toBe(false)
  })

  it('keeps the frontend flag off in the production build config', async () => {
    const { EVALUATION_MODE } = await import('../src/lib/evaluation')
    expect(EVALUATION_MODE).toBe(false)
  })
})

describe('evaluation mode on', () => {
  it('offers the four seats with a description each, and the password form below', async () => {
    const { mockApi, renderApp, version } = await load('true')
    mockApi({
      'GET /api/v1/version': { body: version('production') },
      'GET /api/v1/auth/me': unauth,
    })
    renderApp('/sign-in')
    await screen.findByRole('heading', { name: 'Enter the evaluation', level: 1 })
    for (const name of [
      'Trainee operator',
      'Detachment commander',
      'Instructor',
      'Administrator',
    ]) {
      expect(screen.getByRole('button', { name: new RegExp(name) })).toBeInTheDocument()
    }
    expect(screen.getByText(/Assign sectors, hand over tracks/)).toBeInTheDocument()
    const form = screen.getByRole('heading', { name: 'Sign in with an account', level: 2 })
    const seats = screen.getByRole('button', { name: /Administrator/ })
    expect(seats.compareDocumentPosition(form) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(screen.getByLabelText('Password')).toBeInTheDocument()
  })

  it.each([
    ['Trainee operator', 'trainee', 'operator', 'trainee'],
    ['Detachment commander', 'commander', 'commander', 'trainee'],
    ['Instructor', 'instructor', 'operator', 'instructor'],
    ['Administrator', 'admin', 'operator', 'admin'],
  ] as const)('%s signs in with one click and no password', async (label, seat, team, role) => {
    const { makeUser, mockApi, renderApp, session, version } = await load('true')
    let signed = false
    const calls = mockApi({
      'GET /api/v1/version': { body: version('production') },
      'GET /api/v1/auth/me': () => (signed ? { body: session(makeUser(role)) } : unauth),
      'POST /api/v1/auth/evaluation-login': () => {
        signed = true
        return { body: session(makeUser(role)) }
      },
    })
    renderApp('/sign-in')
    await userEvent.click(await screen.findByRole('button', { name: new RegExp(label) }))
    await screen.findByRole('heading', { name: 'Status', level: 1 })
    const sent = calls.find((c) => c.key === 'POST /api/v1/auth/evaluation-login')
    expect(JSON.parse(String(sent?.init?.body))).toEqual({ seat })
    expect(window.localStorage.getItem('ui.teamRole')).toBe(team)
  })

  it('says so when the seats are not set up, and when the entry is rate limited', async () => {
    const { mockApi, renderApp, version } = await load('true')
    let status = 503
    mockApi({
      'GET /api/v1/version': { body: version('production') },
      'GET /api/v1/auth/me': unauth,
      'POST /api/v1/auth/evaluation-login': () => ({
        status,
        body: { detail: 'x' },
        headers: { 'Retry-After': '30' },
      }),
    })
    renderApp('/sign-in')
    await userEvent.click(await screen.findByRole('button', { name: /Instructor/ }))
    expect(await screen.findByText(/not set up on this server/)).toBeInTheDocument()
    status = 429
    await userEvent.click(screen.getByRole('button', { name: /Instructor/ }))
    expect(await screen.findByText(/Try again in 30 seconds/)).toBeInTheDocument()
  })

  it('disables the account, settings and restore actions on the administrator screens', async () => {
    const { makeUser, mockApi, renderApp, session, version } = await load('true')
    mockApi({
      'GET /api/v1/version': { body: version('production') },
      'GET /api/v1/auth/me': { body: session(makeUser('admin')) },
    })
    renderApp('/admin/users-and-roles')
    await userEvent.click(await screen.findByRole('tab', { name: 'User detail' }))
    expect(await screen.findByRole('button', { name: 'Reset access' })).toBeDisabled()
    expect(screen.getByText(/Disabled in the evaluation build/)).toBeInTheDocument()
    await waitFor(() => expect(screen.getByRole('combobox', { name: 'Role' })).toBeDisabled())
  })
})
