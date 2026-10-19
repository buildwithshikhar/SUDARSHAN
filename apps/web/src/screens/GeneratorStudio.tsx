import { CheckmarkFilled, ErrorFilled } from '@carbon/icons-react'
import { useCallback, useEffect, useId, useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useLocation } from 'react-router-dom'
import { PageHeader } from '../layout/PageHeader'
import { ApiError } from '../lib/api'
import { localised } from '../live/restApi'
import { useLang } from '../live/format'
import { HeatLegend, HeatMap } from '../scenarios/HeatMap'
import {
  checkTitle,
  FeatureList,
  failureOf,
  fmt3,
  fmtPct,
  isAbort,
  useScenarioApi,
  type Failure,
} from '../scenarios/shared'
import {
  DIFFICULTY_AXES,
  TERRAINS,
  THREAT_MIXES,
  TIMES_OF_DAY,
  WEATHERS,
  type Archive,
  type Check,
  type DifficultyAxis,
  type GeneratedScenario,
  type GeneratorRequest,
  type ThreatMix,
} from '../scenarios/types'
import { Badge } from '../ui/Badge'
import { Button } from '../ui/Button'
import { Checkbox, Input, Select } from '../ui/Field'
import { InlineAlert } from '../ui/InlineAlert'
import { Panel } from '../ui/Panel'
import { EmptyState, ErrorState, LoadingState } from '../ui/States'
import { Table, type Column } from '../ui/Table'

const DEFAULT_REQUEST: GeneratorRequest = {
  seed: 260311,
  terrain: 'heron-ridge',
  time_of_day: 'day',
  weather: 'clear',
  difficulty: { threat_load: 40, ambiguity: 35, speed: 45, stealth: 20, degradation: 25 },
  threat_mix: ['single', 'swarm'],
  oracle_min_score: 80,
  max_attempts: 12,
}

const MAX_SEED = 4_294_967_295

function Fact({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid min-h-6 grid-cols-[148px_1fr] items-baseline gap-2 border-b border-line px-3 py-0.5 last:border-b-0">
      <dt className="text-sm text-ink-2">{label}</dt>
      <dd className="num m-0 min-w-0 break-words text-sm">{children}</dd>
    </div>
  )
}

function RangeRow({
  axis,
  value,
  onChange,
}: {
  axis: DifficultyAxis
  value: number
  onChange: (value: number) => void
}) {
  const { t } = useTranslation()
  const id = useId()
  return (
    <div className="grid grid-cols-[120px_1fr_40px] items-center gap-2">
      <label htmlFor={id} className="text-sm text-ink-2">
        {t(`scenarios.generator.axis.${axis}`)}
      </label>
      <input
        id={id}
        type="range"
        min={0}
        max={100}
        step={1}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        style={{ accentColor: 'var(--accent)' }}
        className="h-5 w-full"
      />
      <output htmlFor={id} className="num text-right text-sm" data-testid={`out-${axis}`}>
        {value}
      </output>
    </div>
  )
}

type Run =
  | { kind: 'idle' }
  | { kind: 'running'; what: 'generate' | 'batch' | 'code' }
  | { kind: 'failed'; failure: Failure; detail: string | null }

type ArchiveLoad =
  { kind: 'loading' } | { kind: 'error'; failure: Failure } | { kind: 'ready'; archive: Archive }

const detailOf = (error: unknown): string | null =>
  error instanceof ApiError && error.message && error.message !== 'Internal Server Error'
    ? error.message
    : null

function randomSeed(): number {
  const buffer = new Uint32Array(1)
  crypto.getRandomValues(buffer)
  return buffer[0] ?? 1
}

/** Route /content/generator: a request in, verified scenarios out, and how varied the archive is. */
export function GeneratorStudio() {
  const { t, i18n } = useTranslation()
  const lang = useLang()
  const api = useScenarioApi()
  const { search } = useLocation()

  const [request, setRequest] = useState<GeneratorRequest>(DEFAULT_REQUEST)
  const [seedText, setSeedText] = useState(String(DEFAULT_REQUEST.seed))
  const [oracleText, setOracleText] = useState(String(DEFAULT_REQUEST.oracle_min_score))
  const [attemptsText, setAttemptsText] = useState(String(DEFAULT_REQUEST.max_attempts))
  const [countText, setCountText] = useState('4')
  const [save, setSave] = useState(false)
  const [code, setCode] = useState('')
  const [codeNote, setCodeNote] = useState<{
    tone: 'info' | 'error' | 'warning'
    text: string
  } | null>(null)
  const [run, setRun] = useState<Run>({ kind: 'idle' })
  const [results, setResults] = useState<GeneratedScenario[]>([])
  const [savingId, setSavingId] = useState<string | null>(null)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [archive, setArchive] = useState<ArchiveLoad>({ kind: 'loading' })
  const [archiveAttempt, setArchiveAttempt] = useState(0)
  const [xAxis, setXAxis] = useState(0)
  const [yAxis, setYAxis] = useState(1)

  const loadArchive = useCallback(() => {
    setArchive({ kind: 'loading' })
    setArchiveAttempt((n) => n + 1)
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    api
      .archive(controller.signal)
      .then((a) => {
        if (!controller.signal.aborted) setArchive({ kind: 'ready', archive: a })
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted || isAbort(error)) return
        setArchive({ kind: 'error', failure: failureOf(error) })
      })
    return () => controller.abort()
  }, [api, archiveAttempt])

  // The text fields hold what was typed; the request holds what is valid.
  const seedOk = /^\d+$/.test(seedText.trim()) && Number(seedText) <= MAX_SEED
  const oracleOk =
    /^\d+$/.test(oracleText.trim()) && Number(oracleText) >= 50 && Number(oracleText) <= 100
  const attemptsOk =
    /^\d+$/.test(attemptsText.trim()) && Number(attemptsText) >= 1 && Number(attemptsText) <= 64
  const countOk =
    /^\d+$/.test(countText.trim()) && Number(countText) >= 1 && Number(countText) <= 12
  const mixOk = request.threat_mix.length > 0
  const valid = seedOk && oracleOk && attemptsOk && mixOk
  const busy = run.kind === 'running'

  const current = (): GeneratorRequest => ({
    ...request,
    seed: Number(seedText),
    oracle_min_score: Number(oracleText),
    max_attempts: Number(attemptsText),
  })

  const adopt = (r: GeneratorRequest) => {
    setRequest(r)
    setSeedText(String(r.seed))
    setOracleText(String(r.oracle_min_score))
    setAttemptsText(String(r.max_attempts))
  }

  const fail = (error: unknown) =>
    setRun({ kind: 'failed', failure: failureOf(error), detail: detailOf(error) })

  const generate = () => {
    setRun({ kind: 'running', what: 'generate' })
    api
      .generate({ request: current(), save })
      .then((r) => {
        setResults([r])
        setRun({ kind: 'idle' })
        if (r.saved) loadArchive()
      })
      .catch(fail)
  }
  const batch = () => {
    setRun({ kind: 'running', what: 'batch' })
    api
      .batch({ request: current(), count: Number(countText), save })
      .then((rs) => {
        setResults(rs)
        setRun({ kind: 'idle' })
        if (rs.some((r) => r.saved)) loadArchive()
      })
      .catch(fail)
  }
  const fromCode = () => {
    setRun({ kind: 'running', what: 'code' })
    api
      .generate({ code: code.trim(), save })
      .then((r) => {
        adopt(r.request)
        setResults([r])
        setRun({ kind: 'idle' })
        if (r.saved) loadArchive()
      })
      .catch(fail)
  }

  const decode = () => {
    setCodeNote(null)
    api
      .decode(code.trim())
      .then((d) => {
        adopt(d.request)
        setCodeNote(
          d.warning
            ? {
                tone: 'warning',
                text: t('scenarios.generator.code.versionWarning', { detail: d.warning }),
              }
            : {
                tone: 'info',
                text: t('scenarios.generator.code.decoded', { seed: d.request.seed }),
              },
        )
      })
      .catch((error: unknown) =>
        setCodeNote({
          tone: 'error',
          text:
            error instanceof ApiError && error.status < 500
              ? t('scenarios.generator.code.invalid')
              : t('scenarios.generator.code.unreachable'),
        }),
      )
  }
  const encode = () => {
    setCodeNote(null)
    api
      .encode(current())
      .then((c) => {
        setCode(c)
        setCodeNote({ tone: 'info', text: t('scenarios.generator.code.encoded') })
      })
      .catch(() => setCodeNote({ tone: 'error', text: t('scenarios.generator.code.unreachable') }))
  }
  const copy = async (text: string, select = false) => {
    try {
      await navigator.clipboard.writeText(text)
      setCodeNote({ tone: 'info', text: t('scenarios.generator.code.copied') })
    } catch {
      if (select) document.querySelector<HTMLInputElement>('[data-code-field]')?.select()
      setCodeNote({ tone: 'info', text: t('scenarios.generator.code.copyManual') })
    }
  }

  const keep = (r: GeneratedScenario) => {
    setSavingId(r.id)
    setSaveError(null)
    api
      .generate({ request: r.request, save: true })
      .then((saved) => {
        setResults((list) => list.map((x) => (x.id === r.id ? saved : x)))
        loadArchive()
      })
      .catch((error: unknown) =>
        setSaveError(
          error instanceof ApiError
            ? t('scenarios.generator.result.saveFailed', { detail: error.message })
            : t('scenarios.generator.result.saveUnreachable'),
        ),
      )
      .finally(() => setSavingId(null))
  }

  const toggleMix = (mix: ThreatMix, on: boolean) =>
    setRequest((r) => ({
      ...r,
      threat_mix: on
        ? THREAT_MIXES.filter((m) => m === mix || r.threat_mix.includes(m))
        : r.threat_mix.filter((m) => m !== mix),
    }))

  const checkColumns = (): Column<Check>[] => [
    {
      key: 'check',
      header: t('scenarios.editor.checks.check'),
      render: (c) => checkTitle(t, i18n, c),
    },
    {
      key: 'result',
      header: t('scenarios.editor.checks.result'),
      render: (c) => (
        <span className="inline-flex items-center gap-1">
          {c.passed ? (
            <CheckmarkFilled size={16} aria-hidden="true" className="text-track-neutral" />
          ) : (
            <ErrorFilled size={16} aria-hidden="true" className="text-track-hostile" />
          )}
          {c.passed ? t('scenarios.editor.checks.passed') : t('scenarios.editor.checks.failed')}
        </span>
      ),
    },
    {
      key: 'value',
      header: t('scenarios.editor.checks.value'),
      className: 'whitespace-nowrap',
      mono: true,
      align: 'right',
      render: (c) =>
        c.value === null
          ? '—'
          : c.code === 'solvability.score' && typeof c.value === 'number'
            ? fmtPct(c.value)
            : String(c.value),
    },
  ]

  const axes = archive.kind === 'ready' ? archive.archive.axes : []

  return (
    <>
      <PageHeader
        title={t('scenarios.generator.title')}
        crumbs={[t('nav.group.content'), t('nav.module.generator'), t('scenarios.generator.title')]}
        actions={<Badge>{t('scenarios.reference')}</Badge>}
      />
      <div className="grid grid-cols-1 items-start gap-4 xl:grid-cols-12">
        <div className="flex min-w-0 flex-col gap-4 xl:col-span-5">
          <Panel title={t('scenarios.generator.difficulty.title')}>
            <div
              className="flex flex-col gap-2"
              role="group"
              aria-label={t('scenarios.generator.difficulty.title')}
            >
              {DIFFICULTY_AXES.map((axis) => (
                <RangeRow
                  key={axis}
                  axis={axis}
                  value={request.difficulty[axis]}
                  onChange={(value) =>
                    setRequest((r) => ({ ...r, difficulty: { ...r.difficulty, [axis]: value } }))
                  }
                />
              ))}
            </div>
            <p className="m-0 mt-3 text-xs text-ink-2">
              {t('scenarios.generator.difficulty.note')}
            </p>
          </Panel>

          <Panel title={t('scenarios.generator.constraints.title')}>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <Select
                label={t('scenarios.generator.constraints.terrain')}
                value={request.terrain}
                onChange={(e) =>
                  setRequest((r) => ({
                    ...r,
                    terrain: e.target.value as GeneratorRequest['terrain'],
                  }))
                }
                options={TERRAINS.map((x) => ({ value: x, label: t(`scenarios.terrain.${x}`) }))}
              />
              <Select
                label={t('scenarios.generator.constraints.time')}
                value={request.time_of_day}
                onChange={(e) =>
                  setRequest((r) => ({
                    ...r,
                    time_of_day: e.target.value as GeneratorRequest['time_of_day'],
                  }))
                }
                options={TIMES_OF_DAY.map((x) => ({ value: x, label: t(`scenarios.time.${x}`) }))}
              />
              <Select
                label={t('scenarios.generator.constraints.weather')}
                value={request.weather}
                onChange={(e) => setRequest((r) => ({ ...r, weather: e.target.value }))}
                options={WEATHERS.map((x) => ({ value: x, label: t(`live.weather.${x}`) }))}
              />
            </div>
            <fieldset className="m-0 mt-3 border-0 p-0">
              <legend className="mb-1 p-0 text-sm text-ink-2">
                {t('scenarios.generator.constraints.mix')}
              </legend>
              <div className="grid grid-cols-2 gap-x-3 gap-y-1">
                {THREAT_MIXES.map((mix) => (
                  <Checkbox
                    key={mix}
                    label={t(`scenarios.generator.mix.${mix}`)}
                    checked={request.threat_mix.includes(mix)}
                    onChange={(e) => toggleMix(mix, e.target.checked)}
                  />
                ))}
              </div>
              {!mixOk && (
                <p role="alert" className="m-0 mt-1 text-xs text-track-hostile">
                  {t('scenarios.generator.constraints.mixError')}
                </p>
              )}
            </fieldset>
            <div className="mt-3 grid grid-cols-2 gap-3">
              <Input
                label={t('scenarios.generator.constraints.oracle')}
                hint={t('scenarios.generator.constraints.oracleHint')}
                inputMode="numeric"
                value={oracleText}
                onChange={(e) => setOracleText(e.target.value)}
                error={oracleOk ? undefined : t('scenarios.generator.constraints.oracleError')}
                className="num"
              />
              <Input
                label={t('scenarios.generator.constraints.attempts')}
                hint={t('scenarios.generator.constraints.attemptsHint')}
                inputMode="numeric"
                value={attemptsText}
                onChange={(e) => setAttemptsText(e.target.value)}
                error={attemptsOk ? undefined : t('scenarios.generator.constraints.attemptsError')}
                className="num"
              />
            </div>
          </Panel>

          <Panel title={t('scenarios.generator.seed.title')}>
            <div className="flex items-end gap-2">
              <div className="flex-1">
                <Input
                  label={t('scenarios.generator.seed.seed')}
                  inputMode="numeric"
                  value={seedText}
                  onChange={(e) => setSeedText(e.target.value)}
                  error={seedOk ? undefined : t('scenarios.generator.seed.error')}
                  className="num"
                />
              </div>
              <Button
                onClick={() => {
                  const s = randomSeed()
                  setSeedText(String(s))
                }}
              >
                {t('scenarios.generator.seed.randomise')}
              </Button>
            </div>
            <div className="mt-3 flex items-end gap-2">
              <div className="flex-1">
                <Input
                  data-code-field=""
                  label={t('scenarios.generator.code.label')}
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                  autoComplete="off"
                  spellCheck={false}
                  className="num"
                />
              </div>
              <Button onClick={decode} disabled={code.trim() === ''}>
                {t('scenarios.generator.code.decode')}
              </Button>
              <Button onClick={() => void copy(code, true)} disabled={code.trim() === ''}>
                {t('scenarios.generator.code.copy')}
              </Button>
              <Button onClick={encode} disabled={!valid}>
                {t('scenarios.generator.code.encode')}
              </Button>
            </div>
            <div className="mt-2" aria-live="polite">
              {codeNote && <InlineAlert tone={codeNote.tone}>{codeNote.text}</InlineAlert>}
            </div>
            <p className="m-0 mt-2 text-xs text-ink-2">{t('scenarios.generator.code.note')}</p>
          </Panel>

          <Panel title={t('scenarios.generator.run.title')}>
            <div className="flex flex-col gap-3">
              <Checkbox
                label={t('scenarios.generator.run.save')}
                checked={save}
                onChange={(e) => setSave(e.target.checked)}
              />
              <div className="flex flex-wrap items-end gap-2">
                <Button variant="primary" disabled={!valid || busy} onClick={generate}>
                  {run.kind === 'running' && run.what === 'generate'
                    ? t('scenarios.generator.run.generating')
                    : t('scenarios.generator.run.generate')}
                </Button>
                <div className="w-[88px]">
                  <Input
                    label={t('scenarios.generator.run.count')}
                    inputMode="numeric"
                    value={countText}
                    onChange={(e) => setCountText(e.target.value)}
                    error={countOk ? undefined : t('scenarios.generator.run.countError')}
                    className="num"
                  />
                </div>
                <Button disabled={!valid || !countOk || busy} onClick={batch}>
                  {run.kind === 'running' && run.what === 'batch'
                    ? t('scenarios.generator.run.generating')
                    : t('scenarios.generator.run.batch')}
                </Button>
                <Button disabled={code.trim() === '' || busy} onClick={fromCode}>
                  {t('scenarios.generator.run.fromCode')}
                </Button>
              </div>
              <p className="m-0 text-xs text-ink-2">{t('scenarios.generator.run.note')}</p>
            </div>
          </Panel>
        </div>

        <div className="flex min-w-0 flex-col gap-4 xl:col-span-7">
          <Panel
            title={t('scenarios.generator.result.title')}
            flush
            actions={
              results.length > 0 ? (
                <span className="num text-xs text-ink-2">
                  {t('scenarios.generator.result.count', { count: results.length })}
                </span>
              ) : undefined
            }
          >
            {run.kind === 'running' && (
              <div>
                <LoadingState label={t('scenarios.generator.result.loading')} />
                <p className="m-0 px-3 pb-3 text-xs text-ink-2">
                  {t('scenarios.generator.result.loadingNote')}
                </p>
              </div>
            )}
            {run.kind === 'failed' && (
              <div className="p-3">
                <ErrorState
                  offline={run.failure === 'network'}
                  title={t(`scenarios.generator.result.error.${run.failure}`)}
                  description={run.detail ?? t('scenarios.generator.result.errorBody')}
                  retryLabel={t('app.retry')}
                  onRetry={generate}
                />
              </div>
            )}
            {run.kind === 'idle' && results.length === 0 && (
              <div className="p-3">
                <EmptyState
                  title={t('scenarios.generator.result.emptyTitle')}
                  description={t('scenarios.generator.result.emptyBody')}
                />
              </div>
            )}
            {saveError && (
              <div className="p-3 pb-0">
                <InlineAlert tone="error">{saveError}</InlineAlert>
              </div>
            )}
            {run.kind !== 'running' && (
              <ol className="m-0 list-none p-0">
                {results.map((r) => (
                  <li key={r.id} className="border-b border-line last:border-b-0">
                    <article data-testid="result" data-id={r.id} aria-labelledby={`r-${r.id}`}>
                      <header className="flex items-start justify-between gap-3 px-3 py-2">
                        <div className="min-w-0">
                          <h3 id={`r-${r.id}`} className="num m-0 truncate text-sm font-semibold">
                            {r.id}
                          </h3>
                          <p className="m-0 text-xs text-ink-2">{localised(r.spec.title, lang)}</p>
                        </div>
                        <p
                          data-testid="result-wording"
                          data-wording={r.solvability_wording}
                          className="m-0 inline-flex shrink-0 items-center gap-1 text-sm font-semibold"
                        >
                          <CheckmarkFilled
                            size={16}
                            aria-hidden="true"
                            className="text-track-neutral"
                          />
                          {t('scenarios.wording.verified')}
                        </p>
                      </header>
                      <Table
                        caption={`${t('scenarios.editor.checks.caption')}: ${r.id}`}
                        columns={checkColumns()}
                        rows={r.checks}
                        rowKey={(c) => c.name}
                        dense
                      />
                      <dl className="m-0 border-t border-line">
                        <Fact label={t('scenarios.generator.result.attempts')}>{r.attempts}</Fact>
                        <Fact label={t('scenarios.generator.result.relaxations')}>
                          {r.relaxations.length === 0 ? (
                            t('scenarios.generator.result.noRelaxations')
                          ) : (
                            <ul className="m-0 list-none p-0" data-testid="relaxations">
                              {r.relaxations.map((x) => (
                                <li key={x} lang="en">
                                  {x}
                                </li>
                              ))}
                            </ul>
                          )}
                        </Fact>
                        <Fact label={t('scenarios.generator.result.diversity')}>
                          {r.diversity.novelty === null ? '—' : fmt3(r.diversity.novelty)} /{' '}
                          {fmt3(r.diversity.threshold)} ·{' '}
                          {r.diversity.passes === null
                            ? t('scenarios.editor.checks.diversityNone')
                            : r.diversity.passes
                              ? t('scenarios.editor.checks.diversityPass')
                              : t('scenarios.editor.checks.diversityFail')}{' '}
                          ·{' '}
                          {t('scenarios.generator.result.history', {
                            count: r.diversity.history_size,
                          })}
                        </Fact>
                        <Fact label={t('scenarios.generator.result.version')}>
                          {r.generator_version} · {r.spec_sha256.slice(0, 12)}
                        </Fact>
                        <Fact label={t('scenarios.generator.result.code')}>
                          <span data-testid="result-code">{r.code}</span>{' '}
                          <button
                            type="button"
                            className="h-6 border-0 bg-transparent p-0 text-sm text-accent underline"
                            onClick={() => void copy(r.code)}
                          >
                            {t('scenarios.generator.code.copy')}
                          </button>
                        </Fact>
                      </dl>
                      <FeatureList features={r.features} wide />
                      <div className="flex items-center gap-3 border-t border-line px-3 py-2">
                        {r.saved ? (
                          <>
                            <Badge tone="neutralTrack">
                              {t('scenarios.generator.result.saved')}
                            </Badge>
                            <Link
                              to={`/content/scenarios/editor/${encodeURIComponent(r.id)}${search}`}
                            >
                              {t('scenarios.library.open')}
                            </Link>
                          </>
                        ) : (
                          <Button disabled={savingId !== null} onClick={() => keep(r)}>
                            {savingId === r.id
                              ? t('scenarios.generator.result.saving')
                              : t('scenarios.generator.result.save')}
                          </Button>
                        )}
                      </div>
                    </article>
                  </li>
                ))}
              </ol>
            )}
            <p className="m-0 border-t border-line px-3 py-2 text-xs text-ink-2">
              {t('scenarios.check.note')}
            </p>
          </Panel>

          <Panel title={t('scenarios.generator.report.title')} flush>
            {archive.kind === 'loading' && (
              <LoadingState label={t('scenarios.generator.report.loading')} />
            )}
            {archive.kind === 'error' && (
              <div className="p-3">
                <ErrorState
                  offline={archive.failure === 'network'}
                  title={t(`scenarios.generator.report.error.${archive.failure}`)}
                  description={t('scenarios.generator.report.errorBody')}
                  retryLabel={t('app.retry')}
                  onRetry={loadArchive}
                />
              </div>
            )}
            {archive.kind === 'ready' && (
              <div className="flex flex-col gap-3 p-3">
                {archive.archive.cells.length === 0 && (
                  <InlineAlert tone="info">{t('scenarios.generator.report.emptyBody')}</InlineAlert>
                )}
                <div className="grid grid-cols-2 gap-3">
                  <Select
                    label={t('scenarios.generator.report.xAxis')}
                    value={String(xAxis)}
                    onChange={(e) => {
                      const next = Number(e.target.value)
                      setXAxis(next)
                      if (next === yAxis) setYAxis(axes.findIndex((_, i) => i !== next))
                    }}
                    options={axes.map((a, i) => ({
                      value: String(i),
                      label: t(`scenarios.axis.${a.name}`, { defaultValue: a.name }),
                    }))}
                  />
                  <Select
                    label={t('scenarios.generator.report.yAxis')}
                    value={String(yAxis)}
                    onChange={(e) => {
                      const next = Number(e.target.value)
                      setYAxis(next)
                      if (next === xAxis) setXAxis(axes.findIndex((_, i) => i !== next))
                    }}
                    options={axes.map((a, i) => ({
                      value: String(i),
                      label: t(`scenarios.axis.${a.name}`, { defaultValue: a.name }),
                    }))}
                  />
                </div>
                <HeatMap archive={archive.archive} xAxis={xAxis} yAxis={yAxis} />
                <HeatLegend />
                <p className="m-0 text-xs text-ink-2">{t('scenarios.generator.report.note')}</p>
              </div>
            )}
            {archive.kind === 'ready' && (
              <dl className="m-0 border-t border-line" data-testid="archive-metrics">
                <Fact label={t('scenarios.generator.report.coverage')}>
                  <span data-testid="metric-coverage">
                    {fmtPct(archive.archive.metrics.coverage)}
                  </span>{' '}
                  <span className="text-ink-2">
                    {t('scenarios.generator.report.cells', {
                      filled: archive.archive.metrics.filled,
                      total: archive.archive.metrics.total,
                    })}
                  </span>
                </Fact>
                <Fact label={t('scenarios.generator.report.qd')}>
                  <span data-testid="metric-qd">{fmt3(archive.archive.metrics.qd_score)}</span>
                </Fact>
                <Fact label={t('scenarios.generator.report.pairwise')}>
                  <span data-testid="metric-pairwise">
                    {fmt3(archive.archive.metrics.mean_pairwise_distance)}
                  </span>
                </Fact>
              </dl>
            )}
          </Panel>
        </div>
      </div>
    </>
  )
}
