import { describe, expect, it } from 'vitest'
import {
  BIRDS,
  BenchRunner,
  GATE,
  PHASES,
  SWARM,
  benchReports,
  cameraBearing,
  evaluateGate,
  summarise,
  type BenchHooks,
  type PhaseResult,
  type PhaseSpec,
} from '../../src/bench/plan'
import { FrameStats, type Tier } from '../../src/live/quality'

function result(id: PhaseResult['id'], fpsMedian: number, fps5th: number): PhaseResult {
  return {
    id,
    mode: 'thermal-white-hot',
    tier: 'high',
    frames: 100,
    durationMs: 1000,
    fpsMedian,
    fps5th,
    fpsMean: fpsMedian,
    p50Ms: 1000 / fpsMedian,
    p95Ms: 1000 / fps5th,
    p99Ms: 40,
    maxMs: 60,
    slowFrames: 0,
    interruptions: 0,
  }
}

describe('the gate', () => {
  it('passes on the high tier alone', () => {
    const g = evaluateGate([result('high', 60, 45), result('auto', 20, 10)])
    expect(g).toEqual({ fixedHigh: true, autoHolds: false, pass: true })
  })

  it('passes when auto holds 30 fps even if the high tier does not', () => {
    const g = evaluateGate([result('high', 22, 15), result('auto', 40, 31)])
    expect(g).toEqual({ fixedHigh: false, autoHolds: true, pass: true })
  })

  it('fails when neither does, at the exact edges', () => {
    expect(evaluateGate([result('high', 44.9, 40), result('auto', 29.9, 29)]).pass).toBe(false)
    expect(
      evaluateGate([result('high', GATE.medianFps, GATE.fps5th), result('auto', 1, 1)]).pass,
    ).toBe(true)
    expect(evaluateGate([result('high', 60, 29.9), result('auto', 29.9, 40)]).pass).toBe(false)
  })

  it('is undecided when a phase was not measured', () => {
    expect(evaluateGate([result('high', 60, 45)])).toEqual({
      fixedHigh: true,
      autoHolds: null,
      pass: null,
    })
    expect(evaluateGate([]).pass).toBeNull()
  })
})

describe('summarise', () => {
  it('reports median and 5th-percentile fps from frame times', () => {
    const stats = new FrameStats()
    for (let i = 0; i < 95; i++) stats.push(16.67)
    for (let i = 0; i < 5; i++) stats.push(40)
    const r = summarise({ id: 'high', mode: 'day' }, 'medium', stats, 5000.4)
    expect(r.fpsMedian).toBeCloseTo(60, 0)
    expect(r.fps5th).toBeCloseTo(60, 0) // 95th percentile frame time is still 16.67 ms
    expect(r.maxMs).toBe(40)
    expect(r).toMatchObject({ frames: 100, tier: 'medium', id: 'high', durationMs: 5000 })
  })
})

describe('the reference scene', () => {
  it('has the swarm and the birds, with unique keys, identical for the same time', () => {
    const a = benchReports(12.5, 1000)
    expect(a).toHaveLength(SWARM + BIRDS)
    expect(new Set(a.map((r) => r.key)).size).toBe(a.length)
    expect(a.filter((r) => r.shape === 'bird')).toHaveLength(BIRDS)
    expect(benchReports(12.5, 1000)).toEqual(a)
    expect(benchReports(13, 1000)).not.toEqual(a)
  })

  it('stays within the picture as the camera pans', () => {
    for (const t of [0, 7, 31, 59.9]) {
      const bearing = cameraBearing(t)
      for (const r of benchReports(t, 0)) {
        const d = Math.abs(((r.azimuthDeg - bearing + 540) % 360) - 180)
        expect(d).toBeLessThan(20) // the camera's field of view is 40 degrees wide
        expect(r.elevationDeg).toBeGreaterThan(0)
        expect(r.elevationDeg).toBeLessThan(20)
      }
    }
  })

  it('pans at a constant rate and wraps', () => {
    expect(cameraBearing(0)).toBe(0)
    expect(cameraBearing(10)).toBe(60)
    expect(cameraBearing(61)).toBeCloseTo(6, 6)
  })
})

describe('BenchRunner', () => {
  function rig(frameMs: (phase: string) => number) {
    const log: string[] = []
    let tier: Tier = 'high'
    let phase = ''
    const hooks: BenchHooks = {
      begin: (spec: PhaseSpec) => {
        phase = spec.id
        tier = spec.tier ?? 'high'
        log.push(`begin ${spec.id}`)
      },
      draw: () => log.push('draw'),
      autoFrame: () => {
        log.push('auto')
        return null
      },
      tier: () => tier,
    }
    const runner = new BenchRunner(hooks, [
      { id: 'high', tier: 'high', mode: 'thermal-white-hot', warmupMs: 100, measureMs: 1000 },
      { id: 'auto', tier: null, mode: 'thermal-white-hot', warmupMs: 100, measureMs: 1000 },
    ])
    let now = 5000
    let state = runner.step(now)
    let guard = 0
    while (state.status === 'running' && guard++ < 10_000) {
      now += frameMs(phase)
      state = runner.step(now)
    }
    return { state, log }
  }

  it('runs each phase, warms up before measuring, and ends with a result per phase', () => {
    const { state, log } = rig((phase) => (phase === 'high' ? 10 : 25))
    expect(state.status).toBe('done')
    if (state.status !== 'done') return
    expect(state.phases.map((p) => p.id)).toEqual(['high', 'auto'])
    const [high, auto] = state.phases
    expect(high?.fpsMedian).toBeCloseTo(100, 0)
    expect(auto?.fpsMedian).toBeCloseTo(40, 0)
    // The warm-up frames are drawn but not counted: 1000 ms at 10 ms is 100 frames.
    expect(high?.frames).toBeGreaterThanOrEqual(99)
    expect(high?.frames).toBeLessThanOrEqual(101)
    expect(log.filter((l) => l === 'begin high')).toHaveLength(1)
    expect(log.filter((l) => l === 'auto').length).toBeGreaterThan(40) // fed only in the auto phase
    expect(log.indexOf('auto')).toBeGreaterThan(log.indexOf('begin auto'))
  })

  function runWith(times: number[], interrupted?: () => boolean, measureMs = 500): PhaseResult {
    const hooks: BenchHooks = {
      begin: () => undefined,
      draw: () => undefined,
      autoFrame: () => null,
      tier: () => 'high',
      interrupted,
    }
    const runner = new BenchRunner(hooks, [
      { id: 'high', tier: 'high', mode: 'day', warmupMs: 0, measureMs },
    ])
    for (const t of times) {
      const s = runner.step(t)
      if (s.status === 'done') return s.phases[0] as PhaseResult
    }
    throw new Error('the run did not finish')
  }

  it('counts a slow frame instead of dropping it (Q-28: software rendering, 2 s a frame)', () => {
    // Every interval is over a second: the old one-second filter recorded zero frames here.
    const r = runWith([0, 2000, 4000, 6000], undefined, 5000)
    expect(r.frames).toBe(3)
    expect(r.slowFrames).toBe(3)
    expect(r.interruptions).toBe(0)
    expect(r.fpsMedian).toBeCloseTo(0.5, 2)
    expect(r.maxMs).toBe(2000)
  })

  it('leaves out the interval across a hidden tab, as the page reports it', () => {
    let hidden = false
    const times = [0, 16, 32, 5032, 5048, 5064, 5600]
    let i = 0
    const r = runWith(times, () => {
      i++
      // The page reports one pause, on the frame that follows the 5 s gap (the fourth step).
      const was = i === 4 && !hidden
      if (was) hidden = true
      return was
    })
    expect(r.interruptions).toBe(1)
    expect(r.maxMs).toBeLessThan(1000)
    expect(r.slowFrames).toBe(0)
  })

  it('treats an interval over a minute with no known cause as an interruption', () => {
    const r = runWith([0, 16, 32, 90_000, 90_016, 90_600])
    expect(r.interruptions).toBe(1)
    expect(r.maxMs).toBeLessThan(1000)
  })

  it('has the five documented phases', () => {
    expect(PHASES.map((p) => p.id)).toEqual(['high', 'medium', 'low', 'auto', 'high-day'])
  })
})
