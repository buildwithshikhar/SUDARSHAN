import { describe, expect, it } from 'vitest'
import { acousticLayout, rfLayout } from '../../src/live/consoles/draw'
import { ConsoleFeed, RECENT_MAX, RECENT_S } from '../../src/live/consoles/feed'
import { RowRing } from '../../src/live/consoles/ring'
import {
  AC_BINS,
  AC_BIN_HZ,
  AC_MAX_HZ,
  BINS_PER_BAND,
  HISTORY_S,
  INFERNO_LUT,
  RF_BANDS,
  RF_BINS,
  ROWS,
  ROW_S,
  acousticEmissionOf,
  carrierBin,
  hopBin,
  moveCursor,
  nearestHarmonic,
  rfBandIndex,
  rfBinMHz,
  rfEmissionOf,
} from '../../src/live/consoles/spectra'
import { AcousticModel, RfModel } from '../../src/live/consoles/synth'
import { LiveStore } from '../../src/live/store'
import type { Report } from '../../src/live/protocol'
import { frame } from './helpers'

function report(over: Partial<Report>): Report {
  return {
    tick: 0,
    sensor_id: 'rf-1',
    modality: 'rf',
    azimuth_deg: 90,
    elevation_deg: 3,
    range_m: null,
    radial_speed_mps: null,
    sigma_azimuth_deg: 6,
    sigma_elevation_deg: 12,
    sigma_range_m: null,
    sigma_radial_mps: null,
    reported_class: null,
    features: {},
    data_status: 'reference',
    ...over,
  }
}

const rf = (features: Report['features'], over: Partial<Report> = {}) =>
  report({ modality: 'rf', features, ...over })
const ac = (features: Report['features'], over: Partial<Report> = {}) =>
  report({ modality: 'acoustic', sensor_id: 'acoustic-1', features, ...over })

/** The byte at one window of the newest row of an RF ring. */
const windowMax = (ring: RowRing, band: number, age = 0): number => {
  let m = 0
  for (let b = band * BINS_PER_BAND; b < (band + 1) * BINS_PER_BAND; b++)
    m = Math.max(m, ring.at(age, b))
  return m
}
const lit = (ring: RowRing, from: number, to: number, age = 0, over = 40): number => {
  let n = 0
  for (let b = from; b < to; b++) if (ring.at(age, b) > over) n++
  return n
}

describe('RF band mapping', () => {
  it('has the five bands of the server plan in ascending order of frequency', () => {
    expect(RF_BANDS.map((b) => b.label)).toEqual([
      '433 MHz',
      '900 MHz',
      '1.2-1.3 GHz',
      '2.4 GHz',
      '5.8 GHz',
    ])
    const centres = RF_BANDS.map((b) => b.centreMHz)
    expect([...centres].sort((a, b) => a - b)).toEqual(centres)
    expect(new Set(centres)).toEqual(new Set([2440, 5800, 900, 433, 1250]))
    expect(RF_BINS).toBe(5 * BINS_PER_BAND)
  })

  it('maps a reported label to its window and an unknown label to -1', () => {
    expect(rfBandIndex('2.4 GHz')).toBe(3)
    expect(rfBandIndex('433 MHz')).toBe(0)
    expect(rfBandIndex('60 GHz')).toBe(-1)
    expect(rfBandIndex(undefined)).toBe(-1)
  })

  it('gives each bin a frequency inside its own window, rising across the window', () => {
    expect(Math.abs(rfBinMHz(3 * BINS_PER_BAND + BINS_PER_BAND / 2) - 2440)).toBeLessThan(2)
    for (let band = 0; band < RF_BANDS.length; band++) {
      const info = RF_BANDS[band]!
      const lo = rfBinMHz(band * BINS_PER_BAND)
      const hi = rfBinMHz((band + 1) * BINS_PER_BAND - 1)
      expect(lo).toBeGreaterThan(info.centreMHz - info.halfSpanMHz)
      expect(hi).toBeLessThan(info.centreMHz + info.halfSpanMHz)
      expect(hi).toBeGreaterThan(lo)
    }
  })

  it('places a carrier and every hop inside the window of its band, deterministically', () => {
    for (let band = 0; band < RF_BANDS.length; band++) {
      for (const az of [0, 44, 90, 181, 359]) {
        const c = carrierBin(band, az)
        expect(Math.floor(c / BINS_PER_BAND)).toBe(band)
        expect(carrierBin(band, az)).toBe(c)
        for (let k = 0; k < 40; k++) {
          expect(Math.floor(hopBin(band, az, k) / BINS_PER_BAND)).toBe(band)
          expect(hopBin(band, az, k)).toBe(hopBin(band, az, k))
        }
      }
    }
  })
})

describe('report parsing', () => {
  it('reads an RF report and nothing but what the report carries', () => {
    const e = rfEmissionOf(
      rf(
        { band: '2.4 GHz', hopping: true, hop_rate_hz: 41.6, rssi_dbm: -71.2 },
        { azimuth_deg: 33 },
      ),
      12.5,
    )
    expect(e).toMatchObject({
      band: 3,
      bandLabel: '2.4 GHz',
      rssiDbm: -71.2,
      hopping: true,
      hopRateHz: 41.6,
      azimuthDeg: 33,
      timeS: 12.5,
      dataStatus: 'reference',
    })
    expect(Object.keys(e!).sort()).toEqual(
      [
        'azimuthDeg',
        'band',
        'bandLabel',
        'dataStatus',
        'hopRateHz',
        'hopping',
        'rssiDbm',
        'sensorId',
        'timeS',
      ].sort(),
    )
  })

  it('drops a hop rate on a fixed link, and rejects other modalities or a missing level', () => {
    expect(
      rfEmissionOf(rf({ band: '5.8 GHz', hopping: false, hop_rate_hz: 9, rssi_dbm: -80 }), 0)
        ?.hopRateHz,
    ).toBe(0)
    expect(rfEmissionOf(rf({ band: '5.8 GHz', hopping: false }), 0)).toBeNull()
    expect(rfEmissionOf(ac({ blade_pass_hz: 100, snr_db: 5 }), 0)).toBeNull()
  })

  it('reads an acoustic report and bounds the harmonic count', () => {
    const e = acousticEmissionOf(
      ac({ blade_pass_hz: 188.4, harmonics: 4, tonal: true, snr_db: 17.5 }, { azimuth_deg: 210 }),
      3,
    )
    expect(e).toMatchObject({
      fundamentalHz: 188.4,
      harmonics: 4,
      tonal: true,
      snrDb: 17.5,
      azimuthDeg: 210,
    })
    expect(
      acousticEmissionOf(ac({ blade_pass_hz: 10, harmonics: 500, snr_db: 5 }), 0)?.harmonics,
    ).toBe(32)
    expect(acousticEmissionOf(ac({ blade_pass_hz: 0, harmonics: 2, snr_db: 5 }), 0)).toBeNull()
    expect(acousticEmissionOf(rf({ rssi_dbm: -70, band: '2.4 GHz' }), 0)).toBeNull()
  })
})

describe('row ring', () => {
  it('keeps a fixed-size array, newest first by age, and wraps', () => {
    const ring = new RowRing(4, 3)
    const length = ring.data.length
    for (let i = 1; i <= 5; i++) {
      const o = ring.next()
      ring.data[o] = i
    }
    expect(ring.data.length).toBe(length)
    expect(ring.count).toBe(3)
    expect(ring.version).toBe(5)
    expect([ring.at(0, 0), ring.at(1, 0), ring.at(2, 0)]).toEqual([5, 4, 3])
    expect(ring.at(3, 0)).toBe(0)
    expect(ring.slotOfAge(-1)).toBe(-1)
  })

  it('clears a claimed row before it is written', () => {
    const ring = new RowRing(2, 2)
    ring.data.fill(9)
    ring.next()
    expect(ring.at(0, 0)).toBe(0)
  })
})

describe('RF synthesis', () => {
  const advance = (m: RfModel, from: number, to: number) => {
    for (let t = from; t <= to + 1e-9; t += 0.05) m.advanceTo(t)
  }

  it('scrolls at a fixed rate in scenario time: four rows a second, none while time stands still', () => {
    const m = new RfModel()
    m.advanceTo(10)
    expect(m.ring.count).toBe(0)
    m.advanceTo(11)
    expect(m.ring.count).toBe(4)
    m.advanceTo(11)
    m.advanceTo(11.1)
    expect(m.ring.count).toBe(4)
    m.advanceTo(12)
    expect(m.ring.count).toBe(8)
    expect(ROW_S * ROWS).toBe(HISTORY_S)
  })

  it('draws only a noise floor with no reports', () => {
    const m = new RfModel()
    advance(m, 0, 3)
    for (let band = 0; band < 5; band++) expect(windowMax(m.ring, band)).toBeLessThan(40)
    expect(Math.max(...m.spectrum)).toBeLessThan(-90)
  })

  it('puts a fixed link in its band window only, at the reported level', () => {
    const m = new RfModel()
    m.advanceTo(0)
    m.ingest(rfEmissionOf(rf({ band: '5.8 GHz', hopping: false, rssi_dbm: -60 }), 0.1)!)
    advance(m, 0, 1)
    expect(windowMax(m.ring, 4, 1)).toBeGreaterThan(150)
    for (const other of [0, 1, 2, 3]) expect(windowMax(m.ring, other, 1)).toBeLessThan(40)
    expect(Math.max(...m.spectrum.slice(4 * BINS_PER_BAND))).toBeCloseTo(-60, 0)
    // narrow: a fixed carrier is a few bins wide
    expect(lit(m.ring, 4 * BINS_PER_BAND, 5 * BINS_PER_BAND, 1, 100)).toBeLessThanOrEqual(5)
  })

  it('a stronger report is drawn brighter than a weaker one', () => {
    const level = (rssi: number) => {
      const m = new RfModel()
      m.advanceTo(0)
      m.ingest(rfEmissionOf(rf({ band: '2.4 GHz', hopping: false, rssi_dbm: rssi }), 0.1)!)
      advance(m, 0, 1)
      return windowMax(m.ring, 3, 1)
    }
    expect(level(-55)).toBeGreaterThan(level(-75))
    expect(level(-75)).toBeGreaterThan(level(-92))
  })

  it('smears a hopping link across its window; the peak trace keeps what was hit', () => {
    const fixed = new RfModel()
    const hop = new RfModel()
    fixed.advanceTo(0)
    hop.advanceTo(0)
    fixed.ingest(rfEmissionOf(rf({ band: '2.4 GHz', hopping: false, rssi_dbm: -65 }), 0.1)!)
    hop.ingest(
      rfEmissionOf(rf({ band: '2.4 GHz', hopping: true, hop_rate_hz: 80, rssi_dbm: -65 }), 0.1)!,
    )
    advance(fixed, 0, 1)
    advance(hop, 0, 1)
    const from = 3 * BINS_PER_BAND
    const to = 4 * BINS_PER_BAND
    expect(lit(hop.ring, from, to, 1)).toBeGreaterThan(lit(fixed.ring, from, to, 1) + 3)
    const held = [...hop.peak.slice(from, to)].filter((v) => v > -80).length
    expect(held).toBeGreaterThan(8)
  })

  it('steps a slow hopper from one position to another between rows', () => {
    const m = new RfModel()
    m.advanceTo(0)
    m.ingest(
      rfEmissionOf(rf({ band: '900 MHz', hopping: true, hop_rate_hz: 1, rssi_dbm: -62 }), 0)!,
    )
    advance(m, 0, 1.2)
    const peaks = new Set<number>()
    for (let age = 0; age < m.ring.count; age++) {
      let best = 0
      let at = -1
      for (let b = BINS_PER_BAND; b < 2 * BINS_PER_BAND; b++)
        if (m.ring.at(age, b) > best) {
          best = m.ring.at(age, b)
          at = b
        }
      if (best > 100) peaks.add(at)
    }
    expect(peaks.size).toBeGreaterThanOrEqual(1)
    // the first second sits on hop 0 and the next on hop 1: different positions
    const a = hopBin(1, 90, 0)
    const b = hopBin(1, 90, 1)
    expect(a).not.toBe(b)
  })

  it('stops painting a report after it is held for 1.25 s', () => {
    const m = new RfModel()
    m.advanceTo(0)
    m.ingest(rfEmissionOf(rf({ band: '433 MHz', hopping: false, rssi_dbm: -60 }), 0.1)!)
    advance(m, 0, 3)
    expect(windowMax(m.ring, 0, 8)).toBeGreaterThan(150) // about 1 s after
    expect(windowMax(m.ring, 0, 0)).toBeLessThan(40) // 3 s after
  })

  it('ignores a report in a band the display has no window for', () => {
    const m = new RfModel()
    m.advanceTo(0)
    m.ingest(rfEmissionOf(rf({ band: '60 GHz', hopping: false, rssi_dbm: -40 }), 0.1)!)
    advance(m, 0, 1)
    for (let band = 0; band < 5; band++) expect(windowMax(m.ring, band, 1)).toBeLessThan(40)
  })

  it('is deterministic: the same reports give the same bytes', () => {
    const run = () => {
      const m = new RfModel()
      m.advanceTo(0)
      m.ingest(
        rfEmissionOf(
          rf({ band: '2.4 GHz', hopping: true, hop_rate_hz: 41.6, rssi_dbm: -70 }),
          0.2,
        )!,
      )
      advance(m, 0, 4)
      return Array.from(m.ring.data)
    }
    expect(run()).toEqual(run())
  })

  it('does not grow after construction', () => {
    const m = new RfModel()
    const sizes = [m.ring.data.length, m.spectrum.length, m.peak.length]
    m.advanceTo(0)
    for (let i = 0; i < 200; i++) {
      m.ingest(
        rfEmissionOf(
          rf({ band: '2.4 GHz', hopping: true, hop_rate_hz: 400, rssi_dbm: -70 }),
          i * 0.5,
        )!,
      )
      m.advanceTo(i * 0.5)
    }
    expect([m.ring.data.length, m.spectrum.length, m.peak.length]).toEqual(sizes)
    expect(m.ring.count).toBe(ROWS)
  })

  it('skips ahead rather than writing a minute of rows after a long gap', () => {
    const m = new RfModel()
    m.advanceTo(0)
    m.advanceTo(500)
    expect(m.ring.version).toBeLessThanOrEqual(ROWS + 1)
  })
})

describe('acoustic synthesis', () => {
  const run = (f: Record<string, number | boolean>) => {
    const m = new AcousticModel()
    m.advanceTo(0)
    m.ingest(acousticEmissionOf(ac(f), 0.1)!)
    for (let t = 0; t <= 1.5; t += 0.05) m.advanceTo(t)
    return m
  }
  const peaksAt = (m: AcousticModel, age = 1, over = 30): number[] => {
    const out: number[] = []
    for (let b = 0; b < AC_BINS; b++) {
      const v = m.ring.at(age, b)
      if (v > over && v >= m.ring.at(age, b - 1) && v >= m.ring.at(age, b + 1)) out.push(b)
    }
    return out
  }

  it('draws the fundamental and k x fundamental up to the reported harmonic count', () => {
    const m = run({ blade_pass_hz: 200, harmonics: 4, tonal: true, snr_db: 30 })
    expect(peaksAt(m).map((b) => b * AC_BIN_HZ)).toEqual([200, 400, 600, 800])
  })

  it('makes higher harmonics weaker, and a stronger SNR brighter', () => {
    const m = run({ blade_pass_hz: 200, harmonics: 3, tonal: true, snr_db: 30 })
    const bytes = [200, 400, 600].map((hz) => m.ring.at(1, hz / AC_BIN_HZ))
    expect(bytes[0]).toBeGreaterThan(bytes[1]!)
    expect(bytes[1]).toBeGreaterThan(bytes[2]!)
    const weak = run({ blade_pass_hz: 200, harmonics: 3, tonal: true, snr_db: 15 })
    expect(weak.ring.at(1, 40)).toBeLessThan(m.ring.at(1, 40))
  })

  it('stays on the 0 to 2 kHz scale and draws a wing-beat fundamental near the bottom', () => {
    const m = run({ blade_pass_hz: 900, harmonics: 8, tonal: true, snr_db: 40 })
    expect(peaksAt(m).map((b) => b * AC_BIN_HZ)).toEqual([900, 1800])
    expect(AC_MAX_HZ / AC_BIN_HZ).toBe(AC_BINS)
    const bird = run({ blade_pass_hz: 12, harmonics: 3, tonal: false, snr_db: 25 })
    expect(bird.ring.at(1, 2)).toBeGreaterThan(100)
  })

  it('shows only the noise floor with no report', () => {
    const m = new AcousticModel()
    for (let t = 0; t <= 2; t += 0.05) m.advanceTo(t)
    expect(peaksAt(m, 0, 30)).toEqual([])
  })
})

describe('cursor maths', () => {
  it('moves one step or one coarse step, snapped and clamped to the scale', () => {
    expect(moveCursor(200, 1, false)).toBe(205)
    expect(moveCursor(200, -1, false)).toBe(195)
    expect(moveCursor(200, 1, true)).toBe(250)
    expect(moveCursor(0, -1, false)).toBe(0)
    expect(moveCursor(2000, 1, true)).toBe(2000)
    expect(moveCursor(203, 1, false)).toBe(210)
  })

  it('finds the nearest harmonic order and the implied blade-pass rate', () => {
    const lines = [{ fundamentalHz: 100, harmonics: 5 }]
    const n = nearestHarmonic(310, lines)!
    expect(n.order).toBe(3)
    expect(n.lineHz).toBe(300)
    expect(n.deltaHz).toBe(10)
    expect(n.impliedBladePassHz).toBeCloseTo(310 / 3)
  })

  it('caps the order at the reported harmonic count and at the scale', () => {
    expect(nearestHarmonic(900, [{ fundamentalHz: 100, harmonics: 3 }])!.order).toBe(3)
    expect(nearestHarmonic(2000, [{ fundamentalHz: 900, harmonics: 9 }])!.order).toBe(2)
    expect(nearestHarmonic(50, [{ fundamentalHz: 100, harmonics: 3 }])!.order).toBe(1)
  })

  it('picks the closest line over several reports, the stronger on a tie, and none at 0 Hz', () => {
    const lines = [
      { fundamentalHz: 100, harmonics: 4, snrDb: 10 },
      { fundamentalHz: 130, harmonics: 4, snrDb: 20 },
    ]
    expect(nearestHarmonic(262, lines)!.line).toBe(1)
    expect(nearestHarmonic(100, lines)!.line).toBe(0)
    const tie = [
      { fundamentalHz: 100, harmonics: 2, snrDb: 5 },
      { fundamentalHz: 100, harmonics: 2, snrDb: 12 },
    ]
    expect(nearestHarmonic(200, tie)!.line).toBe(1)
    expect(nearestHarmonic(0, lines)).toBeNull()
    expect(nearestHarmonic(150, [])).toBeNull()
  })
})

describe('colour map and layouts', () => {
  it('runs from near black to pale yellow and brightens', () => {
    expect([INFERNO_LUT[0], INFERNO_LUT[1], INFERNO_LUT[2]]).toEqual([0, 0, 4])
    expect([INFERNO_LUT[765], INFERNO_LUT[766], INFERNO_LUT[767]]).toEqual([252, 255, 164])
    const luma = (i: number) =>
      0.2126 * INFERNO_LUT[i * 3]! +
      0.7152 * INFERNO_LUT[i * 3 + 1]! +
      0.0722 * INFERNO_LUT[i * 3 + 2]!
    for (let i = 1; i < 256; i++) expect(luma(i)).toBeGreaterThanOrEqual(luma(i - 1) - 0.01)
  })

  it('lays the RF plots inside the canvas without overlap, down to a small canvas', () => {
    for (const [w, h] of [
      [800, 300],
      [353, 131],
      [200, 80],
    ] as const) {
      const l = rfLayout(w, h)
      for (const r of [l.spectrum, l.waterfall]) {
        expect(r.w).toBeGreaterThan(0)
        expect(r.h).toBeGreaterThan(0)
        expect(r.x).toBeGreaterThanOrEqual(0)
      }
      expect(l.waterfall.y).toBeGreaterThanOrEqual(l.spectrum.y + l.spectrum.h)
      expect(l.spectrum.x + l.spectrum.w).toBeLessThanOrEqual(w)
    }
    const a = acousticLayout(353, 131)
    expect(a.plot.w).toBeGreaterThan(0)
    expect(a.plot.h).toBeGreaterThan(0)
  })
})

describe('console feed', () => {
  const push = (
    store: LiveStore,
    tick: number,
    reports: Report[],
    sensors = ['rf', 'acoustic'],
  ) => {
    const f = frame({ tick, time_s: tick / 20, reports })
    f.sensors = [
      ...f.sensors,
      ...sensors.map((m) => ({
        id: `${m}-1`,
        modality: m as 'rf' | 'acoustic',
        position: { x: 0, y: 0, z: 0 },
        bearing_deg: 0,
        elevation_deg: 0,
        fov_deg: null,
        cued: false,
        supports_cue: false,
        outage: false,
        data_status: 'reference' as const,
      })),
    ]
    store.dispatch({ type: 'message', message: f, at: tick * 50 })
  }

  it('feeds reports to the models, advances them with scenario time and lists the latest', () => {
    const store = new LiveStore()
    const feed = new ConsoleFeed(store)
    feed.attach()
    const seen: number[] = []
    feed.subscribe(() => seen.push(feed.version))
    push(store, 0, [])
    push(store, 20, [
      rf({ band: '2.4 GHz', hopping: false, rssi_dbm: -70 }),
      ac({ blade_pass_hz: 190, harmonics: 3, tonal: true, snr_db: 20 }),
    ])
    push(store, 40, [])
    expect(feed.rfSensor && feed.acousticSensor).toBe(true)
    expect(feed.rf.ring.count).toBe(8)
    expect(feed.acoustic.ring.count).toBe(8)
    expect(feed.rfRecent).toHaveLength(1)
    expect(feed.acousticRecent[0]?.fundamentalHz).toBe(190)
    expect(seen.length).toBeGreaterThan(0)
    feed.detach()
    push(store, 60, [])
    expect(feed.rf.ring.count).toBe(8)
  })

  it('lets reports age out of the list and caps its length', () => {
    const store = new LiveStore()
    const feed = new ConsoleFeed(store)
    feed.attach()
    push(store, 0, [])
    const many = Array.from({ length: RECENT_MAX + 4 }, () =>
      rf({ band: '900 MHz', hopping: false, rssi_dbm: -80 }),
    )
    push(store, 20, many)
    expect(feed.rfRecent).toHaveLength(RECENT_MAX)
    push(store, 20 + Math.round((RECENT_S + 1) * 20), [])
    expect(feed.rfRecent).toHaveLength(0)
  })

  it('does not draw a console for a modality the frame has no sensor for', () => {
    const store = new LiveStore()
    const feed = new ConsoleFeed(store)
    feed.attach()
    push(store, 0, [], [])
    push(store, 40, [], [])
    expect(feed.rfSensor).toBe(false)
    expect(feed.rf.ring.count).toBe(0)
  })

  it('ignores a repeated tick', () => {
    const store = new LiveStore()
    const feed = new ConsoleFeed(store)
    feed.attach()
    push(store, 0, [])
    push(store, 20, [rf({ band: '2.4 GHz', hopping: false, rssi_dbm: -70 })])
    push(store, 20, [rf({ band: '2.4 GHz', hopping: false, rssi_dbm: -70 })])
    expect(feed.rfRecent).toHaveLength(1)
  })
})
