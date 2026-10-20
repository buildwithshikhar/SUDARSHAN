import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  COHORTS,
  CURRICULA,
  RULES,
  RULE_DIFF,
  RULE_PACKS,
  RULE_THRESHOLDS,
  RULE_WEIGHTS,
  SCENARIOS,
  SKILLS,
  TRAINEES,
  UNITS,
  at,
  contactCount,
  curveFor,
  lastSession,
  latestSkill,
  mean,
  monitorRows,
  rankings,
  round,
  scenarioById,
  traineeById,
  type MonitorRow,
  type SessionRecord,
  type Trainee,
} from '../../mock'
import { Badge } from '../../ui/Badge'
import { Button } from '../../ui/Button'
import { Checkbox, Input, Select } from '../../ui/Field'
import { InlineAlert } from '../../ui/InlineAlert'
import { Panel } from '../../ui/Panel'
import { Table, type Column } from '../../ui/Table'
import { Segmented } from '../../ui/Segmented'
import {
  ConfusionPanel,
  MissZonePanel,
  ReactionPanel,
  ReplayPanel,
  TrackSymbol,
  type Annotation,
} from './aar'
import { RoleAssignment, SectorAssignment, TeamProvider, TeamScore, TrackHandover } from './command'
import { fmtClock, pct, shortDate, viridis } from './format'
import { Bar, Facts, Grid, LineChart, Mark, ModulePage } from './kit'
import { ReportBuilder } from './report'

// -- Cohorts -----------------------------------------------------------------------------------

function CohortList({ onOpen }: { onOpen: (id: string) => void }) {
  const { t } = useTranslation()
  const columns: Column<(typeof COHORTS)[number]>[] = [
    { key: 'n', header: t('m.cohorts.cohort'), render: (c) => c.name },
    {
      key: 'u',
      header: t('m.cohorts.unit'),
      render: (c) => UNITS.find((u) => u.id === c.unitId)?.name ?? '',
    },
    { key: 'i', header: t('m.cohorts.instructor'), render: (c) => c.instructor },
    {
      key: 'm',
      header: t('m.cohorts.members'),
      align: 'right',
      mono: true,
      render: (c) => c.traineeIds.length,
    },
    { key: 's', header: t('m.cohorts.started'), mono: true, render: (c) => c.start },
    {
      key: 'avg',
      header: t('m.common.score'),
      align: 'right',
      mono: true,
      render: (c) => mean(c.traineeIds.map((id) => lastSession(traineeById(id)).score)).toFixed(1),
    },
  ]
  return (
    <Panel title={t('m.cohorts.list')} flush>
      <Table
        caption={t('m.cohorts.list')}
        columns={columns}
        rows={COHORTS}
        rowKey={(c) => c.id}
        density="comfortable"
        onRowClick={(c) => onOpen(c.id)}
      />
    </Panel>
  )
}

function CohortDetail({ id, onPick }: { id: string; onPick: (id: string) => void }) {
  const { t } = useTranslation()
  const cohort = COHORTS.find((c) => c.id === id) ?? at(COHORTS, 0)
  const members = cohort.traineeIds.map(traineeById)
  const course = CURRICULA.find((c) => c.id === cohort.curriculumId) ?? at(CURRICULA, 0)
  return (
    <div className="flex flex-col gap-4">
      <div className="max-w-[320px]">
        <Select
          label={t('m.cohorts.cohort')}
          value={cohort.id}
          options={COHORTS.map((c) => ({ value: c.id, label: c.name }))}
          onChange={(e) => onPick(e.target.value)}
        />
      </div>
      <Grid cols={2}>
        <Panel title={t('m.cohorts.members')} flush>
          <Table
            caption={t('m.cohorts.members')}
            columns={[
              {
                key: 'n',
                header: t('m.common.trainee'),
                render: (x: Trainee) => `${x.name} (${x.callSign})`,
              },
              {
                key: 's',
                header: t('m.common.sessions'),
                align: 'right',
                mono: true,
                render: (x: Trainee) => x.sessions.length,
              },
              {
                key: 'sc',
                header: t('m.common.score'),
                align: 'right',
                mono: true,
                render: (x: Trainee) => lastSession(x).score.toFixed(1),
              },
            ]}
            rows={members}
            rowKey={(x) => x.id}
          />
        </Panel>
        <Panel title={t('m.cohorts.assigned')}>
          <Facts
            rows={[
              { label: t('m.drills.course'), value: course.name },
              { label: t('m.drills.stages'), value: course.stages.length },
              { label: t('m.cohorts.instructor'), value: cohort.instructor },
              { label: t('m.cohorts.started'), value: cohort.start },
            ]}
          />
        </Panel>
      </Grid>
      <Panel title={t('m.cohorts.sequence')}>
        <ol className="m-0 flex list-none flex-wrap gap-3 p-0">
          {course.stages.map((s, i) => (
            <li key={s.id} className="min-w-[200px] flex-1 border border-line p-3">
              <p className="m-0 mb-1 text-sm font-semibold">{t('m.drills.stage', { n: i + 1 })}</p>
              <ul className="m-0 list-none p-0 text-sm">
                {s.scenarioIds.map((sid) => (
                  <li key={sid}>{scenarioById(sid).name}</li>
                ))}
              </ul>
            </li>
          ))}
        </ol>
      </Panel>
    </div>
  )
}

export function Cohorts() {
  const { t } = useTranslation()
  const [id, setId] = useState(at(COHORTS, 0).id)
  const [, setParams] = useSearchParams()
  return (
    <ModulePage
      group="class"
      module="cohorts"
      tabs={[
        {
          id: 'list',
          label: t('m.cohorts.list'),
          panel: (
            <CohortList
              onOpen={(c) => {
                setId(c)
                setParams({ s: 'detail' })
              }}
            />
          ),
        },
        {
          id: 'detail',
          label: t('m.cohorts.detail'),
          panel: <CohortDetail id={id} onPick={setId} />,
        },
      ]}
    />
  )
}

// -- Trainees ----------------------------------------------------------------------------------

function TraineeList() {
  const { t } = useTranslation()
  const [cohort, setCohort] = useState('all')
  const [query, setQuery] = useState('')
  const rows = rankings(TRAINEES).filter(
    (r) =>
      (cohort === 'all' || r.trainee.cohortId === cohort) &&
      `${r.trainee.name} ${r.trainee.callSign}`.toLowerCase().includes(query.toLowerCase()),
  )
  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end gap-4">
        <div className="w-[260px]">
          <Select
            label={t('m.cohorts.cohort')}
            value={cohort}
            options={[
              { value: 'all', label: t('m.common.all') },
              ...COHORTS.map((c) => ({ value: c.id, label: c.name })),
            ]}
            onChange={(e) => setCohort(e.target.value)}
          />
        </div>
        <div className="w-[260px]">
          <Input
            label={t('m.common.search')}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
      </div>
      <Panel title={t('m.trainees.list', { count: rows.length })} flush>
        <Table
          caption={t('m.trainees.list', { count: rows.length })}
          columns={[
            { key: 'r', header: '#', mono: true, render: (r: (typeof rows)[number]) => r.rank },
            {
              key: 'n',
              header: t('m.common.trainee'),
              render: (r: (typeof rows)[number]) => r.trainee.name,
            },
            {
              key: 'c',
              header: t('m.trainees.callSign'),
              render: (r: (typeof rows)[number]) => r.trainee.callSign,
            },
            {
              key: 'co',
              header: t('m.cohorts.cohort'),
              render: (r: (typeof rows)[number]) =>
                COHORTS.find((c) => c.id === r.trainee.cohortId)?.name ?? '',
            },
            {
              key: 's',
              header: t('m.common.score'),
              align: 'right',
              mono: true,
              render: (r: (typeof rows)[number]) => r.score.toFixed(1),
            },
            {
              key: 'd',
              header: t('m.common.change'),
              align: 'right',
              mono: true,
              render: (r: (typeof rows)[number]) =>
                `${r.delta >= 0 ? '+' : ''}${r.delta.toFixed(1)}`,
            },
            {
              key: 'a',
              header: t('m.common.accuracy'),
              align: 'right',
              mono: true,
              render: (r: (typeof rows)[number]) => pct(r.accuracy),
            },
          ]}
          rows={rows}
          rowKey={(r) => r.trainee.id}
          empty={<p className="m-0 p-3 text-sm text-ink-2">{t('m.common.noMatch')}</p>}
        />
      </Panel>
    </div>
  )
}

function TraineeProfile() {
  const { t } = useTranslation()
  const [id, setId] = useState(at(TRAINEES, 1).id)
  const trainee = traineeById(id)
  const [notes, setNotes] = useState<
    Record<string, { date: string; author: string; text: string }[]>
  >({})
  const [draft, setDraft] = useState('')
  const list = [...trainee.notes, ...(notes[id] ?? [])]
  return (
    <div className="flex flex-col gap-4">
      <div className="max-w-[320px]">
        <Select
          label={t('m.common.trainee')}
          value={id}
          options={TRAINEES.map((x) => ({ value: x.id, label: `${x.name} (${x.callSign})` }))}
          onChange={(e) => setId(e.target.value)}
        />
      </div>
      <Grid cols={2}>
        <Panel title={t('m.trainees.skillModel')}>
          {SKILLS.map((k) => (
            <Bar
              key={k}
              label={t(`m.skill.${k}`)}
              value={at(trainee.skills[k], 3)}
              text={pct(at(trainee.skills[k], 3))}
            />
          ))}
        </Panel>
        <Panel title={t('m.trainees.history')} flush>
          <Table
            caption={t('m.trainees.history')}
            columns={[
              {
                key: 'd',
                header: t('m.common.date'),
                mono: true,
                render: (s: SessionRecord) => s.date,
              },
              {
                key: 'sc',
                header: t('m.common.scenario'),
                render: (s: SessionRecord) => scenarioById(s.scenarioId).name,
              },
              {
                key: 'm',
                header: t('m.common.mode'),
                render: (s: SessionRecord) => t(`m.mode.${s.mode}`),
              },
              {
                key: 's',
                header: t('m.common.score'),
                align: 'right',
                mono: true,
                render: (s: SessionRecord) => s.score.toFixed(1),
              },
            ]}
            rows={trainee.sessions}
            rowKey={(s) => s.id}
          />
        </Panel>
      </Grid>
      <Panel title={t('m.trainees.notes')}>
        {list.length === 0 && (
          <p className="m-0 mb-3 text-sm text-ink-2">{t('m.trainees.noNotes')}</p>
        )}
        <ul className="m-0 mb-3 flex list-none flex-col gap-2 p-0">
          {list.map((n, i) => (
            <li key={`${n.date}-${i}`} className="border-l-2 border-line pl-3 text-sm">
              <span className="num text-xs text-ink-2">
                {n.date} · {n.author}
              </span>
              <br />
              {n.text}
            </li>
          ))}
        </ul>
        <form
          className="flex flex-wrap items-end gap-3"
          onSubmit={(e) => {
            e.preventDefault()
            if (!draft.trim()) return
            setNotes({
              ...notes,
              [id]: [
                ...(notes[id] ?? []),
                { date: '2026-10-12', author: t('m.aar.you'), text: draft.trim() },
              ],
            })
            setDraft('')
          }}
        >
          <div className="min-w-[280px] flex-1">
            <Input
              label={t('m.trainees.addNote')}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
            />
          </div>
          <Button type="submit" variant="primary">
            {t('m.trainees.saveNote')}
          </Button>
        </form>
      </Panel>
    </div>
  )
}

export function Trainees() {
  const { t } = useTranslation()
  return (
    <ModulePage
      group="class"
      module="trainees"
      tabs={[
        { id: 'list', label: t('m.trainees.listTab'), panel: <TraineeList /> },
        { id: 'profile', label: t('m.trainees.profile'), panel: <TraineeProfile /> },
      ]}
    />
  )
}

// -- Live sessions -----------------------------------------------------------------------------

function LaunchSession({ onLaunched }: { onLaunched: () => void }) {
  const { t } = useTranslation()
  const [scenario, setScenario] = useState('sc-04')
  const [cohort, setCohort] = useState('co-kestrel')
  const [mode, setMode] = useState<'assessed' | 'practice'>('assessed')
  const [picked, setPicked] = useState<Record<string, boolean>>({})
  const [team, setTeam] = useState(false)
  const sc = scenarioById(scenario)
  const members = (COHORTS.find((c) => c.id === cohort)?.traineeIds ?? []).map(traineeById)
  const chosen = members.filter((m) => picked[m.id] !== false)
  return (
    <Grid cols={2}>
      <Panel title={t('m.live.launch')}>
        <div className="flex max-w-[420px] flex-col gap-4">
          <Select
            label={t('m.common.scenario')}
            value={scenario}
            options={SCENARIOS.map((s) => ({ value: s.id, label: s.name }))}
            onChange={(e) => setScenario(e.target.value)}
          />
          <Select
            label={t('m.cohorts.cohort')}
            value={cohort}
            options={COHORTS.map((c) => ({ value: c.id, label: c.name }))}
            onChange={(e) => {
              setCohort(e.target.value)
              setPicked({})
            }}
          />
          <Segmented
            label={t('m.common.mode')}
            value={mode}
            options={[
              { value: 'assessed', label: t('m.mode.assessed') },
              { value: 'practice', label: t('m.mode.practice') },
            ]}
            onChange={setMode}
          />
          <Checkbox
            label={t('m.live.teamMode')}
            checked={team}
            onChange={(e) => setTeam(e.target.checked)}
          />
          <Button variant="primary" onClick={onLaunched} disabled={chosen.length === 0}>
            {t('m.live.start', { count: chosen.length })}
          </Button>
        </div>
      </Panel>
      <div className="flex flex-col gap-4">
        <Panel title={t('m.live.scenarioSummary')}>
          <Facts
            rows={[
              { label: t('m.common.scenario'), value: sc.name },
              { label: t('m.common.terrain'), value: sc.terrain },
              { label: t('m.common.time'), value: t(`m.tod.${sc.timeOfDay}`) },
              { label: t('m.common.weather'), value: t(`live.weather.${sc.weather}`) },
              { label: t('m.common.difficulty'), value: `${sc.difficulty} / 5` },
              { label: t('m.common.contacts'), value: contactCount(sc) },
              { label: t('m.common.duration'), value: fmtClock(sc.durationS) },
            ]}
          />
        </Panel>
        <Panel title={t('m.live.participants')}>
          <fieldset className="m-0 flex flex-col gap-2 border-0 p-0">
            <legend className="sr-only">{t('m.live.participants')}</legend>
            {members.map((m) => (
              <Checkbox
                key={m.id}
                label={`${m.name} (${m.callSign})`}
                checked={picked[m.id] !== false}
                onChange={(e) => setPicked({ ...picked, [m.id]: e.target.checked })}
              />
            ))}
          </fieldset>
        </Panel>
      </div>
    </Grid>
  )
}

interface LogEntry {
  id: number
  clock: number
  kind: 'inject' | 'annotate' | 'pause' | 'resume'
  text: string
}

function LiveMonitor() {
  const { t } = useTranslation()
  const [tick, setTick] = useState(112)
  const [paused, setPaused] = useState(false)
  const [selected, setSelected] = useState(at(TRAINEES, 0).id)
  const [log, setLog] = useState<LogEntry[]>([])
  const [inject, setInject] = useState('contact')
  const [note, setNote] = useState('')
  useEffect(() => {
    if (paused) return undefined
    const id = window.setInterval(() => setTick((n) => (n >= 358 ? 0 : n + 1)), 1000)
    return () => window.clearInterval(id)
  }, [paused])
  const rows = useMemo(() => monitorRows(tick), [tick])
  const row = rows.find((r) => r.id === selected) ?? at(rows, 0)
  const push = (kind: LogEntry['kind'], text: string) =>
    setLog((l) => [{ id: l.length + 1, clock: tick, kind, text }, ...l])
  const sc = scenarioById('sc-04')
  const truth = useMemo(() => replayContacts(row.elapsedS), [row.elapsedS])

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-3">
        <Badge tone={paused ? 'warning' : 'neutralTrack'}>
          {paused ? t('m.live.paused') : t('m.live.running')}
        </Badge>
        <span className="num text-sm">
          {sc.name} · {fmtClock(tick)}
        </span>
        <Button
          onClick={() => {
            setPaused(!paused)
            push(paused ? 'resume' : 'pause', t(paused ? 'm.live.log.resume' : 'm.live.log.pause'))
          }}
        >
          {paused ? t('m.live.resume') : t('m.live.pause')}
        </Button>
      </div>
      <Panel title={t('m.live.classGrid')}>
        <ul className="m-0 grid list-none grid-cols-1 gap-3 p-0 sm:grid-cols-2 xl:grid-cols-4">
          {rows.map((r) => (
            <li key={r.id}>
              <button
                type="button"
                aria-pressed={r.id === selected}
                onClick={() => setSelected(r.id)}
                className={`w-full border p-3 text-left ${r.id === selected ? 'border-accent bg-surface-2' : 'border-line bg-surface-1'}`}
              >
                <span className="flex items-center justify-between">
                  <span className="text-sm font-semibold">{r.callSign}</span>
                  {r.attention ? (
                    <Mark ok={false} label={t('m.live.attention')} />
                  ) : (
                    <Mark ok label={t('m.live.onTrack')} />
                  )}
                </span>
                <span className="block text-xs text-ink-2">{r.name}</span>
                <span className="num mt-2 grid grid-cols-3 gap-2 text-xs">
                  <span>
                    <span className="block text-ink-2">{t('m.live.stage')}</span>
                    {t(`m.aar.nodeName.${r.stage}`)}
                  </span>
                  <span>
                    <span className="block text-ink-2">{t('m.live.tracks')}</span>
                    {r.tracks}
                  </span>
                  <span>
                    <span className="block text-ink-2">{t('m.common.score')}</span>
                    {r.score.toFixed(1)}
                  </span>
                </span>
              </button>
            </li>
          ))}
        </ul>
      </Panel>
      <Grid cols={2}>
        <DrillDown row={row} truth={truth} />
        <div className="flex flex-col gap-4">
          <Panel title={t('m.live.inject')}>
            <form
              className="flex flex-wrap items-end gap-3"
              onSubmit={(e) => {
                e.preventDefault()
                push(
                  'inject',
                  t('m.live.log.inject', {
                    what: t(`m.live.injection.${inject}`),
                    who: row.callSign,
                  }),
                )
              }}
            >
              <div className="min-w-[200px] flex-1">
                <Select
                  label={t('m.live.event')}
                  value={inject}
                  options={['contact', 'degrade', 'weather', 'comms'].map((k) => ({
                    value: k,
                    label: t(`m.live.injection.${k}`),
                  }))}
                  onChange={(e) => setInject(e.target.value)}
                />
              </div>
              <Button type="submit" variant="primary">
                {t('m.live.injectNow')}
              </Button>
            </form>
          </Panel>
          <Panel title={t('m.live.annotate')}>
            <form
              className="flex flex-wrap items-end gap-3"
              onSubmit={(e) => {
                e.preventDefault()
                if (!note.trim()) return
                push('annotate', `${row.callSign}: ${note.trim()}`)
                setNote('')
              }}
            >
              <div className="min-w-[200px] flex-1">
                <Input
                  label={t('m.live.annotateLabel', { clock: fmtClock(tick) })}
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                />
              </div>
              <Button type="submit">{t('m.aar.annotate')}</Button>
            </form>
          </Panel>
          <Panel title={t('m.live.timeline')} flush>
            {log.length === 0 ? (
              <p className="m-0 p-3 text-sm text-ink-2">{t('m.live.timelineEmpty')}</p>
            ) : (
              <ol className="m-0 max-h-[200px] list-none overflow-y-auto p-0">
                {log.map((e) => (
                  <li
                    key={e.id}
                    className="flex gap-2 border-b border-line px-3 py-1 text-xs last:border-b-0"
                  >
                    <span className="num shrink-0">{fmtClock(e.clock)}</span>
                    <span className="shrink-0 text-ink-2">[{t(`m.live.kind.${e.kind}`)}]</span>
                    <span>{e.text}</span>
                  </li>
                ))}
              </ol>
            )}
          </Panel>
        </div>
      </Grid>
    </div>
  )
}

function replayContacts(elapsed: number) {
  const out: { id: string; identity: 'hostile' | 'neutral'; x: number; y: number }[] = []
  const base = [
    { id: 'K1', identity: 'hostile' as const, ax: 2200, ay: 1500, bx: 380, by: 260 },
    { id: 'K2', identity: 'neutral' as const, ax: -1700, ay: 900, bx: -1300, by: 500 },
    { id: 'K3', identity: 'neutral' as const, ax: -2000, ay: -1100, bx: 2000, by: -900 },
  ]
  for (const b of base) {
    const k = Math.min(1, elapsed / 300)
    out.push({
      id: b.id,
      identity: b.identity,
      x: b.ax + (b.bx - b.ax) * k,
      y: b.ay + (b.by - b.ay) * k,
    })
  }
  return out
}

function DrillDown({ row, truth }: { row: MonitorRow; truth: ReturnType<typeof replayContacts> }) {
  const { t } = useTranslation()
  const S = 300
  const H = S / 2
  const k = (H - 14) / 2600
  return (
    <Panel title={t('m.live.drill', { name: row.callSign })}>
      <svg
        viewBox={`0 0 ${S} ${S}`}
        role="img"
        aria-label={t('m.live.drillAlt', { name: row.callSign })}
        className="block h-auto w-full max-w-[360px] bg-bg"
      >
        <circle
          cx={H}
          cy={H}
          r={1500 * k}
          fill="none"
          stroke="var(--border)"
          strokeDasharray="4 3"
        />
        <circle cx={H} cy={H} r={500 * k} fill="none" stroke="var(--signal)" />
        <rect x={H - 4} y={H - 4} width="8" height="8" fill="var(--accent)" />
        {truth.map((c) => (
          <g key={c.id}>
            <TrackSymbol identity={c.identity} x={H + c.x * k} y={H - c.y * k} />
            <text x={H + c.x * k + 9} y={H - c.y * k + 4} fontSize="10" fill="var(--text)">
              {c.id}
            </text>
          </g>
        ))}
      </svg>
      <p className="micro-label m-0 mt-2">{t('m.live.overlay')}</p>
    </Panel>
  )
}

function CompareSessions() {
  const { t } = useTranslation()
  const all = TRAINEES.flatMap((x) => x.sessions.map((s) => ({ s, who: x })))
  const [a, setA] = useState(at(all, 3).s.id)
  const [b, setB] = useState(at(all, 7).s.id)
  const sa = all.find((x) => x.s.id === a) ?? at(all, 3)
  const sb = all.find((x) => x.s.id === b) ?? at(all, 7)
  const options = all.map((x) => ({
    value: x.s.id,
    label: `${x.who.callSign} · ${shortDate(x.s.date)} · ${scenarioById(x.s.scenarioId).name}`,
  }))
  const metrics: {
    key: string
    label: string
    pick: (s: SessionRecord) => number
    fmt: (n: number) => string
    better: 'high' | 'low'
  }[] = [
    {
      key: 'score',
      label: t('m.common.score'),
      pick: (s) => s.score,
      fmt: (n) => n.toFixed(1),
      better: 'high',
    },
    {
      key: 'det',
      label: t('m.common.detectTime'),
      pick: (s) => s.detectTimeS,
      fmt: (n) => `${n.toFixed(1)} s`,
      better: 'low',
    },
    {
      key: 'cls',
      label: t('m.common.classifyTime'),
      pick: (s) => s.classifyTimeS,
      fmt: (n) => `${n.toFixed(1)} s`,
      better: 'low',
    },
    {
      key: 'acc',
      label: t('m.common.accuracy'),
      pick: (s) => s.classifyAccuracy,
      fmt: (n) => pct(n),
      better: 'high',
    },
    {
      key: 'fa',
      label: t('m.common.falseAlarms'),
      pick: (s) => s.falseAlarms,
      fmt: (n) => String(n),
      better: 'low',
    },
    {
      key: 'roe',
      label: t('m.common.roe'),
      pick: (s) => s.roeCompliance,
      fmt: (n) => pct(n),
      better: 'high',
    },
  ]
  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <Select
          label={t('m.compare.sessionA')}
          value={a}
          options={options}
          onChange={(e) => setA(e.target.value)}
        />
        <Select
          label={t('m.compare.sessionB')}
          value={b}
          options={options}
          onChange={(e) => setB(e.target.value)}
        />
      </div>
      <Panel title={t('m.compare.metrics')} flush>
        <Table
          caption={t('m.compare.metrics')}
          columns={[
            {
              key: 'm',
              header: t('m.compare.metric'),
              render: (m: (typeof metrics)[number]) => m.label,
            },
            {
              key: 'a',
              header: `A · ${sa.who.callSign}`,
              align: 'right',
              mono: true,
              render: (m: (typeof metrics)[number]) => m.fmt(m.pick(sa.s)),
            },
            {
              key: 'b',
              header: `B · ${sb.who.callSign}`,
              align: 'right',
              mono: true,
              render: (m: (typeof metrics)[number]) => m.fmt(m.pick(sb.s)),
            },
            {
              key: 'd',
              header: t('m.compare.better'),
              render: (m: (typeof metrics)[number]) => {
                const da = m.pick(sa.s)
                const db = m.pick(sb.s)
                if (da === db) return t('m.compare.equal')
                const aBetter = m.better === 'high' ? da > db : da < db
                return aBetter ? 'A' : 'B'
              },
            },
          ]}
          rows={metrics}
          rowKey={(m) => m.key}
        />
      </Panel>
    </div>
  )
}

export function LiveSessions() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  return (
    <ModulePage
      group="run"
      module="live-sessions"
      tabs={[
        {
          id: 'launch',
          label: t('m.live.launchTab'),
          panel: (
            <LaunchSession onLaunched={() => navigate('/instructor/live-sessions?s=monitor')} />
          ),
        },
        { id: 'monitor', label: t('m.live.monitor'), panel: <LiveMonitor /> },
        { id: 'compare', label: t('m.compare.sessions'), panel: <CompareSessions /> },
      ]}
    />
  )
}

// -- Team exercise -----------------------------------------------------------------------------

export function TeamExercise() {
  const { t } = useTranslation()
  return (
    <TeamProvider>
      <ModulePage
        group="run"
        module="team-exercise"
        tabs={[
          {
            id: 'setup',
            label: t('m.team.setup'),
            panel: (
              <div className="flex flex-col gap-4">
                <RoleAssignment />
                <SectorAssignment />
              </div>
            ),
          },
          {
            id: 'monitor',
            label: t('m.team.monitor'),
            panel: (
              <div className="flex flex-col gap-4">
                <TrackHandover role="monitor" />
                <TeamScore />
              </div>
            ),
          },
        ]}
      />
    </TeamProvider>
  )
}

// -- Rule packs and curricula ------------------------------------------------------------------

function RulePackList({ onOpen }: { onOpen: () => void }) {
  const { t } = useTranslation()
  return (
    <Panel title={t('m.rules.list')} flush>
      <Table
        caption={t('m.rules.list')}
        columns={[
          {
            key: 'n',
            header: t('m.rules.pack'),
            render: (r: (typeof RULE_PACKS)[number]) => r.name,
          },
          {
            key: 'v',
            header: t('m.common.version'),
            mono: true,
            render: (r: (typeof RULE_PACKS)[number]) => r.version,
          },
          {
            key: 'r',
            header: t('m.rules.rules'),
            align: 'right',
            mono: true,
            render: (r: (typeof RULE_PACKS)[number]) => r.rules,
          },
          {
            key: 'u',
            header: t('m.common.updated'),
            mono: true,
            render: (r: (typeof RULE_PACKS)[number]) => r.updated,
          },
          {
            key: 'a',
            header: t('m.rules.author'),
            render: (r: (typeof RULE_PACKS)[number]) => r.author,
          },
          {
            key: 'i',
            header: t('m.rules.inUse'),
            align: 'right',
            mono: true,
            render: (r: (typeof RULE_PACKS)[number]) => r.inUse,
          },
        ]}
        rows={RULE_PACKS}
        rowKey={(r) => r.id}
        density="comfortable"
        onRowClick={onOpen}
      />
    </Panel>
  )
}

function RulePackEditor() {
  const { t } = useTranslation()
  const [weights, setWeights] = useState<Record<string, string>>(
    Object.fromEntries(Object.entries(RULE_WEIGHTS).map(([k, v]) => [k, String(v)])),
  )
  const [thresholds, setThresholds] = useState<Record<string, string>>(
    Object.fromEntries(Object.entries(RULE_THRESHOLDS).map(([k, v]) => [k, String(v)])),
  )
  const [saved, setSaved] = useState(false)
  const sum = Object.values(weights).reduce((a, v) => a + (Number(v) || 0), 0)
  const valid = Math.abs(sum - 1) < 0.001
  return (
    <div className="flex flex-col gap-4">
      <Grid cols={2}>
        <Panel title={t('m.rules.weights')}>
          <div className="grid max-w-[360px] grid-cols-2 gap-3">
            {Object.keys(weights).map((k) => (
              <Input
                key={k}
                label={t(`m.aar.nodeName.${k}`)}
                inputMode="decimal"
                value={weights[k] ?? ''}
                onChange={(e) => {
                  setSaved(false)
                  setWeights({ ...weights, [k]: e.target.value })
                }}
                className="num"
              />
            ))}
          </div>
          <p className="num m-0 mt-3 text-sm">
            <Mark
              ok={valid}
              label={t(valid ? 'm.rules.sumOk' : 'm.rules.sumBad', { sum: round(sum, 2) })}
            />
          </p>
        </Panel>
        <Panel title={t('m.rules.thresholds')}>
          <div className="grid max-w-[360px] grid-cols-2 gap-3">
            {Object.keys(thresholds).map((k) => (
              <Input
                key={k}
                label={t(`m.rules.threshold.${k}`)}
                inputMode="numeric"
                value={thresholds[k] ?? ''}
                onChange={(e) => {
                  setSaved(false)
                  setThresholds({ ...thresholds, [k]: e.target.value })
                }}
                className="num"
              />
            ))}
          </div>
        </Panel>
      </Grid>
      <Panel title={t('m.rules.roe')} flush>
        <Table
          caption={t('m.rules.roe')}
          columns={[
            {
              key: 'id',
              header: t('m.rules.ruleId'),
              mono: true,
              render: (r: (typeof RULES)[number]) => r.id,
            },
            {
              key: 't',
              header: t('m.rules.ruleTitle'),
              render: (r: (typeof RULES)[number]) => t(`m.rules.rule.${r.titleKey}`),
            },
            {
              key: 'w',
              header: t('m.rules.when'),
              mono: true,
              render: (r: (typeof RULES)[number]) => r.when,
            },
            {
              key: 'a',
              header: t('m.rules.authority'),
              render: (r: (typeof RULES)[number]) => t(`m.team.${r.authority}`),
            },
            {
              key: 'p',
              header: t('m.rules.permits'),
              render: (r: (typeof RULES)[number]) =>
                r.permits.map((p) => t(`m.aar.action.${p}`)).join(', '),
            },
          ]}
          rows={RULES}
          rowKey={(r) => r.id}
        />
      </Panel>
      <Panel title={t('m.rules.diff')} flush>
        <Table
          caption={t('m.rules.diff')}
          columns={[
            {
              key: 'k',
              header: t('m.rules.field'),
              mono: true,
              render: (r: (typeof RULE_DIFF)[number]) => r.key,
            },
            {
              key: 'f',
              header: 'v1.1.0',
              align: 'right',
              mono: true,
              render: (r: (typeof RULE_DIFF)[number]) => r.from,
            },
            {
              key: 't',
              header: 'v1.2.0',
              align: 'right',
              mono: true,
              render: (r: (typeof RULE_DIFF)[number]) => r.to,
            },
          ]}
          rows={RULE_DIFF}
          rowKey={(r) => r.key}
        />
      </Panel>
      <div className="flex items-center gap-3">
        <Button variant="primary" disabled={!valid} onClick={() => setSaved(true)}>
          {t('m.rules.save')}
        </Button>
        {saved && <InlineAlert tone="success">{t('m.rules.saved')}</InlineAlert>}
      </div>
    </div>
  )
}

export function RulePacks() {
  const { t } = useTranslation()
  return (
    <ModulePage
      group="content"
      module="rule-packs"
      tabs={[
        {
          id: 'list',
          label: t('m.rules.listTab'),
          panel: <RulePackList onOpen={() => undefined} />,
        },
        { id: 'editor', label: t('m.rules.editor'), panel: <RulePackEditor /> },
      ]}
    />
  )
}

function CurriculumList() {
  const { t } = useTranslation()
  return (
    <Panel title={t('m.curricula.list')} flush>
      <Table
        caption={t('m.curricula.list')}
        columns={[
          {
            key: 'n',
            header: t('m.drills.course'),
            render: (c: (typeof CURRICULA)[number]) => c.name,
          },
          {
            key: 's',
            header: t('m.drills.stages'),
            align: 'right',
            mono: true,
            render: (c: (typeof CURRICULA)[number]) => c.stages.length,
          },
          {
            key: 'sc',
            header: t('m.drills.scenarios'),
            align: 'right',
            mono: true,
            render: (c: (typeof CURRICULA)[number]) =>
              c.stages.reduce((a, s) => a + s.scenarioIds.length, 0),
          },
          {
            key: 'co',
            header: t('m.curricula.cohorts'),
            align: 'right',
            mono: true,
            render: (c: (typeof CURRICULA)[number]) =>
              COHORTS.filter((x) => x.curriculumId === c.id).length,
          },
        ]}
        rows={CURRICULA}
        rowKey={(c) => c.id}
        density="comfortable"
      />
    </Panel>
  )
}

function CurriculumEditor() {
  const { t } = useTranslation()
  const [id, setId] = useState(at(CURRICULA, 0).id)
  const course = CURRICULA.find((c) => c.id === id) ?? at(CURRICULA, 0)
  const [gates, setGates] = useState<Record<string, { score: string; acc: string }>>({})
  const [saved, setSaved] = useState(false)
  return (
    <div className="flex flex-col gap-4">
      <div className="max-w-[320px]">
        <Select
          label={t('m.drills.course')}
          value={id}
          options={CURRICULA.map((c) => ({ value: c.id, label: c.name }))}
          onChange={(e) => {
            setId(e.target.value)
            setSaved(false)
          }}
        />
      </div>
      <Panel title={t('m.curricula.stagesGates')}>
        <ol className="m-0 flex list-none flex-col gap-3 p-0">
          {course.stages.map((s, i) => {
            const key = `${id}-${s.id}`
            const g = gates[key] ?? {
              score: String(s.gate.minScore),
              acc: String(Math.round(s.gate.minAccuracy * 100)),
            }
            return (
              <li
                key={s.id}
                className="grid grid-cols-1 gap-3 border border-line p-3 lg:grid-cols-[1fr_160px_160px]"
              >
                <div>
                  <p className="m-0 text-sm font-semibold">{t('m.drills.stage', { n: i + 1 })}</p>
                  <p className="m-0 text-sm text-ink-2">
                    {s.scenarioIds.map((sid) => scenarioById(sid).name).join(' · ')}
                  </p>
                </div>
                <Input
                  label={t('m.curricula.minScore')}
                  inputMode="numeric"
                  className="num"
                  value={g.score}
                  onChange={(e) => {
                    setSaved(false)
                    setGates({ ...gates, [key]: { ...g, score: e.target.value } })
                  }}
                />
                <Input
                  label={t('m.curricula.minAccuracy')}
                  inputMode="numeric"
                  className="num"
                  value={g.acc}
                  onChange={(e) => {
                    setSaved(false)
                    setGates({ ...gates, [key]: { ...g, acc: e.target.value } })
                  }}
                />
              </li>
            )
          })}
        </ol>
      </Panel>
      <div className="flex items-center gap-3">
        <Button variant="primary" onClick={() => setSaved(true)}>
          {t('m.curricula.save')}
        </Button>
        {saved && <InlineAlert tone="success">{t('m.curricula.saved')}</InlineAlert>}
      </div>
    </div>
  )
}

export function Curricula() {
  const { t } = useTranslation()
  return (
    <ModulePage
      group="content"
      module="curricula"
      tabs={[
        { id: 'list', label: t('m.curricula.listTab'), panel: <CurriculumList /> },
        { id: 'editor', label: t('m.curricula.editor'), panel: <CurriculumEditor /> },
      ]}
    />
  )
}

// -- Unit AAR ----------------------------------------------------------------------------------

function UnitDashboard() {
  const { t } = useTranslation()
  const [cohort, setCohort] = useState('all')
  const group = cohort === 'all' ? TRAINEES : TRAINEES.filter((x) => x.cohortId === cohort)
  const ranks = rankings(group)
  return (
    <div className="flex flex-col gap-4">
      <div className="max-w-[320px]">
        <Select
          label={t('m.cohorts.cohort')}
          value={cohort}
          options={[
            { value: 'all', label: t('m.common.all') },
            ...COHORTS.map((c) => ({ value: c.id, label: c.name })),
          ]}
          onChange={(e) => setCohort(e.target.value)}
        />
      </div>
      <Grid cols={2}>
        <Panel title={t('m.unit.trends')}>
          <LineChart
            alt={t('m.unit.trendAlt')}
            xTitle={t('m.common.sessionNumber')}
            yTitle={t('m.common.score')}
            yMin={0}
            yMax={100}
            series={[
              { id: 'score', label: t('m.common.score'), points: curveFor(group, (s) => s.score) },
              {
                id: 'acc',
                label: t('m.perf.accuracyPct'),
                points: curveFor(group, (s) => s.classifyAccuracy * 100),
              },
            ]}
            tableLabel={t('m.common.dataTable')}
          />
        </Panel>
        <Panel title={t('m.unit.rankings')} flush>
          <Table
            caption={t('m.unit.rankings')}
            columns={[
              { key: 'r', header: '#', mono: true, render: (r: (typeof ranks)[number]) => r.rank },
              {
                key: 'n',
                header: t('m.common.trainee'),
                render: (r: (typeof ranks)[number]) => r.trainee.name,
              },
              {
                key: 's',
                header: t('m.common.score'),
                align: 'right',
                mono: true,
                render: (r: (typeof ranks)[number]) => r.score.toFixed(1),
              },
              {
                key: 'd',
                header: t('m.common.change'),
                align: 'right',
                mono: true,
                render: (r: (typeof ranks)[number]) =>
                  `${r.delta >= 0 ? '+' : ''}${r.delta.toFixed(1)}`,
              },
            ]}
            rows={ranks}
            rowKey={(r) => r.trainee.id}
          />
        </Panel>
      </Grid>
      <SkillHeat trainees={group} />
      <Grid cols={2}>
        <MissZonePanel trainees={group} />
        <ConfusionPanel trainees={group} title={t('m.aar.confusion')} />
      </Grid>
    </div>
  )
}

function SkillHeat({ trainees }: { trainees: Trainee[] }) {
  const { t } = useTranslation()
  return (
    <Panel title={t('m.unit.skillHeat')}>
      <div className="overflow-x-auto">
        <table className="num w-full border-collapse text-center text-xs">
          <caption className="sr-only">{t('m.unit.skillHeat')}</caption>
          <thead>
            <tr>
              <th scope="col" className="h-8 text-left font-medium text-ink-2">
                {t('m.common.trainee')}
              </th>
              {SKILLS.map((k) => (
                <th key={k} scope="col" className="h-8 px-1 align-bottom font-medium text-ink-2">
                  <span className="block max-w-[72px] break-words leading-tight">
                    {t(`m.skill.${k}`)}
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {trainees.map((x) => (
              <tr key={x.id}>
                <th scope="row" className="h-7 pr-2 text-left font-normal">
                  {x.callSign}
                </th>
                {SKILLS.map((k) => {
                  const v = at(x.skills[k], 3)
                  return (
                    <td
                      key={k}
                      className="h-7 border border-line"
                      style={{ background: viridis(v) }}
                    >
                      <span className="inline-block min-w-[28px] bg-surface-1 px-1 text-ink">
                        {Math.round(v * 100)}
                      </span>
                    </td>
                  )
                })}
              </tr>
            ))}
            <tr>
              <th scope="row" className="h-7 pr-2 text-left font-semibold">
                {t('m.unit.mean')}
              </th>
              {SKILLS.map((k) => (
                <td key={k} className="h-7 border border-line font-semibold">
                  {Math.round(latestSkill(trainees, k) * 100)}
                </td>
              ))}
            </tr>
          </tbody>
        </table>
      </div>
    </Panel>
  )
}

function CompareTrainees() {
  const { t } = useTranslation()
  const [a, setA] = useState(at(TRAINEES, 0).id)
  const [b, setB] = useState(at(TRAINEES, 6).id)
  const ta = traineeById(a)
  const tb = traineeById(b)
  const options = TRAINEES.map((x) => ({ value: x.id, label: `${x.name} (${x.callSign})` }))
  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <Select
          label={t('m.compare.traineeA')}
          value={a}
          options={options}
          onChange={(e) => setA(e.target.value)}
        />
        <Select
          label={t('m.compare.traineeB')}
          value={b}
          options={options}
          onChange={(e) => setB(e.target.value)}
        />
      </div>
      <Grid cols={2}>
        <Panel title={t('m.perf.learningCurves')}>
          <LineChart
            alt={t('m.perf.learningAlt')}
            xTitle={t('m.common.sessionNumber')}
            yTitle={t('m.common.score')}
            yMin={0}
            yMax={100}
            series={[
              {
                id: 'a',
                label: `A · ${ta.callSign}`,
                points: ta.sessions.map((s, i) => ({ x: i + 1, y: s.score })),
              },
              {
                id: 'b',
                label: `B · ${tb.callSign}`,
                points: tb.sessions.map((s, i) => ({ x: i + 1, y: s.score })),
              },
            ]}
            tableLabel={t('m.common.dataTable')}
          />
        </Panel>
        <ReactionPanel trainees={[ta, tb]} label={`A+B`} />
      </Grid>
      <Panel title={t('m.perf.skillProficiency')}>
        {SKILLS.map((k) => (
          <div key={k} className="grid grid-cols-1 gap-x-6 md:grid-cols-2">
            <Bar
              label={`A · ${t(`m.skill.${k}`)}`}
              value={at(ta.skills[k], 3)}
              text={pct(at(ta.skills[k], 3))}
            />
            <Bar
              label={`B · ${t(`m.skill.${k}`)}`}
              value={at(tb.skills[k], 3)}
              text={pct(at(tb.skills[k], 3))}
              tone="signal"
            />
          </div>
        ))}
      </Panel>
    </div>
  )
}

function AnnotatedReplay() {
  const { t } = useTranslation()
  const [id, setId] = useState(at(TRAINEES, 0).id)
  const trainee = traineeById(id)
  const [notes, setNotes] = useState<Annotation[]>([
    {
      t: 131,
      text: 'Assessment came after the first approach was already inside the outer zone.',
      author: 'Maj. Ritu Banerjee',
    },
  ])
  const session = at(trainee.sessions, 3)
  return (
    <div className="flex flex-col gap-4">
      <div className="max-w-[320px]">
        <Select
          label={t('m.common.trainee')}
          value={id}
          options={TRAINEES.map((x) => ({ value: x.id, label: `${x.name} (${x.callSign})` }))}
          onChange={(e) => setId(e.target.value)}
        />
      </div>
      <ReplayPanel
        key={session.id}
        session={session}
        initialT={131}
        annotations={notes}
        onAnnotate={(n) => setNotes([...notes, n])}
      />
    </div>
  )
}

export function UnitAar() {
  const { t } = useTranslation()
  return (
    <ModulePage
      group="review"
      module="unit-aar"
      tabs={[
        { id: 'dashboard', label: t('m.unit.dashboard'), panel: <UnitDashboard /> },
        { id: 'compare', label: t('m.unit.compare'), panel: <CompareTrainees /> },
        { id: 'replay', label: t('m.unit.replay'), panel: <AnnotatedReplay /> },
      ]}
    />
  )
}

export function Reports() {
  const { t } = useTranslation()
  return (
    <ModulePage
      group="review"
      module="reports"
      tabs={[{ id: 'builder', label: t('m.report.builder'), panel: <ReportBuilder /> }]}
    />
  )
}
