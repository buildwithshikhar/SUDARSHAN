import { useId, useRef, useState, type KeyboardEvent, type ReactNode } from 'react'

export interface TabItem {
  id: string
  label: string
  panel: ReactNode
}

export function Tabs({ label, tabs }: { label: string; tabs: TabItem[] }) {
  const base = useId()
  const [selected, setSelected] = useState(tabs[0]?.id ?? '')
  const buttons = useRef<Record<string, HTMLButtonElement | null>>({})

  const move = (event: KeyboardEvent, index: number) => {
    const last = tabs.length - 1
    const target =
      event.key === 'ArrowRight'
        ? (index + 1) % tabs.length
        : event.key === 'ArrowLeft'
          ? (index - 1 + tabs.length) % tabs.length
          : event.key === 'Home'
            ? 0
            : event.key === 'End'
              ? last
              : -1
    const next = tabs[target]
    if (!next) return
    event.preventDefault()
    setSelected(next.id)
    buttons.current[next.id]?.focus()
  }

  return (
    <div>
      <div role="tablist" aria-label={label} className="flex border-b border-line">
        {tabs.map((tab, index) => {
          const active = tab.id === selected
          return (
            <button
              key={tab.id}
              ref={(node) => {
                buttons.current[tab.id] = node
              }}
              role="tab"
              type="button"
              id={`${base}-tab-${tab.id}`}
              aria-selected={active}
              aria-controls={`${base}-panel-${tab.id}`}
              tabIndex={active ? 0 : -1}
              onClick={() => setSelected(tab.id)}
              onKeyDown={(event) => move(event, index)}
              className={`-mb-px h-8 border-b-2 px-3 text-sm ${active ? 'border-accent text-ink' : 'border-transparent text-ink-2 hover:text-ink'}`}
            >
              {tab.label}
            </button>
          )
        })}
      </div>
      {tabs.map((tab) => (
        <div
          key={tab.id}
          role="tabpanel"
          id={`${base}-panel-${tab.id}`}
          aria-labelledby={`${base}-tab-${tab.id}`}
          hidden={tab.id !== selected}
          tabIndex={0}
          className="pt-3"
        >
          {tab.id === selected ? tab.panel : null}
        </div>
      ))}
    </div>
  )
}
