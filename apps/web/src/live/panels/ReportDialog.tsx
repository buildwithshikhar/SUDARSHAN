import { ErrorFilled } from '@carbon/icons-react'
import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '../../ui/Button'
import { Dialog } from '../../ui/Dialog'
import { Input, Select } from '../../ui/Field'
import { checkReport, prefillReport, type ReportField, type ReportValues } from '../report'
import type { Briefing, TrackView } from '../protocol'

const FORM_ID = 'contact-report-form'

/**
 * The structured contact report: what, where, how many, heading and confidence. Opened by
 * choosing "Report up the chain" in the Respond step. Everything is optional; "Skip details" files
 * a bare report. The values start from the selected track and can be edited.
 */
export function ReportDialog({
  track,
  briefing,
  classes,
  classification,
  onClose,
  onSubmit,
  onSkip,
}: {
  track: TrackView | null
  briefing: Briefing
  classes: string[]
  classification: string | null
  onClose: () => void
  onSubmit: (payload: Record<string, unknown>) => void
  onSkip: (track: string) => void
}) {
  const { t } = useTranslation()
  return (
    <Dialog
      open={track !== null}
      title={t('live.report.title', { track: track?.label ?? '' })}
      onClose={onClose}
      width="w-[600px]"
    >
      {track && (
        <ReportForm
          key={track.id}
          track={track}
          briefing={briefing}
          classes={classes}
          classification={classification}
          onSubmit={onSubmit}
          onSkip={onSkip}
          onClose={onClose}
        />
      )}
    </Dialog>
  )
}

function ReportForm({
  track,
  briefing,
  classes,
  classification,
  onSubmit,
  onSkip,
  onClose,
}: {
  track: TrackView
  briefing: Briefing
  classes: string[]
  classification: string | null
  onSubmit: (payload: Record<string, unknown>) => void
  onSkip: (track: string) => void
  onClose: () => void
}) {
  const { t } = useTranslation()
  const [values, setValues] = useState<ReportValues>(() =>
    prefillReport(
      track,
      briefing,
      classification && classes.includes(classification) ? classification : null,
    ),
  )
  const [attempted, setAttempted] = useState(false)
  const form = useRef<HTMLFormElement>(null)
  const check = checkReport(track.id, values)
  const errors = attempted ? check.errors : {}
  const failures = Object.keys(errors).length

  const set = (field: ReportField) => (value: string) =>
    setValues((current) => ({ ...current, [field]: value }))
  const text = (field: ReportField) => ({
    value: values[field],
    onChange: (event: { target: { value: string } }) => set(field)(event.target.value),
  })
  const message = (field: ReportField): string | undefined => {
    const key = errors[field]
    return key ? t(`live.report.error.${key}`) : undefined
  }

  // After a refused submit, put focus on the first field that needs fixing.
  const [refusals, setRefusals] = useState(0)
  useEffect(() => {
    if (refusals > 0) form.current?.querySelector<HTMLElement>('[aria-invalid="true"]')?.focus()
  }, [refusals])

  const submit = (event: FormEvent) => {
    event.preventDefault()
    setAttempted(true)
    if (check.payload) onSubmit(check.payload)
    else setRefusals((n) => n + 1)
  }

  // Digits choose the class while the select has focus: 1 to 4, and 0 for not stated.
  const chooseByDigit = (event: KeyboardEvent<HTMLSelectElement>) => {
    if (event.ctrlKey || event.metaKey || event.altKey || !/^[0-9]$/.test(event.key)) return
    const n = Number(event.key)
    if (n === 0) set('what')('')
    else if (n <= classes.length) set('what')(classes[n - 1] ?? '')
    else return
    event.preventDefault()
  }

  return (
    <form
      id={FORM_ID}
      ref={form}
      onSubmit={submit}
      onKeyDown={(event) => {
        if (event.key === 'Escape') {
          event.preventDefault()
          onClose()
        }
      }}
      noValidate
      className="flex flex-col gap-3"
    >
      <p className="m-0 text-sm text-ink-2">{t('live.report.intro')}</p>
      {failures > 0 && (
        <p role="alert" className="m-0 flex items-start gap-2 text-sm" data-testid="report-errors">
          <ErrorFilled size={16} aria-hidden="true" className="mt-px shrink-0 text-track-hostile" />
          {t('live.report.errorSummary')}
        </p>
      )}
      <Select
        label={t('live.report.what')}
        hint={t('live.report.whatHint')}
        value={values.what}
        onChange={(event) => set('what')(event.target.value)}
        onKeyDown={chooseByDigit}
        options={[
          { value: '', label: `0 · ${t('live.report.whatNone')}` },
          ...classes.map((id, index) => ({
            value: id,
            label: `${index + 1} · ${t(`live.class.${id}`, { defaultValue: id })}`,
          })),
        ]}
      />
      <fieldset className="m-0 grid grid-cols-2 gap-x-3 gap-y-3 border-0 p-0">
        <legend className="col-span-2 mb-1 p-0 text-xs font-medium text-ink-2">
          {t('live.report.where')}
        </legend>
        <Input
          label={t('live.report.bearing')}
          hint={t('live.report.bearingHint')}
          error={message('bearing')}
          inputMode="decimal"
          autoComplete="off"
          className="num"
          {...text('bearing')}
        />
        <Input
          label={t('live.report.range')}
          hint={t('live.report.rangeHint')}
          error={message('range')}
          inputMode="decimal"
          autoComplete="off"
          className="num"
          {...text('range')}
        />
      </fieldset>
      <div className="grid grid-cols-3 gap-x-3">
        <Input
          label={t('live.report.count')}
          hint={t('live.report.countHint')}
          error={message('count')}
          inputMode="numeric"
          autoComplete="off"
          className="num"
          {...text('count')}
        />
        <Input
          label={t('live.report.heading')}
          hint={t('live.report.headingHint')}
          error={message('heading')}
          inputMode="decimal"
          autoComplete="off"
          className="num"
          {...text('heading')}
        />
        <Input
          label={t('live.report.confidence')}
          hint={t('live.report.confidenceHint')}
          error={message('confidence')}
          inputMode="decimal"
          autoComplete="off"
          className="num"
          {...text('confidence')}
        />
      </div>
      <p className="m-0 text-xs text-ink-2">{t('live.report.prefill')}</p>
      <p className="m-0 text-xs text-ink-2">{t('live.report.keys')}</p>
      <div className="-mx-4 -mb-4 mt-1 flex justify-end gap-2 border-t border-line px-4 py-3">
        <Button onClick={onClose}>{t('live.decision.cancel')}</Button>
        <Button onClick={() => onSkip(track.id)} title={t('live.report.skipHint')}>
          {t('live.report.skip')}
        </Button>
        <Button variant="primary" type="submit">
          {t('live.report.submit')}
        </Button>
      </div>
    </form>
  )
}
