interface Option<V extends string> {
  value: V
  label: string
  lang?: string
}

interface Props<V extends string> {
  label: string
  options: Option<V>[]
  value: V
  onChange: (value: V) => void
}

/** A small group of mutually exclusive toggle buttons (language, theme). */
export function Segmented<V extends string>({ label, options, value, onChange }: Props<V>) {
  return (
    <div role="group" aria-label={label} className="flex">
      {options.map((option, index) => (
        <button
          key={option.value}
          type="button"
          className={`seg rounded-none ${index > 0 ? '-ml-px' : ''}`}
          aria-pressed={value === option.value}
          lang={option.lang}
          onClick={() => onChange(option.value)}
        >
          {option.label}
        </button>
      ))}
    </div>
  )
}
