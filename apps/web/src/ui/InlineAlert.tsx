import { CheckmarkFilled, ErrorFilled, InformationFilled, WarningFilled } from '@carbon/icons-react'
import type { ReactNode } from 'react'

type Tone = 'info' | 'success' | 'warning' | 'error'

const icons = {
  info: InformationFilled,
  success: CheckmarkFilled,
  warning: WarningFilled,
  error: ErrorFilled,
}
const colours: Record<Tone, string> = {
  info: 'text-accent',
  success: 'text-track-neutral',
  warning: 'text-signal',
  error: 'text-track-hostile',
}

export function InlineAlert({ tone = 'info', children }: { tone?: Tone; children: ReactNode }) {
  const Icon = icons[tone]
  return (
    <div
      role={tone === 'error' || tone === 'warning' ? 'alert' : 'status'}
      className="flex items-start gap-2 border border-line bg-surface-2 p-3 text-sm"
    >
      <span className={`mt-0.5 shrink-0 ${colours[tone]}`}>
        <Icon size={16} aria-hidden="true" />
      </span>
      <div>{children}</div>
    </div>
  )
}
