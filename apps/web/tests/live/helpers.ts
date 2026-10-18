import { vi } from 'vitest'
import { MOCK_WELCOME } from '../../src/live/mock'
import type {
  ClientAction,
  Frame,
  LiveClientMessage,
  LiveServerMessage,
  TraineeEvent,
  TrackView,
  Welcome,
} from '../../src/live/protocol'
import type {
  ConnectionInfo,
  Transport,
  TransportHandlers,
  WebSocketLike,
} from '../../src/live/transport'
import { decode } from '@msgpack/msgpack'

export const welcome = (): Welcome => structuredClone(MOCK_WELCOME)

export function track(id: string, extra: Partial<TrackView> = {}): TrackView {
  return {
    id,
    label: id,
    status: 'confirmed',
    tick: 0,
    age_s: 10,
    since_update_s: 0.4,
    hits: 9,
    position: { x: 100, y: 200, z: 60 },
    velocity: { x: 10, y: -5, z: 0 },
    speed_mps: 11.2,
    heading_deg: 116.6,
    sigma_position_m: 14.2,
    sigma_speed_mps: 1.4,
    class_estimate: 'rotary-small',
    class_support: 0.71,
    sensors: ['radar-1'],
    data_status: 'reference',
    ...extra,
  }
}

export function frame(extra: Partial<Frame> = {}): Frame {
  return {
    t: 'frame',
    tick: 20,
    time_s: 1,
    time_of_day_h: 15.6,
    status: 'running',
    reports: [],
    tracks: [track('T011')],
    assist: [],
    sensors: [
      {
        id: 'eo-1',
        modality: 'eo',
        position: { x: -126, y: 92, z: 9 },
        bearing_deg: 38,
        elevation_deg: 4.2,
        fov_deg: 24.4,
        cued: false,
        supports_cue: true,
        outage: false,
        data_status: 'reference',
      },
    ],
    events: [],
    data_notice: 'reference',
    ...extra,
  }
}

export function event(
  seq: number,
  type: string,
  payload: Record<string, unknown> = {},
  tick = seq,
): TraineeEvent {
  return { seq, t: tick, type, actor: 'operator', payload: payload as TraineeEvent['payload'] }
}

export function verdictEvent(seq: number, over: Record<string, unknown> = {}): TraineeEvent {
  return event(seq, 'roe.verdict', {
    action: 'engage',
    track: 'T011',
    effector_class: 'ec-a',
    context: { identity: 'unknown', classification: null, zone_role: 'outer', confidence: 0.4 },
    permitted: false,
    code: 'conditions',
    rule_id: 'suspect-outer-zone',
    rule_title: {
      en: 'Suspect contact in the outer zone may receive a class A response',
      hi: 'बाहरी क्षेत्र में संदिग्ध संपर्क पर वर्ग A प्रतिक्रिया दी जा सकती है',
    },
    pack_id: 'training-baseline',
    pack_version: '1.0.0',
    authority: 'operator',
    detail: {
      unmet: [
        { field: 'identity', required: ['suspect', 'hostile'], actual: null },
        { field: 'confidence', required: 0.6, actual: 0.4 },
      ],
    },
    ...over,
  })
}

/** A transport the test drives by hand. */
export class FakeTransport implements Transport {
  handlers: TransportHandlers | null = null
  sent: { action: ClientAction; payload: Record<string, unknown> }[] = []
  control: string[] = []
  private seq = 0
  open(handlers: TransportHandlers): void {
    this.handlers = handlers
  }
  close(): void {
    this.control.push('close')
  }
  start(): void {
    this.control.push('start')
  }
  end(): void {
    this.control.push('end')
  }
  leave(): void {
    this.control.push('leave')
  }
  act(action: ClientAction, payload: Record<string, unknown> = {}): number | null {
    this.sent.push({ action, payload })
    return ++this.seq
  }
  push(message: LiveServerMessage): void {
    this.handlers?.onMessage(message)
  }
  connection(info: Partial<ConnectionInfo>): void {
    this.handlers?.onConnection({ state: 'open', closeCode: null, attempt: 0, ...info })
  }
}

/** A socket the test drives by hand. */
export class FakeSocket implements WebSocketLike {
  static instances: FakeSocket[] = []
  binaryType = 'blob'
  readyState = 0
  onopen: ((event: unknown) => void) | null = null
  onmessage: ((event: { data: unknown }) => void) | null = null
  onclose: ((event: { code: number; reason?: string }) => void) | null = null
  onerror: ((event: unknown) => void) | null = null
  sent: LiveClientMessage[] = []
  closedWith: number | undefined
  constructor(readonly url: string) {
    FakeSocket.instances.push(this)
  }
  send(data: Uint8Array): void {
    this.sent.push(decode(data) as LiveClientMessage)
  }
  close(code?: number): void {
    this.closedWith = code
    this.readyState = 3
  }
  // test helpers
  open(): void {
    this.readyState = 1
    this.onopen?.({})
  }
  receive(data: unknown): void {
    this.onmessage?.({ data })
  }
  drop(code: number): void {
    this.readyState = 3
    this.onclose?.({ code })
  }
}

export const fakeTimers = () => {
  vi.useFakeTimers()
  return () => vi.useRealTimers()
}
