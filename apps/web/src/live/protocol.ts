/**
 * The live-session wire protocol as the browser sees it: the generated message types (never edited
 * here), type guards on the `t` discriminator, and the MessagePack codec. See docs/LIVE_SESSION.md.
 */
import { decode, encode } from '@msgpack/msgpack'
import type { LiveClientMessage } from '../contracts/live-client.v1'
import type {
  Ack,
  AssistView,
  Briefing,
  EndSummary,
  Ended,
  Fault,
  Frame,
  LiveServerMessage,
  Pong,
  Report,
  RuleView,
  RulesView,
  SensorStatus,
  Status3 as StatusMessage,
  TraineeEvent,
  TrackView,
  Vec3,
  Welcome,
  ZoneView,
} from '../contracts/live-server.v1'

export type {
  Ack,
  AssistView,
  Briefing,
  EndSummary,
  Ended,
  Fault,
  Frame,
  LiveClientMessage,
  LiveServerMessage,
  Pong,
  Report,
  RuleView,
  RulesView,
  SensorStatus,
  StatusMessage,
  TraineeEvent,
  TrackView,
  Vec3,
  Welcome,
  ZoneView,
}

export type ClientAction = Extract<LiveClientMessage, { t: 'act' }>['action']
export type SessionStatus = Frame['status']
export type Identity = Welcome['identities'][number]
export type Text = Briefing['title']

/** WebSocket close codes the server uses (docs/LIVE_SESSION.md). */
export const CLOSE = {
  notSignedIn: 4401,
  forbidden: 4403,
  notFound: 4404,
  superseded: 4408,
  ended: 4409,
  tooLarge: 4413,
  full: 1013,
} as const

/** Close codes after which the client must not reconnect. */
export const TERMINAL_CLOSE_CODES: ReadonlySet<number> = new Set(Object.values(CLOSE))

const SERVER_TYPES = ['welcome', 'frame', 'status', 'ack', 'pong', 'ended', 'error'] as const

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

/** A cheap structural check on a decoded value: the `t` is known and the essential fields exist. */
export function parseServerMessage(raw: unknown): LiveServerMessage | null {
  if (!isRecord(raw) || typeof raw.t !== 'string') return null
  if (!(SERVER_TYPES as readonly string[]).includes(raw.t)) return null
  switch (raw.t) {
    case 'welcome':
      return isRecord(raw.briefing) && isRecord(raw.rules) && Array.isArray(raw.operator_classes)
        ? (raw as unknown as Welcome)
        : null
    case 'frame':
      return typeof raw.tick === 'number' &&
        typeof raw.time_s === 'number' &&
        Array.isArray(raw.tracks) &&
        Array.isArray(raw.reports) &&
        Array.isArray(raw.sensors) &&
        Array.isArray(raw.events) &&
        Array.isArray(raw.assist)
        ? (raw as unknown as Frame)
        : null
    case 'status':
      return typeof raw.status === 'string' && typeof raw.tick === 'number'
        ? (raw as unknown as StatusMessage)
        : null
    case 'ack':
      return typeof raw.seq === 'number' && typeof raw.ok === 'boolean'
        ? (raw as unknown as Ack)
        : null
    case 'pong':
      return typeof raw.ts === 'number' ? (raw as unknown as Pong) : null
    case 'ended':
      return isRecord(raw.summary) ? (raw as unknown as Ended) : null
    case 'error':
      return typeof raw.code === 'string' ? (raw as unknown as Fault) : null
    default:
      return null
  }
}

export const isWelcome = (m: LiveServerMessage): m is Welcome => m.t === 'welcome'
export const isFrame = (m: LiveServerMessage): m is Frame => m.t === 'frame'
export const isStatus = (m: LiveServerMessage): m is StatusMessage => m.t === 'status'
export const isAck = (m: LiveServerMessage): m is Ack => m.t === 'ack'
export const isPong = (m: LiveServerMessage): m is Pong => m.t === 'pong'
export const isEnded = (m: LiveServerMessage): m is Ended => m.t === 'ended'
export const isFault = (m: LiveServerMessage): m is Fault => m.t === 'error'

export function encodeClientMessage(message: LiveClientMessage): Uint8Array {
  return encode(message)
}

/** Decode one binary frame. Returns null for anything that is not a known server message. */
export function decodeServerMessage(data: ArrayBuffer | Uint8Array): LiveServerMessage | null {
  try {
    return parseServerMessage(decode(data))
  } catch {
    return null
  }
}

export function encodeServerMessage(message: LiveServerMessage): Uint8Array {
  return encode(message)
}
