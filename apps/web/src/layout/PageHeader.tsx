import type { ReactNode } from 'react'

export function PageHeader({
  title,
  crumbs,
  actions,
}: {
  title: string
  crumbs?: string[]
  actions?: ReactNode
}) {
  return (
    <div className="mb-4 flex items-end justify-between gap-4 border-b border-line pb-3">
      <div>
        {crumbs && crumbs.length > 0 && (
          <p className="num m-0 mb-1 text-xs text-ink-2">{crumbs.join(' / ')}</p>
        )}
        <h1 className="m-0 text-lg font-semibold">{title}</h1>
      </div>
      {actions}
    </div>
  )
}
