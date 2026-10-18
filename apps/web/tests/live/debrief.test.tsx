import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { MOCK_SCORE, MOCK_SCORE_EMPTY } from '../../src/live/mockScore'
import { makeUser, mockApi, renderApp, session, version } from '../utils'

const SCENARIO = {
  id: 'harrier-field-afternoon-watch',
  version: '0.3.1-mock',
  title: { en: 'Harrier Field: afternoon watch', hi: 'हैरियर फील्ड: दोपहर की निगरानी' },
  summary: { en: 'x', hi: 'x' },
  duration_s: 64,
  default_seed: 240117,
  start_time_of_day_h: 15.6,
  weather_condition: 'clear',
}

function open(
  score: unknown,
  options: {
    status?: number
    network?: boolean
    language?: string
    role?: 'trainee' | 'admin'
  } = {},
) {
  return mockApi({
    'GET /api/v1/version': { body: version() },
    'GET /api/v1/auth/me': {
      body: session(makeUser(options.role ?? 'trainee', { language: options.language ?? 'en' })),
    },
    'GET /api/v1/scenarios': { body: [SCENARIO] },
    'GET /api/v1/sessions/abc/score': options.network
      ? 'network-error'
      : { status: options.status ?? 200, body: score },
  })
}

const contact = (id: string) => {
  const el = document.querySelector(`[data-threat="${id}"]`)
  if (!el) throw new Error(`no contact ${id}`)
  return within(el as HTMLElement)
}

describe('debrief: populated', () => {
  it('shows the record, the reference note, the label and the ground truth', async () => {
    open(MOCK_SCORE)
    renderApp('/train/session/abc/debrief')
    expect(await screen.findByRole('heading', { name: 'Debrief', level: 1 })).toBeInTheDocument()
    expect(await screen.findByText('Harrier Field: afternoon watch')).toBeInTheDocument()
    expect(
      screen.getByText(/Reference scoring: timing standards and weights are fictional/),
    ).toBeVisible()
    expect(screen.getByText('Fictional scenarios · open-source parameters')).toBeInTheDocument()
    expect(screen.getByText('harrier-field-afternoon-watch 0.3.1-mock')).toBeInTheDocument()
    expect(screen.getByText('training-baseline 1.0.0')).toBeInTheDocument()
    expect(screen.getByText('240117')).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { name: 'Contact quad: Small rotary, hostile' }),
    ).toBeInTheDocument()
  })

  it('shows the score summary with d prime, rates, counts and the correction note', async () => {
    open(MOCK_SCORE)
    renderApp('/train/session/abc/debrief')
    const summary = await screen.findByRole('table', { name: 'Session score and decision score' })
    expect(within(summary).getByText('34.6%')).toBeInTheDocument()
    expect(within(summary).getByText('41.8%')).toBeInTheDocument()
    expect(within(summary).getByText('87.7%')).toBeInTheDocument()
    const sdt = screen.getByRole('table', { name: 'Signal-detection counts and rates' })
    expect(within(sdt).getByText('0.674')).toBeInTheDocument()
    expect(within(sdt).getByText('-0.337')).toBeInTheDocument()
    expect(within(sdt).getByText('100.0%')).toBeInTheDocument()
    expect(within(sdt).getByText('used 75.0%')).toBeInTheDocument()
    expect(screen.getByTestId('sdt-corrected')).toHaveTextContent('Log-linear correction applied')
  })

  it('has no correction note when no rate was exactly 0 or 1', async () => {
    open({ ...MOCK_SCORE, sdt: { ...MOCK_SCORE.sdt, corrected: false, hit_rate: 0.8 } })
    renderApp('/train/session/abc/debrief')
    await screen.findByRole('table', { name: 'Signal-detection counts and rates' })
    expect(screen.queryByTestId('sdt-corrected')).not.toBeInTheDocument()
  })

  it('lists the node path of a contact with weight, points, mark and the reason in words', async () => {
    open(MOCK_SCORE)
    renderApp('/train/session/abc/debrief')
    await screen.findByText('Harrier Field: afternoon watch')
    const quad = contact('th-quad')
    const path = quad.getByRole('table', { name: 'Path through the nodes for contact quad' })
    const rows = within(path).getAllByRole('row')
    // header, detect, classify, assess, respond, report
    expect(rows).toHaveLength(6)
    expect(within(rows[1]!).getByText('Detect')).toBeInTheDocument()
    expect(within(rows[1]!).getByText('0.250 / 0.25')).toBeInTheDocument()
    expect(within(rows[1]!).getByText('100.0%')).toBeInTheDocument()
    expect(
      within(rows[2]!).getByText(
        /Classified correctly as Small rotary after 31\.4 s against a standard of 25\.0 s\. Timing credit 75%\. Class calls changed before the final one: 1\./,
      ),
    ).toBeInTheDocument()
    expect(
      within(rows[3]!).getByText(/Assessed as Suspect for a hostile contact\. Partial credit\./),
    ).toBeInTheDocument()
    expect(within(rows[4]!).getByText(/Responded with ec-a after 52\.7 s/)).toBeInTheDocument()
    expect(
      within(rows[4]!).getByText(/Responses blocked by the rules on this contact: 1/),
    ).toBeInTheDocument()
    expect(within(rows[5]!).getByText('Report')).toBeInTheDocument()
  })

  it('shows findings of a contact with their cost', async () => {
    open(MOCK_SCORE)
    renderApp('/train/session/abc/debrief')
    await screen.findByText('Harrier Field: afternoon watch')
    const findings = contact('th-quad').getAllByTestId('finding')
    expect(findings).toHaveLength(2)
    expect(findings[0]).toHaveTextContent('Blocked response')
    expect(findings[0]).toHaveTextContent('The rules blocked 1 of your responses on this contact.')
    expect(findings[0]).toHaveTextContent('Cost 15.0 pts')
    expect(findings[1]).toHaveTextContent(
      'Track labels were swapped at 37.6 s (error swap-1) and never restored.',
    )
  })

  it('states a hard fail in words, with the breach, the position and a score of 0', async () => {
    open(MOCK_SCORE)
    renderApp('/train/session/abc/debrief')
    await screen.findByText('Harrier Field: afternoon watch')
    const fail = within(contact('th-survey').getByTestId('hard-fail'))
    expect(fail.getByText('Hard fail: rules of engagement breached')).toBeInTheDocument()
    expect(
      fail.getByText(
        'Engaged track T021 at 58.4 s on a contact that was civil traffic. Engaging a contact that is not hostile fails the contact: score 0.',
      ),
    ).toBeInTheDocument()
    expect(fail.getByText(/Contact score 0\./)).toBeInTheDocument()
    // the nodes are still listed so the path is visible
    expect(
      contact('th-survey').getByRole('table', {
        name: 'Path through the nodes for contact survey',
      }),
    ).toBeInTheDocument()
    expect(document.querySelectorAll('[data-testid="hard-fail"]')).toHaveLength(1)
  })

  it('grades the contact report per field', async () => {
    open(MOCK_SCORE)
    renderApp('/train/session/abc/debrief')
    await screen.findByText('Harrier Field: afternoon watch')
    const grades = contact('th-quad').getByRole('table', { name: 'Report grade for contact quad' })
    const rows = within(grades).getAllByRole('row')
    expect(rows).toHaveLength(6)
    expect(within(rows[1]!).getByText('Small rotary / Small rotary')).toBeInTheDocument()
    expect(within(rows[2]!).getByText('212 m off')).toBeInTheDocument()
    expect(within(rows[2]!).getByText('150 m')).toBeInTheDocument()
    expect(within(rows[3]!).getByText('1 / 2')).toBeInTheDocument()
    expect(within(rows[4]!).getByText('27° off')).toBeInTheDocument()
    expect(within(rows[5]!).getByText('90% stated, 82% right')).toBeInTheDocument()
    expect(
      within(rows[5]!).getByText(
        /Stated confidence 90%\. The report was 82% right\. Well calibrated\./,
      ),
    ).toBeInTheDocument()
    expect(
      contact('th-quad').getByText(/2 reports filed\. The last one is graded\./),
    ).toBeInTheDocument()
  })

  it('lists the first three lessons in order with what they cost', async () => {
    open(MOCK_SCORE)
    renderApp('/train/session/abc/debrief')
    await screen.findByText('Harrier Field: afternoon watch')
    const lessons = screen.getAllByTestId('lesson')
    expect(lessons).toHaveLength(3)
    expect(lessons[0]).toHaveTextContent(
      'survey: you engaged a contact that was civil traffic. Never engage before the contact is identified as hostile.',
    )
    expect(lessons[0]).toHaveTextContent('Marks lost 75.0 pts')
    expect(lessons[1]).toHaveTextContent('quad: the rules blocked 1 of your responses.')
    expect(lessons[2]).toHaveTextContent('quad: a track error at 37.6 s was left uncorrected.')
  })

  it('keeps contacts that were not presented or not worked in a quiet Not scored group', async () => {
    open(MOCK_SCORE)
    renderApp('/train/session/abc/debrief')
    await screen.findByText('Harrier Field: afternoon watch')
    const group = within(screen.getByTestId('not-scored'))
    const table = group.getByRole('table', { name: 'Contacts that were not scored' })
    const rows = within(table).getAllByRole('row')
    expect(rows).toHaveLength(3)
    expect(within(rows[1]!).getByText('Contact flock: Bird, clutter')).toBeInTheDocument()
    expect(within(rows[1]!).getByText('Not worked')).toBeInTheDocument()
    expect(within(rows[1]!).getByText(/Leaving it alone was correct/)).toBeInTheDocument()
    expect(within(rows[2]!).getByText('Not presented')).toBeInTheDocument()
    expect(within(rows[2]!).getByText(/No sensor reported this contact/)).toBeInTheDocument()
    // and they do not get a path of their own
    expect(document.querySelector('[data-threat="th-flock"][data-testid="contact"]')).toBeNull()
  })

  it('renders in Hindi with the Hindi labels and templates', async () => {
    open(MOCK_SCORE, { language: 'hi' })
    renderApp('/train/session/abc/debrief')
    expect(await screen.findByRole('heading', { name: 'डीब्रीफ़', level: 1 })).toBeInTheDocument()
    expect(await screen.findByText('हैरियर फील्ड: दोपहर की निगरानी')).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { name: /संपर्क क्वाड: छोटा रोटरी, शत्रु/ }),
    ).toBeInTheDocument()
    expect(screen.getAllByTestId('lesson')[0]).toHaveTextContent('सर्वे:')
    expect(document.body.textContent).not.toMatch(/\{\{/)
  })
})

describe('debrief: other states', () => {
  it('shows an empty state and the not-presented list when no contact was presented', async () => {
    open(MOCK_SCORE_EMPTY)
    renderApp('/train/session/abc/debrief')
    expect(await screen.findByText('No contact was presented')).toBeInTheDocument()
    expect(screen.queryAllByTestId('contact')).toHaveLength(0)
    expect(screen.getByText('None: no contact was scored')).toBeInTheDocument()
    expect(
      screen.getByText('No marks were lost on a scored contact, so there are no lessons.'),
    ).toBeInTheDocument()
    expect(screen.getByText(/d′ needs at least one signal trial/)).toBeInTheDocument()
    expect(within(screen.getByTestId('not-scored')).getAllByText('Not presented')).toHaveLength(4)
  })

  it('shows a loading state while the score is fetched', async () => {
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
        if (url.endsWith('/scenarios')) return Promise.resolve(json([SCENARIO]))
        return new Promise<Response>((resolve) => (release = resolve))
      }),
    )
    renderApp('/train/session/abc/debrief')
    expect(await screen.findByText('Reading the scored record')).toBeInTheDocument()
    release(json(MOCK_SCORE))
    expect(await screen.findByText('Harrier Field: afternoon watch')).toBeInTheDocument()
    expect(screen.queryByText('Reading the scored record')).not.toBeInTheDocument()
  })

  it('explains a session that has not ended (409) and links back to it', async () => {
    open({ detail: 'session has not ended' }, { status: 409 })
    renderApp('/train/session/abc/debrief')
    const failure = await screen.findByTestId('debrief-failure')
    expect(failure).toHaveAttribute('data-failure', 'notEnded')
    expect(within(failure).getByText('The session has not ended')).toBeInTheDocument()
    expect(within(failure).getByRole('link', { name: 'Session record' })).toHaveAttribute(
      'href',
      '/train/session/abc',
    )
    expect(screen.queryByText('Contact quad')).not.toBeInTheDocument()
  })

  it('explains a missing record (404)', async () => {
    open({ detail: 'not found' }, { status: 404 })
    renderApp('/train/session/abc/debrief')
    const failure = await screen.findByTestId('debrief-failure')
    expect(failure).toHaveAttribute('data-failure', 'notFound')
    expect(within(failure).getByText('No scored record for this session')).toBeInTheDocument()
  })

  it('says the server could not be reached on a network failure, and retries', async () => {
    open(null, { network: true })
    renderApp('/train/session/abc/debrief')
    const failure = await screen.findByTestId('debrief-failure')
    expect(failure).toHaveAttribute('data-failure', 'network')
    expect(within(failure).getByText('The server could not be reached')).toBeInTheDocument()
    open(MOCK_SCORE)
    await userEvent.click(within(failure).getByRole('button', { name: 'Try again' }))
    expect(await screen.findByText('Harrier Field: afternoon watch')).toBeInTheDocument()
  })

  it('shows a generic error for a server failure', async () => {
    open({ detail: 'boom' }, { status: 500 })
    renderApp('/train/session/abc/debrief')
    const failure = await screen.findByTestId('debrief-failure')
    expect(failure).toHaveAttribute('data-failure', 'error')
  })

  it('is closed to an admin', async () => {
    open(MOCK_SCORE, { role: 'admin' })
    renderApp('/train/session/abc/debrief')
    expect((await screen.findAllByText(/no access/i))[0]).toBeInTheDocument()
  })
})
