import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate } from 'react-router-dom'
import {
  CLASSES,
  CURRICULA,
  SCENARIOS,
  SKILLS,
  TRAINEES,
  at,
  contactCount,
  curveFor,
  mulberry32,
  recommend,
  round,
  scenarioById,
  type ClassId,
  type SkillId,
} from '../../mock'
import { Button } from '../../ui/Button'
import { EmptyState } from '../../ui/States'
import { Select } from '../../ui/Field'
import { Panel } from '../../ui/Panel'
import { Table, type Column } from '../../ui/Table'
import { ConfusionPanel, DecisionPath, MissZonePanel, ReactionPanel, ReplayPanel } from './aar'
import { ME, pct, skillVector } from './format'
import { Bar, Facts, Grid, LineChart, ModulePage, Mark } from './kit'
import { ReportBuilder } from './report'

// -- Today ------------------------------------------------------------------------------------

export function Today() {
  const { t } = useTranslation()
  const last = at(ME.sessions, 3)
  const vector = skillVector(ME.skills)
  const rec = recommend(vector, [last.scenarioId])
  const top = at(rec, 0)
  const due = [...SKILLS].sort((a, b) => vector[a] - vector[b]).slice(0, 5)
  return (
    <ModulePage
      group="train"
      module="today"
      tabs={[
        {
          id: 'overview',
          label: t('m.today.overview'),
          panel: (
            <Grid cols={3}>
              <Panel title={t('m.today.recommended')}>
                <p className="m-0 text-md font-semibold">{top.scenario.name}</p>
                <p className="num m-0 mb-3 text-xs text-ink-2">
                  {top.scenario.site} · {t(`m.tod.${top.scenario.timeOfDay}`)} ·{' '}
                  {t(`live.weather.${top.scenario.weather}`)}
                </p>
                <Facts
                  rows={[
                    { label: t('m.common.difficulty'), value: `${top.scenario.difficulty} / 5` },
                    {
                      label: t('m.today.focus'),
                      value: top.focus.map((f) => t(`m.skill.${f}`)).join(', ') || '—',
                    },
                    { label: t('m.today.predicted'), value: pct(top.predicted) },
                    { label: t('m.common.contacts'), value: contactCount(top.scenario) },
                  ]}
                />
                <div className="mt-3 flex gap-2">
                  <Link
                    to="/train/lobby"
                    className="inline-flex h-7 items-center border border-accent bg-accent px-3 text-sm font-medium text-accent-on no-underline"
                  >
                    {t('m.today.start')}
                  </Link>
                </div>
              </Panel>
              <Panel title={t('m.today.due')}>
                {due.map((k, i) => (
                  <Bar
                    key={k}
                    label={t(`m.skill.${k}`)}
                    value={vector[k]}
                    text={pct(vector[k])}
                    tone={i < 2 ? 'signal' : 'accent'}
                  />
                ))}
                <p className="num m-0 mt-2 text-xs text-ink-2">{t('m.today.dueNote')}</p>
              </Panel>
              <Panel title={t('m.today.last')}>
                <Facts
                  rows={[
                    { label: t('m.common.scenario'), value: scenarioById(last.scenarioId).name },
                    { label: t('m.common.date'), value: last.date },
                    { label: t('m.common.score'), value: last.score.toFixed(1) },
                    { label: t('m.common.detectTime'), value: `${last.detectTimeS.toFixed(1)} s` },
                    { label: t('m.common.accuracy'), value: pct(last.classifyAccuracy) },
                    { label: t('m.common.falseAlarms'), value: last.falseAlarms },
                  ]}
                />
                <p className="m-0 mt-3 text-sm">
                  <Link to="/trainee/my-performance">{t('m.today.openReview')}</Link>
                </p>
              </Panel>
              <Panel title={t('m.today.next')} className="xl:col-span-2 lg:col-span-2" flush>
                <NextScenarios />
              </Panel>
              <Panel title={t('m.today.trend')}>
                <LineChart
                  alt={t('m.today.trendAlt')}
                  xTitle={t('m.common.sessionNumber')}
                  yTitle={t('m.common.score')}
                  yMin={0}
                  yMax={100}
                  series={[
                    {
                      id: 'me',
                      label: ME.callSign,
                      points: ME.sessions.map((s, i) => ({ x: i + 1, y: s.score })),
                    },
                  ]}
                  tableLabel={t('m.common.dataTable')}
                />
              </Panel>
            </Grid>
          ),
        },
      ]}
    />
  )
}

/** The next-scenario recommendation table, used on Today and in Progress. */
export function NextScenarios() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const vector = skillVector(ME.skills)
  const rows = recommend(vector, [at(ME.sessions, 3).scenarioId])
  const columns: Column<(typeof rows)[number]>[] = [
    { key: 'name', header: t('m.common.scenario'), render: (r) => r.scenario.name },
    {
      key: 'diff',
      header: t('m.common.difficulty'),
      mono: true,
      render: (r) => `${r.scenario.difficulty} / 5`,
    },
    {
      key: 'focus',
      header: t('m.today.focus'),
      render: (r) => r.focus.map((f) => t(`m.skill.${f}`)).join(', ') || '—',
    },
    {
      key: 'pred',
      header: t('m.today.predicted'),
      align: 'right',
      mono: true,
      render: (r) => pct(r.predicted),
    },
    {
      key: 'go',
      header: '',
      render: (r) => (
        <Button
          onClick={() => navigate('/train/lobby')}
          aria-label={t('m.today.startNamed', { name: r.scenario.name })}
        >
          {t('m.today.start')}
        </Button>
      ),
    },
  ]
  return (
    <Table
      caption={t('m.today.next')}
      columns={columns}
      rows={rows}
      rowKey={(r) => r.scenario.id}
    />
  )
}

// -- Drills: curriculum, quick drill, lobby -----------------------------------------------------

function Curriculum() {
  const { t } = useTranslation()
  const [open, setOpen] = useState(CURRICULA[0]?.id ?? '')
  const course = CURRICULA.find((c) => c.id === open) ?? at(CURRICULA, 0)
  const doneStages = open === 'cu-core' ? 2 : open === 'cu-night' ? 1 : 0
  const columns: Column<(typeof CURRICULA)[number]>[] = [
    { key: 'name', header: t('m.drills.course'), render: (c) => c.name },
    {
      key: 'stages',
      header: t('m.drills.stages'),
      align: 'right',
      mono: true,
      render: (c) => c.stages.length,
    },
    {
      key: 'sc',
      header: t('m.drills.scenarios'),
      align: 'right',
      mono: true,
      render: (c) => c.stages.reduce((a, s) => a + s.scenarioIds.length, 0),
    },
  ]
  return (
    <Grid cols={2}>
      <Panel title={t('m.drills.courses')} flush>
        <Table
          caption={t('m.drills.courses')}
          columns={columns}
          rows={CURRICULA}
          rowKey={(c) => c.id}
          selectedKey={open}
          onRowClick={(c) => setOpen(c.id)}
        />
      </Panel>
      <Panel title={t('m.drills.courseDetail', { name: course.name })}>
        <ol className="m-0 flex list-none flex-col gap-3 p-0">
          {course.stages.map((stage, i) => {
            const state = i < doneStages ? 'done' : i === doneStages ? 'current' : 'locked'
            return (
              <li key={stage.id} className="border border-line p-3">
                <div className="flex items-center justify-between">
                  <p className="m-0 text-sm font-semibold">{t('m.drills.stage', { n: i + 1 })}</p>
                  <Mark ok={state === 'done'} label={t(`m.drills.state.${state}`)} />
                </div>
                <ul className="m-0 mt-2 list-none p-0 text-sm">
                  {stage.scenarioIds.map((id) => (
                    <li key={id} className="py-0.5">
                      {scenarioById(id).name}
                    </li>
                  ))}
                </ul>
                <p className="num m-0 mt-2 text-xs text-ink-2">
                  {t('m.drills.gate', {
                    score: stage.gate.minScore,
                    accuracy: pct(stage.gate.minAccuracy),
                  })}
                </p>
              </li>
            )
          })}
        </ol>
      </Panel>
    </Grid>
  )
}

function QuickDrill() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [difficulty, setDifficulty] = useState('3')
  const [focus, setFocus] = useState<SkillId>('classify-fpv')
  const [site, setSite] = useState('any')
  const matches = SCENARIOS.filter(
    (s) => s.difficulty === Number(difficulty) && (site === 'any' || s.terrain === site),
  )
  return (
    <Grid cols={2}>
      <Panel title={t('m.drills.quickTitle')}>
        <div className="flex max-w-[360px] flex-col gap-4">
          <Select
            label={t('m.common.difficulty')}
            value={difficulty}
            options={[1, 2, 3, 4, 5].map((d) => ({ value: String(d), label: `${d} / 5` }))}
            onChange={(e) => setDifficulty(e.target.value)}
          />
          <Select
            label={t('m.today.focus')}
            value={focus}
            options={SKILLS.map((k) => ({ value: k, label: t(`m.skill.${k}`) }))}
            onChange={(e) => setFocus(e.target.value as SkillId)}
          />
          <Select
            label={t('m.common.terrain')}
            value={site}
            options={[
              { value: 'any', label: t('m.common.any') },
              { value: 'Heron Ridge', label: 'Heron Ridge' },
              { value: 'Osprey Town', label: 'Osprey Town' },
            ]}
            onChange={(e) => setSite(e.target.value)}
          />
          <Button variant="primary" onClick={() => navigate('/train/lobby')}>
            {t('m.drills.startQuick')}
          </Button>
        </div>
      </Panel>
      <Panel title={t('m.drills.matching', { count: matches.length })} flush>
        <Table
          caption={t('m.drills.matching', { count: matches.length })}
          columns={[
            { key: 'n', header: t('m.common.scenario'), render: (s) => s.name },
            { key: 't', header: t('m.common.terrain'), render: (s) => s.terrain },
            {
              key: 'c',
              header: t('m.common.contacts'),
              align: 'right',
              mono: true,
              render: (s) => contactCount(s),
            },
          ]}
          rows={matches}
          rowKey={(s) => s.id}
          empty={
            <EmptyState title={t('m.drills.noMatch')} description={t('m.drills.noMatchBody')} />
          }
        />
      </Panel>
    </Grid>
  )
}

export function Drills() {
  const { t } = useTranslation()
  return (
    <ModulePage
      group="train"
      module="drills"
      tabs={[
        { id: 'curriculum', label: t('m.drills.curriculum'), panel: <Curriculum /> },
        { id: 'quick', label: t('m.drills.quick'), panel: <QuickDrill /> },
        {
          id: 'lobby',
          label: t('m.drills.lobby'),
          panel: (
            <Panel title={t('m.drills.lobby')}>
              <p className="m-0 mb-3 max-w-[560px] text-sm text-ink-2">{t('m.drills.lobbyBody')}</p>
              <Link
                to="/train/lobby"
                className="inline-flex h-7 items-center border border-accent bg-accent px-3 text-sm font-medium text-accent-on no-underline"
              >
                {t('m.drills.openLobby')}
              </Link>
            </Panel>
          ),
        },
      ]}
    />
  )
}

// -- Recognition library -----------------------------------------------------------------------

type Level = 'high' | 'medium' | 'low' | 'none'
const APPEARANCE: Record<
  Exclude<ClassId, 'unknown'>,
  Record<'radar' | 'eo' | 'rf' | 'acoustic', Level>
> = {
  'rotary-small': { radar: 'low', eo: 'medium', rf: 'high', acoustic: 'high' },
  'fpv-small': { radar: 'low', eo: 'low', rf: 'high', acoustic: 'high' },
  'fixed-wing-small': { radar: 'medium', eo: 'medium', rf: 'medium', acoustic: 'low' },
  'fixed-wing-medium': { radar: 'high', eo: 'high', rf: 'medium', acoustic: 'medium' },
  'fixed-wing-large': { radar: 'high', eo: 'high', rf: 'low', acoustic: 'medium' },
  bird: { radar: 'low', eo: 'medium', rf: 'none', acoustic: 'none' },
  kite: { radar: 'low', eo: 'medium', rf: 'none', acoustic: 'none' },
  balloon: { radar: 'low', eo: 'medium', rf: 'none', acoustic: 'none' },
}
const THREATS: Exclude<ClassId, 'unknown'>[] = [
  'rotary-small',
  'fpv-small',
  'fixed-wing-small',
  'fixed-wing-medium',
  'fixed-wing-large',
]
const CLUTTER: Exclude<ClassId, 'unknown'>[] = ['bird', 'kite', 'balloon']

function Catalogue({ ids, title }: { ids: Exclude<ClassId, 'unknown'>[]; title: string }) {
  const { t } = useTranslation()
  const [open, setOpen] = useState<string>(at(ids, 0))
  const sel = (open in APPEARANCE ? open : at(ids, 0)) as Exclude<ClassId, 'unknown'>
  const columns: Column<Exclude<ClassId, 'unknown'>>[] = [
    { key: 'n', header: t('m.lib.class'), render: (c) => t(`live.class.${c}`) },
  ]
  return (
    <Grid cols={2}>
      <Panel title={title} flush>
        <Table
          caption={title}
          columns={columns}
          rows={ids}
          rowKey={(c) => c}
          selectedKey={sel}
          onRowClick={(c) => setOpen(c)}
        />
      </Panel>
      <Panel title={t('m.lib.detail', { name: t(`live.class.${sel}`) })}>
        <p className="m-0 mb-3 text-sm">{t(`m.lib.desc.${sel}`)}</p>
        <table className="w-full border-collapse text-left text-sm">
          <caption className="micro-label mb-1 text-left">{t('m.lib.appearance')}</caption>
          <thead className="sr-only">
            <tr>
              <th scope="col">{t('m.lib.sensor')}</th>
              <th scope="col">{t('m.lib.return')}</th>
            </tr>
          </thead>
          <tbody>
            {(['radar', 'eo', 'rf', 'acoustic'] as const).map((m) => (
              <tr key={m} className="h-7 border-b border-line last:border-b-0">
                <th scope="row" className="w-[120px] font-normal text-ink-2">
                  {t(`live.modality.${m}`)}
                </th>
                <td>
                  <span className="inline-flex items-center gap-2">
                    <span aria-hidden="true" className="flex gap-0.5">
                      {[1, 2, 3].map((n) => (
                        <span
                          key={n}
                          className={`block h-2 w-3 ${n <= { high: 3, medium: 2, low: 1, none: 0 }[APPEARANCE[sel][m]] ? 'bg-accent' : 'bg-surface-2'}`}
                        />
                      ))}
                    </span>
                    {t(`m.lib.level.${APPEARANCE[sel][m]}`)}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="micro-label m-0 mb-1 mt-3">{t('m.lib.tellApart')}</p>
        <p className="m-0 text-sm">{t(`m.lib.tell.${sel}`)}</p>
      </Panel>
    </Grid>
  )
}

const CARD_SIZE = { w: 320, h: 140 }

/** An acoustic spectrogram card: harmonic bands for rotor classes, broadband wind noise for the rest. */
function SpectrogramCard({ cls, seed }: { cls: ClassId; seed: number }) {
  const { t } = useTranslation()
  const rng = mulberry32(seed)
  const spec: Record<string, { f0: number; n: number; width: number }> = {
    'rotary-small': { f0: 26, n: 5, width: 2.4 },
    'fpv-small': { f0: 44, n: 3, width: 3.2 },
    'fixed-wing-small': { f0: 16, n: 3, width: 2 },
    'fixed-wing-medium': { f0: 12, n: 3, width: 3 },
    'fixed-wing-large': { f0: 9, n: 4, width: 3.6 },
  }
  const s = spec[cls]
  const columns = 64
  return (
    <svg
      viewBox={`0 0 ${CARD_SIZE.w} ${CARD_SIZE.h}`}
      role="img"
      aria-label={t('m.lib.cardAlt')}
      className="block h-auto w-full max-w-[420px] bg-bg"
    >
      {Array.from({ length: columns }, (_, i) => {
        const x = (i / columns) * CARD_SIZE.w
        const wobble = Math.sin(i / 6 + seed) * 2
        return (
          <g key={i}>
            {s
              ? Array.from({ length: s.n }, (_, h) => (
                  <rect
                    key={h}
                    x={x}
                    y={CARD_SIZE.h - (s.f0 * (h + 1) + wobble + rng() * 1.2)}
                    width={CARD_SIZE.w / columns + 0.5}
                    height={s.width}
                    fill="var(--accent)"
                    opacity={0.95 - h * 0.14}
                  />
                ))
              : null}
            {Array.from({ length: 10 }, (_, k) => (
              <rect
                key={k}
                x={x}
                y={CARD_SIZE.h - 6 - k * 6 - rng() * 4}
                width={CARD_SIZE.w / columns + 0.5}
                height="3"
                fill="var(--text-2)"
                opacity={s ? 0.1 : 0.25 + rng() * 0.2 - k * 0.015}
              />
            ))}
          </g>
        )
      })}
    </svg>
  )
}

function SignatureDrills() {
  const { t } = useTranslation()
  const deck: ClassId[] = [
    'rotary-small',
    'fpv-small',
    'bird',
    'fixed-wing-medium',
    'rotary-small',
    'fixed-wing-small',
    'fpv-small',
    'balloon',
  ]
  const [queue, setQueue] = useState<{ cls: ClassId; n: number }[]>(
    deck.map((cls, n) => ({ cls, n })),
  )
  const [answer, setAnswer] = useState<ClassId | null>(null)
  const [right, setRight] = useState(0)
  const [seen, setSeen] = useState(0)
  const card = queue[0]
  const options = useMemo<ClassId[]>(() => {
    if (!card) return []
    const rng = mulberry32(card.n * 31 + 5)
    const others = CLASSES.filter((c) => c !== card.cls && c !== 'unknown')
    const picks = [...others].sort(() => rng() - 0.5).slice(0, 3)
    return [...picks, card.cls].sort(() => rng() - 0.5)
  }, [card])
  if (!card)
    return (
      <Panel title={t('m.lib.drillsDone')}>
        <Facts
          rows={[
            { label: t('m.lib.cardsSeen'), value: seen },
            { label: t('m.lib.correctFirst'), value: right },
          ]}
        />
        <div className="mt-3">
          <Button
            onClick={() => {
              setQueue(deck.map((cls, n) => ({ cls, n })))
              setSeen(0)
              setRight(0)
              setAnswer(null)
            }}
          >
            {t('m.lib.again')}
          </Button>
        </div>
      </Panel>
    )
  const correct = answer === card.cls
  return (
    <Panel title={t('m.lib.cardTitle', { n: seen + 1, of: seen + queue.length })}>
      <p className="m-0 mb-2 text-sm text-ink-2">{t('m.lib.cardPrompt')}</p>
      <SpectrogramCard cls={card.cls} seed={card.n * 7 + 3} />
      <div role="group" aria-label={t('m.lib.cardPrompt')} className="mt-3 flex flex-wrap gap-2">
        {options.map((o) => (
          <Button key={o} disabled={answer !== null} onClick={() => setAnswer(o)}>
            {t(`live.class.${o}`)}
          </Button>
        ))}
      </div>
      {answer && (
        <div role="status" className="mt-3 border-l-2 border-accent pl-3 text-sm">
          <p className="m-0 font-semibold">
            {correct ? t('m.lib.right') : t('m.lib.wrong', { name: t(`live.class.${card.cls}`) })}
          </p>
          <p className="m-0 text-ink-2">{t(`m.lib.tell.${card.cls}`)}</p>
          <div className="mt-2">
            <Button
              variant="primary"
              onClick={() => {
                if (correct) setRight((r) => r + 1)
                setSeen((s) => s + 1)
                setQueue((q) =>
                  correct
                    ? q.slice(1)
                    : [...q.slice(1), at(q, 0)].filter((_, i, a) => a.length < 12 || i < 11),
                )
                setAnswer(null)
              }}
            >
              {t('m.lib.next')}
            </Button>
          </div>
        </div>
      )}
    </Panel>
  )
}

export function RecognitionLibrary() {
  const { t } = useTranslation()
  return (
    <ModulePage
      group="train"
      module="recognition-library"
      tabs={[
        {
          id: 'threats',
          label: t('m.lib.threats'),
          panel: <Catalogue ids={THREATS} title={t('m.lib.threats')} />,
        },
        {
          id: 'clutter',
          label: t('m.lib.clutter'),
          panel: <Catalogue ids={CLUTTER} title={t('m.lib.clutter')} />,
        },
        { id: 'drills', label: t('m.lib.signatureDrills'), panel: <SignatureDrills /> },
      ]}
    />
  )
}

// -- My performance ----------------------------------------------------------------------------

function Sessions() {
  const { t } = useTranslation()
  const [open, setOpen] = useState(at(ME.sessions, 3).id)
  const session = ME.sessions.find((s) => s.id === open) ?? at(ME.sessions, 3)
  const columns: Column<(typeof ME.sessions)[number]>[] = [
    { key: 'date', header: t('m.common.date'), mono: true, render: (s) => s.date },
    { key: 'sc', header: t('m.common.scenario'), render: (s) => scenarioById(s.scenarioId).name },
    { key: 'mode', header: t('m.common.mode'), render: (s) => t(`m.mode.${s.mode}`) },
    {
      key: 'score',
      header: t('m.common.score'),
      align: 'right',
      mono: true,
      render: (s) => s.score.toFixed(1),
    },
    {
      key: 'det',
      header: t('m.common.detectTime'),
      align: 'right',
      mono: true,
      render: (s) => `${s.detectTimeS.toFixed(1)} s`,
    },
    {
      key: 'acc',
      header: t('m.common.accuracy'),
      align: 'right',
      mono: true,
      render: (s) => pct(s.classifyAccuracy),
    },
  ]
  return (
    <div className="flex flex-col gap-4">
      <Panel title={t('m.perf.sessionList')} flush>
        <Table
          caption={t('m.perf.sessionList')}
          columns={columns}
          rows={ME.sessions}
          rowKey={(s) => s.id}
          selectedKey={open}
          onRowClick={(s) => setOpen(s.id)}
        />
      </Panel>
      <ReplayPanel key={session.id} session={session} initialT={90} />
      <DecisionPath session={session} />
      <ConfusionPanel trainees={[ME]} title={t('m.aar.confusion')} />
    </div>
  )
}

function Progress() {
  const { t } = useTranslation()
  const unit = TRAINEES.filter((x) => x.cohortId === ME.cohortId)
  const vector = skillVector(ME.skills)
  return (
    <div className="flex flex-col gap-4">
      <Grid cols={2}>
        <Panel title={t('m.perf.skillProficiency')}>
          {SKILLS.map((k) => (
            <Bar key={k} label={t(`m.skill.${k}`)} value={vector[k]} text={pct(vector[k])} />
          ))}
        </Panel>
        <Panel title={t('m.perf.learningCurves')}>
          <LineChart
            alt={t('m.perf.learningAlt')}
            xTitle={t('m.common.sessionNumber')}
            yTitle={t('m.common.score')}
            yMin={0}
            yMax={100}
            series={[
              {
                id: 'me',
                label: ME.callSign,
                points: ME.sessions.map((s, i) => ({ x: i + 1, y: s.score })),
              },
              { id: 'unit', label: t('m.perf.cohortMean'), points: curveFor(unit, (s) => s.score) },
            ]}
            tableLabel={t('m.common.dataTable')}
          />
          <LineChart
            alt={t('m.perf.accuracyAlt')}
            xTitle={t('m.common.sessionNumber')}
            yTitle={t('m.perf.accuracyPct')}
            yMin={0}
            yMax={100}
            series={[
              {
                id: 'me',
                label: ME.callSign,
                points: ME.sessions.map((s, i) => ({
                  x: i + 1,
                  y: round(s.classifyAccuracy * 100, 0),
                })),
              },
              {
                id: 'unit',
                label: t('m.perf.cohortMean'),
                points: curveFor(unit, (s) => s.classifyAccuracy * 100),
              },
            ]}
            tableLabel={t('m.common.dataTable')}
          />
        </Panel>
      </Grid>
      <Grid cols={2}>
        <ReactionPanel trainees={[ME]} label={ME.callSign} />
        <MissZonePanel trainees={[ME]} />
      </Grid>
      <Panel title={t('m.today.next')} flush>
        <NextScenarios />
      </Panel>
    </div>
  )
}

export function MyPerformance() {
  const { t } = useTranslation()
  return (
    <ModulePage
      group="review"
      module="my-performance"
      tabs={[
        { id: 'sessions', label: t('m.perf.sessions'), panel: <Sessions /> },
        { id: 'progress', label: t('m.perf.progress'), panel: <Progress /> },
        { id: 'reports', label: t('m.perf.reports'), panel: <ReportBuilder fixedTrainee={ME} /> },
      ]}
    />
  )
}

// -- Help --------------------------------------------------------------------------------------

const SHORTCUTS: [string, string][] = [
  ['Tab', 'nextTrack'],
  ['C', 'classify'],
  ['A', 'assess'],
  ['R', 'respond'],
  ['H', 'hold'],
  ['Space', 'pause'],
  ['?', 'help'],
  ['1–9', 'options'],
  ['Enter', 'commit'],
]

export function Help() {
  const { t } = useTranslation()
  return (
    <ModulePage
      group="account"
      module="help"
      tabs={[
        {
          id: 'shortcuts',
          label: t('m.help.shortcuts'),
          panel: (
            <Panel title={t('m.help.shortcuts')} flush>
              <Table
                caption={t('m.help.shortcuts')}
                columns={[
                  {
                    key: 'k',
                    header: t('m.help.key'),
                    mono: true,
                    render: (r: [string, string]) => (
                      <kbd className="num border border-line px-2">{r[0]}</kbd>
                    ),
                  },
                  {
                    key: 'a',
                    header: t('m.help.action'),
                    render: (r: [string, string]) => t(`m.help.shortcut.${r[1]}`),
                  },
                ]}
                rows={SHORTCUTS}
                rowKey={(r) => r[0]}
              />
            </Panel>
          ),
        },
        {
          id: 'sops',
          label: t('m.help.sops'),
          panel: (
            <Grid cols={2}>
              {(['watch', 'classify', 'report', 'handover'] as const).map((sop) => (
                <Panel key={sop} title={t(`m.help.sop.${sop}.title`)}>
                  <ol className="m-0 flex list-decimal flex-col gap-1 pl-4 text-sm">
                    {[1, 2, 3, 4].map((n) => (
                      <li key={n}>{t(`m.help.sop.${sop}.s${n}`)}</li>
                    ))}
                  </ol>
                </Panel>
              ))}
            </Grid>
          ),
        },
        {
          id: 'about',
          label: t('m.help.about'),
          panel: (
            <Panel title={t('m.help.about')}>
              <p className="m-0 mb-3 max-w-[560px] text-sm">{t('m.help.aboutBody')}</p>
              <Link to="/about">{t('nav.about')}</Link>
            </Panel>
          ),
        },
      ]}
    />
  )
}
