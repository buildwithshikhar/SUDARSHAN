import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '../../ui/Button'
import { Dialog } from '../../ui/Dialog'
import { Checkbox, Input } from '../../ui/Field'

const SHORTCUTS: { keys: string; id: string }[] = [
  { keys: 'Tab · Shift+Tab', id: 'cycle' },
  { keys: 'C', id: 'classify' },
  { keys: 'A', id: 'assess' },
  { keys: 'R', id: 'respond' },
  { keys: '1 – 9', id: 'choose' },
  { keys: 'Enter', id: 'commit' },
  { keys: 'Esc', id: 'cancel' },
  { keys: 'H', id: 'hold' },
  { keys: 'U', id: 'cue' },
  { keys: 'L', id: 'relabel' },
  { keys: 'M', id: 'merge' },
  { keys: 'S', id: 'split' },
  { keys: 'D', id: 'drop' },
  { keys: 'X', id: 'dismiss' },
  { keys: '?', id: 'help' },
]

export function ShortcutsDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { t } = useTranslation()
  return (
    <Dialog
      open={open}
      title={t('live.keys.title')}
      onClose={onClose}
      actions={<Button onClick={onClose}>{t('live.keys.close')}</Button>}
    >
      <table className="w-full border-collapse text-left text-sm">
        <caption className="sr-only">{t('live.keys.title')}</caption>
        <thead>
          <tr className="border-b border-line text-xs text-ink-2">
            <th scope="col" className="h-6 pr-3 font-medium">
              {t('live.keys.key')}
            </th>
            <th scope="col" className="h-6 font-medium">
              {t('live.keys.does')}
            </th>
          </tr>
        </thead>
        <tbody>
          {SHORTCUTS.map((row) => (
            <tr key={row.id} className="h-6 border-b border-line last:border-b-0">
              <td className="num pr-3">
                <kbd className="num">{row.keys}</kbd>
              </td>
              <td>{t(`live.keys.${row.id}`)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="mb-0 mt-3 text-xs text-ink-2">{t('live.keys.note')}</p>
    </Dialog>
  )
}

export function RelabelDialog({
  track,
  current,
  onClose,
  onSubmit,
}: {
  track: string | null
  current: string
  onClose: () => void
  onSubmit: (label: string, exchange: boolean) => void
}) {
  const { t } = useTranslation()
  return (
    <Dialog
      open={track !== null}
      title={t('live.relabel.title', { track: track ?? '' })}
      onClose={onClose}
    >
      {track !== null && (
        <RelabelForm key={track} current={current} onClose={onClose} onSubmit={onSubmit} />
      )}
    </Dialog>
  )
}

function RelabelForm({
  current,
  onClose,
  onSubmit,
}: {
  current: string
  onClose: () => void
  onSubmit: (label: string, exchange: boolean) => void
}) {
  const { t } = useTranslation()
  const [label, setLabel] = useState(current)
  const [exchange, setExchange] = useState(false)
  const trimmed = label.trim()
  const submit = (event: FormEvent) => {
    event.preventDefault()
    if (trimmed.length === 0) return
    onSubmit(trimmed, exchange)
  }
  return (
    <form onSubmit={submit} className="flex flex-col gap-3">
      <Input
        label={t('live.relabel.label')}
        hint={t('live.relabel.hint')}
        value={label}
        maxLength={24}
        onChange={(event) => setLabel(event.target.value)}
        autoComplete="off"
      />
      <Checkbox
        label={t('live.relabel.exchange')}
        checked={exchange}
        onChange={(event) => setExchange(event.target.checked)}
      />
      <div className="flex justify-end gap-2">
        <Button onClick={onClose}>{t('live.decision.cancel')}</Button>
        <Button type="submit" variant="primary" disabled={trimmed.length === 0}>
          {t('live.relabel.apply')}
        </Button>
      </div>
    </form>
  )
}

export function EndDialog({
  open,
  onClose,
  onConfirm,
}: {
  open: boolean
  onClose: () => void
  onConfirm: () => void
}) {
  const { t } = useTranslation()
  return (
    <Dialog
      open={open}
      title={t('live.end.title')}
      onClose={onClose}
      actions={
        <>
          <Button onClick={onClose}>{t('live.decision.cancel')}</Button>
          <Button variant="primary" onClick={onConfirm}>
            {t('live.end.confirm')}
          </Button>
        </>
      }
    >
      <p className="m-0">{t('live.end.body')}</p>
    </Dialog>
  )
}
