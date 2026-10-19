/**
 * Pure maths for the RF and acoustic consoles.
 *
 * The server sends no raw spectra. Each console DRAWS A SYNTHESISED DISPLAY from the sensor
 * reports of a frame: an RF report names a band, a level in dBm and whether the link hops; an
 * acoustic report names a blade-pass frequency, a harmonic count and an SNR. Nothing here reads
 * bearing, class or identity ground truth: only what a report carries is used, and placement
 * choices the report does not carry (a carrier slot inside a band window, the hop sequence, the
 * noise texture) are labelled as display decisions in the console legend.
 */
import type { Report } from '../protocol'

export type DataStatus = Report['data_status']

/** One display row covers this much scenario time. */
export const ROW_S = 0.25
/** Rows kept: the console shows the last 30 s of scenario time. */
export const ROWS = 120
export const HISTORY_S = ROW_S * ROWS

/** How long one report keeps painting after it arrives (the sensors update every 0.5 to 1 s). */
export const RF_HOLD_S = 1.25
export const ACOUSTIC_HOLD_S = 0.75

// ------------------------------------------------------------------------------------- RF

export interface RfBand {
  /** The label the server reports, e.g. '2.4 GHz'. */
  label: string
  centreMHz: number
  /** Half the width of the display window around the centre. A display span, not a channel plan. */
  halfSpanMHz: number
}

/**
 * The five bands of services/api/sim/sensors/rf.py `BANDS`, in ascending frequency. The bands are
 * far apart, so the console shows five equal windows side by side rather than one continuous axis.
 */
export const RF_BANDS: readonly RfBand[] = [
  { label: '433 MHz', centreMHz: 433, halfSpanMHz: 5 },
  { label: '900 MHz', centreMHz: 900, halfSpanMHz: 15 },
  { label: '1.2-1.3 GHz', centreMHz: 1250, halfSpanMHz: 50 },
  { label: '2.4 GHz', centreMHz: 2440, halfSpanMHz: 45 },
  { label: '5.8 GHz', centreMHz: 5800, halfSpanMHz: 80 },
]

export const BINS_PER_BAND = 48
export const RF_BINS = RF_BANDS.length * BINS_PER_BAND
/** Hop positions inside a window. */
export const HOP_CHANNELS = 16
/** The vertical scale of the spectrum line. */
export const RF_FLOOR_DBM = -100
export const RF_CEIL_DBM = -50
/** The noise floor of the RF profile (docs/SENSOR_MODELS.md, `noise_floor`). */
export const RF_NOISE_DBM = -95

/** Index into `RF_BANDS` for a reported band label, or -1 when the label is not in the plan. */
export function rfBandIndex(label: unknown): number {
  return typeof label === 'string' ? RF_BANDS.findIndex((b) => b.label === label) : -1
}

/** Centre frequency (MHz) of display bin `bin`: the window's centre plus the offset inside it. */
export function rfBinMHz(bin: number): number {
  const band = Math.min(RF_BANDS.length - 1, Math.max(0, Math.floor(bin / BINS_PER_BAND)))
  const info = RF_BANDS[band]
  if (!info) return 0
  const within = (bin - band * BINS_PER_BAND + 0.5) / BINS_PER_BAND - 0.5
  return info.centreMHz + within * 2 * info.halfSpanMHz
}

// ------------------------------------------------------------------------------- acoustic

export const AC_MAX_HZ = 2000
export const AC_BIN_HZ = 5
export const AC_BINS = AC_MAX_HZ / AC_BIN_HZ
export const AC_STEP_HZ = AC_BIN_HZ
export const AC_COARSE_HZ = 50
/** Display ceiling in dB above the noise floor. */
export const AC_CEIL_DB = 40
/** Each harmonic is drawn this much weaker than the one below it (display rule). */
export const AC_ROLLOFF_DB = 3

// -------------------------------------------------------------------------- report parsing

export interface RfEmission {
  sensorId: string
  /** Index into `RF_BANDS`, or -1 for a band label the display has no window for. */
  band: number
  bandLabel: string
  rssiDbm: number
  hopping: boolean
  hopRateHz: number
  azimuthDeg: number
  timeS: number
  dataStatus: DataStatus
}

export interface AcousticEmission {
  sensorId: string
  fundamentalHz: number
  harmonics: number
  tonal: boolean
  snrDb: number
  azimuthDeg: number
  timeS: number
  dataStatus: DataStatus
}

const num = (value: unknown): number | null =>
  typeof value === 'number' && Number.isFinite(value) ? value : null

/** An RF report as an emission, or null when it is not an RF report or lacks a level. */
export function rfEmissionOf(report: Report, timeS: number): RfEmission | null {
  if (report.modality !== 'rf') return null
  const f = report.features
  const rssi = num(f.rssi_dbm)
  if (rssi === null) return null
  const hopping = f.hopping === true
  const rate = num(f.hop_rate_hz)
  return {
    sensorId: report.sensor_id,
    band: rfBandIndex(f.band),
    bandLabel: typeof f.band === 'string' ? f.band : '',
    rssiDbm: rssi,
    hopping,
    hopRateHz: hopping && rate !== null && rate > 0 ? rate : 0,
    azimuthDeg: report.azimuth_deg,
    timeS,
    dataStatus: report.data_status,
  }
}

/** An acoustic report as an emission, or null when it is not one or lacks a blade-pass rate. */
export function acousticEmissionOf(report: Report, timeS: number): AcousticEmission | null {
  if (report.modality !== 'acoustic') return null
  const f = report.features
  const fundamental = num(f.blade_pass_hz)
  const snr = num(f.snr_db)
  if (fundamental === null || fundamental <= 0 || snr === null) return null
  const harmonics = num(f.harmonics)
  return {
    sensorId: report.sensor_id,
    fundamentalHz: fundamental,
    harmonics: harmonics === null ? 1 : Math.max(1, Math.min(32, Math.floor(harmonics))),
    tonal: f.tonal === true,
    snrDb: snr,
    azimuthDeg: report.azimuth_deg,
    timeS,
    dataStatus: report.data_status,
  }
}

// ------------------------------------------------------------------------------ hashing

/** A small integer hash: the same inputs always give the same display texture. */
export function hash32(a: number, b = 0, c = 0): number {
  let h = Math.imul(a | 0, 0x9e3779b1) ^ Math.imul(b | 0, 0x85ebca6b) ^ Math.imul(c | 0, 0xc2b2ae35)
  h ^= h >>> 15
  h = Math.imul(h, 0x2c1b3c6d)
  h ^= h >>> 12
  h = Math.imul(h, 0x297a2d39)
  h ^= h >>> 15
  return h >>> 0
}

/** Hash mapped to [0, 1). */
export const unit = (a: number, b = 0, c = 0): number => hash32(a, b, c) / 4294967296

/** 45 degree sector of a bearing, 0 to 7: separates two links in one band on the display. */
export const sectorOf = (azimuthDeg: number): number =>
  Math.floor((((azimuthDeg % 360) + 360) % 360) / 45) % 8

/**
 * Where a non-hopping carrier sits inside its window, as a bin. A display placement: the report
 * carries a band, not a frequency, so the slot is chosen from the bearing sector to keep two
 * simultaneous links in one band apart.
 */
export function carrierBin(band: number, azimuthDeg: number): number {
  const slot = unit(band + 1, sectorOf(azimuthDeg), 77)
  const inner = Math.round((slot - 0.5) * 0.5 * BINS_PER_BAND)
  return band * BINS_PER_BAND + BINS_PER_BAND / 2 + inner
}

/** Display bin of hop number `k` of a link in `band` (a deterministic pseudo-random sequence). */
export function hopBin(band: number, azimuthDeg: number, k: number): number {
  const channel = hash32(k, band + 1, sectorOf(azimuthDeg) + 11) % HOP_CHANNELS
  return band * BINS_PER_BAND + Math.floor(((channel + 0.5) / HOP_CHANNELS) * BINS_PER_BAND)
}

// ------------------------------------------------------------------------------ levels

const clamp01 = (x: number): number => Math.min(1, Math.max(0, x))

/** Level to a byte (0 to 255) over a floor and a ceiling. */
export const levelToByte = (value: number, floor: number, ceil: number): number =>
  Math.round(clamp01((value - floor) / (ceil - floor)) * 255)

/** dBm to the 0 to 1 vertical position on the spectrum line. */
export const dbmFraction = (dbm: number): number =>
  clamp01((dbm - RF_FLOOR_DBM) / (RF_CEIL_DBM - RF_FLOOR_DBM))

// ----------------------------------------------------------------------------- colormap

/** Inferno at nine anchors (matplotlib's colormap), interpolated to 256 entries. */
const INFERNO: readonly (readonly [number, number, number])[] = [
  [0, 0, 4],
  [31, 12, 72],
  [85, 15, 109],
  [136, 34, 106],
  [186, 54, 85],
  [227, 89, 51],
  [249, 140, 10],
  [249, 201, 50],
  [252, 255, 164],
]

/** 256 RGB triples, packed as r, g, b. */
export const INFERNO_LUT: Uint8Array = (() => {
  const out = new Uint8Array(256 * 3)
  const last = INFERNO.length - 1
  for (let i = 0; i < 256; i++) {
    const x = (i / 255) * last
    const lo = Math.min(last - 1, Math.floor(x))
    const k = x - lo
    for (let c = 0; c < 3; c++) {
      const a = INFERNO[lo]?.[c] ?? 0
      const b = INFERNO[lo + 1]?.[c] ?? 0
      out[i * 3 + c] = Math.round(a + (b - a) * k)
    }
  }
  return out
})()

// ------------------------------------------------------------------------- cursor maths

/** Move the acoustic cursor one step (or one coarse step) left or right, kept on the scale. */
export function moveCursor(hz: number, direction: -1 | 1, coarse: boolean): number {
  const step = coarse ? AC_COARSE_HZ : AC_STEP_HZ
  const next = Math.round((hz + direction * step) / AC_STEP_HZ) * AC_STEP_HZ
  return Math.min(AC_MAX_HZ, Math.max(0, next))
}

export interface NearestHarmonic {
  /** Index into the lines passed in. */
  line: number
  order: number
  /** Frequency of that harmonic. */
  lineHz: number
  /** Cursor minus the harmonic, in Hz. */
  deltaHz: number
  /** The fundamental the cursor implies if it sits on that order: cursor / order. */
  impliedBladePassHz: number
}

export interface HarmonicLine {
  fundamentalHz: number
  harmonics: number
  snrDb?: number
}

/** The highest order of a line that stays on the 0 to 2 kHz scale. */
export const maxOrder = (line: HarmonicLine): number =>
  Math.max(1, Math.min(line.harmonics, Math.floor(AC_MAX_HZ / line.fundamentalHz)))

/**
 * The harmonic of any reported line that lies nearest the cursor. The order is capped at the
 * reported harmonic count. Ties go to the stronger report. Null when no line is reported or the
 * cursor sits at 0 Hz (an order cannot be read from it).
 */
export function nearestHarmonic(
  cursorHz: number,
  lines: readonly HarmonicLine[],
): NearestHarmonic | null {
  if (cursorHz <= 0) return null
  let best: NearestHarmonic | null = null
  let bestSnr = -Infinity
  for (let index = 0; index < lines.length; index++) {
    const line = lines[index]
    if (!line || line.fundamentalHz <= 0) continue
    const order = Math.min(maxOrder(line), Math.max(1, Math.round(cursorHz / line.fundamentalHz)))
    const lineHz = order * line.fundamentalHz
    const delta = cursorHz - lineHz
    const snr = line.snrDb ?? 0
    if (
      best === null ||
      Math.abs(delta) < Math.abs(best.deltaHz) - 1e-9 ||
      (Math.abs(Math.abs(delta) - Math.abs(best.deltaHz)) <= 1e-9 && snr > bestSnr)
    ) {
      best = {
        line: index,
        order,
        lineHz,
        deltaHz: delta,
        impliedBladePassHz: cursorHz / order,
      }
      bestSnr = snr
    }
  }
  return best
}
