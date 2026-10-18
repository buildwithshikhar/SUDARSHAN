/**
 * Transport between the workspace and the live-session server.
 *
 * `Transport` is the seam: the real `WebSocketTransport` speaks MessagePack over
 * `/api/v1/sessions/{id}/ws`; the dev-only `ScriptedTransport` (live/mock.ts) plays a canned session.
 */
import {
  decodeServerMessage,
  encodeClientMessage,
  isEnded,
  isPong,
  TERMINAL_CLOSE_CODES,
  type ClientAction,
  type LiveClientMessage,
  type LiveServerMessage,
} from './protocol'

export type ConnectionState = 'connecting' | 'open' | 'reconnecting' | 'closed'

export interface ConnectionInfo {
  state: ConnectionState
  /** The last WebSocket close code seen, or null before any close. */
  closeCode: number | null
  /** Reconnect attempts since the last successful open (0 while open). */
  attempt: number
}

export interface TransportHandlers {
  onMessage: (message: LiveServerMessage) => void
  onConnection: (info: ConnectionInfo) => void
  onLatency: (ms: number) => void
}

export interface Transport {
  open(handlers: TransportHandlers): void
  /** Close for good; no reconnect. */
  close(): void
  start(): void
  end(): void
  leave(): void
  /** Send an operator input. Returns its sequence number, or null if the link is not open. */
  act(action: ClientAction, payload?: Record<string, unknown>): number | null
}

/** The part of the browser WebSocket the transport uses (so tests can inject a fake). */
export interface WebSocketLike {
  binaryType: string
  readyState: number
  onopen: ((event: unknown) => void) | null
  onmessage: ((event: { data: unknown }) => void) | null
  onclose: ((event: { code: number; reason?: string }) => void) | null
  onerror: ((event: unknown) => void) | null
  send(data: Uint8Array): void
  close(code?: number): void
}

export const WS_OPEN = 1

export interface WebSocketTransportOptions {
  url: string
  createSocket?: (url: string) => WebSocketLike
  /** First reconnect delay and the cap, in ms; the delay doubles each attempt. */
  backoffBaseMs?: number
  backoffMaxMs?: number
  pingIntervalMs?: number
  now?: () => number
  random?: () => number
}

/** `/api/v1/sessions/{id}/ws` on this page's host (ws or wss), or on `VITE_API_URL` when set. */
export function sessionSocketUrl(
  sessionId: string,
  location: Pick<Location, 'protocol' | 'host'> = window.location,
  apiBase: string | undefined = import.meta.env.VITE_API_URL as string | undefined,
): string {
  const path = `/api/v1/sessions/${encodeURIComponent(sessionId)}/ws`
  if (apiBase) return `${apiBase.replace(/^http/, 'ws').replace(/\/$/, '')}${path}`
  return `${location.protocol === 'https:' ? 'wss:' : 'ws:'}//${location.host}${path}`
}

/** The delay before reconnect attempt `attempt` (1 is the first), with up to 20% jitter. */
export function backoffDelay(
  attempt: number,
  baseMs: number,
  maxMs: number,
  random: () => number,
): number {
  const raw = Math.min(maxMs, baseMs * 2 ** Math.max(0, attempt - 1))
  return Math.round(raw * (0.8 + 0.4 * random()))
}

export class WebSocketTransport implements Transport {
  private readonly opts: Required<Omit<WebSocketTransportOptions, 'createSocket'>> & {
    createSocket: (url: string) => WebSocketLike
  }
  private handlers: TransportHandlers | null = null
  private socket: WebSocketLike | null = null
  private seq = 0
  private attempt = 0
  private closedByUs = false
  private endedSeen = false
  private lastCloseCode: number | null = null
  private pingTimer: ReturnType<typeof setInterval> | null = null
  private retryTimer: ReturnType<typeof setTimeout> | null = null

  constructor(options: WebSocketTransportOptions) {
    this.opts = {
      backoffBaseMs: 500,
      backoffMaxMs: 8000,
      pingIntervalMs: 2000,
      now: () => performance.now(),
      random: Math.random,
      createSocket: (url) => new WebSocket(url) as unknown as WebSocketLike,
      ...options,
    }
  }

  open(handlers: TransportHandlers): void {
    this.handlers = handlers
    this.closedByUs = false
    this.connect('connecting')
  }

  close(): void {
    this.closedByUs = true
    this.stopTimers()
    const socket = this.socket
    this.socket = null
    if (socket) {
      socket.onclose = null
      socket.onmessage = null
      socket.onerror = null
      socket.close(1000)
    }
    this.report('closed')
  }

  start(): void {
    this.sendRaw({ t: 'start' })
  }
  end(): void {
    this.sendRaw({ t: 'end' })
  }
  leave(): void {
    this.sendRaw({ t: 'leave' })
  }

  act(action: ClientAction, payload: Record<string, unknown> = {}): number | null {
    if (!this.isOpen()) return null
    const seq = ++this.seq
    this.sendRaw({ t: 'act', seq, action, payload })
    return seq
  }

  // ------------------------------------------------------------------ internals

  private isOpen(): boolean {
    return this.socket !== null && this.socket.readyState === WS_OPEN
  }

  private sendRaw(message: LiveClientMessage): void {
    if (!this.isOpen() || !this.socket) return
    this.socket.send(encodeClientMessage(message))
  }

  private report(state: ConnectionState): void {
    this.handlers?.onConnection({ state, closeCode: this.lastCloseCode, attempt: this.attempt })
  }

  private connect(state: 'connecting' | 'reconnecting'): void {
    this.report(state)
    let socket: WebSocketLike
    try {
      socket = this.opts.createSocket(this.opts.url)
    } catch {
      this.scheduleRetry()
      return
    }
    socket.binaryType = 'arraybuffer'
    this.socket = socket
    socket.onopen = () => {
      this.attempt = 0
      this.report('open')
      this.startPing()
    }
    socket.onmessage = (event) => {
      // Text frames are not part of the protocol; ignore them.
      if (!(event.data instanceof ArrayBuffer) && !(event.data instanceof Uint8Array)) return
      const message = decodeServerMessage(event.data)
      if (!message) return
      if (isPong(message)) {
        this.handlers?.onLatency(Math.max(0, Math.round(this.opts.now() - message.ts)))
      }
      if (isEnded(message)) this.endedSeen = true
      this.handlers?.onMessage(message)
    }
    socket.onerror = () => {
      /* the close event that follows carries the code */
    }
    socket.onclose = (event) => {
      this.stopTimers()
      this.socket = null
      this.lastCloseCode = event.code
      if (this.closedByUs) return
      if (this.endedSeen || TERMINAL_CLOSE_CODES.has(event.code) || event.code === 1000) {
        this.report('closed')
        return
      }
      this.scheduleRetry()
    }
  }

  private scheduleRetry(): void {
    this.attempt += 1
    this.report('reconnecting')
    const delay = backoffDelay(
      this.attempt,
      this.opts.backoffBaseMs,
      this.opts.backoffMaxMs,
      this.opts.random,
    )
    this.retryTimer = setTimeout(() => {
      this.retryTimer = null
      if (!this.closedByUs) this.connect('reconnecting')
    }, delay)
  }

  private startPing(): void {
    this.stopPing()
    const ping = () => this.sendRaw({ t: 'ping', ts: Math.floor(this.opts.now()) })
    ping()
    this.pingTimer = setInterval(ping, this.opts.pingIntervalMs)
  }

  private stopPing(): void {
    if (this.pingTimer !== null) clearInterval(this.pingTimer)
    this.pingTimer = null
  }

  private stopTimers(): void {
    this.stopPing()
    if (this.retryTimer !== null) clearTimeout(this.retryTimer)
    this.retryTimer = null
  }
}
