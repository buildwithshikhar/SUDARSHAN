// Generated from packs/schemas/sensor-profile.v1.json by `npm run contracts:gen`. Do not edit.

/**
 * @minItems 2
 * @maxItems 32
 */
export type Labels = [string, string, ...string[]]
export type SourceId = string
/**
 * True only when the matrix was checked against the source.
 */
export type Verified = boolean
export type Contract = 'sensor-profile.v1'
export type Fictional = true
export type Id = string
export type Modality = 'radar' | 'eo' | 'ir' | 'rf' | 'acoustic'
export type En = string
export type Hi = string
export type SourceId1 = string
export type Unit = string
export type Value = number
/**
 * True only when the value was checked against the source.
 */
export type Verified1 = boolean
export type Version = string

export interface SensorProfile {
  confusion?: Confusion
  contract: Contract
  fictional: Fictional
  id: Id
  modality: Modality
  notes?: Text | null
  parameters: Parameters
  title: Text
  version: Version
}
export interface Confusion {
  [k: string]: ConfusionTable
}
/**
 * How a sensor labels each true class: one row per true class, one column per label.
 *
 * Rows are probabilities and sum to 1 (row-normalised). The columns are the labels the sensor
 * can report, `unknown` included; the true classes need not be a subset of them.
 *
 * This interface was referenced by `Confusion`'s JSON-Schema definition
 * via the `patternProperty` "^[a-z][a-z0-9_]*$".
 */
export interface ConfusionTable {
  labels: Labels
  rows: Rows
  source_id: SourceId
  verified: Verified
}
export interface Rows {
  /**
   * This interface was referenced by `Rows`'s JSON-Schema definition
   * via the `patternProperty` "^[a-z0-9]+(?:-[a-z0-9]+)*$".
   */
  [k: string]: number[]
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
  source_id: SourceId1
  unit: Unit
  value: Value
  verified: Verified1
}
