// Generated from packs/schemas/session-record.v1.json by `npm run contracts:gen`. Do not edit.

export type Action =
  | ('designate' | 'classify' | 'assess' | 'engage' | 'hold' | 'report')
  | ('track-relabel' | 'track-merge' | 'track-split' | 'track-drop' | 'sensor-cue')
  | 'set-weather'
export type Actor = string
export type JsonValue = unknown
export type Tick = number
export type Actions = ActionRecord[]
export type Contract = 'session-record.v1'
export type Actor1 = string
export type Hash = string
export type PrevHash = string
export type Seq = number
export type T = number
export type Type = string
export type Events = EventRecord[]
export type FinalStateHash = string
export type Picture = boolean
export type Id = string
export type Version = string
export type Profiles = PackRef[]
export type Roe = boolean
export type Seed = number
export type ThreatClasses = PackRef[]
export type Ticks = number

/**
 * Everything needed to replay a session and check the replay matches.
 */
export interface SessionRecord {
  actions: Actions
  contract: Contract
  events: Events
  final_state_hash: FinalStateHash
  picture?: Picture
  profiles?: Profiles
  roe?: Roe
  scenario: PackRef
  seed: Seed
  threat_classes?: ThreatClasses
  ticks: Ticks
}
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
export interface EventRecord {
  actor: Actor1
  hash: Hash
  payload: Payload1
  prev_hash: PrevHash
  seq: Seq
  t: T
  type: Type
}
export interface Payload1 {
  [k: string]: JsonValue
}
/**
 * Reference to another versioned pack by ID and exact version.
 */
export interface PackRef {
  id: Id
  version: Version
}
