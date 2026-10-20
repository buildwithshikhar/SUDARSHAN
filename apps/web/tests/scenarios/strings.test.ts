import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import en from '../../src/i18n/en.json'
import hi from '../../src/i18n/hi.json'
import { FAILED_CHECKS, MOCK_LIBRARY, SOLVED_CHECKS } from '../../src/scenarios/mock'
import {
  DIFFICULTY_AXES,
  ORIGINS,
  TERRAINS,
  THREAT_MIXES,
  TIMES_OF_DAY,
} from '../../src/scenarios/types'

const src = resolve(import.meta.dirname, '../../src')

function sources(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name)
    if (statSync(path).isDirectory()) return sources(path)
    return /\.tsx?$/.test(name) && !path.includes('/contracts/') ? [path] : []
  })
}

const lookup = (tree: unknown, key: string): unknown =>
  key
    .split('.')
    .reduce<unknown>((node, part) => (node as Record<string, unknown> | undefined)?.[part], tree)

const leaves = (node: unknown): string[] =>
  typeof node === 'string'
    ? [node]
    : node && typeof node === 'object'
      ? Object.values(node).flatMap(leaves)
      : []

const scenarioFiles = sources(src).filter((f) =>
  /\/(scenarios\/|screens\/(ScenarioLibrary|ScenarioEditor|GeneratorStudio))/.test(f),
)

describe('scenario strings', () => {
  it('has English and Hindi text for every literal scenarios.* key used in the source', () => {
    const keys = new Set<string>()
    for (const file of scenarioFiles)
      for (const m of readFileSync(file, 'utf-8').matchAll(
        /\bt\(\s*['"](scenarios\.[A-Za-z0-9_.-]+)['"]/g,
      ))
        keys.add(m[1]!)
    expect(keys.size).toBeGreaterThan(150)
    expect([...keys].filter((k) => typeof lookup(en, k) !== 'string')).toEqual([])
    expect([...keys].filter((k) => typeof lookup(hi, k) !== 'string')).toEqual([])
  })

  it('covers every key chosen at run time', () => {
    const lint = [
      'timing.reaction-window',
      'coverage.none',
      'coverage.late',
      'roe.no-engage-rule',
      'roe.zone-missing',
      'roe.pack-missing',
      'route.leaves-area',
      'route.below-envelope',
      'route.above-envelope',
      'route.speed',
      'route.unreachable',
      'route.underground',
      'catalogue.limits',
      'group.link-range',
      'sensor.profile',
    ].map((c) => `scenarios.lint.${c}`)
    const checks = ['presented', 'answered', 'failures', 'score'].map(
      (c) => `scenarios.check.solvability.${c}`,
    )
    const failures = ['network', 'forbidden', 'notFound', 'error']
    const dynamic = [
      ...lint,
      ...checks,
      ...['yaml', 'contract', 'schema'].map((p) => `scenarios.error.${p}`),
      ...ORIGINS.map((o) => `scenarios.origin.${o}`),
      ...TERRAINS.map((o) => `scenarios.terrain.${o}`),
      ...TIMES_OF_DAY.map((o) => `scenarios.time.${o}`),
      ...THREAT_MIXES.map((o) => `scenarios.generator.mix.${o}`),
      ...DIFFICULTY_AXES.map((o) => `scenarios.generator.axis.${o}`),
      ...['threat_count', 'id_ambiguity', 'approach_speed'].map((o) => `scenarios.axis.${o}`),
      ...[
        'threat_count',
        'id_ambiguity',
        'approach_speed',
        'bearing_spread',
        'clutter_density',
        'degradation_load',
        'timing_tightness',
        'stealth',
      ].map((o) => `scenarios.feature.${o}`),
      ...['verified', 'failed', 'unchecked'].map((o) => `scenarios.solvability.${o}`),
      ...['error', 'warning'].map((o) => `scenarios.severity.${o}`),
      ...['order', 'title', 'difficultyUp', 'difficultyDown', 'hostile', 'duration'].map(
        (o) => `scenarios.library.sorts.${o}`,
      ),
      ...['hostile', 'civil', 'clutter', 'zone', 'sensor', 'asset'].map(
        (o) => `scenarios.editor.preview.legend.${o}`,
      ),
      ...failures.flatMap((f) => [
        `scenarios.library.error.${f}`,
        `scenarios.editor.loadError.${f}`,
        `scenarios.editor.validation.error.${f}`,
        `scenarios.editor.checks.error.${f}`,
        `scenarios.editor.preview.error.${f}`,
        `scenarios.generator.result.error.${f}`,
        `scenarios.generator.report.error.${f}`,
      ]),
      ...['inner', 'outer', 'restricted'].map((z) => `live.zone.${z}`),
    ]
    for (const tree of [en, hi])
      expect(dynamic.filter((k) => typeof lookup(tree, k) !== 'string')).toEqual([])
    // every mock check code has a sentence
    for (const c of [...SOLVED_CHECKS, ...FAILED_CHECKS])
      expect(typeof lookup(en, `scenarios.check.${c.code}`)).toBe('string')
    for (const r of MOCK_LIBRARY)
      expect(typeof lookup(en, `live.weather.${r.weather}`)).toBe('string')
  })

  it('uses exactly one solvability sentence in three forms', () => {
    expect(en.scenarios.solvability).toEqual({
      verified: 'Verified solvable by test run',
      failed: 'Not verified solvable',
      unchecked: 'Unchecked',
    })
    expect(en.scenarios.wording).toEqual({
      verified: 'Verified solvable by test run',
      notVerified: 'Not verified solvable',
    })
  })

  it('never writes "provably" or "guaranteed" in the strings or the sources', () => {
    const all = [...leaves(en.scenarios), ...leaves(hi.scenarios)].join('\n')
    expect(all).not.toMatch(/provabl|guarantee/i)
    for (const file of scenarioFiles)
      expect(readFileSync(file, 'utf-8'), file).not.toMatch(/provabl|guarantee/i)
    // and nowhere else in the catalogues
    expect(JSON.stringify(en)).not.toMatch(/provabl|guarantee/i)
    expect(JSON.stringify(hi)).not.toMatch(/provabl|guarantee/i)
  })

  it('does not claim proof, validation or doctrine', () => {
    const text = leaves(en.scenarios).join('\n')
    expect(text).not.toMatch(/\bproof\b|\bproven\b|doctrine|operational data|classified/i)
  })

  it('writes the Hindi as Devanagari, not as a copy of the English', () => {
    const same: string[] = []
    const walk = (a: unknown, b: unknown, path: string) => {
      if (typeof a === 'string' && typeof b === 'string') {
        if (a === b && /[A-Za-z]{4,}/.test(a)) same.push(path)
      } else if (a && b && typeof a === 'object')
        for (const k of Object.keys(a)) walk((a as never)[k], (b as never)[k], `${path}.${k}`)
    }
    walk(en.scenarios, hi.scenarios, 'scenarios')
    expect(same).toEqual([])
  })

  it('carries no data-source labels inside the scenario screens', () => {
    for (const text of leaves(en.scenarios))
      expect(text.toLowerCase()).not.toContain('reference data')
  })

  it('uses no emoji in strings or sources', () => {
    const emoji = /\p{Extended_Pictographic}/u
    for (const text of leaves(en.scenarios)) expect(emoji.test(text)).toBe(false)
    for (const file of scenarioFiles)
      expect(emoji.test(readFileSync(file, 'utf-8')), file).toBe(false)
  })

  it('imports icons only from the Carbon set', () => {
    for (const file of scenarioFiles) {
      const text = readFileSync(file, 'utf-8')
      for (const m of text.matchAll(/from '(@[^']*icons[^']*|[^']*icons[^']*)'/g))
        expect(m[1], file).toBe('@carbon/icons-react')
    }
  })
})
