import { describe, expect, it } from 'vitest'
import {
  availableModes,
  easeRange,
  gainPercent,
  lumaRange,
  nvGain,
  pickEoSensor,
  resolveMode,
  reticleInk,
  surfaceTemperature,
  type ThermalClass,
} from '../../src/live/views/eoMode'
import {
  BREEZE,
  fogDensity,
  fogShape,
  rainIntensity,
  swayStrength,
  windOf,
} from '../../src/live/views/eoWeather'
import { celestial, lighting } from '../../src/live/views/sky'

describe('mode availability', () => {
  it('offers both polarities for a thermal camera, by modality or by profile', () => {
    expect(availableModes({ modality: 'ir', profile: 'ir-generic-thermal' })).toEqual([
      'thermal-white-hot',
      'thermal-black-hot',
    ])
    expect(availableModes({ modality: 'eo', profile: 'something-thermal' })).toEqual([
      'thermal-white-hot',
      'thermal-black-hot',
    ])
  })

  it('offers night vision only for a night-vision profile', () => {
    expect(availableModes({ modality: 'eo', profile: 'eo-generic-nv' })).toEqual(['night-vision'])
    expect(availableModes({ modality: 'eo', profile: 'eo-night-generic' })).toEqual([
      'night-vision',
    ])
  })

  it('offers the daylight picture only for a day camera, and as the default for unknowns', () => {
    expect(availableModes({ modality: 'eo', profile: 'eo-generic-day' })).toEqual(['day'])
    expect(availableModes({ modality: 'eo', profile: 'eo-day-generic' })).toEqual(['day'])
    expect(availableModes(null)).toEqual(['day'])
    expect(availableModes({ modality: 'eo' })).toEqual(['day'])
    // "nv" inside a word is not a night-vision camera
    expect(availableModes({ modality: 'eo', profile: 'env-camera' })).toEqual(['day'])
  })

  it('resolves a wanted mode only if the sensor supports it', () => {
    const thermal = availableModes({ modality: 'ir' })
    expect(resolveMode('thermal-black-hot', thermal)).toBe('thermal-black-hot')
    expect(resolveMode('night-vision', thermal)).toBe('thermal-white-hot')
    expect(resolveMode(null, thermal)).toBe('thermal-white-hot')
    expect(resolveMode('day', [])).toBe('day')
  })

  it('shows the optical sensor, visible band first', () => {
    const sensors = [
      { id: 'radar-1', modality: 'radar' },
      { id: 'ir-1', modality: 'ir' },
      { id: 'eo-1', modality: 'eo' },
    ]
    expect(pickEoSensor(sensors)?.id).toBe('eo-1')
    expect(pickEoSensor(sensors.filter((s) => s.id !== 'eo-1'))?.id).toBe('ir-1')
    expect(pickEoSensor([{ id: 'radar-1', modality: 'radar' }])).toBeNull()
  })
})

describe('thermal temperature model', () => {
  const classes: ThermalClass[] = [
    'terrain',
    'building',
    'vegetation',
    'water',
    'sky',
    'target',
    'metal',
  ]

  it('stays in 0..1 for every class at every hour', () => {
    for (const cls of classes) {
      for (let h = 0; h < 24; h += 0.5) {
        for (const cloud of [0, 50, 100]) {
          const t = surfaceTemperature(cls, h, cloud)
          expect(t).toBeGreaterThanOrEqual(0)
          expect(t).toBeLessThanOrEqual(1)
        }
      }
    }
  })

  it('heats the ground in the afternoon and cools it before dawn', () => {
    expect(surfaceTemperature('terrain', 14.5)).toBeGreaterThan(surfaceTemperature('terrain', 5))
    expect(surfaceTemperature('terrain', 14.5)).toBeGreaterThan(
      surfaceTemperature('terrain', 2.5) + 0.3,
    )
  })

  it('orders the classes: sky coldest, target hottest, vegetation cooler than buildings', () => {
    for (const h of [3, 9, 14.5, 21]) {
      const t = (c: ThermalClass) => surfaceTemperature(c, h)
      expect(t('sky')).toBeLessThan(t('vegetation'))
      expect(t('vegetation')).toBeLessThan(t('building'))
      expect(t('target')).toBeGreaterThan(t('building'))
      expect(t('target')).toBeGreaterThan(t('terrain'))
    }
    // buildings hold the day's heat after dusk better than bare ground
    expect(surfaceTemperature('building', 22)).toBeGreaterThan(surfaceTemperature('terrain', 22))
  })

  it('warms the sky and damps the ground swing under cloud', () => {
    expect(surfaceTemperature('sky', 12, 100)).toBeGreaterThan(surfaceTemperature('sky', 12, 0))
    const swing = (cloud: number) =>
      surfaceTemperature('terrain', 14.5, cloud) - surfaceTemperature('terrain', 2.5, cloud)
    expect(swing(100)).toBeLessThan(swing(0))
  })
})

describe('automatic gain', () => {
  /** An RGBA image whose red channel holds the given sqrt-encoded luminance values. */
  const image = (values: number[]) => {
    const out = new Uint8Array(values.length * 4)
    values.forEach((v, i) => (out[i * 4] = Math.round(Math.sqrt(v) * 255)))
    return out
  }

  it('finds the percentile range of a scene', () => {
    const values = Array.from({ length: 1000 }, (_, i) => 0.2 + (0.4 * i) / 999)
    const r = lumaRange(image(values))
    expect(r.lo).toBeGreaterThan(0.19)
    expect(r.lo).toBeLessThan(0.23)
    expect(r.hi).toBeGreaterThan(0.57)
    expect(r.hi).toBeLessThan(0.62)
    expect(r.mean).toBeCloseTo(0.4, 1)
  })

  it('ignores a few outlier pixels, as a percentile should', () => {
    const values = [
      ...Array.from({ length: 990 }, () => 0.3),
      ...Array.from({ length: 10 }, () => 1),
    ]
    const r = lumaRange(image(values))
    expect(r.hi).toBeLessThan(0.35)
  })

  it('keeps a minimum span on a flat scene so noise is not stretched to full contrast', () => {
    const r = lumaRange(image(Array.from({ length: 64 }, () => 0.25)))
    expect(r.hi - r.lo).toBeGreaterThanOrEqual(0.0599)
  })

  it('handles an empty sample', () => {
    expect(lumaRange(new Uint8Array(0))).toEqual({ lo: 0, hi: 1, mean: 0.5 })
  })

  it('eases towards a new range without jumping', () => {
    const a = { lo: 0.1, hi: 0.5, mean: 0.3 }
    const b = { lo: 0.3, hi: 0.9, mean: 0.6 }
    const mid = easeRange(a, b, 0.25)
    expect(mid.lo).toBeCloseTo(0.15, 10)
    expect(mid.hi).toBeCloseTo(0.6, 10)
    expect(easeRange(a, b, 1)).toEqual(b)
  })

  it('reads a wide range as low gain and a narrow one as high gain', () => {
    expect(gainPercent({ lo: 0, hi: 1, mean: 0.5 })).toBe(0)
    expect(gainPercent({ lo: 0.4, hi: 0.5, mean: 0.45 })).toBe(90)
  })

  it('lifts a dark scene for night vision and eases off a bright one', () => {
    expect(nvGain(0.01)).toBeGreaterThan(nvGain(0.1))
    expect(nvGain(0.5)).toBeCloseTo(0.6, 5)
    expect(nvGain(0)).toBeLessThanOrEqual(16)
  })
})

describe('reticle ink', () => {
  it('inverts between white-hot and black-hot', () => {
    const w = reticleInk('thermal-white-hot')
    const b = reticleInk('thermal-black-hot')
    expect(w.stroke).toBe(b.halo)
    expect(w.halo).toBe(b.stroke)
  })

  it('uses theme tokens by day and bright phosphor green in night vision', () => {
    expect(reticleInk('day').stroke).toBe('var(--text)')
    expect(reticleInk('night-vision').stroke).toMatch(/^#[0-9a-f]{6}$/)
  })
})

describe('sun and moon', () => {
  it('puts the sun east at 06:00, high in the south at noon, west at 18:00', () => {
    const dawn = celestial(6).sunDir
    expect(dawn[0]).toBeCloseTo(1, 5)
    expect(dawn[1]).toBeCloseTo(0, 5)
    const noon = celestial(12).sunDir
    expect(noon[1]).toBeGreaterThan(0.9)
    const dusk = celestial(18).sunDir
    expect(dusk[0]).toBeCloseTo(-1, 5)
  })

  it('keeps the moon opposite the sun, and up at night', () => {
    for (const h of [0, 3, 9, 15, 21]) {
      const { sunDir, moonDir } = celestial(h)
      for (let k = 0; k < 3; k++) expect(sunDir[k]! + moonDir[k]!).toBeCloseTo(0, 10)
    }
    expect(celestial(0).moonDir[1]).toBeGreaterThan(0.5)
    expect(celestial(12).moonDir[1]).toBeLessThan(-0.5)
  })

  it('shows stars only in the dark, and fewer under cloud', () => {
    expect(celestial(12).stars).toBe(0)
    expect(celestial(0).stars).toBeCloseTo(1, 5)
    expect(celestial(0, 100).stars).toBeLessThan(0.2)
    expect(celestial(12).night).toBe(0)
    expect(celestial(0).night).toBe(1)
  })

  it('lights by day with the sun and at night with a dim cool moon', () => {
    const day = lighting(12)
    const night = lighting(0)
    expect(day.sunIntensity).toBeGreaterThan(night.sunIntensity * 10)
    expect(day.moonIntensity).toBe(0)
    expect(night.moonIntensity).toBeGreaterThan(0)
    // the moon is a dim fraction of the daytime sun
    expect(night.moonIntensity).toBeLessThan(day.sunIntensity / 3)
    expect(night.exposure).toBeGreaterThan(day.exposure)
    expect(lighting(12, 100).sunIntensity).toBeLessThan(day.sunIntensity)
    expect(lighting(17.5).sunWarmth).toBeGreaterThan(lighting(12).sunWarmth)
  })
})

describe('weather effects', () => {
  it('blows the wind towards the opposite of where it comes from', () => {
    const west = windOf({ wind_from_deg: 270, wind_speed_mps: 10 })
    expect(west.x).toBeCloseTo(10, 5)
    expect(west.z).toBeCloseTo(0, 5)
    const north = windOf({ wind_from_deg: 0, wind_speed_mps: 4 })
    // from the north: blowing south, which is +z in three.js axes
    expect(north.z).toBeCloseTo(4, 5)
    expect(north.speedMps).toBe(4)
  })

  it('falls back to a constant breeze when the briefing has no wind', () => {
    const w = windOf(undefined)
    expect(w.speedMps).toBe(BREEZE.speedMps)
    expect(Math.hypot(w.x, w.z)).toBeCloseTo(BREEZE.speedMps, 5)
  })

  it('maps visibility to exponential fog density and clamps silly values', () => {
    expect(fogDensity(10_000)).toBeCloseTo(Math.sqrt(-Math.log(0.02)) / 10_000, 10)
    expect(fogDensity(500)).toBeGreaterThan(fogDensity(5000))
    expect(fogDensity(0)).toBe(fogDensity(150))
    expect(fogDensity(undefined)).toBe(fogDensity(10_000))
  })

  it('rains only when the condition says rain, harder with less visibility', () => {
    expect(rainIntensity({ condition: 'clear' })).toBe(0)
    expect(rainIntensity(undefined)).toBe(0)
    expect(rainIntensity({ condition: 'rain', visibility_m: 9000 })).toBeGreaterThanOrEqual(0.35)
    expect(rainIntensity({ condition: 'rain', visibility_m: 1500 })).toBeGreaterThan(
      rainIntensity({ condition: 'rain', visibility_m: 8000 }),
    )
    expect(rainIntensity({ condition: 'rain', visibility_m: 0 })).toBeLessThanOrEqual(1)
  })

  it('sways trees more in stronger wind, but never none', () => {
    expect(swayStrength(0)).toBeGreaterThan(0)
    expect(swayStrength(8)).toBeGreaterThan(swayStrength(2))
    expect(swayStrength(40)).toBe(1)
  })

  it('makes fog hug the ground more than clear air', () => {
    expect(fogShape({ condition: 'fog' }).groundBoost).toBeGreaterThan(
      fogShape({ condition: 'clear' }).groundBoost,
    )
    expect(fogShape({ condition: 'dust' }).tint).toBeGreaterThan(0)
  })
})
