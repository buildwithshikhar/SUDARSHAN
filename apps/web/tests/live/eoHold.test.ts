import { describe, expect, it } from 'vitest'
import type { Report } from '../../src/live/protocol'
import { HOLD_MS, ReportHold, shapeFor } from '../../src/live/views/eoHold'

const report = (extra: Partial<Report> = {}): Report => ({
  tick: 1,
  sensor_id: 'eo-1',
  modality: 'eo',
  azimuth_deg: 40,
  elevation_deg: 4,
  range_m: null,
  radial_speed_mps: null,
  reported_class: null,
  sigma_azimuth_deg: 0.01,
  sigma_elevation_deg: 0.01,
  sigma_range_m: null,
  sigma_radial_mps: null,
  features: { apparent_px: 12, recognised: false },
  data_status: 'reference',
  ...extra,
})

const FOV = { 'eo-1': 4.8 }

describe('EO report hold', () => {
  it('shows a report for 0.4 s and then forgets it', () => {
    const hold = new ReportHold()
    hold.ingest([report()], FOV, 1000)
    expect(HOLD_MS).toBe(400)
    expect(hold.active(1000)).toHaveLength(1)
    expect(hold.active(1399)).toHaveLength(1)
    expect(hold.active(1401)).toHaveLength(0)
  })

  it('places it at the reported bearing and elevation, at the size its pixels imply', () => {
    const hold = new ReportHold()
    hold.ingest(
      [report({ azimuth_deg: 41.5, elevation_deg: 3.2, features: { apparent_px: 24 } })],
      FOV,
      0,
    )
    const [h] = hold.active(0)
    expect(h).toMatchObject({ azimuthDeg: 41.5, elevationDeg: 3.2, apparentPx: 24 })
    expect(h!.sizeDeg).toBeCloseTo(24 * (4.8 / 1920))
  })

  it('refreshes the same object when the next report lands near it', () => {
    const hold = new ReportHold()
    hold.ingest([report()], FOV, 0)
    const key = hold.active(0)[0]!.key
    hold.ingest([report({ azimuth_deg: 40.2, elevation_deg: 4.05 })], FOV, 300)
    expect(hold.active(600)).toHaveLength(1)
    expect(hold.active(600)[0]!.key).toBe(key)
    hold.ingest([report({ azimuth_deg: 47, elevation_deg: 9 })], FOV, 300)
    expect(hold.active(600)).toHaveLength(2)
  })

  it('uses only EO and IR reports that carry apparent pixels, and never invents a range', () => {
    const hold = new ReportHold()
    hold.ingest(
      [
        report({ modality: 'radar', sensor_id: 'radar-1', range_m: 1200 }),
        report({ modality: 'rf', sensor_id: 'rf-1', features: { band: '2.4 GHz' } }),
        report({ features: { recognised: true } }),
        report({ sensor_id: 'eo-9' }),
      ],
      FOV,
      0,
    )
    expect(hold.active(0)).toEqual([])
    hold.ingest([report({ modality: 'ir', sensor_id: 'eo-1' })], FOV, 0)
    expect(hold.active(0)).toHaveLength(1)
    expect(Object.keys(hold.active(0)[0]!)).not.toContain('rangeM')
  })

  it('draws a generic point below recognition and the reported class above it', () => {
    expect(shapeFor(null)).toBe('point')
    expect(shapeFor('unknown')).toBe('point')
    expect(shapeFor('anything else')).toBe('point')
    expect(shapeFor('rotary-small')).toBe('rotary-small')
    expect(shapeFor('fixed-wing-small')).toBe('fixed-wing-small')
    expect(shapeFor('bird')).toBe('bird')
    const hold = new ReportHold()
    hold.ingest([report({ reported_class: 'bird' })], FOV, 0)
    expect(hold.active(0)[0]!.shape).toBe('bird')
  })
})
