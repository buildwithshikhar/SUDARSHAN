import type { TFunction } from 'i18next'
import { useTranslation } from 'react-i18next'
import { useLive } from '../context'
import { fmtBearing, fmtPercent, fmtRange, fmtSpeed, sensorCode, sitePosition } from '../format'
import { polarFrom, wrap180 } from '../geometry'
import type { Report, TrackView, Welcome } from '../protocol'

const RF_MAX_AGE_S = 6

/** The latest RF report whose bearing from the RF site agrees with the track: the 'RF link' feature. */
export function rfLinkFor(
  track: TrackView,
  reports: readonly (Report & { timeS: number })[],
  sites: Record<string, { x: number; y: number; z: number }>,
  nowS: number,
): (Report & { timeS: number }) | null {
  let best: { report: Report & { timeS: number }; gap: number } | null = null
  for (const r of reports) {
    const site = sites[r.sensor_id]
    if (!site || nowS - r.timeS > RF_MAX_AGE_S) continue
    const expected = polarFrom(site, track.position).bearingDeg
    const gap = Math.abs(wrap180(expected - r.azimuth_deg))
    const limit = Math.max(10, 3 * (r.sigma_azimuth_deg ?? 5))
    if (gap <= limit && (!best || gap < best.gap)) best = { report: r, gap }
  }
  return best?.report ?? null
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid shrink-0 grid-cols-[80px_1fr] items-baseline gap-2">
      <dt className="text-xs text-ink-2">{label}</dt>
      <dd className="num m-0 text-xs">{children}</dd>
    </div>
  )
}

function rfText(r: Report, t: TFunction): string {
  const f = r.features
  const parts = [String(f.band ?? '')]
  parts.push(
    f.hopping === true
      ? t('live.detail.hopping', { rate: Number(f.hop_rate_hz ?? 0).toFixed(1) })
      : t('live.detail.fixed'),
  )
  if (typeof f.rssi_dbm === 'number') parts.push(`${f.rssi_dbm.toFixed(1)} dBm`)
  return parts.filter(Boolean).join(' · ')
}

export function TrackDetail({ welcome }: { welcome: Welcome }) {
  const { t } = useTranslation()
  const frame = useLive((s) => s.frame)
  const selected = useLive((s) => s.selected)
  const assessments = useLive((s) => s.assessments)
  const classifications = useLive((s) => s.classifications)
  const rf = useLive((s) => s.rfReports)
  const track = frame?.tracks.find((x) => x.id === selected)
  if (!frame || !track) {
    return (
      <div className="flex h-full flex-col justify-center gap-1 p-3 text-sm text-ink-2">
        <p className="m-0 font-semibold text-ink">{t('live.detail.none')}</p>
        <p className="m-0 text-xs">{t('live.detail.noneBody')}</p>
      </div>
    )
  }
  const site = sitePosition(welcome.briefing)
  const polar = polarFrom(site, track.position)
  const assist = frame.assist.find((a) => a.track === track.id)
  const sites = Object.fromEntries(frame.sensors.map((s) => [s.id, s.position]))
  const link = rfLinkFor(track, rf, sites, frame.time_s)
  const mine = classifications[track.id]
  const identity = assessments[track.id]

  return (
    <dl
      tabIndex={0}
      aria-label={t('live.detail.title')}
      className="m-0 flex h-full flex-col gap-0.5 overflow-auto px-3 py-2"
    >
      <Row label={t('live.detail.track')}>
        {track.label}
        {track.label !== track.id && <span className="text-ink-2"> ({track.id})</span>} ·{' '}
        {t(`live.track.status.${track.status}`)} · {track.age_s.toFixed(0)} s{' '}
        {track.data_status === 'reference' ? (
          <abbr
            title={t('live.detail.reference')}
            className="border border-line px-1 text-2xs text-ink-2 no-underline"
          >
            {t('live.table.ref')}
          </abbr>
        ) : (
          <span className="text-ink-2">{t('live.detail.verified')}</span>
        )}
      </Row>
      <Row label={t('live.detail.fromSite')}>
        {fmtBearing(polar.bearingDeg)} · {fmtRange(polar.rangeM)} · {t('live.detail.alt')}{' '}
        {Math.round(track.position.z)} m
      </Row>
      <Row label={t('live.detail.motion')}>
        {fmtSpeed(track.speed_mps)} {t('live.units.mps')} · {fmtBearing(track.heading_deg)} · σ{' '}
        {track.sigma_position_m.toFixed(0)} m
      </Row>
      <Row label={t('live.detail.estimate')}>
        {track.class_estimate
          ? t(`live.class.${track.class_estimate}`, { defaultValue: track.class_estimate })
          : '—'}{' '}
        {track.class_estimate ? fmtPercent(track.class_support) : ''} · {t('live.detail.sensors')}{' '}
        {track.sensors.map(sensorCode).join(' ')}
      </Row>
      <Row label={t('live.detail.yours')}>
        {mine ? t(`live.class.${mine}`, { defaultValue: mine }) : t('live.detail.notSet')} ·{' '}
        {identity
          ? t(`live.identity.${identity}`, { defaultValue: identity })
          : t('live.detail.notSet')}
      </Row>
      <Row label={t('live.detail.assist')}>
        {assist ? (
          <>
            {t(`live.assist.flag.${assist.flag}`)} {fmtPercent(assist.confidence)}
            {assist.proposed_class
              ? ` · ${t(`live.class.${assist.proposed_class}`, { defaultValue: assist.proposed_class })}`
              : ''}
            <span className="block text-ink-2">
              {t('live.assist.source', { source: assist.source })}
            </span>
          </>
        ) : (
          '—'
        )}
      </Row>
      <Row label={t('live.detail.rfLink')}>{link ? rfText(link, t) : t('live.detail.noRf')}</Row>
    </dl>
  )
}
