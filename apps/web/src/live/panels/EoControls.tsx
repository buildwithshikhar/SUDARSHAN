import { Information } from '@carbon/icons-react'
import { useTranslation } from 'react-i18next'
import { Segmented } from '../../ui/Segmented'
import { Tooltip } from '../../ui/Tooltip'
import { TIER_CHOICES, type TierChoice } from '../quality'
import { useQuality } from '../qualityStore'
import type { EoMode } from '../views/eoMode'

/**
 * The picture mode of the EO sensor. Only the modes its profile supports are offered, so a day
 * camera shows one and a thermal camera shows both polarities. Thermal and night vision carry a
 * short note that they are rendering models.
 */
export function EoModeControl({
  modes,
  mode,
  onChange,
}: {
  modes: readonly EoMode[]
  mode: EoMode
  onChange: (mode: EoMode) => void
}) {
  const { t } = useTranslation()
  const helpKey = mode === 'day' ? null : mode.startsWith('thermal') ? 'thermal' : mode
  return (
    <div className="flex items-center gap-1">
      <Segmented
        label={t('live.eo.mode')}
        value={mode}
        options={modes.map((m) => ({ value: m, label: t(`live.eo.modeName.${m}`) }))}
        onChange={onChange}
      />
      {helpKey && (
        <Tooltip label={t(`live.eo.modeHelp.${helpKey}`)}>
          <button
            type="button"
            className="inline-flex h-7 w-7 items-center justify-center border border-line bg-surface-1 text-ink-2 hover:text-ink"
            aria-label={t('live.eo.modeHelpLabel')}
          >
            <Information size={16} aria-hidden="true" />
          </button>
        </Tooltip>
      )}
    </div>
  )
}

/** Graphics quality: Auto picks a tier from measured frame times; the others fix it. */
export function QualityControl() {
  const { t } = useTranslation()
  const { choice, tier, phase, stats, setChoice } = useQuality()
  const measured = phase !== 'probe' && stats.count > 30
  return (
    <div className="flex items-center gap-2">
      <Segmented<TierChoice>
        label={t('live.eo.quality.label')}
        value={choice}
        options={TIER_CHOICES.map((c) => ({ value: c, label: t(`live.eo.quality.${c}`) }))}
        onChange={setChoice}
      />
      <span
        className="num hidden min-w-[88px] text-2xs text-ink-2 2xl:inline"
        data-testid="quality-readout"
      >
        {t(`live.eo.quality.${tier}`)}
        {measured ? ` · ${Math.round(stats.fps5th)} fps` : ''}
      </span>
    </div>
  )
}
