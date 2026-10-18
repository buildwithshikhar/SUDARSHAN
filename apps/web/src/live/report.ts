/**
 * The contact-report form as pure functions: what the form starts with, how its text fields are
 * checked, and the payload the `report` action carries. Ranges are the simulation's
 * (docs/LIVE_SESSION.md): count 1 to 99, bearing and heading 0 to under 360, range 0 to 50,000 m,
 * confidence 0 to 1 (entered as a percentage).
 */
import { polarFrom, wrap360 } from './geometry'
import { sitePosition } from './format'
import type { Briefing, TrackView } from './protocol'

export interface ReportValues {
  /** An operator class, or '' for not stated. */
  what: string
  bearing: string
  range: string
  count: string
  heading: string
  confidence: string
}

export type ReportField = keyof ReportValues

/** Error message keys under `live.report.error`, by the field they belong to. */
export interface ReportCheck {
  errors: Partial<
    Record<ReportField, 'bearing' | 'range' | 'pair' | 'count' | 'heading' | 'confidence'>
  >
  payload: Record<string, unknown> | null
}

export const MAX_RANGE_M = 50_000

/** Bearing and range from the site to the track, and the track's heading, rounded for typing. */
export function prefillReport(
  track: TrackView,
  briefing: Briefing,
  classification: string | null,
): ReportValues {
  const polar = polarFrom(sitePosition(briefing), track.position)
  const bearing = Math.round(polar.bearingDeg) % 360
  const heading = Math.round(wrap360(track.heading_deg)) % 360
  return {
    what: classification ?? '',
    bearing: String(bearing),
    range: String(Math.min(MAX_RANGE_M, Math.round(polar.rangeM))),
    count: '1',
    heading: String(heading),
    confidence: '',
  }
}

const NUMBER = /^\s*-?\d+(\.\d+)?\s*$/

function parse(text: string): number | null | 'empty' {
  if (text.trim() === '') return 'empty'
  if (!NUMBER.test(text)) return null
  const value = Number(text)
  return Number.isFinite(value) ? value : null
}

/**
 * Check the form. Every field is optional; a field that is filled must be in range. Bearing and
 * range go together, because a position needs both. `payload` is null when anything is wrong.
 */
export function checkReport(track: string, values: ReportValues): ReportCheck {
  const errors: ReportCheck['errors'] = {}
  const payload: Record<string, unknown> = { track }
  if (values.what !== '') payload.class_id = values.what

  const count = parse(values.count)
  if (count !== 'empty') {
    if (count === null || !Number.isInteger(count) || count < 1 || count > 99)
      errors.count = 'count'
    else payload.count = count
  }

  const bearing = parse(values.bearing)
  const range = parse(values.range)
  if (bearing !== 'empty' && (bearing === null || bearing < 0 || bearing >= 360))
    errors.bearing = 'bearing'
  if (range !== 'empty' && (range === null || range < 0 || range > MAX_RANGE_M))
    errors.range = 'range'
  if (!errors.bearing && !errors.range) {
    if ((bearing === 'empty') !== (range === 'empty')) {
      if (bearing === 'empty') errors.bearing = 'pair'
      else errors.range = 'pair'
    } else if (bearing !== 'empty' && range !== 'empty' && bearing !== null && range !== null) {
      payload.bearing_deg = bearing
      payload.range_m = range
    }
  }

  const heading = parse(values.heading)
  if (heading !== 'empty') {
    if (heading === null || heading < 0 || heading >= 360) errors.heading = 'heading'
    else payload.heading_deg = heading
  }

  const confidence = parse(values.confidence)
  if (confidence !== 'empty') {
    if (confidence === null || confidence < 0 || confidence > 100) errors.confidence = 'confidence'
    else payload.confidence = Math.round(confidence * 100) / 10000
  }

  return { errors, payload: Object.keys(errors).length === 0 ? payload : null }
}
