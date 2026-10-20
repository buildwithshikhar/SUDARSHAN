import {
  useCallback,
  useEffect,
  useId,
  useMemo,
  useState,
  useSyncExternalStore,
  type KeyboardEvent,
} from 'react'
import { useTranslation } from 'react-i18next'
import { fmtBearing } from '../format'
import { RECENT_S, type ConsoleFeed } from './feed'
import { drawAcoustic, RowImage } from './draw'
import { ConsoleBody, ScaleBar, type StreamState } from './parts'
import { moveCursor, nearestHarmonic } from './spectra'
import { useInstrument } from './useInstrument'

const MONO = '"IBM Plex Mono", ui-monospace, Menlo, Consolas, monospace'

export function AcousticConsole({
  feed,
  stream,
  sensorId,
  outage,
  lang,
}: {
  feed: ConsoleFeed
  stream: StreamState
  sensorId: string
  outage: boolean
  lang: string
}) {
  const { t } = useTranslation()
  const readoutId = useId()
  useSyncExternalStore(feed.subscribe, feed.getVersion)
  const recent = feed.acousticRecent
  const image = useMemo(() => new RowImage(feed.acoustic.ring), [feed])
  const [cursor, setCursor] = useState(feed.cursorHz)
  const [focused, setFocused] = useState(false)
  const [announce, setAnnounce] = useState('')
  const staleMark = t('live.consoles.stale.mark')
  const stale = stream.stale

  const paint = useCallback(
    (ctx: CanvasRenderingContext2D, width: number, height: number) => {
      image.sync()
      drawAcoustic(ctx, {
        width,
        height,
        mono: MONO,
        image,
        cursorHz: cursor,
        focused,
        lines: feed.acousticRecent,
        stale: stale ? { text: staleMark } : null,
      })
    },
    [feed, image, cursor, focused, stale, staleMark],
  )
  const { wrapRef, canvasRef, invalidate } = useInstrument({
    paint,
    modelVersion: () => feed.acoustic.ring.version,
  })
  useEffect(invalidate, [invalidate, cursor, focused, stale, staleMark, lang, recent])

  const nearest = nearestHarmonic(cursor, recent)
  const describe = (hz: number) => {
    const n = nearestHarmonic(hz, recent)
    return n
      ? `${t('live.consoles.ac.moved', { hz })} · ${t('live.consoles.ac.nearest')}: ${t('live.consoles.ac.nearestValue', { order: n.order, line: n.lineHz.toFixed(1), delta: n.deltaHz.toFixed(1) })}`
      : t('live.consoles.ac.moved', { hz })
  }

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return
    if (event.altKey || event.ctrlKey || event.metaKey) return
    event.preventDefault()
    const next = moveCursor(cursor, event.key === 'ArrowLeft' ? -1 : 1, event.shiftKey)
    feed.setCursor(next)
    setCursor(next)
    setAnnounce(describe(next))
  }

  const state = outage ? 'outage' : recent.length > 0 ? 'heard' : 'listening'

  return (
    <ConsoleBody
      sideLabel={t('live.consoles.tabAcoustic')}
      plot={
        <div
          ref={wrapRef}
          role="group"
          tabIndex={0}
          aria-label={t('live.consoles.ac.group')}
          aria-describedby={readoutId}
          data-testid="spectrogram"
          data-cursor={cursor}
          data-rows={feed.acoustic.ring.count}
          onKeyDown={onKeyDown}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          className="relative min-h-0 bg-bg"
        >
          <canvas
            ref={canvasRef}
            role="img"
            aria-label={t('live.consoles.ac.aria')}
            className="absolute inset-0 h-full w-full"
          />
          <span className="sr-only" role="status" aria-live="polite">
            {announce}
          </span>
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
            <p className="m-0 text-ink-2">{t('live.consoles.ac.listenBody')}</p>
          )}
          <dl id={readoutId} data-testid="cursor-readout" className="m-0 grid gap-0.5">
            <div>
              <dt className="micro-label">{t('live.consoles.ac.cursor')}</dt>
              <dd className="num m-0 text-sm">{t('live.consoles.ac.cursorHz', { hz: cursor })}</dd>
            </div>
            <div>
              <dt className="micro-label">{t('live.consoles.ac.nearest')}</dt>
              <dd className="num m-0" data-testid="cursor-nearest">
                {nearest
                  ? t('live.consoles.ac.nearestValue', {
                      order: nearest.order,
                      line: nearest.lineHz.toFixed(1),
                      delta: nearest.deltaHz.toFixed(1),
                    })
                  : t('live.consoles.ac.none')}
              </dd>
            </div>
            <div>
              <dt className="micro-label">{t('live.consoles.ac.implied')}</dt>
              <dd className="num m-0" data-testid="cursor-implied">
                {nearest
                  ? t('live.consoles.ac.impliedValue', {
                      bpf: nearest.impliedBladePassHz.toFixed(1),
                    })
                  : t('live.consoles.ac.none')}
              </dd>
            </div>
          </dl>
          <p className="m-0 text-2xs text-ink-2">{t('live.consoles.ac.keys')}</p>
          <table className="w-full border-collapse text-left" data-testid="ac-reports">
            <caption className="micro-label pb-1 text-left">
              {t('live.consoles.ac.caption')}
            </caption>
            <thead>
              <tr className="border-b border-line text-ink-2">
                <th scope="col" className="pr-1 text-right font-medium">
                  {t('live.consoles.ac.bladePass')}
                </th>
                <th scope="col" className="pr-1 text-right font-medium">
                  {t('live.consoles.ac.harmonics')}
                </th>
                <th scope="col" className="pr-1 font-medium">
                  {t('live.consoles.ac.tonal')}
                </th>
                <th scope="col" className="pr-1 text-right font-medium">
                  {t('live.consoles.ac.snr')}
                </th>
                <th scope="col" className="text-right font-medium">
                  {t('live.consoles.bearing')}
                </th>
              </tr>
            </thead>
            <tbody>
              {recent.length === 0 ? (
                <tr>
                  <td colSpan={5} className="py-1 text-ink-2">
                    {t('live.consoles.tableEmpty', { seconds: RECENT_S })}
                  </td>
                </tr>
              ) : (
                recent.map((e, i) => (
                  <tr
                    key={`${e.timeS}-${e.sensorId}-${i}`}
                    className="border-b border-line align-top"
                  >
                    <td className="num pr-1 text-right">{e.fundamentalHz.toFixed(1)}</td>
                    <td className="num pr-1 text-right">{e.harmonics}</td>
                    <td className="pr-1">
                      {e.tonal ? t('live.consoles.ac.yes') : t('live.consoles.ac.no')}
                    </td>
                    <td className="num pr-1 text-right">{e.snrDb.toFixed(1)}</td>
                    <td className="num text-right">{fmtBearing(e.azimuthDeg)}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
          <ScaleBar range={t('live.consoles.ac.scaleRange')} />
          <p className="m-0 text-2xs text-ink-2">{t('live.consoles.ac.legend')}</p>
        </>
      }
    />
  )
}
