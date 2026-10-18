import { Checkmark, Close } from '@carbon/icons-react'
import { useTranslation } from 'react-i18next'
import { Button } from '../../ui/Button'
import { useLive } from '../context'
import { STEPS, stepOptions, type Option, type Step } from '../decision'
import { useLang } from '../format'
import type { Welcome } from '../protocol'
import { conditionLines, effectorLabel, pick, previewContext, ruleThatWouldPermit } from '../roe'
import type { WorkspaceControls } from '../useWorkspaceControls'

function useOptionLabel(welcome: Welcome) {
  const { t } = useTranslation()
  const lang = useLang()
  return (option: Option): string => {
    switch (option.kind) {
      case 'class':
        return t(`live.class.${option.value}`, { defaultValue: option.value })
      case 'identity':
        return t(`live.identity.${option.value}`, { defaultValue: option.value })
      case 'engage':
        return t('live.respond.engage', {
          effector: effectorLabel(option.value, welcome.rules, lang),
        })
      case 'report':
        return t('live.respond.report')
      case 'hold':
        return t('live.respond.hold')
    }
  }
}

function RulePreview({
  welcome,
  option,
  track,
}: {
  welcome: Welcome
  option: Option
  track: string
}) {
  const { t } = useTranslation()
  const lang = useLang()
  const frame = useLive((s) => s.frame)
  const assessments = useLive((s) => s.assessments)
  const classifications = useLive((s) => s.classifications)
  const view = frame?.tracks.find((x) => x.id === track)
  const action = option.kind === 'engage' ? 'engage' : option.kind
  const rule = ruleThatWouldPermit(
    welcome.rules,
    action,
    option.kind === 'engage' ? option.value : null,
  )
  if (action === 'hold' && !rule) {
    return <p className="m-0 text-xs text-ink-2">{t('live.preview.holdDefault')}</p>
  }
  if (!rule) {
    return (
      <p className="m-0 text-xs">
        {t('live.preview.noRule', { action: t(`live.roe.action.${action}`) })}{' '}
        <span className="text-ink-2">
          {t('live.preview.packOf', { pack: `${welcome.rules.id} ${welcome.rules.version}` })}
        </span>
      </p>
    )
  }
  const lines = view
    ? conditionLines(rule, previewContext(view, welcome.briefing, assessments, classifications), t)
    : []
  return (
    <div className="flex flex-col gap-1">
      <p className="m-0 text-xs">
        <span className="text-ink-2">{t('live.preview.permittedBy')}</span> {pick(rule.title, lang)}
      </p>
      <p className="num m-0 text-2xs text-ink-2">
        {welcome.rules.id} {welcome.rules.version} ·{' '}
        {t('live.preview.authority', { authority: t(`live.roe.authority.${rule.authority}`) })}
      </p>
      {lines.length > 0 && (
        <ul className="m-0 flex list-none flex-wrap gap-x-4 gap-y-0 p-0 text-xs">
          {lines.map((line) => (
            <li key={line.field} className="flex items-center gap-1">
              {line.status === 'met' ? (
                <Checkmark size={16} aria-hidden="true" className="text-track-neutral" />
              ) : (
                <Close size={16} aria-hidden="true" className="text-track-hostile" />
              )}
              <span>
                {t(`live.roe.field.${line.field}`)}: {line.required}{' '}
                <span className="text-ink-2">
                  ({t(line.status === 'met' ? 'live.preview.met' : 'live.preview.unmet')})
                </span>
              </span>
            </li>
          ))}
        </ul>
      )}
      <p className="m-0 text-2xs text-ink-2">{t('live.preview.indicative')}</p>
    </div>
  )
}

export function DecisionPanel({
  welcome,
  controls,
}: {
  welcome: Welcome
  controls: WorkspaceControls
}) {
  const { t } = useTranslation()
  const selected = useLive((s) => s.selected)
  const frame = useLive((s) => s.frame)
  const assessments = useLive((s) => s.assessments)
  const classifications = useLive((s) => s.classifications)
  const pending = useLive((s) => s.pending)
  const label = useOptionLabel(welcome)
  const { decision } = controls
  const track = frame?.tracks.find((x) => x.id === selected)
  const options = decision.step ? stepOptions(decision.step, welcome) : []
  const chosen = decision.step && decision.chosen !== null ? options[decision.chosen] : undefined
  const last = pending[pending.length - 1]

  const stepDone = (step: Step): string | null => {
    if (!selected) return null
    if (step === 'classify') {
      const v = classifications[selected]
      return v ? t(`live.class.${v}`, { defaultValue: v }) : null
    }
    if (step === 'assess') {
      const v = assessments[selected]
      return v ? t(`live.identity.${v}`, { defaultValue: v }) : null
    }
    return null
  }

  return (
    <div className="flex h-full min-h-0 flex-col" data-testid="decision-panel">
      <div
        className="flex h-7 shrink-0 items-center gap-1 border-b border-line px-2"
        role="group"
        aria-label={t('live.decision.steps')}
      >
        {STEPS.map((step, index) => {
          const active = decision.step === step
          const done = stepDone(step)
          return (
            <button
              key={step}
              type="button"
              aria-current={active ? 'step' : undefined}
              disabled={!track}
              onClick={() => controls.run({ kind: 'open', step })}
              className={`inline-flex h-6 items-center gap-2 border px-2 text-xs disabled:cursor-not-allowed disabled:opacity-50 ${
                active
                  ? 'border-accent bg-surface-2 text-ink'
                  : 'border-line text-ink-2 hover:text-ink'
              }`}
            >
              <span className="num text-2xs">{index + 1}</span>
              <span>{t(`live.decision.step.${step}`)}</span>
              <kbd className="num border border-line px-1 text-2xs text-ink-2">
                {t(`live.decision.key.${step}`)}
              </kbd>
              {done && <span className="text-ink-2">· {done}</span>}
            </button>
          )
        })}
        <span className="num ml-auto text-xs text-ink-2">{track ? `${track.label}` : ''}</span>
      </div>

      <div
        className="min-h-0 flex-1 overflow-auto p-2"
        tabIndex={0}
        role="group"
        aria-label={t('live.decision.title')}
      >
        {!track && (
          <div className="flex h-full flex-col justify-center gap-1">
            <p className="m-0 text-sm font-semibold">{t('live.decision.noTrack')}</p>
            <p className="m-0 text-xs text-ink-2">{t('live.decision.noTrackBody')}</p>
          </div>
        )}
        {track && !decision.step && !decision.confirmDrop && (
          <div className="flex h-full flex-col justify-center gap-1">
            <p className="m-0 text-sm font-semibold">
              {t('live.decision.ready', { track: track.label })}
            </p>
            <p className="m-0 text-xs text-ink-2">{t('live.decision.readyBody')}</p>
          </div>
        )}
        {track && decision.confirmDrop && (
          <div
            className="flex h-full flex-col justify-center gap-2"
            role="alertdialog"
            aria-label={t('live.decision.dropTitle')}
          >
            <p className="m-0 text-sm font-semibold">
              {t('live.decision.dropConfirm', { track: track.label })}
            </p>
            <div className="flex gap-2">
              <Button
                variant="primary"
                onClick={() => controls.run({ kind: 'commit' })}
                data-decision-option=""
              >
                {t('live.decision.dropYes')}
              </Button>
              <Button onClick={() => controls.run({ kind: 'cancel' })}>
                {t('live.decision.cancel')}
              </Button>
            </div>
          </div>
        )}
        {track && decision.step && (
          <div className="flex flex-col gap-2">
            <ol
              className="m-0 grid list-none grid-cols-1 gap-1 p-0 2xl:grid-cols-2"
              aria-label={t(`live.decision.step.${decision.step}`)}
            >
              {options.map((option, index) => {
                const on = decision.chosen === index
                return (
                  <li key={`${option.kind}-${option.value}`}>
                    <button
                      type="button"
                      data-decision-option=""
                      aria-pressed={on}
                      title={label(option)}
                      onClick={() => controls.choose(index)}
                      className={`flex h-6 w-full items-center gap-2 border px-2 text-left text-xs ${
                        on
                          ? 'border-accent bg-surface-2 text-ink'
                          : 'border-line text-ink hover:border-accent'
                      }`}
                    >
                      <span className="num w-4 border border-line text-center text-2xs text-ink-2">
                        {index + 1}
                      </span>
                      <span className="truncate">{label(option)}</span>
                    </button>
                  </li>
                )
              })}
            </ol>
            {decision.step === 'respond' && chosen && (
              <div className="border-t border-line pt-2">
                <RulePreview welcome={welcome} option={chosen} track={track.id} />
              </div>
            )}
          </div>
        )}
      </div>

      <div className="flex h-7 shrink-0 items-center justify-between gap-2 border-t border-line px-2">
        <p className="m-0 truncate text-2xs text-ink-2">{t('live.decision.hint')}</p>
        <div className="flex items-center gap-2">
          {last && (
            <span role="status" className="num truncate text-2xs text-ink-2">
              {t(`live.pending.${last.state}`, {
                action: t(`live.roe.action.${last.action}`),
                message: last.message ?? '',
              })}
            </span>
          )}
          {decision.step && (
            <>
              <Button
                variant="primary"
                disabled={chosen === undefined}
                onClick={() => controls.run({ kind: 'commit' })}
              >
                {t('live.decision.commit')}
              </Button>
              <Button onClick={() => controls.run({ kind: 'cancel' })}>
                {t('live.decision.cancel')}
              </Button>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
