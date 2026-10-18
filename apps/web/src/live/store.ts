/**
 * Client state of one live session: a plain reducer behind a tiny store. Server messages go in,
 * a snapshot comes out; the canvas views read it directly each animation frame, React
 * components subscribe through `useLive` (live/context.tsx).
 */
import { clamp, extrapolate, lerp, lerpAngleDeg } from './geometry'
import type {
  Ack,
  ClientAction,
  EndSummary,
  Fault,
  Frame,
  LiveServerMessage,
  SensorStatus,
  SessionStatus,
  Report,
  TraineeEvent,
  TrackView,
  Vec3,
  Welcome,
} from './protocol'
import type { ConnectionInfo } from './transport'

export const EVENT_CAP = 500
export const TRAIL_MAX = 30
export const TRAIL_STEP_S = 1
export const RF_KEEP_S = 8
/** Pending actions with no resolving event after this long are dropped from the list. */
export const PENDING_TTL_MS = 12_000
/** The longest the clock and tracks are carried forward from the last frame. */
export const MAX_EXTRAPOLATE_S = 0.25

export interface TrailPoint {
  x: number
  y: number
  timeS: number
}

export interface PendingAction {
  seq: number
  action: ClientAction
  payload: Record<string, unknown>
  sentAt: number
  /** sent: on the wire; queued: server accepted it for the next tick; refused: ack said no. */
  state: 'sent' | 'queued' | 'refused'
  message?: string
}

/** The rules verdict the server logged for the operator's last response. */
export interface Verdict {
  seq: number
  action: string
  track: string
  effectorClass: string | null
  permitted: boolean
  code: string
  ruleId: string | null
  ruleTitle: { en: string; hi: string } | null
  packId: string
  packVersion: string
  authority: string | null
  detail: Record<string, unknown>
  context: Record<string, unknown>
}

export interface LiveState {
  connection: ConnectionInfo
  latencyMs: number | null
  welcome: Welcome | null
  status: SessionStatus
  frame: Frame | null
  prevFrame: Frame | null
  /** performance.now() when `frame` / `prevFrame` arrived. */
  frameAt: number
  prevFrameAt: number
  trails: Record<string, TrailPoint[]>
  /** Each sensor's field of view the first time it was seen uncued: the zoom reference. */
  homeFov: Record<string, number>
  /** Recent RF reports (the last few seconds), for the track detail's RF link. */
  rfReports: (Report & { timeS: number })[]
  events: TraineeEvent[]
  lastEventSeq: number
  selected: string | null
  /** First track of a merge in progress. */
  mergeFrom: string | null
  /** The operator's own assessment (identity) and classification per track, from events. */
  assessments: Record<string, string>
  classifications: Record<string, string>
  pending: PendingAction[]
  verdict: Verdict | null
  ended: EndSummary | null
  fault: Fault | null
  /** Frames dropped for being older than the current one. */
  staleFrames: number
}

export const initialState = (): LiveState => ({
  connection: { state: 'connecting', closeCode: null, attempt: 0 },
  latencyMs: null,
  welcome: null,
  status: 'lobby',
  frame: null,
  prevFrame: null,
  frameAt: 0,
  prevFrameAt: 0,
  trails: {},
  homeFov: {},
  rfReports: [],
  events: [],
  lastEventSeq: 0,
  selected: null,
  mergeFrom: null,
  assessments: {},
  classifications: {},
  pending: [],
  verdict: null,
  ended: null,
  fault: null,
  staleFrames: 0,
})

export type LiveAction =
  | { type: 'connection'; info: ConnectionInfo }
  | { type: 'latency'; ms: number }
  | { type: 'message'; message: LiveServerMessage; at: number }
  | { type: 'select'; id: string | null }
  | { type: 'cycle'; direction: 1 | -1 }
  | { type: 'merge-from'; id: string | null }
  | {
      type: 'sent'
      seq: number
      action: ClientAction
      payload: Record<string, unknown>
      at: number
    }
  | { type: 'send-failed'; action: ClientAction; payload: Record<string, unknown>; at: number }
  | { type: 'dismiss-verdict' }

/** The actions whose verdict the decision panel keeps on screen. */
export const RESPONSES: ReadonlySet<string> = new Set(['engage', 'hold', 'report'])

const str = (value: unknown): string | null => (typeof value === 'string' ? value : null)

/** Which events answer which action (by the track the action named). */
const ANSWERS: Record<ClientAction, readonly string[]> = {
  designate: ['action.designate'],
  classify: ['action.classify'],
  assess: ['action.assess'],
  engage: ['roe.verdict'],
  hold: ['roe.verdict'],
  report: ['roe.verdict'],
  'track-relabel': ['track.relabel'],
  'track-merge': ['track.merge'],
  'track-split': ['track.split'],
  'track-drop': ['track.drop'],
  'sensor-cue': ['sensor.cue'],
}

function resolves(pending: PendingAction, event: TraineeEvent): boolean {
  if (event.type === 'action.rejected') return event.payload.action === pending.action
  if (!ANSWERS[pending.action].includes(event.type)) return false
  const track = str(pending.payload.track)
  if (pending.action === 'track-merge') return true
  if (track === null) return true
  const eventTrack =
    str(event.payload.track) ?? str(event.payload.source) ?? str(event.payload.survivor)
  return eventTrack === null || eventTrack === track
}

function toVerdict(event: TraineeEvent): Verdict | null {
  const p = event.payload
  const action = str(p.action)
  const track = str(p.track)
  const code = str(p.code)
  if (!action || !track || !code || typeof p.permitted !== 'boolean') return null
  const title = p.rule_title as { en?: unknown; hi?: unknown } | null | undefined
  return {
    seq: event.seq,
    action,
    track,
    effectorClass: str(p.effector_class),
    permitted: p.permitted,
    code,
    ruleId: str(p.rule_id),
    ruleTitle:
      title && typeof title.en === 'string' && typeof title.hi === 'string'
        ? { en: title.en, hi: title.hi }
        : null,
    packId: str(p.pack_id) ?? '',
    packVersion: str(p.pack_version) ?? '',
    authority: str(p.authority),
    detail: (p.detail as Record<string, unknown> | null) ?? {},
    context: (p.context as Record<string, unknown> | null) ?? {},
  }
}

function applyEvents(state: LiveState, incoming: TraineeEvent[], at: number): LiveState {
  const fresh = incoming.filter((e) => e.seq > state.lastEventSeq)
  if (fresh.length === 0) return state
  let { assessments, classifications, verdict, selected, mergeFrom } = state
  let pending = state.pending
  for (const event of fresh) {
    const p = event.payload
    switch (event.type) {
      case 'action.assess': {
        const track = str(p.track)
        const identity = str(p.identity)
        if (track && identity) assessments = { ...assessments, [track]: identity }
        break
      }
      case 'action.classify': {
        const track = str(p.track)
        const classId = str(p.class_id)
        if (track && classId) classifications = { ...classifications, [track]: classId }
        break
      }
      case 'track.merge': {
        const survivor = str(p.survivor)
        const absorbed = str(p.absorbed)
        if (survivor && absorbed) {
          const carry = <T>(map: Record<string, T>): Record<string, T> => {
            const { [absorbed]: moved, ...rest } = map
            return moved !== undefined && rest[survivor] === undefined
              ? { ...rest, [survivor]: moved }
              : rest
          }
          assessments = carry(assessments)
          classifications = carry(classifications)
          if (selected === absorbed) selected = survivor
          if (mergeFrom === absorbed) mergeFrom = null
        }
        break
      }
      case 'track.split': {
        const source = str(p.source)
        const created = str(p.new)
        if (source && created) {
          if (assessments[source]) assessments = { ...assessments, [created]: assessments[source] }
          if (classifications[source])
            classifications = { ...classifications, [created]: classifications[source] }
        }
        break
      }
      case 'track.drop': {
        const track = str(p.track)
        if (track) {
          const { [track]: _a, ...a } = assessments
          const { [track]: _c, ...c } = classifications
          void _a
          void _c
          assessments = a
          classifications = c
        }
        break
      }
      case 'roe.verdict': {
        // Classify and assess are checked too, but only a response verdict is held on screen.
        const next = toVerdict(event)
        if (next && RESPONSES.has(next.action)) verdict = next
        break
      }
      default:
        break
    }
    pending = pending.filter((entry) => !resolves(entry, event))
  }
  pending = pending.filter((entry) => at - entry.sentAt < PENDING_TTL_MS)
  const events = [...state.events, ...fresh]
  return {
    ...state,
    events: events.length > EVENT_CAP ? events.slice(events.length - EVENT_CAP) : events,
    lastEventSeq: fresh[fresh.length - 1]?.seq ?? state.lastEventSeq,
    assessments,
    classifications,
    verdict,
    selected,
    mergeFrom,
    pending,
  }
}

function applyFrame(state: LiveState, frame: Frame, at: number): LiveState {
  if (state.frame && frame.tick < state.frame.tick) {
    return { ...state, staleFrames: state.staleFrames + 1 }
  }
  const sameTick = state.frame !== null && frame.tick === state.frame.tick
  const trails: Record<string, TrailPoint[]> = {}
  for (const track of frame.tracks) {
    const old = state.trails[track.id] ?? []
    const last = old[old.length - 1]
    if (!last || frame.time_s - last.timeS >= TRAIL_STEP_S) {
      const next = [...old, { x: track.position.x, y: track.position.y, timeS: frame.time_s }]
      trails[track.id] = next.length > TRAIL_MAX ? next.slice(next.length - TRAIL_MAX) : next
    } else {
      trails[track.id] = old
    }
  }
  let homeFov = state.homeFov
  for (const sensor of frame.sensors) {
    if (!sensor.cued && sensor.fov_deg !== null && homeFov[sensor.id] === undefined)
      homeFov = { ...homeFov, [sensor.id]: sensor.fov_deg }
  }
  const freshRf = frame.reports
    .filter((r) => r.modality === 'rf')
    .map((r) => ({ ...r, timeS: frame.time_s }))
  const keptRf = state.rfReports.filter((r) => frame.time_s - r.timeS <= RF_KEEP_S)
  const rfReports =
    freshRf.length === 0 && keptRf.length === state.rfReports.length
      ? state.rfReports
      : [...keptRf, ...freshRf].slice(-24)
  const ids = new Set(frame.tracks.map((t) => t.id))
  let selected = state.selected
  if (selected && !ids.has(selected)) selected = null
  const mergeFrom = state.mergeFrom && ids.has(state.mergeFrom) ? state.mergeFrom : null
  const next: LiveState = {
    ...state,
    status: frame.status,
    prevFrame: sameTick ? state.prevFrame : state.frame,
    prevFrameAt: sameTick ? state.prevFrameAt : state.frameAt,
    frame,
    frameAt: at,
    trails,
    homeFov,
    rfReports,
    selected,
    mergeFrom,
  }
  return applyEvents(next, frame.events, at)
}

function applyAck(state: LiveState, ack: Ack): LiveState {
  const pending = state.pending.map((entry) =>
    entry.seq !== ack.seq
      ? entry
      : ack.ok
        ? { ...entry, state: 'queued' as const }
        : { ...entry, state: 'refused' as const, message: ack.error?.message ?? ack.error?.code },
  )
  return { ...state, pending }
}

export function reduce(state: LiveState, action: LiveAction): LiveState {
  switch (action.type) {
    case 'connection':
      return { ...state, connection: action.info }
    case 'latency':
      return { ...state, latencyMs: action.ms }
    case 'select':
      return { ...state, selected: action.id }
    case 'merge-from':
      return { ...state, mergeFrom: action.id }
    case 'cycle': {
      const ids = (state.frame?.tracks ?? []).map((t) => t.id).sort()
      if (ids.length === 0) return state
      const at = state.selected ? ids.indexOf(state.selected) : -1
      const next =
        at === -1
          ? action.direction === 1
            ? 0
            : ids.length - 1
          : (at + action.direction + ids.length) % ids.length
      return { ...state, selected: ids[next] ?? null }
    }
    case 'dismiss-verdict':
      return { ...state, verdict: null }
    case 'sent':
      return {
        ...state,
        pending: [
          ...state.pending.slice(-19),
          {
            seq: action.seq,
            action: action.action,
            payload: action.payload,
            sentAt: action.at,
            state: 'sent',
          },
        ],
      }
    case 'send-failed':
      return {
        ...state,
        pending: [
          ...state.pending.slice(-19),
          {
            seq: -1,
            action: action.action,
            payload: action.payload,
            sentAt: action.at,
            state: 'refused',
            message: 'not-connected',
          },
        ],
      }
    case 'message': {
      const m = action.message
      switch (m.t) {
        case 'welcome':
          return { ...state, welcome: m, status: m.status }
        case 'frame':
          return applyFrame(state, m, action.at)
        case 'status':
          return { ...state, status: m.status }
        case 'ack':
          return applyAck(state, m)
        case 'pong':
          return state
        case 'ended':
          return { ...state, ended: m.summary, status: m.status }
        case 'error':
          return { ...state, fault: m }
      }
    }
  }
}

type Listener = () => void

export class LiveStore {
  private state: LiveState = initialState()
  private readonly listeners = new Set<Listener>()

  getState = (): LiveState => this.state

  subscribe = (listener: Listener): (() => void) => {
    this.listeners.add(listener)
    return () => {
      this.listeners.delete(listener)
    }
  }

  dispatch(action: LiveAction): void {
    const next = reduce(this.state, action)
    if (next === this.state) return
    this.state = next
    this.listeners.forEach((listener) => listener())
  }
}

// ---------------------------------------------------------------------- derived values

/** Scenario time now: the last frame's time carried forward while running, capped. */
export function simTimeNow(state: LiveState, nowMs: number): number {
  if (!state.frame) return 0
  if (state.status !== 'running') return state.frame.time_s
  return state.frame.time_s + clamp((nowMs - state.frameAt) / 1000, 0, MAX_EXTRAPOLATE_S)
}

export interface TrackPose extends TrackView {
  /** Position carried along the velocity to `nowMs`. */
  at: Vec3
}

/** Every track dead-reckoned from the last frame to `nowMs` (60 fps rendering). */
export function trackPoses(state: LiveState, nowMs: number): TrackPose[] {
  if (!state.frame) return []
  const dt = state.status === 'running' ? (nowMs - state.frameAt) / 1000 : 0
  return state.frame.tracks.map((track) => ({
    ...track,
    at: extrapolate(track.position, track.velocity, dt, MAX_EXTRAPOLATE_S),
  }))
}

export interface SensorPose {
  id: string
  bearingDeg: number
  elevationDeg: number
  fovDeg: number | null
}

/**
 * Sensor pointing blended between the last two frames: the pose shown at `nowMs` runs one frame
 * behind, so a slew is smooth at 60 fps even though frames arrive at 20 Hz.
 */
export function sensorPose(state: LiveState, sensorId: string, nowMs: number): SensorPose | null {
  const latest = state.frame?.sensors.find((s) => s.id === sensorId)
  if (!latest) return null
  const previous = state.prevFrame?.sensors.find((s) => s.id === sensorId)
  if (!previous || state.status !== 'running') return poseOf(latest)
  const span = Math.max(1, state.frameAt - state.prevFrameAt)
  const k = clamp((nowMs - state.frameAt) / span, 0, 1)
  return interpolateSensor(previous, latest, k)
}

const poseOf = (s: SensorStatus): SensorPose => ({
  id: s.id,
  bearingDeg: s.bearing_deg,
  elevationDeg: s.elevation_deg,
  fovDeg: s.fov_deg,
})

export function interpolateSensor(from: SensorStatus, to: SensorStatus, k: number): SensorPose {
  return {
    id: to.id,
    bearingDeg: lerpAngleDeg(from.bearing_deg, to.bearing_deg, k),
    elevationDeg: lerp(from.elevation_deg, to.elevation_deg, k),
    fovDeg:
      from.fov_deg !== null && to.fov_deg !== null ? lerp(from.fov_deg, to.fov_deg, k) : to.fov_deg,
  }
}
