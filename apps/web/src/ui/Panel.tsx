import { useId, type ReactNode } from 'react'

interface Props {
  title: string
  actions?: ReactNode
  children: ReactNode
  className?: string
  flush?: boolean
}

/** A bordered region with a header row. Panels are separated by borders, not shadows. */
export function Panel({ title, actions, children, className = '', flush = false }: Props) {
  const id = useId()
  return (
    <section aria-labelledby={id} className={`border border-line bg-surface-1 ${className}`}>
      <header className="flex h-8 items-center justify-between border-b border-line px-3">
        <h2 id={id} className="m-0 text-sm font-semibold">
          {title}
        </h2>
        {actions}
      </header>
      <div className={flush ? '' : 'p-3'}>{children}</div>
    </section>
  )
}
