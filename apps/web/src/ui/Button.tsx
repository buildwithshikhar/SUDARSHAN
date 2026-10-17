import type { ButtonHTMLAttributes } from 'react'

type Variant = 'primary' | 'secondary' | 'ghost'

const variants: Record<Variant, string> = {
  primary: 'border-accent bg-accent text-accent-on hover:opacity-90',
  secondary: 'border-line bg-surface-1 text-ink hover:border-accent',
  ghost: 'border-transparent bg-transparent text-ink-2 hover:text-ink',
}

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
}

export function Button({ variant = 'secondary', className = '', type = 'button', ...rest }: Props) {
  return (
    <button
      type={type}
      className={`inline-flex h-7 items-center justify-center gap-2 border px-3 text-sm font-medium disabled:cursor-not-allowed disabled:opacity-50 ${variants[variant]} ${className}`}
      style={{ transition: 'border-color 140ms ease-out, opacity 140ms ease-out' }}
      {...rest}
    />
  )
}
