import type { ReactNode } from 'react'

export interface Column<Row> {
  key: string
  header: string
  render: (row: Row) => ReactNode
  align?: 'left' | 'right'
  mono?: boolean
  /** Extra classes for the column's cells and header (width, wrapping). */
  className?: string
}

interface Props<Row> {
  caption: string
  columns: Column<Row>[]
  rows: Row[]
  rowKey: (row: Row) => string
  density?: 'compact' | 'comfortable'
  empty?: ReactNode
  /** Tighter cell padding (8 px instead of 12 px) for instrument panels. */
  dense?: boolean
  /** Key of the selected row: marked with a 2 px accent bar and a raised background. */
  selectedKey?: string | null // undefined: selection is not used
  onRowClick?: (row: Row) => void
}

/** Compact rows are 28 px, comfortable rows 36 px. */
export function Table<Row>({
  caption,
  columns,
  rows,
  rowKey,
  density = 'compact',
  empty,
  dense = false,
  selectedKey,
  onRowClick,
}: Props<Row>) {
  const height = density === 'compact' ? 'h-7' : 'h-9'
  const pad = dense ? 'px-2' : 'px-3'
  const bar = selectedKey !== undefined
  if (rows.length === 0 && empty) return <>{empty}</>
  return (
    <table className="w-full border-collapse text-left text-sm">
      <caption className="sr-only">{caption}</caption>
      <thead>
        <tr className="border-b border-line">
          {columns.map((column, index) => (
            <th
              key={column.key}
              scope="col"
              className={`h-7 ${pad} text-xs font-medium text-ink-2 ${bar && index === 0 ? 'border-l-2 border-transparent' : ''} ${column.align === 'right' ? 'text-right' : ''} ${column.className ?? ''}`}
            >
              {column.header}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => {
          const key = rowKey(row)
          const selected = selectedKey === key
          return (
            <tr
              key={key}
              data-selected={selected ? 'true' : undefined}
              onClick={onRowClick ? () => onRowClick(row) : undefined}
              className={`${height} border-b border-line last:border-b-0 ${selected ? 'bg-surface-2' : ''} ${onRowClick ? 'cursor-pointer' : ''}`}
            >
              {columns.map((column, index) => (
                <td
                  key={column.key}
                  className={`${pad} ${bar && index === 0 ? `border-l-2 ${selected ? 'border-accent' : 'border-transparent'}` : ''} ${column.mono ? 'num' : ''} ${column.align === 'right' ? 'text-right' : ''} ${column.className ?? ''}`}
                >
                  {column.render(row)}
                </td>
              ))}
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}
