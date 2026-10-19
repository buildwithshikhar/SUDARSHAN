// Generated from packs/schemas/score-result.v1.json by `npm run contracts:gen`. Do not edit.

export type Contract = 'score-result.v1'
export type DecisionScore = number | null
export type DurationS = number
export type EventHead = string
export type Cost = number
export type Kind =
  | 'hard-fail'
  | 'track-error'
  | 'blocked-attempt'
  | 'false-alarm'
  | 'false-engagement'
  | 'not-presented'
  | 'not-worked'
export type JsonValue = unknown
export type Reason = string
export type Findings = Finding[]
export type Cost1 = number
export type Key = string
export type ThreatId = string | null
export type Lessons = Lesson[]
export type Id = string
export type Version = string
export type Profiles = PackRef[]
export type ReportScore = number | null
export type ReportWeight = number
export type En = string
export type Hi = string
export type Score = number | null
export type CorrectRejections = number
export type Corrected = boolean
export type Criterion = number | null
export type DPrime = number | null
export type FalseAlarmRate = number | null
export type FalseAlarmRateUsed = number | null
export type FalseAlarms = number
export type HitRate = number | null
export type HitRateUsed = number | null
export type Hits = number
export type Misses = number
export type NoiseTrials = number
export type SignalTrials = number
export type Seed = number
export type ThreatClasses = PackRef[]
export type ClassId = string
export type Decision = number | null
export type Disposition = 'hostile' | 'civil-permitted' | 'clutter'
export type Findings1 = Finding[]
export type FirstReportS = number | null
export type HardFail = boolean
export type Node = 'detect' | 'classify' | 'assess' | 'respond'
export type Reason1 = string
export type Score1 = number
export type Weight = number
export type Nodes = NodeResult[]
export type Presented = boolean
export type Field = 'what' | 'where' | 'count' | 'heading' | 'calibration'
export type Reason2 = string
export type Score2 = number
export type Weight1 = number
export type Fields = FieldMark[]
export type Filed = boolean
export type Quality = number
export type Reason3 = string
export type ReportsFiled = number
export type Score3 = number
export type Timeliness = number | null
export type Score4 = number | null
export type ThreatId1 = string
export type Worked = boolean
export type Threats = ThreatScore[]
export type Ticks = number

export interface SessionScore {
  contract: Contract
  decision_score: DecisionScore
  duration_s: DurationS
  event_head: EventHead
  findings?: Findings
  lessons?: Lessons
  profiles?: Profiles
  report_score: ReportScore
  report_weight: ReportWeight
  rule_pack: PackRef
  scenario: PackRef
  scenario_title: Text
  score: Score
  sdt: Sdt
  seed: Seed
  threat_classes?: ThreatClasses
  threats: Threats
  ticks: Ticks
}
/**
 * Something that cost marks or deserves a plain statement: a hard fail, an unfixed track
 * error, a blocked response, a false alarm.
 */
export interface Finding {
  cost?: Cost
  kind: Kind
  params?: Params
  reason: Reason
}
export interface Params {
  [k: string]: JsonValue
}
/**
 * One of the first lessons: where the most marks were lost.
 */
export interface Lesson {
  cost: Cost1
  key: Key
  params?: Params1
  threat_id?: ThreatId
}
export interface Params1 {
  [k: string]: JsonValue
}
/**
 * Reference to another versioned pack by ID and exact version.
 */
export interface PackRef {
  id: Id
  version: Version
}
/**
 * User-facing text in both interface languages.
 */
export interface Text {
  en: En
  hi: Hi
}
/**
 * Signal-detection metrics for the session's threat-or-not calls.
 */
export interface Sdt {
  correct_rejections: CorrectRejections
  corrected: Corrected
  criterion: Criterion
  d_prime: DPrime
  false_alarm_rate: FalseAlarmRate
  false_alarm_rate_used: FalseAlarmRateUsed
  false_alarms: FalseAlarms
  hit_rate: HitRate
  hit_rate_used: HitRateUsed
  hits: Hits
  misses: Misses
  noise_trials: NoiseTrials
  signal_trials: SignalTrials
}
/**
 * The path of one scenario contact through Detect, Classify, Assess and Respond.
 */
export interface ThreatScore {
  class_id: ClassId
  decision?: Decision
  disposition: Disposition
  findings?: Findings1
  first_report_s?: FirstReportS
  hard_fail?: HardFail
  label: Text
  nodes?: Nodes
  presented: Presented
  report?: ReportGrade | null
  score?: Score4
  threat_id: ThreatId1
  worked?: Worked
}
export interface NodeResult {
  node: Node
  params?: Params2
  reason: Reason1
  score: Score1
  weight: Weight
}
export interface Params2 {
  [k: string]: JsonValue
}
export interface ReportGrade {
  fields?: Fields
  filed: Filed
  params?: Params4
  quality?: Quality
  reason?: Reason3
  reports_filed?: ReportsFiled
  score?: Score3
  timeliness?: Timeliness
}
export interface FieldMark {
  field: Field
  params?: Params3
  reason: Reason2
  score: Score2
  weight: Weight1
}
export interface Params3 {
  [k: string]: JsonValue
}
export interface Params4 {
  [k: string]: JsonValue
}
