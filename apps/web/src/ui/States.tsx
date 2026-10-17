import { CloudOffline, Information } from '@carbon/icons-react'
import type { ReactNode } from 'react'
import { Button } from './Button'

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string
  description?: string
  action?: ReactNode
}) {
  return (
    <div className="flex flex-col items-start gap-2 border border-dashed border-line p-6">
      <Information size={20} aria-hidden="true" className="text-ink-2" />
      <p className="m-0 text-md font-semibold">{title}</p>
      {description && <p className="m-0 max-w-[560px] text-sm text-ink-2">{description}</p>}
      {action}
    </div>
  )
}

export function LoadingState({ label }: { label: string }) {
  return (
    <div role="status" aria-live="polite" className="flex flex-col gap-2 p-3">
      <span className="sr-only">{label}</span>
      {[160, 240, 200].map((width) => (
        <span key={width} aria-hidden="true" className="block h-2 bg-surface-2" style={{ width }} />
      ))}
    </div>
  )
}

export function ErrorState({
  title,
  description,
  retryLabel,
  onRetry,
  offline = false,
}: {
  title: string
  description?: string
  retryLabel: string
  onRetry: () => void
  offline?: boolean
}) {
  return (
    <div
      role="alert"
      className="flex flex-col items-start gap-2 border border-line bg-surface-1 p-6"
    >
      {offline && <CloudOffline size={20} aria-hidden="true" className="text-ink-2" />}
      <p className="m-0 text-md font-semibold">{title}</p>
      {description && <p className="m-0 max-w-[560px] text-sm text-ink-2">{description}</p>}
      <Button onClick={onRetry}>{retryLabel}</Button>
    </div>
  )
}
