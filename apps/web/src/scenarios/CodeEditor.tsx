import { ErrorFilled, WarningFilled } from '@carbon/icons-react'
import { forwardRef, useImperativeHandle, useMemo, useRef, type ChangeEvent } from 'react'

export const LINE_HEIGHT = 20
const PAD = 8

export interface CodeEditorHandle {
  /** Focus the editor, put the caret at (line, column) and select the rest of the line. */
  jumpTo(line: number, column: number): void
}

interface Props {
  value: string
  onChange: (value: string) => void
  /** Worst severity per 1-based line, drawn in the gutter next to the line number. */
  markers: ReadonlyMap<number, 'error' | 'warning'>
  label: string
  describedBy?: string
  onCaret?: (line: number, column: number) => void
  className?: string
}

/** 1-based line and column of an offset in `text`. */
export function positionOf(text: string, offset: number): { line: number; column: number } {
  const before = text.slice(0, offset)
  const line = before.split('\n').length
  return { line, column: offset - (before.lastIndexOf('\n') + 1) + 1 }
}

/**
 * A plain text area with a line-number gutter. No dependency: the gutter is a second column of
 * numbers that follows the text area's scroll. Tab leaves the field (it does not insert a tab),
 * so the editor is never a keyboard trap.
 */
export const CodeEditor = forwardRef<CodeEditorHandle, Props>(function CodeEditor(
  { value, onChange, markers, label, describedBy, onCaret, className = '' },
  ref,
) {
  const area = useRef<HTMLTextAreaElement>(null)
  const gutter = useRef<HTMLDivElement>(null)
  const count = useMemo(() => value.split('\n').length, [value])

  const report = () => {
    const el = area.current
    if (!el || !onCaret) return
    const { line, column } = positionOf(el.value, el.selectionStart)
    onCaret(line, column)
  }

  useImperativeHandle(ref, () => ({
    jumpTo(line, column) {
      const el = area.current
      if (!el) return
      const rows = el.value.split('\n')
      const target = Math.min(Math.max(line, 1), rows.length)
      let offset = 0
      for (let i = 0; i < target - 1; i++) offset += (rows[i] ?? '').length + 1
      const length = (rows[target - 1] ?? '').length
      const start = offset + Math.min(Math.max(column - 1, 0), length)
      el.focus()
      el.setSelectionRange(start, offset + length, 'backward')
      el.scrollTop = Math.max(0, (target - 1) * LINE_HEIGHT - el.clientHeight / 2)
      if (gutter.current) gutter.current.scrollTop = el.scrollTop
      onCaret?.(target, start - offset + 1)
    },
  }))

  return (
    <div className={`flex min-h-0 border border-line bg-bg ${className}`}>
      <div
        ref={gutter}
        aria-hidden="true"
        data-testid="gutter"
        className="num w-12 shrink-0 select-none overflow-hidden border-r border-line bg-surface-1 text-xs text-ink-2"
        style={{ paddingTop: PAD, lineHeight: `${LINE_HEIGHT}px` }}
      >
        {Array.from({ length: count }, (_, i) => {
          const marker = markers.get(i + 1)
          return (
            <div
              key={i}
              data-line={i + 1}
              data-marker={marker}
              className="flex items-center justify-end gap-1 pr-2"
              style={{ height: LINE_HEIGHT }}
            >
              {marker === 'error' && <ErrorFilled size={12} className="text-track-hostile" />}
              {marker === 'warning' && <WarningFilled size={12} className="text-signal" />}
              {i + 1}
            </div>
          )
        })}
      </div>
      <textarea
        ref={area}
        value={value}
        aria-label={label}
        aria-describedby={describedBy}
        wrap="off"
        spellCheck={false}
        autoCapitalize="off"
        autoCorrect="off"
        autoComplete="off"
        onChange={(e: ChangeEvent<HTMLTextAreaElement>) => {
          onChange(e.target.value)
          report()
        }}
        onScroll={(e) => {
          if (gutter.current) gutter.current.scrollTop = e.currentTarget.scrollTop
        }}
        onSelect={report}
        onKeyUp={report}
        onClick={report}
        className="num min-w-0 flex-1 resize-none overflow-auto whitespace-pre border-0 bg-transparent px-2 text-sm text-ink"
        style={{ lineHeight: `${LINE_HEIGHT}px`, paddingTop: PAD, paddingBottom: PAD, tabSize: 2 }}
      />
    </div>
  )
})
