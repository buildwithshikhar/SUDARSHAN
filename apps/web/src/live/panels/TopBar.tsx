import { CheckmarkFilled, CloudOffline, Exit, Help, Renew, Stop } from '@carbon/icons-react'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import brand from '../../../../../brand.json'
import { BrandMark } from '../../ui/BrandMark'
import { useLive } from '../context'
import { fmtElapsed, fmtHours, fmtUtc } from '../format'

/** 32 px bar: session clock, weather and light, rule pack and link state. */
export function TopBar({ onHelp, onEnd }: { onHelp: () => void; onEnd: () => void }) {
  const { t } = useTranslation()
  const welcome = useLive((s) => s.welcome)
  const connection = useLive((s) => s.connection)
  const latency = useLive((s) => s.latencyMs)
  const status = useLive((s) => s.status)
  const frame = useLive((s) => s.frame)
  const [now, setNow] = useState(() => new Date())
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000)
    return () => clearInterval(id)
  }, [])

  const weather = welcome?.briefing.weather
  const linkIcon =
    connection.state === 'open' ? (
      <CheckmarkFilled size={16} aria-hidden="true" className="text-track-neutral" />
    ) : connection.state === 'closed' ? (
      <CloudOffline size={16} aria-hidden="true" className="text-track-hostile" />
    ) : (
      <Renew size={16} aria-hidden="true" className="text-signal" />
    )

  return (
    <header className="flex h-8 shrink-0 items-center gap-4 border-b border-line bg-surface-1 px-3 text-xs">
      <Link to="/train/lobby" className="flex items-center gap-2 text-ink no-underline">
        <BrandMark size={20} />
        <span className="text-sm font-semibold tracking-[0.14em]">{brand.productName}</span>
      </Link>
      <span className="h-4 w-px bg-line" aria-hidden="true" />
      <dl className="num m-0 flex items-center gap-4 whitespace-nowrap">
        <div className="flex gap-1">
          <dt className="text-ink-2">{t('live.top.utc')}</dt>
          <dd className="m-0">{fmtUtc(now)}Z</dd>
        </div>
        <div className="flex gap-1">
          <dt className="text-ink-2">{t('live.top.scenario')}</dt>
          <dd className="m-0">{frame ? fmtElapsed(frame.time_s) : '--:--.-'}</dd>
        </div>
        {frame && (
          <div className="hidden gap-1 xl:flex">
            <dt className="text-ink-2">{t('live.top.light')}</dt>
            <dd className="m-0">{fmtHours(frame.time_of_day_h)}</dd>
          </div>
        )}
        {weather && (
          <div className="hidden gap-1 2xl:flex">
            <dt className="text-ink-2">{t('live.top.weather')}</dt>
            <dd className="m-0">
              {t(`live.weather.${weather.condition}`)} · {t('live.top.vis')}{' '}
              {(weather.visibility_m / 1000).toFixed(1)} km · {Math.round(weather.wind_from_deg)}°/
              {weather.wind_speed_mps.toFixed(1)} {t('live.units.mps')}
            </dd>
          </div>
        )}
        {welcome && (
          <div className="flex gap-1">
            <dt className="text-ink-2">{t('live.top.rules')}</dt>
            <dd className="m-0">
              {welcome.rules.id} {welcome.rules.version}
            </dd>
          </div>
        )}
      </dl>
      <div className="ml-auto flex items-center gap-4 whitespace-nowrap">
        <span className="flex items-center gap-1" role="status" aria-live="polite">
          {linkIcon}
          <span>
            {t(`live.conn.${connection.state}`)}
            {connection.state === 'reconnecting' && connection.attempt > 0
              ? ` ${connection.attempt}`
              : ''}
          </span>
          <span className="num text-ink-2">
            {latency !== null && connection.state === 'open' ? `${latency} ms` : '— ms'}
          </span>
        </span>
        <span className="num hidden text-ink-2 2xl:inline">{t(`live.status.${status}`)}</span>
        <button
          type="button"
          onClick={onHelp}
          aria-label={t('live.top.helpLabel')}
          title={t('live.top.helpLabel')}
          className="inline-flex h-6 items-center gap-1 border border-line px-2 text-ink-2 hover:border-accent hover:text-ink"
        >
          <Help size={16} aria-hidden="true" />
        </button>
        {status === 'running' && (
          <button
            type="button"
            onClick={onEnd}
            className="inline-flex h-6 items-center gap-1 border border-line px-2 text-ink-2 hover:border-accent hover:text-ink"
          >
            <Stop size={16} aria-hidden="true" />
            <span className="sr-only 2xl:not-sr-only">{t('live.top.end')}</span>
          </button>
        )}
        <Link
          to="/train/lobby"
          className="inline-flex h-6 items-center gap-1 border border-line px-2 text-ink-2 no-underline hover:border-accent hover:text-ink"
        >
          <Exit size={16} aria-hidden="true" />
          <span className="sr-only 2xl:not-sr-only">{t('live.top.leave')}</span>
        </Link>
      </div>
    </header>
  )
}
