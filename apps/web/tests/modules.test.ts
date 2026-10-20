import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join, resolve } from 'node:path'
import en from '../src/i18n/en.json'
import hi from '../src/i18n/hi.json'
import { AUDIT, SCENARIOS, TRAINEES, verifyChain } from '../src/mock'
import { NAV, findModule, sidebarGroups } from '../src/nav/modules'
import { MODULE_SCREENS } from '../src/screens/modules'

const src = resolve(import.meta.dirname, '../src')

function sources(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name)
    if (statSync(path).isDirectory()) return sources(path)
    return /\.tsx$/.test(name) ? [path] : []
  })
}

const lookup = (tree: unknown, key: string): unknown =>
  key
    .split('.')
    .reduce<unknown>((node, part) => (node as Record<string, unknown> | undefined)?.[part], tree)

function leaves(node: unknown, path = ''): [string, string][] {
  if (typeof node === 'string') return [[path, node]]
  if (typeof node !== 'object' || node === null) return []
  return Object.entries(node).flatMap(([k, v]) => leaves(v, path ? `${path}.${k}` : k))
}

describe('module screens', () => {
  it('gives every sidebar item a screen, for every seat', () => {
    for (const role of ['trainee', 'instructor', 'admin', 'commander'] as const)
      for (const group of sidebarGroups(role))
        for (const module of group.modules)
          expect(
            module.home !== undefined ||
              module.slug === 'profile' ||
              MODULE_SCREENS[module.slug] !== undefined,
            `${role}/${module.slug}`,
          ).toBe(true)
    expect(findModule('commander', 'command')?.group.id).toBe('command')
    expect(NAV.trainee.some((g) => g.id === 'command')).toBe(false)
  })

  it('has English and Hindi text for every literal m.* key used in the screens', () => {
    const keys = new Set<string>()
    for (const file of sources(resolve(src, 'screens/modules')))
      for (const m of readFileSync(file, 'utf-8').matchAll(/\bt\(\s*['"](m\.[A-Za-z0-9_.-]+)['"]/g))
        keys.add(m[1] as string)
    expect(keys.size).toBeGreaterThan(250)
    const missing = [...keys].filter(
      (k) => typeof lookup(en, k) !== 'string' || typeof lookup(hi, k) !== 'string',
    )
    expect(missing).toEqual([])
  })

  it('covers every key chosen at run time', () => {
    const dynamic = [
      ...['detect', 'classify', 'assess', 'respond', 'report'].map((k) => `m.aar.nodeName.${k}`),
      ...[
        'detect',
        'classifyRight',
        'classifyWrong',
        'assessRight',
        'assessWrong',
        'respondHold',
        'respondPermitted',
        'report',
      ].map((k) => `m.aar.reason.${k}`),
      ...[
        'sensor',
        'detect',
        'classify',
        'assess',
        'hold',
        'respond',
        'wind',
        'rfLoss',
        'note',
      ].map((k) => `m.aar.event.${k}`),
      ...['sensor', 'detect', 'classify', 'assess', 'respond', 'injected', 'note'].map(
        (k) => `m.aar.kind.${k}`,
      ),
      ...['hold', 'report', 'track', 'engage', 'designate', 'classify', 'assess'].map(
        (k) => `m.aar.action.${k}`,
      ),
      ...[
        'rotary-small',
        'fpv-small',
        'fixed-wing-small',
        'fixed-wing-medium',
        'fixed-wing-large',
        'bird',
        'kite',
        'balloon',
      ].flatMap((c) => [`m.lib.desc.${c}`, `m.lib.tell.${c}`]),
      ...['high', 'medium', 'low', 'none'].map((k) => `m.lib.level.${k}`),
      ...['north', 'east', 'south', 'west'].map((k) => `m.team.sector.${k}`),
      ...['none', 'offered', 'accepted'].map((k) => `m.team.state.${k}`),
      ...['coverage', 'handover', 'roe', 'tempo'].map((k) => `m.team.part.${k}`),
      ...['done', 'current', 'locked'].map((k) => `m.drills.state.${k}`),
      ...['dawn', 'day', 'dusk', 'night'].map((k) => `m.tod.${k}`),
      ...['assessed', 'practice'].map((k) => `m.mode.${k}`),
      ...['contact', 'degrade', 'weather', 'comms'].map((k) => `m.live.injection.${k}`),
      ...['inject', 'annotate', 'pause', 'resume'].map((k) => `m.live.kind.${k}`),
      ...['summary', 'sessions', 'skills', 'confusion', 'missZone'].map(
        (k) => `m.report.section.${k}`,
      ),
      ...['proxy', 'web', 'api', 'sim', 'db'].map((k) => `m.health.name.${k}`),
      ...['database', 'packs', 'records', 'backups'].map((k) => `m.health.store.${k}`),
      ...[
        'holdCivil',
        'trackUnknown',
        'engageHostileInner',
        'designateOuter',
        'restrictedAny',
        'suspectReport',
      ].map((k) => `m.rules.rule.${k}`),
      ...['detect_within_s', 'classify_within_s', 'report_within_s', 'respond_within_s'].map(
        (k) => `m.rules.threshold.${k}`,
      ),
      ...[
        'nextTrack',
        'classify',
        'assess',
        'respond',
        'hold',
        'pause',
        'help',
        'options',
        'commit',
      ].map((k) => `m.help.shortcut.${k}`),
      ...['watch', 'classify', 'report', 'handover'].flatMap((s) =>
        ['title', 's1', 's2', 's3', 's4'].map((k) => `m.help.sop.${s}.${k}`),
      ),
      ...['terrain', 'sensor', 'scenario', 'rule'].map((k) => `m.packs.${k}`),
      ...['full', 'incremental'].map((k) => `m.backup.${k}`),
      ...['ok', 'denied'].map((k) => `m.audit.${k}`),
      ...Object.values(NAV)
        .flat()
        .flatMap((g) => g.modules)
        .concat(sidebarGroups('commander').flatMap((g) => g.modules))
        .map((m) => `status.about.${m.slug}`),
    ]
    const missing = dynamic.filter(
      (k) => typeof lookup(en, k) !== 'string' || typeof lookup(hi, k) !== 'string',
    )
    expect(missing).toEqual([])
  })

  it('keeps development-phase and status wording out of every visible string', () => {
    const banned =
      /\b(waves?|phase|beta|mock|samples?|placeholder|planned|not yet (built|available)|coming|stubs?|todo|demo data|will come|unavailable|fictional scenarios?|reference data|synthesi[sz]ed)\b/i
    const hits: string[] = []
    for (const [lang, tree] of [
      ['en', en],
      ['hi', hi],
    ] as const)
      for (const [key, text] of leaves(tree)) {
        // The About page keeps its scope statement; placeholders such as {{phase}} are variable names.
        if (key.startsWith('about.')) continue
        if (banned.test(text.replace(/\{\{\w+\}\}/g, ''))) hits.push(`${lang}:${key}`)
      }
    expect(hits).toEqual([])
    expect(
      /\bREF\b/.test(
        leaves(en)
          .map(([, t]) => t)
          .join(' '),
      ),
    ).toBe(false)
  })
})

describe('seeded screen data', () => {
  it('holds 12 trainees with four sessions each whose scores improve', () => {
    expect(TRAINEES).toHaveLength(12)
    for (const trainee of TRAINEES) {
      expect(trainee.sessions).toHaveLength(4)
      expect(trainee.sessions[3]!.score).toBeGreaterThan(trainee.sessions[0]!.score)
    }
  })

  it('holds about twenty scenarios, each with a verified oracle result', () => {
    expect(SCENARIOS).toHaveLength(20)
    expect(SCENARIOS.every((s) => s.oracleScore >= 90)).toBe(true)
  })

  it('holds an audit chain that verifies and fails when an entry changes', () => {
    expect(AUDIT.length).toBeGreaterThan(40)
    expect(verifyChain(AUDIT).ok).toBe(true)
    const altered = AUDIT.map((e) => (e.seq === 12 ? { ...e, target: 'changed' } : e))
    expect(verifyChain(altered)).toEqual({ ok: false, brokenSeq: 12 })
  })
})
