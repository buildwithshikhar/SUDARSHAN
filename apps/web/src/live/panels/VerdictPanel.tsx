import { CheckmarkFilled, ErrorFilled } from '@carbon/icons-react'
import { useTranslation } from 'react-i18next'
import { useLive, useLiveSession } from '../context'
import { useLang } from '../format'
import type { Welcome } from '../protocol'
import { describeVerdict } from '../roe'

/**
 * The server's rules verdict for the last response. A blocked response is marked three ways, by
 * words, by a stop icon and by a heavy outline, and it stays here until dismissed or replaced.
 */
export function VerdictPanel({ welcome }: { welcome: Welcome }) {
  const { t } = useTranslation()
  const lang = useLang()
  const session = useLiveSession()
  const verdict = useLive((s) => s.verdict)

  if (!verdict) {
    return (
      <div className="flex h-full flex-col justify-center gap-1 p-3">
        <p className="m-0 text-sm font-semibold">{t('live.verdict.none')}</p>
        <p className="m-0 text-xs text-ink-2">
          {t('live.verdict.noneBody', { pack: `${welcome.rules.id} ${welcome.rules.version}` })}
        </p>
      </div>
    )
  }
  const text = describeVerdict(verdict, welcome.rules, t, lang)
  const blocked = !text.permitted
  const Icon = blocked ? ErrorFilled : CheckmarkFilled

  return (
    <div
      role={blocked ? 'alert' : 'status'}
      data-testid="verdict"
      data-permitted={text.permitted ? 'true' : 'false'}
      className={`flex h-full min-h-0 flex-col gap-1 overflow-auto p-2 ${blocked ? 'border-2 border-track-hostile bg-surface-2' : 'border-l-2 border-track-neutral'}`}
    >
      <div className="flex items-center gap-2">
        <Icon
          size={20}
          aria-hidden="true"
          className={blocked ? 'text-track-hostile' : 'text-track-neutral'}
        />
        <p className="m-0 text-md font-semibold tracking-[0.06em]">{text.headline}</p>
        <span className="num text-xs text-ink-2">
          {t(`live.roe.action.${verdict.action}`, { defaultValue: verdict.action })} ·{' '}
          {verdict.track}
        </span>
        <button
          type="button"
          onClick={() => session.store.dispatch({ type: 'dismiss-verdict' })}
          className="ml-auto h-6 border border-line px-2 text-xs text-ink-2 hover:border-accent hover:text-ink"
        >
          {t('live.verdict.dismiss')} <kbd className="num ml-1 text-2xs">X</kbd>
        </button>
      </div>
      {text.rule && (
        <p className="m-0 text-xs">
          <span className="text-ink-2">{t('live.verdict.rule')}</span> {text.rule}
        </p>
      )}
      <p className="m-0 text-xs">{text.reason}</p>
      {text.unmet.length > 0 && (
        <table className="w-full border-collapse text-xs">
          <caption className="sr-only">{t('live.verdict.unmetCaption')}</caption>
          <thead>
            <tr className="text-left text-ink-2">
              <th scope="col" className="h-5 pr-2 font-medium">
                {t('live.verdict.field')}
              </th>
              <th scope="col" className="h-5 pr-2 font-medium">
                {t('live.verdict.required')}
              </th>
              <th scope="col" className="h-5 font-medium">
                {t('live.verdict.actual')}
              </th>
            </tr>
          </thead>
          <tbody>
            {text.unmet.map((row) => (
              <tr key={row.field} className="border-t border-line">
                <td className="h-5 pr-2">{row.field}</td>
                <td className="num pr-2">{row.required}</td>
                <td className="num">{row.actual}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <p className="num m-0 mt-auto text-2xs text-ink-2">
        {t('live.verdict.pack', { pack: text.pack })}
        {verdict.authority
          ? ` · ${t(`live.roe.authority.${verdict.authority}`, { defaultValue: verdict.authority })}`
          : ''}
      </p>
    </div>
  )
}
