// Generated from packs/schemas/rulepack.v1.json by `npm run contracts:gen`. Do not edit.

export type Contract = 'rulepack.v1'
export type DefaultAction = 'hold'
export type En = string
export type Hi = string
export type Id = string
export type SourceId = string
export type Unit = string
export type Value = number
/**
 * True only when the value was checked against the source.
 */
export type Verified = boolean
/**
 * @maxItems 16
 */
export type EffectorClasses = EffectorClass[]
export type Fictional = true
export type Id1 = string
/**
 * @minItems 1
 * @maxItems 64
 */
export type Rules = [Rule, ...Rule[]]
export type Authority = 'operator' | 'commander'
export type EffectorClasses1 = string[]
export type Id2 = string
/**
 * @minItems 1
 */
export type Permits = [
  'designate' | 'classify' | 'assess' | 'engage' | 'hold' | 'report',
  ...('designate' | 'classify' | 'assess' | 'engage' | 'hold' | 'report')[],
]
export type ClassificationIn = string[] | null
export type IdentityIn = ('hostile' | 'suspect' | 'unknown' | 'neutral' | 'friend')[] | null
export type MinConfidence = number | null
export type ZoneRoleIn = ('inner' | 'outer' | 'restricted')[] | null
export type ClassifyWithinS = number
export type DetectWithinS = number
export type ReportWithinS = number
export type Version = string
export type Assess = number
export type Classify = number
export type Detect = number
export type Report = number
export type Respond = number

export interface RulePack {
  contract: Contract
  default_action: DefaultAction
  effector_classes: EffectorClasses
  fictional: Fictional
  id: Id1
  rules: Rules
  thresholds: Thresholds
  title: Text
  version: Version
  weights: Weights
}
/**
 * A generic, fictional response class. No real system names or performance figures.
 */
export interface EffectorClass {
  description: Text
  id: Id
  label: Text
  max_range: Quantity
}
/**
 * User-facing text in both interface languages.
 */
export interface Text {
  en: En
  hi: Hi
}
/**
 * A numeric parameter with its unit and provenance.
 */
export interface Quantity {
  source_id: SourceId
  unit: Unit
  value: Value
  verified: Verified
}
export interface Rule {
  authority: Authority
  effector_classes?: EffectorClasses1
  id: Id2
  permits: Permits
  title: Text
  when: Condition
}
/**
 * All present fields must hold for a rule to apply; an absent field matches anything.
 */
export interface Condition {
  classification_in?: ClassificationIn
  identity_in?: IdentityIn
  min_confidence?: MinConfidence
  zone_role_in?: ZoneRoleIn
}
/**
 * Fictional, editable timing standards in seconds (no public doctrinal source; Q-12).
 */
export interface Thresholds {
  classify_within_s: ClassifyWithinS
  detect_within_s: DetectWithinS
  report_within_s: ReportWithinS
}
export interface Weights {
  assess: Assess
  classify: Classify
  detect: Detect
  report: Report
  respond: Respond
}
