import { describe, expect, it } from 'vitest'
import {
  FrameStats,
  percentileOf,
  pickTier,
  stepDown,
  stepUp,
  TierController,
  TIERS,
  type TierEvent,
} from '../../src/live/quality'
import { QUALITY_KEY, QualityStore } from '../../src/live/qualityStore'

/** Feed a constant frame time for `seconds`, returning every tier event and the final clock. */
function run(
  controller: TierController,
  start: number,
  seconds: number,
  frameMs: number | ((n: number) => number),
) {
  const events: TierEvent[] = []
  let t = start
  const end = start + seconds * 1000
  let n = 0
  while (t < end) {
    t += typeof frameMs === 'number' ? frameMs : frameMs(n)
    n++
    const event = controller.frame(t)
    if (event) events.push(event)
  }
  return { events, t }
}

describe('percentileOf and FrameStats', () => {
  it('uses nearest-rank percentiles', () => {
    const sorted = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    expect(percentileOf(sorted, 50)).toBe(5)
    expect(percentileOf(sorted, 95)).toBe(10)
    expect(percentileOf(sorted, 0)).toBe(1)
    expect(percentileOf([], 50)).toBe(0)
  })

  it('reports frame-time percentiles and the 5th percentile fps', () => {
    const stats = new FrameStats(256)
    for (let i = 0; i < 95; i++) stats.push(10)
    for (let i = 0; i < 5; i++) stats.push(50)
    expect(stats.count).toBe(100)
    expect(stats.percentile(50)).toBe(10)
    expect(stats.percentile(99)).toBe(50)
    // the slowest 5 % of frames took 50 ms: 20 fps
    expect(stats.fpsPercentile(5)).toBeCloseTo(1000 / 10, 5)
    const snap = stats.snapshot()
    expect(snap.maxMs).toBe(50)
    expect(snap.meanMs).toBeCloseTo(12, 5)
    expect(snap.fpsMean).toBeCloseTo(1000 / 12, 3)
  })

  it('resets, ignores junk and keeps only the newest frames in a full ring', () => {
    const stats = new FrameStats(4)
    stats.push(Number.NaN)
    stats.push(-3)
    expect(stats.count).toBe(0)
    for (const ms of [100, 100, 100, 100, 5, 5, 5, 5]) stats.push(ms)
    expect(stats.count).toBe(8)
    expect(stats.percentile(100)).toBe(5)
    stats.reset()
    expect(stats.count).toBe(0)
    expect(stats.snapshot().p50Ms).toBe(0)
    expect(stats.percentile(50)).toBe(0)
  })
})

describe('tier table and picking', () => {
  it('orders the tiers from heavy to light', () => {
    expect(TIERS.high.pixelRatioCap).toBeGreaterThan(TIERS.medium.pixelRatioCap)
    expect(TIERS.medium.pixelRatioCap).toBeGreaterThan(TIERS.low.pixelRatioCap)
    expect(TIERS.high.shadows).toBe(true)
    expect(TIERS.medium.shadows).toBe(false)
    expect(TIERS.low.shadows).toBe(false)
    expect(TIERS.high.rainParticles).toBeGreaterThan(TIERS.low.rainParticles)
    expect(TIERS.high.treeFraction).toBe(1)
    expect(TIERS.low.antialias).toBe(false)
    expect(stepDown('high')).toBe('medium')
    expect(stepDown('low')).toBe('low')
    expect(stepUp('low')).toBe('medium')
    expect(stepUp('high')).toBe('high')
  })

  it('picks a tier from the probe result', () => {
    expect(pickTier(60)).toBe('high')
    expect(pickTier(50)).toBe('high')
    expect(pickTier(35)).toBe('medium')
    expect(pickTier(12)).toBe('low')
  })
})

describe('TierController probe', () => {
  it('keeps high on a machine that holds 60 fps', () => {
    const c = new TierController()
    expect(c.phase).toBe('probe')
    const { events } = run(c, 0, 3, 1000 / 60)
    expect(events).toHaveLength(1)
    expect(events[0]?.reason).toBe('probe')
    expect(c.tier).toBe('high')
    expect(c.phase).toBe('run')
  })

  it('drops to medium and to low on slow machines, after about two seconds', () => {
    const slow = new TierController()
    const first = run(slow, 0, 3, 1000 / 30)
    expect(first.events[0]?.tier).toBe('medium')
    const crawl = new TierController()
    const second = run(crawl, 0, 3, 1000 / 12)
    expect(second.events[0]?.tier).toBe('low')
    // decision lands after warm-up plus two seconds, not before
    const timing = new TierController()
    const early = run(timing, 0, 1.5, 1000 / 12)
    expect(early.events).toHaveLength(0)
  })

  it('is not fooled by a few slow frames among many fast ones', () => {
    const c = new TierController()
    // one 40 ms frame in 40: 2.5 % of frames, outside the 5th percentile
    const { events } = run(c, 0, 3, (n) => (n % 40 === 0 ? 40 : 16))
    expect(events[0]?.tier).toBe('high')
  })

  it('restarts when the tab was hidden mid-probe', () => {
    const c = new TierController()
    let t = 0
    for (let i = 0; i < 40; i++) c.frame((t += 16.7))
    c.frame((t += 5000)) // hidden tab
    const { events } = run(c, t, 3, 1000 / 60)
    expect(events[0]?.tier).toBe('high')
  })
})

describe('TierController at runtime', () => {
  function settled(frameMs: number) {
    const c = new TierController()
    const { t } = run(c, 0, 3, frameMs)
    expect(c.phase).toBe('run')
    return { c, t }
  }

  it('steps down after a rolling 3 s window below 30 fps', () => {
    const { c, t } = settled(1000 / 60)
    expect(c.tier).toBe('high')
    const { events } = run(c, t, 12, 1000 / 20)
    expect(events[0]?.reason).toBe('step-down')
    expect(events[0]?.tier).toBe('medium')
  })

  it('does not step down for a short stutter', () => {
    const { c, t } = settled(1000 / 60)
    const { events } = run(c, t, 1.5, 1000 / 15)
    const after = run(c, t + 1500, 10, 1000 / 60)
    expect([...events, ...after.events]).toHaveLength(0)
    expect(c.tier).toBe('high')
  })

  it('waits for a fresh window and a cooldown between steps, so it cannot flap', () => {
    const { c, t } = settled(1000 / 60)
    const { events, t: end } = run(c, t, 30, 1000 / 14)
    // 30 s at 14 fps: high -> medium -> low, with at least a cooldown between the two
    expect(events.map((e) => e.tier)).toEqual(['medium', 'low'])
    expect(c.tier).toBe('low')
    expect(end - t).toBeGreaterThan(0)
    // already lowest: nothing more to do however slow it stays
    expect(run(c, end, 20, 1000 / 8).events).toHaveLength(0)
  })

  it('steps up at most once, and only after sustained headroom', () => {
    const c = new TierController()
    // the probe sees 30 fps and picks medium
    let { t } = run(c, 0, 3, 1000 / 30)
    expect(c.tier).toBe('medium')
    // 8 s of 60 fps is not enough (hold is 10 s)
    const brief = run(c, t, 8, 1000 / 60)
    t = brief.t
    expect(brief.events).toHaveLength(0)
    const long = run(c, t, 12, 1000 / 60)
    t = long.t
    expect(long.events.map((e) => e.reason)).toEqual(['step-up'])
    expect(c.tier).toBe('high')
    // it falls over again, comes back to fine: no second automatic step-up
    const bad = run(c, t, 12, 1000 / 20)
    t = bad.t
    expect(c.tier).not.toBe('high')
    const fine = run(c, t, 60, 1000 / 60)
    expect(fine.events.filter((e) => e.reason === 'step-up')).toHaveLength(0)
  })

  it('ignores gaps from hidden tabs', () => {
    const { c, t } = settled(1000 / 60)
    c.frame(t + 20_000)
    const { events } = run(c, t + 20_000, 6, 1000 / 60)
    expect(events).toHaveLength(0)
    expect(c.tier).toBe('high')
  })
})

describe('TierController user choice', () => {
  it('a fixed tier switches the controller off', () => {
    const c = new TierController({ choice: 'low' })
    expect(c.phase).toBe('fixed')
    expect(c.tier).toBe('low')
    expect(run(c, 0, 20, 1000 / 5).events).toHaveLength(0)
    expect(c.tier).toBe('low')
  })

  it('Auto restarts the probe from the heaviest tier', () => {
    const c = new TierController({ choice: 'low' })
    expect(c.setChoice('auto')).toBe('high')
    expect(c.phase).toBe('probe')
    const { events } = run(c, 0, 3, 1000 / 30)
    expect(events[0]?.tier).toBe('medium')
    expect(c.setChoice('high')).toBe('high')
    expect(c.phase).toBe('fixed')
  })
})

describe('QualityStore', () => {
  const memory = () => {
    const data = new Map<string, string>()
    return {
      data,
      read: (k: string) => data.get(k) ?? null,
      write: (k: string, v: string) => void data.set(k, v),
    }
  }

  it('persists the choice and restores it', () => {
    const storage = memory()
    const store = new QualityStore(storage)
    expect(store.getState().choice).toBe('auto')
    expect(store.getState().phase).toBe('probe')
    store.setChoice('medium')
    expect(storage.data.get(QUALITY_KEY)).toBe('medium')
    expect(store.getState()).toMatchObject({ choice: 'medium', tier: 'medium', phase: 'fixed' })
    const again = new QualityStore(storage)
    expect(again.getState().tier).toBe('medium')
  })

  it('ignores an unknown stored value', () => {
    const storage = memory()
    storage.write(QUALITY_KEY, 'ultra')
    expect(new QualityStore(storage).getState().choice).toBe('auto')
  })

  it('collects frame stats, publishes about once a second, and resets', () => {
    const store = new QualityStore(memory())
    let seen = 0
    store.subscribe(() => seen++)
    let t = 0
    for (let i = 0; i < 130; i++) store.frame((t += 1000 / 60))
    expect(store.frameStats.count).toBeGreaterThan(120)
    expect(store.getState().stats.fpsMean).toBeCloseTo(60, 0)
    expect(seen).toBeGreaterThanOrEqual(2)
    store.frame(t + 9000) // hidden tab: not a frame time
    expect(store.frameStats.percentile(100)).toBeLessThan(20)
    store.resetStats()
    expect(store.frameStats.count).toBe(0)
    expect(store.getState().stats.count).toBe(0)
  })

  it('reports the probe decision', () => {
    const store = new QualityStore(memory())
    let t = 0
    for (let i = 0; i < 150; i++) store.frame((t += 1000 / 15))
    expect(store.getState().lastEvent?.reason).toBe('probe')
    expect(store.getState().tier).toBe('low')
  })
})
