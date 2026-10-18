import { act, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeAll, describe, expect, it, vi } from 'vitest'
import { reportProblem } from '../../src/live/mock'
import type { LiveServerMessage } from '../../src/live/protocol'
import { checkReport, prefillReport } from '../../src/live/report'
import { makeUser, mockApi, renderApp, session, version } from '../utils'
import { event, frame, track, verdictEvent, welcome, type FakeTransport } from './helpers'

const holder = vi.hoisted(() => ({ current: null as unknown }))
vi.mock('../../src/live/createTransport', () => ({
  createTransport: async () => {
    const { FakeTransport } = await import('./helpers')
    const transport = new FakeTransport()
    holder.current = transport
    return transport
  },
}))

beforeAll(async () => {
  await import('../../src/live/views/EoView')
}, 60_000)

const fake = () => holder.current as unknown as FakeTransport
const push = (message: LiveServerMessage) => act(() => fake().push(message))

async function running(language = 'en') {
  // a stale transport from the previous test must not satisfy the wait for the new one
  holder.current = null
  mockApi({
    'GET /api/v1/version': { body: version() },
    'GET /api/v1/auth/me': { body: session(makeUser('trainee', { language })) },
  })
  renderApp('/train/session/abc')
  await waitFor(() =>
    expect((holder.current as FakeTransport | null)?.handlers ?? null).not.toBeNull(),
  )
  act(() => fake().connection({ state: 'open' }))
  await push(welcome())
  await push(frame({ status: 'running', tracks: [track('T011')] }))
  await screen.findAllByRole('table')
  return userEvent.setup()
}

/** Select the track, open Respond and choose "Report up the chain" (option 3), then Enter. */
async function openForm(user: Awaited<ReturnType<typeof running>>) {
  await user.keyboard('{Tab}r3{Enter}')
  return screen.findByRole('dialog', { name: 'Contact report: T011' })
}

describe('the report form values', () => {
  const briefing = welcome().briefing

  it('prefills bearing, range and heading from the track relative to the site, and defaults count to 1', () => {
    const values = prefillReport(track('T1'), briefing, null)
    // track at (100 E, 200 N): bearing 26.6 degrees, range 223.6 m; course 116.6 degrees
    expect(values).toEqual({
      what: '',
      bearing: '27',
      range: '224',
      count: '1',
      heading: '117',
      confidence: '',
    })
    expect(prefillReport(track('T1'), briefing, 'bird').what).toBe('bird')
  })

  it('builds the payload with confidence as a fraction', () => {
    const check = checkReport('T1', {
      what: 'rotary-small',
      bearing: '48.5',
      range: '1820',
      count: '2',
      heading: '215',
      confidence: '70',
    })
    expect(check.errors).toEqual({})
    expect(check.payload).toEqual({
      track: 'T1',
      class_id: 'rotary-small',
      count: 2,
      bearing_deg: 48.5,
      range_m: 1820,
      heading_deg: 215,
      confidence: 0.7,
    })
  })

  it('leaves out every empty field and accepts a form with nothing in it', () => {
    const empty = { what: '', bearing: '', range: '', count: '', heading: '', confidence: '' }
    expect(checkReport('T1', empty)).toEqual({ errors: {}, payload: { track: 'T1' } })
  })

  it('names each field that is out of range', () => {
    const bad = checkReport('T1', {
      what: '',
      bearing: '360',
      range: '50001',
      count: '0',
      heading: '-1',
      confidence: '101',
    })
    expect(bad.errors).toEqual({
      bearing: 'bearing',
      range: 'range',
      count: 'count',
      heading: 'heading',
      confidence: 'confidence',
    })
    expect(bad.payload).toBeNull()
    expect(
      checkReport('T1', { ...prefillReport(track('T1'), welcome().briefing, null), count: '2.5' })
        .errors.count,
    ).toBe('count')
    expect(
      checkReport('T1', {
        what: '',
        bearing: 'abc',
        range: '',
        count: '',
        heading: '',
        confidence: '',
      }).errors.bearing,
    ).toBe('bearing')
  })

  it('takes the edges of the ranges', () => {
    const edge = checkReport('T1', {
      what: '',
      bearing: '359.9',
      range: '50000',
      count: '99',
      heading: '0',
      confidence: '0',
    })
    expect(edge.errors).toEqual({})
    expect(edge.payload).toMatchObject({
      count: 99,
      bearing_deg: 359.9,
      range_m: 50000,
      confidence: 0,
    })
  })

  it('asks for bearing and range together', () => {
    const only = checkReport('T1', {
      what: '',
      bearing: '90',
      range: '',
      count: '',
      heading: '',
      confidence: '',
    })
    expect(only.errors).toEqual({ range: 'pair' })
    const other = checkReport('T1', {
      what: '',
      bearing: '',
      range: '800',
      count: '',
      heading: '',
      confidence: '',
    })
    expect(other.errors).toEqual({ bearing: 'pair' })
  })

  it('agrees with the scripted session on what is out of range', () => {
    expect(reportProblem({ track: 'T1', count: 100 })).toMatch(/count/)
    expect(reportProblem({ track: 'T1', bearing_deg: 360 })).toMatch(/bearing_deg/)
    expect(reportProblem({ track: 'T1', confidence: 1.1 })).toMatch(/confidence/)
    expect(reportProblem({ track: 'T1', class_id: 'tank' })).toMatch(/class_id/)
    expect(
      reportProblem({ track: 'T1', count: 2, bearing_deg: 10, range_m: 5, confidence: 1 }),
    ).toBeNull()
    expect(reportProblem({ track: 'T1' })).toBeNull()
  })
})

describe('the contact report form in the workspace', () => {
  it('opens on Report up the chain with the track values filled in and focus inside', async () => {
    const user = await running()
    const dialog = await openForm(user)
    expect(fake().sent).toEqual([])
    expect(within(dialog).getByLabelText('Bearing (°)')).toHaveValue('27')
    expect(within(dialog).getByLabelText('Range (m)')).toHaveValue('224')
    expect(within(dialog).getByLabelText('How many')).toHaveValue('1')
    expect(within(dialog).getByLabelText('Heading (°)')).toHaveValue('117')
    expect(within(dialog).getByLabelText('Confidence (%)')).toHaveValue('')
    expect(within(dialog).getByLabelText('What')).toHaveValue('')
  })

  it('is filled and filed from the keyboard: digit chooses the class, Enter files', async () => {
    const user = await running()
    const dialog = await openForm(user)
    const what = within(dialog).getByLabelText('What')
    await act(async () => what.focus())
    await user.keyboard('1')
    expect(what).toHaveValue('rotary-small')
    await user.keyboard('4')
    expect(what).toHaveValue('unknown')
    await user.keyboard('0')
    expect(what).toHaveValue('')
    await user.keyboard('1')
    const bearing = within(dialog).getByLabelText('Bearing (°)')
    await user.clear(bearing)
    await user.type(bearing, '48')
    const count = within(dialog).getByLabelText('How many')
    await user.clear(count)
    await user.type(count, '2')
    const confidence = within(dialog).getByLabelText('Confidence (%)')
    await user.type(confidence, '70{Enter}')
    expect(fake().sent.at(-1)).toEqual({
      action: 'report',
      payload: {
        track: 'T011',
        class_id: 'rotary-small',
        count: 2,
        bearing_deg: 48,
        range_m: 224,
        heading_deg: 117,
        confidence: 0.7,
      },
    })
    expect(screen.queryByRole('dialog', { name: 'Contact report: T011' })).not.toBeInTheDocument()
  })

  it('shows an inline error per field, moves focus to the first, and sends nothing', async () => {
    const user = await running()
    const dialog = await openForm(user)
    const bearing = within(dialog).getByLabelText('Bearing (°)')
    await user.clear(bearing)
    await user.type(bearing, '400')
    const count = within(dialog).getByLabelText('How many')
    await user.clear(count)
    await user.type(count, '0')
    await user.click(within(dialog).getByLabelText('Confidence (%)'))
    await user.keyboard('150{Enter}')
    expect(fake().sent).toEqual([])
    expect(within(dialog).getByText('Enter a bearing from 0 to under 360.')).toBeInTheDocument()
    expect(within(dialog).getByText('Enter a whole number from 1 to 99.')).toBeInTheDocument()
    expect(within(dialog).getByText('Enter a percentage from 0 to 100.')).toBeInTheDocument()
    expect(within(dialog).getByTestId('report-errors')).toHaveTextContent('The report has errors')
    expect(bearing).toHaveAttribute('aria-invalid', 'true')
    expect(bearing).toHaveFocus()
    // fixing the fields clears the errors and the report goes
    await user.clear(bearing)
    await user.type(bearing, '40')
    await user.clear(count)
    await user.type(count, '3')
    const confidence = within(dialog).getByLabelText('Confidence (%)')
    await user.clear(confidence)
    await user.type(confidence, '80{Enter}')
    expect(fake().sent.at(-1)?.payload).toMatchObject({
      count: 3,
      bearing_deg: 40,
      confidence: 0.8,
    })
  })

  it('cancels with Escape and sends nothing', async () => {
    const user = await running()
    const dialog = await openForm(user)
    // a browser moves focus into the modal; jsdom does not
    await act(async () => within(dialog).getByLabelText('What').focus())
    await user.keyboard('{Escape}')
    expect(screen.queryByRole('dialog', { name: 'Contact report: T011' })).not.toBeInTheDocument()
    expect(fake().sent).toEqual([])
  })

  it('files a bare report with Skip details', async () => {
    const user = await running()
    const dialog = await openForm(user)
    await user.click(within(dialog).getByRole('button', { name: 'Skip details' }))
    expect(fake().sent).toEqual([{ action: 'report', payload: { track: 'T011' } }])
    expect(screen.queryByRole('dialog', { name: 'Contact report: T011' })).not.toBeInTheDocument()
  })

  it('files with the File report button', async () => {
    const user = await running()
    const dialog = await openForm(user)
    await user.click(within(dialog).getByRole('button', { name: 'File report' }))
    expect(fake().sent.at(-1)).toEqual({
      action: 'report',
      payload: { track: 'T011', count: 1, bearing_deg: 27, range_m: 224, heading_deg: 117 },
    })
  })

  it('shows the outcome in the event log and the verdict area', async () => {
    const user = await running()
    const dialog = await openForm(user)
    await user.click(within(dialog).getByRole('button', { name: 'File report' }))
    await push(
      frame({
        status: 'running',
        tick: 30,
        tracks: [track('T011')],
        events: [
          verdictEvent(11, {
            action: 'report',
            permitted: true,
            code: 'permitted',
            rule_id: 'track-everything',
          }),
          event(12, 'action.report', {
            track: 'T011',
            class_id: 'rotary-small',
            count: 2,
            bearing_deg: 48,
            range_m: 1820,
            heading_deg: 215,
            confidence: 0.7,
          }),
        ],
      }),
    )
    expect(
      await screen.findByText(
        'T011 reported: Small rotary, count 2, bearing 048, range 1.82 km, heading 215°, confidence 70%.'.replace(
          'bearing 048,',
          'bearing 048°,',
        ),
      ),
    ).toBeInTheDocument()
    expect(screen.getByTestId('verdict')).toHaveAttribute('data-permitted', 'true')
  })

  it('has the form in Hindi', async () => {
    const user = await running('hi')
    await user.keyboard('{Tab}r3{Enter}')
    const dialog = await screen.findByRole('dialog', { name: 'संपर्क रिपोर्ट: T011' })
    expect(within(dialog).getByRole('button', { name: 'रिपोर्ट दाखिल करें' })).toBeInTheDocument()
    expect(within(dialog).getByRole('button', { name: 'विवरण छोड़ें' })).toBeInTheDocument()
    expect(within(dialog).getByLabelText('दिशा (°)')).toHaveValue('27')
  })
})
