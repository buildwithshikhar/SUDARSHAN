import { CLASSES, type ClassId, type SessionRecord, type Trainee } from './people'
import { at, clamp, mulberry32, round } from './rng'

export type Identity = 'hostile' | 'suspect' | 'unknown' | 'neutral' | 'friend'
export type ResponseAction = 'hold' | 'report' | 'track' | 'engage'
export type NodeId = 'detect' | 'classify' | 'assess' | 'respond' | 'report'

export const ZONES = { inner: 500, outer: 1500, extent: 2400 }
export const REPLAY_DURATION_S = 300

type Waypoint = [t: number, x: number, y: number]

export interface ReplayContact {
  id: string
  label: string
  truthClass: ClassId
  truthIdentity: Identity
  route: Waypoint[]
  spawnS: number
  firstReturnS: number
  detectS: number
  classifyS: number
  calledClass: ClassId
  assessS: number
  assessedIdentity: Identity
  respondS: number
  response: ResponseAction
  /** The response the rule pack permits for this contact at that moment. */
  roePermitted: boolean
  reportQuality: number
}

export interface DecisionNode {
  node: NodeId
  score: number
  max: number
  /** Translation key under `m.aar.reason` and its parameters. */
  reason: string
  params: Record<string, string | number>
}

export interface ScoredContact extends ReplayContact {
  nodes: DecisionNode[]
  total: number
  totalMax: number
}

export interface ReplayEvent {
  t: number
  kind: 'sensor' | 'detect' | 'classify' | 'assess' | 'respond' | 'injected' | 'note'
  contactId?: string
  /** Translation key under `m.aar.event` and its parameters. */
  key: string
  params: Record<string, string | number>
}

const CONTACTS: ReplayContact[] = [
  {
    id: 'K1',
    label: 'K1',
    truthClass: 'rotary-small',
    truthIdentity: 'hostile',
    route: [
      [0, 2200, 1500],
      [120, 900, 600],
      [190, 380, 260],
      [240, 420, 300],
      [300, 380, 250],
    ],
    spawnS: 0,
    firstReturnS: 14,
    detectS: 24,
    classifyS: 41,
    calledClass: 'rotary-small',
    assessS: 56,
    assessedIdentity: 'hostile',
    respondS: 148,
    response: 'engage',
    roePermitted: true,
    reportQuality: 0.88,
  },
  {
    id: 'K2',
    label: 'K2',
    truthClass: 'bird',
    truthIdentity: 'neutral',
    route: [
      [0, -1700, 900],
      [80, -1400, 1200],
      [160, -1000, 800],
      [240, -1300, 500],
      [300, -1600, 700],
    ],
    spawnS: 0,
    firstReturnS: 10,
    detectS: 19,
    classifyS: 34,
    calledClass: 'bird',
    assessS: 44,
    assessedIdentity: 'neutral',
    respondS: 52,
    response: 'hold',
    roePermitted: true,
    reportQuality: 0.94,
  },
  {
    id: 'K3',
    label: 'K3',
    truthClass: 'fixed-wing-small',
    truthIdentity: 'neutral',
    route: [
      [0, -2000, -1100],
      [150, 0, -1000],
      [300, 2000, -900],
    ],
    spawnS: 0,
    firstReturnS: 5,
    detectS: 31,
    classifyS: 52,
    calledClass: 'fixed-wing-small',
    assessS: 63,
    assessedIdentity: 'neutral',
    respondS: 70,
    response: 'hold',
    roePermitted: true,
    reportQuality: 0.71,
  },
  {
    id: 'K4',
    label: 'K4',
    truthClass: 'fpv-small',
    truthIdentity: 'hostile',
    route: [
      [60, 300, -2200],
      [200, 150, -700],
      [300, 100, -300],
    ],
    spawnS: 60,
    firstReturnS: 82,
    detectS: 97,
    classifyS: 118,
    calledClass: 'rotary-small',
    assessS: 131,
    assessedIdentity: 'hostile',
    respondS: 176,
    response: 'engage',
    roePermitted: true,
    reportQuality: 0.58,
  },
]

const STANDARD = { detect: 10, classify: 20, assess: 15, respond: 45 }
const MAX = { detect: 20, classify: 20, assess: 15, respond: 30, report: 15 }

function scoreContact(c: ReplayContact): ScoredContact {
  const detectDelay = c.detectS - c.firstReturnS
  const detectQ =
    detectDelay <= STANDARD.detect ? 1 : Math.max(0, 1 - (detectDelay - STANDARD.detect) / 30)
  const classifyDelay = c.classifyS - c.firstReturnS
  const timing =
    classifyDelay <= STANDARD.classify
      ? 1
      : Math.max(0.5, 1 - (classifyDelay - STANDARD.classify) / 80)
  const correct = c.calledClass === c.truthClass
  const classifyQ = (correct ? 1 : 0.3) * timing
  const assessQ = c.assessedIdentity === c.truthIdentity ? 1 : 0
  const respondQ = c.roePermitted ? 1 : 0
  const nodes: DecisionNode[] = [
    {
      node: 'detect',
      score: round(MAX.detect * detectQ, 1),
      max: MAX.detect,
      reason: 'detect',
      params: { delay: detectDelay, std: STANDARD.detect },
    },
    {
      node: 'classify',
      score: round(MAX.classify * classifyQ, 1),
      max: MAX.classify,
      reason: correct ? 'classifyRight' : 'classifyWrong',
      params: { called: c.calledClass, truth: c.truthClass, delay: classifyDelay },
    },
    {
      node: 'assess',
      score: MAX.assess * assessQ,
      max: MAX.assess,
      reason: assessQ === 1 ? 'assessRight' : 'assessWrong',
      params: { identity: c.assessedIdentity },
    },
    {
      node: 'respond',
      score: MAX.respond * respondQ,
      max: MAX.respond,
      reason: c.response === 'hold' ? 'respondHold' : 'respondPermitted',
      params: { action: c.response, at: c.respondS },
    },
    {
      node: 'report',
      score: round(MAX.report * c.reportQuality, 1),
      max: MAX.report,
      reason: 'report',
      params: { quality: Math.round(c.reportQuality * 100) },
    },
  ]
  return {
    ...c,
    nodes,
    total: round(
      nodes.reduce((a, n) => a + n.score, 0),
      1,
    ),
    totalMax: nodes.reduce((a, n) => a + n.max, 0),
  }
}

export interface Replay {
  contacts: ScoredContact[]
  events: ReplayEvent[]
  /** Decision-tree score for the replayed contacts, 0 to 100. */
  score: number
}

/** The reference reaction time the base contact timings were authored at. */
const REFERENCE_REACTION_S = 4.6

/** Contacts as one session played out: the trainee's delays scale with their reaction time. */
function contactsFor(session: SessionRecord): ReplayContact[] {
  const f = clamp(session.reactionTimeS / REFERENCE_REACTION_S, 0.55, 1.9)
  return CONTACTS.map((c) => {
    const detectS = Math.round(c.firstReturnS + (c.detectS - c.firstReturnS) * f)
    const classifyS = Math.round(detectS + (c.classifyS - c.detectS) * f)
    const assessS = Math.round(classifyS + (c.assessS - c.classifyS) * f)
    const respondS = Math.round(assessS + (c.respondS - c.assessS) * f)
    let calledClass = c.calledClass
    if (c.id === 'K4') calledClass = session.classifyAccuracy > 0.8 ? c.truthClass : 'rotary-small'
    if (c.id === 'K3' && session.classifyAccuracy < 0.6) calledClass = 'bird'
    return {
      ...c,
      detectS,
      classifyS,
      assessS,
      respondS,
      calledClass,
      roePermitted: c.id === 'K4' ? session.roeCompliance > 0.8 : c.roePermitted,
      reportQuality: round(
        clamp(c.reportQuality + (session.classifyAccuracy - 0.85) * 0.5, 0.3, 0.98),
        2,
      ),
    }
  })
}

const replayCache = new Map<string, Replay>()

export function replayFor(session: SessionRecord): Replay {
  const cached = replayCache.get(session.id)
  if (cached) return cached
  const contacts = contactsFor(session).map(scoreContact)
  const replay: Replay = {
    contacts,
    events: eventsFor(contacts),
    score: round(
      (contacts.reduce((a, c) => a + c.total, 0) / contacts.reduce((a, c) => a + c.totalMax, 0)) *
        100,
      1,
    ),
  }
  replayCache.set(session.id, replay)
  return replay
}

function eventsFor(contacts: ReplayContact[]): ReplayEvent[] {
  const events: ReplayEvent[] = []
  for (const c of contacts) {
    events.push({
      t: c.firstReturnS,
      kind: 'sensor',
      contactId: c.id,
      key: 'sensor',
      params: { id: c.id },
    })
    events.push({
      t: c.detectS,
      kind: 'detect',
      contactId: c.id,
      key: 'detect',
      params: { id: c.id },
    })
    events.push({
      t: c.classifyS,
      kind: 'classify',
      contactId: c.id,
      key: 'classify',
      params: { id: c.id, called: c.calledClass },
    })
    events.push({
      t: c.assessS,
      kind: 'assess',
      contactId: c.id,
      key: 'assess',
      params: { id: c.id, identity: c.assessedIdentity },
    })
    events.push({
      t: c.respondS,
      kind: 'respond',
      contactId: c.id,
      key: c.response === 'hold' ? 'hold' : 'respond',
      params: { id: c.id, action: c.response },
    })
  }
  events.push({ t: 120, kind: 'injected', key: 'wind', params: {} })
  events.push({ t: 200, kind: 'injected', key: 'rfLoss', params: {} })
  events.push({
    t: 97,
    kind: 'note',
    key: 'note',
    params: { text: 'Late call on the second approach. Compare the radar and EO cues with K1.' },
  })
  return events.sort((a, b) => a.t - b.t)
}

/** Position of a contact at time t along its route, or null before it appears. */
export function positionAt(c: ReplayContact, t: number): { x: number; y: number } | null {
  const first = c.route[0]
  const last = c.route[c.route.length - 1]
  if (!first || !last || t < first[0]) return null
  if (t >= last[0]) return { x: last[1], y: last[2] }
  for (let i = 0; i < c.route.length - 1; i += 1) {
    const a = c.route[i]
    const b = c.route[i + 1]
    if (a && b && t >= a[0] && t <= b[0]) {
      const k = (t - a[0]) / (b[0] - a[0])
      return { x: a[1] + (b[1] - a[1]) * k, y: a[2] + (b[2] - a[2]) * k }
    }
  }
  return null
}

/** What the trainee's track table shows for a contact at time t, or null before it is detected. */
export function seenAt(
  c: ReplayContact,
  t: number,
): { x: number; y: number; label: ClassId } | null {
  if (t < c.detectS) return null
  const p = positionAt(c, t)
  if (!p) return null
  const jitter = (axis: number) => Math.sin(t * 0.9 + c.id.charCodeAt(1) * (axis + 1)) * 38
  return {
    x: p.x + jitter(0),
    y: p.y + jitter(1),
    label: t >= c.classifyS ? c.calledClass : 'unknown',
  }
}

export const CONTACT_DATA = CONTACTS

/** A confusion matrix: rows are the true class, columns the class the trainee called. */
const CONFUSABLE: Record<ClassId, ClassId[]> = {
  'rotary-small': ['fpv-small', 'unknown'],
  'fixed-wing-small': ['bird', 'fixed-wing-medium'],
  bird: ['kite', 'unknown'],
  unknown: ['rotary-small', 'bird'],
  'fpv-small': ['rotary-small', 'bird'],
  'fixed-wing-medium': ['fixed-wing-small', 'fixed-wing-large'],
  'fixed-wing-large': ['fixed-wing-medium', 'fixed-wing-small'],
  kite: ['bird', 'balloon'],
  balloon: ['kite', 'unknown'],
}

export function confusionFor(trainees: Trainee[]): number[][] {
  const matrix = CLASSES.map(() => CLASSES.map(() => 0))
  for (const trainee of trainees) {
    const rng = mulberry32(300 + Number(trainee.id.slice(1)) * 29)
    for (const session of trainee.sessions) {
      for (let k = 0; k < session.contacts; k += 1) {
        const truthIndex = Math.floor(Math.pow(rng(), 1.35) * CLASSES.length)
        const truth = at(CLASSES, truthIndex)
        let called: ClassId = truth
        if (rng() > session.classifyAccuracy) {
          const options = CONFUSABLE[truth]
          called = at(options, rng() < 0.7 ? 0 : 1)
        }
        const row = matrix[CLASSES.indexOf(truth)]
        if (row) row[CLASSES.indexOf(called)] = (row[CLASSES.indexOf(called)] ?? 0) + 1
      }
    }
  }
  return matrix
}

export const SECTORS = 12
export const RING_COUNT = 5
export const RING_EDGES_M = [0, 600, 1200, 1800, 2400, 3000]

/** Share of contacts missed (not detected before the standard time), by bearing sector and range ring. */
export function missZones(trainees: Trainee[]): { rate: number; contacts: number }[][] {
  const skill =
    trainees.length === 0
      ? 0.6
      : trainees.reduce((a, t) => a + clamp(at(t.sessions, 3).classifyAccuracy, 0, 1), 0) /
        trainees.length
  const rng = mulberry32(5150 + trainees.length * 13)
  return Array.from({ length: SECTORS }, (_, s) =>
    Array.from({ length: RING_COUNT }, (_, r) => {
      const farWest = Math.exp(-(((s - 8) / 1.6) ** 2)) * (0.25 + r * 0.15)
      const eastMid = Math.exp(-(((s - 2) / 1.3) ** 2)) * (r === 2 ? 0.28 : 0.06)
      const base = 0.03 + r * 0.025
      const rate = clamp((base + farWest + eastMid) * (1.3 - skill) + (rng() - 0.5) * 0.04, 0, 0.95)
      return {
        rate: round(rate, 2),
        contacts: 6 + Math.round(rng() * 14) * (trainees.length > 3 ? 3 : 1),
      }
    }),
  )
}
