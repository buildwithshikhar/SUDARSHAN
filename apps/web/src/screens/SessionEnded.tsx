import { CheckmarkFilled, ErrorFilled } from '@carbon/icons-react'
import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { PageHeader } from '../layout/PageHeader'
import { fmtElapsed } from '../live/format'
import type { EndSummary } from '../live/protocol'
import { getSession, getSessionLog, type SessionLog, type SessionRow } from '../live/restApi'
import { Panel } from '../ui/Panel'
import { ErrorState, LoadingState } from '../ui/States'

type Load =
  | { state: 'loading' }
  | { state: 'error' }
  | { state: 'ready'; log: SessionLog; row: SessionRow | null }

const short = (hash: string) => (hash.length > 20 ? `${hash.slice(0, 12)}…${hash.slice(-8)}` : hash)

/** After the session: what happened in numbers, and whether the stored event log verifies. No scoring. */
export function SessionEnded({ id, summary }: { id: string; summary: EndSummary | null }) {
  const { t } = useTranslation()
  const [load, setLoad] = useState<Load>({ state: 'loading' })
  const [attempt, setAttempt] = useState(0)
  const retry = useCallback(() => {
    setLoad({ state: 'loading' })
    setAttempt((n) => n + 1)
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    Promise.all([
      getSessionLog(id, controller.signal),
      summary ? Promise.resolve(null) : getSession(id, controller.signal),
    ])
      .then(([log, row]) => setLoad({ state: 'ready', log, row }))
      .catch(() => {
        if (!controller.signal.aborted) setLoad({ state: 'error' })
      })
    return () => controller.abort()
  }, [id, summary, attempt])

  return (
    <>
      <PageHeader
        title={t('live.ended.title')}
        crumbs={[t('nav.group.train'), t('nav.module.drills'), t('live.ended.title')]}
        actions={
          <Link
            to="/train/lobby"
            className="inline-flex h-7 items-center border border-line px-3 text-sm no-underline hover:border-accent"
          >
            {t('live.ended.back')}
          </Link>
        }
      />
      <div className="grid max-w-[880px] grid-cols-1 gap-4">
        <Panel title={t('live.ended.record')} flush>
          {load.state === 'loading' && <LoadingState label={t('live.ended.loading')} />}
          {load.state === 'error' && (
            <ErrorState
              offline
              title={t('live.ended.error')}
              description={t('live.ended.errorBody')}
              retryLabel={t('app.retry')}
              onRetry={retry}
            />
          )}
          {load.state === 'ready' && (
            <dl className="m-0">
              {[
                [t('live.ended.ticks'), String(summary?.ticks ?? load.row?.ticks ?? '—')],
                [
                  t('live.ended.duration'),
                  summary
                    ? fmtElapsed(summary.duration_s)
                    : load.row?.started_at && load.row.ended_at
                      ? fmtElapsed(
                          (Date.parse(load.row.ended_at) - Date.parse(load.row.started_at)) / 1000,
                        )
                      : '—',
                ],
                [t('live.ended.events'), String(summary?.event_count ?? load.log.event_count)],
                [t('live.ended.head'), short(load.log.head)],
                [t('live.ended.stateHash'), short(load.log.final_state_hash)],
              ].map(([label, value]) => (
                <div
                  key={label}
                  className="grid min-h-7 grid-cols-[176px_1fr] items-center border-b border-line px-3"
                >
                  <dt className="text-sm text-ink-2">{label}</dt>
                  <dd className="num m-0 text-sm">{value}</dd>
                </div>
              ))}
              <div className="grid min-h-8 grid-cols-[176px_1fr] items-center px-3">
                <dt className="text-sm text-ink-2">{t('live.ended.verification')}</dt>
                <dd
                  className="m-0 flex items-center gap-2 text-sm"
                  role="status"
                  data-testid="log-verification"
                >
                  {load.log.verified ? (
                    <>
                      <CheckmarkFilled
                        size={16}
                        aria-hidden="true"
                        className="text-track-neutral"
                      />
                      {t('live.ended.verified')}
                    </>
                  ) : (
                    <>
                      <ErrorFilled size={16} aria-hidden="true" className="text-track-hostile" />
                      {t('live.ended.failed', { seq: load.log.first_bad_seq ?? '—' })}
                    </>
                  )}
                </dd>
              </div>
            </dl>
          )}
        </Panel>
        <p className="m-0 text-sm text-ink-2">{t('live.ended.note')}</p>
      </div>
    </>
  )
}
