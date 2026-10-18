import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import en from '../../src/i18n/en.json'
import hi from '../../src/i18n/hi.json'
import '../../src/i18n'
import { formatParams, renderReason } from '../../src/live/scoring'

const keysPy = readFileSync(
  resolve(import.meta.dirname, '../../../../services/api/app/scoring/keys.py'),
  'utf-8',
)

const tuple = (name: string): string[] => {
  const match = new RegExp(`${name} = \\(([^)]*)\\)`).exec(keysPy)
  return [...(match?.[1] ?? '').matchAll(/"([^"]+)"/g)].map((m) => m[1]!)
}

/** Every key the evaluator can emit, read from services/api/app/scoring/keys.py. */
function allKeys(): string[] {
  const fields = tuple('REPORT_FIELDS')
  const outcomes = tuple('REPORT_OUTCOMES')
  const literal = [...keysPy.matchAll(/^\s+"([a-z][a-z0-9-]*(?:\.[a-z0-9-]+)+)",?$/gm)].map(
    (m) => m[1]!,
  )
  const built = fields.flatMap((f) => outcomes.map((o) => `report.${f}.${o}`))
  return [...new Set([...literal, ...built])]
}

const lookup = (tree: unknown, key: string): unknown =>
  key
    .split('.')
    .reduce<unknown>((node, part) => (node as Record<string, unknown> | undefined)?.[part], tree)

/** One value for every parameter name the evaluator uses. */
const SAMPLE = {
  seconds: 14.2,
  standard: 25,
  first_action: 'classify',
  track: 'T014',
  class: 'rotary-small',
  timing: 0.75,
  changes: 1,
  given: 'bird',
  actual: 'rotary-small',
  effector: 'ec-a',
  blocked_attempts: 2,
  attempts: 2,
  t: 41.3,
  error_id: 'e-2',
  error_m: 212,
  tolerance_m: 150,
  error_deg: 40,
  tolerance_deg: 20,
  stated: 0.8,
  achieved: 0.824,
  worst_field: 'count',
  timeliness: 0.5,
  threat: { en: 'quad', hi: 'क्वाड' },
}

/** `given` and `actual` mean a different thing in assess messages. */
const sampleFor = (key: string) =>
  /assess\./.test(key)
    ? { ...SAMPLE, given: 'suspect', actual: 'civil-permitted' }
    : /hard-fail/.test(key)
      ? { ...SAMPLE, actual: 'clutter' }
      : /report\.count/.test(key)
        ? { ...SAMPLE, given: 2, actual: 3 }
        : SAMPLE

describe('scoring explanations', () => {
  const keys = allKeys()

  it('reads the full key list from the evaluator', () => {
    // 16 node reasons, 23 report reasons, 10 findings and 21 lessons
    expect(keys.length).toBe(70)
    expect(keys).toContain('report.calibration.partial')
    expect(keys).toContain('lesson.hard-fail.no-positive-id')
    expect(keys).toContain('finding.track-error.merge')
  })

  it.each(['en', 'hi'] as const)('has a template for every key in %s', (lang) => {
    const tree = lang === 'en' ? en : hi
    const missing = keys.filter((k) => typeof lookup(tree, `scoring.${k}`) !== 'string')
    expect(missing).toEqual([])
  })

  it.each(['en', 'hi'] as const)(
    'renders every key in %s with its parameters and no placeholder left',
    (lang) => {
      for (const key of keys) {
        const sentence = renderReason(key, sampleFor(key), lang)
        expect(sentence, key).not.toContain('{{')
        expect(sentence, key).not.toContain('—')
        expect(sentence.length, key).toBeGreaterThan(10)
        expect(sentence, key).not.toMatch(/undefined|NaN|\[object/)
      }
    },
  )

  it('uses the same placeholders in English and Hindi', () => {
    const names = (s: string) => [...s.matchAll(/\{\{(\w+)\}\}/g)].map((m) => m[1]!).sort()
    for (const key of keys) {
      const e = lookup(en, `scoring.${key}`) as string
      const h = lookup(hi, `scoring.${key}`) as string
      expect(names(h), key).toEqual(names(e))
    }
  })

  it('renders the documented example', () => {
    expect(
      renderReason(
        'classify.correct',
        { class: 'rotary-small', seconds: 14.2, standard: 25, timing: 1, changes: 0 },
        'en',
      ),
    ).toBe(
      'Classified correctly as Small rotary after 14.2 s against a standard of 25.0 s. Timing credit 100%.',
    )
  })

  it('appends the class changes and blocked attempts only when there are some', () => {
    const base = { class: 'bird', seconds: 3, standard: 25, timing: 1 }
    expect(renderReason('classify.correct', { ...base, changes: 0 }, 'en')).not.toContain('changed')
    expect(renderReason('classify.correct', { ...base, changes: 2 }, 'en')).toContain(
      'changed before the final one: 2',
    )
    expect(renderReason('respond.hold-fire', { blocked_attempts: 0 }, 'en')).not.toContain(
      'blocked by the rules',
    )
    expect(renderReason('respond.hold-fire', { blocked_attempts: 1 }, 'en')).toContain(
      'blocked by the rules on this contact: 1',
    )
  })

  it('formats parameters by the rules in docs/SCORING.md', () => {
    const p = formatParams(
      'report.where.ok',
      { error_m: 61.6, tolerance_m: 150, stated: 0.8, t: 3, worst_field: 'where' },
      'en',
    )
    expect(p).toMatchObject({
      error_m: '62 m',
      tolerance_m: '150 m',
      stated: '80%',
      t: '3.0 s',
      worst_field: 'Where',
    })
    expect(formatParams('classify.wrong', { given: 'bird', actual: 'unknown' }, 'hi')).toEqual({
      given: 'पक्षी',
      actual: 'अज्ञात',
    })
    expect(
      formatParams('assess.wrong', { given: 'friend', actual: 'civil-permitted' }, 'en'),
    ).toEqual({ given: 'Friend', actual: 'civil traffic' })
    expect(formatParams('lesson.detect.band', { threat: { en: 'a', hi: 'ब' } }, 'hi')).toEqual({
      threat: 'ब',
    })
  })

  it('shows a dash, not a placeholder, for a parameter the evaluator did not send', () => {
    const sentence = renderReason('classify.wrong', { given: 'bird' }, 'en')
    expect(sentence).toBe('Classified as Bird. The contact was —.')
  })

  it('writes the Hindi in Devanagari', () => {
    const latin = keys.filter((k) => {
      const h = (lookup(hi, `scoring.${k}`) as string).replace(/\{\{\w+\}\}/g, '')
      return !/[ऀ-ॿ]/.test(h)
    })
    expect(latin).toEqual([])
  })
})
