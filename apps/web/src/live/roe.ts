/**
 * Rules-of-engagement text for the decision panel: the verdict codes rendered in the current
 * language, and the pre-commit preview of which rule would permit a chosen response.
 * The server's verdict is authoritative; the preview is indicative only and says so.
 */
import type { TFunction } from 'i18next'
import { polarFrom } from './geometry'
import type { Briefing, RuleView, RulesView, TrackView, Vec3 } from './protocol'
import type { Verdict } from './store'

export type Lang = 'en' | 'hi'

export const pick = (text: { en: string; hi: string }, lang: Lang): string => text[lang]

export interface UnmetLine {
  field: string
  required: string
  actual: string
}

export interface VerdictText {
  permitted: boolean
  headline: string
  rule: string | null
  pack: string
  reason: string
  unmet: UnmetLine[]
}

const asList = (value: unknown): unknown[] => (Array.isArray(value) ? value : [value])

function formatValue(field: string, value: unknown, t: TFunction): string {
  if (value === null || value === undefined) return t('live.roe.notSet')
  if (field === 'confidence' && typeof value === 'number') return `${Math.round(value * 100)}%`
  const key =
    field === 'identity'
      ? 'live.identity'
      : field === 'classification'
        ? 'live.class'
        : field === 'zone'
          ? 'live.zone'
          : null
  return asList(value)
    .map((v) => (key ? t(`${key}.${String(v)}`, { defaultValue: String(v) }) : String(v)))
    .join(' / ')
}

const fieldLabel = (field: string, t: TFunction): string =>
  t(`live.roe.field.${field}`, { defaultValue: field })

/** The effector class label for an ID, from the rule pack in force. */
export function effectorLabel(id: string, rules: RulesView, lang: Lang): string {
  const found = rules.effector_classes.find((e) => e.id === id)
  return found ? pick(found.label, lang) : id
}

/** Render a logged verdict: headline, rule title, pack, the reason for its code and unmet rows. */
export function describeVerdict(
  verdict: Verdict,
  rules: RulesView,
  t: TFunction,
  lang: Lang,
): VerdictText {
  const detail = verdict.detail
  const unmetRaw = Array.isArray(detail.unmet) ? (detail.unmet as Record<string, unknown>[]) : []
  const unmet = unmetRaw.map((row) => {
    const field = String(row.field ?? '')
    const required =
      field === 'confidence' && typeof row.required === 'number'
        ? t('live.roe.atLeast', { value: formatValue(field, row.required, t) })
        : formatValue(field, row.required, t)
    return {
      field: fieldLabel(field, t),
      required,
      actual: formatValue(field, row.actual, t),
    }
  })
  const allowed = asList(detail.allowed ?? [])
    .map((id) => effectorLabel(String(id), rules, lang))
    .join(', ')
  const reason = t(`live.roe.reason.${verdict.code}`, {
    defaultValue: t('live.roe.reason.unknown', { code: verdict.code }),
    rule: verdict.ruleTitle ? pick(verdict.ruleTitle, lang) : '',
    action: t(`live.roe.action.${verdict.action}`, { defaultValue: verdict.action }),
    effector: verdict.effectorClass ? effectorLabel(verdict.effectorClass, rules, lang) : '',
    allowed,
    authority: t(
      `live.roe.authority.${String(detail.required ?? verdict.authority ?? 'commander')}`,
      {
        defaultValue: String(detail.required ?? verdict.authority ?? ''),
      },
    ),
  })
  return {
    permitted: verdict.permitted,
    headline: t(verdict.permitted ? 'live.roe.permitted' : 'live.roe.blocked'),
    rule: verdict.ruleTitle ? pick(verdict.ruleTitle, lang) : null,
    pack: `${verdict.packId} ${verdict.packVersion}`,
    reason,
    unmet,
  }
}

// ---------------------------------------------------------------------- preview

/** The first rule that lists `action` (and, for engage, the effector class), in pack order. */
export function ruleThatWouldPermit(
  rules: RulesView,
  action: string,
  effectorClass: string | null,
): RuleView | null {
  return (
    rules.rules.find(
      (rule) =>
        rule.permits.includes(action) &&
        (action !== 'engage' ||
          (effectorClass !== null && rule.effector_classes.includes(effectorClass))),
    ) ?? null
  )
}

/** The role of the smallest zone that contains the position, or null outside every zone. */
export function zoneRoleAt(briefing: Briefing, position: Vec3): string | null {
  const zones = [...briefing.zones].sort((a, b) => a.radius_m - b.radius_m)
  for (const zone of zones) {
    if (polarFrom(zone.center, { ...position, z: zone.center.z }).rangeM <= zone.radius_m) {
      return zone.role
    }
  }
  return null
}

export interface ConditionLine {
  field: 'identity' | 'classification' | 'zone' | 'confidence'
  required: string
  status: 'met' | 'unmet'
}

export interface PreviewContext {
  identity: string | null
  classification: string | null
  zoneRole: string | null
  confidence: number
}

/** What the client can see of the context the rules will be asked about. */
export function previewContext(
  track: TrackView,
  briefing: Briefing,
  assessments: Record<string, string>,
  classifications: Record<string, string>,
): PreviewContext {
  return {
    identity: assessments[track.id] ?? null,
    classification: classifications[track.id] ?? null,
    zoneRole: zoneRoleAt(briefing, track.position),
    confidence: track.class_support,
  }
}

/** The rule's conditions, each marked met or unmet against what the client knows. */
export function conditionLines(rule: RuleView, ctx: PreviewContext, t: TFunction): ConditionLine[] {
  const when = rule.when as Record<string, unknown>
  const lines: ConditionLine[] = []
  const list = (key: string): string[] | null =>
    Array.isArray(when[key]) ? (when[key] as unknown[]).map(String) : null
  const identity = list('identity_in')
  if (identity)
    lines.push({
      field: 'identity',
      required: formatValue('identity', identity, t),
      status: identity.includes(ctx.identity ?? 'unknown') ? 'met' : 'unmet',
    })
  const classification = list('classification_in')
  if (classification)
    lines.push({
      field: 'classification',
      required: formatValue('classification', classification, t),
      status:
        ctx.classification !== null && classification.includes(ctx.classification)
          ? 'met'
          : 'unmet',
    })
  const zone = list('zone_role_in')
  if (zone)
    lines.push({
      field: 'zone',
      required: formatValue('zone', zone, t),
      status: ctx.zoneRole !== null && zone.includes(ctx.zoneRole) ? 'met' : 'unmet',
    })
  if (typeof when.min_confidence === 'number')
    lines.push({
      field: 'confidence',
      required: t('live.roe.atLeast', { value: formatValue('confidence', when.min_confidence, t) }),
      status: ctx.confidence >= when.min_confidence ? 'met' : 'unmet',
    })
  return lines
}
