import { useCallback, useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useLocation, useNavigate } from 'react-router-dom'
import { PageHeader } from '../layout/PageHeader'
import { ApiError, NetworkError } from '../lib/api'
import { fmtElapsed, useLang } from '../live/format'
import { createSession, localised } from '../live/restApi'
import { Badge } from '../ui/Badge'
import { Button } from '../ui/Button'
import { Dialog } from '../ui/Dialog'
import { Input, Select } from '../ui/Field'
import { InlineAlert } from '../ui/InlineAlert'
import { Panel } from '../ui/Panel'
import { EmptyState, ErrorState, LoadingState } from '../ui/States'
import { Table, type Column } from '../ui/Table'
import {
  failureOf,
  isAbort,
  SolvabilityBadge,
  useScenarioApi,
  type Failure,
} from '../scenarios/shared'
import {
  ORIGINS,
  TERRAINS,
  TIMES_OF_DAY,
  type Origin,
  type ScenarioSummary,
  type TerrainId,
  type TimeOfDay,
} from '../scenarios/types'

type Load =
  | { state: 'loading' }
  | { state: 'error'; failure: Failure }
  | { state: 'ready'; rows: ScenarioSummary[] }

type SortKey = 'order' | 'title' | 'difficultyUp' | 'difficultyDown' | 'hostile' | 'duration'

const SORTS: SortKey[] = ['order', 'title', 'difficultyUp', 'difficultyDown', 'hostile', 'duration']

const originRank: Record<Origin, number> = { scripted: 0, example: 1, generated: 2, authored: 3 }

function sorter(key: SortKey, lang: 'en' | 'hi') {
  const byTitle = (a: ScenarioSummary, b: ScenarioSummary) =>
    localised(a.title, lang).localeCompare(localised(b.title, lang), lang)
  switch (key) {
    case 'title':
      return byTitle
    case 'difficultyUp':
      return (a: ScenarioSummary, b: ScenarioSummary) =>
        (a.difficulty ?? 99) - (b.difficulty ?? 99) || byTitle(a, b)
    case 'difficultyDown':
      return (a: ScenarioSummary, b: ScenarioSummary) =>
        (b.difficulty ?? -1) - (a.difficulty ?? -1) || byTitle(a, b)
    case 'hostile':
      return (a: ScenarioSummary, b: ScenarioSummary) =>
        b.hostile_count - a.hostile_count || byTitle(a, b)
    case 'duration':
      return (a: ScenarioSummary, b: ScenarioSummary) =>
        b.duration_s - a.duration_s || byTitle(a, b)
    default:
      // The curriculum first in its own order, then by where the scenario came from.
      return (a: ScenarioSummary, b: ScenarioSummary) =>
        (a.curriculum_order ?? 999) - (b.curriculum_order ?? 999) ||
        originRank[a.origin] - originRank[b.origin] ||
        a.id.localeCompare(b.id)
  }
}

/** Route /content/scenarios: every scenario the instance holds, with filters and row actions. */
export function ScenarioLibrary() {
  const { t } = useTranslation()
  const lang = useLang()
  const api = useScenarioApi()
  const navigate = useNavigate()
  const { search } = useLocation()
  const [load, setLoad] = useState<Load>({ state: 'loading' })
  const [attempt, setAttempt] = useState(0)

  const [query, setQuery] = useState('')
  const [origin, setOrigin] = useState('')
  const [terrain, setTerrain] = useState('')
  const [time, setTime] = useState('')
  const [tag, setTag] = useState('')
  const [sort, setSort] = useState<SortKey>('order')

  const [starting, setStarting] = useState<string | null>(null)
  const [startError, setStartError] = useState<string | null>(null)
  const [doomed, setDoomed] = useState<ScenarioSummary | null>(null)
  const [deleting, setDeleting] = useState(false)
  const [deleteError, setDeleteError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  const retry = useCallback(() => {
    setLoad({ state: 'loading' })
    setAttempt((n) => n + 1)
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    api
      .list(controller.signal)
      .then((rows) => {
        if (!controller.signal.aborted) setLoad({ state: 'ready', rows })
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted || isAbort(error)) return
        setLoad({ state: 'error', failure: failureOf(error) })
      })
    return () => controller.abort()
  }, [api, attempt])

  const rows = useMemo(() => (load.state === 'ready' ? load.rows : []), [load])
  const tags = useMemo(() => [...new Set(rows.flatMap((r) => r.tags))].sort(), [rows])

  const shown = useMemo(() => {
    const needle = query.trim().toLowerCase()
    return rows
      .filter(
        (r) =>
          (origin === '' || r.origin === origin) &&
          (terrain === '' || r.terrain === terrain) &&
          (time === '' || r.time_of_day === time) &&
          (tag === '' || r.tags.includes(tag)) &&
          (needle === '' ||
            r.id.toLowerCase().includes(needle) ||
            r.title.en.toLowerCase().includes(needle) ||
            r.title.hi.toLowerCase().includes(needle) ||
            r.tags.some((x) => x.toLowerCase().includes(needle))),
      )
      .sort(sorter(sort, lang))
  }, [rows, query, origin, terrain, time, tag, sort, lang])

  const filtered = query !== '' || origin !== '' || terrain !== '' || time !== '' || tag !== ''
  const clear = () => {
    setQuery('')
    setOrigin('')
    setTerrain('')
    setTime('')
    setTag('')
  }

  const editorPath = (id: string) => `/content/scenarios/editor/${encodeURIComponent(id)}${search}`

  const start = async (row: ScenarioSummary) => {
    setStarting(row.id)
    setStartError(null)
    setNotice(null)
    try {
      const session = await createSession(row.id)
      navigate(`/train/session/${session.id}${search}`)
    } catch (error) {
      setStarting(null)
      setStartError(
        error instanceof ApiError
          ? error.status === 403
            ? t('live.lobby.createForbidden')
            : t('live.lobby.createFailed', { detail: error.message })
          : t('live.lobby.createUnreachable'),
      )
    }
  }

  const confirmDelete = async () => {
    if (!doomed) return
    setDeleting(true)
    setDeleteError(null)
    try {
      await api.remove(doomed.id)
      const id = doomed.id
      setDoomed(null)
      setNotice(t('scenarios.library.deleted', { id }))
      setLoad((current) =>
        current.state === 'ready'
          ? { state: 'ready', rows: current.rows.filter((r) => r.id !== id) }
          : current,
      )
    } catch (error) {
      setDeleteError(
        error instanceof NetworkError
          ? t('scenarios.library.deleteUnreachable')
          : error instanceof ApiError && error.status === 403
            ? t('scenarios.library.deleteForbidden')
            : t('scenarios.library.deleteFailed', {
                detail: error instanceof Error ? error.message : '',
              }),
      )
    } finally {
      setDeleting(false)
    }
  }

  const columns: Column<ScenarioSummary>[] = [
    {
      key: 'title',
      header: t('scenarios.library.col.title'),
      className: 'min-w-[240px] py-1',
      render: (r) => (
        <div>
          <span className="block text-sm">{localised(r.title, lang)}</span>
          <span className="num block text-xs text-ink-2">{r.id}</span>
          {r.tags.length > 0 && (
            <span className="block text-xs text-ink-2">{r.tags.join(' · ')}</span>
          )}
        </div>
      ),
    },
    {
      key: 'origin',
      header: t('scenarios.library.col.origin'),
      render: (r) => <Badge>{t(`scenarios.origin.${r.origin}`)}</Badge>,
    },
    {
      key: 'terrain',
      header: t('scenarios.library.col.terrain'),
      render: (r) => t(`scenarios.terrain.${r.terrain}`),
    },
    {
      key: 'time',
      header: t('scenarios.library.col.time'),
      render: (r) => t(`scenarios.time.${r.time_of_day}`),
    },
    {
      key: 'weather',
      header: t('scenarios.library.col.weather'),
      render: (r) => t(`live.weather.${r.weather}`, { defaultValue: r.weather }),
    },
    {
      key: 'contacts',
      header: t('scenarios.library.col.contacts'),
      mono: true,
      align: 'right',
      render: (r) => `${r.hostile_count} / ${r.contact_count}`,
    },
    {
      key: 'sensors',
      header: t('scenarios.library.col.sensors'),
      mono: true,
      align: 'right',
      render: (r) => (
        <>
          {r.sensor_count}
          {r.degraded && (
            <span className="block text-xs text-ink-2">{t('scenarios.library.degraded')}</span>
          )}
        </>
      ),
    },
    {
      key: 'difficulty',
      header: t('scenarios.library.col.difficulty'),
      mono: true,
      align: 'right',
      render: (r) => (r.difficulty === null ? '—' : r.difficulty),
    },
    {
      key: 'solvability',
      header: t('scenarios.library.col.solvability'),
      render: (r) => (
        <div className="py-1">
          <SolvabilityBadge status={r.solvability.status} />
          {r.solvability.oracle_score !== null && (
            <span className="num mt-1 block text-xs text-ink-2">
              {t('scenarios.library.oracleScore', {
                score: (r.solvability.oracle_score * 100).toFixed(0),
              })}
            </span>
          )}
        </div>
      ),
    },
    {
      key: 'actions',
      header: t('scenarios.library.col.actions'),
      className: 'min-w-[132px] py-1',
      render: (r) => (
        <div className="flex flex-col items-start gap-1">
          <Button
            variant="ghost"
            className="h-6 px-1"
            aria-label={`${t('scenarios.library.open')}: ${localised(r.title, lang)}`}
            onClick={() => navigate(editorPath(r.id))}
          >
            {t('scenarios.library.open')}
          </Button>
          <Button
            variant="ghost"
            className="h-6 px-1"
            disabled={!r.playable || starting !== null}
            aria-label={`${t('scenarios.library.start')}: ${localised(r.title, lang)}`}
            onClick={() => void start(r)}
          >
            {starting === r.id ? t('scenarios.library.starting') : t('scenarios.library.start')}
          </Button>
          {r.can_delete && (
            <Button
              variant="ghost"
              className="h-6 px-1"
              aria-label={`${t('scenarios.library.delete')}: ${localised(r.title, lang)}`}
              onClick={() => {
                setDeleteError(null)
                setDoomed(r)
              }}
            >
              {t('scenarios.library.delete')}
            </Button>
          )}
        </div>
      ),
    },
  ]

  return (
    <>
      <PageHeader
        title={t('scenarios.library.title')}
        crumbs={[t('nav.group.content'), t('nav.module.scenarios'), t('scenarios.library.title')]}
        actions={
          <div className="flex items-center gap-2">
            <Badge>{t('scenarios.reference')}</Badge>
            <Button
              variant="primary"
              onClick={() => navigate(`/content/scenarios/editor${search}`)}
            >
              {t('scenarios.library.newInEditor')}
            </Button>
          </div>
        }
      />
      {load.state === 'loading' && <LoadingState label={t('scenarios.library.loading')} />}
      {load.state === 'error' && (
        <div className="max-w-[640px]">
          <ErrorState
            offline={load.failure === 'network'}
            title={t(`scenarios.library.error.${load.failure}`)}
            description={t('scenarios.library.errorBody')}
            retryLabel={t('app.retry')}
            onRetry={retry}
          />
        </div>
      )}
      {load.state === 'ready' && rows.length === 0 && (
        <div className="max-w-[640px]">
          <EmptyState
            title={t('scenarios.library.empty')}
            description={t('scenarios.library.emptyBody')}
            action={
              <Button onClick={() => navigate(`/content/generator${search}`)}>
                {t('nav.module.generator')}
              </Button>
            }
          />
        </div>
      )}
      {load.state === 'ready' && rows.length > 0 && (
        <div className="flex flex-col gap-3">
          {notice && <InlineAlert tone="success">{notice}</InlineAlert>}
          {startError && <InlineAlert tone="error">{startError}</InlineAlert>}
          <Panel title={t('scenarios.library.filters')}>
            <div className="grid grid-cols-2 items-end gap-3 lg:grid-cols-3 xl:grid-cols-6">
              <Input
                type="search"
                label={t('scenarios.library.search')}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                autoComplete="off"
              />
              <Select
                label={t('scenarios.library.col.origin')}
                value={origin}
                onChange={(e) => setOrigin(e.target.value)}
                options={[
                  { value: '', label: t('scenarios.library.all') },
                  ...ORIGINS.map((o) => ({ value: o, label: t(`scenarios.origin.${o}`) })),
                ]}
              />
              <Select
                label={t('scenarios.library.col.terrain')}
                value={terrain}
                onChange={(e) => setTerrain(e.target.value)}
                options={[
                  { value: '', label: t('scenarios.library.all') },
                  ...TERRAINS.map((o: TerrainId) => ({
                    value: o,
                    label: t(`scenarios.terrain.${o}`),
                  })),
                ]}
              />
              <Select
                label={t('scenarios.library.col.time')}
                value={time}
                onChange={(e) => setTime(e.target.value)}
                options={[
                  { value: '', label: t('scenarios.library.all') },
                  ...TIMES_OF_DAY.map((o: TimeOfDay) => ({
                    value: o,
                    label: t(`scenarios.time.${o}`),
                  })),
                ]}
              />
              <Select
                label={t('scenarios.library.tag')}
                value={tag}
                onChange={(e) => setTag(e.target.value)}
                options={[
                  { value: '', label: t('scenarios.library.all') },
                  ...tags.map((x) => ({ value: x, label: x })),
                ]}
              />
              <Select
                label={t('scenarios.library.sort')}
                value={sort}
                onChange={(e) => setSort(e.target.value as SortKey)}
                options={SORTS.map((s) => ({ value: s, label: t(`scenarios.library.sorts.${s}`) }))}
              />
            </div>
            <div className="mt-3 flex items-center gap-3">
              <p role="status" className="num m-0 text-xs text-ink-2" data-testid="library-count">
                {t('scenarios.library.count', { shown: shown.length, total: rows.length })}
              </p>
              {filtered && (
                <Button variant="ghost" onClick={clear}>
                  {t('scenarios.library.clear')}
                </Button>
              )}
            </div>
          </Panel>
          <Panel title={t('scenarios.library.title')} flush>
            {shown.length === 0 ? (
              <div className="p-3">
                <EmptyState
                  title={t('scenarios.library.noMatch')}
                  description={t('scenarios.library.noMatchBody')}
                  action={<Button onClick={clear}>{t('scenarios.library.clear')}</Button>}
                />
              </div>
            ) : (
              <div
                tabIndex={0}
                role="region"
                aria-label={t('scenarios.library.tableRegion')}
                className="overflow-x-auto"
              >
                <Table
                  caption={t('scenarios.library.caption')}
                  columns={columns}
                  rows={shown}
                  rowKey={(r) => r.id}
                  dense
                />
              </div>
            )}
            <p className="m-0 border-t border-line px-3 py-2 text-xs text-ink-2">
              {t('scenarios.library.note')}
            </p>
          </Panel>
        </div>
      )}
      <Dialog
        open={doomed !== null}
        title={t('scenarios.library.deleteTitle')}
        onClose={() => setDoomed(null)}
        actions={
          <>
            <Button onClick={() => setDoomed(null)} disabled={deleting}>
              {t('scenarios.cancel')}
            </Button>
            <Button variant="primary" onClick={() => void confirmDelete()} disabled={deleting}>
              {deleting ? t('scenarios.library.deleting') : t('scenarios.library.confirmDelete')}
            </Button>
          </>
        }
      >
        {doomed && (
          <div className="flex flex-col gap-3">
            <p className="m-0">
              {t('scenarios.library.deleteBody', { title: localised(doomed.title, lang) })}
            </p>
            <p className="num m-0 text-xs text-ink-2">
              {doomed.id} · {fmtElapsed(doomed.duration_s)}
            </p>
            {deleteError && <InlineAlert tone="error">{deleteError}</InlineAlert>}
          </div>
        )}
      </Dialog>
    </>
  )
}
