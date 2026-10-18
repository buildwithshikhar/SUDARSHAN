import { act, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeAll, describe, expect, it, vi } from 'vitest'
import { setLanguage } from '../../src/lib/prefs'
import type { Frame, LiveServerMessage, TraineeEvent } from '../../src/live/protocol'
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

// The EO view is a lazy chunk (three.js); load it once up front so no test waits on the transform.
beforeAll(async () => {
  await import('../../src/live/views/EoView')
}, 60_000)

const fake = () => holder.current as unknown as FakeTransport
const push = (message: LiveServerMessage) => act(() => fake().push(message))
const connection = (info: Parameters<FakeTransport['connection']>[0]) =>
  act(() => fake().connection(info))

const LOG_OK = {
  verified: true,
  first_bad_seq: null,
  event_count: 31,
  head: 'a'.repeat(64),
  final_state_hash: 'b'.repeat(64),
  events: [],
}

function signedIn(
  role: 'trainee' | 'instructor' | 'admin' = 'trainee',
  extra = {},
  language = 'en',
) {
  // a stale transport from the previous test must not satisfy the wait for the new one
  holder.current = null
  return mockApi({
    'GET /api/v1/version': { body: version() },
    'GET /api/v1/auth/me': { body: session(makeUser(role, { language })) },
    'GET /api/v1/sessions/abc/log': { body: LOG_OK },
    'GET /api/v1/sessions/abc': {
      body: {
        id: 'abc',
        status: 'ended',
        ticks: 640,
        started_at: '2026-10-18T09:00:00+00:00',
        ended_at: '2026-10-18T09:00:32+00:00',
      },
    },
    ...extra,
  })
}

const two = (extra: Partial<Frame> = {}) =>
  frame({
    tracks: [track('T011'), track('T012', { class_estimate: 'bird', class_support: 0.64 })],
    ...extra,
  })

/** Open the workspace and bring it to a running session with two tracks. */
async function running(extra: Partial<Frame> = {}, language = 'en', eoCamera?: 'thermal' | 'nv') {
  signedIn('trainee', {}, language)
  renderApp('/train/session/abc')
  await waitFor(() =>
    expect((holder.current as FakeTransport | null)?.handlers ?? null).not.toBeNull(),
  )
  connection({ state: 'open' })
  const w = welcome()
  const f = two({ status: 'running', ...extra })
  if (eoCamera) {
    // the same EO sensor, as a thermal camera ('ir') or a night-vision one
    const site = w.briefing.sensors.find((s) => s.id === 'eo-1')
    if (site) {
      site.profile = eoCamera === 'thermal' ? 'ir-generic-thermal' : 'eo-generic-nv'
      if (eoCamera === 'thermal') site.modality = 'ir'
    }
    const live = f.sensors.find((s) => s.id === 'eo-1')
    if (live && eoCamera === 'thermal') live.modality = 'ir'
  }
  await push(w)
  await push(f)
  await screen.findAllByRole('table')
  return userEvent.setup()
}

describe('opening a session', () => {
  it('says it is connecting until the welcome arrives', async () => {
    signedIn()
    renderApp('/train/session/abc')
    await waitFor(() => expect(screen.getByText('Connecting to the session')).toBeInTheDocument())
  })

  it('shows the briefing and a Begin button in the lobby state, and sends start', async () => {
    signedIn()
    renderApp('/train/session/abc')
    await waitFor(() =>
      expect((holder.current as FakeTransport | null)?.handlers ?? null).not.toBeNull(),
    )
    connection({ state: 'open' })
    await push(welcome())
    await push(frame({ status: 'lobby', tracks: [] }))
    expect(
      await screen.findByRole('heading', { name: 'Harrier Field: afternoon watch' }),
    ).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Begin session' }))
    expect(fake().control).toContain('start')
  })

  it('shows the permanent label, the ROE pack version and the link state in the top bar', async () => {
    await running()
    expect(screen.getByText('Fictional scenario · open-source parameters')).toBeInTheDocument()
    const bar = screen.getAllByRole('banner')[0]!
    expect(within(bar).getByText('training-baseline 1.0.0')).toBeInTheDocument()
    expect(within(bar).getByText('Connected')).toBeInTheDocument()
  })

  it('shows the empty state while no contact is held', async () => {
    signedIn()
    renderApp('/train/session/abc')
    await waitFor(() =>
      expect((holder.current as FakeTransport | null)?.handlers ?? null).not.toBeNull(),
    )
    connection({ state: 'open' })
    await push(welcome())
    await push(frame({ status: 'running', tracks: [] }))
    expect(await screen.findByText('No contacts. Sensors are scanning.')).toBeInTheDocument()
  })

  it('says the EO view is unavailable when WebGL is missing, and still works around it', async () => {
    await running()
    expect(screen.getByText('EO view unavailable (WebGL)')).toBeInTheDocument()
    expect(screen.getByRole('table', { name: 'Tracks held by the tracker' })).toBeInTheDocument()
  })

  it('offers only the day picture for a day camera, with no night-vision or thermal wording', async () => {
    await running()
    const mode = screen.getByRole('group', { name: 'Mode' })
    expect(
      within(mode)
        .getAllByRole('button')
        .map((b) => b.textContent),
    ).toEqual(['Day TV'])
    expect(screen.queryByText(/thermal|night/i)).not.toBeInTheDocument()
  })

  it('offers both thermal polarities for a thermal camera, and switches with the keyboard', async () => {
    const user = await running({}, 'en', 'thermal')
    const mode = screen.getByRole('group', { name: 'Mode' })
    const buttons = within(mode).getAllByRole('button')
    expect(buttons.map((b) => b.textContent)).toEqual(['White-hot', 'Black-hot'])
    expect(buttons[0]).toHaveAttribute('aria-pressed', 'true')
    buttons[1]?.focus()
    await user.keyboard('{Enter}')
    expect(buttons[1]).toHaveAttribute('aria-pressed', 'true')
    expect(buttons[0]).toHaveAttribute('aria-pressed', 'false')
    // no day or night-vision picture is offered for a thermal sensor
    expect(within(mode).queryByRole('button', { name: /Day TV|Night vision/ })).toBeNull()
    expect(screen.getByRole('button', { name: 'About this picture' })).toBeInTheDocument()
  })

  it('offers the night-vision picture alone for a night-vision camera', async () => {
    await running({}, 'en', 'nv')
    const mode = screen.getByRole('group', { name: 'Mode' })
    expect(
      within(mode)
        .getAllByRole('button')
        .map((b) => b.textContent),
    ).toEqual(['Night vision'])
  })

  it('has the graphics control next to the mode, starting on Auto', async () => {
    await running()
    const graphics = screen.getByRole('group', { name: 'Graphics' })
    expect(within(graphics).getByRole('button', { name: 'Auto' })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
  })
})

describe('connection states', () => {
  it('shows a reconnecting banner over the frozen picture', async () => {
    await running()
    await connection({ state: 'reconnecting', closeCode: 1006, attempt: 2 })
    expect(await screen.findByText(/Connection lost\. Reconnecting, attempt 2/)).toBeInTheDocument()
    expect(screen.getByRole('table', { name: 'Tracks held by the tracker' })).toBeInTheDocument()
  })

  it.each([
    [4403, 'Session not available to you'],
    [4404, 'Session not found'],
    [4401, 'Not signed in'],
    [4408, 'Opened in another window'],
    [1013, 'Server is full'],
  ])('explains close code %i when the session never opened', async (code, title) => {
    signedIn()
    renderApp('/train/session/abc')
    await waitFor(() =>
      expect((holder.current as FakeTransport | null)?.handlers ?? null).not.toBeNull(),
    )
    await connection({ state: 'closed', closeCode: code })
    expect(await screen.findByText(title)).toBeInTheDocument()
    expect(screen.getByTestId('session-failure')).toHaveAttribute('data-code', String(code))
  })

  it('turns 4409 into the ended view and reads the stored log', async () => {
    signedIn()
    renderApp('/train/session/abc')
    await waitFor(() =>
      expect((holder.current as FakeTransport | null)?.handlers ?? null).not.toBeNull(),
    )
    await connection({ state: 'closed', closeCode: 4409 })
    expect(await screen.findByText('Event log verified')).toBeInTheDocument()
    expect(screen.getByText('640')).toBeInTheDocument()
  })
})

describe('session ended view', () => {
  const ended: LiveServerMessage = {
    t: 'ended',
    status: 'ended',
    summary: {
      ticks: 1280,
      duration_s: 64.02,
      event_count: 112,
      head: 'c4'.repeat(32),
      final_state_hash: '7b'.repeat(32),
      verified: true,
    },
  }

  it('shows ticks, duration, events and that the event log verified, with a link to the debrief', async () => {
    await running()
    await push(ended)
    expect(
      await screen.findByRole('heading', { name: 'Session ended', level: 1 }),
    ).toBeInTheDocument()
    expect(await screen.findByText('Event log verified')).toBeInTheDocument()
    expect(screen.getByText('1280')).toBeInTheDocument()
    expect(screen.getByText('01:04.0')).toBeInTheDocument()
    expect(screen.getByText('112')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Open the debrief' })).toHaveAttribute(
      'href',
      '/train/session/abc/debrief',
    )
    expect(screen.queryByText(/score:/i)).not.toBeInTheDocument()
  })

  it('names the failing sequence number when the log does not verify', async () => {
    signedIn('trainee', {
      'GET /api/v1/sessions/abc/log': { body: { ...LOG_OK, verified: false, first_bad_seq: 41 } },
    })
    renderApp('/train/session/abc')
    await waitFor(() =>
      expect((holder.current as FakeTransport | null)?.handlers ?? null).not.toBeNull(),
    )
    connection({ state: 'open' })
    await push(welcome())
    await push(two({ status: 'running' }))
    await push(ended)
    expect(
      await screen.findByText('Event log failed verification at sequence 41'),
    ).toBeInTheDocument()
  })

  it('has an error state with a retry when the log cannot be read', async () => {
    signedIn('trainee', { 'GET /api/v1/sessions/abc/log': { status: 500, body: { detail: 'x' } } })
    renderApp('/train/session/abc')
    await waitFor(() =>
      expect((holder.current as FakeTransport | null)?.handlers ?? null).not.toBeNull(),
    )
    connection({ state: 'open' })
    await push(welcome())
    await push(two({ status: 'running' }))
    await push(ended)
    expect(await screen.findByText('The event log could not be read')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument()
  })
})

describe('track table', () => {
  it('lists the tracks with class, assist, bearing and range, and marks reference data', async () => {
    await running({
      assist: [
        {
          track: 'T011',
          tick: 20,
          flag: 'threat',
          confidence: 0.83,
          proposed_class: 'rotary-small',
          source: 'simulated assist',
          basis: 'configured rates',
          data_status: 'reference',
        },
      ],
    })
    const table = screen.getByRole('table', { name: 'Tracks held by the tracker' })
    const row = within(table).getByRole('button', { name: 'T011' }).closest('tr')!
    expect(row).toHaveTextContent('Small rotary')
    expect(row).toHaveTextContent('71%')
    expect(row).toHaveTextContent('Threat 83%')
    expect(row).toHaveTextContent('REF')
    expect(within(table).getByText('Assist (simulated AI)')).toBeInTheDocument()
    expect(screen.getByText(/Reference data: parameters not yet verified/)).toBeInTheDocument()
    expect(screen.getByText('2 tracks')).toBeInTheDocument()
  })

  it('selects a track by click and shows its detail with the RF link feature', async () => {
    await running({
      reports: [
        {
          tick: 20,
          sensor_id: 'rf-1',
          modality: 'rf',
          azimuth_deg: 343,
          elevation_deg: 2,
          range_m: null,
          radial_speed_mps: null,
          reported_class: null,
          sigma_azimuth_deg: 6.5,
          sigma_elevation_deg: 12,
          sigma_range_m: null,
          sigma_radial_mps: null,
          features: { band: '2.4 GHz', rssi_dbm: -71.4, hopping: true, hop_rate_hz: 41.6 },
          data_status: 'reference',
        },
      ],
      sensors: [
        ...frame().sensors,
        {
          id: 'rf-1',
          modality: 'rf',
          position: { x: 212, y: -158, z: 5 },
          bearing_deg: 0,
          elevation_deg: 0,
          fov_deg: null,
          cued: false,
          supports_cue: false,
          outage: false,
          data_status: 'reference',
        },
      ],
    })
    await userEvent.click(screen.getByRole('button', { name: 'T011' }))
    const detail = screen.getByRole('region', { name: 'Selected track' })
    expect(within(detail).getByText('RF link')).toBeInTheDocument()
    expect(detail).toHaveTextContent('2.4 GHz · hopping 41.6 Hz · -71.4 dBm')
  })
})

describe('the keyboard flow', () => {
  it('selects tracks with Tab and Shift+Tab, and hands Tab back at the ends', async () => {
    const user = await running()
    const pressed = () =>
      screen
        .getAllByRole('button', { pressed: true })
        .map((b) => b.textContent)
        .filter((t) => /^T01/.test(t ?? ''))
    await user.keyboard('{Tab}')
    expect(pressed()).toEqual(['T011'])
    await user.keyboard('{Tab}')
    expect(pressed()).toEqual(['T012'])
    await user.keyboard('{Shift>}{Tab}{/Shift}')
    expect(pressed()).toEqual(['T011'])
    // at the last track Tab is not captured, so the browser can move on
    await user.keyboard('{Tab}')
    const keep = vi.fn()
    window.addEventListener('keydown', (e) => keep(e.defaultPrevented), { once: true })
    await user.keyboard('{Tab}')
    expect(keep).toHaveBeenCalledWith(false)
  })

  it('does nothing for letters without a selected track and ignores Space', async () => {
    const user = await running()
    await user.keyboard('chars ')
    expect(fake().sent).toEqual([])
    expect(screen.getAllByText('No track selected')).toHaveLength(2)
  })

  it('classifies, assesses and responds with C, A, R, digits and Enter', async () => {
    const user = await running()
    await user.keyboard('{Tab}c')
    expect(screen.getByRole('list', { name: 'Classify' })).toBeInTheDocument()
    await user.keyboard('1{Enter}')
    expect(fake().sent.at(-1)).toEqual({
      action: 'classify',
      payload: { track: 'T011', class_id: 'rotary-small' },
    })
    // the panel moved on to Assess by itself
    expect(screen.getByRole('list', { name: 'Assess' })).toBeInTheDocument()
    await user.keyboard('1{Enter}')
    expect(fake().sent.at(-1)).toEqual({
      action: 'assess',
      payload: { track: 'T011', identity: 'hostile' },
    })
    await user.keyboard('1')
    // choosing a response shows the rule that would permit it, with the pack version
    expect(
      screen.getByText('Suspect contact in the outer zone may receive a class A response'),
    ).toBeInTheDocument()
    expect(screen.getByText(/training-baseline 1.0.0 · authority: operator/)).toBeInTheDocument()
    await user.keyboard('{Enter}')
    expect(fake().sent.at(-1)).toEqual({
      action: 'engage',
      payload: { track: 'T011', effector_class: 'ec-a' },
    })
    expect(fake().sent).toHaveLength(3)
  })

  it('cancels a step with Escape without sending anything', async () => {
    const user = await running()
    await user.keyboard('{Tab}r1{Escape}')
    expect(fake().sent).toEqual([])
    expect(screen.queryByRole('list', { name: 'Respond' })).not.toBeInTheDocument()
  })

  it('holds fire with H and shows the default-hold verdict when it comes back', async () => {
    const user = await running()
    await user.keyboard('{Tab}h')
    expect(fake().sent.at(-1)).toEqual({ action: 'hold', payload: { track: 'T011' } })
    await push(
      two({
        tick: 21,
        events: [
          verdictEvent(1, {
            action: 'hold',
            permitted: true,
            code: 'default-hold',
            rule_id: null,
            rule_title: null,
            authority: null,
            detail: {},
          }),
        ],
      }),
    )
    const verdict = await screen.findByTestId('verdict')
    expect(verdict).toHaveAttribute('data-permitted', 'true')
    expect(verdict).toHaveTextContent('PERMITTED')
    expect(verdict).toHaveTextContent('Hold fire is the default action')
  })

  it('opens the shortcut dialog with ?', async () => {
    const user = await running()
    await user.keyboard('?')
    const dialog = screen.getByRole('dialog', { name: 'Keyboard shortcuts' })
    expect(within(dialog).getByText('Open the Classify step')).toBeInTheDocument()
    expect(within(dialog).getByText(/Space is not used/)).toBeInTheDocument()
  })
})

describe('a blocked response', () => {
  const blocked = (seq = 5): TraineeEvent => verdictEvent(seq)

  it('shows BLOCKED with the rule text, the pack version and every unmet condition, and stays', async () => {
    const user = await running()
    await user.keyboard('{Tab}r1{Enter}')
    await push(two({ tick: 22, events: [blocked()] }))
    const verdict = await screen.findByTestId('verdict')
    expect(verdict).toHaveAttribute('data-permitted', 'false')
    expect(verdict).toHaveAttribute('role', 'alert')
    expect(verdict).toHaveTextContent('BLOCKED')
    expect(verdict).toHaveTextContent(
      'Suspect contact in the outer zone may receive a class A response',
    )
    expect(verdict).toHaveTextContent('training-baseline 1.0.0')
    const rows = within(verdict)
      .getAllByRole('row')
      .slice(1)
      .map((r) => r.textContent)
    expect(rows).toEqual(['IdentitySuspect / Hostilenot set', 'Confidenceat least 60%40%'])
    // later frames do not clear it
    await push(two({ tick: 23 }))
    await push(two({ tick: 24, events: [event(6, 'track.confirm', { track: 'T011' })] }))
    expect(screen.getByTestId('verdict')).toHaveAttribute('data-permitted', 'false')
    // a classify verdict does not replace it either
    await push(
      two({
        tick: 25,
        events: [
          verdictEvent(7, {
            action: 'classify',
            permitted: true,
            code: 'permitted',
            rule_id: 'track-everything',
          }),
        ],
      }),
    )
    expect(screen.getByTestId('verdict')).toHaveAttribute('data-permitted', 'false')
  })

  it('is replaced by the next response verdict', async () => {
    await running()
    await push(two({ tick: 22, events: [blocked()] }))
    await screen.findByTestId('verdict')
    await push(
      two({
        tick: 23,
        events: [
          verdictEvent(6, {
            permitted: true,
            code: 'permitted',
            detail: { effector_class: 'ec-a' },
          }),
        ],
      }),
    )
    await waitFor(() =>
      expect(screen.getByTestId('verdict')).toHaveAttribute('data-permitted', 'true'),
    )
  })

  it('is dismissed by the button or the X key', async () => {
    const user = await running()
    await push(two({ tick: 22, events: [blocked()] }))
    await user.click(await screen.findByRole('button', { name: /Dismiss/ }))
    expect(screen.queryByTestId('verdict')).not.toBeInTheDocument()
    await push(two({ tick: 23, events: [blocked(9)] }))
    await screen.findByTestId('verdict')
    await user.keyboard('x')
    expect(screen.queryByTestId('verdict')).not.toBeInTheDocument()
  })

  it('reads the effector gap and the authority gap in words', async () => {
    await running()
    await push(
      two({
        tick: 22,
        events: [
          verdictEvent(5, {
            code: 'effector',
            effector_class: 'ec-b',
            detail: { effector_class: 'ec-b', allowed: ['ec-a'] },
          }),
        ],
      }),
    )
    expect(await screen.findByTestId('verdict')).toHaveTextContent(
      'The closest rule does not list Effector class B (generic, kinetic). Allowed: Effector class A (generic, non-kinetic).',
    )
    await push(
      two({
        tick: 23,
        events: [
          verdictEvent(6, {
            code: 'authority',
            rule_id: 'hostile-inner-zone',
            authority: 'commander',
            detail: { required: 'commander' },
          }),
        ],
      }),
    )
    await waitFor(() =>
      expect(screen.getByTestId('verdict')).toHaveTextContent(
        'The closest rule needs commander authority. This session has none.',
      ),
    )
  })

  it('shows the same verdict in Hindi, with the rule title and pack version', async () => {
    setLanguage('hi')
    await running({}, 'hi')
    await push(two({ tick: 22, events: [blocked()] }))
    const verdict = await screen.findByTestId('verdict')
    expect(verdict).toHaveTextContent('अवरुद्ध')
    expect(verdict).toHaveTextContent(
      'बाहरी क्षेत्र में संदिग्ध संपर्क पर वर्ग A प्रतिक्रिया दी जा सकती है',
    )
    expect(verdict).toHaveTextContent('training-baseline 1.0.0')
    expect(verdict).toHaveTextContent('विश्वास')
    expect(verdict).toHaveTextContent('कम से कम 60%')
  })
})

describe('track management from the keyboard', () => {
  it('cues the EO sensor onto the selected track with U and shows the cue event', async () => {
    const user = await running()
    await user.keyboard('{Tab}u')
    expect(fake().sent.at(-1)).toEqual({
      action: 'sensor-cue',
      payload: { sensor: 'eo-1', track: 'T011', narrow: true },
    })
    await push(
      two({
        tick: 23,
        events: [
          event(8, 'sensor.cue', {
            sensor: 'eo-1',
            track: 'T011',
            bearing_deg: 41.2,
            elevation_deg: 3.1,
            fov_deg: 4.3,
            accepted: true,
            reason: null,
          }),
        ],
      }),
    )
    expect(
      await screen.findByText('Cue accepted: eo-1 onto T011, bearing 41.2°, field 4.3°.'),
    ).toBeInTheDocument()
  })

  it('shows a refused cue and a refused command with the server reason', async () => {
    await running()
    await push(
      two({
        tick: 23,
        events: [
          event(8, 'sensor.cue', {
            sensor: 'eo-1',
            track: 'T011',
            accepted: false,
            reason: 'sensor in outage',
          }),
          event(9, 'action.rejected', {
            action: 'track-relabel',
            reason: "label 'LEAD' is on track T012; exchange labels to take it",
            payload: {},
          }),
        ],
      }),
    )
    expect(
      await screen.findByText(/Cue refused: eo-1 onto T011\. sensor in outage/),
    ).toBeInTheDocument()
    expect(screen.getByText(/Refused: Relabel\. label 'LEAD' is on track T012/)).toBeInTheDocument()
  })

  it('relabels through a dialog (L), and the table follows the track.relabel event', async () => {
    const user = await running()
    await user.keyboard('{Tab}l')
    const dialog = screen.getByRole('dialog', { name: 'Relabel track T011' })
    const input = within(dialog).getByLabelText('New label')
    await user.clear(input)
    await user.type(input, 'LEAD-1{Enter}')
    expect(fake().sent.at(-1)).toEqual({
      action: 'track-relabel',
      payload: { track: 'T011', label: 'LEAD-1' },
    })
    await push(
      two({
        tick: 24,
        tracks: [track('T011', { label: 'LEAD-1' }), track('T012', { class_estimate: 'bird' })],
        events: [event(10, 'track.relabel', { track: 'T011', label: 'LEAD-1', previous: 'T011' })],
      }),
    )
    const table = screen.getByRole('table', { name: 'Tracks held by the tracker' })
    expect(within(table).getByRole('button', { name: 'LEAD-1' })).toBeInTheDocument()
    expect(screen.getByText("Track T011 relabelled 'LEAD-1' (was 'T011').")).toBeInTheDocument()
  })

  it('merges with M on a first track, Tab to a second, M again', async () => {
    const user = await running()
    await user.keyboard('{Tab}m')
    expect(screen.getByText('MERGE')).toBeInTheDocument()
    await user.keyboard('{Tab}m')
    expect(fake().sent.at(-1)).toEqual({
      action: 'track-merge',
      payload: { tracks: ['T011', 'T012'] },
    })
    expect(screen.queryByText('MERGE')).not.toBeInTheDocument()
  })

  it('splits with S and drops with D after a confirmation', async () => {
    const user = await running()
    await user.keyboard('{Tab}s')
    expect(fake().sent.at(-1)).toEqual({ action: 'track-split', payload: { track: 'T011' } })
    await user.keyboard('d')
    expect(screen.getByText(/Drop track T011\?/)).toBeInTheDocument()
    expect(fake().sent).toHaveLength(1)
    await user.keyboard('{Enter}')
    expect(fake().sent.at(-1)).toEqual({ action: 'track-drop', payload: { track: 'T011' } })
  })

  it('tells the operator an input was not sent while the link is down', async () => {
    const user = await running()
    fake().act = () => null
    await user.keyboard('{Tab}h')
    expect(screen.getByText(/Hold fire: refused \(not-connected\)/)).toBeInTheDocument()
  })
})

describe('who may open it', () => {
  it('turns an administrator away, since admins cannot play', async () => {
    signedIn('admin')
    renderApp('/train/session/abc')
    expect(await screen.findByRole('heading', { name: 'No access', level: 1 })).toBeInTheDocument()
  })

  it('leaves the session when the page goes away', async () => {
    signedIn()
    const { unmount } = renderApp('/train/session/abc')
    await waitFor(() =>
      expect((holder.current as FakeTransport | null)?.handlers ?? null).not.toBeNull(),
    )
    const transport = fake()
    unmount()
    expect(transport.control).toEqual(['leave', 'close'])
  })
})
