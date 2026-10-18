// Generated from packs/schemas/live-client.v1.json by `npm run contracts:gen`. Do not edit.

export type LiveClientMessage = Start | End | Act | Ping | Leave
export type T = 'start'
export type T1 = 'end'
export type Action =
  | 'designate'
  | 'classify'
  | 'assess'
  | 'engage'
  | 'hold'
  | 'report'
  | 'track-relabel'
  | 'track-merge'
  | 'track-split'
  | 'track-drop'
  | 'sensor-cue'
export type JsonValue = unknown
export type Seq = number
export type T2 = 'act'
export type T3 = 'ping'
export type Ts = number
export type T4 = 'leave'

/**
 * Begin ticking (lobby to running).
 */
export interface Start {
  t: T
}
/**
 * Finish the session now; the event log is stored and verified.
 */
export interface End {
  t: T1
}
/**
 * An operator input. `seq` is the client's own counter, echoed in the `ack`.
 */
export interface Act {
  action: Action
  payload?: Payload
  seq: Seq
  t: T2
}
export interface Payload {
  [k: string]: JsonValue
}
/**
 * Latency probe: the server echoes `ts` unchanged.
 */
export interface Ping {
  t: T3
  ts: Ts
}
/**
 * Leave without ending; the session pauses until the trainee rejoins or the grace expires.
 */
export interface Leave {
  t: T4
}
