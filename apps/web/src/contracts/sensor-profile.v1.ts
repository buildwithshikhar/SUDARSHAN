// Generated from packs/schemas/sensor-profile.v1.json by `npm run contracts:gen`. Do not edit.

export type Contract = 'sensor-profile.v1'
export type Fictional = true
export type Id = string
export type Modality = 'radar' | 'eo' | 'ir' | 'rf' | 'acoustic'
export type En = string
export type Hi = string
export type SourceId = string
export type Unit = string
export type Value = number
/**
 * True only when the value was checked against the source.
 */
export type Verified = boolean
export type Version = string

export interface SensorProfile {
  contract: Contract
  fictional: Fictional
  id: Id
  modality: Modality
  notes?: Text | null
  parameters: Parameters
  title: Text
  version: Version
}
/**
 * User-facing text in both interface languages.
 */
export interface Text {
  en: En
  hi: Hi
}
export interface Parameters {
  [k: string]: Quantity
}
/**
 * A numeric parameter with its unit and provenance.
 *
 * This interface was referenced by `Parameters`'s JSON-Schema definition
 * via the `patternProperty` "^[a-z][a-z0-9_]*$".
 */
export interface Quantity {
  source_id: SourceId
  unit: Unit
  value: Value
  verified: Verified
}
