/**
 * The shared quality state of the 3D views: the user's choice (persisted), the tier in force, the
 * frame statistics and a small subscription for React. One instance serves the app; the /bench
 * harness reads the same one (`qualityStore.frameStats`, `qualityStore.getState()`).
 */
import { useSyncExternalStore } from 'react'
import { readSetting, writeSetting } from '../lib/storage'
import {
  DEFAULTS,
  FrameStats,
  isTierChoice,
  TierController,
  type FrameSnapshot,
  type Tier,
  type TierChoice,
  type TierEvent,
} from './quality'

export const QUALITY_KEY = 'ui.quality'

export interface QualityState {
  /** What the user picked: Auto or a fixed tier. */
  choice: TierChoice
  /** The tier in force. */
  tier: Tier
  phase: 'probe' | 'run' | 'fixed'
  /** The last automatic decision and the figures it was made on; null before the probe ends. */
  lastEvent: TierEvent | null
  /** Frame statistics, refreshed about once a second while frames arrive. */
  stats: FrameSnapshot
}

export interface Storage {
  read(key: string): string | null
  write(key: string, value: string): void
}

const EMPTY: FrameSnapshot = {
  count: 0,
  meanMs: 0,
  p50Ms: 0,
  p95Ms: 0,
  p99Ms: 0,
  maxMs: 0,
  fpsMean: 0,
  fps5th: 0,
}

/** Publish the statistics at most this often (ms of frame time). */
const PUBLISH_EVERY_MS = 1000

export class QualityStore {
  /** Per-frame durations since the last `resetStats()`. The /bench route reads percentiles here. */
  readonly frameStats = new FrameStats()
  private readonly controller: TierController
  private state: QualityState
  private readonly listeners = new Set<() => void>()
  private lastFrame = Number.NaN
  private lastPublish = Number.NEGATIVE_INFINITY

  constructor(private readonly storage: Storage) {
    const stored = storage.read(QUALITY_KEY)
    const choice: TierChoice = isTierChoice(stored) ? stored : 'auto'
    this.controller = new TierController({ choice })
    this.state = {
      choice,
      tier: this.controller.tier,
      phase: this.controller.phase,
      lastEvent: null,
      stats: EMPTY,
    }
  }

  getState = (): QualityState => this.state

  subscribe = (listener: () => void): (() => void) => {
    this.listeners.add(listener)
    return () => this.listeners.delete(listener)
  }

  private set(patch: Partial<QualityState>): void {
    this.state = { ...this.state, ...patch }
    this.listeners.forEach((l) => l())
  }

  /** The user's choice; persisted. Auto restarts the two-second probe. */
  setChoice = (choice: TierChoice): void => {
    this.storage.write(QUALITY_KEY, choice)
    const tier = this.controller.setChoice(choice)
    this.lastFrame = Number.NaN
    this.set({ choice, tier, phase: this.controller.phase, lastEvent: null })
  }

  /**
   * Call once per presented frame with its timestamp (the rAF time). Records the duration, feeds
   * the controller and returns the event if the tier changed.
   */
  frame = (nowMs: number): TierEvent | null => {
    const dt = nowMs - this.lastFrame
    this.lastFrame = nowMs
    // A gap this long is a hidden tab, not a slow frame.
    if (Number.isFinite(dt) && dt > 0 && dt <= DEFAULTS.gapMs) this.frameStats.push(dt)
    const event = this.controller.frame(nowMs)
    const publish = nowMs - this.lastPublish >= PUBLISH_EVERY_MS
    if (event || publish) {
      if (publish) this.lastPublish = nowMs
      this.set({
        tier: this.controller.tier,
        phase: this.controller.phase,
        lastEvent: event ?? this.state.lastEvent,
        stats: publish ? this.frameStats.snapshot() : this.state.stats,
      })
    }
    return event
  }

  resetStats = (): void => {
    this.frameStats.reset()
    this.lastFrame = Number.NaN
    this.set({ stats: EMPTY })
  }
}

export const qualityStore = new QualityStore({ read: readSetting, write: writeSetting })

export function useQuality(): QualityState & { setChoice: (choice: TierChoice) => void } {
  const state = useSyncExternalStore(
    qualityStore.subscribe,
    qualityStore.getState,
    qualityStore.getState,
  )
  return { ...state, setChoice: qualityStore.setChoice }
}
