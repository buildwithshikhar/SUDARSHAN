import { CheckmarkFilled, CircleDash, ErrorFilled, WarningFilled } from '@carbon/icons-react'
import type { TFunction } from 'i18next'
import { useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { useLocation } from 'react-router-dom'
import { ApiError, NetworkError } from '../lib/api'
import { scenarioApi, type ScenarioApi } from './api'
import type { Check, LintItem, SolvabilityStatus, ValidationError } from './types'

/** The scenario client for the page, with `?mock=1` honoured in the dev server. */
export function useScenarioApi(): ScenarioApi {
  const { search } = useLocation()
  return useMemo(() => scenarioApi(search), [search])
}

export type Failure = 'network' | 'forbidden' | 'notFound' | 'error'

export const failureOf = (error: unknown): Failure =>
  error instanceof NetworkError
    ? 'network'
    : error instanceof ApiError && (error.status === 401 || error.status === 403)
      ? 'forbidden'
      : error instanceof ApiError && error.status === 404
        ? 'notFound'
        : 'error'

export const isAbort = (error: unknown): boolean =>
  error instanceof DOMException && error.name === 'AbortError'

/** `0.923` as `92.3%`. */
export const fmtPct = (share: number): string => `${(share * 100).toFixed(1)}%`

/** `0.4` as `0.400`: indices and distances. */
export const fmt3 = (value: number): string => value.toFixed(3)

/** Seconds as `m:ss`. */
export function fmtClock(seconds: number): string {
  const total = Math.max(0, Math.round(seconds))
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, '0')}`
}

/**
 * A server code rendered through the catalogue: `scenarios.<group>.<code>` when it has an entry,
 * else null so the caller falls back to the server's English text.
 */
export function catalogueText(
  t: TFunction,
  i18n: { exists: (key: string) => boolean },
  key: string,
): string | null {
  return i18n.exists(key) ? t(key) : null
}

export interface Rendered {
  /** The sentence in the interface language, or null when the catalogue has no entry. */
  title: string | null
  /** The server's English message, shown whenever it adds to the title. */
  detail: string
}

export function lintText(
  t: TFunction,
  i18n: { exists: (key: string) => boolean },
  item: LintItem,
): Rendered {
  return { title: catalogueText(t, i18n, `scenarios.lint.${item.code}`), detail: item.message }
}

export function errorText(
  t: TFunction,
  i18n: { exists: (key: string) => boolean },
  error: ValidationError,
): Rendered {
  const prefix = error.code.split('.')[0] ?? error.code
  return { title: catalogueText(t, i18n, `scenarios.error.${prefix}`), detail: error.message }
}

export function checkTitle(
  t: TFunction,
  i18n: { exists: (key: string) => boolean },
  check: Check,
): string {
  return catalogueText(t, i18n, `scenarios.check.${check.code}`) ?? check.name
}

const statusIcon = { verified: CheckmarkFilled, failed: ErrorFilled, unchecked: CircleDash }
const statusTone: Record<SolvabilityStatus, string> = {
  verified: 'border-track-neutral text-track-neutral',
  failed: 'border-track-hostile text-track-hostile',
  unchecked: 'border-line text-ink-2',
}

/**
 * The solvability badge. Its text is the only solvability sentence the product uses; the icon and
 * the border reinforce it, and colour is never the only cue.
 */
export function SolvabilityBadge({ status }: { status: SolvabilityStatus }) {
  const { t } = useTranslation()
  const Icon = statusIcon[status]
  return (
    <span
      data-status={status}
      className={`inline-flex min-h-5 items-center gap-1 whitespace-nowrap border px-2 text-xs ${statusTone[status]}`}
    >
      <Icon size={16} aria-hidden="true" />
      {t(`scenarios.solvability.${status}`)}
    </span>
  )
}

export function SeverityMark({ severity }: { severity: 'error' | 'warning' }) {
  const { t } = useTranslation()
  const Icon = severity === 'error' ? ErrorFilled : WarningFilled
  return (
    <span className="inline-flex items-center gap-1 text-xs text-ink">
      <Icon
        size={16}
        aria-hidden="true"
        className={severity === 'error' ? 'text-track-hostile' : 'text-signal'}
      />
      {t(`scenarios.severity.${severity}`)}
    </span>
  )
}

/** The sensor family named by a profile id such as `radar-generic-s`. */
export const modalityOf = (profileId: string): string => profileId.split('-')[0] ?? profileId

/** The eight feature axes of a scenario as labelled numbers. */
export function FeatureList({
  features,
  wide = false,
}: {
  features: Record<string, number>
  wide?: boolean
}) {
  const { t } = useTranslation()
  return (
    <div
      role="group"
      aria-label={t('scenarios.editor.checks.features')}
      className="border-t border-line"
    >
      <dl className={`m-0 grid grid-cols-2 ${wide ? 'md:grid-cols-4' : ''}`}>
        {Object.entries(features).map(([axis, value]) => (
          <div
            key={axis}
            className="flex items-baseline justify-between gap-2 border-b border-line px-3 py-0.5"
          >
            <dt className="text-xs text-ink-2">
              {t(`scenarios.feature.${axis}`, { defaultValue: axis })}
            </dt>
            <dd className="num m-0 text-sm">{fmt3(value)}</dd>
          </div>
        ))}
      </dl>
    </div>
  )
}
