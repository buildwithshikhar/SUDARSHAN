/**
 * Graphics quality tiers for the 3D views, the frame-time statistics behind them and the
 * controller that picks a tier. Pure logic: no DOM, no WebGL and no wall clock. The caller passes
 * the frame timestamp, so tests drive it with synthetic frame times.
 *
 * Target hardware is an 8 GB laptop with integrated graphics (docs/04-engine.md), so the controller starts
 * at the heaviest tier, measures for about two seconds, and settles on the highest tier the
 * machine holds. It can step down while the session runs, and step up at most once.
 */

export type Tier = 'high' | 'medium' | 'low'
export type TierChoice = 'auto' | Tier

export const TIER_ORDER: readonly Tier[] = ['low', 'medium', 'high']
export const TIER_CHOICES: readonly TierChoice[] = ['auto', 'high', 'medium', 'low']

export interface TierSettings {
  /** Upper bound on the renderer pixel ratio. */
  pixelRatioCap: number
  shadows: boolean
  /** Share of the baked trees that is drawn, 0..1. */
  treeFraction: number
  /** Rain streaks drawn at full intensity. */
  rainParticles: number
  /** Post-process render target size as a fraction of the canvas in device pixels. */
  postScale: number
  /** Applied when the renderer is created; a running context cannot change it. */
  antialias: boolean
}

export const TIERS: Readonly<Record<Tier, TierSettings>> = {
  high: {
    pixelRatioCap: 1.5,
    shadows: true,
    treeFraction: 1,
    rainParticles: 2400,
    postScale: 1,
    antialias: true,
  },
  medium: {
    pixelRatioCap: 1.25,
    shadows: false,
    treeFraction: 0.6,
    rainParticles: 1200,
    postScale: 0.75,
    antialias: true,
  },
  low: {
    pixelRatioCap: 1,
    shadows: false,
    treeFraction: 0.25,
    rainParticles: 450,
    postScale: 0.5,
    antialias: false,
  },
}

export function isTier(value: unknown): value is Tier {
  return value === 'high' || value === 'medium' || value === 'low'
}

export function isTierChoice(value: unknown): value is TierChoice {
  return value === 'auto' || isTier(value)
}

export function stepDown(tier: Tier): Tier {
  return TIER_ORDER[Math.max(0, TIER_ORDER.indexOf(tier) - 1)] ?? 'low'
}

export function stepUp(tier: Tier): Tier {
  return TIER_ORDER[Math.min(TIER_ORDER.length - 1, TIER_ORDER.indexOf(tier) + 1)] ?? 'high'
}

// ---------------------------------------------------------------------- statistics

export interface FrameSnapshot {
  count: number
  meanMs: number
  p50Ms: number
  p95Ms: number
  p99Ms: number
  maxMs: number
  /** Frame rate at the mean frame time. */
  fpsMean: number
  /** Frame rate of the slow end: 1000 / (95th percentile frame time). The "5th percentile fps". */
  fps5th: number
}

/** Nearest-rank percentile of an ascending array (p in 0..100). */
export function percentileOf(sorted: ArrayLike<number>, p: number): number {
  const length = sorted.length
  if (length === 0) return 0
  const rank = Math.ceil((Math.min(100, Math.max(0, p)) / 100) * length)
  return sorted[Math.min(length - 1, Math.max(0, rank - 1))] ?? 0
}

/**
 * Per-frame durations in a ring buffer, with percentiles on demand. Recording a frame allocates
 * nothing; a percentile copies and sorts the buffer, so ask for it about once a second, not per frame.
 */
export class FrameStats {
  private readonly buffer: Float32Array
  private readonly scratch: Float32Array
  private head = 0
  private filled = 0
  private total = 0

  constructor(readonly capacity = 8192) {
    this.buffer = new Float32Array(capacity)
    this.scratch = new Float32Array(capacity)
  }

  push(durationMs: number): void {
    if (!Number.isFinite(durationMs) || durationMs < 0) return
    this.buffer[this.head] = durationMs
    this.head = (this.head + 1) % this.capacity
    this.filled = Math.min(this.capacity, this.filled + 1)
    this.total++
  }

  reset(): void {
    this.head = 0
    this.filled = 0
    this.total = 0
  }

  /** Frames pushed since the last reset, including any that have left the ring. */
  get count(): number {
    return this.total
  }

  private sorted(): Float32Array {
    const view = this.scratch.subarray(0, this.filled)
    view.set(this.buffer.subarray(0, this.filled))
    return view.sort()
  }

  /** Frame time at percentile p (0..100), in ms, over the frames still in the ring. */
  percentile(p: number): number {
    return this.filled === 0 ? 0 : percentileOf(this.sorted(), p)
  }

  /** Frame rate of the p-th slowest percent of frames: p = 5 gives the "5th percentile fps". */
  fpsPercentile(p: number): number {
    const ms = this.percentile(100 - p)
    return ms > 0 ? 1000 / ms : 0
  }

  snapshot(): FrameSnapshot {
    if (this.filled === 0) {
      return { count: 0, meanMs: 0, p50Ms: 0, p95Ms: 0, p99Ms: 0, maxMs: 0, fpsMean: 0, fps5th: 0 }
    }
    const sorted = this.sorted()
    let sum = 0
    for (let i = 0; i < sorted.length; i++) sum += sorted[i] ?? 0
    const meanMs = sum / sorted.length
    const p95Ms = percentileOf(sorted, 95)
    return {
      count: this.total,
      meanMs,
      p50Ms: percentileOf(sorted, 50),
      p95Ms,
      p99Ms: percentileOf(sorted, 99),
      maxMs: sorted[sorted.length - 1] ?? 0,
      fpsMean: meanMs > 0 ? 1000 / meanMs : 0,
      fps5th: p95Ms > 0 ? 1000 / p95Ms : 0,
    }
  }
}

// ---------------------------------------------------------------------- controller

export interface TierEvent {
  tier: Tier
  reason: 'probe' | 'step-down' | 'step-up'
  /** The 5th-percentile fps the decision was made on. */
  fps5th: number
  fpsMedian: number
}

export interface TierControllerOptions {
  choice?: TierChoice
  /** The tier the probe runs at: the heaviest, so the measurement is the worst case. */
  startTier?: Tier
  /** Probe length after warm-up. */
  probeMs?: number
  /** Time skipped before the probe starts (shader compile and texture upload). */
  warmupMs?: number
  /** Rolling window the runtime check looks at. */
  windowMs?: number
  /** Step down when the 5th-percentile fps over the window stays below this. */
  floorFps?: number
  /** Step up (once) when the window holds at least this for `upHoldMs`. */
  ceilingFps?: number
  upHoldMs?: number
  /** Quiet period after any change. */
  cooldownMs?: number
  /** A frame gap longer than this is a paused tab, not a slow frame. */
  gapMs?: number
}

export const DEFAULTS = {
  probeMs: 2000,
  warmupMs: 400,
  windowMs: 3000,
  floorFps: 30,
  ceilingFps: 55,
  upHoldMs: 10_000,
  cooldownMs: 5000,
  gapMs: 1000,
  /** Re-evaluate the window this often, not every frame. */
  checkEveryMs: 250,
} as const

/** The tier a probe result earns. The probe runs at the heaviest tier, so a slow result steps down. */
export function pickTier(fps5th: number): Tier {
  if (fps5th >= 50) return 'high'
  if (fps5th >= 20) return 'medium'
  return 'low'
}

const RING = 1024

interface Window {
  fps5th: number
  fpsMedian: number
  frames: number
}

export class TierController {
  private choice: TierChoice
  private current: Tier
  private mode: 'probe' | 'run' | 'fixed'
  private readonly o: Required<Omit<TierControllerOptions, 'choice'>>
  private last = Number.NaN
  private warmFrom = Number.NaN
  private probeStart = Number.NaN
  private lastChange = Number.NEGATIVE_INFINITY
  private lastCheck = Number.NEGATIVE_INFINITY
  private upSteps = 0
  private goodSince = Number.NaN
  private windowStart = Number.NEGATIVE_INFINITY
  private readonly stamps = new Float64Array(RING)
  private readonly durations = new Float32Array(RING)
  private readonly scratch = new Float32Array(RING)
  private head = 0
  private size = 0

  constructor(options: TierControllerOptions = {}) {
    this.o = {
      startTier: options.startTier ?? 'high',
      probeMs: options.probeMs ?? DEFAULTS.probeMs,
      warmupMs: options.warmupMs ?? DEFAULTS.warmupMs,
      windowMs: options.windowMs ?? DEFAULTS.windowMs,
      floorFps: options.floorFps ?? DEFAULTS.floorFps,
      ceilingFps: options.ceilingFps ?? DEFAULTS.ceilingFps,
      upHoldMs: options.upHoldMs ?? DEFAULTS.upHoldMs,
      cooldownMs: options.cooldownMs ?? DEFAULTS.cooldownMs,
      gapMs: options.gapMs ?? DEFAULTS.gapMs,
    }
    this.choice = options.choice ?? 'auto'
    this.current = isTier(this.choice) ? this.choice : this.o.startTier
    this.mode = isTier(this.choice) ? 'fixed' : 'probe'
  }

  get tier(): Tier {
    return this.current
  }

  get phase(): 'probe' | 'run' | 'fixed' {
    return this.mode
  }

  get selection(): TierChoice {
    return this.choice
  }

  /** The user's choice. A fixed tier switches the controller off; 'auto' restarts the probe. */
  setChoice(choice: TierChoice): Tier {
    this.choice = choice
    this.upSteps = 0
    this.lastChange = Number.NEGATIVE_INFINITY
    this.restartWindow()
    this.last = Number.NaN
    this.warmFrom = Number.NaN
    this.probeStart = Number.NaN
    if (isTier(choice)) {
      this.current = choice
      this.mode = 'fixed'
    } else {
      this.current = this.o.startTier
      this.mode = 'probe'
    }
    return this.current
  }

  private restartWindow(): void {
    this.head = 0
    this.size = 0
    this.goodSince = Number.NaN
    this.windowStart = Number.NEGATIVE_INFINITY
  }

  /** Feed the timestamp (ms) of a presented frame. Returns an event when the tier changed. */
  frame(nowMs: number): TierEvent | null {
    const dt = nowMs - this.last
    this.last = nowMs
    if (this.mode === 'fixed' || !Number.isFinite(dt)) return null
    if (dt > this.o.gapMs || dt < 0) {
      // The tab was hidden or the machine stalled: what came before says nothing about now.
      this.restartWindow()
      this.probeStart = Number.NaN
      this.warmFrom = Number.NaN
      return null
    }
    return this.mode === 'probe' ? this.probe(nowMs, dt) : this.run(nowMs, dt)
  }

  private add(nowMs: number, dt: number): void {
    this.stamps[this.head] = nowMs
    this.durations[this.head] = dt
    this.head = (this.head + 1) % RING
    this.size = Math.min(RING, this.size + 1)
  }

  /** 5th-percentile fps and median fps over the frames since `since`. */
  private measure(since: number): Window {
    let n = 0
    for (let i = 0; i < this.size; i++) {
      const at = (this.head - 1 - i + RING) % RING
      if ((this.stamps[at] ?? 0) < since) break
      this.scratch[n++] = this.durations[at] ?? 0
    }
    if (n === 0) return { fps5th: 0, fpsMedian: 0, frames: 0 }
    const view = this.scratch.subarray(0, n).sort()
    const slow = percentileOf(view, 95)
    const median = percentileOf(view, 50)
    return {
      fps5th: slow > 0 ? 1000 / slow : 0,
      fpsMedian: median > 0 ? 1000 / median : 0,
      frames: n,
    }
  }

  private probe(nowMs: number, dt: number): TierEvent | null {
    if (Number.isNaN(this.warmFrom)) this.warmFrom = nowMs
    if (nowMs - this.warmFrom < this.o.warmupMs) return null
    if (Number.isNaN(this.probeStart)) this.probeStart = nowMs
    this.add(nowMs, dt)
    if (nowMs - this.probeStart < this.o.probeMs) return null
    const m = this.measure(this.probeStart)
    const tier = m.frames < 10 ? this.current : pickTier(m.fps5th)
    this.mode = 'run'
    this.current = tier
    return this.settle(nowMs, tier, 'probe', m)
  }

  private run(nowMs: number, dt: number): TierEvent | null {
    this.add(nowMs, dt)
    if (nowMs - this.lastCheck < DEFAULTS.checkEveryMs) return null
    this.lastCheck = nowMs
    // A full window of fresh data after any change is required before a judgement.
    if (nowMs - this.lastChange < this.o.cooldownMs) return null
    if (nowMs - this.windowStart < this.o.windowMs) return null
    const m = this.measure(nowMs - this.o.windowMs)
    if (m.frames < 20) return null

    if (m.fps5th < this.o.floorFps && this.current !== 'low') {
      return this.settle(nowMs, stepDown(this.current), 'step-down', m)
    }
    if (m.fps5th >= this.o.ceilingFps && this.current !== 'high' && this.upSteps < 1) {
      if (Number.isNaN(this.goodSince)) this.goodSince = nowMs
      if (nowMs - this.goodSince >= this.o.upHoldMs) {
        this.upSteps++
        return this.settle(nowMs, stepUp(this.current), 'step-up', m)
      }
    } else {
      this.goodSince = Number.NaN
    }
    return null
  }

  private settle(nowMs: number, tier: Tier, reason: TierEvent['reason'], m: Window): TierEvent {
    this.current = tier
    this.lastChange = nowMs
    this.restartWindow()
    this.windowStart = nowMs
    return { tier, reason, fps5th: m.fps5th, fpsMedian: m.fpsMedian }
  }
}
