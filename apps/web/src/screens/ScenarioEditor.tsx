import { CheckmarkFilled, ErrorFilled } from '@carbon/icons-react'
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'
import { PageHeader } from '../layout/PageHeader'
import { ApiError } from '../lib/api'
import { fmtElapsed, fmtHours, useLang } from '../live/format'
import { localised } from '../live/restApi'
import { dispositionLabel } from '../live/scoring'
import { CodeEditor, type CodeEditorHandle } from '../scenarios/CodeEditor'
import { flightTimeS, MapLegend, PreviewMap, TimeStrip } from '../scenarios/charts'
import {
  checkTitle,
  FeatureList,
  errorText,
  failureOf,
  fmt3,
  fmtPct,
  isAbort,
  lintText,
  modalityOf,
  SeverityMark,
  useScenarioApi,
  type Failure,
} from '../scenarios/shared'
import type {
  CheckResponse,
  PreviewResponse,
  ScenarioDetail,
  ScenarioSpec,
  ValidateResponse,
} from '../scenarios/types'
import { Badge } from '../ui/Badge'
import { Button } from '../ui/Button'
import { Dialog } from '../ui/Dialog'
import { Input } from '../ui/Field'
import { InlineAlert } from '../ui/InlineAlert'
import { Panel } from '../ui/Panel'
import { EmptyState, ErrorState, LoadingState } from '../ui/States'
import { Table, type Column } from '../ui/Table'

const DEBOUNCE_MS = 400

type Validation =
  | { kind: 'idle' }
  | { kind: 'ready'; yaml: string; res: ValidateResponse }
  | { kind: 'failed'; yaml: string; failure: Failure }

type Run<T> =
  | { kind: 'idle' }
  | { kind: 'running' }
  | { kind: 'ready'; yaml: string; res: T }
  | { kind: 'failed'; failure: Failure }

type Loaded =
  | { kind: 'none' }
  | { kind: 'loading' }
  | { kind: 'failed'; failure: Failure }
  | { kind: 'ready'; detail: ScenarioDetail }

function Fact({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid min-h-6 grid-cols-[148px_1fr] items-baseline gap-2 border-b border-line px-3 py-0.5 last:border-b-0">
      <dt className="text-sm text-ink-2">{label}</dt>
      <dd className="num m-0 text-sm">{children}</dd>
    </div>
  )
}

function Note({ children }: { children: ReactNode }) {
  return <p className="m-0 border-t border-line px-3 py-2 text-xs text-ink-2">{children}</p>
}

function NoSpec() {
  const { t } = useTranslation()
  return (
    <div className="p-3">
      <EmptyState
        title={t('scenarios.editor.summary.emptyTitle')}
        description={t('scenarios.editor.summary.emptyBody')}
      />
    </div>
  )
}

const km = (m: number) => `${(m / 1000).toFixed(m % 1000 === 0 ? 0 : 1)} km`

function TerrainPanel({ spec, stale }: { spec: ScenarioSpec | null; stale: boolean }) {
  const { t } = useTranslation()
  const lang = useLang()
  const zones = spec?.zones ?? []
  const columns: Column<(typeof zones)[number]>[] = [
    {
      key: 'zone',
      header: t('scenarios.editor.terrain.zone'),
      render: (z) => localised(z.label, lang),
    },
    {
      key: 'role',
      header: t('scenarios.editor.terrain.role'),
      render: (z) => t(`live.zone.${z.role}`),
    },
    {
      key: 'radius',
      header: t('scenarios.editor.terrain.radius'),
      mono: true,
      align: 'right',
      render: (z) => `${z.radius_m} m`,
    },
  ]
  return (
    <Panel
      title={t('scenarios.editor.terrain.title')}
      flush
      actions={stale && spec ? <Badge>{t('scenarios.editor.summary.lastValid')}</Badge> : undefined}
    >
      {!spec ? (
        <NoSpec />
      ) : (
        <>
          <dl className="m-0">
            <Fact label={t('scenarios.editor.terrain.terrain')}>
              {spec.world.terrain.kind === 'pack'
                ? `${t(`scenarios.terrain.${spec.world.terrain.id}`, { defaultValue: spec.world.terrain.id })} · ${spec.world.terrain.id} ${spec.world.terrain.version}`
                : t('scenarios.editor.terrain.flat', {
                    elevation: spec.world.terrain.elevation_m ?? 0,
                  })}
            </Fact>
            <Fact label={t('scenarios.editor.terrain.area')}>±{km(spec.world.half_extent_m)}</Fact>
            <Fact label={t('scenarios.editor.terrain.rules')}>
              {spec.rule_pack.id} {spec.rule_pack.version}
            </Fact>
            <Fact label={t('scenarios.editor.terrain.assets')}>
              {(spec.assets ?? []).map((a) => localised(a.label, lang)).join(' · ') || '—'}
            </Fact>
          </dl>
          {zones.length > 0 && (
            <Table
              caption={t('scenarios.editor.terrain.zones')}
              columns={columns}
              rows={zones}
              rowKey={(z) => z.id}
              dense
            />
          )}
          <Note>{t('scenarios.editor.terrain.note')}</Note>
        </>
      )}
    </Panel>
  )
}

function ThreatPanel({ spec, stale }: { spec: ScenarioSpec | null; stale: boolean }) {
  const { t } = useTranslation()
  const lang = useLang()
  const threats = spec?.threats ?? []
  const groupOf = (id: string) => spec?.groups?.find((g) => g.members.includes(id))?.id ?? '—'
  const columns: Column<(typeof threats)[number]>[] = [
    { key: 'id', header: t('scenarios.editor.threats.id'), mono: true, render: (x) => x.id },
    {
      key: 'class',
      header: t('scenarios.editor.threats.class'),
      mono: true,
      render: (x) => x.class_id,
    },
    {
      key: 'disposition',
      header: t('scenarios.editor.threats.disposition'),
      render: (x) => dispositionLabel(x.disposition ?? 'hostile', lang),
    },
    {
      key: 'spawn',
      header: t('scenarios.editor.threats.spawn'),
      mono: true,
      align: 'right',
      render: (x) => `${x.spawn_s} s`,
    },
    {
      key: 'flight',
      header: t('scenarios.editor.threats.flight'),
      mono: true,
      align: 'right',
      render: (x) => `${Math.round(flightTimeS(x))} s`,
    },
    {
      key: 'route',
      header: t('scenarios.editor.threats.route'),
      mono: true,
      align: 'right',
      render: (x) => x.route.length,
    },
    {
      key: 'group',
      header: t('scenarios.editor.threats.group'),
      mono: true,
      render: (x) => groupOf(x.id),
    },
  ]
  return (
    <Panel
      title={t('scenarios.editor.threats.title')}
      flush
      actions={stale && spec ? <Badge>{t('scenarios.editor.summary.lastValid')}</Badge> : undefined}
    >
      {!spec ? (
        <NoSpec />
      ) : (
        <>
          <Table
            caption={t('scenarios.editor.threats.caption')}
            columns={columns}
            rows={threats}
            rowKey={(x) => x.id}
            dense
          />
          <div className="border-t border-line p-3">
            <TimeStrip spec={spec} />
            <p className="m-0 mt-2 text-xs text-ink-2">{t('scenarios.editor.threats.note')}</p>
          </div>
          <Note>{t('scenarios.editor.threats.reference')}</Note>
        </>
      )}
    </Panel>
  )
}

function SensorPanel({ spec, stale }: { spec: ScenarioSpec | null; stale: boolean }) {
  const { t } = useTranslation()
  const sensors = spec?.sensors ?? []
  const columns: Column<(typeof sensors)[number]>[] = [
    { key: 'id', header: t('scenarios.editor.sensors.id'), mono: true, render: (s) => s.id },
    {
      key: 'modality',
      header: t('scenarios.editor.sensors.modality'),
      render: (s) =>
        t(`live.modality.${modalityOf(s.profile.id)}`, { defaultValue: modalityOf(s.profile.id) }),
    },
    {
      key: 'profile',
      header: t('scenarios.editor.sensors.profile'),
      mono: true,
      render: (s) => `${s.profile.id} ${s.profile.version}`,
    },
    {
      key: 'position',
      header: t('scenarios.editor.sensors.position'),
      mono: true,
      render: (s) => `${Math.round(s.position.x)}, ${Math.round(s.position.y)}`,
    },
    {
      key: 'boresight',
      header: t('scenarios.editor.sensors.boresight'),
      mono: true,
      align: 'right',
      render: (s) => `${Math.round(s.boresight_deg)}°`,
    },
  ]
  const w = spec?.world.weather
  return (
    <Panel
      title={t('scenarios.editor.sensors.title')}
      flush
      actions={stale && spec ? <Badge>{t('scenarios.editor.summary.lastValid')}</Badge> : undefined}
    >
      {!spec ? (
        <NoSpec />
      ) : (
        <>
          {sensors.length === 0 ? (
            <div className="p-3">
              <EmptyState title={t('scenarios.editor.sensors.none')} />
            </div>
          ) : (
            <Table
              caption={t('scenarios.editor.sensors.caption')}
              columns={columns}
              rows={sensors}
              rowKey={(s) => s.id}
              dense
            />
          )}
          {w && (
            <dl className="m-0 border-t border-line">
              <Fact label={t('scenarios.editor.sensors.conditions')}>
                {t(`live.weather.${w.condition}`, { defaultValue: w.condition })} ·{' '}
                {t('live.top.vis')} {km(w.visibility_m)} ·{' '}
                {fmtHours(spec.world.start_time_of_day_h)}
              </Fact>
            </dl>
          )}
          <Note>{t('scenarios.editor.sensors.note')}</Note>
        </>
      )}
    </Panel>
  )
}

function WeatherPanel({ spec, stale }: { spec: ScenarioSpec | null; stale: boolean }) {
  const { t } = useTranslation()
  const w = spec?.world.weather
  return (
    <Panel
      title={t('scenarios.editor.weather.title')}
      flush
      actions={stale && spec ? <Badge>{t('scenarios.editor.summary.lastValid')}</Badge> : undefined}
    >
      {!spec || !w ? (
        <NoSpec />
      ) : (
        <>
          <dl className="m-0">
            <Fact label={t('scenarios.editor.weather.start')}>
              {fmtHours(spec.world.start_time_of_day_h)} · {fmtElapsed(spec.duration_s)}
            </Fact>
            <Fact label={t('scenarios.editor.weather.condition')}>
              {t(`live.weather.${w.condition}`, { defaultValue: w.condition })}
            </Fact>
            <Fact label={t('scenarios.editor.weather.visibility')}>{km(w.visibility_m)}</Fact>
            <Fact label={t('scenarios.editor.weather.wind')}>
              {Math.round(w.wind_from_deg)}° / {w.wind_speed_mps.toFixed(1)} {t('live.units.mps')} ·{' '}
              {t('scenarios.editor.weather.gust', { sigma: w.gust_sigma_mps.toFixed(1) })}
            </Fact>
            <Fact label={t('scenarios.editor.weather.temperature')}>
              {Math.round(w.temperature_c)} °C
            </Fact>
            <Fact label={t('scenarios.editor.weather.cloud')}>
              {Math.round(w.cloud_cover_pct)}%
            </Fact>
          </dl>
          <Note>{t('scenarios.editor.weather.note')}</Note>
        </>
      )}
    </Panel>
  )
}

function formatValue(code: string, value: number | string | null): string {
  if (value === null) return '—'
  if (code === 'solvability.score' && typeof value === 'number') return fmtPct(value)
  return String(value)
}

/** Route /content/scenarios/editor[/:id]: YAML in, validation, checks and a preview run out. */
export function ScenarioEditor() {
  const { id } = useParams()
  const { t, i18n } = useTranslation()
  const lang = useLang()
  const api = useScenarioApi()
  const navigate = useNavigate()
  const { search } = useLocation()
  const editor = useRef<CodeEditorHandle>(null)
  const immediate = useRef(false)

  const [yaml, setYaml] = useState('')
  const [loaded, setLoaded] = useState<Loaded>(id ? { kind: 'loading' } : { kind: 'none' })
  const [loadAttempt, setLoadAttempt] = useState(0)
  const [val, setVal] = useState<Validation>({ kind: 'idle' })
  const [valAttempt, setValAttempt] = useState(0)
  const [lastSpec, setLastSpec] = useState<ScenarioSpec | null>(null)
  const [seed, setSeed] = useState('')
  const [checks, setChecks] = useState<Run<CheckResponse>>({ kind: 'idle' })
  const [preview, setPreview] = useState<Run<PreviewResponse>>({ kind: 'idle' })
  const [caret, setCaret] = useState({ line: 1, column: 1 })
  const [moved, setMoved] = useState('')
  const [openId, setOpenId] = useState('')
  const [saving, setSaving] = useState(false)
  const [saveOpen, setSaveOpen] = useState(false)
  const [tags, setTags] = useState('')
  const [saveError, setSaveError] = useState<string | null>(null)
  const [saved, setSaved] = useState<string | null>(null)

  // A scenario opened by id: its YAML replaces the text.
  const [seenId, setSeenId] = useState(id)
  if (seenId !== id) {
    setSeenId(id)
    setLoaded(id ? { kind: 'loading' } : { kind: 'none' })
  }
  useEffect(() => {
    if (!id) return
    const controller = new AbortController()
    api
      .get(id, controller.signal)
      .then((detail) => {
        if (controller.signal.aborted) return
        immediate.current = true
        setYaml(detail.yaml)
        setLoaded({ kind: 'ready', detail })
        setChecks({ kind: 'idle' })
        setPreview({ kind: 'idle' })
        setSaved(null)
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted || isAbort(error)) return
        setLoaded({ kind: 'failed', failure: failureOf(error) })
      })
    return () => controller.abort()
  }, [api, id, loadAttempt])

  // Debounced validation of the text; the last result stays on screen while a new one is pending.
  useEffect(() => {
    if (yaml.trim() === '') return
    const controller = new AbortController()
    const wait = immediate.current ? 0 : DEBOUNCE_MS
    immediate.current = false
    const timer = setTimeout(() => {
      api
        .validate(yaml, controller.signal)
        .then((res) => {
          if (controller.signal.aborted) return
          setVal({ kind: 'ready', yaml, res })
          if (res.spec) setLastSpec(res.spec)
        })
        .catch((error: unknown) => {
          if (controller.signal.aborted || isAbort(error)) return
          setVal({ kind: 'failed', yaml, failure: failureOf(error) })
        })
    }, wait)
    return () => {
      clearTimeout(timer)
      controller.abort()
    }
  }, [api, yaml, valAttempt])

  const empty = yaml.trim() === ''
  const result = val.kind === 'ready' ? val.res : null
  const pending = !empty && (val.kind === 'idle' || val.yaml !== yaml)
  const spec = !empty ? (result?.spec ?? lastSpec) : null
  const stale = !!spec && result?.spec == null

  const items = useMemo(() => {
    if (!result || empty) return []
    return [
      ...result.errors.map((e) => ({ kind: 'error' as const, line: e.line, column: e.column, e })),
      ...result.lint.map((l) => ({ kind: 'lint' as const, line: l.line, column: l.column, l })),
    ].sort((a, b) => a.line - b.line || a.column - b.column)
  }, [result, empty])

  const markers = useMemo(() => {
    const map = new Map<number, 'error' | 'warning'>()
    for (const item of items) {
      const severity = item.kind === 'error' ? 'error' : item.l.severity
      if (map.get(item.line) !== 'error') map.set(item.line, severity)
    }
    return map
  }, [items])

  const errorCount = items.filter((i) => i.kind === 'error' || i.l.severity === 'error').length
  const warningCount = items.length - errorCount

  const jump = useCallback(
    (line: number, column: number) => {
      editor.current?.jumpTo(line, column)
      setMoved(t('scenarios.editor.validation.moved', { line }))
    },
    [t],
  )

  const runChecks = () => {
    setChecks({ kind: 'running' })
    const n = seed.trim() === '' ? undefined : Number(seed)
    api
      .check(yaml, n)
      .then((res) => setChecks({ kind: 'ready', yaml, res }))
      .catch((error: unknown) => setChecks({ kind: 'failed', failure: failureOf(error) }))
  }
  const runPreview = () => {
    setPreview({ kind: 'running' })
    const n = seed.trim() === '' ? undefined : Number(seed)
    api
      .preview(yaml, n)
      .then((res) => setPreview({ kind: 'ready', yaml, res }))
      .catch((error: unknown) => setPreview({ kind: 'failed', failure: failureOf(error) }))
  }

  const save = async () => {
    setSaving(true)
    setSaveError(null)
    try {
      const row = await api.save({
        yaml,
        tags: tags
          .split(',')
          .map((x) => x.trim())
          .filter(Boolean),
      })
      setSaved(row.id)
      setSaveOpen(false)
    } catch (error) {
      setSaveError(
        error instanceof ApiError
          ? t('scenarios.editor.save.failed', { detail: error.message })
          : t('scenarios.editor.save.unreachable'),
      )
    } finally {
      setSaving(false)
    }
  }

  const seedValid = seed.trim() === '' || /^\d+$/.test(seed.trim())
  const canRun = !empty && !pending && !!result?.valid && seedValid
  const canSave = !empty && !pending && !!result?.valid

  const checkColumns: Column<CheckResponse['solvability']['checks'][number]>[] = [
    {
      key: 'check',
      header: t('scenarios.editor.checks.check'),
      render: (c) => (
        <>
          <span className="block">{checkTitle(t, i18n, c)}</span>
          <span className="num block text-xs text-ink-2">{c.name}</span>
        </>
      ),
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
      render: (c) => formatValue(c.code, c.value),
    },
    {
      key: 'detail',
      header: t('scenarios.editor.checks.detail'),
      render: (c) => (
        <span lang="en" className="text-xs text-ink-2">
          {c.detail}
        </span>
      ),
    },
  ]

  const contactColumns: Column<PreviewResponse['contacts'][number]>[] = [
    { key: 'id', header: t('scenarios.editor.threats.id'), mono: true, render: (c) => c.id },
    {
      key: 'disposition',
      header: t('scenarios.editor.threats.disposition'),
      render: (c) => dispositionLabel(c.disposition, lang),
    },
    {
      key: 'class',
      header: t('scenarios.editor.threats.class'),
      mono: true,
      render: (c) => c.class_id,
    },
    {
      key: 'first',
      header: t('scenarios.editor.preview.firstReport'),
      mono: true,
      align: 'right',
      render: (c) => (c.first_report_s === null ? '—' : `${c.first_report_s.toFixed(1)} s`),
    },
    {
      key: 'answered',
      header: t('scenarios.editor.preview.answered'),
      mono: true,
      align: 'right',
      render: (c) => (c.answered_s === null ? '—' : `${c.answered_s.toFixed(1)} s`),
    },
    {
      key: 'score',
      header: t('scenarios.editor.preview.score'),
      mono: true,
      align: 'right',
      render: (c) => (c.score === null ? '—' : fmtPct(c.score)),
    },
  ]

  const title = t('scenarios.editor.title')
  const header = (
    <PageHeader
      title={title}
      crumbs={[t('nav.group.content'), t('nav.module.scenarios'), title]}
      actions={
        <div className="flex items-end gap-2">
          <form
            className="flex items-end gap-2"
            onSubmit={(e) => {
              e.preventDefault()
              const target = openId.trim()
              if (target)
                navigate(`/content/scenarios/editor/${encodeURIComponent(target)}${search}`)
            }}
          >
            <Input
              label={t('scenarios.editor.openById')}
              value={openId}
              onChange={(e) => setOpenId(e.target.value)}
              className="num w-[220px]"
              autoComplete="off"
            />
            <Button type="submit" disabled={openId.trim() === ''}>
              {t('scenarios.editor.open')}
            </Button>
          </form>
          <Button
            variant="primary"
            disabled={!canSave}
            onClick={() => {
              setSaveError(null)
              setSaveOpen(true)
            }}
          >
            {t('scenarios.editor.save.button')}
          </Button>
        </div>
      }
    />
  )

  if (loaded.kind === 'loading') {
    return (
      <>
        {header}
        <LoadingState label={t('scenarios.editor.loading')} />
      </>
    )
  }
  if (loaded.kind === 'failed') {
    return (
      <>
        {header}
        <div className="max-w-[640px]">
          <ErrorState
            offline={loaded.failure === 'network'}
            title={t(`scenarios.editor.loadError.${loaded.failure}`)}
            description={t('scenarios.editor.loadErrorBody', { id: id ?? '' })}
            retryLabel={t('app.retry')}
            onRetry={() => {
              setLoaded({ kind: 'loading' })
              setLoadAttempt((n) => n + 1)
            }}
          />
          <p className="mt-3 text-sm">
            <Link to={`/content/scenarios${search}`}>{t('scenarios.editor.toLibrary')}</Link>
          </p>
        </div>
      </>
    )
  }

  const lineCount = yaml.split('\n').length
  const detail = loaded.kind === 'ready' ? loaded.detail : null

  return (
    <>
      {header}
      <div className="grid grid-cols-1 items-start gap-4 xl:grid-cols-12">
        <div className="flex min-w-0 flex-col gap-4 xl:col-span-7">
          {saved && (
            <InlineAlert tone="success">
              {t('scenarios.editor.save.done', { id: saved })}{' '}
              <Link to={`/content/scenarios${search}`}>{t('scenarios.editor.toLibrary')}</Link>
            </InlineAlert>
          )}
          <Panel
            title={t('scenarios.editor.yaml')}
            bodyClassName="p-0"
            flush
            actions={
              <span className="num text-xs text-ink-2" data-testid="caret">
                {t('scenarios.editor.caret', { line: caret.line, column: caret.column })} ·{' '}
                {t('scenarios.editor.lines', { count: lineCount })}
              </span>
            }
          >
            <CodeEditor
              ref={editor}
              value={yaml}
              onChange={setYaml}
              markers={markers}
              label={t('scenarios.editor.yamlLabel')}
              describedBy="editor-hint"
              onCaret={(line, column) => setCaret({ line, column })}
              className="h-[360px] border-0"
            />
            <p id="editor-hint" className="m-0 border-t border-line px-3 py-2 text-xs text-ink-2">
              {detail
                ? t('scenarios.editor.opened', {
                    id: detail.id,
                    origin: t(`scenarios.origin.${detail.origin}`),
                  })
                : t('scenarios.editor.hint')}
            </p>
          </Panel>

          <Panel
            title={t('scenarios.editor.validation.title')}
            flush
            actions={
              pending ? (
                <span className="text-xs text-ink-2" data-testid="validating">
                  {t('scenarios.editor.validation.checking')}
                </span>
              ) : undefined
            }
          >
            <p role="status" className="sr-only">
              {moved}
            </p>
            {empty && (
              <div className="p-3">
                <EmptyState
                  title={t('scenarios.editor.validation.emptyTitle')}
                  description={t('scenarios.editor.validation.emptyBody')}
                  action={
                    <Link to={`/content/scenarios${search}`}>
                      {t('scenarios.editor.toLibrary')}
                    </Link>
                  }
                />
              </div>
            )}
            {!empty && val.kind === 'failed' && val.yaml === yaml && (
              <div className="p-3">
                <ErrorState
                  offline={val.failure === 'network'}
                  title={t(`scenarios.editor.validation.error.${val.failure}`)}
                  description={t('scenarios.editor.validation.errorBody')}
                  retryLabel={t('app.retry')}
                  onRetry={() => setValAttempt((n) => n + 1)}
                />
              </div>
            )}
            {!empty && val.kind === 'idle' && (
              <div className="p-3">
                <LoadingState label={t('scenarios.editor.validation.loading')} />
              </div>
            )}
            {!empty && result && (
              <>
                <p
                  role="status"
                  data-testid="validation-summary"
                  data-valid={result.valid ? 'true' : 'false'}
                  className="m-0 flex items-center gap-2 border-b border-line px-3 py-2 text-sm"
                >
                  {result.valid ? (
                    <CheckmarkFilled size={16} aria-hidden="true" className="text-track-neutral" />
                  ) : (
                    <ErrorFilled size={16} aria-hidden="true" className="text-track-hostile" />
                  )}
                  <span className="font-semibold">
                    {result.valid
                      ? t('scenarios.editor.validation.valid')
                      : t('scenarios.editor.validation.invalid')}
                  </span>
                  <span className="num text-ink-2">
                    {t('scenarios.editor.validation.counts', {
                      errors: errorCount,
                      warnings: warningCount,
                    })}
                  </span>
                </p>
                {items.length === 0 ? (
                  <p className="m-0 px-3 py-2 text-sm text-ink-2">
                    {t('scenarios.editor.validation.clean')}
                  </p>
                ) : (
                  <ul
                    className="m-0 list-none p-0"
                    aria-label={t('scenarios.editor.validation.list')}
                  >
                    {items.map((item, index) => {
                      const rendered =
                        item.kind === 'error'
                          ? errorText(t, i18n, item.e)
                          : lintText(t, i18n, item.l)
                      const code = item.kind === 'error' ? item.e.code : item.l.code
                      const severity = item.kind === 'error' ? 'error' : item.l.severity
                      return (
                        <li
                          key={`${item.line}-${code}-${index}`}
                          className="border-b border-line last:border-b-0"
                        >
                          <button
                            type="button"
                            data-line={item.line}
                            data-code={code}
                            onClick={() => jump(item.line, item.column)}
                            className="grid w-full grid-cols-[64px_88px_1fr] items-start gap-2 border-0 bg-transparent px-3 py-2 text-left text-sm hover:bg-surface-2"
                          >
                            <span className="num text-ink-2">
                              {t('scenarios.editor.validation.line', { line: item.line })}
                            </span>
                            <SeverityMark severity={severity} />
                            <span>
                              <span className="block">{rendered.title ?? rendered.detail}</span>
                              {rendered.title && rendered.title !== rendered.detail && (
                                <span lang="en" className="block text-xs text-ink-2">
                                  {rendered.detail}
                                </span>
                              )}
                              <span className="num block text-xs text-ink-2">{code}</span>
                            </span>
                          </button>
                        </li>
                      )
                    })}
                  </ul>
                )}
              </>
            )}
          </Panel>

          <Panel
            title={t('scenarios.editor.checks.title')}
            flush
            actions={
              <div className="flex items-center gap-2">
                <label className="flex items-center gap-2 text-xs text-ink-2">
                  {t('scenarios.editor.seed')}
                  <input
                    value={seed}
                    onChange={(e) => setSeed(e.target.value)}
                    inputMode="numeric"
                    aria-invalid={!seedValid || undefined}
                    className="num h-6 w-[96px] border border-line bg-bg px-2 text-sm text-ink"
                  />
                </label>
                <Button disabled={!canRun || checks.kind === 'running'} onClick={runChecks}>
                  {checks.kind === 'running'
                    ? t('scenarios.editor.checks.running')
                    : t('scenarios.editor.checks.run')}
                </Button>
              </div>
            }
          >
            {checks.kind === 'idle' && (
              <p className="m-0 px-3 py-3 text-sm text-ink-2">
                {t('scenarios.editor.checks.idle')}
              </p>
            )}
            {checks.kind === 'running' && (
              <LoadingState label={t('scenarios.editor.checks.running')} />
            )}
            {checks.kind === 'failed' && (
              <div className="p-3">
                <ErrorState
                  offline={checks.failure === 'network'}
                  title={t(`scenarios.editor.checks.error.${checks.failure}`)}
                  description={t('scenarios.editor.checks.errorBody')}
                  retryLabel={t('app.retry')}
                  onRetry={runChecks}
                />
              </div>
            )}
            {checks.kind === 'ready' && (
              <CheckResult
                res={checks.res}
                outdated={checks.yaml !== yaml}
                columns={checkColumns}
              />
            )}
          </Panel>

          <Panel
            title={t('scenarios.editor.preview.title')}
            flush
            actions={
              <Button disabled={!canRun || preview.kind === 'running'} onClick={runPreview}>
                {preview.kind === 'running'
                  ? t('scenarios.editor.preview.running')
                  : t('scenarios.editor.preview.run')}
              </Button>
            }
          >
            {preview.kind === 'idle' && (
              <p className="m-0 px-3 py-3 text-sm text-ink-2">
                {t('scenarios.editor.preview.idle')}
              </p>
            )}
            {preview.kind === 'running' && (
              <LoadingState label={t('scenarios.editor.preview.running')} />
            )}
            {preview.kind === 'failed' && (
              <div className="p-3">
                <ErrorState
                  offline={preview.failure === 'network'}
                  title={t(`scenarios.editor.preview.error.${preview.failure}`)}
                  description={t('scenarios.editor.preview.errorBody')}
                  retryLabel={t('app.retry')}
                  onRetry={runPreview}
                />
              </div>
            )}
            {preview.kind === 'ready' && (
              <div data-testid="preview-result">
                {preview.yaml !== yaml && (
                  <div className="p-3 pb-0">
                    <InlineAlert tone="warning">{t('scenarios.editor.outdated')}</InlineAlert>
                  </div>
                )}
                {!preview.res.ok ? (
                  <div className="p-3">
                    <EmptyState
                      title={t('scenarios.editor.preview.notRun')}
                      description={t('scenarios.editor.preview.notRunBody')}
                    />
                  </div>
                ) : (
                  <>
                    <div className="flex flex-col gap-2 p-3">
                      <PreviewMap spec={spec} preview={preview.res} />
                      <MapLegend />
                      <p className="num m-0 text-xs text-ink-2">
                        {t('scenarios.editor.preview.finished', {
                          time: preview.res.finished_s.toFixed(1),
                          score:
                            preview.res.oracle_score === null
                              ? '—'
                              : fmtPct(preview.res.oracle_score),
                        })}
                      </p>
                    </div>
                    <Table
                      caption={t('scenarios.editor.preview.contacts')}
                      columns={contactColumns}
                      rows={preview.res.contacts}
                      rowKey={(c) => c.id}
                      dense
                    />
                    <Table
                      caption={t('scenarios.editor.preview.coverage')}
                      columns={[
                        {
                          key: 't',
                          header: t('scenarios.editor.threats.id'),
                          mono: true,
                          render: (c) => c.threat_id,
                        },
                        {
                          key: 'f',
                          header: t('scenarios.editor.preview.firstCovered'),
                          mono: true,
                          align: 'right',
                          render: (c) =>
                            c.first_s === null
                              ? t('scenarios.editor.preview.never')
                              : `${c.first_s.toFixed(1)} s`,
                        },
                        {
                          key: 's',
                          header: t('scenarios.editor.preview.sensors'),
                          mono: true,
                          render: (c) => c.sensors.join(', ') || '—',
                        },
                      ]}
                      rows={preview.res.coverage}
                      rowKey={(c) => c.threat_id}
                      dense
                    />
                    <Note>{t('scenarios.editor.preview.note')}</Note>
                  </>
                )}
              </div>
            )}
          </Panel>
        </div>

        <div className="flex min-w-0 flex-col gap-4 xl:col-span-5">
          <TerrainPanel spec={spec} stale={stale} />
          <ThreatPanel spec={spec} stale={stale} />
          <SensorPanel spec={spec} stale={stale} />
          <WeatherPanel spec={spec} stale={stale} />
        </div>
      </div>

      <Dialog
        open={saveOpen}
        title={t('scenarios.editor.save.title')}
        onClose={() => setSaveOpen(false)}
        actions={
          <>
            <Button onClick={() => setSaveOpen(false)} disabled={saving}>
              {t('scenarios.cancel')}
            </Button>
            <Button variant="primary" onClick={() => void save()} disabled={saving}>
              {saving ? t('scenarios.editor.save.saving') : t('scenarios.editor.save.confirm')}
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-3">
          <dl className="m-0 border border-line">
            <Fact label={t('scenarios.editor.save.id')}>{spec?.id ?? '—'}</Fact>
            <Fact label={t('scenarios.editor.save.name')}>
              {spec ? localised(spec.title, lang) : '—'}
            </Fact>
          </dl>
          <p className="m-0 text-xs text-ink-2">{t('scenarios.editor.save.idNote')}</p>
          <Input
            label={t('scenarios.editor.save.tags')}
            hint={t('scenarios.editor.save.tagsHint')}
            value={tags}
            onChange={(e) => setTags(e.target.value)}
            autoComplete="off"
          />
          {saveError && <InlineAlert tone="error">{saveError}</InlineAlert>}
        </div>
      </Dialog>
    </>
  )
}

function CheckResult({
  res,
  outdated,
  columns,
}: {
  res: CheckResponse
  outdated: boolean
  columns: Column<CheckResponse['solvability']['checks'][number]>[]
}) {
  const { t } = useTranslation()
  const s = res.solvability
  const features = Object.keys(res.features)
  const nearestColumns: Column<CheckResponse['diversity']['nearest'][number]>[] = [
    {
      key: 'id',
      header: t('scenarios.editor.checks.nearest'),
      mono: true,
      render: (n) => n.scenario_id,
    },
    {
      key: 'd',
      header: t('scenarios.editor.checks.distance'),
      mono: true,
      align: 'right',
      render: (n) => fmt3(n.distance),
    },
  ]
  return (
    <div data-testid="check-result">
      {outdated && (
        <div className="p-3 pb-0">
          <InlineAlert tone="warning">{t('scenarios.editor.outdated')}</InlineAlert>
        </div>
      )}
      {!s.ran ? (
        <div className="p-3">
          <EmptyState
            title={t('scenarios.editor.checks.notRun')}
            description={t('scenarios.editor.checks.notRunBody')}
          />
        </div>
      ) : (
        <>
          <div className="flex flex-col gap-1 border-b border-line px-3 py-3">
            <p
              role="status"
              data-testid="solvability-wording"
              data-wording={s.wording}
              className="m-0 flex items-center gap-2 text-md font-semibold"
            >
              {s.solved ? (
                <CheckmarkFilled size={20} aria-hidden="true" className="text-track-neutral" />
              ) : (
                <ErrorFilled size={20} aria-hidden="true" className="text-track-hostile" />
              )}
              {s.solved ? t('scenarios.wording.verified') : t('scenarios.wording.notVerified')}
            </p>
            <p className="num m-0 text-xs text-ink-2">
              {t('scenarios.editor.checks.engineWording')} <span lang="en">{s.wording}</span> ·{' '}
              {t('scenarios.editor.checks.score', {
                score: s.oracle_score === null ? '—' : fmtPct(s.oracle_score),
              })}{' '}
              · {t('scenarios.editor.checks.seconds', { seconds: s.seconds.toFixed(2) })}
            </p>
          </div>
          <Table
            caption={t('scenarios.editor.checks.caption')}
            columns={columns}
            rows={s.checks}
            rowKey={(c) => c.name}
            dense
          />
          <dl className="m-0 border-t border-line" data-testid="diversity">
            <Fact label={t('scenarios.editor.checks.history')}>{res.diversity.history_size}</Fact>
            <Fact label={t('scenarios.editor.checks.novelty')}>
              {res.diversity.novelty === null ? '—' : fmt3(res.diversity.novelty)}
            </Fact>
            <Fact label={t('scenarios.editor.checks.threshold')}>
              {fmt3(res.diversity.threshold)}
            </Fact>
            <Fact label={t('scenarios.editor.checks.diversity')}>
              {res.diversity.passes === null
                ? t('scenarios.editor.checks.diversityNone')
                : res.diversity.passes
                  ? t('scenarios.editor.checks.diversityPass')
                  : t('scenarios.editor.checks.diversityFail')}
            </Fact>
          </dl>
          {res.diversity.nearest.length > 0 && (
            <Table
              caption={t('scenarios.editor.checks.nearestCaption')}
              columns={nearestColumns}
              rows={res.diversity.nearest}
              rowKey={(n) => n.scenario_id}
              dense
            />
          )}
          {features.length > 0 && <FeatureList features={res.features} />}
        </>
      )}
      <Note>{t('scenarios.check.note')}</Note>
    </div>
  )
}
