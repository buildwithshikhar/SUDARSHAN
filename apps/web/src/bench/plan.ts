/**
 * The benchmark scene and the arithmetic of the benchmark gate (docs/04-engine.md): a rural
 * terrain pack, 40-odd buildings, the recorded run of a real 24-drone swarm and 30-bird flock
 * (wave 8 behaviours), the thermal pass on, measured at 1920 x 1080. Pure: no DOM and no WebGL, so the plan and the pass or fail logic
 * are tested with synthetic frame times.
 *
 * Nothing here claims a result: the numbers come from running the harness on a machine.
 */
import { FrameStats, type Tier } from '../live/quality'
import type { EoMode } from '../live/views/eoMode'
import type { EoShape, HeldReport } from '../live/views/eoHold'

export const BENCH_FORMAT = 'bench-result.v1'
export const BENCH_PACK = { kind: 'pack', id: 'heron-ridge', version: '1.0.0' } as const
export const CANVAS = { width: 1920, height: 1080 } as const
export const SWARM = 24
export const BIRDS = 30
/** Time of day of the benchmark scene, in hours: full daylight, so day and thermal both read. */
export const BENCH_HOUR = 14

/** The gate: median and 5th-percentile fps at 1080p, or an auto tier that holds 30 fps. */
export const GATE = {
  medianFps: 45,
  fps5th: 30,
  autoMedianFps: 30,
  autoFps5th: 30,
} as const

export type PhaseId = 'high' | 'medium' | 'low' | 'auto' | 'high-day'

export interface PhaseSpec {
  id: PhaseId
  /** The tier forced for the phase, or null for the automatic controller. */
  tier: Tier | null
  mode: EoMode
  /** Time before measurement starts: shader compile, texture upload and the auto probe. */
  warmupMs: number
  measureMs: number
}

export const PHASES: readonly PhaseSpec[] = [
  { id: 'high', tier: 'high', mode: 'thermal-white-hot', warmupMs: 3000, measureMs: 15000 },
  { id: 'medium', tier: 'medium', mode: 'thermal-white-hot', warmupMs: 3000, measureMs: 15000 },
  { id: 'low', tier: 'low', mode: 'thermal-white-hot', warmupMs: 3000, measureMs: 15000 },
  { id: 'auto', tier: null, mode: 'thermal-white-hot', warmupMs: 6000, measureMs: 20000 },
  { id: 'high-day', tier: 'high', mode: 'day', warmupMs: 3000, measureMs: 15000 },
]

/** The same phases at a tenth of the length, for the smoke test. Not a measurement. */
export function quickPhases(phases: readonly PhaseSpec[] = PHASES): PhaseSpec[] {
  return phases.map((p) => ({
    ...p,
    warmupMs: Math.max(300, p.warmupMs / 10),
    measureMs: Math.max(1000, p.measureMs / 10),
  }))
}

export interface PhaseResult {
  id: PhaseId
  mode: EoMode
  /** The tier in force when the phase ended (the auto phase may have changed it). */
  tier: Tier
  frames: number
  durationMs: number
  fpsMedian: number
  fps5th: number
  fpsMean: number
  p50Ms: number
  p95Ms: number
  p99Ms: number
  maxMs: number
  /** Frames that took longer than SLOW_FRAME_MS. They are counted in every figure above. */
  slowFrames: number
  /** Intervals left out because the tab was hidden or the page stalled (see BenchHooks). */
  interruptions: number
}

/** A frame slower than this is reported as slow; it is still a frame and still measured. */
export const SLOW_FRAME_MS = 1000
/** An interval longer than this with no known cause is treated as an interruption, not a frame. */
export const MAX_FRAME_MS = 60_000

export function summarise(
  spec: Pick<PhaseSpec, 'id' | 'mode'>,
  tier: Tier,
  stats: FrameStats,
  durationMs: number,
  counts: { slowFrames?: number; interruptions?: number } = {},
): PhaseResult {
  const s = stats.snapshot()
  const r = (x: number, digits = 2) => Number(x.toFixed(digits))
  return {
    id: spec.id,
    mode: spec.mode,
    tier,
    frames: s.count,
    durationMs: Math.round(durationMs),
    fpsMedian: r(s.p50Ms > 0 ? 1000 / s.p50Ms : 0),
    fps5th: r(s.fps5th),
    fpsMean: r(s.fpsMean),
    p50Ms: r(s.p50Ms),
    p95Ms: r(s.p95Ms),
    p99Ms: r(s.p99Ms),
    maxMs: r(s.maxMs),
    slowFrames: counts.slowFrames ?? 0,
    interruptions: counts.interruptions ?? 0,
  }
}

export interface GateOutcome {
  /** Fixed high tier, thermal on: median >= 45 fps and 5th percentile >= 30 fps. */
  fixedHigh: boolean | null
  /** Auto tier: median >= 30 fps and 5th percentile >= 30 fps. */
  autoHolds: boolean | null
  /** The gate passes if either does. Null when a needed phase was not measured. */
  pass: boolean | null
}

export function evaluateGate(phases: readonly PhaseResult[]): GateOutcome {
  const high = phases.find((p) => p.id === 'high')
  const auto = phases.find((p) => p.id === 'auto')
  const fixedHigh = high ? high.fpsMedian >= GATE.medianFps && high.fps5th >= GATE.fps5th : null
  const autoHolds = auto
    ? auto.fpsMedian >= GATE.autoMedianFps && auto.fps5th >= GATE.autoFps5th
    : null
  const pass = fixedHigh === null || autoHolds === null ? null : fixedHigh || autoHolds
  return { fixedHigh, autoHolds, pass }
}

// ---------------------------------------------------------------------- the scene

export const SCENE_URL = '/scenes/bench-breadth.v1.json'
export const SCENE_FORMAT = 'bench-scene.v1'

/**
 * The recorded run of the real swarm and flock behaviours (`python -m sim.breadth`, wave 8):
 * positions of every contact sampled at `hz`, in decimetres east, north and up of the pack datum.
 * The harness replays it; nothing here moves a contact on its own.
 */
export interface BenchScene {
  format: typeof SCENE_FORMAT
  pack: string
  hz: number
  duration_s: number
  unit: 'dm'
  members: { id: string; shape: EoShape }[]
  /** One row per sample; three numbers (x, y, z) per member, in member order. */
  frames: number[][]
}

/** Real size of each shape in metres, from the threat catalogue's EO figures. */
const SIZE_M: Record<EoShape, number> = {
  'rotary-small': 0.39,
  'fpv-small': 0.3,
  'fixed-wing-small': 1.2,
  'fixed-wing-medium': 3,
  'fixed-wing-large': 6,
  bird: 0.79,
  kite: 1.2,
  balloon: 1.5,
  point: 0.5,
}

/** The picture is 40 degrees wide at 1920 pixels (see Bench.tsx). */
const FOV_DEG = 40

export function parseBenchScene(raw: unknown): BenchScene {
  const scene = raw as Partial<BenchScene> | null
  if (
    !scene ||
    scene.format !== SCENE_FORMAT ||
    !Array.isArray(scene.members) ||
    !Array.isArray(scene.frames) ||
    scene.frames.length < 2 ||
    typeof scene.hz !== 'number' ||
    scene.hz <= 0
  ) {
    throw new Error('the benchmark scene file is not a bench-scene.v1 file')
  }
  const width = 3 * scene.members.length
  if (scene.frames.some((row) => !Array.isArray(row) || row.length !== width)) {
    throw new Error('the benchmark scene file has a row of the wrong length')
  }
  const swarm = scene.members.filter((m) => m.id.startsWith('swarm-')).length
  const birds = scene.members.filter((m) => m.shape === 'bird').length
  if (swarm !== SWARM || birds !== BIRDS) {
    throw new Error(`the benchmark scene must hold ${SWARM} drones and ${BIRDS} birds`)
  }
  return scene as BenchScene
}

export async function loadBenchScene(url: string = SCENE_URL): Promise<BenchScene> {
  const response = await fetch(url)
  if (!response.ok) throw new Error(`could not load the benchmark scene (${response.status})`)
  return parseBenchScene(await response.json())
}

export interface Eye {
  x: number
  y: number
  z: number
}

/** Positions in metres at time `timeS`, interpolated between samples; the run loops. */
export function positionsAt(scene: BenchScene, timeS: number): [number, number, number][] {
  const span = scene.frames.length - 1
  const f = (((timeS * scene.hz) % span) + span) % span
  const i = Math.floor(f)
  const k = f - i
  const a = scene.frames[i] ?? []
  const b = scene.frames[i + 1] ?? a
  const at = (row: number[], j: number) => row[j] ?? 0
  return scene.members.map((_, m) => {
    const j = 3 * m
    return [0, 1, 2].map((c) => (at(a, j + c) + (at(b, j + c) - at(a, j + c)) * k) / 10) as [
      number,
      number,
      number,
    ]
  })
}

function bearingTo(eye: Eye, x: number, y: number): number {
  const deg = (Math.atan2(x - eye.x, y - eye.y) * 180) / Math.PI
  return (deg + 360) % 360
}

/** Where the benchmark camera looks at time t: at the swarm and the flock, with a slow sway over the terrain. */
export function cameraBearing(scene: BenchScene, timeS: number, eye: Eye): number {
  const pos = positionsAt(scene, timeS)
  let x = 0
  let y = 0
  let n = 0
  scene.members.forEach((m, i) => {
    const p = pos[i]
    if (!(m.id.startsWith('swarm-') || m.shape === 'bird') || !p) return
    x += p[0]
    y += p[1]
    n++
  })
  return (bearingTo(eye, x / n, y / n) + 5 * Math.sin(timeS * 0.25) + 360) % 360
}

/**
 * Every contact of the recorded run as an EO report from the camera position: bearing, elevation
 * and the angular size its real size subtends at its range. Same time, same scene.
 */
export function benchReports(
  scene: BenchScene,
  timeS: number,
  nowMs: number,
  eye: Eye,
): HeldReport[] {
  const pos = positionsAt(scene, timeS)
  return scene.members.map((m, i) => {
    const [x, y, z] = pos[i] ?? [0, 0, 0]
    const dx = x - eye.x
    const dy = y - eye.y
    const dz = z - eye.z
    const ground = Math.hypot(dx, dy)
    const range = Math.max(Math.hypot(ground, dz), 1)
    const sizeDeg = ((SIZE_M[m.shape] ?? SIZE_M.point) / range) * (180 / Math.PI)
    return {
      key: i + 1,
      sensorId: 'bench',
      azimuthDeg: bearingTo(eye, x, y),
      elevationDeg: (Math.atan2(dz, ground) * 180) / Math.PI,
      sizeDeg,
      apparentPx: (sizeDeg * CANVAS.width) / FOV_DEG,
      shape: m.shape,
      seenAt: nowMs,
    }
  })
}

// ---------------------------------------------------------------------- the runner

/** What the runner needs from the 3D scene and from the automatic tier controller. */
export interface BenchHooks {
  /** Force a tier and a mode for the next phase, or start the automatic controller (tier null). */
  begin(spec: PhaseSpec): void
  /** Draw one frame at `timeS` into the benchmark scene. */
  draw(nowMs: number, timeS: number): void
  /** Feed the frame to the automatic controller; returns the tier it now wants, if it changed. */
  autoFrame(nowMs: number): Tier | null
  /** The tier in force. */
  tier(): Tier
  /**
   * True once if the page was hidden or otherwise paused since the last call (and clears itself).
   * The interval across such a pause is left out of the figures; every other interval counts, so a
   * machine that renders one frame every few seconds records those frames instead of none.
   */
  interrupted?(): boolean
}

export type RunnerState =
  | { status: 'running'; phase: PhaseId; index: number; total: number; elapsedMs: number }
  | { status: 'done'; phases: PhaseResult[] }

/**
 * Drives the phases from the page's animation frames: `step(now)` once per frame. A phase warms
 * up, then records frame durations for its measuring time. No timers, so a test feeds `step`
 * synthetic timestamps.
 */
export class BenchRunner {
  private index = 0
  private phaseStart = Number.NaN
  private last = Number.NaN
  private stats = new FrameStats()
  private readonly results: PhaseResult[] = []
  private begun = false
  private slow = 0
  private interruptions = 0

  constructor(
    private readonly hooks: BenchHooks,
    private readonly phases: readonly PhaseSpec[] = PHASES,
  ) {}

  step(nowMs: number): RunnerState {
    const spec = this.phases[this.index]
    if (!spec) return { status: 'done', phases: this.results }
    if (!this.begun) {
      this.begun = true
      this.hooks.begin(spec)
      this.phaseStart = nowMs
      this.last = Number.NaN
      this.stats = new FrameStats()
      this.slow = 0
      this.interruptions = 0
    }
    const elapsed = nowMs - this.phaseStart
    this.hooks.draw(nowMs, elapsed / 1000)
    if (spec.tier === null) this.hooks.autoFrame(nowMs)
    const dt = nowMs - this.last
    this.last = nowMs
    const paused = this.hooks.interrupted?.() ?? false
    if (elapsed >= spec.warmupMs && Number.isFinite(dt) && dt > 0) {
      if (paused || dt > MAX_FRAME_MS) {
        this.interruptions++
      } else {
        if (dt > SLOW_FRAME_MS) this.slow++
        this.stats.push(dt)
      }
    }
    if (elapsed >= spec.warmupMs + spec.measureMs) {
      this.results.push(
        summarise(spec, this.hooks.tier(), this.stats, elapsed - spec.warmupMs, {
          slowFrames: this.slow,
          interruptions: this.interruptions,
        }),
      )
      this.index++
      this.begun = false
      if (this.index >= this.phases.length) return { status: 'done', phases: this.results }
    }
    return {
      status: 'running',
      phase: this.phases[Math.min(this.index, this.phases.length - 1)]?.id ?? spec.id,
      index: this.index,
      total: this.phases.length,
      elapsedMs: elapsed,
    }
  }
}
