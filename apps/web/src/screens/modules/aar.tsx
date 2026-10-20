import { useEffect, useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  CLASSES,
  RING_COUNT,
  RING_EDGES_M,
  SECTORS,
  ZONES,
  REPLAY_DURATION_S,
  confusionFor,
  curveFor,
  missZones,
  positionAt,
  replayFor,
  seenAt,
  TRAINEES,
  type Identity,
  type ReplayContact,
  type ScoredContact,
  type SessionRecord,
  type Trainee,
} from '../../mock'
import { Button } from '../../ui/Button'
import { Input, Select } from '../../ui/Field'
import { Panel } from '../../ui/Panel'
import { Table, type Column } from '../../ui/Table'
import { fmtClock } from './format'
import { LineChart, Matrix, MissZoneMap } from './kit'

const SIZE = 300
const HALF = SIZE / 2
const SCALE = (HALF - 14) / 2600

const IDENTITY_COLOUR: Record<Identity, string> = {
  hostile: 'var(--track-hostile)',
  suspect: 'var(--track-suspect)',
  unknown: 'var(--track-unknown)',
  neutral: 'var(--track-neutral)',
  friend: 'var(--track-friend)',
}

/** Track symbol: the frame shape carries the identity, so colour is never the only cue. */
export function TrackSymbol({ identity, x, y }: { identity: Identity; x: number; y: number }) {
  const colour = IDENTITY_COLOUR[identity]
  const common = { fill: 'var(--bg)', stroke: colour, strokeWidth: 2 }
  if (identity === 'hostile')
    return (
      <rect
        x={x - 5}
        y={y - 5}
        width="10"
        height="10"
        transform={`rotate(45 ${x} ${y})`}
        {...common}
      />
    )
  if (identity === 'suspect')
    return <path d={`M ${x} ${y - 6} L ${x + 6} ${y + 5} L ${x - 6} ${y + 5} Z`} {...common} />
  if (identity === 'neutral') return <circle cx={x} cy={y} r="5" {...common} />
  if (identity === 'friend') return <rect x={x - 5} y={y - 4} width="10" height="8" {...common} />
  return <rect x={x - 5} y={y - 5} width="10" height="10" {...common} strokeDasharray="3 2" />
}

const px = (x: number) => HALF + x * SCALE
const py = (y: number) => HALF - y * SCALE

function SiteMap({ alt, children }: { alt: string; children: React.ReactNode }) {
  return (
    <svg
      viewBox={`0 0 ${SIZE} ${SIZE}`}
      role="img"
      aria-label={alt}
      className="block h-auto w-full max-w-[360px] bg-bg"
    >
      <circle
        cx={HALF}
        cy={HALF}
        r={ZONES.outer * SCALE}
        fill="none"
        stroke="var(--border)"
        strokeWidth="1"
        strokeDasharray="4 3"
      />
      <circle
        cx={HALF}
        cy={HALF}
        r={ZONES.inner * SCALE}
        fill="none"
        stroke="var(--signal)"
        strokeWidth="1"
      />
      <circle
        cx={HALF}
        cy={HALF}
        r={ZONES.extent * SCALE}
        fill="none"
        stroke="var(--border)"
        strokeWidth="1"
      />
      <line x1={HALF} x2={HALF} y1="6" y2={SIZE - 6} stroke="var(--border)" strokeWidth="1" />
      <line x1="6" x2={SIZE - 6} y1={HALF} y2={HALF} stroke="var(--border)" strokeWidth="1" />
      <text x={HALF + 4} y="14" fontSize="10" fill="var(--text-2)">
        N
      </text>
      <rect x={HALF - 4} y={HALF - 4} width="8" height="8" fill="var(--accent)" />
      {children}
    </svg>
  )
}

export interface Annotation {
  t: number
  text: string
  author: string
}

/** Timeline replay: what the trainee saw beside the ground truth, with a scrubber and event log. */
export function ReplayPanel({
  session,
  initialT = 0,
  annotations,
  onAnnotate,
}: {
  session: SessionRecord
  initialT?: number
  annotations?: Annotation[]
  onAnnotate?: (note: Annotation) => void
}) {
  const { t } = useTranslation()
  const replay = replayFor(session)
  const [now, setNow] = useState(initialT)
  const [playing, setPlaying] = useState(false)
  const [speed, setSpeed] = useState('10')
  const [draft, setDraft] = useState('')
  const timer = useRef<number | null>(null)

  useEffect(() => {
    if (!playing) return undefined
    timer.current = window.setInterval(() => {
      setNow((n) => {
        const next = n + Number(speed) * 0.1
        if (next >= REPLAY_DURATION_S) {
          setPlaying(false)
          return REPLAY_DURATION_S
        }
        return next
      })
    }, 100)
    return () => {
      if (timer.current !== null) window.clearInterval(timer.current)
    }
  }, [playing, speed])

  const className = (id: string) => t(`live.class.${id}`)
  const eventText = (e: (typeof replay.events)[number]) =>
    t(`m.aar.event.${e.key}`, {
      ...e.params,
      called: typeof e.params.called === 'string' ? className(e.params.called) : '',
      identity:
        typeof e.params.identity === 'string' ? t(`live.identity.${e.params.identity}`) : '',
      action: typeof e.params.action === 'string' ? t(`m.aar.action.${e.params.action}`) : '',
    })

  const merged = useMemo(() => {
    const notes = (annotations ?? []).map((a) => ({
      t: a.t,
      text: `${a.author}: ${a.text}`,
      kind: 'note' as const,
    }))
    return [
      ...replay.events.map((e) => ({
        t: e.t,
        text: e.kind === 'note' ? String(e.params.text ?? '') : eventText(e),
        kind: e.kind,
      })),
      ...notes,
    ].sort((a, b) => a.t - b.t)
    // eventText depends on t only through i18n; recompute when the language changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [replay, annotations, t])

  const visibleTruth = replay.contacts
    .map((c) => ({ c, p: positionAt(c, now) }))
    .filter((x): x is { c: ScoredContact; p: { x: number; y: number } } => x.p !== null)
  const visibleSeen = replay.contacts
    .map((c) => ({ c, s: seenAt(c, now) }))
    .filter(
      (
        x,
      ): x is { c: ScoredContact; s: { x: number; y: number; label: (typeof CLASSES)[number] } } =>
        x.s !== null,
    )

  const trail = (c: ReplayContact) => {
    const pts: string[] = []
    for (let s = c.route[0]?.[0] ?? 0; s <= now; s += 6) {
      const p = positionAt(c, s)
      if (p) pts.push(`${px(p.x).toFixed(1)},${py(p.y).toFixed(1)}`)
    }
    return pts.join(' ')
  }

  const lastIndex = merged.reduce((acc, e, i) => (e.t <= now ? i : acc), -1)

  return (
    <Panel
      title={t('m.aar.replay')}
      actions={
        <span className="num text-xs text-ink-2">
          {fmtClock(now)} / {fmtClock(REPLAY_DURATION_S)}
        </span>
      }
    >
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2 2xl:grid-cols-[1fr_1fr_320px]">
        <figure className="m-0">
          <figcaption className="micro-label mb-1">{t('m.aar.seen')}</figcaption>
          <SiteMap alt={t('m.aar.seenAlt')}>
            {visibleSeen.map(({ c, s }) => (
              <g key={c.id}>
                <TrackSymbol
                  identity={s.label === 'unknown' ? 'unknown' : c.assessedIdentity}
                  x={px(s.x)}
                  y={py(s.y)}
                />
                <text x={px(s.x) + 9} y={py(s.y) + 4} fontSize="10" fill="var(--text)">
                  {c.id} · {className(s.label)}
                </text>
              </g>
            ))}
          </SiteMap>
        </figure>
        <figure className="m-0">
          <figcaption className="micro-label mb-1">{t('m.aar.truth')}</figcaption>
          <SiteMap alt={t('m.aar.truthAlt')}>
            {visibleTruth.map(({ c, p }) => (
              <g key={c.id}>
                <polyline
                  points={trail(c)}
                  fill="none"
                  stroke="var(--text-2)"
                  strokeWidth="1"
                  strokeDasharray="3 3"
                />
                <TrackSymbol identity={c.truthIdentity} x={px(p.x)} y={py(p.y)} />
                <text x={px(p.x) + 9} y={py(p.y) + 4} fontSize="10" fill="var(--text)">
                  {c.id} · {className(c.truthClass)}
                </text>
              </g>
            ))}
          </SiteMap>
        </figure>
        <div className="flex min-w-0 flex-col gap-2 lg:col-span-2 2xl:col-span-1">
          <p className="micro-label m-0">{t('m.aar.eventLog')}</p>
          <ol className="m-0 max-h-[300px] list-none overflow-y-auto border border-line p-0">
            {merged.map((e, i) => (
              <li key={`${e.t}-${i}`} className={i === lastIndex ? 'bg-surface-2' : ''}>
                <button
                  type="button"
                  onClick={() => setNow(e.t)}
                  className={`flex min-h-6 w-full items-center gap-2 border-0 bg-transparent px-2 py-0.5 text-left text-xs ${e.t <= now ? 'text-ink' : 'text-ink-2'}`}
                >
                  <span className="num shrink-0">{fmtClock(e.t)}</span>
                  <span className="shrink-0 text-ink-2">[{t(`m.aar.kind.${e.kind}`)}]</span>
                  <span>{e.text}</span>
                </button>
              </li>
            ))}
          </ol>
        </div>
      </div>

      <div className="mt-3 flex flex-wrap items-end gap-3">
        <Button onClick={() => setPlaying((p) => !p)} variant="primary">
          {playing ? t('m.aar.pause') : t('m.aar.play')}
        </Button>
        <Button
          onClick={() => {
            setPlaying(false)
            setNow(0)
          }}
        >
          {t('m.aar.restart')}
        </Button>
        <div className="w-[120px]">
          <Select
            label={t('m.aar.speed')}
            value={speed}
            options={[
              { value: '1', label: '×1' },
              { value: '4', label: '×4' },
              { value: '10', label: '×10' },
              { value: '30', label: '×30' },
            ]}
            onChange={(e) => setSpeed(e.target.value)}
          />
        </div>
        <label className="flex min-w-[240px] flex-1 flex-col gap-1 text-sm text-ink-2">
          {t('m.aar.scrub')}
          <input
            type="range"
            min={0}
            max={REPLAY_DURATION_S}
            step={1}
            value={Math.round(now)}
            onChange={(e) => setNow(Number(e.target.value))}
            aria-valuetext={fmtClock(now)}
            style={{ accentColor: 'var(--accent)' }}
          />
        </label>
      </div>

      {onAnnotate && (
        <form
          className="mt-3 flex flex-wrap items-end gap-3 border-t border-line pt-3"
          onSubmit={(e) => {
            e.preventDefault()
            const text = draft.trim()
            if (!text) return
            onAnnotate({ t: Math.round(now), text, author: t('m.aar.you') })
            setDraft('')
          }}
        >
          <div className="min-w-[260px] flex-1">
            <Input
              label={t('m.aar.annotateLabel', { time: fmtClock(now) })}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
            />
          </div>
          <Button type="submit" variant="primary">
            {t('m.aar.annotate')}
          </Button>
        </form>
      )}
    </Panel>
  )
}

/** Decision-tree path per contact: Detect, Classify, Assess, Respond and Report with reasons. */
export function DecisionPath({ session }: { session: SessionRecord }) {
  const { t } = useTranslation()
  const replay = replayFor(session)
  const [open, setOpen] = useState(replay.contacts[3]?.id ?? 'K4')
  const contact = replay.contacts.find((c) => c.id === open) ?? replay.contacts[0]
  const reasonText = (n: ScoredContact['nodes'][number]) =>
    t(`m.aar.reason.${n.reason}`, {
      ...n.params,
      called: typeof n.params.called === 'string' ? t(`live.class.${n.params.called}`) : '',
      truth: typeof n.params.truth === 'string' ? t(`live.class.${n.params.truth}`) : '',
      identity:
        typeof n.params.identity === 'string' ? t(`live.identity.${n.params.identity}`) : '',
      action: typeof n.params.action === 'string' ? t(`m.aar.action.${n.params.action}`) : '',
    })
  const summary: Column<ScoredContact>[] = [
    { key: 'id', header: t('m.aar.contact'), render: (c) => <strong>{c.id}</strong> },
    { key: 'truth', header: t('m.aar.truthClass'), render: (c) => t(`live.class.${c.truthClass}`) },
    {
      key: 'called',
      header: t('m.aar.calledClass'),
      render: (c) => t(`live.class.${c.calledClass}`),
    },
    {
      key: 'total',
      header: t('m.aar.points'),
      align: 'right',
      mono: true,
      render: (c) => `${c.total} / ${c.totalMax}`,
    },
  ]
  const nodes: Column<ScoredContact['nodes'][number]>[] = [
    { key: 'node', header: t('m.aar.node'), render: (n) => t(`m.aar.nodeName.${n.node}`) },
    {
      key: 'score',
      header: t('m.aar.points'),
      align: 'right',
      mono: true,
      render: (n) => `${n.score} / ${n.max}`,
    },
    { key: 'reason', header: t('m.aar.reasonCol'), render: (n) => reasonText(n) },
  ]
  return (
    <Panel title={t('m.aar.decisionPath')} flush>
      <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
        <div className="border-b border-line xl:border-b-0 xl:border-r">
          <Table
            caption={t('m.aar.decisionPath')}
            columns={summary}
            rows={replay.contacts}
            rowKey={(c) => c.id}
            selectedKey={open}
            onRowClick={(c) => setOpen(c.id)}
          />
        </div>
        <div>
          {contact && (
            <>
              <p className="micro-label m-0 px-3 py-2">{t('m.aar.pathFor', { id: contact.id })}</p>
              <Table
                caption={t('m.aar.pathFor', { id: contact.id })}
                columns={nodes}
                rows={contact.nodes}
                rowKey={(n) => n.node}
              />
            </>
          )}
        </div>
      </div>
    </Panel>
  )
}

export function ConfusionPanel({ trainees, title }: { trainees: Trainee[]; title: string }) {
  const { t } = useTranslation()
  const values = useMemo(() => confusionFor(trainees), [trainees])
  const labels = CLASSES.map((c) => t(`live.class.${c}`))
  return (
    <Panel title={title}>
      <Matrix
        rowLabels={labels}
        colLabels={labels}
        values={values}
        caption={title}
        rowTitle={t('m.aar.trueClass')}
        colTitle={t('m.aar.calledClass')}
      />
    </Panel>
  )
}

/** Reaction time per session for one trainee (or a set) against the mean of the full roster. */
export function ReactionPanel({ trainees, label }: { trainees: Trainee[]; label: string }) {
  const { t } = useTranslation()
  return (
    <Panel title={t('m.aar.reactionCurve')}>
      <LineChart
        alt={t('m.aar.reactionAlt')}
        xTitle={t('m.common.sessionNumber')}
        yTitle={t('m.aar.seconds')}
        yMin={0}
        series={[
          { id: 'self', label, points: curveFor(trainees, (s) => s.reactionTimeS) },
          {
            id: 'all',
            label: t('m.aar.rosterMean'),
            points: curveFor(TRAINEES, (s) => s.reactionTimeS),
          },
        ]}
        tableLabel={t('m.common.dataTable')}
      />
    </Panel>
  )
}

export function MissZonePanel({ trainees }: { trainees: Trainee[] }) {
  const { t } = useTranslation()
  const data = useMemo(() => missZones(trainees), [trainees])
  return (
    <Panel title={t('m.aar.missZone')}>
      <MissZoneMap
        data={data}
        alt={t('m.aar.missZoneAlt', { sectors: SECTORS, rings: RING_COUNT })}
        legend={t('m.aar.missLegend')}
        ringLabel={(r) => `${RING_EDGES_M[r] ?? 0}–${RING_EDGES_M[r + 1] ?? 0} m`}
        sectorLabel={(s) => `${s * 30}°–${(s + 1) * 30}°`}
        tableLabel={t('m.common.dataTable')}
      />
    </Panel>
  )
}
