import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { MOCK_WELCOME, MockWorld, ScriptedTransport } from '../../src/live/mock'
import { parseServerMessage, type Frame, type LiveServerMessage } from '../../src/live/protocol'

function play(seconds: number, setup?: (world: MockWorld) => void) {
  const world = new MockWorld()
  world.start()
  setup?.(world)
  const frames: Frame[] = []
  while (world.timeS < seconds) frames.push(world.step())
  return { world, frames }
}

const act = (world: MockWorld, seq: number, action: string, payload: Record<string, unknown>) =>
  world.receive({ t: 'act', seq, action: action as 'hold', payload })

describe('scripted welcome', () => {
  it('describes the Harrier Field briefing without any threat', () => {
    const b = MOCK_WELCOME.briefing
    expect(b.title.en).toContain('Harrier Field')
    expect(b.zones.map((z) => [z.role, z.radius_m])).toEqual([
      ['inner', 900],
      ['outer', 3200],
    ])
    expect(b.sensors.map((s) => s.id)).toEqual(['radar-1', 'eo-1', 'rf-1'])
    expect(b.filed_flights).toHaveLength(1)
    expect(JSON.stringify(MOCK_WELCOME)).not.toMatch(/threat|truth|disposition/i)
    expect(MOCK_WELCOME.rules).toMatchObject({ id: 'training-baseline', version: '1.0.0' })
    expect(MOCK_WELCOME.tick_hz).toBe(20)
  })
})

describe('scripted session', () => {
  const { frames } = play(60)

  it('produces only well-formed protocol messages', () => {
    for (const f of frames.filter((_, i) => i % 40 === 0)) {
      expect(parseServerMessage(f)).not.toBeNull()
    }
    expect(parseServerMessage(MOCK_WELCOME)).not.toBeNull()
  })

  it('is deterministic', () => {
    const again = play(20).frames
    expect(JSON.stringify(again)).toBe(JSON.stringify(frames.slice(0, again.length)))
  })

  it('holds four bird tracks, a civil rotary and a hostile rotary by half a minute', () => {
    const f = frames.find((x) => x.time_s >= 30)!
    expect(f.tracks).toHaveLength(6)
    const classes = f.tracks.map((t) => t.class_estimate)
    expect(classes.filter((c) => c === 'bird')).toHaveLength(4)
    expect(classes.filter((c) => c === 'rotary-small')).toHaveLength(2)
    expect(f.tracks.every((t) => t.data_status === 'reference')).toBe(true)
  })

  it('paints each target once per 1.2 s on the radar, with a range', () => {
    const radar = frames.flatMap((f) => f.reports.filter((r) => r.modality === 'radar'))
    expect(radar.length).toBeGreaterThan(150)
    const phases = new Set(radar.map((r) => r.tick % 24))
    expect([...phases].sort((a, b) => a - b)).toEqual([2, 4, 6, 10, 14, 18])
    expect(radar.every((r) => typeof r.range_m === 'number')).toBe(true)
  })

  it('starts tracks tentative, then confirms them after three plots', () => {
    const events = frames.flatMap((f) => f.events)
    const init = events.find((e) => e.type === 'track.init')!
    const confirm = events.find(
      (e) => e.type === 'track.confirm' && e.payload.track === init.payload.track,
    )!
    expect(confirm.t - init.t).toBeGreaterThanOrEqual(2 * 24)
    expect(
      frames.find((f) => f.tick === init.t)!.tracks.find((t) => t.id === init.payload.track)!
        .status,
    ).toBe('tentative')
  })

  it('lets one bird track coast and resume', () => {
    const types = frames.flatMap((f) => f.events.map((e) => e.type))
    expect(types).toContain('track.coast')
    expect(types).toContain('track.resume')
  })

  it('gives every confirmed track an assist view that says it is simulated', () => {
    const f = frames.find((x) => x.time_s >= 30)!
    expect(f.assist).toHaveLength(6)
    expect(
      f.assist.every((a) => a.source.includes('simulated') && a.data_status === 'reference'),
    ).toBe(true)
    expect(new Set(f.assist.map((a) => a.flag))).toEqual(new Set(['threat', 'no-threat']))
  })

  it('carries RF reports for emitters and no range for EO or RF', () => {
    const reports = frames.flatMap((f) => f.reports)
    expect(reports.some((r) => r.modality === 'rf' && r.features.band)).toBe(true)
    for (const r of reports.filter((x) => x.modality !== 'radar')) expect(r.range_m).toBeNull()
  })

  it('never reports a target to the EO camera it is not pointed at', () => {
    // with no cue the camera stays on its home bearing, so EO reports stay near it
    const eo = frames.slice(0, 20 * 25).flatMap((f) => f.reports.filter((r) => r.modality === 'eo'))
    for (const r of eo) expect(Math.abs(r.azimuth_deg - 38)).toBeLessThan(13)
  })
})

describe('operator actions in the scripted session', () => {
  function session() {
    const world = new MockWorld()
    world.start()
    while (world.timeS < 12) world.step()
    return world
  }
  const events = (world: MockWorld, ticks = 3) => {
    const out = []
    for (let i = 0; i < ticks; i++) out.push(...world.step().events)
    return out
  }

  it('refuses an action when the session is not running, and an unknown action', () => {
    const idle = new MockWorld()
    expect(act(idle, 1, 'hold', { track: 'T011' })).toMatchObject({
      ok: false,
      error: { code: 'not-running' },
    })
    const world = session()
    expect(act(world, 2, 'fire-at-will', {})).toMatchObject({
      ok: false,
      error: { code: 'unknown-action' },
    })
    expect(act(world, 3, 'hold', { track: 'T011' })).toMatchObject({ ok: true, seq: 3 })
  })

  it('accepts each of the nine operator classes and refuses anything else', () => {
    expect(MOCK_WELCOME.operator_classes).toHaveLength(9)
    const outcome = (id: string) => {
      const world = session()
      act(world, 1, 'classify', { track: 'T014', class_id: id })
      return events(world).map((e) => e.type)
    }
    for (const id of MOCK_WELCOME.operator_classes) {
      const types = outcome(id)
      expect(types, id).toContain('action.classify')
      expect(types, id).not.toContain('action.rejected')
    }
    for (const bad of ['rotary', 'autonomous-small', 'decoy-small', 'civil-drone', ''])
      expect(outcome(bad), bad).toContain('action.rejected')
  })

  it('reports a forced EO class on every EO report, and the default class otherwise', () => {
    const eoReports = (variant: ConstructorParameters<typeof MockWorld>[0]) => {
      const world = new MockWorld(variant)
      world.start()
      const out = []
      while (world.timeS < 12) world.step()
      act(world, 1, 'sensor-cue', { sensor: 'eo-1', track: 'T014', narrow: true })
      while (world.timeS < 30) out.push(...world.step().reports.filter((r) => r.modality === 'eo'))
      return out
    }
    const forced = eoReports({ eoClass: 'kite' })
    expect(forced.length).toBeGreaterThan(0)
    expect(forced.every((r) => r.reported_class === 'kite')).toBe(true)
    expect(eoReports({}).every((r) => r.reported_class !== 'kite')).toBe(true)
  })

  it('blocks a response the rules do not allow, naming the rule, the pack and what is missing', () => {
    const world = session()
    act(world, 1, 'engage', { track: 'T014', effector_class: 'ec-a' })
    const verdict = events(world).find((e) => e.type === 'roe.verdict')!
    expect(verdict.payload).toMatchObject({
      permitted: false,
      code: 'conditions',
      rule_id: 'suspect-outer-zone',
      pack_id: 'training-baseline',
      pack_version: '1.0.0',
    })
    expect((verdict.payload.detail as { unmet: unknown[] }).unmet.length).toBeGreaterThan(0)
    expect(events(world, 5).some((e) => e.type === 'action.engage')).toBe(false)
  })

  it('permits it once the operator has assessed the track and the class support is high enough', () => {
    const world = session()
    act(world, 1, 'assess', { track: 'T014', identity: 'hostile' })
    while (world.timeS < 30) world.step()
    act(world, 2, 'engage', { track: 'T014', effector_class: 'ec-a' })
    const seen = events(world)
    expect(
      seen.find((e) => e.type === 'roe.verdict' && e.payload.action === 'engage')?.payload,
    ).toMatchObject({
      permitted: true,
      code: 'permitted',
    })
    expect(seen.some((e) => e.type === 'action.engage')).toBe(true)
  })

  it('answers an unknown track with a rejection and the other track commands with their events', () => {
    const world = session()
    act(world, 1, 'track-relabel', { track: 'T999', label: 'x' })
    act(world, 2, 'track-relabel', { track: 'T011', label: 'T012' })
    act(world, 3, 'track-relabel', { track: 'T011', label: 'LEAD' })
    act(world, 4, 'track-split', { track: 'T012' })
    act(world, 5, 'track-merge', { tracks: ['T013', 'T014'] })
    act(world, 6, 'track-drop', { track: 'T012' })
    const seen = events(world, 2)
    const types = seen.map((e) => e.type)
    expect(types.filter((t) => t === 'action.rejected')).toHaveLength(2)
    expect(seen.find((e) => e.type === 'track.relabel')?.payload).toMatchObject({
      track: 'T011',
      label: 'LEAD',
      previous: 'T011',
    })
    expect(types).toContain('track.split')
    expect(seen.find((e) => e.type === 'track.merge')?.payload).toEqual({
      survivor: 'T013',
      absorbed: 'T014',
    })
    expect(seen.find((e) => e.type === 'track.drop')?.payload).toMatchObject({
      track: 'T012',
      reason: 'operator',
    })
  })

  it('swaps labels when asked to take one in use', () => {
    const world = session()
    act(world, 1, 'track-relabel', { track: 'T011', label: 'T012', exchange: true })
    const e = events(world).find((x) => x.type === 'track.relabel')!
    expect(e.payload).toMatchObject({ track: 'T011', label: 'T012', exchanged_with: 'T012' })
  })

  it('cues the EO sensor, which narrows and points at the track, and refuses a radar cue', () => {
    const world = session()
    act(world, 1, 'sensor-cue', { sensor: 'eo-1', track: 'T014', narrow: true })
    act(world, 2, 'sensor-cue', { sensor: 'radar-1', track: 'T014' })
    const seen = events(world)
    const cues = seen.filter((e) => e.type === 'sensor.cue').map((e) => e.payload)
    expect(cues[0]).toMatchObject({ sensor: 'eo-1', accepted: true })
    expect(cues[1]).toMatchObject({ sensor: 'radar-1', accepted: false })
    let frame: Frame | undefined
    for (let i = 0; i < 20 * 8; i++) frame = world.step()
    const eo = frame!.sensors.find((s) => s.id === 'eo-1')!
    expect(eo.cued).toBe(true)
    expect(eo.fov_deg).toBeLessThan(6)
  })
})

describe('ScriptedTransport', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it('welcomes, runs on start, acks asynchronously and ends with a verified summary', async () => {
    const t = new ScriptedTransport({ speed: 1 })
    const got: LiveServerMessage[] = []
    const states: string[] = []
    t.open({
      onMessage: (m) => got.push(m),
      onConnection: (i) => states.push(i.state),
      onLatency: () => undefined,
    })
    await vi.advanceTimersByTimeAsync(100)
    expect(got.map((m) => m.t)).toEqual(['welcome', 'frame'])
    expect(states).toEqual(['connecting', 'open'])
    t.start()
    await vi.advanceTimersByTimeAsync(15_000)
    const seq = t.act('hold', { track: 'T011' })
    expect(seq).toBe(1)
    expect(got.some((m) => m.t === 'ack')).toBe(false)
    await vi.advanceTimersByTimeAsync(100)
    expect(got.find((m) => m.t === 'ack')).toMatchObject({ seq: 1, ok: true })
    await vi.advanceTimersByTimeAsync(60_000)
    const ended = got.find((m) => m.t === 'ended')
    expect(ended).toMatchObject({ status: 'ended', summary: { verified: true } })
    expect(states.at(-1)).toBe('closed')
    expect(got.filter((m) => m.t === 'frame').length).toBeGreaterThan(1200)
  })
})
