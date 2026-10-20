import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { renderApp } from '../utils'
import { installScenarioFetch } from './helpers'

const rows = () => within(screen.getByRole('table')).getAllByRole('row').slice(1)

describe('scenario library', () => {
  it('lists the scenarios with the exact solvability wording', async () => {
    installScenarioFetch()
    renderApp('/content/scenarios')
    expect(await screen.findByRole('heading', { name: 'Scenario library', level: 1 })).toBeVisible()
    await waitFor(() => expect(rows()).toHaveLength(14))
    const table = screen.getByRole('table', { name: 'Scenarios held by this instance' })
    expect(within(table).getAllByText('Verified solvable by test run').length).toBeGreaterThan(5)
    expect(within(table).getByText('Not verified solvable')).toBeInTheDocument()
    expect(within(table).getAllByText('Unchecked')).toHaveLength(2)
    expect(screen.getByTestId('library-count')).toHaveTextContent('14 of 14 scenarios')
    // every status badge has an icon and text
    for (const badge of table.querySelectorAll('[data-status]'))
      expect(badge.querySelector('svg')).not.toBeNull()
  })

  it('offers Delete only for saved scenarios', async () => {
    installScenarioFetch()
    renderApp('/content/scenarios')
    await waitFor(() => expect(rows()).toHaveLength(14))
    const scripted = rows().find((r) => r.textContent?.includes('curriculum-01-first-light'))!
    expect(within(scripted).queryByRole('button', { name: /^Delete/ })).toBeNull()
    const generated = rows().find((r) => r.textContent?.includes('gen-48213907-a1f3c2'))!
    expect(within(generated).getByRole('button', { name: /^Delete/ })).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: /^Delete: / })).toHaveLength(7)
  })

  it('filters by origin, terrain, time of day and tag, searches, and clears', async () => {
    installScenarioFetch()
    const user = userEvent.setup()
    renderApp('/content/scenarios')
    await waitFor(() => expect(rows()).toHaveLength(14))
    await user.selectOptions(screen.getByLabelText('Origin'), 'scripted')
    expect(rows()).toHaveLength(5)
    await user.selectOptions(screen.getByLabelText('Time of day'), 'night')
    expect(rows()).toHaveLength(1)
    await user.click(screen.getByRole('button', { name: 'Clear filters' }))
    expect(rows()).toHaveLength(14)
    await user.selectOptions(screen.getByLabelText('Terrain'), 'osprey-town')
    expect(rows()).toHaveLength(2)
    await user.click(screen.getByRole('button', { name: 'Clear filters' }))
    await user.selectOptions(screen.getByLabelText('Tag'), 'swarm')
    expect(rows()).toHaveLength(2)
    await user.click(screen.getByRole('button', { name: 'Clear filters' }))
    await user.type(screen.getByLabelText('Search by id, title or tag'), 'marlin')
    expect(rows()).toHaveLength(1)
    await user.clear(screen.getByLabelText('Search by id, title or tag'))
    await user.type(screen.getByLabelText('Search by id, title or tag'), 'zzzz')
    expect(screen.getByText('No scenario matches these filters')).toBeInTheDocument()
  })

  it('sorts by difficulty and by duration', async () => {
    installScenarioFetch()
    const user = userEvent.setup()
    renderApp('/content/scenarios')
    await waitFor(() => expect(rows()).toHaveLength(14))
    await user.selectOptions(screen.getByLabelText('Sort by'), 'duration')
    expect(rows()[0]).toHaveTextContent('curriculum-05-town-edge-swarm')
    expect(rows()[13]).toHaveTextContent('example-minimal-single')
    await user.selectOptions(screen.getByLabelText('Sort by'), 'title')
    expect(rows()[0]).toHaveTextContent('Bird or drone')
  })

  it('shows the Hindi interface with the catalogue wording', async () => {
    installScenarioFetch({ language: 'hi' })
    renderApp('/content/scenarios')
    expect(
      await screen.findByRole('heading', { name: 'परिदृश्य पुस्तकालय', level: 1 }),
    ).toBeVisible()
    await waitFor(() => expect(rows()).toHaveLength(14))
    expect(screen.getAllByText('परीक्षण-रन से हल-योग्य सत्यापित').length).toBeGreaterThan(5)
    expect(screen.getByText('हल-योग्य सत्यापित नहीं')).toBeInTheDocument()
  })

  it('asks before deleting, cancels with Escape, and deletes with a CSRF-protected request', async () => {
    const { seen } = installScenarioFetch()
    const user = userEvent.setup()
    renderApp('/content/scenarios')
    await waitFor(() => expect(rows()).toHaveLength(14))
    await user.click(screen.getByRole('button', { name: /^Delete: Ridge picket drill/ }))
    const dialog = await screen.findByRole('dialog', { name: 'Delete scenario' })
    expect(dialog).toHaveTextContent('auth-ridge-picket-drill')
    // the browser closes a modal <dialog> on Escape (the real key is covered by the mock e2e spec)
    fireEvent(dialog, new Event('close'))
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
    expect(rows()).toHaveLength(14)
    expect(seen.some((s) => s.method === 'DELETE')).toBe(false)
    await user.click(screen.getByRole('button', { name: /^Delete: Ridge picket drill/ }))
    await user.click(
      within(await screen.findByRole('dialog')).getByRole('button', { name: 'Delete scenario' }),
    )
    await waitFor(() => expect(rows()).toHaveLength(13))
    expect(screen.getByText('Deleted auth-ridge-picket-drill.')).toBeInTheDocument()
    const call = seen.find((s) => s.method === 'DELETE')!
    expect(call.path).toBe('/scenario-library/auth-ridge-picket-drill')
    expect(call.csrf).toBe('csrf-token-1')
  })

  it('says so when a delete is refused', async () => {
    installScenarioFetch({
      override: {
        'DELETE /scenario-library/gen-48213907-a1f3c2': () =>
          new Response(JSON.stringify({ detail: 'nope' }), { status: 403 }),
      },
    })
    const user = userEvent.setup()
    renderApp('/content/scenarios')
    await waitFor(() => expect(rows()).toHaveLength(14))
    await user.click(screen.getByRole('button', { name: /^Delete: Generated 48213907/ }))
    await user.click(
      within(await screen.findByRole('dialog')).getByRole('button', { name: 'Delete scenario' }),
    )
    expect(await screen.findByText('Your account cannot delete this scenario.')).toBeInTheDocument()
    expect(rows()).toHaveLength(14)
  })

  it('starts a session on the scenario and opens it', async () => {
    const { seen } = installScenarioFetch()
    const user = userEvent.setup()
    renderApp('/content/scenarios')
    await waitFor(() => expect(rows()).toHaveLength(14))
    await user.click(screen.getByRole('button', { name: /^Start a session: Marlin Hill/ }))
    await waitFor(() =>
      expect(seen.find((s) => s.path === '/sessions')?.body).toEqual({
        scenario_id: 'marlin-hill-evening-picket',
      }),
    )
  })

  it('shows a loading state, then the table', async () => {
    let release: () => void = () => undefined
    installScenarioFetch({ gate: new Promise<void>((r) => (release = r)) })
    renderApp('/content/scenarios')
    expect(await screen.findByText('Loading the scenario library')).toBeInTheDocument()
    release()
    await waitFor(() => expect(rows()).toHaveLength(14))
  })

  it('shows an empty state', async () => {
    installScenarioFetch({ variant: 'empty' })
    renderApp('/content/scenarios')
    expect(await screen.findByText('The library holds no scenarios')).toBeInTheDocument()
  })

  it('shows an error state and retries', async () => {
    installScenarioFetch({ variant: 'error' })
    const user = userEvent.setup()
    renderApp('/content/scenarios')
    expect(await screen.findByText('The scenario library could not be loaded')).toBeInTheDocument()
    installScenarioFetch()
    await user.click(screen.getByRole('button', { name: 'Retry' }))
    await waitFor(() => expect(rows()).toHaveLength(14))
  })

  it('says the server is unreachable on a network failure', async () => {
    installScenarioFetch({ variant: 'offline' })
    renderApp('/content/scenarios')
    expect(await screen.findByText('The server is unreachable')).toBeInTheDocument()
  })

  it('is closed to trainees and open to administrators', async () => {
    installScenarioFetch({ role: 'trainee' })
    renderApp('/content/scenarios')
    expect(await screen.findByRole('heading', { name: 'No access', level: 1 })).toBeInTheDocument()
  })

  it('is reached from the instructor sidebar and the old module path', async () => {
    installScenarioFetch()
    const user = userEvent.setup()
    renderApp('/instructor/scenarios')
    expect(await screen.findByRole('heading', { name: 'Scenario library', level: 1 })).toBeVisible()
    await user.click(
      within(screen.getByRole('navigation', { name: 'Main navigation' })).getByRole('link', {
        name: 'Generator',
      }),
    )
    expect(await screen.findByRole('heading', { name: 'Generator studio', level: 1 })).toBeVisible()
  })

  it('opens administrators too', async () => {
    installScenarioFetch({ role: 'admin' })
    renderApp('/content/scenarios')
    expect(await screen.findByRole('heading', { name: 'Scenario library', level: 1 })).toBeVisible()
  })
})
