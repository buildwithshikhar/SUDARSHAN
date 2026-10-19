import { useEffect, useId, useRef, useState, type KeyboardEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { EmptyState, ErrorState, LoadingState } from '../../ui/States'
import { AcousticConsole } from '../consoles/AcousticConsole'
import { ConsoleFeed } from '../consoles/feed'
import { StaleNotice, useStreamState } from '../consoles/parts'
import { RfConsole } from '../consoles/RfConsole'
import { useLang } from '../format'
import { useLive, useLiveSession } from '../context'
import type { LiveState } from '../store'

type Tab = 'rf' | 'acoustic'
const TABS: readonly Tab[] = ['rf', 'acoustic']

/** Id of the first sensor of a modality in the briefing, or null when the scenario has none. */
const siteSensor = (s: LiveState, modality: Tab): string | null =>
  s.welcome?.briefing.sensors.find((x) => x.modality === modality)?.id ?? null

const outageOf = (s: LiveState, modality: Tab): boolean =>
  (s.frame?.sensors ?? []).some((x) => x.modality === modality && x.outage)

/** The data-status labels of a modality's sensors in the last frame, as one primitive string. */
const statusesOf = (s: LiveState, modality: Tab): string =>
  (s.frame?.sensors ?? [])
    .filter((x) => x.modality === modality)
    .map((x) => x.data_status)
    .sort()
    .join(',')

const splitStatuses = (value: string): ('reference' | 'verified')[] =>
  value === '' ? [] : value.split(',').map((x) => (x === 'verified' ? 'verified' : 'reference'))

/**
 * The RF spectrum and acoustic spectrogram consoles as tabs under the radar PPI. Both models keep
 * following the frames while one tab is hidden. A tab for a sensor the scenario lacks stays in
 * the list and says it is unavailable.
 */
export function SensorConsoles({ className = '' }: { className?: string }) {
  const { t } = useTranslation()
  const lang = useLang()
  const session = useLiveSession()
  const base = useId()
  const stream = useStreamState()
  const rfId = useLive((s) => siteSensor(s, 'rf'))
  const acId = useLive((s) => siteSensor(s, 'acoustic'))
  const rfOutage = useLive((s) => outageOf(s, 'rf'))
  const acOutage = useLive((s) => outageOf(s, 'acoustic'))
  const rfStatuses = useLive((s) => statusesOf(s, 'rf'))
  const acStatuses = useLive((s) => statusesOf(s, 'acoustic'))
  const [picked, setPicked] = useState<Tab | null>(null)
  const buttons = useRef<Record<string, HTMLButtonElement | null>>({})

  const [feed] = useState(() => new ConsoleFeed(session.store))
  useEffect(() => {
    feed.attach()
    return () => feed.detach()
  }, [feed])

  const available: Record<Tab, boolean> = { rf: rfId !== null, acoustic: acId !== null }
  const selected: Tab = picked ?? (available.rf || !available.acoustic ? 'rf' : 'acoustic')

  const move = (event: KeyboardEvent, index: number) => {
    const last = TABS.length - 1
    const target =
      event.key === 'ArrowRight'
        ? (index + 1) % TABS.length
        : event.key === 'ArrowLeft'
          ? (index - 1 + TABS.length) % TABS.length
          : event.key === 'Home'
            ? 0
            : event.key === 'End'
              ? last
              : -1
    const next = TABS[target]
    if (!next) return
    event.preventDefault()
    setPicked(next)
    buttons.current[next]?.focus()
  }

  const title = (tab: Tab) => t(tab === 'rf' ? 'live.consoles.tabRf' : 'live.consoles.tabAcoustic')

  const panel = (tab: Tab) => {
    if (!stream.hasFrame) {
      return stream.closed ? (
        <div className="p-2">
          <ErrorState
            offline
            title={t('live.consoles.failed.title')}
            description={t('live.consoles.failed.body')}
            retryLabel={t('live.consoles.failed.retry')}
            onRetry={() => window.location.reload()}
          />
        </div>
      ) : (
        <LoadingState label={t('live.consoles.loading')} />
      )
    }
    if (!available[tab]) {
      return (
        <div className="p-2" data-testid={`console-empty-${tab}`}>
          <EmptyState
            title={t(tab === 'rf' ? 'live.consoles.rf.emptyTitle' : 'live.consoles.ac.emptyTitle')}
            description={t(
              tab === 'rf' ? 'live.consoles.rf.emptyBody' : 'live.consoles.ac.emptyBody',
            )}
          />
        </div>
      )
    }
    return (
      <div className="flex h-full min-h-0 flex-col" data-stale={stream.stale}>
        {stream.stale && <StaleNotice lastTimeS={stream.lastTimeS} />}
        <div className="min-h-0 flex-1">
          {tab === 'rf' ? (
            <RfConsole
              feed={feed}
              stream={stream}
              sensorId={rfId ?? ''}
              outage={rfOutage}
              lang={lang}
              sensorStatuses={splitStatuses(rfStatuses)}
            />
          ) : (
            <AcousticConsole
              feed={feed}
              stream={stream}
              sensorId={acId ?? ''}
              outage={acOutage}
              lang={lang}
              sensorStatuses={splitStatuses(acStatuses)}
            />
          )}
        </div>
      </div>
    )
  }

  return (
    <section
      aria-label={t('live.consoles.title')}
      className={`border border-line bg-surface-1 ${className}`}
    >
      <header className="flex h-8 shrink-0 items-end justify-between border-b border-line px-3">
        <div role="tablist" aria-label={t('live.consoles.tabsLabel')} className="flex">
          {TABS.map((tab, index) => {
            const active = tab === selected
            return (
              <button
                key={tab}
                ref={(node) => {
                  buttons.current[tab] = node
                }}
                role="tab"
                type="button"
                id={`${base}-tab-${tab}`}
                aria-selected={active}
                aria-controls={`${base}-panel-${tab}`}
                tabIndex={active ? 0 : -1}
                onClick={() => setPicked(tab)}
                onKeyDown={(event) => move(event, index)}
                data-unavailable={available[tab] ? undefined : 'true'}
                className={`-mb-px h-8 border-b-2 pr-3 text-sm ${index === 0 ? 'pl-0' : 'pl-3'} ${active ? 'border-accent text-ink' : 'border-transparent text-ink-2 hover:text-ink'}`}
              >
                {title(tab)}
                {!available[tab] && (
                  <span className="text-xs text-ink-2"> · {t('live.consoles.unavailable')}</span>
                )}
              </button>
            )
          })}
        </div>
        <span className="num pb-1.5 text-xs text-ink-2">{t('live.consoles.scale')}</span>
      </header>
      {TABS.map((tab) => (
        <div
          key={tab}
          role="tabpanel"
          id={`${base}-panel-${tab}`}
          aria-labelledby={`${base}-tab-${tab}`}
          hidden={tab !== selected}
          className="min-h-0 flex-1"
        >
          {tab === selected ? panel(tab) : null}
        </div>
      ))}
    </section>
  )
}
