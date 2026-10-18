/** One line of text per trainee event, in the current language, for the event log and outcomes. */
import type { TFunction } from 'i18next'
import { fmtBearing, fmtPercent, fmtRange } from './format'
import type { TraineeEvent } from './protocol'
import { pick, type Lang } from './roe'

export type Tone = 'ok' | 'refused' | 'blocked' | 'info'

export interface EventLine {
  tone: Tone
  text: string
  /** The track the event is about, when it has one. */
  track: string | null
}

const s = (value: unknown): string => (typeof value === 'string' ? value : '')
const n = (value: unknown, digits = 1): string =>
  typeof value === 'number' && Number.isFinite(value) ? value.toFixed(digits) : '—'

/** The fields of a filed contact report as one phrase, or null for a bare report. */
function reportDetail(p: Record<string, unknown>, t: TFunction): string | null {
  const part = (key: string, value: string) => t(`live.event.reportDetail.${key}`, { value })
  const parts: string[] = []
  if (typeof p.class_id === 'string')
    parts.push(t(`live.class.${p.class_id}`, { defaultValue: p.class_id }))
  if (typeof p.count === 'number') parts.push(part('count', String(p.count)))
  if (typeof p.bearing_deg === 'number' && typeof p.range_m === 'number')
    parts.push(
      t('live.event.reportDetail.where', {
        bearing: fmtBearing(p.bearing_deg),
        range: fmtRange(p.range_m),
      }),
    )
  if (typeof p.heading_deg === 'number') parts.push(part('heading', fmtBearing(p.heading_deg)))
  if (typeof p.confidence === 'number') parts.push(part('confidence', fmtPercent(p.confidence)))
  return parts.length > 0 ? parts.join(', ') : null
}

export function describeEvent(event: TraineeEvent, t: TFunction, lang: Lang): EventLine {
  const p = event.payload
  const track = s(p.track) || s(p.source) || s(p.survivor) || null
  const line = (tone: Tone, key: string, params: Record<string, unknown> = {}): EventLine => ({
    tone,
    text: t(`live.event.${key}`, params),
    track,
  })
  switch (event.type) {
    case 'session.start':
      return line('info', 'sessionStart')
    case 'session.end':
      return line('info', 'sessionEnd')
    case 'track.init':
      return line('info', 'trackInit', { track: s(p.track) })
    case 'track.confirm':
      return line('info', 'trackConfirm', { track: s(p.track) })
    case 'track.coast':
      return line('info', 'trackCoast', { track: s(p.track) })
    case 'track.resume':
      return line('info', 'trackResume', { track: s(p.track) })
    case 'track.drop':
      return line('ok', 'trackDrop', {
        track: s(p.track),
        reason: t(`live.event.dropReason.${s(p.reason)}`, { defaultValue: s(p.reason) }),
      })
    case 'track.relabel':
      return line('ok', p.exchanged_with ? 'trackRelabelSwap' : 'trackRelabel', {
        track: s(p.track),
        label: s(p.label),
        previous: s(p.previous),
        other: s(p.exchanged_with),
      })
    case 'track.merge':
      return line('ok', 'trackMerge', { survivor: s(p.survivor), absorbed: s(p.absorbed) })
    case 'track.split':
      return line('ok', 'trackSplit', { source: s(p.source), created: s(p.new) })
    case 'sensor.cue':
      return p.accepted === false
        ? line('refused', 'cueRefused', {
            sensor: s(p.sensor),
            track: s(p.track),
            reason: s(p.reason),
          })
        : line('ok', 'cueAccepted', {
            sensor: s(p.sensor),
            track: s(p.track),
            bearing: n(p.bearing_deg),
            fov: n(p.fov_deg),
          })
    case 'action.rejected':
      return line('refused', 'rejected', {
        action: t(`live.roe.action.${s(p.action)}`, { defaultValue: s(p.action) }),
        reason: s(p.reason),
      })
    case 'roe.verdict': {
      const title = p.rule_title as { en: string; hi: string } | null
      return line(
        p.permitted === true ? 'ok' : 'blocked',
        p.permitted === true ? 'verdictPermitted' : 'verdictBlocked',
        {
          action: t(`live.roe.action.${s(p.action)}`, { defaultValue: s(p.action) }),
          track: s(p.track),
          rule: title ? pick(title, lang) : t('live.event.noRule'),
        },
      )
    }
    case 'action.classify':
      return line('ok', 'classified', {
        track: s(p.track),
        value: t(`live.class.${s(p.class_id)}`, { defaultValue: s(p.class_id) }),
      })
    case 'action.assess':
      return line('ok', 'assessed', {
        track: s(p.track),
        value: t(`live.identity.${s(p.identity)}`, { defaultValue: s(p.identity) }),
      })
    case 'action.engage':
      return line('ok', 'engaged', { track: s(p.track), effector: s(p.effector_class) })
    case 'action.hold':
      return line('ok', 'held', { track: s(p.track) })
    case 'action.report': {
      const detail = reportDetail(p, t)
      return detail
        ? line('ok', 'reportedWith', { track: s(p.track), detail })
        : line('ok', 'reported', { track: s(p.track) })
    }
    case 'action.designate':
      return line('ok', 'designated', { track: s(p.track) })
    default:
      if (event.type.startsWith('action.')) {
        // The operator's own accepted track command or cue; the tracker's answer follows it.
        const name = event.type.slice('action.'.length).replace(/_/g, '-')
        return line('info', 'requested', {
          action: t(`live.roe.action.${name}`, { defaultValue: name }),
        })
      }
      return { tone: 'info', text: event.type, track }
  }
}
