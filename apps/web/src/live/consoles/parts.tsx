import { useEffect, useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { InlineAlert } from '../../ui/InlineAlert'
import { useLive, useLiveSession } from '../context'
import { fmtElapsed } from '../format'
import { INFERNO_LUT } from './spectra'

/** No frame for this long while the session runs means the stream has stopped. */
export const STALE_AFTER_MS = 3000

export interface StreamState {
  /** The link dropped or frames stopped arriving: the picture is frozen. */
  stale: boolean
  /** Scenario time of the last frame. */
  lastTimeS: number
  hasFrame: boolean
  closed: boolean
}

/** Whether the frame stream is alive, checked once a second (and on every connection change). */
export function useStreamState(): StreamState {
  const session = useLiveSession()
  const connection = useLive((s) => s.connection)
  const hasFrame = useLive((s) => s.frame !== null)
  const [idle, setIdle] = useState(false)

  useEffect(() => {
    const check = () => {
      const state = session.store.getState()
      setIdle(
        state.frame !== null &&
          state.status === 'running' &&
          performance.now() - state.frameAt > STALE_AFTER_MS,
      )
    }
    check()
    const timer = window.setInterval(check, 1000)
    return () => window.clearInterval(timer)
  }, [session])

  const dropped = connection.state === 'reconnecting' || connection.state === 'closed'
  return {
    stale: hasFrame && (dropped || idle),
    // read when the render happens, which is when `stale` changes; it is only shown while stale
    lastTimeS: session.store.getState().frame?.time_s ?? 0,
    hasFrame,
    closed: connection.state === 'closed',
  }
}

/** The inferno map as a legend strip, with its numeric range beside it. */
const STRIP = `linear-gradient(to right, ${Array.from({ length: 9 }, (_, i) => {
  const k = Math.round((i / 8) * 255) * 3
  return `rgb(${INFERNO_LUT[k]}, ${INFERNO_LUT[k + 1]}, ${INFERNO_LUT[k + 2]})`
}).join(', ')})`

export function ScaleBar({ range }: { range: string }) {
  const { t } = useTranslation()
  return (
    <div className="text-2xs text-ink-2">
      <div className="mb-0.5">{t('live.consoles.scaleBar')}</div>
      <div
        aria-hidden="true"
        className="h-2 w-full border border-line"
        style={{ background: STRIP }}
      />
      <div className="num mt-0.5">{range}</div>
    </div>
  )
}

/**
 * The body of one console: the plot on the left and a scrollable readout column on the right.
 * The column is a keyboard stop because it scrolls.
 */
export function ConsoleBody({
  plot,
  side,
  sideLabel,
}: {
  plot: ReactNode
  side: ReactNode
  sideLabel: string
}) {
  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="grid min-h-0 flex-1 grid-cols-[minmax(0,1fr)_216px] gap-px bg-line">
        {plot}
        <div
          tabIndex={0}
          role="group"
          aria-label={sideLabel}
          className="flex min-h-0 flex-col gap-2 overflow-auto bg-surface-1 p-2 text-xs"
        >
          {side}
        </div>
      </div>
    </div>
  )
}

/** The frozen-display notice: the existing warning alert, with the scenario time of the last frame. */
export function StaleNotice({ lastTimeS }: { lastTimeS: number }) {
  const { t } = useTranslation()
  return (
    <div
      className="shrink-0 border-b border-line bg-surface-1 px-2 py-1"
      data-testid="console-stale"
    >
      <InlineAlert tone="warning">
        <p className="m-0 font-semibold">{t('live.consoles.stale.title')}</p>
        <p className="num m-0 text-xs text-ink-2">
          {t('live.consoles.stale.body', { time: fmtElapsed(lastTimeS) })}
        </p>
      </InlineAlert>
    </div>
  )
}
