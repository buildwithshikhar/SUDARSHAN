/** One live session: a transport wired to a store, plus the operator commands. */
import type { ClientAction } from './protocol'
import { LiveStore } from './store'
import type { Transport } from './transport'

export class LiveSession {
  readonly store = new LiveStore()

  constructor(
    readonly transport: Transport,
    private readonly now: () => number = () => performance.now(),
  ) {}

  connect(): void {
    this.transport.open({
      onMessage: (message) => this.store.dispatch({ type: 'message', message, at: this.now() }),
      onConnection: (info) => this.store.dispatch({ type: 'connection', info }),
      onLatency: (ms) => this.store.dispatch({ type: 'latency', ms }),
    })
  }

  dispose(): void {
    this.transport.close()
  }

  start(): void {
    this.transport.start()
  }

  end(): void {
    this.transport.end()
  }

  leave(): void {
    this.transport.leave()
  }

  /** Send an operator input and track it until the server's events answer it. */
  act(action: ClientAction, payload: Record<string, unknown> = {}): number | null {
    const at = this.now()
    const seq = this.transport.act(action, payload)
    if (seq === null) this.store.dispatch({ type: 'send-failed', action, payload, at })
    else this.store.dispatch({ type: 'sent', seq, action, payload, at })
    return seq
  }
}
