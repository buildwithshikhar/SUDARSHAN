import { useId, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes } from 'react'

interface FieldShellProps {
  id: string
  label: string
  hint?: string
  error?: string
  children: ReactNode
}

function FieldShell({ id, label, hint, error, children }: FieldShellProps) {
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="text-sm text-ink-2">
        {label}
      </label>
      {children}
      {hint && !error && (
        <p id={`${id}-hint`} className="m-0 text-xs text-ink-2">
          {hint}
        </p>
      )}
      {error && (
        <p id={`${id}-error`} className="m-0 text-xs text-track-hostile">
          {error}
        </p>
      )}
    </div>
  )
}

const control =
  'h-7 w-full border border-line bg-bg px-2 text-sm text-ink placeholder:text-ink-2 focus:border-accent aria-[invalid=true]:border-track-hostile'

interface InputProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'id'> {
  label: string
  hint?: string
  error?: string
}

export function Input({ label, hint, error, className = '', ...rest }: InputProps) {
  const id = useId()
  const described = error ? `${id}-error` : hint ? `${id}-hint` : undefined
  return (
    <FieldShell id={id} label={label} hint={hint} error={error}>
      <input
        id={id}
        className={`${control} ${className}`}
        aria-invalid={error ? true : undefined}
        aria-describedby={described}
        {...rest}
      />
    </FieldShell>
  )
}

interface SelectProps extends Omit<SelectHTMLAttributes<HTMLSelectElement>, 'id'> {
  label: string
  hint?: string
  error?: string
  options: { value: string; label: string; lang?: string }[]
}

export function Select({ label, hint, error, options, className = '', ...rest }: SelectProps) {
  const id = useId()
  const described = error ? `${id}-error` : hint ? `${id}-hint` : undefined
  return (
    <FieldShell id={id} label={label} hint={hint} error={error}>
      <select
        id={id}
        className={`${control} ${className}`}
        aria-invalid={error ? true : undefined}
        aria-describedby={described}
        {...rest}
      >
        {options.map((option) => (
          <option key={option.value} value={option.value} lang={option.lang}>
            {option.label}
          </option>
        ))}
      </select>
    </FieldShell>
  )
}

interface CheckboxProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'id' | 'type'> {
  label: string
}

export function Checkbox({ label, className = '', ...rest }: CheckboxProps) {
  const id = useId()
  return (
    <div className="flex items-center gap-2">
      <input
        id={id}
        type="checkbox"
        className={`h-4 w-4 ${className}`}
        style={{ accentColor: 'var(--accent)' }}
        {...rest}
      />
      <label htmlFor={id} className="text-sm">
        {label}
      </label>
    </div>
  )
}
