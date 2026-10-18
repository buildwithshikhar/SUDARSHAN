// Generated from packs/schemas/action-record.v1.json by `npm run contracts:gen`. Do not edit.

export type Action =
  | ('designate' | 'classify' | 'assess' | 'engage' | 'hold' | 'report')
  | ('track-relabel' | 'track-merge' | 'track-split' | 'track-drop' | 'sensor-cue')
  | 'set-weather'
export type Actor = string
export type JsonValue = unknown
export type Tick = number

/**
 * A trainee or instructor input, applied at the start of `tick`.
 *
 * Pause and resume are not actions: a paused session simply stops ticking, so they never reach
 * the simulation and cannot change its outcome.
 */
export interface ActionRecord {
  action: Action
  actor: Actor
  payload?: Payload
  tick: Tick
}
export interface Payload {
  [k: string]: JsonValue
}
