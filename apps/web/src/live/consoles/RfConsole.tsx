import { useCallback, useEffect, useMemo, useSyncExternalStore } from 'react'
import { useTranslation } from 'react-i18next'
import { fmtBearing } from '../format'
import { RECENT_S, type ConsoleFeed } from './feed'
import { drawRf, RowImage } from './draw'
import { ConsoleBody, ScaleBar, SynthLabel, type StreamState } from './parts'
import { useInstrument } from './useInstrument'

const MONO = '"IBM Plex Mono", ui-monospace, Menlo, Consolas, monospace'

export function RfConsole({
  feed,
  stream,
  sensorId,
  outage,
  lang,
  sensorStatuses,
}: {
  feed: ConsoleFeed
  stream: StreamState
  sensorId: string
  outage: boolean
  lang: string
  sensorStatuses: readonly ('reference' | 'verified')[]
}) {
  const { t } = useTranslation()
  useSyncExternalStore(feed.subscribe, feed.getVersion)
  const recent = feed.rfRecent
  const image = useMemo(() => new RowImage(feed.rf.ring), [feed])
  const staleMark = t('live.consoles.stale.mark')
  const stale = stream.stale

  const paint = useCallback(
    (ctx: CanvasRenderingContext2D, width: number, height: number) => {
      image.sync()
      drawRf(ctx, {
        width,
        height,
        mono: MONO,
        spectrum: feed.rf.spectrum,
        peak: feed.rf.peak,
        image,
        stale: stale ? { text: staleMark } : null,
      })
    },
    [feed, image, stale, staleMark],
  )
  const { wrapRef, canvasRef, invalidate } = useInstrument({
    paint,
    modelVersion: () => feed.rf.ring.version,
  })
  useEffect(invalidate, [invalidate, stale, staleMark, lang])

  const state = outage ? 'outage' : recent.length > 0 ? 'heard' : 'listening'
  const statuses = [...sensorStatuses, ...recent.map((e) => e.dataStatus)]

  return (
    <ConsoleBody
      sideLabel={t('live.consoles.tabRf')}
      plot={
        <div ref={wrapRef} className="relative min-h-0 bg-bg" data-rows={feed.rf.ring.count}>
          <canvas
            ref={canvasRef}
            role="img"
            aria-label={t('live.consoles.rf.aria')}
            className="absolute inset-0 h-full w-full"
          />
        </div>
      }
      side={
        <>
          <p
            role="status"
            data-testid="console-status"
            data-state={state}
            className="m-0 font-semibold"
          >
            {state === 'outage'
              ? t('live.consoles.outage', { id: sensorId })
              : state === 'heard'
                ? t('live.consoles.heard', { count: recent.length, seconds: RECENT_S })
                : t('live.consoles.heardNone')}
          </p>
          {state === 'listening' && (
            <p className="m-0 text-ink-2">{t('live.consoles.rf.listenBody')}</p>
          )}
          <table className="w-full border-collapse text-left" data-testid="rf-reports">
            <caption className="micro-label pb-1 text-left">
              {t('live.consoles.rf.caption')}
            </caption>
            <thead>
              <tr className="border-b border-line text-ink-2">
                <th scope="col" className="pr-1 font-medium">
                  {t('live.consoles.rf.band')}
                </th>
                <th scope="col" className="pr-1 text-right font-medium">
                  {t('live.consoles.rf.level')}
                </th>
                <th scope="col" className="pr-1 font-medium">
                  {t('live.consoles.rf.link')}
                </th>
                <th scope="col" className="text-right font-medium">
                  {t('live.consoles.bearing')}
                </th>
              </tr>
            </thead>
            <tbody>
              {recent.length === 0 ? (
                <tr>
                  <td colSpan={4} className="py-1 text-ink-2">
                    {t('live.consoles.tableEmpty', { seconds: RECENT_S })}
                  </td>
                </tr>
              ) : (
                recent.map((e, i) => (
                  <tr
                    key={`${e.timeS}-${e.sensorId}-${i}`}
                    className="border-b border-line align-top"
                  >
                    <td className="num pr-1">{e.bandLabel || '—'}</td>
                    <td className="num pr-1 text-right">{e.rssiDbm.toFixed(1)}</td>
                    <td className="pr-1">
                      {!e.hopping
                        ? t('live.consoles.rf.fixed')
                        : e.hopRateHz > 0
                          ? t('live.consoles.rf.hopping', { rate: e.hopRateHz.toFixed(1) })
                          : t('live.consoles.rf.hoppingUnknown')}
                    </td>
                    <td className="num text-right">{fmtBearing(e.azimuthDeg)}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
          <ScaleBar range={t('live.consoles.rf.scaleRange')} />
          <p className="m-0 text-2xs text-ink-2">{t('live.consoles.rf.legend')}</p>
          <p className="m-0 text-2xs text-ink-2">{t('live.consoles.decor')}</p>
        </>
      }
      footer={
        <>
          <p className="m-0 text-ink">
            <SynthLabel statuses={statuses} />
          </p>
          <p className="m-0" data-testid="rf-open-note">
            {t('live.consoles.rfOpen')}
          </p>
        </>
      }
    />
  )
}
