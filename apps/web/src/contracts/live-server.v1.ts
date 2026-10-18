// Generated from packs/schemas/live-server.v1.json by `npm run contracts:gen`. Do not edit.

export type LiveServerMessage = Welcome | Frame | Status3 | Ack | Pong | Ended | Fault
export type Actions = (
  | 'designate'
  | 'classify'
  | 'assess'
  | 'engage'
  | 'hold'
  | 'report'
  | 'track-relabel'
  | 'track-merge'
  | 'track-split'
  | 'track-drop'
  | 'sensor-cue'
)[]
export type Id = string
export type En = string
export type Hi = string
export type X = number
export type Y = number
export type Z = number
export type Assets = AssetView[]
export type DurationS = number
export type FromS = number
export type Id1 = string
export type RadiusM = number
export type ToS = number
export type FiledFlights = FlightView[]
export type HalfExtentM = number
export type Id2 = string
export type BoresightDeg = number
export type Id3 = string
export type Modality = 'radar' | 'eo' | 'ir' | 'rf' | 'acoustic'
export type Profile = string
export type Sensors = SensorSite[]
export type StartTimeOfDayH = number
export type Version = string
export type CloudCoverPct = number
export type Condition = 'clear' | 'haze' | 'rain' | 'fog' | 'dust'
export type TemperatureC = number
export type VisibilityM = number
export type WindFromDeg = number
export type WindSpeedMps = number
export type Id4 = string
export type RadiusM1 = number
export type Role = 'inner' | 'outer' | 'restricted'
export type Zones = ZoneView[]
export type DataNotice = string
export type Identities = ('hostile' | 'suspect' | 'unknown' | 'neutral' | 'friend')[]
export type OperatorClasses = string[]
export type Protocol = 1
export type DefaultAction = 'hold'
export type Id5 = string
export type EffectorClasses = EffectorView[]
export type Id6 = string
export type Authority = 'operator' | 'commander'
export type EffectorClasses1 = string[]
export type Id7 = string
export type Permits = string[]
export type JsonValue = unknown
export type Rules = RuleView[]
export type Version1 = string
export type SessionId = string
export type Status = 'lobby' | 'running' | 'ended' | 'abandoned'
export type T = 'welcome'
export type Tick = number
export type TickHz = 20
export type Basis = string
export type Confidence = number
export type DataStatus = 'reference' | 'verified'
export type Flag = 'threat' | 'no-threat'
export type ProposedClass = string | null
export type Source = string
export type Tick1 = number
export type Track = string
export type Assist = AssistView[]
export type DataNotice1 = string
export type Actor = string
export type Seq = number
export type T1 = number
export type Type = string
export type Events = TraineeEvent[]
export type AzimuthDeg = number
export type DataStatus1 = 'reference' | 'verified'
export type ElevationDeg = number
export type Modality1 = 'radar' | 'eo' | 'ir' | 'rf' | 'acoustic'
export type RadialSpeedMps = number | null
export type RangeM = number | null
export type ReportedClass = string | null
export type SensorId = string
export type SigmaAzimuthDeg = number | null
export type SigmaElevationDeg = number | null
export type SigmaRadialMps = number | null
export type SigmaRangeM = number | null
export type Tick2 = number
export type Reports = Report[]
export type BearingDeg = number
export type Cued = boolean
export type DataStatus2 = 'reference' | 'verified'
export type ElevationDeg1 = number
export type FovDeg = number | null
export type Id8 = string
export type Modality2 = 'radar' | 'eo' | 'ir' | 'rf' | 'acoustic'
export type Outage = boolean
export type PixelsH = number | null
export type SupportsCue = boolean
export type Sensors1 = SensorStatus[]
export type Status1 = 'lobby' | 'running' | 'ended' | 'abandoned'
export type T2 = 'frame'
export type Tick3 = number
export type TimeOfDayH = number
export type TimeS = number
export type AgeS = number
export type ClassEstimate = string | null
export type ClassSupport = number
export type DataStatus3 = 'reference' | 'verified'
export type HeadingDeg = number
export type Hits = number
export type Id9 = string
export type Label = string
export type Sensors2 = string[]
export type SigmaPositionM = number
export type SigmaSpeedMps = number
export type SinceUpdateS = number
export type SpeedMps = number
export type Status2 = 'tentative' | 'confirmed' | 'coasting'
export type Tick4 = number
export type Tracks = TrackView[]
export type Status4 = 'lobby' | 'running' | 'ended' | 'abandoned'
export type T3 = 'status'
export type Tick5 = number
export type Code = 'invalid' | 'not-running' | 'unknown-action' | 'too-many'
export type Message = string
export type Ok = boolean
export type Seq1 = number
export type T4 = 'ack'
export type Tick6 = number | null
export type T5 = 'pong'
export type Tick7 = number
export type Ts = number
export type Status5 = 'ended' | 'abandoned'
export type DurationS1 = number
export type EventCount = number
export type FinalStateHash = string
export type Head = string
export type Ticks = number
export type Verified = boolean
export type T6 = 'ended'
export type Code1 = string
export type Message1 = string
export type T7 = 'error'

export interface Welcome {
  actions: Actions
  briefing: Briefing
  data_notice: DataNotice
  identities: Identities
  operator_classes: OperatorClasses
  protocol: Protocol
  rules: RulesView
  session_id: SessionId
  status: Status
  t: T
  tick: Tick
  tick_hz: TickHz
}
/**
 * The scenario as the operator is briefed: the site, the sensors and the filed flights.
 * Never the threats.
 */
export interface Briefing {
  assets: Assets
  duration_s: DurationS
  filed_flights: FiledFlights
  half_extent_m: HalfExtentM
  id: Id2
  sensors: Sensors
  start_time_of_day_h: StartTimeOfDayH
  summary: Text
  title: Text
  version: Version
  weather: WeatherView
  zones: Zones
}
export interface AssetView {
  id: Id
  label: Text
  position: Vec3
}
/**
 * User-facing text in both interface languages.
 */
export interface Text {
  en: En
  hi: Hi
}
/**
 * Local east-north-up position in metres; z is height above the flat ground plane.
 */
export interface Vec3 {
  x: X
  y: Y
  z: Z
}
export interface FlightView {
  center: Vec3
  from_s: FromS
  id: Id1
  label: Text
  radius_m: RadiusM
  to_s: ToS
}
export interface SensorSite {
  boresight_deg: BoresightDeg
  id: Id3
  modality: Modality
  position: Vec3
  profile: Profile
}
export interface WeatherView {
  cloud_cover_pct: CloudCoverPct
  condition: Condition
  temperature_c: TemperatureC
  visibility_m: VisibilityM
  wind_from_deg: WindFromDeg
  wind_speed_mps: WindSpeedMps
}
export interface ZoneView {
  center: Vec3
  id: Id4
  label: Text
  radius_m: RadiusM1
  role: Role
}
/**
 * The rule pack in force, with its version, for the decision panel.
 */
export interface RulesView {
  default_action: DefaultAction
  effector_classes: EffectorClasses
  id: Id6
  rules: Rules
  title: Text
  version: Version1
}
export interface EffectorView {
  description: Text
  id: Id5
  label: Text
}
export interface RuleView {
  authority: Authority
  effector_classes: EffectorClasses1
  id: Id7
  permits: Permits
  title: Text
  when: When
}
export interface When {
  [k: string]: JsonValue
}
/**
 * One simulation tick as the operator's sensors and tracker saw it.
 */
export interface Frame {
  assist: Assist
  data_notice: DataNotice1
  events: Events
  reports: Reports
  sensors: Sensors1
  status: Status1
  t: T2
  tick: Tick3
  time_of_day_h: TimeOfDayH
  time_s: TimeS
  tracks: Tracks
}
export interface AssistView {
  basis: Basis
  confidence: Confidence
  data_status: DataStatus
  flag: Flag
  proposed_class: ProposedClass
  source: Source
  tick: Tick1
  track: Track
}
/**
 * An event the trainee may see (`sim.audience`): tracker lifecycle, the operator's own
 * commands, rules verdicts and session start and end. No ground truth.
 */
export interface TraineeEvent {
  actor: Actor
  payload: Payload
  seq: Seq
  t: T1
  type: Type
}
export interface Payload {
  [k: string]: JsonValue
}
/**
 * One sensor report this tick: a plot on the PPI, or something in the EO view.
 */
export interface Report {
  azimuth_deg: AzimuthDeg
  data_status: DataStatus1
  elevation_deg: ElevationDeg
  features: Features
  modality: Modality1
  radial_speed_mps: RadialSpeedMps
  range_m: RangeM
  reported_class: ReportedClass
  sensor_id: SensorId
  sigma_azimuth_deg: SigmaAzimuthDeg
  sigma_elevation_deg: SigmaElevationDeg
  sigma_radial_mps: SigmaRadialMps
  sigma_range_m: SigmaRangeM
  tick: Tick2
}
export interface Features {
  [k: string]: number | string | boolean
}
export interface SensorStatus {
  bearing_deg: BearingDeg
  cued: Cued
  data_status: DataStatus2
  elevation_deg: ElevationDeg1
  fov_deg: FovDeg
  id: Id8
  modality: Modality2
  outage: Outage
  pixels_h?: PixelsH
  position: Vec3
  supports_cue: SupportsCue
}
export interface TrackView {
  age_s: AgeS
  class_estimate: ClassEstimate
  class_support: ClassSupport
  data_status: DataStatus3
  heading_deg: HeadingDeg
  hits: Hits
  id: Id9
  label: Label
  position: Vec3
  sensors: Sensors2
  sigma_position_m: SigmaPositionM
  sigma_speed_mps: SigmaSpeedMps
  since_update_s: SinceUpdateS
  speed_mps: SpeedMps
  status: Status2
  tick: Tick4
  velocity: Vec3
}
export interface Status3 {
  status: Status4
  t: T3
  tick: Tick5
}
/**
 * The server received action `seq` (ok) or refused it before it reached the simulation.
 * The simulation's own decision (ROE verdict, rejection) arrives as events.
 */
export interface Ack {
  error?: AckError | null
  ok: Ok
  seq: Seq1
  t: T4
  tick?: Tick6
}
export interface AckError {
  code: Code
  message: Message
}
export interface Pong {
  t: T5
  tick: Tick7
  ts: Ts
}
export interface Ended {
  status: Status5
  summary: EndSummary
  t: T6
}
export interface EndSummary {
  duration_s: DurationS1
  event_count: EventCount
  final_state_hash: FinalStateHash
  head: Head
  ticks: Ticks
  verified: Verified
}
export interface Fault {
  code: Code1
  message: Message1
  t: T7
}
