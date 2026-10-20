import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import brand from '../../../brand.json'
import { makeUser, mockApi, renderApp, session, version } from './utils'

async function select(label: string) {
  return waitFor(() => {
    const found = screen.getAllByLabelText(label).find((element) => element.tagName === 'SELECT')
    if (!found) throw new Error(`no select labelled ${label}`)
    return found
  })
}

const unauth = { status: 401, body: { detail: 'Not signed in' } }

describe('signed out', () => {
  it('redirects a protected page to sign in and shows the demo hint only in demo mode', async () => {
    mockApi({ 'GET /api/v1/version': { body: version('demo') }, 'GET /api/v1/auth/me': unauth })
    renderApp('/status')
    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
    expect(await screen.findByRole('group', { name: 'Open as' })).toBeInTheDocument()
    expect(screen.getByText(brand.descriptor)).toBeInTheDocument()
  })

  it('shows no demo hint in production', async () => {
    mockApi({
      'GET /api/v1/version': { body: version('production') },
      'GET /api/v1/auth/me': unauth,
    })
    renderApp('/sign-in')
    await screen.findByRole('heading', { name: 'Sign in' })
    expect(screen.queryByRole('group', { name: 'Open as' })).not.toBeInTheDocument()
  })

  it('validates the form before sending anything', async () => {
    const calls = mockApi({
      'GET /api/v1/version': { body: version() },
      'GET /api/v1/auth/me': unauth,
    })
    renderApp('/sign-in')
    await userEvent.click(await screen.findByRole('button', { name: 'Sign in' }))
    expect(screen.getByText('Enter your email address.')).toBeInTheDocument()
    expect(screen.getByText('Enter your password.')).toBeInTheDocument()
    expect(calls.some((c) => c.key.includes('login'))).toBe(false)
  })

  it.each([
    [{ status: 401, body: { detail: 'Invalid email or password' } }, 'Invalid email or password.'],
    [
      { status: 429, body: { detail: 'x' }, headers: { 'Retry-After': '42' } },
      'Too many failed attempts. Try again in 42 seconds.',
    ],
    ['network-error' as const, 'The server is unreachable. Check the connection and try again.'],
  ])('reports a failed sign-in (%#)', async (reply, message) => {
    mockApi({
      'GET /api/v1/version': { body: version() },
      'GET /api/v1/auth/me': unauth,
      'POST /api/v1/auth/login': reply,
    })
    renderApp('/sign-in')
    await userEvent.type(await screen.findByLabelText('Email address'), 'a@unit.example')
    await userEvent.type(screen.getByLabelText('Password'), 'whatever-password')
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(message)
  })

  it('serves About publicly with the data notice, scope and affiliation', async () => {
    mockApi({ 'GET /api/v1/version': { body: version() }, 'GET /api/v1/auth/me': unauth })
    renderApp('/about')
    expect(
      await screen.findByRole('heading', { name: 'About and data notice', level: 1 }),
    ).toBeInTheDocument()
    expect(screen.getByText(/calibrated from open research datasets/)).toBeInTheDocument()
    expect(screen.getByText(/Defensive training only/)).toBeInTheDocument()
    expect(screen.getByText(/independent student project/)).toBeInTheDocument()
  })

  it('shows Not found for unknown addresses and the footer label everywhere', async () => {
    mockApi({ 'GET /api/v1/version': { body: version() }, 'GET /api/v1/auth/me': unauth })
    renderApp('/no/such/page/at/all')
    expect(
      await screen.findByRole('heading', { name: 'Page not found', level: 1 }),
    ).toBeInTheDocument()
    expect(
      screen.getByText('Built on published specifications and open research.'),
    ).toBeInTheDocument()
  })
})

describe('offline', () => {
  it('shows the unreachable screen and recovers on retry', async () => {
    let up = false
    mockApi({
      'GET /api/v1/version': { body: version() },
      'GET /api/v1/auth/me': () => (up ? unauth : 'network-error'),
    })
    renderApp('/')
    expect(await screen.findByRole('alert')).toHaveTextContent('Server unreachable')
    up = true
    await userEvent.click(screen.getByRole('button', { name: 'Retry' }))
    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
  })
})

function signedIn(role: 'trainee' | 'instructor' | 'admin', env = 'demo', extra = {}) {
  return mockApi({
    'GET /api/v1/version': { body: version(env) },
    'GET /api/v1/auth/me': { body: session(makeUser(role, extra)) },
    'POST /api/v1/auth/logout': { status: 204 },
    'PATCH /api/v1/auth/me/preferences': (init) => ({
      body: { ...makeUser(role), ...JSON.parse(String(init?.body)) },
    }),
  })
}

describe('shell by role', () => {
  it.each([
    [
      'trainee',
      ['Today', 'Drills', 'Recognition library', 'My performance', 'Profile', 'Help and SOPs'],
      ['Cohorts', 'Health'],
    ],
    [
      'instructor',
      ['Cohorts', 'Live sessions', 'Rule packs', 'Unit AAR', 'Profile'],
      ['Today', 'Health'],
    ],
    ['admin', ['Users and roles', 'Records', 'Backup', 'Profile'], ['Today', 'Cohorts']],
  ] as const)('%s sees only its own modules', async (role, present, absent) => {
    signedIn(role)
    renderApp('/status')
    const nav = await screen.findByRole('navigation', { name: 'Main navigation' })
    for (const name of present) expect(within(nav).getByRole('link', { name })).toBeInTheDocument()
    for (const name of absent)
      expect(within(nav).queryByRole('link', { name })).not.toBeInTheDocument()
  })

  it('shows the account, role and the modules table with what each module does', async () => {
    signedIn('instructor')
    renderApp('/status')
    expect(
      await screen.findByText('instructor@unit.example', { selector: 'dd' }),
    ).toBeInTheDocument()
    const table = screen.getByRole('table', { name: 'Modules for your role' })
    const cohorts = within(table)
      .getByRole('link', { name: 'Cohorts' })
      .closest('tr') as HTMLElement
    expect(cohorts).toHaveTextContent('Cohorts, members and drill sequences.')
    expect(await screen.findByText('abc1234')).toBeInTheDocument()
  })

  it('opens the Today overview for a trainee', async () => {
    signedIn('trainee')
    renderApp('/trainee/today')
    expect(await screen.findByText('Recommended drill')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Today', level: 1 })).toBeInTheDocument()
  })

  it.each([
    ['trainee', '/admin/users-and-roles'],
    ['trainee', '/instructor/cohorts'],
    ['instructor', '/trainee/today'],
    ['instructor', '/admin/health'],
    ['admin', '/trainee/drills'],
  ] as const)('%s opening %s gets No access', async (role, path) => {
    signedIn(role)
    renderApp(path)
    expect(await screen.findByRole('heading', { name: 'No access', level: 1 })).toBeInTheDocument()
  })

  it('shows Not found for a module the role does not have, and for an unknown role segment', async () => {
    signedIn('trainee')
    const { unmount } = renderApp('/trainee/cohorts')
    expect(
      await screen.findByRole('heading', { name: 'Page not found', level: 1 }),
    ).toBeInTheDocument()
    unmount()
    signedIn('trainee')
    renderApp('/wizard/spells')
    expect(
      await screen.findByRole('heading', { name: 'Page not found', level: 1 }),
    ).toBeInTheDocument()
  })

  it('opens the shared Help module and rejects unknown account modules', async () => {
    signedIn('admin')
    const { unmount } = renderApp('/account/help')
    expect(await screen.findByRole('tab', { name: 'Keyboard shortcuts' })).toBeInTheDocument()
    unmount()
    signedIn('admin')
    renderApp('/account/nothing')
    expect(
      await screen.findByRole('heading', { name: 'Page not found', level: 1 }),
    ).toBeInTheDocument()
  })

  it('exposes the developer components route in demo mode only', async () => {
    signedIn('admin', 'demo')
    const demo = renderApp('/dev/components')
    expect(await screen.findByRole('heading', { name: 'Components', level: 1 })).toBeInTheDocument()
    demo.unmount()
    signedIn('admin', 'production')
    renderApp('/dev/components')
    expect(
      await screen.findByRole('heading', { name: 'Page not found', level: 1 }),
    ).toBeInTheDocument()
  })

  it('applies the signed-in user’s saved language and theme', async () => {
    signedIn('trainee', 'demo', { language: 'hi', theme: 'light' })
    renderApp('/status')
    expect(await screen.findByRole('heading', { name: 'स्थिति', level: 1 })).toBeInTheDocument()
    expect(document.documentElement.dataset.theme).toBe('light')
    expect(document.documentElement.lang).toBe('hi')
  })
})

describe('sign in and out', () => {
  it('signs in, lands on Status, and signs out again', async () => {
    let signed = false
    mockApi({
      'GET /api/v1/version': { body: version() },
      'GET /api/v1/auth/me': () => (signed ? { body: session(makeUser('admin')) } : unauth),
      'POST /api/v1/auth/login': () => {
        signed = true
        return { body: session(makeUser('admin')) }
      },
      'POST /api/v1/auth/logout': { status: 204 },
    })
    renderApp('/status')
    await userEvent.type(await screen.findByLabelText('Email address'), 'admin@unit.example')
    await userEvent.type(screen.getByLabelText('Password'), 'correct-horse-battery')
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(await screen.findByRole('heading', { name: 'Status', level: 1 })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Sign out' }))
    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
  })

  it('returns to the page that was asked for after signing in', async () => {
    mockApi({
      'GET /api/v1/version': { body: version() },
      'GET /api/v1/auth/me': unauth,
      'POST /api/v1/auth/login': { body: session(makeUser('trainee')) },
    })
    renderApp('/trainee/today')
    await userEvent.type(await screen.findByLabelText('Email address'), 'trainee@unit.example')
    await userEvent.type(screen.getByLabelText('Password'), 'correct-horse-battery')
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(await screen.findByText('Recommended drill')).toBeInTheDocument()
  })
})

describe('preferences', () => {
  it('saves language and theme from the top bar with the CSRF token', async () => {
    const calls = signedIn('trainee')
    renderApp('/status')
    await screen.findByRole('navigation', { name: 'Main navigation' })
    await userEvent.click(screen.getByRole('button', { name: 'हिन्दी' }))
    await userEvent.click(screen.getByRole('button', { name: 'हल्का' }))
    const patches = calls.filter((c) => c.key === 'PATCH /api/v1/auth/me/preferences')
    expect(patches).toHaveLength(2)
    expect(JSON.parse(String(patches[0]?.init?.body))).toEqual({ language: 'hi' })
    expect(JSON.parse(String(patches[1]?.init?.body))).toEqual({ theme: 'light' })
    expect((patches[0]?.init?.headers as Record<string, string>)['X-CSRF-Token']).toBe(
      'csrf-token-1',
    )
    expect(document.documentElement.dataset.theme).toBe('light')
  })

  it('works from the Profile screen and reports a failed save without losing the choice', async () => {
    mockApi({
      'GET /api/v1/version': { body: version() },
      'GET /api/v1/auth/me': { body: session(makeUser('trainee')) },
      'PATCH /api/v1/auth/me/preferences': 'network-error',
    })
    renderApp('/account/profile')
    await userEvent.selectOptions(await select('Theme'), 'light')
    expect(await screen.findByRole('alert')).toHaveTextContent('Could not save to your account')
    expect(document.documentElement.dataset.theme).toBe('light')
    await userEvent.click(screen.getByRole('tab', { name: 'Accessibility' }))
    expect(screen.getByText(/Every control can be reached/)).toBeInTheDocument()
  })

  it('confirms a successful save', async () => {
    signedIn('trainee')
    renderApp('/account/profile')
    await userEvent.selectOptions(await select('Language'), 'hi')
    expect(await screen.findByText('प्राथमिकताएँ आपके खाते में सहेजी गईं।')).toBeInTheDocument()
  })
})
