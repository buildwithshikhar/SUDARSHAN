import { useTranslation } from 'react-i18next'
import { useLive } from '../context'
import { fmtBearing } from '../format'
import type { Affiliation } from '../views/theme'

const COLOUR: Record<Affiliation, string> = {
  hostile: 'var(--track-hostile)',
  suspect: 'var(--track-suspect)',
  unknown: 'var(--track-unknown)',
  neutral: 'var(--track-neutral)',
  friend: 'var(--track-friend)',
}

/** The legend glyphs mirror the canvas symbols: one frame shape per assessed identity. */
function Glyph({ kind }: { kind: Affiliation }) {
  const common = { fill: 'none', stroke: COLOUR[kind], strokeWidth: 1.5 }
  return (
    <svg width="18" height="18" viewBox="-9 -9 18 18" aria-hidden="true" focusable="false">
      {kind === 'hostile' && <path d="M0 -7 L7 0 L0 7 L-7 0 Z" {...common} />}
      {kind === 'suspect' && <path d="M0 -7 L7 0 L0 7 L-7 0 Z" {...common} strokeDasharray="3 2" />}
      {kind === 'friend' && <rect x="-7" y="-5" width="14" height="10" {...common} />}
      {kind === 'neutral' && <rect x="-5.5" y="-5.5" width="11" height="11" {...common} />}
      {kind === 'unknown' && (
        <path
          d="M0 -5.95 A4.3 4.3 0 1 1 5.95 0 A4.3 4.3 0 1 1 0 5.95 A4.3 4.3 0 1 1 -5.95 0 A4.3 4.3 0 1 1 0 -5.95 Z"
          {...common}
        />
      )}
    </svg>
  )
}

const IDENTITIES: Affiliation[] = ['hostile', 'suspect', 'unknown', 'neutral', 'friend']

export function SensorStatus() {
  const { t } = useTranslation()
  const frame = useLive((s) => s.frame)
  return (
    <div className="flex h-full min-h-0 flex-col gap-2 overflow-auto p-2 text-xs">
      <section aria-labelledby="sensors-h">
        <h3 id="sensors-h" className="micro-label m-0 mb-1">
          {t('live.sensors.title')}
        </h3>
        <ul className="m-0 flex list-none flex-col gap-1 p-0">
          {(frame?.sensors ?? []).map((s) => (
            <li key={s.id} className="border-b border-line pb-1 last:border-b-0">
              <div className="flex justify-between gap-2">
                <span className="num">{s.id}</span>
                <span>
                  {s.outage
                    ? t('live.sensors.outage')
                    : s.cued
                      ? t('live.sensors.cued')
                      : t('live.sensors.ok')}
                </span>
              </div>
              <div className="num text-ink-2">
                {t(`live.modality.${s.modality}`)} · {fmtBearing(s.bearing_deg)}
                {s.fov_deg !== null ? ` · ${s.fov_deg.toFixed(1)}°` : ''}
              </div>
            </li>
          ))}
        </ul>
      </section>
      <section aria-labelledby="legend-h">
        <h3 id="legend-h" className="micro-label m-0 mb-1">
          {t('live.legend.title')}
        </h3>
        <ul className="m-0 grid list-none grid-cols-1 gap-0 p-0 2xl:grid-cols-1">
          {IDENTITIES.map((kind) => (
            <li key={kind} className="flex h-[18px] items-center gap-2">
              <Glyph kind={kind} />
              <span>{t(`live.identity.${kind}`)}</span>
            </li>
          ))}
        </ul>
        <p className="m-0 mt-1 hidden text-2xs text-ink-2 2xl:block">{t('live.legend.note')}</p>
      </section>
    </div>
  )
}
