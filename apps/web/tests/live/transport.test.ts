import { encode } from '@msgpack/msgpack'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  decodeServerMessage,
  encodeClientMessage,
  isAck,
  isEnded,
  isFault,
  isFrame,
  isPong,
  isStatus,
  isWelcome,
  parseServerMessage,
} from '../../src/live/protocol'
import {
  backoffDelay,
  sessionSocketUrl,
  WebSocketTransport,
  type ConnectionInfo,
} from '../../src/live/transport'
import { decode } from '@msgpack/msgpack'
import { FakeSocket, frame, welcome } from './helpers'

describe('protocol codec', () => {
  it('decodes each server message type and narrows it with the guards', () => {
    const cases = [
      welcome(),
      frame(),
      { t: 'status', status: 'running', tick: 3 },
      { t: 'ack', seq: 4, ok: true, tick: 5 },
      { t: 'pong', ts: 123, tick: 6 },
      {
        t: 'ended',
        status: 'ended',
        summary: {
          ticks: 1,
          duration_s: 1,
          event_count: 2,
          head: 'a',
          final_state_hash: 'b',
          verified: true,
        },
      },
      { t: 'error', code: 'x', message: 'y' },
    ]
    const guards = [isWelcome, isFrame, isStatus, isAck, isPong, isEnded, isFault]
    cases.forEach((message, i) => {
      const decoded = decodeServerMessage(encode(message))
      expect(decoded?.t).toBe(message.t)
      guards.forEach((guard, j) => expect(guard(decoded!)).toBe(i === j))
    })
  })

  it('refuses anything that is not a known, well-formed server message', () => {
    expect(decodeServerMessage(encode({ t: 'nope' }))).toBeNull()
    expect(decodeServerMessage(encode('text'))).toBeNull()
    expect(decodeServerMessage(encode({ t: 'frame', tick: 1 }))).toBeNull()
    expect(decodeServerMessage(encode({ t: 'ack', seq: '1', ok: true }))).toBeNull()
    expect(decodeServerMessage(new Uint8Array([0xc1]))).toBeNull()
    expect(parseServerMessage(null)).toBeNull()
    expect(parseServerMessage([])).toBeNull()
  })

  it('round-trips client messages as MessagePack maps keyed by t', () => {
    const bytes = encodeClientMessage({
      t: 'act',
      seq: 7,
      action: 'classify',
      payload: { track: 'T011', class_id: 'bird' },
    })
    expect(decode(bytes)).toEqual({
      t: 'act',
      seq: 7,
      action: 'classify',
      payload: { track: 'T011', class_id: 'bird' },
    })
  })
})

describe('socket address', () => {
  it('uses wss on https pages and ws on http pages', () => {
    expect(sessionSocketUrl('abc', { protocol: 'https:', host: 'x.example' }, undefined)).toBe(
      'wss://x.example/api/v1/sessions/abc/ws',
    )
    expect(sessionSocketUrl('abc', { protocol: 'http:', host: 'localhost:5173' }, undefined)).toBe(
      'ws://localhost:5173/api/v1/sessions/abc/ws',
    )
  })

  it('follows VITE_API_URL when the API is on another origin', () => {
    expect(
      sessionSocketUrl('s1', { protocol: 'https:', host: 'app.example' }, 'https://api.example/'),
    ).toBe('wss://api.example/api/v1/sessions/s1/ws')
  })

  it('doubles the backoff each attempt up to the cap, with bounded jitter', () => {
    const noJitter = () => 0.5
    expect([1, 2, 3, 4, 5, 6].map((n) => backoffDelay(n, 500, 8000, noJitter))).toEqual([
      500, 1000, 2000, 4000, 8000, 8000,
    ])
    expect(backoffDelay(1, 500, 8000, () => 0)).toBe(400)
    expect(backoffDelay(1, 500, 8000, () => 1)).toBe(600)
  })
})

describe('WebSocketTransport', () => {
  let states: ConnectionInfo[]
  let latencies: number[]
  let messages: string[]
  let clock = 0
  const make = (random = () => 0.5) => {
    const transport = new WebSocketTransport({
      url: 'ws://x/api/v1/sessions/s/ws',
      createSocket: (url) => new FakeSocket(url),
      now: () => clock,
      random,
    })
    transport.open({
      onMessage: (m) => messages.push(m.t),
      onConnection: (i) => states.push(i),
      onLatency: (ms) => latencies.push(ms),
    })
    return transport
  }
  const socket = () => FakeSocket.instances[FakeSocket.instances.length - 1]!

  beforeEach(() => {
    vi.useFakeTimers()
    FakeSocket.instances = []
    states = []
    latencies = []
    messages = []
    clock = 1000
  })
  afterEach(() => vi.useRealTimers())

  it('connects, asks for binary frames, and reports open', () => {
    make()
    expect(states.map((s) => s.state)).toEqual(['connecting'])
    expect(socket().binaryType).toBe('arraybuffer')
    socket().open()
    expect(states.at(-1)).toEqual({ state: 'open', closeCode: null, attempt: 0 })
  })

  it('passes decoded messages on and ignores text and malformed frames', () => {
    make()
    socket().open()
    socket().receive(new Uint8Array(encode({ t: 'status', status: 'running', tick: 1 })).buffer)
    socket().receive('{"t":"status"}')
    socket().receive(new Uint8Array([0xc1]))
    socket().receive(encode({ t: 'wat' }))
    expect(messages).toEqual(['status'])
  })

  it('pings every 2 s and reports the latency of each pong', () => {
    make()
    socket().open()
    expect(socket().sent.map((m) => m.t)).toEqual(['ping'])
    clock = 1000
    vi.advanceTimersByTime(2000)
    vi.advanceTimersByTime(2000)
    expect(socket().sent.filter((m) => m.t === 'ping')).toHaveLength(3)
    clock = 1031
    socket().receive(encode({ t: 'pong', ts: 1000, tick: 9 }))
    expect(latencies).toEqual([31])
  })

  it('numbers operator inputs from 1 and refuses to send while the link is down', () => {
    const transport = make()
    expect(transport.act('hold', { track: 'T011' })).toBeNull()
    socket().open()
    expect(transport.act('hold', { track: 'T011' })).toBe(1)
    expect(transport.act('classify', { track: 'T011', class_id: 'bird' })).toBe(2)
    const acts = socket().sent.filter((m) => m.t === 'act')
    expect(acts).toEqual([
      { t: 'act', seq: 1, action: 'hold', payload: { track: 'T011' } },
      { t: 'act', seq: 2, action: 'classify', payload: { track: 'T011', class_id: 'bird' } },
    ])
  })

  it('sends start, end and leave', () => {
    const transport = make()
    socket().open()
    transport.start()
    transport.end()
    transport.leave()
    expect(socket().sent.map((m) => m.t)).toEqual(['ping', 'start', 'end', 'leave'])
  })

  it('reconnects with growing delays after an abnormal close and resets after opening', () => {
    make()
    socket().open()
    socket().drop(1006)
    expect(states.at(-1)).toMatchObject({ state: 'reconnecting', attempt: 1, closeCode: 1006 })
    vi.advanceTimersByTime(499)
    expect(FakeSocket.instances).toHaveLength(1)
    vi.advanceTimersByTime(1)
    expect(FakeSocket.instances).toHaveLength(2)
    socket().drop(1006)
    expect(states.at(-1)).toMatchObject({ state: 'reconnecting', attempt: 2 })
    vi.advanceTimersByTime(1000)
    expect(FakeSocket.instances).toHaveLength(3)
    socket().open()
    expect(states.at(-1)).toMatchObject({ state: 'open', attempt: 0 })
    socket().drop(1006)
    expect(states.at(-1)).toMatchObject({ state: 'reconnecting', attempt: 1 })
  })

  it.each([4401, 4403, 4404, 4408, 4409, 4413, 1013])(
    'does not reconnect after close code %i',
    (code) => {
      make()
      socket().open()
      socket().drop(code)
      expect(states.at(-1)).toEqual({ state: 'closed', closeCode: code, attempt: 0 })
      vi.advanceTimersByTime(60_000)
      expect(FakeSocket.instances).toHaveLength(1)
    },
  )

  it('does not reconnect once the session has ended', () => {
    make()
    socket().open()
    socket().receive(
      encode({
        t: 'ended',
        status: 'ended',
        summary: {
          ticks: 1,
          duration_s: 1,
          event_count: 1,
          head: 'a',
          final_state_hash: 'b',
          verified: true,
        },
      }),
    )
    socket().drop(1006)
    expect(states.at(-1)?.state).toBe('closed')
    vi.advanceTimersByTime(60_000)
    expect(FakeSocket.instances).toHaveLength(1)
  })

  it('close() stops pings and reconnects for good', () => {
    const transport = make()
    socket().open()
    transport.close()
    expect(socket().closedWith).toBe(1000)
    expect(states.at(-1)?.state).toBe('closed')
    vi.advanceTimersByTime(30_000)
    expect(FakeSocket.instances).toHaveLength(1)
    expect(socket().sent.filter((m) => m.t === 'ping')).toHaveLength(1)
  })
})
