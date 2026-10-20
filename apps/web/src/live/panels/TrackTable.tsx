import { useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { Table, type Column } from '../../ui/Table'
import { EmptyState } from '../../ui/States'
import { useLive, useLiveSession } from '../context'
import { fmtBearing, fmtPercent, fmtRange, fmtSpeed, sensorCode, sitePosition } from '../format'
import { polarFrom } from '../geometry'
import type { AssistView, TrackView } from '../protocol'

interface Row {
  track: TrackView
  assist: AssistView | undefined
  identity: string | undefined
  bearing: number
  range: number
}

const classText = (t: (k: string, o?: Record<string, unknown>) => string, id: string | null) =>
  id === null ? '—' : t(`live.class.${id}`, { defaultValue: id })

/** The track table: 28 px rows, monospace figures, reference data marked on every row. */
export function TrackTable() {
  const { t } = useTranslation()
  const session = useLiveSession()
  const frame = useLive((s) => s.frame)
  const welcome = useLive((s) => s.welcome)
  const selected = useLive((s) => s.selected)
  const mergeFrom = useLive((s) => s.mergeFrom)
  const assessments = useLive((s) => s.assessments)

  const rows: Row[] = useMemo(() => {
    if (!frame || !welcome) return []
    const site = sitePosition(welcome.briefing)
    return [...frame.tracks]
      .sort((a, b) => a.id.localeCompare(b.id))
      .map((track) => {
        const polar = polarFrom(site, track.position)
        return {
          track,
          assist: frame.assist.find((a) => a.track === track.id),
          identity: assessments[track.id],
          bearing: polar.bearingDeg,
          range: polar.rangeM,
        }
      })
  }, [frame, welcome, assessments])

  const select = (id: string) => session.store.dispatch({ type: 'select', id })

  const columns: Column<Row>[] = [
    {
      key: 'track',
      header: t('live.table.track'),
      render: (row) => (
        <span className="flex items-center gap-2">
          <button
            type="button"
            aria-pressed={selected === row.track.id}
            onClick={(event) => {
              event.stopPropagation()
              select(row.track.id)
            }}
            className="num h-6 border-0 bg-transparent p-0 text-left text-sm text-ink underline decoration-dotted underline-offset-4"
          >
            {row.track.label}
          </button>
          {mergeFrom === row.track.id && (
            <span className="border border-accent px-1 text-2xs text-accent">
              {t('live.table.mergeMark')}
            </span>
          )}
        </span>
      ),
    },
    {
      key: 'status',
      header: t('live.table.status'),
      render: (row) => t(`live.track.status.${row.track.status}`),
    },
    {
      key: 'class',
      header: t('live.table.class'),
      render: (row) => (
        <span>
          {classText(t, row.track.class_estimate)}{' '}
          <span className="num text-ink-2">
            {row.track.class_estimate ? fmtPercent(row.track.class_support) : ''}
          </span>
        </span>
      ),
    },
    {
      key: 'assist',
      header: t('live.table.assist'),
      render: (row) =>
        row.assist ? (
          <span title={`${row.assist.source}: ${row.assist.basis}`}>
            {t(`live.assist.flag.${row.assist.flag}`)}{' '}
            <span className="num text-ink-2">{fmtPercent(row.assist.confidence)}</span>
          </span>
        ) : (
          <span className="text-ink-2">—</span>
        ),
    },
    {
      key: 'brg',
      header: t('live.table.brgRng'),
      mono: true,
      render: (row) => `${fmtBearing(row.bearing)} ${fmtRange(row.range)}`,
    },
    {
      key: 'spd',
      header: t('live.table.speed'),
      mono: true,
      align: 'right',
      render: (row) => fmtSpeed(row.track.speed_mps),
    },
    {
      key: 'hdg',
      header: t('live.table.heading'),
      mono: true,
      className: 'hidden 2xl:table-cell',
      render: (row) => fmtBearing(row.track.heading_deg),
    },
    {
      key: 'sensors',
      header: t('live.table.sensors'),
      mono: true,
      className: 'hidden 2xl:table-cell',
      render: (row) => row.track.sensors.map(sensorCode).join(' '),
    },
  ]

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div
        className="min-h-0 flex-1 overflow-auto"
        tabIndex={0}
        role="group"
        aria-label={t('live.table.title')}
      >
        <Table
          caption={t('live.table.caption')}
          columns={columns}
          rows={rows}
          rowKey={(row) => row.track.id}
          dense
          selectedKey={selected}
          onRowClick={(row) => select(row.track.id)}
          empty={
            <div className="p-3">
              <EmptyState title={t('live.table.empty')} description={t('live.table.emptyBody')} />
            </div>
          }
        />
      </div>
      <p className="m-0 flex shrink-0 items-center justify-between gap-2 border-t border-line px-2 py-1 text-2xs text-ink-2">
        <span />
        <span className="num">{t('live.table.count', { count: rows.length })}</span>
      </p>
    </div>
  )
}
