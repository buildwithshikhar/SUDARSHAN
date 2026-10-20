import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { MOCK_WELCOME } from '../../src/live/mock'
import { makeUser, mockApi, renderApp, session, version } from '../utils'

const scenario = {
  id: 'harrier-field-afternoon-watch',
  version: '0.3.1-mock',
  title: { en: 'Harrier Field: afternoon watch', hi: 'हैरियर फील्ड: दोपहर की निगरानी' },
  summary: {
    en: 'A small rotary contact closes on the field from the north-east.',
    hi: 'एक छोटा रोटरी संपर्क उत्तर-पूर्व से मैदान की ओर आता है।',
  },
  duration_s: 420,
  default_seed: 240117,
  start_time_of_day_h: 15.6,
  weather_condition: 'clear',
}

function api(scenarios: unknown, role: 'trainee' | 'instructor' | 'admin' = 'trainee', extra = {}) {
  return mockApi({
    'GET /api/v1/version': { body: version() },
    'GET /api/v1/auth/me': { body: session(makeUser(role)) },
    'GET /api/v1/scenarios': scenarios as never,
    ...extra,
  })
}

describe('session lobby', () => {
  it('shows a loading state while the scenarios are fetched', async () => {
    let release: (r: Response) => void = () => undefined
    const json = (body: unknown) =>
      new Response(JSON.stringify(body), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    vi.stubGlobal(
      'fetch',
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input)
        if (url.endsWith('/version')) return Promise.resolve(json(version()))
        if (url.endsWith('/auth/me')) return Promise.resolve(json(session(makeUser('trainee'))))
        return new Promise<Response>((resolve) => (release = resolve))
      }),
    )
    renderApp('/train/lobby')
    expect(await screen.findByText('Loading scenarios')).toBeInTheDocument()
    release(json([scenario]))
    expect(await screen.findByRole('table', { name: 'Scenarios' })).toBeInTheDocument()
    expect(screen.queryByText('Loading scenarios')).not.toBeInTheDocument()
  })

  it('shows the scenarios and the briefing', async () => {
    api({ body: [scenario] })
    renderApp('/train/lobby')
    expect(
      await screen.findByRole('heading', { name: 'Session lobby', level: 1 }),
    ).toBeInTheDocument()
    const table = await screen.findByRole('table', { name: 'Scenarios' })
    expect(
      within(table).getByRole('button', { name: 'Harrier Field: afternoon watch' }),
    ).toHaveAttribute('aria-pressed', 'true')
    expect(
      screen.getByText('A small rotary contact closes on the field from the north-east.'),
    ).toBeInTheDocument()
    const briefing = screen.getByRole('region', { name: 'Briefing' })
    expect(within(briefing).getByText('07:00.0')).toBeInTheDocument()
    expect(within(briefing).getByText('15:36')).toBeInTheDocument()
    expect(within(briefing).getByText(/The full briefing/)).toBeInTheDocument()
  })

  it('shows site, sensors, filed flights and the rule pack when the server sends the briefing', async () => {
    api({
      body: [
        {
          ...scenario,
          briefing: MOCK_WELCOME.briefing,
          rule_pack: { id: 'training-baseline', version: '1.0.0', title: MOCK_WELCOME.rules.title },
        },
      ],
    })
    renderApp('/train/lobby')
    expect(await screen.findByText(/Inner zone 0.9 km · Outer zone 3.2 km/)).toBeInTheDocument()
    expect(screen.getByText(/radar-1 \(Radar\) · eo-1 \(EO\) · rf-1 \(RF\)/)).toBeInTheDocument()
    expect(screen.getByText(/Survey flight, civil quadcopter · FF-2207/)).toBeInTheDocument()
    expect(
      screen.getByText(/Training baseline rules · training-baseline 1.0.0/),
    ).toBeInTheDocument()
    expect(screen.getByText(/Clear · vis 9.4 km/)).toBeInTheDocument()
  })

  it('checks the kit: role, WebGL, display and controls', async () => {
    api({ body: [scenario] })
    renderApp('/train/lobby')
    const kit = await screen.findByRole('region', { name: 'Role and kit check' })
    expect(within(kit).getByText('Trainee')).toBeInTheDocument()
    // jsdom has no WebGL, so the check says so instead of promising an EO view
    expect(within(kit).getByText(/Missing; the EO view cannot draw/)).toBeInTheDocument()
    expect(within(kit).getByText('Keyboard first; mouse works')).toBeInTheDocument()
  })

  it('has an empty state when no scenario is playable', async () => {
    api({ body: [] })
    renderApp('/train/lobby')
    expect(await screen.findByText('No scenarios available')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Create session' })).not.toBeInTheDocument()
  })

  it('has an error state with a retry for a server error, and for an unreachable server', async () => {
    let up = false
    mockApi({
      'GET /api/v1/version': { body: version() },
      'GET /api/v1/auth/me': { body: session(makeUser('trainee')) },
      'GET /api/v1/scenarios': () =>
        up ? { body: [scenario] } : { status: 500, body: { detail: 'x' } },
    })
    renderApp('/train/lobby')
    expect(await screen.findByText('Scenarios could not be loaded')).toBeInTheDocument()
    up = true
    await userEvent.click(screen.getByRole('button', { name: 'Retry' }))
    expect(await screen.findByRole('table', { name: 'Scenarios' })).toBeInTheDocument()
  })

  it('says the server is unreachable when the request fails outright', async () => {
    api('network-error')
    renderApp('/train/lobby')
    expect(await screen.findByText('The server is unreachable')).toBeInTheDocument()
  })

  it('creates a session with the CSRF token and opens it', async () => {
    const calls = api({ body: [scenario] }, 'trainee', {
      'POST /api/v1/sessions': { body: { id: 'new-1', status: 'lobby' } },
      'GET /api/v1/sessions/new-1/log': { status: 500, body: {} },
    })
    renderApp('/train/lobby')
    await userEvent.click(await screen.findByRole('button', { name: 'Create session' }))
    await waitFor(() => expect(calls.some((c) => c.key === 'POST /api/v1/sessions')).toBe(true))
    const post = calls.find((c) => c.key === 'POST /api/v1/sessions')!
    expect(JSON.parse(String(post.init?.body))).toEqual({
      scenario_id: 'harrier-field-afternoon-watch',
    })
    expect((post.init?.headers as Record<string, string>)['X-CSRF-Token']).toBeTruthy()
    // the route changes to the workspace, which starts by connecting
    await waitFor(() =>
      expect(screen.queryByRole('heading', { name: 'Session lobby' })).not.toBeInTheDocument(),
    )
  })

  it('says why a session could not be created', async () => {
    api({ body: [scenario] }, 'trainee', {
      'POST /api/v1/sessions': { status: 403, body: { detail: 'no' } },
    })
    renderApp('/train/lobby')
    await userEvent.click(await screen.findByRole('button', { name: 'Create session' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Your account cannot create sessions',
    )
  })

  it('opens for an instructor and not for an administrator', async () => {
    api({ body: [scenario] }, 'instructor')
    const { unmount } = renderApp('/train/lobby')
    expect(
      await screen.findByRole('heading', { name: 'Session lobby', level: 1 }),
    ).toBeInTheDocument()
    unmount()
    api({ body: [scenario] }, 'admin')
    renderApp('/train/lobby')
    expect(await screen.findByRole('heading', { name: 'No access', level: 1 })).toBeInTheDocument()
  })

  it('is reached from the Drills module, which links to the lobby', async () => {
    api({ body: [scenario] })
    renderApp('/trainee/drills')
    expect(await screen.findByRole('heading', { name: 'Drills', level: 1 })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Drills' })).toHaveAttribute('href', '/trainee/drills')
    await userEvent.click(screen.getByRole('tab', { name: 'Session lobby' }))
    expect(screen.getByRole('link', { name: 'Open session lobby' })).toHaveAttribute(
      'href',
      '/train/lobby',
    )
  })
})
