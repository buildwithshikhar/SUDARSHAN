/**
 * The two synthesised displays. A model takes emissions (parsed sensor reports), advances in
 * fixed steps of scenario time and writes one row per step into a ring. It owns every typed array
 * it needs, so the per-frame and per-row paths allocate nothing.
 */
import { RowRing } from './ring'
import {
  ACOUSTIC_HOLD_S,
  AC_BINS,
  AC_BIN_HZ,
  AC_CEIL_DB,
  AC_MAX_HZ,
  AC_ROLLOFF_DB,
  BINS_PER_BAND,
  HISTORY_S,
  RF_BINS,
  RF_CEIL_DBM,
  RF_FLOOR_DBM,
  RF_HOLD_S,
  RF_NOISE_DBM,
  ROWS,
  ROW_S,
  carrierBin,
  hopBin,
  levelToByte,
  maxOrder,
  unit,
  type AcousticEmission,
  type RfEmission,
} from './spectra'

const POOL = 32
/** At most this many hops are painted into one row, however fast the link hops. */
const MAX_HOPS_PER_ROW = 12
/** The peak-hold trace falls this many dB per row. */
export const PEAK_DECAY_DB = 2
/** A hopping link whose report carries no rate is stepped at this rate; a display choice only. */
export const DISPLAY_HOP_HZ = 8
/** Slack for the float comparison of row boundaries. */
const EPS = 1e-6

/** Loss in dB at -2 .. +2 bins from the centre of a narrow RF carrier. */
const RF_SKIRT = [16, 8, 0, 8, 16] as const
/** Loss in dB at -1 .. +1 bins from an acoustic line. */
const AC_SKIRT = [9, 0, 9] as const

/** Which of `POOL` slots hold a report that can still paint, newest overwriting oldest. */
class Slots {
  head = 0
  used = 0
  take(): number {
    const slot = this.head
    this.head = (this.head + 1) % POOL
    this.used = Math.min(POOL, this.used + 1)
    return slot
  }
  clear(): void {
    this.head = 0
    this.used = 0
  }
}

export class RfModel {
  readonly ring = new RowRing(RF_BINS, ROWS)
  /** The last row, in dBm. */
  readonly spectrum = new Float32Array(RF_BINS).fill(RF_FLOOR_DBM)
  /** Peak hold: the row maximum, falling slowly. */
  readonly peak = new Float32Array(RF_BINS).fill(RF_FLOOR_DBM)
  /** Scenario time at which the next row starts, or null before the first frame. */
  nextRowS: number | null = null
  /** Bumps whenever rows were written. */
  version = 0

  private readonly scratch = new Float32Array(RF_BINS)
  private readonly slots = new Slots()
  private readonly t0 = new Float64Array(POOL)
  private readonly band = new Int8Array(POOL)
  private readonly rssi = new Float32Array(POOL)
  private readonly rate = new Float32Array(POOL)
  private readonly azimuth = new Float32Array(POOL)

  /** Hold one report so that the rows covering its time paint it. Unknown bands are not drawn. */
  ingest(e: RfEmission): void {
    if (e.band < 0) return
    const i = this.slots.take()
    this.t0[i] = e.timeS
    this.band[i] = e.band
    this.rssi[i] = e.rssiDbm
    this.rate[i] = e.hopping ? (e.hopRateHz > 0 ? e.hopRateHz : DISPLAY_HOP_HZ) : 0
    this.azimuth[i] = e.azimuthDeg
  }

  /** Write every row that scenario time has now finished. Returns the number of rows written. */
  advanceTo(timeS: number): number {
    if (this.nextRowS === null) this.nextRowS = timeS
    if (timeS - this.nextRowS > HISTORY_S) this.nextRowS = timeS - HISTORY_S
    let written = 0
    while (this.nextRowS + ROW_S <= timeS + EPS) {
      this.row(this.nextRowS)
      this.nextRowS += ROW_S
      written += 1
    }
    if (written > 0) this.version += 1
    return written
  }

  /** Forget everything (a new session). */
  reset(): void {
    this.ring.clear()
    this.slots.clear()
    this.spectrum.fill(RF_FLOOR_DBM)
    this.peak.fill(RF_FLOOR_DBM)
    this.nextRowS = null
    this.version += 1
  }

  private stamp(bin: number, level: number): void {
    const window = Math.floor(bin / BINS_PER_BAND)
    for (let d = -2; d <= 2; d++) {
      const b = bin + d
      if (b < 0 || b >= RF_BINS || Math.floor(b / BINS_PER_BAND) !== window) continue
      const v = level - (RF_SKIRT[d + 2] ?? 0)
      if (v > (this.scratch[b] ?? 0)) this.scratch[b] = v
    }
  }

  private row(rowS: number): void {
    const index = Math.round(rowS / ROW_S)
    const s = this.scratch
    for (let b = 0; b < RF_BINS; b++) s[b] = RF_NOISE_DBM + (unit(b, index, 5) - 0.5) * 3
    const end = rowS + ROW_S
    for (let i = 0; i < this.slots.used; i++) {
      if (!((this.t0[i] ?? 0) < end && (this.t0[i] ?? 0) + RF_HOLD_S > rowS)) continue
      const band = this.band[i] ?? 0
      const level = this.rssi[i] ?? 0
      const rate = this.rate[i] ?? 0
      const az = this.azimuth[i] ?? 0
      if (rate > 0) {
        const k0 = Math.floor(rowS * rate)
        const k1 = Math.floor((end - EPS) * rate)
        const n = k1 - k0 + 1
        const step = n > MAX_HOPS_PER_ROW ? n / MAX_HOPS_PER_ROW : 1
        const count = Math.min(n, MAX_HOPS_PER_ROW)
        for (let j = 0; j < count; j++) {
          this.stamp(hopBin(band, az, k0 + Math.floor(j * step)), level)
        }
      } else {
        this.stamp(carrierBin(band, az), level)
      }
    }
    const offset = this.ring.next()
    const out = this.ring.data
    for (let b = 0; b < RF_BINS; b++) {
      out[offset + b] = levelToByte(s[b] ?? 0, RF_FLOOR_DBM, RF_CEIL_DBM)
      this.spectrum[b] = s[b] ?? 0
      const held = (this.peak[b] ?? 0) - PEAK_DECAY_DB
      this.peak[b] = (s[b] ?? 0) > held ? (s[b] ?? 0) : held
    }
  }
}

export class AcousticModel {
  readonly ring = new RowRing(AC_BINS, ROWS)
  nextRowS: number | null = null
  version = 0

  private readonly scratch = new Float32Array(AC_BINS)
  private readonly slots = new Slots()
  private readonly t0 = new Float64Array(POOL)
  private readonly f0 = new Float32Array(POOL)
  private readonly harmonics = new Uint8Array(POOL)
  private readonly snr = new Float32Array(POOL)

  ingest(e: AcousticEmission): void {
    const i = this.slots.take()
    this.t0[i] = e.timeS
    this.f0[i] = e.fundamentalHz
    this.harmonics[i] = e.harmonics
    this.snr[i] = e.snrDb
  }

  advanceTo(timeS: number): number {
    if (this.nextRowS === null) this.nextRowS = timeS
    if (timeS - this.nextRowS > HISTORY_S) this.nextRowS = timeS - HISTORY_S
    let written = 0
    while (this.nextRowS + ROW_S <= timeS + EPS) {
      this.row(this.nextRowS)
      this.nextRowS += ROW_S
      written += 1
    }
    if (written > 0) this.version += 1
    return written
  }

  reset(): void {
    this.ring.clear()
    this.slots.clear()
    this.nextRowS = null
    this.version += 1
  }

  private row(rowS: number): void {
    const index = Math.round(rowS / ROW_S)
    const s = this.scratch
    for (let b = 0; b < AC_BINS; b++) s[b] = 0.5 + unit(b, index, 9) * 1.5
    const end = rowS + ROW_S
    for (let i = 0; i < this.slots.used; i++) {
      if (!((this.t0[i] ?? 0) < end && (this.t0[i] ?? 0) + ACOUSTIC_HOLD_S > rowS)) continue
      const f0 = this.f0[i] ?? 0
      const orders = maxOrder({ fundamentalHz: f0, harmonics: this.harmonics[i] ?? 0 })
      for (let k = 1; k <= orders; k++) {
        const hz = k * f0
        if (hz >= AC_MAX_HZ) break
        const level = (this.snr[i] ?? 0) - AC_ROLLOFF_DB * (k - 1)
        const centre = Math.floor(hz / AC_BIN_HZ)
        for (let d = -1; d <= 1; d++) {
          const b = centre + d
          if (b < 0 || b >= AC_BINS) continue
          const v = level - (AC_SKIRT[d + 1] ?? 0)
          if (v > (s[b] ?? 0)) s[b] = v
        }
      }
    }
    const offset = this.ring.next()
    const out = this.ring.data
    for (let b = 0; b < AC_BINS; b++) out[offset + b] = levelToByte(s[b] ?? 0, 0, AC_CEIL_DB)
  }
}
