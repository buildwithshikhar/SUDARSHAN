/**
 * DEV-ONLY scripted session. Loaded through `createTransport` behind `import.meta.env.DEV` and
 * `?mock=1`, so it is absent from production builds (tests/prodBuild.test.ts checks this).
 *
 * It plays a believable one-minute session shaped exactly like the protocol: a welcome for a
 * fictional site, radar plots every 1.2 s per target, EO reports when the camera is pointed near a
 * target, RF reports, assist views, tracker events and ROE verdicts answering `act`. Every figure
 * is invented reference data; none of it is measured or operational.
 */
import type { LiveClientMessage } from '../contracts/live-client.v1'
import { DEG, polarFrom, wrap180, wrap360 } from './geometry'
import type {
  Ack,
  ClientAction,
  Frame,
  LiveServerMessage,
  Report,
  RuleView,
  RulesView,
  SensorStatus,
  SessionStatus,
  TraineeEvent,
  TrackView,
  Vec3,
  Welcome,
} from './protocol'
import type { Transport, TransportHandlers } from './transport'

export const MOCK_MARKER = 'scripted-transport-marker-7f3a1c'

const DATA_NOTICE = 'Reference data: invented figures in a fictional scenario (mock transport).'
const DURATION_S = 64
const TICK_HZ = 20

// ---------------------------------------------------------------------- fixtures

export const MOCK_RULES: RulesView = {
  id: 'training-baseline',
  version: '1.0.0',
  title: { en: 'Training baseline rules', hi: 'प्रशिक्षण आधार नियम' },
  default_action: 'hold',
  effector_classes: [
    {
      id: 'ec-a',
      label: {
        en: 'Effector class A (generic, non-kinetic)',
        hi: 'प्रभावक वर्ग A (सामान्य, गैर-गतिज)',
      },
      description: {
        en: 'Generic fictional soft response class used for training decisions only.',
        hi: 'केवल प्रशिक्षण निर्णयों के लिए प्रयुक्त सामान्य काल्पनिक सॉफ्ट प्रतिक्रिया वर्ग।',
      },
    },
    {
      id: 'ec-b',
      label: { en: 'Effector class B (generic, kinetic)', hi: 'प्रभावक वर्ग B (सामान्य, गतिज)' },
      description: {
        en: 'Generic fictional hard response class; release needs commander authority.',
        hi: 'सामान्य काल्पनिक हार्ड प्रतिक्रिया वर्ग; प्रयोग के लिए कमांडर का अधिकार आवश्यक है।',
      },
    },
  ],
  rules: [
    {
      id: 'track-everything',
      title: {
        en: 'Designate and classify every contact',
        hi: 'हर संपर्क को चिह्नित और वर्गीकृत करें',
      },
      when: {},
      permits: ['designate', 'classify', 'assess', 'report', 'hold'],
      authority: 'operator',
      effector_classes: [],
    },
    {
      id: 'suspect-outer-zone',
      title: {
        en: 'Suspect contact in the outer zone may receive a class A response',
        hi: 'बाहरी क्षेत्र में संदिग्ध संपर्क पर वर्ग A प्रतिक्रिया दी जा सकती है',
      },
      when: {
        identity_in: ['suspect', 'hostile'],
        zone_role_in: ['outer', 'inner'],
        min_confidence: 0.6,
      },
      permits: ['engage'],
      authority: 'operator',
      effector_classes: ['ec-a'],
    },
    {
      id: 'hostile-inner-zone',
      title: {
        en: 'Hostile contact in the inner zone may receive a class B response',
        hi: 'आंतरिक क्षेत्र में शत्रु संपर्क पर वर्ग B प्रतिक्रिया दी जा सकती है',
      },
      when: { identity_in: ['hostile'], zone_role_in: ['inner'], min_confidence: 0.8 },
      permits: ['engage'],
      authority: 'commander',
      effector_classes: ['ec-a', 'ec-b'],
    },
  ],
}

export const MOCK_WELCOME: Welcome = {
  t: 'welcome',
  protocol: 1,
  session_id: 'mock-session',
  status: 'lobby',
  tick: 0,
  tick_hz: TICK_HZ,
  data_notice: DATA_NOTICE,
  operator_classes: ['rotary-small', 'fixed-wing-small', 'bird', 'unknown'],
  identities: ['hostile', 'suspect', 'unknown', 'neutral', 'friend'],
  actions: [
    'designate',
    'classify',
    'assess',
    'engage',
    'hold',
    'report',
    'track-relabel',
    'track-merge',
    'track-split',
    'track-drop',
    'sensor-cue',
  ],
  rules: MOCK_RULES,
  briefing: {
    id: 'harrier-field-afternoon-watch',
    version: '0.3.1-mock',
    title: { en: 'Harrier Field: afternoon watch', hi: 'हैरियर फील्ड: दोपहर की निगरानी' },
    summary: {
      en: 'A small rotary contact closes on the field from the north-east while a civil survey flight and a bird flock work the outer zone.',
      hi: 'एक छोटा रोटरी संपर्क उत्तर-पूर्व से मैदान की ओर आता है, जबकि एक नागरिक सर्वे उड़ान और पक्षियों का झुंड बाहरी क्षेत्र में हैं।',
    },
    duration_s: DURATION_S,
    start_time_of_day_h: 15.6,
    half_extent_m: 5000,
    terrain: { kind: 'flat', elevation_m: 0 },
    weather: {
      condition: 'clear',
      visibility_m: 9400,
      wind_speed_mps: 4.2,
      wind_from_deg: 232,
      temperature_c: 31.4,
      cloud_cover_pct: 18,
    },
    zones: [
      {
        id: 'inner',
        role: 'inner',
        label: { en: 'Inner zone', hi: 'आंतरिक क्षेत्र' },
        center: { x: 0, y: 0, z: 0 },
        radius_m: 900,
      },
      {
        id: 'outer',
        role: 'outer',
        label: { en: 'Outer zone', hi: 'बाहरी क्षेत्र' },
        center: { x: 0, y: 0, z: 0 },
        radius_m: 3200,
      },
    ],
    assets: [
      {
        id: 'harrier-ops',
        label: { en: 'Harrier Field operations block', hi: 'हैरियर फील्ड संचालन ब्लॉक' },
        position: { x: 0, y: 0, z: 0 },
      },
    ],
    sensors: [
      {
        id: 'radar-1',
        modality: 'radar',
        profile: 'radar-generic-s',
        position: { x: -140, y: 85, z: 6 },
        boresight_deg: 45,
      },
      {
        id: 'eo-1',
        modality: 'eo',
        profile: 'eo-day-generic',
        position: { x: -126, y: 92, z: 9 },
        boresight_deg: 38,
      },
      {
        id: 'rf-1',
        modality: 'rf',
        profile: 'rf-passive-generic',
        position: { x: 212, y: -158, z: 5 },
        boresight_deg: 0,
      },
      {
        id: 'acoustic-1',
        modality: 'acoustic',
        profile: 'acoustic-generic-array',
        position: { x: 640, y: 560, z: 4 },
        boresight_deg: 0,
      },
    ],
    filed_flights: [
      {
        id: 'FF-2207',
        label: { en: 'Survey flight, civil quadcopter', hi: 'सर्वे उड़ान, नागरिक क्वाडकॉप्टर' },
        center: { x: -1120, y: -900, z: 64 },
        radius_m: 640,
        from_s: 0,
        to_s: 540,
      },
    ],
  },
}

/** Why a contact report is refused, by the simulation's own ranges; null when it is well formed. */
export function reportProblem(payload: Record<string, unknown>): string | null {
  const check = (key: string, lo: number, hi: number, upperOpen: boolean, whole = false) => {
    if (!(key in payload)) return null
    const v = payload[key]
    if (typeof v !== 'number' || !Number.isFinite(v)) return `${key} must be a number`
    if (whole && !Number.isInteger(v)) return `${key} must be a whole number`
    if (v < lo || (upperOpen ? v >= hi : v > hi))
      return `${key} must be from ${lo} to ${upperOpen ? 'under ' : ''}${hi}`
    return null
  }
  if (
    'class_id' in payload &&
    !(MOCK_WELCOME.operator_classes as string[]).includes(String(payload.class_id))
  )
    return 'class_id must be one of the operator classes'
  return (
    check('count', 1, 99, false, true) ??
    check('bearing_deg', 0, 360, true) ??
    check('range_m', 0, 50_000, false) ??
    check('heading_deg', 0, 360, true) ??
    check('confidence', 0, 1, false)
  )
}

// ---------------------------------------------------------------------- the world

interface Entity {
  key: string
  cls: 'rotary-small' | 'bird'
  /** Physical size in metres, for the EO apparent size. */
  sizeM: number
  spawnS: number
  phaseS: number
  pos: (t: number) => Vec3
  support: (t: number) => number
  estimate: (t: number) => string | null
  emitsRf: { band: string; hopping: boolean; hopHz: number } | null
  assist: { flag: 'threat' | 'no-threat'; confidence: number; cls: string | null }
}

const orbit =
  (cx: number, cy: number, r: number, z: number, speed: number, phase = 0) =>
  (t: number): Vec3 => {
    const a = phase + (speed / r) * t
    return { x: cx + r * Math.cos(a), y: cy + r * Math.sin(a), z: z + 3 * Math.sin(t / 5) }
  }
const drift =
  (x: number, y: number, z: number, vx: number, vy: number, wob: number) =>
  (t: number): Vec3 => ({
    x: x + vx * t + wob * Math.sin(t / 2.7),
    y: y + vy * t + wob * Math.cos(t / 3.3),
    z: z + 6 * Math.sin(t / 4.1),
  })

const ENTITIES: Entity[] = [
  {
    key: 'civil',
    cls: 'rotary-small',
    sizeM: 0.62,
    spawnS: 0.5,
    phaseS: 0.2,
    pos: orbit(-1120, -900, 640, 64, 7.4, 0.9),
    support: (t) => Math.min(0.71, 0.4 + t * 0.012),
    estimate: () => 'rotary-small',
    emitsRf: { band: '5.8 GHz', hopping: false, hopHz: 0 },
    assist: { flag: 'threat', confidence: 0.64, cls: 'rotary-small' },
  },
  {
    key: 'bird-1',
    cls: 'bird',
    sizeM: 0.85,
    spawnS: 1.7,
    phaseS: 0.5,
    pos: drift(740, -420, 41, -2.3, 1.1, 24),
    support: (t) => Math.min(0.81, 0.5 + t * 0.01),
    estimate: () => 'bird',
    emitsRf: null,
    assist: { flag: 'no-threat', confidence: 0.88, cls: 'bird' },
  },
  {
    key: 'bird-2',
    cls: 'bird',
    sizeM: 0.8,
    spawnS: 2.4,
    phaseS: 0.9,
    pos: drift(-640, 1530, 118, 3.1, -1.4, 30),
    support: (t) => Math.min(0.74, 0.46 + t * 0.011),
    estimate: () => 'bird',
    emitsRf: null,
    assist: { flag: 'no-threat', confidence: 0.83, cls: 'bird' },
  },
  {
    key: 'hostile',
    cls: 'rotary-small',
    sizeM: 0.9,
    spawnS: 3.2,
    phaseS: 0.1,
    pos: (t) => ({
      x: 1180 - 9.7 * t + 14 * Math.sin(t / 6),
      y: 1050 - 9.6 * t + 11 * Math.cos(t / 7),
      z: 86 - 0.55 * t + 4 * Math.sin(t / 3.7),
    }),
    support: (t) => Math.min(0.86, 0.38 + t * 0.0105),
    estimate: (t) => (t < 6 ? 'unknown' : 'rotary-small'),
    emitsRf: { band: '2.4 GHz', hopping: true, hopHz: 41.6 },
    assist: { flag: 'threat', confidence: 0.83, cls: 'rotary-small' },
  },
  {
    key: 'bird-3',
    cls: 'bird',
    sizeM: 0.7,
    spawnS: 5.9,
    phaseS: 0.7,
    pos: drift(1480, -940, 63, -1.9, 2.6, 18),
    support: (t) => Math.min(0.58, 0.31 + t * 0.006),
    estimate: (t) => (t < 14 ? 'unknown' : 'bird'),
    emitsRf: null,
    assist: { flag: 'no-threat', confidence: 0.71, cls: 'bird' },
  },
  {
    key: 'bird-4',
    cls: 'bird',
    sizeM: 0.8,
    spawnS: 9.1,
    phaseS: 0.3,
    pos: drift(-1810, -310, 32, 2.2, 0.8, 21),
    support: (t) => Math.min(0.69, 0.44 + t * 0.008),
    estimate: () => 'bird',
    emitsRf: null,
    assist: { flag: 'no-threat', confidence: 0.79, cls: 'bird' },
  },
]

function site(id: string) {
  const found = MOCK_WELCOME.briefing.sensors.find((s) => s.id === id)
  if (!found) throw new Error(`mock sensor ${id} missing`)
  return found
}
const RADAR = site('radar-1')
const EO = site('eo-1')
const RF = site('rf-1')
const ACOUSTIC = site('acoustic-1')
/** The mock microphone array hears out to this slant range in metres (the profile's own limit is a fictional project value). */
const ACOUSTIC_RANGE_M = 330
const RADAR_PERIOD_S = 1.2
const EO_HOME = { bearing: EO.boresight_deg, elevation: 4.2, fov: 24.4 }
const EO_NARROW_FOV = 2.6
const EO_SLEW_DPS = 30
const CUE_HOLD_S = 12

interface MockTrack {
  id: string
  entity: Entity
  label: string
  born: number
  hits: number
  status: 'tentative' | 'confirmed' | 'coasting'
  estimate: { pos: Vec3; vel: Vec3; at: number }
  lastUpdate: number
  sensors: Set<string>
  /** A clone made by the operator: it has no reports of its own and is folded back. */
  cloneOf: string | null
  cloneUntil: number
}

interface Pointing {
  bearing: number
  elevation: number
  fov: number
  cuedUntil: number
  cuedTrack: string | null
}

const round = (value: number, digits = 1): number => {
  const k = 10 ** digits
  return Math.round(value * k) / k
}
/** Deterministic wobble in [-1, 1] so replays look the same. */
const wobble = (seed: number, t: number): number =>
  Math.sin(seed * 12.9898 + t * 3.17) * Math.cos(seed * 4.1 + t * 1.31)
const vel = (entity: Entity, t: number): Vec3 => {
  const a = entity.pos(t - 0.05)
  const b = entity.pos(t + 0.05)
  return { x: (b.x - a.x) / 0.1, y: (b.y - a.y) / 0.1, z: (b.z - a.z) / 0.1 }
}

interface Verdict {
  permitted: boolean
  code: string
  rule: RuleView | null
  detail: Record<string, unknown>
}

interface RoeContext {
  identity: string | null
  classification: string | null
  zone_role: string | null
  confidence: number
}

/** The rules check, ported from the server's pure function (same codes and detail). */
export function evaluateRoe(
  rules: RulesView,
  action: string,
  ctx: RoeContext,
  effector: string | null,
  commander = false,
): Verdict {
  const unmetOf = (rule: RuleView) => {
    const when = rule.when as Record<string, unknown>
    const out: Record<string, unknown>[] = []
    const identityIn = when.identity_in as string[] | undefined
    if (identityIn && !identityIn.includes(ctx.identity ?? 'unknown'))
      out.push({ field: 'identity', required: identityIn, actual: ctx.identity })
    const classIn = when.classification_in as string[] | undefined
    if (classIn && !(ctx.classification !== null && classIn.includes(ctx.classification)))
      out.push({ field: 'classification', required: classIn, actual: ctx.classification })
    const zoneIn = when.zone_role_in as string[] | undefined
    if (zoneIn && !(ctx.zone_role !== null && zoneIn.includes(ctx.zone_role)))
      out.push({ field: 'zone', required: zoneIn, actual: ctx.zone_role })
    const min = when.min_confidence as number | undefined
    if (min !== undefined && ctx.confidence < min)
      out.push({ field: 'confidence', required: min, actual: round(ctx.confidence, 3) })
    return out
  }
  const candidates = rules.rules.filter((r) => r.permits.includes(action))
  const gaps: {
    distance: number
    index: number
    rule: RuleView
    unmet: Record<string, unknown>[]
    effectorOk: boolean
    authorityOk: boolean
  }[] = []
  for (const [index, rule] of candidates.entries()) {
    const unmet = unmetOf(rule)
    const effectorOk =
      action !== 'engage' || (effector !== null && rule.effector_classes.includes(effector))
    const authorityOk = rule.authority === 'operator' || commander
    if (unmet.length === 0 && effectorOk && authorityOk)
      return { permitted: true, code: 'permitted', rule, detail: { effector_class: effector } }
    gaps.push({
      distance: unmet.length + (effectorOk ? 0 : 2) + (authorityOk ? 0 : 1),
      index,
      rule,
      unmet,
      effectorOk,
      authorityOk,
    })
  }
  if (action === 'hold') return { permitted: true, code: 'default-hold', rule: null, detail: {} }
  if (gaps.length === 0)
    return { permitted: false, code: 'no-rule', rule: null, detail: { action } }
  const best = gaps.reduce((a, b) =>
    b.distance < a.distance || (b.distance === a.distance && b.index < a.index) ? b : a,
  )
  if (best.unmet.length > 0)
    return { permitted: false, code: 'conditions', rule: best.rule, detail: { unmet: best.unmet } }
  if (!best.effectorOk)
    return {
      permitted: false,
      code: 'effector',
      rule: best.rule,
      detail: { effector_class: effector, allowed: best.rule.effector_classes },
    }
  return {
    permitted: false,
    code: 'authority',
    rule: best.rule,
    detail: { required: best.rule.authority },
  }
}

/**
 * Scenario variants for the dev-server mock (`?mock=1&eo=thermal&terrain=fixture-ridge&rain=1&hour=22`):
 * the EO camera type, a terrain pack, rain and the start hour. They exist so the 3D view can be
 * exercised without the API; none of this ships in production builds.
 */
export interface MockVariant {
  eo?: 'day' | 'nv' | 'thermal'
  terrain?: string
  condition?: Welcome['briefing']['weather']['condition']
  hour?: number
}

const EO_PROFILE = { day: 'eo-generic-day', nv: 'eo-generic-nv', thermal: 'ir-generic-thermal' }

/** The welcome for a variant; the unchanged `MOCK_WELCOME` when there is none. */
export function mockWelcome(variant: MockVariant = {}): Welcome {
  if (!variant.eo && !variant.terrain && !variant.condition && variant.hour === undefined) {
    return MOCK_WELCOME
  }
  const briefing = {
    ...MOCK_WELCOME.briefing,
    start_time_of_day_h: variant.hour ?? MOCK_WELCOME.briefing.start_time_of_day_h,
    weather: {
      ...MOCK_WELCOME.briefing.weather,
      condition: variant.condition ?? MOCK_WELCOME.briefing.weather.condition,
    },
    sensors: MOCK_WELCOME.briefing.sensors.map((s) =>
      s.id === 'eo-1' && variant.eo
        ? {
            ...s,
            modality: variant.eo === 'thermal' ? ('ir' as const) : s.modality,
            profile: EO_PROFILE[variant.eo],
          }
        : s,
    ),
  }
  const terrain: Welcome['briefing']['terrain'] = variant.terrain
    ? { kind: 'pack', id: variant.terrain, version: '1.0.0' }
    : briefing.terrain
  return { ...MOCK_WELCOME, briefing: { ...briefing, terrain } }
}

export class MockWorld {
  tick = 0
  status: SessionStatus = 'lobby'
  private seq = 0
  private nextTrack = 11
  private readonly tracks = new Map<string, MockTrack>()
  private readonly owner = new Map<string, string>()
  private readonly assessed: Record<string, string> = {}
  private readonly classified: Record<string, string> = {}
  private readonly pendingActs: { action: ClientAction; payload: Record<string, unknown> }[] = []
  private events: TraineeEvent[] = []
  private eventCount = 0
  readonly pointing: Pointing = { ...EO_HOME, cuedUntil: -1, cuedTrack: null }
  private readonly eoModality: 'eo' | 'ir'
  private readonly startHour: number

  constructor(variant: MockVariant = {}) {
    this.eoModality = variant.eo === 'thermal' ? 'ir' : 'eo'
    this.startHour = variant.hour ?? MOCK_WELCOME.briefing.start_time_of_day_h
  }

  get timeS(): number {
    return this.tick / TICK_HZ
  }

  /** Queue an operator action for the next tick; returns the ack. */
  receive(message: Extract<LiveClientMessage, { t: 'act' }>): Ack {
    if (this.status !== 'running')
      return {
        t: 'ack',
        seq: message.seq,
        ok: false,
        error: { code: 'not-running', message: 'the session is not running' },
      }
    if (!(MOCK_WELCOME.actions as string[]).includes(message.action))
      return {
        t: 'ack',
        seq: message.seq,
        ok: false,
        error: { code: 'unknown-action', message: `unknown action ${message.action}` },
      }
    this.pendingActs.push({
      action: message.action as ClientAction,
      payload: (message.payload ?? {}) as Record<string, unknown>,
    })
    return { t: 'ack', seq: message.seq, ok: true, tick: this.tick + 1 }
  }

  start(): Frame {
    this.status = 'running'
    this.emit('session.start', {})
    return this.snapshot()
  }

  /** The join frame, sent before `start`. */
  snapshot(): Frame {
    const events = this.events
    this.events = []
    return this.frame([], events)
  }

  /** Advance one tick and return the frame. */
  step(): Frame {
    this.tick += 1
    const t = this.timeS
    for (const act of this.pendingActs.splice(0)) this.apply(act.action, act.payload)
    this.updatePointing(t)
    const reports: Report[] = []
    this.radar(t, reports)
    this.eo(t, reports)
    this.rf(t, reports)
    this.acoustic(t, reports)
    this.lifecycle(t)
    const assist = this.assistViews()
    const events = this.events
    this.events = []
    return this.frame(reports, events, assist)
  }

  finished(): boolean {
    return this.timeS >= DURATION_S
  }

  end(): { eventCount: number } {
    this.status = 'ended'
    this.emit('session.end', {})
    return { eventCount: this.eventCount }
  }

  // ------------------------------------------------------------------ internals

  private emit(type: string, payload: Record<string, unknown>, actor = 'sim'): void {
    this.seq += 1
    this.eventCount += 1
    this.events.push({
      seq: this.seq,
      t: this.tick,
      type,
      actor,
      payload: payload as TraineeEvent['payload'],
    })
  }

  private liveTracks(): MockTrack[] {
    return [...this.tracks.values()]
  }

  private radar(t: number, reports: Report[]): void {
    for (const entity of ENTITIES) {
      if (t < entity.spawnS) continue
      // Each target is painted once per radar period, at its own phase.
      const sinceTicks = this.tick - Math.round(entity.phaseS * TICK_HZ)
      if (sinceTicks < 0 || sinceTicks % Math.round(RADAR_PERIOD_S * TICK_HZ) !== 0) continue
      // One bird is lost for a few seconds at the edge of cover.
      if (entity.key === 'bird-4' && t > 30 && t < 34) continue
      const tp = t
      const truth = entity.pos(tp)
      const polar = polarFrom(RADAR.position, truth)
      if (polar.rangeM > 4800) continue
      const k = ENTITIES.indexOf(entity)
      const azimuth = wrap360(polar.bearingDeg + 0.4 * wobble(k, tp))
      const range = polar.slantM + 14 * wobble(k + 7, tp)
      const v = vel(entity, tp)
      const radial =
        ((truth.x - RADAR.position.x) * v.x +
          (truth.y - RADAR.position.y) * v.y +
          (truth.z - RADAR.position.z) * v.z) /
        Math.max(polar.slantM, 1)
      reports.push({
        tick: this.tick,
        sensor_id: 'radar-1',
        modality: 'radar',
        azimuth_deg: round(azimuth, 2),
        elevation_deg: round(polar.elevationDeg + 0.6 * wobble(k + 3, tp), 2),
        range_m: round(range, 1),
        radial_speed_mps: round(radial + 0.3 * wobble(k + 5, tp), 2),
        sigma_azimuth_deg: 0.42,
        sigma_elevation_deg: 0.9,
        sigma_range_m: 14.7,
        sigma_radial_mps: 0.35,
        reported_class: null,
        features: {
          micro_doppler: entity.cls === 'bird' ? 'wingbeat' : 'rotor',
          md_modulation_hz: entity.cls === 'bird' ? 6.2 : 118.4,
        },
        data_status: 'reference',
      })
      this.associate(entity, tp, truth, v, t)
    }
  }

  /** Feed a plot to the tracker: start a track, or update the one that owns the entity. */
  private associate(entity: Entity, tp: number, truth: Vec3, v: Vec3, t: number): void {
    const k = ENTITIES.indexOf(entity)
    const noisy = (value: number, seed: number) => value + 9 * wobble(k * 3 + seed, tp)
    const estimate = {
      pos: { x: noisy(truth.x, 1), y: noisy(truth.y, 2), z: truth.z + 4 * wobble(k + 9, tp) },
      vel: { x: v.x + 0.4 * wobble(k + 11, tp), y: v.y + 0.4 * wobble(k + 13, tp), z: v.z },
      at: t,
    }
    let id = this.owner.get(entity.key)
    let track = id ? this.tracks.get(id) : undefined
    if (!track) {
      id = `T${String(this.nextTrack).padStart(3, '0')}`
      this.nextTrack += id === 'T014' ? 3 : 1
      track = {
        id,
        entity,
        label: id,
        born: t,
        hits: 1,
        status: 'tentative',
        estimate,
        lastUpdate: t,
        sensors: new Set(['radar-1']),
        cloneOf: null,
        cloneUntil: 0,
      }
      this.tracks.set(id, track)
      this.owner.set(entity.key, id)
      this.emit('track.init', { track: id })
      return
    }
    track.hits += 1
    track.estimate = estimate
    track.lastUpdate = t
    track.sensors.add('radar-1')
    if (track.status === 'coasting') {
      track.status = 'confirmed'
      this.emit('track.resume', { track: track.id })
    } else if (track.status === 'tentative' && track.hits >= 3) {
      track.status = 'confirmed'
      this.emit('track.confirm', { track: track.id })
    }
  }

  private updatePointing(t: number): void {
    const p = this.pointing
    const dt = 1 / TICK_HZ
    let goal = { bearing: EO_HOME.bearing, elevation: EO_HOME.elevation, fov: EO_HOME.fov }
    if (p.cuedTrack && t < p.cuedUntil) {
      const track = this.tracks.get(p.cuedTrack)
      if (track) {
        const here = this.trackPosition(track, t)
        const polar = polarFrom(EO.position, here)
        goal = { bearing: polar.bearingDeg, elevation: polar.elevationDeg, fov: EO_NARROW_FOV }
      }
    } else if (p.cuedTrack) {
      p.cuedTrack = null
    }
    const dB = wrap180(goal.bearing - p.bearing)
    const step = EO_SLEW_DPS * dt
    p.bearing = wrap360(p.bearing + Math.max(-step, Math.min(step, dB)))
    p.elevation += Math.max(-step, Math.min(step, goal.elevation - p.elevation))
    p.fov += Math.max(-4 * dt, Math.min(4 * dt, goal.fov - p.fov))
  }

  private eo(t: number, reports: Report[]): void {
    if (this.tick % 10 !== 0) return
    const p = this.pointing
    for (const entity of ENTITIES) {
      if (t < entity.spawnS) continue
      const truth = entity.pos(t)
      const polar = polarFrom(EO.position, truth)
      const off = Math.hypot(
        wrap180(polar.bearingDeg - p.bearing),
        polar.elevationDeg - p.elevation,
      )
      if (off > p.fov / 2 || polar.slantM > 4200) continue
      const ifovDeg = p.fov / 1920
      const apparentPx = entity.sizeM / (polar.slantM * ifovDeg * DEG)
      if (apparentPx < 1.4) continue
      const recognised = apparentPx >= 13
      const k = ENTITIES.indexOf(entity)
      reports.push({
        tick: this.tick,
        sensor_id: 'eo-1',
        modality: this.eoModality,
        azimuth_deg: round(wrap360(polar.bearingDeg + 0.02 * wobble(k, t)), 3),
        elevation_deg: round(polar.elevationDeg + 0.02 * wobble(k + 1, t), 3),
        range_m: null,
        radial_speed_mps: null,
        sigma_azimuth_deg: round((p.fov / 1920) * 3.5, 4),
        sigma_elevation_deg: round((p.fov / 1920) * 3.5, 4),
        sigma_range_m: null,
        sigma_radial_mps: null,
        reported_class: recognised ? entity.cls : null,
        features: { apparent_px: round(apparentPx, 1), recognised },
        data_status: 'reference',
      })
      const id = this.owner.get(entity.key)
      if (id) this.tracks.get(id)?.sensors.add('eo-1')
    }
  }

  private rf(t: number, reports: Report[]): void {
    if (this.tick % 16 !== 0) return
    for (const entity of ENTITIES) {
      if (!entity.emitsRf || t < entity.spawnS + 2) continue
      const truth = entity.pos(t)
      const polar = polarFrom(RF.position, truth)
      if (polar.rangeM > 2600) continue
      const k = ENTITIES.indexOf(entity)
      reports.push({
        tick: this.tick,
        sensor_id: 'rf-1',
        modality: 'rf',
        azimuth_deg: round(wrap360(polar.bearingDeg + 2.1 * wobble(k + 21, t)), 1),
        elevation_deg: round(polar.elevationDeg + 3 * wobble(k + 22, t), 1),
        range_m: null,
        radial_speed_mps: null,
        sigma_azimuth_deg: 6.5,
        sigma_elevation_deg: 12,
        sigma_range_m: null,
        sigma_radial_mps: null,
        reported_class: null,
        features: {
          band: entity.emitsRf.band,
          rssi_dbm: round(-96 + 28 * Math.exp(-polar.slantM / 1400) + 2.2 * wobble(k + 23, t), 1),
          hopping: entity.emitsRf.hopping,
          ...(entity.emitsRf.hopping
            ? { hop_rate_hz: round(entity.emitsRf.hopHz + 1.9 * wobble(k + 24, t), 1) }
            : {}),
        },
        data_status: 'reference',
      })
      const id = this.owner.get(entity.key)
      if (id) this.tracks.get(id)?.sensors.add('rf-1')
    }
  }

  /** Rotor noise from a rotary contact inside the array's short range; birds are not heard. */
  private acoustic(t: number, reports: Report[]): void {
    if (this.tick % 10 !== 0) return
    for (const entity of ENTITIES) {
      if (entity.cls !== 'rotary-small' || t < entity.spawnS + 2) continue
      const truth = entity.pos(t)
      const polar = polarFrom(ACOUSTIC.position, truth)
      if (polar.slantM > ACOUSTIC_RANGE_M) continue
      const k = ENTITIES.indexOf(entity)
      const snr = 10 + 20 * Math.log10(ACOUSTIC_RANGE_M / Math.max(polar.slantM, 20))
      const harmonics = Math.max(1, Math.min(8, 1 + Math.floor((snr - 10) / 3)))
      reports.push({
        tick: this.tick,
        sensor_id: 'acoustic-1',
        modality: 'acoustic',
        azimuth_deg: round(wrap360(polar.bearingDeg + 4 * wobble(k + 31, t)), 1),
        elevation_deg: round(polar.elevationDeg + 6 * wobble(k + 32, t), 1),
        range_m: null,
        radial_speed_mps: null,
        sigma_azimuth_deg: 8,
        sigma_elevation_deg: 14,
        sigma_range_m: null,
        sigma_radial_mps: null,
        reported_class: null,
        features: {
          blade_pass_hz: round(188 + 3.4 * wobble(k + 33, t), 1),
          harmonics,
          tonal: harmonics >= 3,
          snr_db: round(snr + 0.9 * wobble(k + 34, t), 1),
        },
        data_status: 'reference',
      })
    }
  }

  private lifecycle(t: number): void {
    // One bird track starves for a few seconds, as a real tracker's would at the edge of cover.
    const bird4 = this.owner.get('bird-4')
    const track = bird4 ? this.tracks.get(bird4) : undefined
    if (track && track.status === 'confirmed' && t > 30 && t < 34.2) {
      track.status = 'coasting'
      track.lastUpdate = Math.min(track.lastUpdate, t - 1.2)
      this.emit('track.coast', { track: track.id })
    }
    for (const clone of this.liveTracks()) {
      if (clone.cloneOf && t >= clone.cloneUntil) {
        this.tracks.delete(clone.id)
        this.emit('track.drop', {
          track: clone.id,
          reason: 'merged',
          merged_into: clone.cloneOf,
          age_s: round(t - clone.born, 1),
        })
      }
    }
  }

  private trackPosition(track: MockTrack, t: number): Vec3 {
    const dt = Math.max(0, t - track.estimate.at)
    return {
      x: track.estimate.pos.x + track.estimate.vel.x * dt,
      y: track.estimate.pos.y + track.estimate.vel.y * dt,
      z: track.estimate.pos.z + track.estimate.vel.z * dt,
    }
  }

  private trackView(track: MockTrack, t: number): TrackView {
    const position = this.trackPosition(track, t)
    const v = track.estimate.vel
    const cloneBlind = track.cloneOf !== null
    const sinceUpdate = cloneBlind ? t - track.born : t - track.lastUpdate
    const stalled = track.status === 'coasting'
    return {
      id: track.id,
      label: track.label,
      status: track.status,
      tick: this.tick,
      age_s: round(t - track.born, 1),
      since_update_s: round(Math.max(0, stalled ? t - track.lastUpdate : sinceUpdate), 1),
      hits: track.hits,
      position: { x: round(position.x), y: round(position.y), z: round(position.z) },
      velocity: { x: round(v.x), y: round(v.y), z: round(v.z) },
      speed_mps: round(Math.hypot(v.x, v.y, v.z), 1),
      heading_deg: round(wrap360(Math.atan2(v.x, v.y) / DEG), 1),
      sigma_position_m: round(
        Math.max(11.8, 41 - track.hits * 1.9 + (stalled ? (t - track.lastUpdate) * 6 : 0)),
        1,
      ),
      sigma_speed_mps: round(Math.max(0.6, 3.8 - track.hits * 0.11), 1),
      class_estimate: track.status === 'tentative' ? null : track.entity.estimate(t - track.born),
      class_support: round(
        track.status === 'tentative' ? 0 : track.entity.support(t - track.born),
        2,
      ),
      sensors: [...track.sensors].sort(),
      data_status: 'reference',
    }
  }

  private assistViews(): Frame['assist'] {
    const out: Frame['assist'] = []
    for (const track of this.liveTracks()) {
      if (track.status === 'tentative') continue
      const a = track.entity.assist
      out.push({
        track: track.id,
        tick: Math.floor(this.tick / 60) * 60,
        flag: a.flag,
        confidence: round(Math.min(0.95, a.confidence + 0.01 * wobble(track.hits, 1)), 2),
        proposed_class: a.cls,
        source: 'simulated assist',
        basis: 'configured hit and false-alarm rates; no real detector',
        data_status: 'reference',
      })
    }
    return out
  }

  private sensors(): SensorStatus[] {
    const p = this.pointing
    return [
      {
        id: 'radar-1',
        modality: 'radar',
        position: RADAR.position,
        bearing_deg: RADAR.boresight_deg,
        elevation_deg: 0,
        fov_deg: null,
        cued: false,
        supports_cue: false,
        outage: false,
        data_status: 'reference',
      },
      {
        id: 'eo-1',
        modality: this.eoModality,
        position: EO.position,
        bearing_deg: round(p.bearing, 3),
        elevation_deg: round(p.elevation, 3),
        fov_deg: round(p.fov, 3),
        cued: p.cuedTrack !== null,
        supports_cue: true,
        outage: false,
        data_status: 'reference',
      },
      {
        id: 'rf-1',
        modality: 'rf',
        position: RF.position,
        bearing_deg: RF.boresight_deg,
        elevation_deg: 0,
        fov_deg: null,
        cued: false,
        supports_cue: false,
        outage: false,
        data_status: 'reference',
      },
      {
        id: 'acoustic-1',
        modality: 'acoustic',
        position: ACOUSTIC.position,
        bearing_deg: ACOUSTIC.boresight_deg,
        elevation_deg: 0,
        fov_deg: null,
        cued: false,
        supports_cue: false,
        outage: false,
        data_status: 'reference',
      },
    ]
  }

  private frame(reports: Report[], events: TraineeEvent[], assist: Frame['assist'] = []): Frame {
    const t = this.timeS
    return {
      t: 'frame',
      tick: this.tick,
      time_s: round(t, 2),
      time_of_day_h: round(this.startHour + t / 3600, 4),
      status: this.status,
      reports,
      tracks: this.liveTracks().map((track) => this.trackView(track, t)),
      assist,
      sensors: this.sensors(),
      events,
      data_notice: DATA_NOTICE,
    }
  }

  // ------------------------------------------------------------------ operator actions

  private reject(action: string, reason: string, payload: Record<string, unknown>): void {
    this.emit('action.rejected', { action, reason, payload }, 'operator')
  }

  private zoneRole(position: Vec3): string | null {
    const zones = [...MOCK_WELCOME.briefing.zones].sort((a, b) => a.radius_m - b.radius_m)
    return (
      zones.find((z) => polarFrom(z.center, { ...position, z: 0 }).rangeM <= z.radius_m)?.role ??
      null
    )
  }

  private apply(action: ClientAction, payload: Record<string, unknown>): void {
    const t = this.timeS
    const actor = 'operator'
    const trackId = typeof payload.track === 'string' ? payload.track : null
    const track = trackId ? this.tracks.get(trackId) : undefined
    const needsTrack: ClientAction[] = [
      'designate',
      'classify',
      'assess',
      'engage',
      'hold',
      'report',
      'track-relabel',
      'track-split',
      'track-drop',
      'sensor-cue',
    ]
    if (needsTrack.includes(action) && !track) {
      this.reject(action, `no live track ${JSON.stringify(trackId)}`, payload)
      return
    }
    if (track && ['designate', 'classify', 'assess', 'engage', 'hold', 'report'].includes(action)) {
      if (action === 'classify' && typeof payload.class_id !== 'string')
        return this.reject(action, 'classify needs a class_id', payload)
      if (
        action === 'assess' &&
        !(MOCK_WELCOME.identities as string[]).includes(String(payload.identity))
      )
        return this.reject(
          action,
          'assess needs an identity, one of hostile, suspect, unknown, neutral, friend',
          payload,
        )
      if (action === 'engage' && typeof payload.effector_class !== 'string')
        return this.reject(action, 'engage needs an effector_class', payload)
      if (action === 'report') {
        const problem = reportProblem(payload)
        if (problem) return this.reject(action, problem, payload)
      }
      const view = this.trackView(track, t)
      const ctx: RoeContext = {
        identity: this.assessed[track.id] ?? null,
        classification: this.classified[track.id] ?? null,
        zone_role: this.zoneRole(view.position),
        confidence: view.class_support,
      }
      const effector = typeof payload.effector_class === 'string' ? payload.effector_class : null
      const verdict = evaluateRoe(MOCK_RULES, action, ctx, effector)
      this.emit(
        'roe.verdict',
        {
          action,
          track: track.id,
          ...(effector ? { effector_class: effector } : {}),
          context: ctx as unknown as Record<string, unknown>,
          permitted: verdict.permitted,
          code: verdict.code,
          rule_id: verdict.rule?.id ?? null,
          rule_title: verdict.rule?.title ?? null,
          pack_id: MOCK_RULES.id,
          pack_version: MOCK_RULES.version,
          authority: verdict.rule?.authority ?? null,
          detail: verdict.detail,
        },
        actor,
      )
      if (!verdict.permitted) return
      if (action === 'classify') this.classified[track.id] = String(payload.class_id)
      if (action === 'assess') this.assessed[track.id] = String(payload.identity)
      this.emit(`action.${action}`, payload, actor)
      return
    }
    switch (action) {
      case 'track-relabel': {
        const label = typeof payload.label === 'string' ? payload.label.trim() : ''
        if (!track) return
        if (label.length < 1 || label.length > 24)
          return this.reject(action, 'a label is 1 to 24 characters', payload)
        if (label === track.label)
          return this.reject(action, `track ${track.id} is already labelled '${label}'`, payload)
        const other = this.liveTracks().find((x) => x.id !== track.id && x.label === label)
        if (other && payload.exchange !== true)
          return this.reject(
            action,
            `label '${label}' is on track ${other.id}; exchange labels to take it`,
            payload,
          )
        const previous = track.label
        track.label = label
        const body: Record<string, unknown> = { track: track.id, label, previous }
        if (other) {
          other.label = previous
          body.exchanged_with = other.id
        }
        this.emit('action.track_relabel', payload, actor)
        this.emit('track.relabel', body, actor)
        return
      }
      case 'track-merge': {
        const ids = Array.isArray(payload.tracks) ? payload.tracks.map(String) : []
        const pair = ids.map((id) => this.tracks.get(id))
        if (ids.length !== 2 || ids[0] === ids[1])
          return this.reject(action, 'a merge needs exactly two different tracks', payload)
        if (pair.some((x) => !x)) return this.reject(action, 'no such live track', payload)
        if (pair.some((x) => x?.status === 'tentative'))
          return this.reject(action, 'a tentative track cannot be merged', payload)
        const [survivor, absorbed] = [...(pair as MockTrack[])].sort((a, b) =>
          a.id.localeCompare(b.id),
        )
        if (!survivor || !absorbed) return
        absorbed.sensors.forEach((s) => survivor.sensors.add(s))
        this.tracks.delete(absorbed.id)
        this.owner.delete(absorbed.entity.key)
        this.emit('action.track_merge', payload, actor)
        this.emit('track.merge', { survivor: survivor.id, absorbed: absorbed.id }, actor)
        return
      }
      case 'track-split': {
        if (!track) return
        const id = `T${String(this.nextTrack).padStart(3, '0')}`
        this.nextTrack += 1
        this.tracks.set(id, {
          ...track,
          id,
          label: id,
          born: t,
          sensors: new Set(track.sensors),
          estimate: { ...track.estimate },
          cloneOf: track.id,
          cloneUntil: t + 8.5,
        })
        this.emit('action.track_split', payload, actor)
        this.emit('track.split', { source: track.id, new: id }, actor)
        return
      }
      case 'track-drop': {
        if (!track) return
        this.tracks.delete(track.id)
        if (this.owner.get(track.entity.key) === track.id) this.owner.delete(track.entity.key)
        this.emit('action.track_drop', payload, actor)
        this.emit(
          'track.drop',
          { track: track.id, reason: 'operator', age_s: round(t - track.born, 1) },
          actor,
        )
        return
      }
      case 'sensor-cue': {
        if (!track) return
        const sensor = String(payload.sensor)
        const refuse = (reason: string) =>
          this.emit(
            'sensor.cue',
            {
              sensor,
              track: track.id,
              bearing_deg: null,
              elevation_deg: null,
              fov_deg: null,
              accepted: false,
              reason,
            },
            actor,
          )
        if (sensor !== 'eo-1')
          return refuse(
            sensor === 'radar-1' || sensor === 'rf-1'
              ? `sensor ${sensor} cannot be cued`
              : `no sensor '${sensor}'`,
          )
        if (track.status === 'tentative') return refuse('the track is still tentative')
        const polar = polarFrom(EO.position, this.trackPosition(track, t))
        const narrow = payload.narrow !== false
        this.pointing.cuedTrack = track.id
        this.pointing.cuedUntil = t + CUE_HOLD_S
        this.emit('action.sensor_cue', payload, actor)
        this.emit(
          'sensor.cue',
          {
            sensor,
            track: track.id,
            bearing_deg: round(polar.bearingDeg, 3),
            elevation_deg: round(polar.elevationDeg, 3),
            fov_deg: narrow ? EO_NARROW_FOV : EO_HOME.fov,
            accepted: true,
            reason: null,
          },
          actor,
        )
        return
      }
      default:
        return
    }
  }
}

// ---------------------------------------------------------------------- the transport

export interface ScriptedOptions {
  /** Wall-clock speed-up: 1 plays in real time, 4 plays the minute in fifteen seconds. */
  speed?: number
  /** Simulated server round trip for ping, in ms. */
  latencyMs?: number
  /** Camera type, terrain, weather and hour. */
  variant?: MockVariant
}

export class ScriptedTransport implements Transport {
  readonly marker = MOCK_MARKER
  private handlers: TransportHandlers | null = null
  private world: MockWorld
  private readonly welcome: Welcome
  private timer: ReturnType<typeof setInterval> | null = null
  private seq = 0
  private closed = false
  private readonly speed: number
  private readonly latencyMs: number

  constructor(options: ScriptedOptions = {}) {
    this.speed = Math.max(0.1, options.speed ?? 1)
    this.latencyMs = options.latencyMs ?? 19
    this.world = new MockWorld(options.variant)
    this.welcome = mockWelcome(options.variant)
  }

  open(handlers: TransportHandlers): void {
    this.handlers = handlers
    this.closed = false
    handlers.onConnection({ state: 'connecting', closeCode: null, attempt: 0 })
    setTimeout(() => {
      if (this.closed) return
      handlers.onConnection({ state: 'open', closeCode: null, attempt: 0 })
      handlers.onLatency(this.latencyMs)
      this.send(this.welcome)
      this.send(this.world.snapshot())
    }, 40)
  }

  close(): void {
    this.closed = true
    this.stop()
    this.handlers?.onConnection({ state: 'closed', closeCode: 1000, attempt: 0 })
  }

  start(): void {
    if (this.world.status !== 'lobby' || this.closed) return
    const frame = this.world.start()
    this.send({ t: 'status', status: 'running', tick: frame.tick })
    this.send(frame)
    this.timer = setInterval(() => this.tick(), 1000 / TICK_HZ / this.speed)
  }

  end(): void {
    this.finish()
  }

  leave(): void {
    this.stop()
  }

  act(action: ClientAction, payload: Record<string, unknown> = {}): number | null {
    if (this.closed) return null
    const seq = ++this.seq
    const message: Extract<LiveClientMessage, { t: 'act' }> = { t: 'act', seq, action, payload }
    const ack = this.world.receive(message)
    // Like a socket, the answer never arrives in the same call.
    queueMicrotask(() => this.send(ack))
    return seq
  }

  private tick(): void {
    this.send(this.world.step())
    if (this.world.finished()) this.finish()
  }

  private finish(): void {
    if (this.world.status === 'ended' || this.world.status === 'lobby') return
    this.stop()
    const { eventCount } = this.world.end()
    this.send(this.world.snapshot())
    this.send({
      t: 'ended',
      status: 'ended',
      summary: {
        ticks: this.world.tick,
        duration_s: round(this.world.timeS, 2),
        event_count: eventCount,
        head: 'c41f09a7d3e85b62f01a9c7e3d54b8a60e2f719cd8350a46b7e91f2c05d38a14',
        final_state_hash: '7be2d05a91c4f836e0b1a7d92c5f4803ad61e97b2c08f5d34a1e6b90c7d2f853',
        verified: true,
      },
    })
    this.handlers?.onConnection({ state: 'closed', closeCode: 1000, attempt: 0 })
  }

  private stop(): void {
    if (this.timer !== null) clearInterval(this.timer)
    this.timer = null
  }

  private send(message: LiveServerMessage): void {
    if (!this.closed) this.handlers?.onMessage(message)
  }
}
