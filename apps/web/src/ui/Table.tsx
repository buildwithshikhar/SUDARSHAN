import type { ReactNode } from 'react'

export interface Column<Row> {
  key: string
  header: string
  render: (row: Row) => ReactNode
  align?: 'left' | 'right'
  mono?: boolean
}

interface Props<Row> {
  caption: string
  columns: Column<Row>[]
  rows: Row[]
  rowKey: (row: Row) => string
  density?: 'compact' | 'comfortable'
  empty?: ReactNode
}

/** Compact rows are 28 px, comfortable rows 36 px. */
export function Table<Row>({
  caption,
  columns,
  rows,
  rowKey,
  density = 'compact',
  empty,
}: Props<Row>) {
  const height = density === 'compact' ? 'h-7' : 'h-9'
  if (rows.length === 0 && empty) return <>{empty}</>
  return (
    <table className="w-full border-collapse text-left text-sm">
      <caption className="sr-only">{caption}</caption>
      <thead>
        <tr className="border-b border-line">
          {columns.map((column) => (
            <th
              key={column.key}
              scope="col"
              className={`h-7 px-3 text-xs font-medium text-ink-2 ${column.align === 'right' ? 'text-right' : ''}`}
            >
              {column.header}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={rowKey(row)} className={`${height} border-b border-line last:border-b-0`}>
            {columns.map((column) => (
              <td
                key={column.key}
                className={`px-3 ${column.mono ? 'num' : ''} ${column.align === 'right' ? 'text-right' : ''}`}
              >
                {column.render(row)}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  )
}
