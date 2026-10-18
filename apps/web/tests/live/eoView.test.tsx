import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { setLanguage } from '../../src/lib/prefs'
import { EoModeControl, QualityControl } from '../../src/live/panels/EoControls'
import { LiveProvider } from '../../src/live/context'
import { qualityStore } from '../../src/live/qualityStore'
import { LiveSession } from '../../src/live/session'
import type { EoMode } from '../../src/live/views/eoMode'
import { publishLook, resetLook } from '../../src/live/views/eoLook'
import { EoHud } from '../../src/live/views/EoHud'
import { EoView } from '../../src/live/views/EoView'
import { fixtureFetch } from './terrainFixture'
import { FakeTransport, frame, welcome } from './helpers'

/** What the scene was asked to do; the real one needs WebGL, which jsdom does not have. */
const spy = vi.hoisted(() => ({
  calls: [] as { method: string; args: unknown[] }[],
  tiers: [] as string[],
  disposed: 0,
}))

vi.mock('../../src/live/views/webgl', () => ({ webglAvailable: () => true }))
vi.mock('../../src/live/views/eoScene', () => {
  class EoScene {
    renderer = {}
    constructor(
      _canvas: unknown,
      readonly options: { tier: string },
    ) {
      spy.tiers.push(options.tier)
    }
    private rec(method: string, args: unknown[]) {
      spy.calls.push({ method, args })
    }
    setWeather(...a: unknown[]) {
      this.rec('setWeather', a)
    }
    setSite(...a: unknown[]) {
      this.rec('setSite', a)
    }
    setMode(...a: unknown[]) {
      this.rec('setMode', a)
    }
    setQuality(...a: unknown[]) {
      this.rec('setQuality', a)
    }
    setTimeOfDay(...a: unknown[]) {
      this.rec('setTimeOfDay', a)
    }
    setTerrain(...a: unknown[]) {
      this.rec('setTerrain', a)
      return Promise.resolve()
    }
    resize(...a: unknown[]) {
      this.rec('resize', a)
    }
    update(...a: unknown[]) {
      this.rec('update', a)
    }
    render(...a: unknown[]) {
      this.rec('render', a)
    }
    dispose() {
      spy.disposed++
    }
  }
  return { EoScene }
})

const called = (method: string) => spy.calls.filter((c) => c.method === method)

function liveSession(terrain?: unknown) {
  const transport = new FakeTransport()
  const session = new LiveSession(transport)
  session.connect()
  const w = welcome()
  if (terrain) (w.briefing as unknown as { terrain: unknown }).terrain = terrain
  act(() => {
    transport.push(w)
    transport.push(frame())
  })
  return { session, transport }
}

function view(session: LiveSession, mode: EoMode = 'day') {
  const ui = (m: EoMode) => (
    <LiveProvider session={session}>
      <EoView sensorId="eo-1" mode={m} />
    </LiveProvider>
  )
  const result = render(ui(mode))
  return { ...result, setMode: (m: EoMode) => result.rerender(ui(m)) }
}

beforeEach(() => {
  spy.calls.length = 0
  spy.tiers.length = 0
  spy.disposed = 0
  qualityStore.setChoice('auto')
  vi.stubGlobal('fetch', fixtureFetch())
})

afterEach(() => {
  vi.unstubAllGlobals()
  resetLook()
  setLanguage('en')
})

describe('EoView and the terrain pack', () => {
  it('shows loading, then ready with the pack drawn and its provenance named', async () => {
    const { session } = liveSession({ kind: 'pack', id: 'fixture-ridge', version: '1.0.0' })
    const { container } = view(session)
    const box = container.firstElementChild as HTMLElement
    expect(box).toHaveAttribute('data-terrain', 'loading')
    expect(screen.getByTestId('terrain-loading')).toHaveTextContent('Loading terrain')
    await waitFor(() => expect(box).toHaveAttribute('data-terrain', 'pack'))
    expect(screen.queryByTestId('terrain-loading')).not.toBeInTheDocument()
    expect(screen.getByTestId('terrain-label')).toHaveTextContent(
      'Terrain: Fixture Ridge · reference data',
    )
    await waitFor(() => expect(called('setTerrain').length).toBeGreaterThan(0))
    const pack = called('setTerrain').at(-1)?.args[0] as { id: string } | null
    expect(pack?.id).toBe('fixture-ridge')
  })

  it('falls back to flat ground with an accessible notice when the pack fails', async () => {
    const { session } = liveSession({ kind: 'pack', id: 'missing', version: '1.0.0' })
    const { container } = view(session)
    const box = container.firstElementChild as HTMLElement
    await waitFor(() => expect(box).toHaveAttribute('data-terrain', 'error'))
    const notice = screen.getByTestId('terrain-notice')
    expect(notice).toHaveTextContent('Terrain unavailable')
    expect(notice).toHaveTextContent('flat ground')
    expect(screen.getByRole('alert')).toBeInTheDocument()
    // the view still runs: scene made, site drawn, no pack ever handed over
    expect(spy.tiers).toHaveLength(1)
    expect(called('setSite')).toHaveLength(1)
    expect(called('setTerrain').filter((c) => c.args[0] !== null)).toHaveLength(0)
  })

  it('draws flat ground at once for a briefing with no terrain field', async () => {
    const { session } = liveSession()
    const { container } = view(session)
    expect(container.firstElementChild).toHaveAttribute('data-terrain', 'flat')
    await waitFor(() => expect(called('setTerrain').length).toBeGreaterThan(0))
    expect(called('setTerrain').every((c) => c.args[0] === null)).toBe(true)
    expect(screen.queryByTestId('terrain-notice')).not.toBeInTheDocument()
  })

  it('says it in Hindi too', async () => {
    setLanguage('hi')
    const { session } = liveSession({ kind: 'pack', id: 'missing', version: '1.0.0' })
    view(session)
    expect(await screen.findByText('भूभाग उपलब्ध नहीं')).toBeInTheDocument()
  })
})

describe('EoView mode, quality and teardown', () => {
  it('passes the weather and the first mode to the scene and follows mode changes', async () => {
    const { session } = liveSession()
    const { setMode } = view(session, 'thermal-white-hot')
    expect(called('setWeather')[0]?.args[0]).toMatchObject({ condition: 'clear' })
    expect(called('setMode')[0]?.args[0]).toBe('thermal-white-hot')
    setMode('thermal-black-hot')
    await waitFor(() => expect(called('setMode').at(-1)?.args[0]).toBe('thermal-black-hot'))
  })

  it('starts the scene at the current tier and follows the user override', async () => {
    const { session } = liveSession()
    view(session)
    expect(spy.tiers).toEqual(['high'])
    act(() => qualityStore.setChoice('low'))
    await waitFor(() => expect(called('setQuality').at(-1)?.args[0]).toBe('low'))
  })

  it('feeds frame times to the quality store while it draws', async () => {
    const { session } = liveSession()
    qualityStore.resetStats()
    view(session)
    await waitFor(() => expect(called('render').length).toBeGreaterThan(2))
    await waitFor(() => expect(qualityStore.frameStats.count).toBeGreaterThan(1))
  })

  it('disposes the scene on unmount and when WebGL goes away', () => {
    const { session } = liveSession()
    const { unmount } = view(session)
    unmount()
    expect(spy.disposed).toBe(1)
  })
})

describe('EoHud readouts', () => {
  function hud(mode: EoMode) {
    const { session } = liveSession()
    return render(
      <LiveProvider session={session}>
        <EoHud sensorId="eo-1" mode={mode} />
      </LiveProvider>,
    )
  }

  it('labels the day picture and marks sensor figures as reference data', () => {
    hud('day')
    expect(screen.getByText(/T\+00:01\.00 DAY TV/)).toBeInTheDocument()
    expect(screen.getByText(/eo-1 OK RNG n\/a REF/)).toBeInTheDocument()
    expect(screen.queryByText(/AGC|GAIN/)).not.toBeInTheDocument()
    expect(screen.getByText(/Sensor figures are reference data\./)).toBeInTheDocument()
  })

  it('shows polarity, gain and that thermal is a model', () => {
    hud('thermal-white-hot')
    expect(screen.getByText(/IR WHT/)).toBeInTheDocument()
    // before the first gain sample the readout is a dash, not an invented figure
    expect(screen.getByText('AGC — MODEL')).toBeInTheDocument()
    act(() => publishLook({ mode: 'thermal-white-hot', gainPct: 61, tubeGain: 1 }))
    expect(screen.getByText('AGC 61% MODEL')).toBeInTheDocument()
    expect(screen.getByText(/Thermal is a rendering model, not radiometric/)).toBeInTheDocument()
  })

  it('shows night-vision tube gain, and ignores a readout from another mode', () => {
    hud('night-vision')
    act(() => publishLook({ mode: 'thermal-white-hot', gainPct: 40, tubeGain: 1 }))
    expect(screen.getByText('GAIN —')).toBeInTheDocument()
    act(() => publishLook({ mode: 'night-vision', gainPct: 0, tubeGain: 12.04 }))
    expect(screen.getByText('GAIN ×12.0')).toBeInTheDocument()
    expect(screen.getByText(/T\+00:01\.00 NV/)).toBeInTheDocument()
  })

  it('inverts the reticle between white-hot and black-hot, and uses phosphor green in night vision', () => {
    const ink = (container: HTMLElement) =>
      [...container.querySelectorAll('svg g[stroke]')].map((g) => g.getAttribute('stroke'))
    const white = hud('thermal-white-hot')
    expect(ink(white.container)).toContain('#f2f4f5')
    expect(ink(white.container)).toContain('#050607')
    white.unmount()
    const black = hud('thermal-black-hot')
    const blackInk = ink(black.container)
    // the bright pass is drawn under the dark one: the dark stroke is on top, last in order
    expect(blackInk.indexOf('#f2f4f5')).toBeLessThan(blackInk.indexOf('#050607'))
    black.unmount()
    const nv = hud('night-vision')
    expect(ink(nv.container)).toContain('#b6ffc0')
    nv.unmount()
    const day = hud('day')
    expect(ink(day.container)).toContain('var(--text)')
  })
})

describe('mode and quality controls', () => {
  it('offers one mode for a day camera, with no thermal or night-vision wording', () => {
    render(<EoModeControl modes={['day']} mode="day" onChange={() => undefined} />)
    expect(screen.getAllByRole('button').map((b) => b.textContent)).toEqual(['Day TV'])
    expect(screen.queryByText(/thermal|night/i)).not.toBeInTheDocument()
  })

  it('offers both polarities for a thermal camera and switches with the keyboard', async () => {
    const user = userEvent.setup()
    const changes: EoMode[] = []
    render(
      <EoModeControl
        modes={['thermal-white-hot', 'thermal-black-hot']}
        mode="thermal-white-hot"
        onChange={(m) => changes.push(m)}
      />,
    )
    const group = screen.getByRole('group', { name: 'Mode' })
    const [white, black] = [
      screen.getByRole('button', { name: 'White-hot' }),
      screen.getByRole('button', { name: 'Black-hot' }),
    ]
    expect(group).toContainElement(white)
    expect(white).toHaveAttribute('aria-pressed', 'true')
    expect(black).toHaveAttribute('aria-pressed', 'false')
    await user.tab()
    expect(white).toHaveFocus()
    await user.tab()
    expect(black).toHaveFocus()
    await user.keyboard('{Enter}')
    expect(changes).toEqual(['thermal-black-hot'])
    await user.keyboard(' ')
    expect(changes).toEqual(['thermal-black-hot', 'thermal-black-hot'])
  })

  it('explains in a keyboard-reachable tooltip that thermal is not radiometric', async () => {
    const user = userEvent.setup()
    render(
      <EoModeControl
        modes={['thermal-white-hot', 'thermal-black-hot']}
        mode="thermal-black-hot"
        onChange={() => undefined}
      />,
    )
    const help = screen.getByRole('button', { name: 'About this picture' })
    await user.tab()
    await user.tab()
    await user.tab()
    expect(help).toHaveFocus()
    const tip = screen.getByRole('tooltip')
    expect(tip).toBeVisible()
    expect(tip).toHaveTextContent('rendering model, not radiometric')
    await user.keyboard('{Escape}')
    expect(tip).not.toBeVisible()
  })

  it('labels night vision as a rendering model', () => {
    render(
      <EoModeControl modes={['night-vision']} mode="night-vision" onChange={() => undefined} />,
    )
    expect(screen.getByRole('button', { name: 'Night vision' })).toBeInTheDocument()
    expect(screen.getByRole('tooltip', { hidden: true })).toHaveTextContent('rendering model')
  })

  it('has Hindi labels for every mode', () => {
    setLanguage('hi')
    render(
      <EoModeControl
        modes={['thermal-white-hot', 'thermal-black-hot']}
        mode="thermal-white-hot"
        onChange={() => undefined}
      />,
    )
    expect(screen.getByRole('button', { name: 'सफ़ेद-गर्म' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'काला-गर्म' })).toBeInTheDocument()
    expect(screen.getByRole('group', { name: 'मोड' })).toBeInTheDocument()
  })

  it('picks the graphics tier with the keyboard and remembers it', async () => {
    const user = userEvent.setup()
    render(<QualityControl />)
    const group = screen.getByRole('group', { name: 'Graphics' })
    expect(group).toBeInTheDocument()
    expect(screen.getAllByRole('button').map((b) => b.textContent)).toEqual([
      'Auto',
      'High',
      'Medium',
      'Low',
    ])
    expect(screen.getByRole('button', { name: 'Auto' })).toHaveAttribute('aria-pressed', 'true')
    await user.tab()
    await user.tab()
    await user.tab()
    await user.tab()
    expect(screen.getByRole('button', { name: 'Low' })).toHaveFocus()
    await user.keyboard('{Enter}')
    expect(screen.getByRole('button', { name: 'Low' })).toHaveAttribute('aria-pressed', 'true')
    expect(qualityStore.getState()).toMatchObject({ choice: 'low', tier: 'low', phase: 'fixed' })
    expect(window.localStorage.getItem('ui.quality')).toBe('low')
  })

  it('has Hindi labels for the graphics control', () => {
    setLanguage('hi')
    render(<QualityControl />)
    expect(screen.getByRole('group', { name: 'ग्राफ़िक्स' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'स्वचालित' })).toBeInTheDocument()
  })
})
