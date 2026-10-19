// Generated from packs/schemas/threat-class.v1.json by `npm run contracts:gen`. Do not edit.

export type Category = 'drone' | 'clutter'
export type Contract = 'threat-class.v1'
export type DefaultDisposition = 'hostile' | 'civil-permitted' | 'clutter'
export type SourceId = string
export type Unit = string
export type Value = number
/**
 * True only when the value was checked against the source.
 */
export type Verified = boolean
export type Fictional = true
export type Id = string
export type En = string
export type Hi = string
export type RecognitionClass = string
export type UasGroup = ('1' | '2' | '3') | null
export type Version = string

export interface ThreatClass {
  category: Category
  contract: Contract
  default_disposition: DefaultDisposition
  envelope: Envelope
  fictional: Fictional
  id: Id
  notes?: Text | null
  recognition_class: RecognitionClass
  signature: Signature
  summary: Text
  title: Text
  uas_group: UasGroup
  version: Version
}
/**
 * How the class may move: the limits a scenario threat stays inside, plus a cruise speed.
 */
export interface Envelope {
  cruise_speed: Quantity
  max_accel: Quantity
  max_altitude: Quantity
  max_climb: Quantity
  max_descent: Quantity
  max_speed: Quantity
  max_turn_rate: Quantity
  min_altitude: Quantity
}
/**
 * A numeric parameter with its unit and provenance.
 *
 * This interface was referenced by `Signature`'s JSON-Schema definition
 * via the `patternProperty` "^[a-z][a-z0-9_]*$".
 */
export interface Quantity {
  source_id: SourceId
  unit: Unit
  value: Value
  verified: Verified
}
/**
 * User-facing text in both interface languages.
 */
export interface Text {
  en: En
  hi: Hi
}
export interface Signature {
  [k: string]: Quantity
}
