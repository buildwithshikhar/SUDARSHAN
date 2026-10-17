// Generated from packs/schemas/scenario.v1.json by `npm run contracts:gen`. Do not edit.

export type Id = string
export type En = string
export type Hi = string
export type X = number
export type Y = number
export type Z = number
/**
 * @maxItems 32
 */
export type Assets = DefendedAsset[]
export type Contract = 'scenario.v1'
export type DefaultSeed = number
export type DurationS = number
export type Fictional = true
export type Id1 = string
export type Id2 = string
export type Version = string
export type BoresightDeg = number
export type Id3 = string
/**
 * @maxItems 32
 */
export type Sensors = SensorPlacement[]
/**
 * @minItems 1
 * @maxItems 256
 */
export type Threats = [Threat, ...Threat[]]
export type ClassId = string
export type Id4 = string
export type MaxAccelMps2 = number
export type MaxAltitudeM = number
export type MaxClimbMps = number
export type MaxDescentMps = number
export type MaxSpeedMps = number
export type MaxTurnRateDps = number
export type MinAltitudeM = number
export type OnRouteEnd = 'loiter' | 'loop' | 'despawn'
/**
 * @minItems 1
 * @maxItems 200
 */
export type Route = [Waypoint, ...Waypoint[]]
export type HoldS = number
export type SpeedMps = number
export type SpawnS = number
export type StartHeadingDeg = number
export type StartSpeedMps = number
export type TickHz = 20
export type Version1 = string
export type HalfExtentM = number
export type StartTimeOfDayH = number
export type ElevationM = number
export type Kind = 'flat'
export type CloudCoverPct = number
export type Condition = 'clear' | 'haze' | 'rain' | 'fog' | 'dust'
export type GustSigmaMps = number
export type TemperatureC = number
export type VisibilityM = number
export type WindFromDeg = number
export type WindSpeedMps = number
export type Id5 = string
export type RadiusM = number
export type Role = 'inner' | 'outer' | 'restricted'
/**
 * @maxItems 32
 */
export type Zones = Zone[]

export interface ScenarioSpec {
  assets?: Assets
  contract: Contract
  default_seed: DefaultSeed
  duration_s: DurationS
  fictional: Fictional
  id: Id1
  rule_pack: PackRef
  sensors?: Sensors
  summary: Text
  threats: Threats
  tick_hz?: TickHz
  title: Text
  version: Version1
  world: World
  zones?: Zones
}
export interface DefendedAsset {
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
/**
 * Reference to another versioned pack by ID and exact version.
 */
export interface PackRef {
  id: Id2
  version: Version
}
export interface SensorPlacement {
  boresight_deg: BoresightDeg
  id: Id3
  position: Vec3
  profile: PackRef
}
export interface Threat {
  class_id: ClassId
  id: Id4
  label: Text
  limits: KinematicLimits
  on_route_end: OnRouteEnd
  route: Route
  spawn_s: SpawnS
  start: Vec3
  start_heading_deg: StartHeadingDeg
  start_speed_mps: StartSpeedMps
}
/**
 * Envelope of a threat class. Airspeed, not ground speed, is limited.
 */
export interface KinematicLimits {
  max_accel_mps2: MaxAccelMps2
  max_altitude_m: MaxAltitudeM
  max_climb_mps: MaxClimbMps
  max_descent_mps: MaxDescentMps
  max_speed_mps: MaxSpeedMps
  max_turn_rate_dps: MaxTurnRateDps
  min_altitude_m: MinAltitudeM
}
export interface Waypoint {
  hold_s?: HoldS
  position: Vec3
  speed_mps: SpeedMps
}
export interface World {
  half_extent_m: HalfExtentM
  start_time_of_day_h: StartTimeOfDayH
  terrain: Terrain
  weather: Weather
}
export interface Terrain {
  elevation_m?: ElevationM
  kind: Kind
}
/**
 * Modelled weather at session start. Wind blows from `wind_from_deg` (0 = north).
 */
export interface Weather {
  cloud_cover_pct: CloudCoverPct
  condition: Condition
  gust_sigma_mps: GustSigmaMps
  temperature_c: TemperatureC
  visibility_m: VisibilityM
  wind_from_deg: WindFromDeg
  wind_speed_mps: WindSpeedMps
}
/**
 * Circular zone on the ground plane around a centre point.
 */
export interface Zone {
  center: Vec3
  id: Id5
  label: Text
  radius_m: RadiusM
  role: Role
}
