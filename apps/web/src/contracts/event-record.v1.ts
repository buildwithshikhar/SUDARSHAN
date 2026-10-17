// Generated from packs/schemas/event-record.v1.json by `npm run contracts:gen`. Do not edit.

export type Actor = string
export type Hash = string
export type JsonValue = unknown
export type PrevHash = string
export type Seq = number
export type T = number
export type Type = string

export interface EventRecord {
  actor: Actor
  hash: Hash
  payload: Payload
  prev_hash: PrevHash
  seq: Seq
  t: T
  type: Type
}
export interface Payload {
  [k: string]: JsonValue
}
