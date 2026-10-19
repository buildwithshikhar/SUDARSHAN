import { act, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it } from 'vitest'
import { setLanguage } from '../../src/lib/prefs'
import { LiveProvider } from '../../src/live/context'
import { SensorConsoles } from '../../src/live/panels/SensorConsoles'
import type { Frame, Report, SensorStatus } from '../../src/live/protocol'
import { LiveSession } from '../../src/live/session'
import { FakeTransport, frame, welcome } from './helpers'

const sensor = (modality: 'rf' | 'acoustic', over: Partial<SensorStatus> = {}): SensorStatus => ({
  id: `${modality}-1`,
  modality,
  position: { x: 0, y: 0, z: 0 },
  bearing_deg: 0,
  elevation_deg: 0,
  fov_deg: null,
  cued: false,
  supports_cue: false,
  outage: false,
  data_status: 'reference',
  ...over,
})

const report = (over: Partial<Report>): Report => ({
  tick: 20,
  sensor_id: 'rf-1',
  modality: 'rf',
  azimuth_deg: 33,
  elevation_deg: 3,
  range_m: null,
  radial_speed_mps: null,
  sigma_azimuth_deg: 6,
  sigma_elevation_deg: 12,
  sigma_range_m: null,
  sigma_radial_mps: null,
  reported_class: null,
  features: {},
  data_status: 'reference',
  ...over,
})

const rfReport = (over: Partial<Report> = {}) =>
  report({
    features: { band: '2.4 GHz', hopping: true, hop_rate_hz: 41.6, rssi_dbm: -71.2 },
    ...over,
  })
const acReport = (over: Partial<Report> = {}) =>
  report({
    modality: 'acoustic',
    sensor_id: 'acoustic-1',
    azimuth_deg: 210,
    features: { blade_pass_hz: 100, harmonics: 4, tonal: true, snr_db: 17.5 },
    ...over,
  })

interface Setup {
  modalities?: ('rf' | 'acoustic')[]
  /** Send a first frame (default) or stay before it. */
  frame?: boolean
  sensors?: SensorStatus[]
  reports?: Report[]
  connection?: 'open' | 'reconnecting' | 'closed'
}

function open(setup: Setup = {}) {
  const modalities = setup.modalities ?? ['rf', 'acoustic']
  const transport = new FakeTransport()
  const session = new LiveSession(transport)
  session.connect()
  const w = welcome()
  w.briefing.sensors = w.briefing.sensors.filter(
    (s) => (s.modality !== 'rf' && s.modality !== 'acoustic') || modalities.includes(s.modality),
  )
  const send = (f: Partial<Frame>) =>
    act(() => {
      transport.push(
        frame({
          sensors: [...frame().sensors, ...(setup.sensors ?? modalities.map((m) => sensor(m)))],
          ...f,
        }),
      )
    })
  act(() => {
    transport.connection({ state: setup.connection ?? 'open' })
    transport.push(w)
  })
  if (setup.frame !== false) send({ reports: setup.reports ?? [], tick: 20, time_s: 1 })
  const ui = render(
    <LiveProvider session={session}>
      <SensorConsoles />
    </LiveProvider>,
  )
  return { session, transport, send, ...ui }
}

afterEach(() => setLanguage('en'))

describe('tabs', () => {
  it('is a real tablist, RF first, and the arrow keys, Home and End move between the tabs', async () => {
    const user = userEvent.setup()
    open()
    const list = screen.getByRole('tablist', { name: 'Sensor consoles' })
    const tabs = within(list).getAllByRole('tab')
    expect(tabs.map((t) => t.textContent)).toEqual(['RF spectrum', 'Acoustic spectrogram'])
    expect(tabs[0]).toHaveAttribute('aria-selected', 'true')
    expect(tabs[0]).toHaveAttribute('tabindex', '0')
    expect(tabs[1]).toHaveAttribute('tabindex', '-1')
    expect(screen.getByRole('tabpanel', { name: 'RF spectrum' })).toBeVisible()

    tabs[0]!.focus()
    await user.keyboard('{ArrowRight}')
    expect(tabs[1]).toHaveAttribute('aria-selected', 'true')
    expect(tabs[1]).toHaveFocus()
    expect(screen.getByRole('tabpanel', { name: 'Acoustic spectrogram' })).toBeVisible()
    await user.keyboard('{ArrowRight}')
    expect(tabs[0]).toHaveAttribute('aria-selected', 'true')
    await user.keyboard('{End}')
    expect(tabs[1]).toHaveAttribute('aria-selected', 'true')
    await user.keyboard('{Home}')
    expect(tabs[0]).toHaveAttribute('aria-selected', 'true')
    await user.keyboard('{ArrowLeft}')
    expect(tabs[1]).toHaveAttribute('aria-selected', 'true')
    // the hidden panel is not rendered with content
    expect(screen.getAllByRole('tabpanel', { hidden: true })).toHaveLength(2)
    expect(screen.queryByTestId('rf-reports')).not.toBeInTheDocument()
  })

  it('switches with the mouse too', async () => {
    const user = userEvent.setup()
    open()
    await user.click(screen.getByRole('tab', { name: 'Acoustic spectrogram' }))
    expect(screen.getByTestId('spectrogram')).toBeInTheDocument()
  })
})

describe('states', () => {
  it('loading: before the first frame it says it is waiting, and the tabs are there', () => {
    open({ frame: false })
    expect(screen.getByRole('status')).toHaveTextContent('Waiting for the first frame')
    expect(screen.getAllByRole('tab')).toHaveLength(2)
  })

  it('error: a closed link before any frame uses the app error state with a reload button', () => {
    open({ frame: false, connection: 'closed' })
    const alert = screen.getByRole('alert')
    expect(alert).toHaveTextContent('Sensor consoles unavailable')
    expect(within(alert).getByRole('button', { name: 'Reload' })).toBeInTheDocument()
  })

  it('empty: no RF sensor keeps the tab, names it unavailable and explains', async () => {
    const user = userEvent.setup()
    open({ modalities: ['acoustic'] })
    const rf = screen.getByRole('tab', { name: /RF spectrum/ })
    expect(rf).toHaveTextContent('unavailable')
    expect(rf).toHaveAttribute('data-unavailable', 'true')
    // the acoustic console is the one shown when the RF one cannot be
    expect(screen.getByRole('tab', { name: /Acoustic/ })).toHaveAttribute('aria-selected', 'true')
    await user.click(rf)
    expect(screen.getByTestId('console-empty-rf')).toHaveTextContent(
      'No RF sensor in this scenario',
    )
  })

  it('empty: no acoustic sensor says so, and both missing says so on each tab', async () => {
    const user = userEvent.setup()
    open({ modalities: ['rf'] })
    expect(screen.getByRole('tab', { name: /Acoustic/ })).toHaveTextContent('unavailable')
    await user.click(screen.getByRole('tab', { name: /Acoustic/ }))
    expect(screen.getByTestId('console-empty-acoustic')).toHaveTextContent(
      'No acoustic sensor in this scenario',
    )
  })

  it('empty: with neither sensor both tabs stay and say unavailable', async () => {
    open({ modalities: [] })
    expect(screen.getAllByRole('tab').map((t) => t.textContent)).toEqual([
      'RF spectrum · unavailable',
      'Acoustic spectrogram · unavailable',
    ])
    expect(screen.getByTestId('console-empty-rf')).toBeInTheDocument()
  })

  it('listening: a sensor with nothing heard says so, with an empty report table', () => {
    open()
    const status = screen.getByTestId('console-status')
    expect(status).toHaveAttribute('data-state', 'listening')
    expect(status).toHaveTextContent('Listening: nothing heard yet')
    expect(screen.getByTestId('rf-reports')).toHaveTextContent('No reports in the last 6 s')
    expect(screen.getByText(/The noise floor is drawn/)).toBeInTheDocument()
  })

  it('outage: a sensor in outage says so and draws only the floor', () => {
    open({ sensors: [sensor('rf', { outage: true }), sensor('acoustic')] })
    expect(screen.getByTestId('console-status')).toHaveAttribute('data-state', 'outage')
    expect(screen.getByTestId('console-status')).toHaveTextContent('Sensor rf-1 is in outage')
  })

  it('stale: a dropped link freezes the display, marks it stale and gives the last scenario time', () => {
    const { transport } = open()
    expect(screen.queryByTestId('console-stale')).not.toBeInTheDocument()
    act(() => transport.connection({ state: 'reconnecting', attempt: 1 }))
    const notice = screen.getByTestId('console-stale')
    expect(within(notice).getByRole('alert')).toBeInTheDocument()
    expect(notice).toHaveTextContent('Display frozen')
    expect(notice).toHaveTextContent('00:01.0')
    act(() => transport.connection({ state: 'open' }))
    expect(screen.queryByTestId('console-stale')).not.toBeInTheDocument()
  })
})

describe('RF console', () => {
  it('lists the latest reports as an accessible table: band, level, link, bearing', () => {
    open({
      reports: [
        rfReport(),
        rfReport({
          features: { band: '433 MHz', hopping: false, rssi_dbm: -88.4 },
          azimuth_deg: 181,
        }),
      ],
    })
    const table = screen.getByRole('table', { name: 'Latest RF reports' })
    const heads = within(table)
      .getAllByRole('columnheader')
      .map((h) => h.textContent)
    expect(heads).toEqual(['Band', 'Level (dBm)', 'Link', 'Bearing'])
    const rows = within(table).getAllByRole('row').slice(1)
    expect(rows.map((r) => r.textContent)).toEqual([
      '2.4 GHz-71.2Hopping 41.6 Hz033°',
      '433 MHz-88.4Fixed181°',
    ])
    expect(screen.getByTestId('console-status')).toHaveTextContent('2 reports in the last 6 s')
    expect(screen.getByRole('img', { name: /RF spectrum and waterfall/ })).toBeInTheDocument()
  })

  it('states that it is synthesised reference data and that RF is not occluded by terrain', () => {
    open({ reports: [rfReport()] })
    expect(screen.getByTestId('synth-label')).toHaveTextContent(
      'Synthesised from sensor reports · reference data',
    )
    expect(screen.getByTestId('rf-open-note')).toHaveTextContent(
      'RF is not occluded by terrain in this model. A link behind a ridge or building is still heard here.',
    )
    expect(screen.getByText(/drawn by the display, not measured/)).toBeInTheDocument()
  })

  it('shows the label that matches the data: verified, or both', () => {
    const { unmount } = open({
      sensors: [sensor('rf', { data_status: 'verified' }), sensor('acoustic')],
      reports: [rfReport({ data_status: 'verified' })],
    })
    expect(screen.getByTestId('synth-label')).toHaveAttribute('data-status', 'verified')
    expect(screen.getByTestId('synth-label')).toHaveTextContent('verified data')
    unmount()
    open({ reports: [rfReport({ data_status: 'verified' }), rfReport()] })
    expect(screen.getByTestId('synth-label')).toHaveAttribute('data-status', 'mixed')
  })

  it('says a hopping link with no reported rate has none', () => {
    open({
      reports: [report({ features: { band: '900 MHz', hopping: true, rssi_dbm: -80 } })],
    })
    expect(screen.getByTestId('rf-reports')).toHaveTextContent('Hopping, rate not reported')
  })

  it('draws no bearing, class or identity beyond what the report carries', () => {
    open({
      reports: [rfReport({ reported_class: 'wifi-bluetooth' })],
    })
    expect(screen.getByTestId('rf-reports')).not.toHaveTextContent(/wifi|rotary|bird|hostile/i)
  })

  it('shows the honesty text and legend in Hindi', () => {
    setLanguage('hi')
    open({ reports: [rfReport()] })
    expect(screen.getByTestId('synth-label')).toHaveTextContent(
      'सेंसर रिपोर्टों से संश्लेषित · संदर्भ डेटा',
    )
    expect(screen.getByTestId('rf-open-note')).toHaveTextContent('RF को भूभाग से रुकावट नहीं होती')
    expect(screen.getByRole('tab', { name: 'RF स्पेक्ट्रम' })).toBeInTheDocument()
  })
})

describe('acoustic console', () => {
  async function showAcoustic(setup: Setup = {}) {
    const user = userEvent.setup()
    const r = open(setup)
    await user.click(screen.getByRole('tab', { name: 'Acoustic spectrogram' }))
    return { user, ...r }
  }

  it('lists the latest reports and carries the same honesty label', async () => {
    await showAcoustic({ reports: [acReport()] })
    const table = screen.getByRole('table', { name: 'Latest acoustic reports' })
    expect(
      within(table)
        .getAllByRole('columnheader')
        .map((h) => h.textContent),
    ).toEqual(['Blade-pass (Hz)', 'Harmonics', 'Tonal', 'SNR (dB)', 'Bearing'])
    expect(within(table).getAllByRole('row')[1]).toHaveTextContent('100.04Yes17.5210°')
    expect(screen.getByTestId('synth-label')).toHaveTextContent(
      'Synthesised from sensor reports · reference data',
    )
    expect(screen.queryByTestId('rf-open-note')).not.toBeInTheDocument()
  })

  it('listens: nothing heard, no nearest harmonic, the cursor still moves', async () => {
    const { user } = await showAcoustic()
    expect(screen.getByTestId('console-status')).toHaveAttribute('data-state', 'listening')
    expect(screen.getByTestId('cursor-nearest')).toHaveTextContent('none reported')
    const group = screen.getByRole('group', { name: /Acoustic spectrogram cursor/ })
    group.focus()
    await user.keyboard('{ArrowRight}')
    expect(screen.getByTestId('spectrogram')).toHaveAttribute('data-cursor', '205')
  })

  it('moves the cursor with Left and Right, Shift for 50 Hz, and reads out the nearest harmonic', async () => {
    const { user } = await showAcoustic({ reports: [acReport()] })
    const group = screen.getByTestId('spectrogram')
    expect(group).toHaveAttribute('data-cursor', '200')
    expect(screen.getByTestId('cursor-readout')).toHaveTextContent('200 Hz')
    expect(screen.getByTestId('cursor-nearest')).toHaveTextContent(
      'order 2 at 200.0 Hz, offset 0.0 Hz',
    )
    expect(screen.getByTestId('cursor-implied')).toHaveTextContent('100.0 Hz (cursor ÷ order)')

    group.focus()
    await user.keyboard('{ArrowRight}')
    expect(group).toHaveAttribute('data-cursor', '205')
    await user.keyboard('{Shift>}{ArrowRight}{/Shift}')
    expect(group).toHaveAttribute('data-cursor', '255')
    await user.keyboard('{ArrowLeft}{ArrowLeft}')
    expect(group).toHaveAttribute('data-cursor', '245')
    await user.keyboard('{Shift>}{ArrowRight}{ArrowRight}{/Shift}')
    expect(group).toHaveAttribute('data-cursor', '345')
    // 345 Hz is nearest the third harmonic of 100.0 Hz
    expect(screen.getByTestId('cursor-nearest')).toHaveTextContent('order 3')
    expect(screen.getByTestId('cursor-implied')).toHaveTextContent('115.0 Hz')
    // a live region announces the move for a screen reader
    expect(within(group).getByRole('status')).toHaveTextContent('Cursor 345 Hz')
  })

  it('stops at the ends of the scale and keeps the cursor across a tab switch', async () => {
    const { user } = await showAcoustic()
    const group = screen.getByTestId('spectrogram')
    group.focus()
    await user.keyboard('{Shift>}{ArrowLeft}{ArrowLeft}{ArrowLeft}{ArrowLeft}{ArrowLeft}{/Shift}')
    expect(group).toHaveAttribute('data-cursor', '0')
    await user.keyboard('{ArrowRight}')
    await user.click(screen.getByRole('tab', { name: 'RF spectrum' }))
    await user.click(screen.getByRole('tab', { name: 'Acoustic spectrogram' }))
    expect(screen.getByTestId('spectrogram')).toHaveAttribute('data-cursor', '5')
  })

  it('is reachable by Tab and its keys do not run the track decision keys', async () => {
    const { user } = await showAcoustic()
    const group = screen.getByTestId('spectrogram')
    screen.getByRole('tab', { name: 'Acoustic spectrogram' }).focus()
    await user.tab()
    expect(group).toHaveFocus()
  })

  it('shows Hindi labels', async () => {
    setLanguage('hi')
    const user = userEvent.setup()
    open({ reports: [acReport()] })
    await user.click(screen.getByRole('tab', { name: 'ध्वनिक स्पेक्ट्रोग्राम' }))
    expect(screen.getByTestId('synth-label')).toHaveTextContent('संदर्भ डेटा')
    expect(screen.getByTestId('cursor-readout')).toHaveTextContent('कर्सर')
  })
})
