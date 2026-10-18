/**
 * The benchmark scene and the arithmetic of the benchmark gate (docs/04-engine.md): a rural
 * terrain pack, 40-odd buildings, a placeholder swarm of 24 drones and 30 birds, the thermal pass
 * on, measured at 1920 x 1080. Pure: no DOM and no WebGL, so the plan and the pass or fail logic
 * are tested with synthetic frame times.
 *
 * The swarm and birds are placeholders drawn as EO reports (wave 8 brings the real behaviours).
 * Nothing here claims a result: the numbers come from running the harness on a machine.
 */
import { FrameStats, type Tier } from '../live/quality'
import type { EoMode } from '../live/views/eoMode'
import type { HeldReport } from '../live/views/eoHold'

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

/** Where the benchmark camera looks at time t: a slow pan over the whole pack. */
export function cameraBearing(timeS: number): number {
  return (timeS * 6) % 360
}

/**
 * The placeholder swarm and birds, as EO reports around the camera bearing. Positions depend only
 * on `timeS`, so every run draws the same scene. Sizes are a few tenths of a degree, like a real
 * swarm at a few hundred metres.
 */
export function benchReports(timeS: number, nowMs: number): HeldReport[] {
  const reports: HeldReport[] = []
  const bearing = cameraBearing(timeS)
  for (let i = 0; i < SWARM; i++) {
    const row = i % 6
    const col = Math.floor(i / 6)
    const sway = Math.sin(timeS * 0.9 + i * 0.7)
    reports.push({
      key: 1 + i,
      sensorId: 'bench',
      azimuthDeg: bearing + (col - 1.5) * 2.4 + 0.5 * sway,
      elevationDeg: 4 + row * 1.1 + 0.4 * Math.cos(timeS * 0.8 + i),
      sizeDeg: 0.55,
      apparentPx: 12,
      shape: i % 8 === 7 ? 'fixed-wing-small' : 'rotary-small',
      seenAt: nowMs,
    })
  }
  for (let i = 0; i < BIRDS; i++) {
    reports.push({
      key: 100 + i,
      sensorId: 'bench',
      azimuthDeg: bearing - 16 + (i % 10) * 3.2 + 1.2 * Math.sin(timeS * 0.5 + i),
      elevationDeg: 9 + Math.floor(i / 10) * 2.2 + 0.8 * Math.sin(timeS * 1.7 + i * 1.3),
      sizeDeg: 0.4,
      apparentPx: 9,
      shape: 'bird',
      seenAt: nowMs,
    })
  }
  return reports
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
