/**
 * Binds the live store to the two console models. Every new frame feeds its RF and acoustic
 * reports to the models and advances them to the frame's scenario time, whichever console tab is
 * showing, so the history is complete when the operator switches tabs. Frames that carry no
 * report still advance the picture (the noise floor scrolls on).
 */
import type { LiveStore } from '../store'
import { AcousticModel, RfModel } from './synth'
import { acousticEmissionOf, rfEmissionOf, type AcousticEmission, type RfEmission } from './spectra'

/** Reports older than this (scenario seconds) leave the text list. */
export const RECENT_S = 6
/** The text list holds at most this many reports. */
export const RECENT_MAX = 8

export class ConsoleFeed {
  readonly rf = new RfModel()
  readonly acoustic = new AcousticModel()
  /** Newest first. Replaced, never mutated, so a snapshot read in render stays valid. */
  rfRecent: readonly RfEmission[] = []
  acousticRecent: readonly AcousticEmission[] = []
  /** Where the acoustic cursor sits, kept here so it survives a tab switch. */
  cursorHz = 200
  /** Scenario time of the newest frame seen. */
  timeS = 0
  /** True once a frame with an RF / acoustic sensor was seen. */
  rfSensor = false
  acousticSensor = false
  /** Bumps when the text lists or sensor presence change. */
  version = 0

  private lastTick = -1
  private readonly listeners = new Set<() => void>()
  private unsubscribe: (() => void) | null = null

  constructor(private readonly store: LiveStore) {}

  subscribe = (listener: () => void): (() => void) => {
    this.listeners.add(listener)
    return () => {
      this.listeners.delete(listener)
    }
  }

  setCursor(hz: number): void {
    this.cursorHz = hz
  }

  getVersion = (): number => this.version

  /** Start following the store. Safe to call twice. */
  attach(): void {
    if (this.unsubscribe) return
    this.unsubscribe = this.store.subscribe(this.onState)
    this.onState()
  }

  detach(): void {
    this.unsubscribe?.()
    this.unsubscribe = null
  }

  private onState = (): void => {
    const frame = this.store.getState().frame
    if (!frame || frame.tick === this.lastTick) return
    this.lastTick = frame.tick
    const time = frame.time_s
    this.timeS = time
    let changed = false

    const rfSensor = frame.sensors.some((s) => s.modality === 'rf')
    const acousticSensor = frame.sensors.some((s) => s.modality === 'acoustic')
    if (rfSensor !== this.rfSensor || acousticSensor !== this.acousticSensor) {
      this.rfSensor = rfSensor
      this.acousticSensor = acousticSensor
      changed = true
    }

    const newRf: RfEmission[] = []
    const newAcoustic: AcousticEmission[] = []
    for (const report of frame.reports) {
      if (report.modality === 'rf') {
        const e = rfEmissionOf(report, time)
        if (!e) continue
        this.rf.ingest(e)
        newRf.push(e)
      } else if (report.modality === 'acoustic') {
        const e = acousticEmissionOf(report, time)
        if (!e) continue
        this.acoustic.ingest(e)
        newAcoustic.push(e)
      }
    }
    // Newest frame first; inside one frame the reports keep the order they were sent in.
    const fresh = (e: { timeS: number }) => time - e.timeS <= RECENT_S
    if (newRf.length > 0 || this.rfRecent.some((e) => !fresh(e))) {
      this.rfRecent = [...newRf, ...this.rfRecent].filter(fresh).slice(0, RECENT_MAX)
      changed = true
    }
    if (newAcoustic.length > 0 || this.acousticRecent.some((e) => !fresh(e))) {
      this.acousticRecent = [...newAcoustic, ...this.acousticRecent]
        .filter(fresh)
        .slice(0, RECENT_MAX)
      changed = true
    }

    if (rfSensor) this.rf.advanceTo(time)
    if (acousticSensor) this.acoustic.advanceTo(time)
    if (changed) {
      this.version += 1
      this.listeners.forEach((l) => l())
    }
  }
}
