import { ErrorFilled, InformationFilled, WarningFilled } from '@carbon/icons-react'
import type { TFunction } from 'i18next'
import { useCallback, useEffect, useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useLocation, useParams } from 'react-router-dom'
import type {
  Finding,
  FieldMark,
  NodeResult,
  ReportGrade,
  SessionScore,
  ThreatScore,
} from '../contracts/score-result.v1'
import { PageHeader } from '../layout/PageHeader'
import { ApiError, NetworkError } from '../lib/api'
import { fmtElapsed, useLang } from '../live/format'
import { getScore, listScenarios, localised } from '../live/restApi'
import type { Lang } from '../live/roe'
import {
  className,
  dispositionLabel,
  fmtCostPoints,
  fmtDegrees,
  fmtMetres,
  fmtScore,
  nodeLabel,
  num,
  renderReason,
} from '../live/scoring'
import { Badge } from '../ui/Badge'
import { InlineAlert } from '../ui/InlineAlert'
import { Panel } from '../ui/Panel'
import { EmptyState, ErrorState, LoadingState } from '../ui/States'
import { Table, type Column } from '../ui/Table'

type Failure = 'notEnded' | 'notFound' | 'network' | 'error'
type Load =
  | { state: 'loading' }
  | { state: 'failed'; failure: Failure }
  | { state: 'ready'; score: SessionScore; title: ScenarioTitle | null }

type ScenarioTitle = NonNullable<Parameters<typeof localised>[0]>

const failureOf = (error: unknown): Failure =>
  error instanceof NetworkError
    ? 'network'
    : error instanceof ApiError && error.status === 409
      ? 'notEnded'
      : error instanceof ApiError && (error.status === 404 || error.status === 403)
        ? 'notFound'
        : 'error'

/** Route /train/session/:id/debrief: the scored record of an ended session, with ground truth. */
export function Debrief() {
  const { id = '' } = useParams()
  const { search } = useLocation()
  const { t } = useTranslation()
  const [load, setLoad] = useState<Load>({ state: 'loading' })
  const [attempt, setAttempt] = useState(0)
  const retry = useCallback(() => {
    setLoad({ state: 'loading' })
    setAttempt((n) => n + 1)
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    getScore(id, controller.signal, search)
      .then(async (score) => {
        // The score names the scenario by ID only; the title comes from the scenario list, if it answers.
        const title = await listScenarios(controller.signal)
          .then((list) => list.find((s) => s.id === score.scenario.id)?.title ?? null)
          .catch(() => null)
        if (controller.signal.aborted) return
        setLoad({ state: 'ready', score, title })
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) setLoad({ state: 'failed', failure: failureOf(error) })
      })
    return () => controller.abort()
  }, [id, search, attempt])

  const back = (
    <Link
      to="/train/lobby"
      className="inline-flex h-7 items-center border border-line px-3 text-sm no-underline hover:border-accent"
    >
      {t('debrief.back')}
    </Link>
  )
  return (
    <>
      <PageHeader
        title={t('debrief.title')}
        crumbs={[t('nav.group.train'), t('nav.module.drills'), t('debrief.title')]}
        actions={back}
      />
      {load.state === 'loading' && (
        <div className="max-w-[880px]" data-testid="debrief-loading">
          <Panel title={t('debrief.title')} flush>
            <LoadingState label={t('debrief.loading')} />
          </Panel>
        </div>
      )}
      {load.state === 'failed' && (
        <div className="max-w-[640px]" data-testid="debrief-failure" data-failure={load.failure}>
          <ErrorState
            offline={load.failure === 'network'}
            title={t(`debrief.${load.failure}.title`)}
            description={t(`debrief.${load.failure}.body`)}
            retryLabel={t('debrief.retry')}
            onRetry={retry}
          />
          {load.failure === 'notEnded' && (
            <p className="mt-4">
              <Link to={`/train/session/${encodeURIComponent(id)}${search}`}>
                {t('debrief.toRecord')}
              </Link>
            </p>
          )}
        </div>
      )}
      {load.state === 'ready' && (
        <DebriefBody sessionId={id} score={load.score} title={load.title} />
      )}
    </>
  )
}

// ---------------------------------------------------------------------- body

function DebriefBody({
  sessionId,
  score,
  title,
}: {
  sessionId: string
  score: SessionScore
  title: ScenarioTitle | null
}) {
  const { t } = useTranslation()
  const lang = useLang()
  const scored = score.threats.filter((x) => x.presented && x.worked !== false)
  const unscored = score.threats.filter((x) => !x.presented || x.worked === false)
  const presented = score.threats.some((x) => x.presented)
  return (
    <div
      className="flex max-w-[1240px] flex-col gap-4"
      data-testid="debrief"
      data-session={sessionId}
    >
      <div className="flex flex-col gap-2">
        <InlineAlert tone="info">{t('debrief.reference')}</InlineAlert>
        <p className="m-0 text-xs text-ink-2">{t('debrief.truthNote')}</p>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,7fr)_minmax(0,5fr)]">
        <SummaryPanel score={score} />
        <div className="flex flex-col gap-4">
          <LessonsPanel score={score} lang={lang} />
          <RecordPanel score={score} title={title ? localised(title, lang) : null} />
        </div>
      </div>

      {!presented && (
        <EmptyState title={t('debrief.empty.title')} description={t('debrief.empty.body')} />
      )}

      {scored.length > 0 && (
        <section aria-labelledby="contacts-h" className="flex flex-col gap-4">
          <h2 id="contacts-h" className="m-0 text-md font-semibold">
            {t('debrief.contacts.title')}
          </h2>
          {scored.map((threat) => (
            <ContactSection key={threat.threat_id} threat={threat} lang={lang} />
          ))}
        </section>
      )}

      {unscored.length > 0 && <NotScored threats={unscored} lang={lang} />}

      {score.findings && score.findings.length > 0 && (
        <Panel title={t('debrief.sessionFindings.title')}>
          <FindingList findings={score.findings} lang={lang} />
        </Panel>
      )}
    </div>
  )
}

function Fact({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid min-h-7 grid-cols-[148px_1fr] items-baseline gap-2 border-b border-line px-3 py-1 last:border-b-0">
      <dt className="text-sm text-ink-2">{label}</dt>
      <dd className="num m-0 min-w-0 break-words text-sm">{children}</dd>
    </div>
  )
}

function RecordPanel({ score, title }: { score: SessionScore; title: string | null }) {
  const { t } = useTranslation()
  return (
    <Panel title={t('debrief.record.title')} flush>
      <dl className="m-0">
        <Fact label={t('debrief.record.scenario')}>
          <span className="font-sans font-semibold">{title ?? score.scenario.id}</span>
        </Fact>
        <Fact label={t('debrief.record.scenarioVersion')}>
          {score.scenario.id} {score.scenario.version}
        </Fact>
        <Fact label={t('debrief.record.rulePack')}>
          {score.rule_pack.id} {score.rule_pack.version}
        </Fact>
        <Fact label={t('debrief.record.seed')}>{score.seed}</Fact>
        <Fact label={t('debrief.record.duration')}>{fmtElapsed(score.duration_s)}</Fact>
        <Fact label={t('debrief.record.ticks')}>{score.ticks}</Fact>
      </dl>
    </Panel>
  )
}

// ---------------------------------------------------------------------- summary

interface Measure {
  key: string
  label: string
  value: ReactNode
  note?: string
  strong?: boolean
}

function MeasureTable({ caption, rows }: { caption: string; rows: Measure[] }) {
  const { t } = useTranslation()
  const columns: Column<Measure>[] = [
    {
      key: 'label',
      header: t('debrief.summary.measure'),
      render: (r) => r.label,
      className: 'w-[56%]',
    },
    {
      key: 'value',
      header: t('debrief.summary.value'),
      align: 'right',
      mono: true,
      render: (r) => (
        <span className={r.strong ? 'text-lg font-semibold' : ''}>
          {r.value}
          {r.note && (
            <span className="ml-2 whitespace-nowrap text-xs font-normal text-ink-2">{r.note}</span>
          )}
        </span>
      ),
    },
  ]
  return <Table caption={caption} columns={columns} rows={rows} rowKey={(r) => r.key} dense />
}

const fixed = (value: number | null | undefined, digits = 2): string =>
  value === null || value === undefined ? '—' : value.toFixed(digits)

function SummaryPanel({ score }: { score: SessionScore }) {
  const { t } = useTranslation()
  const sdt = score.sdt
  const scores: Measure[] = [
    {
      key: 'session',
      label: t('debrief.summary.session'),
      value: fmtScore(score.score),
      strong: true,
    },
    {
      key: 'decision',
      label: t('debrief.summary.decision'),
      value: fmtScore(score.decision_score),
    },
    { key: 'report', label: t('debrief.summary.report'), value: fmtScore(score.report_score) },
  ]
  const counts: Measure[] = [
    { key: 'dprime', label: t('debrief.summary.dPrime'), value: fixed(sdt.d_prime, 3) },
    { key: 'criterion', label: t('debrief.summary.criterion'), value: fixed(sdt.criterion, 3) },
    {
      key: 'hit',
      label: t('debrief.summary.hitRate'),
      value: fmtScore(sdt.hit_rate),
      note: sdt.corrected ? t('debrief.summary.used', { value: fmtScore(sdt.hit_rate_used) }) : '',
    },
    {
      key: 'fa',
      label: t('debrief.summary.faRate'),
      value: fmtScore(sdt.false_alarm_rate),
      note: sdt.corrected
        ? t('debrief.summary.used', { value: fmtScore(sdt.false_alarm_rate_used) })
        : '',
    },
    { key: 'hits', label: t('debrief.summary.hits'), value: sdt.hits },
    { key: 'misses', label: t('debrief.summary.misses'), value: sdt.misses },
    { key: 'fas', label: t('debrief.summary.falseAlarms'), value: sdt.false_alarms },
    { key: 'crs', label: t('debrief.summary.correctRejections'), value: sdt.correct_rejections },
    { key: 'st', label: t('debrief.summary.signalTrials'), value: sdt.signal_trials },
    { key: 'nt', label: t('debrief.summary.noiseTrials'), value: sdt.noise_trials },
  ]
  return (
    <Panel title={t('debrief.summary.title')} flush>
      <div className="grid grid-cols-1 divide-line md:grid-cols-2 md:divide-x">
        <div>
          <MeasureTable caption={t('debrief.summary.caption')} rows={scores} />
          {score.score === null && (
            <p className="m-0 border-t border-line px-3 py-2 text-xs text-ink-2">
              {t('debrief.summary.none')}
            </p>
          )}
        </div>
        <div>
          <MeasureTable caption={t('debrief.summary.sdtCaption')} rows={counts} />
        </div>
      </div>
      <div className="flex flex-col gap-1 border-t border-line px-3 py-2 text-xs text-ink-2">
        {sdt.corrected && (
          <p className="m-0 flex items-start gap-2 text-ink" data-testid="sdt-corrected">
            <InformationFilled
              size={16}
              aria-hidden="true"
              className="mt-px shrink-0 text-accent"
            />
            <span>
              {t('debrief.summary.corrected', {
                hit: fmtScore(sdt.hit_rate_used),
                fa: fmtScore(sdt.false_alarm_rate_used),
              })}
            </span>
          </p>
        )}
        {sdt.d_prime === null && <p className="m-0">{t('debrief.summary.undefined')}</p>}
        <p className="m-0">{t('debrief.summary.criterionNote')}</p>
      </div>
    </Panel>
  )
}

// ---------------------------------------------------------------------- lessons

function LessonsPanel({ score, lang }: { score: SessionScore; lang: Lang }) {
  const { t } = useTranslation()
  const lessons = score.lessons ?? []
  return (
    <Panel title={t('debrief.lessons.title')} flush>
      {lessons.length === 0 ? (
        <p className="m-0 px-3 py-3 text-sm text-ink-2">{t('debrief.lessons.empty')}</p>
      ) : (
        <ol className="m-0 list-none p-0" aria-label={t('debrief.lessons.caption')}>
          {lessons.map((lesson, index) => (
            <li
              key={`${lesson.key}-${index}`}
              className="grid grid-cols-[24px_1fr] gap-2 border-b border-line px-3 py-2 last:border-b-0"
              data-testid="lesson"
            >
              <span className="num text-sm text-ink-2" aria-hidden="true">
                {index + 1}
              </span>
              <div>
                <p className="m-0 text-sm">{renderReason(lesson.key, lesson.params, lang)}</p>
                <p className="num m-0 mt-1 text-xs text-ink-2">
                  {t('debrief.lessons.cost')}{' '}
                  {t('debrief.lessons.points', { points: fmtCostPoints(lesson.cost) })}
                </p>
              </div>
            </li>
          ))}
        </ol>
      )}
    </Panel>
  )
}

// ---------------------------------------------------------------------- contacts

const contactHeading = (threat: ThreatScore, lang: Lang, t: TFunction): string =>
  t('debrief.contacts.heading', {
    label: threat.label[lang],
    class: className(threat.class_id, lang),
    disposition: dispositionLabel(threat.disposition, lang),
  })

interface PathRow {
  key: string
  node: string
  weight: string
  points: string
  mark: string
  reason: string
}

function pathRows(threat: ThreatScore, lang: Lang, t: TFunction): PathRow[] {
  const rows: PathRow[] = (threat.nodes ?? []).map((n: NodeResult) => ({
    key: n.node,
    node: nodeLabel(n.node, lang),
    weight: n.weight.toFixed(2),
    points: `${(n.score * n.weight).toFixed(3)} / ${n.weight.toFixed(2)}`,
    mark: fmtScore(n.score),
    reason: renderReason(n.reason, n.params, lang),
  }))
  const report = threat.report
  if (report) {
    rows.push({
      key: 'report',
      node: nodeLabel('report', lang),
      weight: '—',
      points: t('debrief.contacts.reportRow'),
      mark: report.filed ? fmtScore(report.score) : fmtScore(0),
      reason: renderReason(report.reason ?? 'report.missing', report.params, lang),
    })
  }
  return rows
}

function ContactSection({ threat, lang }: { threat: ThreatScore; lang: Lang }) {
  const { t } = useTranslation()
  const headingId = `contact-${threat.threat_id}`
  const hardFail = (threat.findings ?? []).find((f) => f.kind === 'hard-fail')
  const rest = (threat.findings ?? []).filter((f) => f.kind !== 'hard-fail')
  const columns: Column<PathRow>[] = [
    {
      key: 'node',
      header: t('debrief.contacts.node'),
      render: (r) => r.node,
      className: 'w-24 align-top py-1',
    },
    {
      key: 'weight',
      header: t('debrief.contacts.weight'),
      render: (r) => r.weight,
      mono: true,
      align: 'right',
      className: 'w-16 align-top py-1',
    },
    {
      key: 'points',
      header: t('debrief.contacts.points'),
      render: (r) => r.points,
      mono: true,
      align: 'right',
      className: 'w-36 align-top py-1',
    },
    {
      key: 'mark',
      header: t('debrief.contacts.mark'),
      render: (r) => r.mark,
      mono: true,
      align: 'right',
      className: 'w-20 align-top py-1',
    },
    {
      key: 'reason',
      header: t('debrief.contacts.reason'),
      render: (r) => r.reason,
      className: 'align-top py-1',
    },
  ]
  return (
    <section
      aria-labelledby={headingId}
      className="border border-line bg-surface-1"
      data-testid="contact"
      data-threat={threat.threat_id}
    >
      <header className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 border-b border-line px-3 py-2">
        <div>
          <h3 id={headingId} className="m-0 text-sm font-semibold">
            {contactHeading(threat, lang, t)}
          </h3>
          <p className="num m-0 mt-1 text-xs text-ink-2">
            {t('debrief.contacts.firstReport', {
              time: threat.first_report_s != null ? fmtElapsed(threat.first_report_s) : '—',
            })}
            {' · '}
            {t('debrief.contacts.decision')} {fmtScore(threat.decision)}
          </p>
        </div>
        <div className="flex items-baseline gap-3">
          <span className="text-xs text-ink-2">{t('debrief.contacts.score')}</span>
          <span className="num text-lg font-semibold">{fmtScore(threat.score)}</span>
        </div>
      </header>

      {hardFail && (
        <div
          className="m-3 flex items-start gap-3 border-2 border-track-hostile bg-surface-2 p-3"
          role="group"
          aria-labelledby={`${headingId}-hf`}
          data-testid="hard-fail"
        >
          <ErrorFilled size={20} aria-hidden="true" className="mt-px shrink-0 text-track-hostile" />
          <div>
            <p id={`${headingId}-hf`} className="m-0 text-sm font-semibold tracking-[0.04em]">
              {t('debrief.hardFail.title')}
            </p>
            <p className="m-0 mt-1 text-sm">
              {renderReason(hardFail.reason, hardFail.params, lang)}
            </p>
            <p className="m-0 mt-1 text-xs text-ink-2">{t('debrief.hardFail.score')}</p>
          </div>
        </div>
      )}

      <Table
        caption={t('debrief.contacts.pathCaption', { label: threat.label[lang] })}
        columns={columns}
        rows={pathRows(threat, lang, t)}
        rowKey={(r) => r.key}
        dense
      />

      {rest.length > 0 && (
        <div className="border-t border-line px-3 py-2">
          <h4 className="m-0 mb-1 text-xs font-medium text-ink-2">
            {t('debrief.contacts.findings')}
          </h4>
          <FindingList findings={rest} lang={lang} />
        </div>
      )}

      {threat.report && <ReportGrades threat={threat} report={threat.report} lang={lang} />}
    </section>
  )
}

const FINDING_ICON: Record<string, typeof WarningFilled> = {
  'hard-fail': ErrorFilled,
  'false-engagement': ErrorFilled,
  'track-error': WarningFilled,
  'blocked-attempt': WarningFilled,
  'false-alarm': WarningFilled,
}

function FindingList({ findings, lang }: { findings: Finding[]; lang: Lang }) {
  const { t } = useTranslation()
  return (
    <ul className="m-0 flex list-none flex-col gap-1 p-0">
      {findings.map((finding, index) => {
        const Icon = FINDING_ICON[finding.kind] ?? InformationFilled
        return (
          <li
            key={`${finding.reason}-${index}`}
            className="flex items-start gap-2 text-sm"
            data-testid="finding"
          >
            <Icon size={16} aria-hidden="true" className="mt-px shrink-0 text-ink-2" />
            <span className="font-medium">{t(`debrief.kind.${finding.kind}`)}</span>
            <span className="min-w-0 flex-1">
              {renderReason(finding.reason, finding.params, lang)}
            </span>
            {finding.cost != null && finding.cost > 0 && (
              <span className="num shrink-0 text-xs text-ink-2">
                {t('debrief.contacts.findingCost', { points: fmtCostPoints(finding.cost) })}
              </span>
            )}
          </li>
        )
      })}
    </ul>
  )
}

// ---------------------------------------------------------------------- report grades

interface FieldRow {
  key: string
  field: string
  reported: string
  tolerance: string
  weight: string
  mark: string
  reason: string
}

function fieldRow(f: FieldMark, lang: Lang, t: TFunction): FieldRow {
  const p = f.params ?? {}
  const missing = f.reason.endsWith('.missing')
  let reported = '—'
  let tolerance = '—'
  if (missing) reported = t('debrief.report.notStated')
  else if (f.field === 'what') {
    reported = `${className(p.given, lang)} / ${className(p.actual, lang)}`
    tolerance = t('debrief.report.exact')
  } else if (f.field === 'where') {
    reported = t('debrief.report.off', { value: fmtMetres(num(p.error_m) ?? 0) })
    tolerance = fmtMetres(num(p.tolerance_m) ?? 0)
  } else if (f.field === 'count') {
    reported = `${String(p.given)} / ${String(p.actual)}`
    tolerance = t('debrief.report.exact')
  } else if (f.field === 'heading') {
    reported = t('debrief.report.off', { value: fmtDegrees(num(p.error_deg) ?? 0) })
    tolerance = fmtDegrees(num(p.tolerance_deg) ?? 0)
  } else if (f.field === 'calibration') {
    reported = t('debrief.report.stated', {
      stated: fmtScore(num(p.stated)).replace('.0%', '%'),
      achieved: fmtScore(num(p.achieved)).replace('.0%', '%'),
    })
  }
  return {
    key: f.field,
    field: t(`scoring.reportField.${f.field}`),
    reported,
    tolerance,
    weight: f.weight.toFixed(2),
    mark: `${fmtScore(f.score)}`,
    reason: renderReason(f.reason, f.params, lang),
  }
}

function ReportGrades({
  threat,
  report,
  lang,
}: {
  threat: ThreatScore
  report: ReportGrade
  lang: Lang
}) {
  const { t } = useTranslation()
  const fields = report.fields ?? []
  const columns: Column<FieldRow>[] = [
    {
      key: 'field',
      header: t('debrief.report.field'),
      render: (r) => r.field,
      className: 'w-24 align-top py-1',
    },
    {
      key: 'reported',
      header: t('debrief.report.reported'),
      render: (r) => r.reported,
      mono: true,
      className: 'w-52 align-top py-1',
    },
    {
      key: 'tolerance',
      header: t('debrief.report.tolerance'),
      render: (r) => r.tolerance,
      mono: true,
      className: 'w-24 align-top py-1',
    },
    {
      key: 'weight',
      header: t('debrief.report.weight'),
      render: (r) => r.weight,
      mono: true,
      align: 'right',
      className: 'w-16 align-top py-1',
    },
    {
      key: 'mark',
      header: t('debrief.report.mark'),
      render: (r) => r.mark,
      mono: true,
      align: 'right',
      className: 'w-20 align-top py-1',
    },
    {
      key: 'reason',
      header: t('debrief.report.reason'),
      render: (r) => r.reason,
      className: 'align-top py-1',
    },
  ]
  return (
    <div className="border-t border-line" data-testid="report-grades">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 px-3 py-2">
        <h4 className="m-0 text-xs font-medium text-ink-2">{t('debrief.report.title')}</h4>
        {report.filed ? (
          <p className="num m-0 text-xs text-ink-2">
            {t('debrief.report.filed', { count: report.reports_filed ?? 1 })}
            {report.quality != null &&
              ` · ${t('debrief.report.quality')} ${fmtScore(report.quality)}`}
            {report.timeliness != null &&
              ` · ${t('debrief.report.timeliness')} ${fmtScore(report.timeliness)}`}
            {report.score != null && ` · ${t('debrief.report.score')} ${fmtScore(report.score)}`}
          </p>
        ) : (
          <p className="m-0 text-xs text-ink-2">{t('debrief.report.none')}</p>
        )}
      </div>
      {report.filed && fields.length > 0 && (
        <Table
          caption={t('debrief.report.caption', { label: threat.label[lang] })}
          columns={columns}
          rows={fields.map((f) => fieldRow(f, lang, t))}
          rowKey={(r) => r.key}
          dense
        />
      )}
    </div>
  )
}

// ---------------------------------------------------------------------- not scored

interface QuietRow {
  key: string
  contact: string
  state: string
  reason: string
}

function NotScored({ threats, lang }: { threats: ThreatScore[]; lang: Lang }) {
  const { t } = useTranslation()
  const rows: QuietRow[] = threats.map((x) => ({
    key: x.threat_id,
    contact: contactHeading(x, lang, t),
    state: x.presented ? t('debrief.notScored.notWorked') : t('debrief.notScored.notPresented'),
    reason: (x.findings ?? []).map((f) => renderReason(f.reason, f.params, lang)).join(' '),
  }))
  const columns: Column<QuietRow>[] = [
    {
      key: 'contact',
      header: t('debrief.notScored.contact'),
      render: (r) => r.contact,
      className: 'w-[34%] align-top py-1',
    },
    {
      key: 'state',
      header: t('debrief.notScored.state'),
      render: (r) => <Badge>{r.state}</Badge>,
      className: 'w-40 align-top py-1',
    },
    {
      key: 'reason',
      header: t('debrief.notScored.why'),
      render: (r) => r.reason,
      className: 'align-top py-1',
    },
  ]
  return (
    <section aria-labelledby="not-scored-h" className="border border-line" data-testid="not-scored">
      <h2
        id="not-scored-h"
        className="m-0 border-b border-line px-3 py-2 text-sm font-medium text-ink-2"
      >
        {t('debrief.notScored.title')}
      </h2>
      <div className="text-ink-2">
        <Table
          caption={t('debrief.notScored.caption')}
          columns={columns}
          rows={rows}
          rowKey={(r) => r.key}
          dense
        />
      </div>
    </section>
  )
}
