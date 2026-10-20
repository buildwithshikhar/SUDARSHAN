import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import en from '../../src/i18n/en.json'
import hi from '../../src/i18n/hi.json'
import { NAV } from '../../src/nav/modules'
import { MOCK_WELCOME } from '../../src/live/mock'

const src = resolve(import.meta.dirname, '../../src')

function sources(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name)
    if (statSync(path).isDirectory()) return sources(path)
    return /\.tsx?$/.test(name) && !name.endsWith('.d.ts') && !path.includes('/contracts/')
      ? [path]
      : []
  })
}

const lookup = (tree: unknown, key: string): unknown =>
  key
    .split('.')
    .reduce<unknown>((node, part) => (node as Record<string, unknown> | undefined)?.[part], tree)

describe('live workspace strings', () => {
  it('has English and Hindi text for every literal live.* key used in the source', () => {
    const keys = new Set<string>()
    for (const file of sources(src)) {
      const text = readFileSync(file, 'utf-8')
      for (const m of text.matchAll(/\bt\(\s*['"](live\.[A-Za-z0-9_.-]+)['"]/g)) keys.add(m[1]!)
    }
    expect(keys.size).toBeGreaterThan(100)
    const missing = [...keys].filter(
      (k) => typeof lookup(en, k) !== 'string' || typeof lookup(hi, k) !== 'string',
    )
    expect(missing).toEqual([])
  })

  it('covers every key chosen at run time: classes, identities, zones, modalities, codes, actions', () => {
    const w = MOCK_WELCOME
    const dynamic = [
      ...w.operator_classes.map((c) => `live.class.${c}`),
      ...w.identities.map((i) => `live.identity.${i}`),
      ...['inner', 'outer', 'restricted', 'none'].map((z) => `live.zone.${z}`),
      ...['clear', 'haze', 'rain', 'fog', 'dust'].map((c) => `live.weather.${c}`),
      ...['radar', 'eo', 'ir', 'rf', 'acoustic'].map((m) => `live.modality.${m}`),
      ...['connecting', 'open', 'reconnecting', 'closed'].map((c) => `live.conn.${c}`),
      ...['lobby', 'running', 'ended', 'abandoned'].map((c) => `live.status.${c}`),
      ...['tentative', 'confirmed', 'coasting'].map((c) => `live.track.status.${c}`),
      ...['threat', 'no-threat'].map((c) => `live.assist.flag.${c}`),
      ...[
        'permitted',
        'default-hold',
        'no-rule',
        'conditions',
        'effector',
        'authority',
        'unknown',
      ].map((c) => `live.roe.reason.${c}`),
      ...w.actions.map((a) => `live.roe.action.${a}`),
      ...['operator', 'commander'].map((a) => `live.roe.authority.${a}`),
      ...['identity', 'classification', 'zone', 'confidence'].map((f) => `live.roe.field.${f}`),
      ...['ok', 'cued', 'outage', 'unknown'].map((h) => `live.eo.health.${h}`),
      ...['ok', 'refused', 'blocked', 'info'].map((t) => `live.log.tone.${t}`),
      ...['sent', 'queued', 'refused'].map((p) => `live.pending.${p}`),
      ...['classify', 'assess', 'respond'].flatMap((s) => [
        `live.decision.step.${s}`,
        `live.decision.key.${s}`,
      ]),
      ...[
        'cycle',
        'classify',
        'assess',
        'respond',
        'choose',
        'commit',
        'cancel',
        'hold',
        'cue',
        'relabel',
        'merge',
        'split',
        'drop',
        'dismiss',
        'help',
        'consoleTabs',
        'consoleCursor',
      ].map((k) => `live.keys.${k}`),
      ...[
        'notSignedIn',
        'forbidden',
        'notFound',
        'superseded',
        'full',
        'tooLarge',
        'closed',
      ].flatMap((f) => [`live.fail.${f}.title`, `live.fail.${f}.body`]),
      ...['operator', 'unconfirmed', 'merged'].map((r) => `live.event.dropReason.${r}`),
    ]
    const missing = dynamic.filter(
      (k) => typeof lookup(en, k) !== 'string' || typeof lookup(hi, k) !== 'string',
    )
    expect(missing).toEqual([])
  })

  it('has a label in both languages for each screen in the navigation list', () => {
    const screens = Object.values(NAV)
      .flat()
      .flatMap((g) => g.modules)
      .flatMap((m) => m.screens ?? [])
    expect(screens.map((s) => s.slug)).toEqual(['session-lobby', 'live-session'])
    for (const s of screens) {
      expect(typeof lookup(en, `nav.screen.${s.slug}`)).toBe('string')
      expect(typeof lookup(hi, `nav.screen.${s.slug}`)).toBe('string')
    }
  })

  it('writes the Hindi as Devanagari, not as a copy of the English', () => {
    const same: string[] = []
    const walk = (a: unknown, b: unknown, path: string) => {
      if (typeof a === 'string' && typeof b === 'string') {
        if (path.startsWith('live.') && a === b && /[A-Za-z]{4,}/.test(a)) same.push(path)
      } else if (a && b && typeof a === 'object') {
        for (const k of Object.keys(a))
          walk((a as never)[k], (b as never)[k], path ? `${path}.${k}` : k)
      }
    }
    walk(en, hi, '')
    // protocol names that stay in Latin on purpose (units, sensor classes) are short; anything else is a miss
    expect(same.filter((p) => !/\.(utc|key\.|modality)/.test(p))).toEqual([])
  })
})
