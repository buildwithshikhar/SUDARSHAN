import { cloneElement, useId, useState, type ReactElement } from 'react'

interface Props {
  label: string
  children: ReactElement<{ 'aria-describedby'?: string }>
}

/** Describes a focusable trigger. Shown on hover and focus, dismissed with Escape. */
export function Tooltip({ label, children }: Props) {
  const id = useId()
  const [visible, setVisible] = useState(false)
  return (
    <span
      className="relative inline-flex"
      onMouseEnter={() => setVisible(true)}
      onMouseLeave={() => setVisible(false)}
      onFocus={() => setVisible(true)}
      onBlur={() => setVisible(false)}
      onKeyDown={(event) => event.key === 'Escape' && setVisible(false)}
    >
      {cloneElement(children, { 'aria-describedby': id })}
      <span
        role="tooltip"
        id={id}
        hidden={!visible}
        className="absolute left-0 top-full z-10 mt-1 w-max max-w-[260px] border border-line bg-surface-2 px-2 py-1 text-xs text-ink"
      >
        {label}
      </span>
    </span>
  )
}
