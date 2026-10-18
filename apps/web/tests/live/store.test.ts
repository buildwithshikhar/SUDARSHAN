import { describe, expect, it } from 'vitest'
import {
  EVENT_CAP,
  initialState,
  interpolateSensor,
  LiveStore,
  MAX_EXTRAPOLATE_S,
  reduce,
  sensorPose,
  simTimeNow,
  TRAIL_MAX,
  trackPoses,
  type LiveAction,
} from '../../src/live/store'
import type { LiveServerMessage } from '../../src/live/protocol'
import { event, frame, track, verdictEvent, welcome } from './helpers'

const msg = (message: LiveServerMessage, at = 0): LiveAction => ({ type: 'message', message, at })
const run = (actions: LiveAction[], from = initialState()) => actions.reduce(reduce, from)

describe('frames', () => {
  it('keeps the latest two frames and when they arrived', () => {
    const s = run([
      msg(frame({ tick: 20, time_s: 1 }), 1000),
      msg(frame({ tick: 21, time_s: 1.05 }), 1050),
    ])
    expect(s.frame?.tick).toBe(21)
    expect(s.prevFrame?.tick).toBe(20)
    expect([s.frameAt, s.prevFrameAt]).toEqual([1050, 1000])
  })

  it('drops a frame older than the current one and counts it', () => {
    const s = run([msg(frame({ tick: 30 }), 1), msg(frame({ tick: 29 }), 2)])
    expect(s.frame?.tick).toBe(30)
    expect(s.staleFrames).toBe(1)
  })

  it('replaces, not shifts, when a frame repeats the tick (status change)', () => {
    const s = run([
      msg(frame({ tick: 5 }), 10),
      msg(frame({ tick: 6 }), 20),
      msg(frame({ tick: 6, status: 'lobby' }), 30),
    ])
    expect(s.prevFrame?.tick).toBe(5)
    expect(s.status).toBe('lobby')
  })

  it('records a short trail per track at most once a second and caps it', () => {
    const frames = Array.from({ length: 80 }, (_, i) =>
      msg(
        frame({
          tick: i + 1,
          time_s: (i + 1) * 0.5,
          tracks: [track('T011', { position: { x: i, y: 0, z: 0 } })],
        }),
        i,
      ),
    )
    const s = run(frames)
    const trail = s.trails.T011 ?? []
    expect(trail.length).toBe(TRAIL_MAX)
    expect(trail[1]!.timeS - trail[0]!.timeS).toBeGreaterThanOrEqual(1)
  })

  it('forgets the trail and the selection of a track that is gone', () => {
    const s = run([
      msg(frame({ tick: 1, tracks: [track('T011'), track('T012')] })),
      { type: 'select', id: 'T012' },
      msg(frame({ tick: 2, tracks: [track('T011')] })),
    ])
    expect(s.selected).toBeNull()
    expect(s.trails.T012).toBeUndefined()
  })

  it('learns the zoom reference from the first uncued look of each sensor', () => {
    const cued = frame({ tick: 1 })
    cued.sensors[0] = { ...cued.sensors[0]!, cued: true, fov_deg: 4.3 }
    const s = run([msg(cued), msg(frame({ tick: 2 })), msg(frame({ tick: 3 }))])
    expect(s.homeFov['eo-1']).toBe(24.4)
  })
})

describe('interpolation', () => {
  it('carries a track along its velocity and caps the carry at a stall', () => {
    const s = run([
      msg(
        frame({
          tick: 1,
          time_s: 1,
          tracks: [track('T011', { velocity: { x: 10, y: -4, z: 1 } })],
        }),
        1000,
      ),
    ])
    const at = (ms: number) => trackPoses(s, ms)[0]!.at
    expect(at(1000)).toEqual({ x: 100, y: 200, z: 60 })
    expect(at(1100)).toEqual({ x: 101, y: 199.6, z: 60.1 })
    // a stalled link does not fling the symbol away
    expect(at(9000).x).toBeCloseTo(100 + 10 * MAX_EXTRAPOLATE_S)
  })

  it('stops the clock and the tracks when the session is not running', () => {
    const s = run([msg(frame({ tick: 1, time_s: 4, status: 'lobby' }), 1000)])
    expect(simTimeNow(s, 1200)).toBe(4)
    expect(trackPoses(s, 1200)[0]!.at).toEqual({ x: 100, y: 200, z: 60 })
  })

  it('advances scenario time between frames, capped', () => {
    const s = run([msg(frame({ tick: 1, time_s: 4 }), 1000)])
    expect(simTimeNow(s, 1100)).toBeCloseTo(4.1)
    expect(simTimeNow(s, 5000)).toBeCloseTo(4 + MAX_EXTRAPOLATE_S)
  })

  it('blends sensor pointing between the last two frames, the short way round', () => {
    const a = frame({ tick: 1 })
    const b = frame({ tick: 2 })
    a.sensors[0] = { ...a.sensors[0]!, bearing_deg: 350, elevation_deg: 2, fov_deg: 24 }
    b.sensors[0] = { ...b.sensors[0]!, bearing_deg: 10, elevation_deg: 6, fov_deg: 20 }
    const s = run([msg(a, 1000), msg(b, 1050)])
    expect(sensorPose(s, 'eo-1', 1050)).toMatchObject({
      bearingDeg: 350,
      elevationDeg: 2,
      fovDeg: 24,
    })
    const mid = sensorPose(s, 'eo-1', 1075)!
    expect(mid.bearingDeg).toBeCloseTo(0, 5)
    expect(mid.elevationDeg).toBeCloseTo(4)
    expect(mid.fovDeg).toBeCloseTo(22)
    expect(sensorPose(s, 'eo-1', 2000)).toMatchObject({ bearingDeg: 10, fovDeg: 20 })
    expect(sensorPose(s, 'nope', 1000)).toBeNull()
    expect(interpolateSensor(a.sensors[0]!, b.sensors[0]!, 1).bearingDeg).toBeCloseTo(10)
  })
})

describe('events', () => {
  it('appends trainee events in order, newest last, and ignores repeats', () => {
    const s = run([
      msg(
        frame({
          tick: 1,
          events: [event(1, 'session.start'), event(2, 'track.init', { track: 'T011' })],
        }),
      ),
      msg(
        frame({
          tick: 2,
          events: [
            event(2, 'track.init', { track: 'T011' }),
            event(3, 'track.confirm', { track: 'T011' }),
          ],
        }),
      ),
    ])
    expect(s.events.map((e) => e.seq)).toEqual([1, 2, 3])
  })

  it('keeps at most the newest 500', () => {
    const many = Array.from({ length: EVENT_CAP + 120 }, (_, i) =>
      event(i + 1, 'track.coast', { track: 'T011' }),
    )
    const s = run([msg(frame({ tick: 1, events: many }))])
    expect(s.events).toHaveLength(EVENT_CAP)
    expect(s.events[0]!.seq).toBe(121)
    expect(s.events.at(-1)!.seq).toBe(EVENT_CAP + 120)
  })

  it('learns the operator own classification and assessment from events', () => {
    const s = run([
      msg(
        frame({
          tick: 1,
          events: [
            event(1, 'action.classify', { track: 'T011', class_id: 'bird' }),
            event(2, 'action.assess', { track: 'T011', identity: 'neutral' }),
          ],
        }),
      ),
    ])
    expect(s.classifications).toEqual({ T011: 'bird' })
    expect(s.assessments).toEqual({ T011: 'neutral' })
  })

  it('moves the marks of an absorbed track to the survivor and copies them on a split', () => {
    const s = run([
      msg(
        frame({
          tick: 1,
          tracks: [track('T011'), track('T012')],
          events: [event(1, 'action.assess', { track: 'T012', identity: 'hostile' })],
        }),
      ),
      { type: 'select', id: 'T012' },
      msg(
        frame({
          tick: 2,
          tracks: [track('T011'), track('T012')],
          events: [event(2, 'track.merge', { survivor: 'T011', absorbed: 'T012' })],
        }),
      ),
    ])
    expect(s.assessments).toEqual({ T011: 'hostile' })
    const split = reduce(
      s,
      msg(
        frame({
          tick: 3,
          tracks: [track('T011'), track('T015')],
          events: [event(3, 'track.split', { source: 'T011', new: 'T015' })],
        }),
      ),
    )
    expect(split.assessments.T015).toBe('hostile')
  })

  it('resolves a pending action from the event that answers it, and from a rejection', () => {
    const base = run([
      msg(frame({ tick: 1 })),
      {
        type: 'sent',
        seq: 1,
        action: 'track-relabel',
        payload: { track: 'T011', label: 'A' },
        at: 0,
      },
      {
        type: 'sent',
        seq: 2,
        action: 'sensor-cue',
        payload: { sensor: 'eo-1', track: 'T011' },
        at: 0,
      },
    ])
    const acked = reduce(base, msg({ t: 'ack', seq: 1, ok: true, tick: 2 }))
    expect(acked.pending.map((p) => p.state)).toEqual(['queued', 'sent'])
    const answered = reduce(
      acked,
      msg(
        frame({
          tick: 2,
          events: [event(1, 'track.relabel', { track: 'T011', label: 'A', previous: 'T011' })],
        }),
      ),
    )
    expect(answered.pending.map((p) => p.seq)).toEqual([2])
    const rejected = reduce(
      answered,
      msg(
        frame({
          tick: 3,
          events: [event(2, 'action.rejected', { action: 'sensor-cue', reason: 'x', payload: {} })],
        }),
      ),
    )
    expect(rejected.pending).toEqual([])
  })

  it('marks a pending action refused when the ack says no', () => {
    const s = run([
      { type: 'sent', seq: 3, action: 'hold', payload: { track: 'T011' }, at: 0 },
      msg({ t: 'ack', seq: 3, ok: false, error: { code: 'not-running', message: 'not running' } }),
    ])
    expect(s.pending[0]).toMatchObject({ state: 'refused', message: 'not running' })
  })
})

describe('rules verdict', () => {
  const blocked = verdictEvent(1)
  const permitted = verdictEvent(2, {
    permitted: true,
    code: 'permitted',
    detail: { effector_class: 'ec-a' },
  })

  it('holds a blocked response on screen until it is replaced or dismissed', () => {
    let s = run([msg(frame({ tick: 1, events: [blocked] }))])
    expect(s.verdict).toMatchObject({ permitted: false, code: 'conditions', packVersion: '1.0.0' })
    // a later frame without a verdict leaves it where it was
    s = reduce(s, msg(frame({ tick: 2 })))
    expect(s.verdict?.permitted).toBe(false)
    s = reduce(s, msg(frame({ tick: 3, events: [permitted] })))
    expect(s.verdict?.permitted).toBe(true)
    s = reduce(s, { type: 'dismiss-verdict' })
    expect(s.verdict).toBeNull()
  })

  it('does not let a classify or assess verdict replace the response verdict', () => {
    const classify = verdictEvent(3, {
      action: 'classify',
      permitted: true,
      code: 'permitted',
      rule_id: 'track-everything',
    })
    const s = run([
      msg(frame({ tick: 1, events: [blocked] })),
      msg(frame({ tick: 2, events: [classify] })),
    ])
    expect(s.verdict?.action).toBe('engage')
    expect(s.events).toHaveLength(2)
  })
})

describe('selection and lifecycle', () => {
  const two = frame({ tick: 1, tracks: [track('T012'), track('T011'), track('T013')] })

  it('cycles through tracks in id order and wraps', () => {
    let s = run([msg(two)])
    const seen: (string | null)[] = []
    for (let i = 0; i < 4; i++) {
      s = reduce(s, { type: 'cycle', direction: 1 })
      seen.push(s.selected)
    }
    expect(seen).toEqual(['T011', 'T012', 'T013', 'T011'])
    s = reduce(s, { type: 'cycle', direction: -1 })
    expect(s.selected).toBe('T013')
  })

  it('starts backwards from the last track and does nothing without tracks', () => {
    expect(reduce(run([msg(two)]), { type: 'cycle', direction: -1 }).selected).toBe('T013')
    expect(reduce(initialState(), { type: 'cycle', direction: 1 }).selected).toBeNull()
  })

  it('records connection, latency, welcome, status, end and fault', () => {
    const w = welcome()
    const s = run([
      { type: 'connection', info: { state: 'reconnecting', closeCode: 1006, attempt: 2 } },
      { type: 'latency', ms: 23 },
      msg(w),
      msg({ t: 'status', status: 'running', tick: 4 }),
      msg({ t: 'error', code: 'x', message: 'y' }),
      msg({
        t: 'ended',
        status: 'ended',
        summary: {
          ticks: 9,
          duration_s: 4,
          event_count: 3,
          head: 'h',
          final_state_hash: 's',
          verified: true,
        },
      }),
    ])
    expect(s.connection).toEqual({ state: 'reconnecting', closeCode: 1006, attempt: 2 })
    expect(s.latencyMs).toBe(23)
    expect(s.welcome?.briefing.title.en).toBe('Harrier Field: afternoon watch')
    expect(s.fault?.code).toBe('x')
    expect(s.ended?.ticks).toBe(9)
    expect(s.status).toBe('ended')
  })

  it('notifies subscribers once per change and not for a no-op', () => {
    const store = new LiveStore()
    let calls = 0
    const off = store.subscribe(() => calls++)
    store.dispatch({ type: 'select', id: 'T011' })
    store.dispatch({ type: 'cycle', direction: 1 }) // no frame: state unchanged
    expect(calls).toBe(1)
    off()
    store.dispatch({ type: 'select', id: 'T012' })
    expect(calls).toBe(1)
  })
})
