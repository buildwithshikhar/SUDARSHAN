import { describe, expect, it } from 'vitest'
import {
  angularSizeDeg,
  directionThree,
  EO_PIXELS_H,
  extrapolate,
  lerpAngleDeg,
  pixelAngleDeg,
  polarFrom,
  ppiProject,
  ppiProjectEnu,
  ppiUnproject,
  ringStepM,
  skyColours,
  sweepBearingDeg,
  sweepPassed,
  verticalFovDeg,
  wrap180,
  wrap360,
  type PpiFrame,
} from '../../src/live/geometry'
import { ladderPosition, tickStepDeg, timeCode } from '../../src/live/views/EoHud'
import { buildRings } from '../../src/live/views/ppiDraw'
import { ppiRangeMax } from '../../src/live/views/PpiView'
import { welcome } from './helpers'

const frame: PpiFrame = { cx: 200, cy: 200, radiusPx: 100, rangeMaxM: 4000 }

describe('bearings', () => {
  it('wraps angles', () => {
    expect(wrap360(-10)).toBe(350)
    expect(wrap360(370)).toBe(10)
    expect(wrap180(190)).toBe(-170)
    expect(lerpAngleDeg(350, 10, 0.5)).toBeCloseTo(0)
    expect(lerpAngleDeg(10, 350, 0.25)).toBeCloseTo(5)
  })

  it('measures bearing, ground range, slant range and elevation from a point', () => {
    const p = polarFrom({ x: 0, y: 0, z: 10 }, { x: 300, y: 400, z: 10 + 500 })
    expect(p.bearingDeg).toBeCloseTo(36.87, 2)
    expect(p.rangeM).toBeCloseTo(500)
    expect(p.slantM).toBeCloseTo(707.1, 1)
    expect(p.elevationDeg).toBeCloseTo(45)
    expect(polarFrom({ x: 0, y: 0, z: 0 }, { x: -1, y: 0, z: 0 }).bearingDeg).toBeCloseTo(270)
  })

  it('carries a position along a velocity for at most the cap', () => {
    const v = { x: 10, y: 0, z: -2 }
    expect(extrapolate({ x: 0, y: 0, z: 100 }, v, 0.1)).toEqual({ x: 1, y: 0, z: 99.8 })
    expect(extrapolate({ x: 0, y: 0, z: 0 }, v, 5).x).toBeCloseTo(2.5)
    expect(extrapolate({ x: 0, y: 0, z: 0 }, v, -1).x).toBe(0)
  })
})

describe('PPI geometry', () => {
  it('puts north up, east right, and range on a linear scale', () => {
    expect(ppiProject(0, 2000, frame)).toEqual({ x: 200, y: 150 })
    const east = ppiProject(90, 4000, frame)
    expect(east.x).toBeCloseTo(300)
    expect(east.y).toBeCloseTo(200)
    const south = ppiProject(180, 1000, frame)
    expect(south.x).toBeCloseTo(200)
    expect(south.y).toBeCloseTo(225)
    expect(ppiProject(270, 0, frame)).toEqual({ x: 200, y: 200 })
  })

  it('maps pixels back to bearing and range', () => {
    for (const [bearing, range] of [
      [0, 1000],
      [45, 2500],
      [135, 3999],
      [225, 100],
      [314, 3000],
    ] as const) {
      const p = ppiProject(bearing, range, frame)
      const back = ppiUnproject(p.x, p.y, frame)
      expect(back.bearingDeg).toBeCloseTo(bearing, 6)
      expect(back.rangeM).toBeCloseTo(range, 6)
    }
  })

  it('projects a position relative to the radar, not the site', () => {
    const radar = { x: -140, y: 85, z: 6 }
    const p = ppiProjectEnu(radar, { x: -140, y: 2085, z: 50 }, frame)
    expect(p.x).toBeCloseTo(200)
    expect(p.y).toBeCloseTo(150)
  })

  it('sizes the scope to the outer zone plus a quarter, in 500 m steps', () => {
    expect(ppiRangeMax(welcome().briefing)).toBe(4000)
  })

  it('draws 1-2-5 range rings, labelled in km', () => {
    expect(ringStepM(4000)).toBe(1000)
    expect(ringStepM(10000)).toBe(2000)
    expect(ringStepM(1200)).toBe(200)
    expect(buildRings(frame).map((r) => r.label)).toEqual(['1', '2', '3', '4'])
    expect(buildRings(frame)[3]!.radiusPx).toBeCloseTo(100)
  })

  it('turns the sweep once per period, clockwise from north', () => {
    expect(sweepBearingDeg(0, 1.2)).toBe(0)
    expect(sweepBearingDeg(0.3, 1.2)).toBeCloseTo(90)
    expect(sweepBearingDeg(1.2, 1.2)).toBeCloseTo(0)
    expect(sweepBearingDeg(1.5, 1.2)).toBeCloseTo(90)
  })

  it('knows when the beam has passed a bearing, across north too', () => {
    expect(sweepPassed(80, 100, 90)).toBe(true)
    expect(sweepPassed(80, 100, 100)).toBe(true)
    expect(sweepPassed(80, 100, 80)).toBe(false)
    expect(sweepPassed(80, 100, 120)).toBe(false)
    expect(sweepPassed(350, 10, 355)).toBe(true)
    expect(sweepPassed(350, 10, 5)).toBe(true)
    expect(sweepPassed(350, 10, 180)).toBe(false)
    expect(sweepPassed(50, 50, 50)).toBe(false)
  })
})

describe('EO geometry', () => {
  it('has no range: angular size is apparent pixels times the pixel angle', () => {
    expect(EO_PIXELS_H).toBe(1920)
    expect(pixelAngleDeg(24)).toBeCloseTo(0.0125)
    expect(angularSizeDeg(16, 24)).toBeCloseTo(0.2)
    expect(angularSizeDeg(16, 4.8)).toBeCloseTo(0.04)
    // zooming in by 5 makes the same pixel count a fifth of the angle
    expect(angularSizeDeg(10, 24) / angularSizeDeg(10, 4.8)).toBeCloseTo(5)
  })

  it('points three.js vectors by compass bearing and elevation', () => {
    const [x0, y0, z0] = directionThree(0, 0)
    expect([x0, y0].map((n) => Math.round(n * 1e6) / 1e6)).toEqual([0, 0])
    expect(z0).toBeCloseTo(-1)
    const east = directionThree(90, 0)
    expect(east[0]).toBeCloseTo(1)
    expect(east[2]).toBeCloseTo(0)
    expect(directionThree(0, 90)[1]).toBeCloseTo(1)
    const v = directionThree(137, 23)
    expect(Math.hypot(...v)).toBeCloseTo(1)
  })

  it('derives the vertical field from the horizontal one and the aspect', () => {
    expect(verticalFovDeg(90, 1)).toBeCloseTo(90)
    expect(verticalFovDeg(24, 16 / 9)).toBeCloseTo(13.64, 2)
  })

  it('lays the zoom ladder out on a log scale, widest at the top', () => {
    expect(ladderPosition(48)).toBe(0)
    expect(ladderPosition(1)).toBe(1)
    expect(ladderPosition(24)).toBeLessThan(ladderPosition(12))
    expect(ladderPosition(100)).toBe(0)
    expect(ladderPosition(0.2)).toBe(1)
  })

  it('picks reticle tick spacing near 70 px and writes a time code', () => {
    expect(tickStepDeg(1920 / 24)).toBeGreaterThanOrEqual(1)
    expect(tickStepDeg(1920 / 4.3) * (1920 / 4.3)).toBeGreaterThanOrEqual(70)
    expect(timeCode(83.456)).toBe('T+01:23.46')
    expect(timeCode(0)).toBe('T+00:00.00')
  })

  it('makes a bright day sky and a dark night sky', () => {
    const noon = skyColours(12)
    const night = skyColours(0)
    expect(noon.zenith[2]).toBeGreaterThan(night.zenith[2])
    expect(noon.horizon[0]).toBeGreaterThan(night.horizon[0])
    for (const c of [...noon.zenith, ...noon.horizon, ...night.zenith, ...night.horizon]) {
      expect(c).toBeGreaterThanOrEqual(0)
      expect(c).toBeLessThanOrEqual(1)
    }
  })
})
