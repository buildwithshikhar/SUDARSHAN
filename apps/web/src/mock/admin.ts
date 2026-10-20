import { TRAINEES } from './people'
import { at, chainValue, mulberry32, round } from './rng'

export type AccountRole = 'trainee' | 'instructor' | 'admin'

export interface UserRow {
  id: string
  name: string
  email: string
  role: AccountRole
  unitId: string
  active: boolean
  lastSignIn: string
  /** Team role the trainee may take in team exercises. */
  teamRole?: 'operator' | 'commander'
}

const STAFF: UserRow[] = [
  {
    id: 'i-01',
    name: 'Maj. Ritu Banerjee',
    email: 'ritu.banerjee@trainer.invalid',
    role: 'instructor',
    unitId: 'u-kestrel',
    active: true,
    lastSignIn: '2026-10-12T05:41:00Z',
  },
  {
    id: 'i-02',
    name: 'Capt. Sandeep Rao',
    email: 'sandeep.rao@trainer.invalid',
    role: 'instructor',
    unitId: 'u-osprey',
    active: true,
    lastSignIn: '2026-10-12T06:07:00Z',
  },
  {
    id: 'i-03',
    name: 'Lt. Farah Siddiqui',
    email: 'farah.siddiqui@trainer.invalid',
    role: 'instructor',
    unitId: 'u-merlin',
    active: true,
    lastSignIn: '2026-10-09T11:20:00Z',
  },
  {
    id: 'a-01',
    name: 'Kiran Deshpande',
    email: 'kiran.deshpande@trainer.invalid',
    role: 'admin',
    unitId: 'u-merlin',
    active: true,
    lastSignIn: '2026-10-12T04:55:00Z',
  },
  {
    id: 'a-02',
    name: 'Naveen Pandey',
    email: 'naveen.pandey@trainer.invalid',
    role: 'admin',
    unitId: 'u-merlin',
    active: false,
    lastSignIn: '2026-08-30T09:12:00Z',
  },
]

export const USERS: UserRow[] = [
  ...TRAINEES.map((t, i): UserRow => ({
    id: t.id,
    name: t.name,
    email: `${t.name.toLowerCase().replace(/[^a-z]+/g, '.')}@trainer.invalid`,
    role: 'trainee',
    unitId: t.unitId,
    active: true,
    lastSignIn: `2026-10-${String(12 - (i % 5)).padStart(2, '0')}T${String(6 + (i % 7)).padStart(2, '0')}:${String(10 + i * 4).padStart(2, '0')}:00Z`,
    teamRole: i % 3 === 0 ? 'commander' : 'operator',
  })),
  ...STAFF,
]

export interface AuditEntry {
  seq: number
  at: string
  actor: string
  action: string
  target: string
  result: 'ok' | 'denied'
  prev: string
  hash: string
}

const AUDIT_SEED: [string, string, string, 'ok' | 'denied'][] = [
  ['Kiran Deshpande', 'user.create', 'Lakshmi Pillai', 'ok'],
  ['Kiran Deshpande', 'user.roleChange', 'Farah Siddiqui', 'ok'],
  ['Maj. Ritu Banerjee', 'auth.signIn', 'console', 'ok'],
  ['Maj. Ritu Banerjee', 'scenario.publish', 'Harrier Field: dusk approach', 'ok'],
  ['Arjun Rawat', 'auth.signIn', 'console', 'ok'],
  ['Arjun Rawat', 'session.start', 'Harrier Field: afternoon watch', 'ok'],
  ['Arjun Rawat', 'session.end', 'Harrier Field: afternoon watch', 'ok'],
  ['system', 'record.sign', 'session s-01-4', 'ok'],
  ['Capt. Sandeep Rao', 'auth.signIn', 'console', 'ok'],
  ['Capt. Sandeep Rao', 'rulepack.update', 'Standard ROE 1.2', 'ok'],
  ['unknown', 'auth.failed', 'console', 'denied'],
  ['Meera Nair', 'auth.signIn', 'console', 'ok'],
  ['Meera Nair', 'session.start', 'Osprey Town: market hours', 'ok'],
  ['Meera Nair', 'session.end', 'Osprey Town: market hours', 'ok'],
  ['system', 'record.sign', 'session s-02-4', 'ok'],
  ['Karan Bhatia', 'auth.signIn', 'console', 'ok'],
  ['Karan Bhatia', 'admin.open', 'User list', 'denied'],
  ['Maj. Ritu Banerjee', 'report.export', 'Kestrel · Course 26-1', 'ok'],
  ['Kiran Deshpande', 'pack.import', 'Heron Ridge terrain 1.0', 'ok'],
  ['Kiran Deshpande', 'backup.run', 'Nightly backup', 'ok'],
  ['Lt. Farah Siddiqui', 'auth.signIn', 'console', 'ok'],
  ['Lt. Farah Siddiqui', 'scenario.publish', 'Merlin Pass: low cloud', 'ok'],
  ['Sunita Yadav', 'auth.signIn', 'console', 'ok'],
  ['Sunita Yadav', 'session.start', 'Heron Ridge: dawn survey', 'ok'],
  ['Sunita Yadav', 'session.end', 'Heron Ridge: dawn survey', 'ok'],
  ['system', 'record.sign', 'session s-04-4', 'ok'],
  ['Capt. Sandeep Rao', 'curriculum.update', 'Core recognition course', 'ok'],
  ['Rohit Chauhan', 'auth.signIn', 'console', 'ok'],
  ['Rohit Chauhan', 'session.start', 'Kestrel Depot: perimeter watch', 'ok'],
  ['Rohit Chauhan', 'session.end', 'Kestrel Depot: perimeter watch', 'ok'],
  ['system', 'record.sign', 'session s-05-4', 'ok'],
  ['Maj. Ritu Banerjee', 'session.inject', 'Wind gust', 'ok'],
  ['Maj. Ritu Banerjee', 'session.annotate', 'Falcon 1', 'ok'],
  ['Ananya Iyer', 'auth.signIn', 'console', 'ok'],
  ['Ananya Iyer', 'session.start', 'Teal Basin: decoy and kite', 'ok'],
  ['Ananya Iyer', 'session.end', 'Teal Basin: decoy and kite', 'ok'],
  ['system', 'record.sign', 'session s-06-4', 'ok'],
  ['Kiran Deshpande', 'user.reset', 'Naveen Pandey', 'ok'],
  ['Kiran Deshpande', 'user.deactivate', 'Naveen Pandey', 'ok'],
  ['Capt. Sandeep Rao', 'report.export', 'Osprey · Course 26-1', 'ok'],
  ['Vikram Sandhu', 'auth.signIn', 'console', 'ok'],
  ['Vikram Sandhu', 'session.start', 'Merlin Pass: two-axis approach', 'ok'],
  ['Vikram Sandhu', 'session.end', 'Merlin Pass: two-axis approach', 'ok'],
  ['system', 'record.sign', 'session s-07-4', 'ok'],
  ['Pooja Menon', 'auth.signIn', 'console', 'ok'],
  ['Kiran Deshpande', 'backup.run', 'Nightly backup', 'ok'],
  ['Harpreet Gill', 'auth.signIn', 'console', 'ok'],
  ['Maj. Ritu Banerjee', 'auth.signIn', 'console', 'ok'],
]

export const AUDIT: AuditEntry[] = (() => {
  let prev = '0000000000000000'
  const start = Date.UTC(2026, 9, 6, 5, 2, 11)
  const rng = mulberry32(88)
  let clock = start
  return AUDIT_SEED.map(([actor, action, target, result], i) => {
    clock += Math.round(900_000 + rng() * 5_400_000)
    const when = new Date(clock).toISOString().replace('.000Z', 'Z')
    const hash = chainValue(`${i + 1}|${when}|${actor}|${action}|${target}|${result}`, prev)
    const entry: AuditEntry = { seq: i + 1, at: when, actor, action, target, result, prev, hash }
    prev = hash
    return entry
  })
})()

/** Recompute the chain over the entries and report the first broken link, or null if intact. */
export function verifyChain(entries: AuditEntry[]): { ok: boolean; brokenSeq: number | null } {
  let prev = '0000000000000000'
  for (const e of entries) {
    const expected = chainValue(
      `${e.seq}|${e.at}|${e.actor}|${e.action}|${e.target}|${e.result}`,
      prev,
    )
    if (e.prev !== prev || e.hash !== expected) return { ok: false, brokenSeq: e.seq }
    prev = e.hash
  }
  return { ok: true, brokenSeq: null }
}

export const SIGNING_KEY_ID = 'key-2026-10 · 9f3a 41c7 0b2e'

export interface PackRow {
  id: string
  name: string
  kind: 'terrain' | 'sensor' | 'scenario' | 'rule'
  version: string
  size: string
  updated: string
  entries: number
  licence: string
}

export const PACKS: PackRow[] = [
  {
    id: 'p-t1',
    name: 'Heron Ridge',
    kind: 'terrain',
    version: '1.0.2',
    size: '48.2 MB',
    updated: '2026-10-02',
    entries: 1,
    licence: 'SRTM, OSM (ODbL)',
  },
  {
    id: 'p-t2',
    name: 'Osprey Town',
    kind: 'terrain',
    version: '1.0.1',
    size: '61.7 MB',
    updated: '2026-10-02',
    entries: 1,
    licence: 'SRTM, OSM (ODbL)',
  },
  {
    id: 'p-s1',
    name: 'Radar profile',
    kind: 'sensor',
    version: '1.3.0',
    size: '18 KB',
    updated: '2026-09-27',
    entries: 11,
    licence: 'Project data',
  },
  {
    id: 'p-s2',
    name: 'EO/IR profile',
    kind: 'sensor',
    version: '1.2.0',
    size: '16 KB',
    updated: '2026-09-27',
    entries: 11,
    licence: 'Project data',
  },
  {
    id: 'p-s3',
    name: 'RF profile',
    kind: 'sensor',
    version: '1.1.0',
    size: '14 KB',
    updated: '2026-09-27',
    entries: 11,
    licence: 'Project data',
  },
  {
    id: 'p-s4',
    name: 'Acoustic profile',
    kind: 'sensor',
    version: '1.1.0',
    size: '13 KB',
    updated: '2026-09-27',
    entries: 11,
    licence: 'Project data',
  },
  {
    id: 'p-c1',
    name: 'Core scenario pack',
    kind: 'scenario',
    version: '2.1.0',
    size: '212 KB',
    updated: '2026-10-08',
    entries: 12,
    licence: 'Project data',
  },
  {
    id: 'p-c2',
    name: 'Generated scenario archive',
    kind: 'scenario',
    version: '2.1.0',
    size: '1.4 MB',
    updated: '2026-10-11',
    entries: 8,
    licence: 'Project data',
  },
  {
    id: 'p-r1',
    name: 'Standard ROE',
    kind: 'rule',
    version: '1.2.0',
    size: '9 KB',
    updated: '2026-10-09',
    entries: 14,
    licence: 'Project data',
  },
  {
    id: 'p-r2',
    name: 'Restricted airspace ROE',
    kind: 'rule',
    version: '1.0.3',
    size: '8 KB',
    updated: '2026-09-30',
    entries: 11,
    licence: 'Project data',
  },
]

export interface RuleRow {
  id: string
  titleKey: string
  authority: 'operator' | 'commander'
  when: string
  permits: string[]
}

export const RULES: RuleRow[] = [
  {
    id: 'R-01',
    titleKey: 'holdCivil',
    authority: 'operator',
    when: 'identity = neutral',
    permits: ['hold', 'report'],
  },
  {
    id: 'R-02',
    titleKey: 'trackUnknown',
    authority: 'operator',
    when: 'identity = unknown',
    permits: ['classify', 'assess', 'report'],
  },
  {
    id: 'R-03',
    titleKey: 'engageHostileInner',
    authority: 'commander',
    when: 'identity = hostile, zone = inner, confidence ≥ 0.7',
    permits: ['engage'],
  },
  {
    id: 'R-04',
    titleKey: 'designateOuter',
    authority: 'operator',
    when: 'identity = hostile, zone = outer',
    permits: ['designate', 'report'],
  },
  {
    id: 'R-05',
    titleKey: 'restrictedAny',
    authority: 'commander',
    when: 'zone = restricted',
    permits: ['engage', 'hold'],
  },
  {
    id: 'R-06',
    titleKey: 'suspectReport',
    authority: 'operator',
    when: 'identity = suspect',
    permits: ['assess', 'report', 'designate'],
  },
]

export const RULE_WEIGHTS = { detect: 0.2, classify: 0.2, assess: 0.15, respond: 0.3, report: 0.15 }
export const RULE_THRESHOLDS = {
  detect_within_s: 10,
  classify_within_s: 20,
  report_within_s: 30,
  respond_within_s: 45,
}

export const RULE_DIFF: { key: string; from: string; to: string }[] = [
  { key: 'weights.respond', from: '0.28', to: '0.30' },
  { key: 'weights.report', from: '0.17', to: '0.15' },
  { key: 'thresholds.classify_within_s', from: '25', to: '20' },
  { key: 'rules.R-03.min_confidence', from: '0.6', to: '0.7' },
]

export const RULE_PACKS = [
  {
    id: 'rp-std',
    name: 'Standard ROE',
    version: '1.2.0',
    rules: 14,
    updated: '2026-10-09',
    author: 'Capt. Sandeep Rao',
    inUse: 6,
  },
  {
    id: 'rp-res',
    name: 'Restricted airspace ROE',
    version: '1.0.3',
    rules: 11,
    updated: '2026-09-30',
    author: 'Maj. Ritu Banerjee',
    inUse: 3,
  },
  {
    id: 'rp-trn',
    name: 'Introductory ROE',
    version: '0.9.4',
    rules: 8,
    updated: '2026-09-12',
    author: 'Lt. Farah Siddiqui',
    inUse: 2,
  },
]

export const SOURCES: {
  id: string
  name: string
  modality: string
  licence: string
  ships: boolean
  use: string
  parameters: number
}[] = [
  {
    id: 'D14',
    name: 'KTH/SAAB 77 GHz radar',
    modality: 'FMCW radar',
    licence: 'CC BY 4.0',
    ships: true,
    use: 'Drone and bird returns, RCS reference',
    parameters: 9,
  },
  {
    id: 'D12',
    name: 'Svanström multi-sensor set',
    modality: 'IR, visible, audio',
    licence: 'Zenodo open; article CC BY',
    ships: false,
    use: 'Confuser classes',
    parameters: 6,
  },
  {
    id: 'D08',
    name: 'DroneRF',
    modality: 'Raw RF, 2.4 GHz',
    licence: 'Article CC BY',
    ships: false,
    use: 'RF detector parameters',
    parameters: 5,
  },
  {
    id: 'G01',
    name: 'NASA SRTM GL1 v003',
    modality: 'DEM 30 m',
    licence: 'Shared without restriction',
    ships: true,
    use: 'Terrain relief',
    parameters: 2,
  },
  {
    id: 'G02',
    name: 'OpenStreetMap',
    modality: 'Vector map data',
    licence: 'ODbL',
    ships: true,
    use: 'Buildings and tree lines',
    parameters: 3,
  },
  {
    id: 'W01',
    name: 'ERA5 reanalysis',
    modality: 'Weather',
    licence: 'CC BY',
    ships: true,
    use: 'Weather presets',
    parameters: 4,
  },
  {
    id: 'X01',
    name: 'UAV Database (NTNU)',
    modality: 'Specification table',
    licence: 'CC0 1.0',
    ships: true,
    use: 'Threat envelopes',
    parameters: 11,
  },
  {
    id: 'F01',
    name: 'Project-authored value',
    modality: 'Any numeric parameter',
    licence: 'Not applicable',
    ships: true,
    use: 'Fictional effector figures, timing standards',
    parameters: 38,
  },
]

export const PROVENANCE: { parameter: string; source: string; verified: boolean }[] = [
  { parameter: 'radar.rotary-small.rcs_dbsm', source: 'D14', verified: true },
  { parameter: 'radar.bird.rcs_dbsm', source: 'D14', verified: true },
  { parameter: 'acoustic.rotary-small.blade_pass_hz', source: 'D12', verified: false },
  { parameter: 'rf.control_link.band_ghz', source: 'D08', verified: false },
  { parameter: 'threat.fixed-wing-medium.cruise_mps', source: 'X01', verified: true },
  { parameter: 'terrain.heron-ridge.elevation', source: 'G01', verified: true },
  { parameter: 'terrain.osprey-town.buildings', source: 'G02', verified: true },
  { parameter: 'weather.haze.visibility_m', source: 'W01', verified: false },
  { parameter: 'rulepack.thresholds.detect_within_s', source: 'F01', verified: false },
  { parameter: 'rulepack.effector.soft-kill.max_range_m', source: 'F01', verified: false },
]

export const SERVICES: {
  id: string
  version: string
  uptimeH: number
  latencyMs: number
  state: 'running'
}[] = [
  { id: 'proxy', version: 'Caddy 2', uptimeH: 412, latencyMs: 2, state: 'running' },
  { id: 'web', version: 'nginx 1.27', uptimeH: 412, latencyMs: 4, state: 'running' },
  { id: 'api', version: 'uvicorn 0.34', uptimeH: 412, latencyMs: 9, state: 'running' },
  { id: 'sim', version: 'sim core 3.4', uptimeH: 118, latencyMs: 6, state: 'running' },
  { id: 'db', version: 'Postgres 16', uptimeH: 412, latencyMs: 3, state: 'running' },
]

export const PERFORMANCE = {
  tickP50Ms: 3.1,
  tickP95Ms: 5.8,
  tickBudgetMs: 50,
  clients: 9,
  clientCap: 12,
  memoryMb: 612,
  memoryCapMb: 2048,
  /** Tick time per minute over the last hour, for the sparkline chart. */
  tickSeries: Array.from({ length: 30 }, (_, i) => {
    const rng = mulberry32(60 + i)
    return { x: i * 2, y: round(2.6 + Math.sin(i / 3.5) * 0.7 + rng() * 0.9, 2) }
  }),
}

export const STORAGE = [
  { id: 'database', usedMb: 318, capMb: 5120 },
  { id: 'packs', usedMb: 124, capMb: 2048 },
  { id: 'records', usedMb: 86, capMb: 2048 },
  { id: 'backups', usedMb: 1210, capMb: 10240 },
]

export const BACKUPS = Array.from({ length: 7 }, (_, i) => ({
  id: `bk-${7 - i}`,
  at: `2026-10-${String(12 - i).padStart(2, '0')}T01:30:00Z`,
  sizeMb: round(168 + i * 0.7 + at([0.4, 1.1, 0.2, 0.8], i), 1),
  verified: true,
  kind: i === 0 || i === 6 ? 'full' : 'incremental',
}))
