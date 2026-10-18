import { CheckmarkOutline, CloseOutline, Information, Locked } from '@carbon/icons-react'
import { useEffect, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { useLive } from '../context'
import { describeEvent, type Tone } from '../eventText'
import { fmtElapsed, useLang } from '../format'

const ICON = {
  ok: CheckmarkOutline,
  refused: CloseOutline,
  blocked: Locked,
  info: Information,
} as const

/** Trainee events, newest last. The tone is carried by an icon and a word, never colour alone. */
export function EventLog() {
  const { t } = useTranslation()
  const lang = useLang()
  const events = useLive((s) => s.events)
  const list = useRef<HTMLOListElement>(null)
  useEffect(() => {
    const el = list.current
    if (el) el.scrollTop = el.scrollHeight
  }, [events])
  const shown = events.slice(-60)

  return (
    <div className="flex h-full min-h-0 flex-col">
      {shown.length === 0 ? (
        <p className="m-0 p-3 text-xs text-ink-2">{t('live.log.empty')}</p>
      ) : (
        <ol
          ref={list}
          role="log"
          aria-label={t('live.log.title')}
          aria-live="polite"
          className="m-0 min-h-0 flex-1 list-none overflow-auto p-0"
        >
          {shown.map((event) => {
            const line = describeEvent(event, t, lang)
            const Icon = ICON[line.tone]
            return (
              <li
                key={event.seq}
                className="flex items-baseline gap-2 border-b border-line px-2 py-0.5 text-xs last:border-b-0"
              >
                <span className="num shrink-0 text-ink-2">{fmtElapsed(event.t / 20)}</span>
                <Icon
                  size={16}
                  aria-hidden="true"
                  className="shrink-0 translate-y-0.5 text-ink-2"
                />
                <span>
                  <span className="sr-only">{t(`live.log.tone.${line.tone as Tone}`)}: </span>
                  {line.text}
                </span>
              </li>
            )
          })}
        </ol>
      )}
    </div>
  )
}
