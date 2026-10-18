import { useEffect, useId, useRef, type ReactNode } from 'react'

interface Props {
  open: boolean
  title: string
  onClose: () => void
  children: ReactNode
  actions?: ReactNode
  /** Tailwind width class; 480 px by default. */
  width?: string
}

/** Modal dialog on the native <dialog> element: focus is trapped and Escape closes it. */
export function Dialog({ open, title, onClose, children, actions, width = 'w-[480px]' }: Props) {
  const ref = useRef<HTMLDialogElement>(null)
  const titleId = useId()

  useEffect(() => {
    const dialog = ref.current
    if (!dialog) return
    if (open && !dialog.open) dialog.showModal()
    if (!open && dialog.open) dialog.close()
  }, [open])

  return (
    <dialog
      ref={ref}
      aria-labelledby={titleId}
      onClose={onClose}
      className={`m-auto ${width} max-w-[calc(100vw-32px)] border border-line bg-surface-1 p-0 text-ink backdrop:bg-black/60`}
    >
      <h2 id={titleId} className="m-0 border-b border-line px-4 py-3 text-md font-semibold">
        {title}
      </h2>
      <div className="p-4 text-sm">{children}</div>
      {actions && (
        <div className="flex justify-end gap-2 border-t border-line px-4 py-3">{actions}</div>
      )}
    </dialog>
  )
}
