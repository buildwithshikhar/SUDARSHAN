// Generated from packs/schemas/action-record.v1.json by `npm run contracts:gen`. Do not edit.

export type Action =
  | ('designate' | 'classify' | 'assess' | 'engage' | 'hold' | 'report')
  | ('pause' | 'resume' | 'set-weather')
export type Actor = string
export type JsonValue = unknown
export type Tick = number

/**
 * A trainee or instructor input, applied at the start of `tick`.
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
