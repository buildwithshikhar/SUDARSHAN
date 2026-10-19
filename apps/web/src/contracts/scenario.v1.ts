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
export type FromS = number
export type Id1 = string
export type RadiusM = number
export type ToS = number
/**
 * @maxItems 32
 */
export type FiledFlights = FiledFlight[]
export type Discipline = number
export type Id2 = string
export type Intent = 'transit' | 'loiter' | 'probe' | 'saturation'
export type Kind = 'swarm' | 'flock'
export type LaneSpacingM = number
export type Leader = string | null
export type LeaderLoss = 'elect' | 'disperse' | 'loiter'
export type LeaderLossHoldS = number
export type LinkEpochS = number
export type LinkLoss = number
export type LinkRangeM = number
export type LoiterRadiusM = number
/**
 * @minItems 2
 * @maxItems 64
 */
export type Members = [string, string, ...string[]]
export type NeighbourRadiusM = number
export type OnRouteEnd = 'loiter' | 'loop' | 'despawn'
export type ProbeCycles = number
export type ProbeStandoffM = number
/**
 * @minItems 1
 * @maxItems 200
 */
export type Route = [Waypoint, ...Waypoint[]]
export type HoldS = number
export type SpeedMps = number
export type SpacingM = number
export type Topology = 'leader-follower' | 'leaderless'
export type Alignment = number
export type Cohesion = number
export type Goal = number
export type Separation = number
/**
 * @maxItems 32
 */
export type Groups = Group[]
export type Id3 = string
export type Id4 = string
export type Version = string
export type BoresightDeg = number
export type Id5 = string
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
export type Disposition = 'hostile' | 'civil-permitted' | 'clutter'
export type Id6 = string
export type MaxAccelMps2 = number
export type MaxAltitudeM = number
export type MaxClimbMps = number
export type MaxDescentMps = number
export type MaxSpeedMps = number
export type MaxTurnRateDps = number
export type MinAltitudeM = number
export type Motion = (Tether | Drift) | null
export type Kind1 = 'tether'
export type LengthM = number
export type SwayM = number
export type SwayPeriodS = number
export type ClimbMps = number
export type Kind2 = 'drift'
export type OnRouteEnd1 = 'loiter' | 'loop' | 'despawn'
/**
 * @minItems 1
 * @maxItems 200
 */
export type Route1 = [Waypoint, ...Waypoint[]]
export type SpawnS = number
export type StartHeadingDeg = number
export type StartSpeedMps = number
export type TickHz = 20
export type Version1 = string
export type HalfExtentM = number
export type StartTimeOfDayH = number
export type Terrain = FlatTerrain | PackTerrain
export type ElevationM = number
export type Kind3 = 'flat'
export type Id7 = string
export type Kind4 = 'pack'
export type Version2 = string
export type CloudCoverPct = number
export type Condition = 'clear' | 'haze' | 'rain' | 'fog' | 'dust'
export type GustSigmaMps = number
export type TemperatureC = number
export type VisibilityM = number
export type WindFromDeg = number
export type WindSpeedMps = number
export type Id8 = string
export type RadiusM1 = number
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
  filed_flights?: FiledFlights
  groups?: Groups
  id: Id3
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
 * A civil flight plan the trainee is told about: an area and a time window, nothing more.
 *
 * It does not name the contact that flies it; matching a track to a plan is the trainee's job.
 */
export interface FiledFlight {
  center: Vec3
  from_s: FromS
  id: Id1
  label: Text
  radius_m: RadiusM
  to_s: ToS
}
/**
 * Members of a group are ordinary threats (own class, limits, spawn and start); the group
 * decides where they steer, and each member stays inside its own class envelope. Behaviour is
 * kinematics only: a member goes where the group's own route and its group-mates take it.
 *
 * Every numeric value is project-authored (register F01, verified: false); the model basis is
 * Reynolds boids, Vicsek noise, consensus with link loss and leader-follower, cited as the model
 * and never as validation (docs/02-research.md section 3).
 */
export interface Group {
  discipline?: Discipline
  id: Id2
  intent?: Intent
  kind?: Kind
  lane_spacing_m?: LaneSpacingM
  leader?: Leader
  leader_loss?: LeaderLoss
  leader_loss_hold_s?: LeaderLossHoldS
  link_epoch_s?: LinkEpochS
  link_loss?: LinkLoss
  link_range_m?: LinkRangeM
  loiter_radius_m?: LoiterRadiusM
  members: Members
  neighbour_radius_m?: NeighbourRadiusM
  on_route_end?: OnRouteEnd
  probe_cycles?: ProbeCycles
  probe_standoff_m?: ProbeStandoffM
  route: Route
  spacing_m?: SpacingM
  topology?: Topology
  weights?: GroupWeights
}
export interface Waypoint {
  hold_s?: HoldS
  position: Vec3
  speed_mps: SpeedMps
}
/**
 * Weights of the four flocking terms (Reynolds boids). Project-authored (register F01,
 * verified: false).
 */
export interface GroupWeights {
  alignment?: Alignment
  cohesion?: Cohesion
  goal?: Goal
  separation?: Separation
}
/**
 * Reference to another versioned pack by ID and exact version.
 */
export interface PackRef {
  id: Id4
  version: Version
}
export interface SensorPlacement {
  boresight_deg: BoresightDeg
  id: Id5
  position: Vec3
  profile: PackRef
}
export interface Threat {
  class_id: ClassId
  disposition?: Disposition
  id: Id6
  label: Text
  limits: KinematicLimits
  motion?: Motion
  on_route_end: OnRouteEnd1
  route: Route1
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
/**
 * Clutter motion: a kite held on a line from a fixed anchor. It rides downwind of the anchor
 * at about 50 degrees elevation, swaying across the wind; the route is ignored.
 */
export interface Tether {
  anchor: Vec3
  kind: Kind1
  length_m: LengthM
  sway_m: SwayM
  sway_period_s: SwayPeriodS
}
/**
 * Clutter motion: a free balloon carried by the wind (mean wind plus gust), climbing at
 * `climb_mps` until the top of its altitude band; the route is ignored.
 */
export interface Drift {
  climb_mps: ClimbMps
  kind: Kind2
}
export interface World {
  half_extent_m: HalfExtentM
  start_time_of_day_h: StartTimeOfDayH
  terrain: Terrain
  weather: Weather
}
export interface FlatTerrain {
  elevation_m?: ElevationM
  kind: Kind3
}
/**
 * A baked terrain pack (`packs/terrain/<id>/`, docs/TERRAIN_PACKS.md). Positions in the
 * scenario are metres above the pack datum, in the pack's local frame.
 */
export interface PackTerrain {
  id: Id7
  kind: Kind4
  version: Version2
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
  id: Id8
  label: Text
  radius_m: RadiusM1
  role: Role
}
