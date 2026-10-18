/**
 * Explanations for the debrief. The evaluator returns reason keys and parameters only; this module
 * turns a key and its parameters into a plain sentence in English or Hindi from the `scoring.*`
 * entries of the message catalogues, following the parameter rules in docs/SCORING.md.
 */
import i18n from '../i18n'
import { fmtPercent } from './format'
import type { Lang } from './roe'

export type ReasonParams = Record<string, unknown> | null | undefined

const text = (lang: Lang, key: string, options?: Record<string, unknown>): string =>
  String(i18n.getFixedT(lang)(key, options as never))

export const num = (value: unknown): number | null =>
  typeof value === 'number' && Number.isFinite(value) ? value : null

/** Seconds, one decimal. */
export const fmtSeconds = (value: number): string => `${value.toFixed(1)} s`
export const fmtMetres = (value: number): string => `${Math.round(value).toLocaleString('en-US')} m`
export const fmtDegrees = (value: number): string => `${Math.round(value)}°`

const isLabel = (value: unknown): value is { en: string; hi: string } =>
  typeof value === 'object' &&
  value !== null &&
  typeof (value as { en?: unknown }).en === 'string' &&
  typeof (value as { hi?: unknown }).hi === 'string'

const classLabel = (id: unknown, lang: Lang): string =>
  text(lang, `live.class.${String(id)}`, { defaultValue: String(id) })

const identityLabel = (id: unknown, lang: Lang): string =>
  text(lang, `live.identity.${String(id)}`, { defaultValue: String(id) })

export const dispositionLabel = (id: unknown, lang: Lang): string =>
  text(lang, `scoring.disposition.${String(id)}`, { defaultValue: String(id) })

export const reportFieldLabel = (id: unknown, lang: Lang): string =>
  text(lang, `scoring.reportField.${String(id)}`, { defaultValue: String(id) })

export const nodeLabel = (id: string, lang: Lang): string =>
  text(lang, `scoring.node.${id}`, { defaultValue: id })

export const className = classLabel

const actionLabel = (action: unknown, lang: Lang): string => {
  const name = String(action).replace(/_/g, '-')
  return text(lang, `live.roe.action.${name}`, { defaultValue: name })
}

/** Which vocabulary `given` and `actual` belong to, from the key they appear in. */
function pairKind(key: string): 'class' | 'assess' | 'number' | 'hard-fail' {
  if (/^(lesson\.)?assess\./.test(key)) return 'assess'
  if (/^report\.count\./.test(key)) return 'number'
  if (/^(finding|lesson)\.hard-fail\./.test(key)) return 'hard-fail'
  return 'class'
}

const PERCENT_PARAMS = new Set(['timing', 'timeliness', 'stated', 'achieved', 'credit'])
const SECONDS_PARAMS = new Set(['seconds', 'standard', 't'])
const METRE_PARAMS = new Set(['error_m', 'tolerance_m'])
const DEGREE_PARAMS = new Set(['error_deg', 'tolerance_deg'])

/** Every parameter of a message as display text, by the rules in docs/SCORING.md "Explanations". */
export function formatParams(
  key: string,
  params: ReasonParams,
  lang: Lang,
): Record<string, string> {
  const out: Record<string, string> = {}
  const kind = pairKind(key)
  for (const [name, value] of Object.entries(params ?? {})) {
    const n = num(value)
    if (name === 'threat' && isLabel(value)) out[name] = value[lang]
    else if (name === 'class') out[name] = classLabel(value, lang)
    else if (name === 'given' || name === 'actual') {
      if (kind === 'assess')
        out[name] = name === 'given' ? identityLabel(value, lang) : dispositionLabel(value, lang)
      else if (kind === 'number') out[name] = String(value)
      else if (kind === 'hard-fail' && name === 'actual') out[name] = dispositionLabel(value, lang)
      else out[name] = classLabel(value, lang)
    } else if (name === 'worst_field') out[name] = reportFieldLabel(value, lang)
    else if (name === 'first_action') out[name] = actionLabel(value, lang)
    else if (n !== null && SECONDS_PARAMS.has(name)) out[name] = fmtSeconds(n)
    else if (n !== null && PERCENT_PARAMS.has(name)) out[name] = fmtPercent(n)
    else if (n !== null && METRE_PARAMS.has(name)) out[name] = fmtMetres(n)
    else if (n !== null && DEGREE_PARAMS.has(name)) out[name] = fmtDegrees(n)
    else if (value === null || value === undefined) out[name] = '—'
    else out[name] = String(value)
  }
  return out
}

const fill = (template: string, values: Record<string, string>): string =>
  template.replace(/\{\{\s*(\w+)\s*\}\}/g, (_, name: string) => values[name] ?? '—')

/** The catalogue entry for `scoring.<key>` with its placeholders intact, English if Hindi lacks it. */
function rawTemplate(lang: Lang, key: string): string | null {
  for (const l of lang === 'en' ? (['en'] as const) : (['hi', 'en'] as const)) {
    const found: unknown = i18n.getResource(l, 'translation', `scoring.${key}`)
    if (typeof found === 'string') return found
  }
  return null
}

/**
 * One plain sentence for a reason key and its parameters. A parameter the key needs but the
 * evaluator did not send is shown as a dash, never as a raw placeholder. Interpolation is done
 * here so that the parameter formats above are the only ones applied.
 */
export function renderReason(key: string, params: ReasonParams, lang: Lang): string {
  const values = formatParams(key, params, lang)
  let sentence = fill(rawTemplate(lang, key) ?? key, values)
  const changes = num(params?.changes)
  if (key === 'classify.correct' && changes !== null && changes > 0)
    sentence += ` ${fill(rawTemplate(lang, 'extra.changes') ?? '', values)}`
  const blocked = num(params?.blocked_attempts)
  if (/^respond\./.test(key) && blocked !== null && blocked > 0)
    sentence += ` ${fill(rawTemplate(lang, 'extra.blocked') ?? '', values)}`
  return sentence
}

/** The share of a mark as points of its weight, two decimals: "0.12 of 0.15". */
export const fmtPoints = (score: number, weight: number): string =>
  `${(score * weight).toFixed(3)} / ${weight.toFixed(2)}`

/** A fraction as a percentage with one decimal, for scores. */
export const fmtScore = (share: number | null | undefined): string =>
  share === null || share === undefined ? '—' : `${(share * 100).toFixed(1)}%`

/** Cost of a lesson or finding in points of the contact score (out of 100). */
export const fmtCostPoints = (cost: number): string => (cost * 100).toFixed(1)
