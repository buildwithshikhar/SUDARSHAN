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
export type BlockedAttemptPenalty = number
export type ClassifyCorrectShare = number
export type EffectorHigherFactor = number
export type FalseEngagementCap = number
export type FalseEngagementPenalty = number
export type CountOffByOneScore = number
export type CountRadiusM = number
export type HeadingToleranceDeg = number
export type HeadingZeroFactor = number
export type PositionToleranceM = number
export type PositionZeroFactor = number
export type TimelinessWeight = number
export type Calibration = number
export type Count = number
export type Heading = number
export type What = number
export type Where = number
export type RespondTimingShare = number
/**
 * @minItems 1
 * @maxItems 8
 */
export type TimingBands = [TimingBand, ...TimingBand[]]
export type MaxFactor = number
export type Score = number
export type TrackErrorCap = number
export type TrackErrorPenalty = number
export type ClassifyWithinS = number
export type DetectWithinS = number
export type ReportWithinS = number
export type RespondWithinS = number
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
  scoring?: Scoring
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
 * How the decision tree turns what the operator did into marks. All fictional and editable.
 */
export interface Scoring {
  assess_credit?: AssessCredit
  blocked_attempt_penalty?: BlockedAttemptPenalty
  classify_correct_share?: ClassifyCorrectShare
  effector_higher_factor?: EffectorHigherFactor
  false_engagement_cap?: FalseEngagementCap
  false_engagement_penalty?: FalseEngagementPenalty
  report?: ReportGrading
  respond_credit?: RespondCredit
  respond_timing_share?: RespondTimingShare
  timing_bands?: TimingBands
  track_error_cap?: TrackErrorCap
  track_error_penalty?: TrackErrorPenalty
}
export interface AssessCredit {
  [k: string]: {
    [k: string]: number
  }
}
/**
 * Tolerances and marks for the structured contact report (fictional, editable).
 */
export interface ReportGrading {
  count_off_by_one_score?: CountOffByOneScore
  count_radius_m?: CountRadiusM
  heading_tolerance_deg?: HeadingToleranceDeg
  heading_zero_factor?: HeadingZeroFactor
  position_tolerance_m?: PositionToleranceM
  position_zero_factor?: PositionZeroFactor
  timeliness_weight?: TimelinessWeight
  weights?: ReportWeights
}
/**
 * How the five report fields add up to the report-quality score (sum to 1).
 */
export interface ReportWeights {
  calibration?: Calibration
  count?: Count
  heading?: Heading
  what?: What
  where?: Where
}
export interface RespondCredit {
  [k: string]: number
}
/**
 * Credit for a response that took up to `max_factor` times the standard.
 */
export interface TimingBand {
  max_factor: MaxFactor
  score: Score
}
/**
 * Fictional, editable timing standards in seconds (no public doctrinal source; Q-12).
 *
 * Each is measured from the first moment a sensor reported the contact.
 */
export interface Thresholds {
  classify_within_s: ClassifyWithinS
  detect_within_s: DetectWithinS
  report_within_s: ReportWithinS
  respond_within_s?: RespondWithinS
}
export interface Weights {
  assess: Assess
  classify: Classify
  detect: Detect
  report: Report
  respond: Respond
}
