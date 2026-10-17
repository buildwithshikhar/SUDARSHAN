import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { vi } from 'vitest'
import brand from '../../../brand.json'
import { Badge } from '../src/ui/Badge'
import { BrandMark } from '../src/ui/BrandMark'
import { Button } from '../src/ui/Button'
import { Dialog } from '../src/ui/Dialog'
import { Checkbox, Input, Select } from '../src/ui/Field'
import { InlineAlert } from '../src/ui/InlineAlert'
import { Panel } from '../src/ui/Panel'
import { Segmented } from '../src/ui/Segmented'
import { EmptyState, ErrorState, LoadingState } from '../src/ui/States'
import { Table } from '../src/ui/Table'
import { Tabs } from '../src/ui/Tabs'
import { Tooltip } from '../src/ui/Tooltip'

describe('Button', () => {
  it('defaults to type=button and fires onClick', async () => {
    const onClick = vi.fn()
    render(<Button onClick={onClick}>Go</Button>)
    const button = screen.getByRole('button', { name: 'Go' })
    expect(button).toHaveAttribute('type', 'button')
    await userEvent.click(button)
    expect(onClick).toHaveBeenCalledTimes(1)
  })

  it('does not fire when disabled', async () => {
    const onClick = vi.fn()
    render(
      <Button disabled onClick={onClick}>
        Go
      </Button>,
    )
    await userEvent.click(screen.getByRole('button'))
    expect(onClick).not.toHaveBeenCalled()
  })
})

describe('fields', () => {
  it('Input labels the control and links hint and error', () => {
    const { rerender } = render(<Input label="Email" hint="Work address" />)
    const input = screen.getByLabelText('Email')
    expect(input).toHaveAccessibleDescription('Work address')
    expect(input).not.toHaveAttribute('aria-invalid')
    rerender(<Input label="Email" hint="Work address" error="Required" />)
    expect(screen.getByLabelText('Email')).toHaveAttribute('aria-invalid', 'true')
    expect(screen.getByLabelText('Email')).toHaveAccessibleDescription('Required')
  })

  it('Select exposes its options and reports changes', async () => {
    const onChange = vi.fn()
    render(
      <Select
        label="Mode"
        options={[
          { value: 'a', label: 'Alpha' },
          { value: 'b', label: 'Beta' },
        ]}
        onChange={onChange}
      />,
    )
    await userEvent.selectOptions(screen.getByLabelText('Mode'), 'b')
    expect(onChange).toHaveBeenCalled()
    expect(screen.getByRole('option', { name: 'Beta' })).toBeInTheDocument()
  })

  it('Checkbox toggles with its label', async () => {
    render(<Checkbox label="Remember" />)
    await userEvent.click(screen.getByLabelText('Remember'))
    expect(screen.getByLabelText('Remember')).toBeChecked()
  })
})

describe('Panel', () => {
  it('is a labelled region with a heading', () => {
    render(<Panel title="Build">body</Panel>)
    expect(screen.getByRole('region', { name: 'Build' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Build', level: 2 })).toBeInTheDocument()
  })
})

describe('Table', () => {
  const columns = [
    { key: 'a', header: 'Track', render: (r: { id: string }) => r.id },
    {
      key: 'b',
      header: 'Range',
      render: () => '1',
      align: 'right' as const,
      mono: true,
    },
  ]

  it('renders a captioned table with column headers and rows', () => {
    render(
      <Table
        caption="Tracks"
        columns={columns}
        rows={[{ id: 'T1' }, { id: 'T2' }]}
        rowKey={(r) => r.id}
      />,
    )
    expect(screen.getByRole('table', { name: 'Tracks' })).toBeInTheDocument()
    expect(screen.getAllByRole('columnheader')).toHaveLength(2)
    expect(screen.getAllByRole('row')).toHaveLength(3)
  })

  it('uses 28 px rows when compact and 36 px when comfortable', () => {
    const { rerender } = render(
      <Table caption="t" columns={columns} rows={[{ id: 'T1' }]} rowKey={(r) => r.id} />,
    )
    expect(screen.getAllByRole('row')[1]).toHaveClass('h-7')
    rerender(
      <Table
        caption="t"
        density="comfortable"
        columns={columns}
        rows={[{ id: 'T1' }]}
        rowKey={(r) => r.id}
      />,
    )
    expect(screen.getAllByRole('row')[1]).toHaveClass('h-9')
  })

  it('shows the empty node when there are no rows', () => {
    render(
      <Table
        caption="t"
        columns={columns}
        rows={[]}
        rowKey={(r: { id: string }) => r.id}
        empty={<p>Nothing</p>}
      />,
    )
    expect(screen.getByText('Nothing')).toBeInTheDocument()
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
  })
})

describe('Tabs', () => {
  const tabs = [
    { id: 'a', label: 'First', panel: <p>Panel A</p> },
    { id: 'b', label: 'Second', panel: <p>Panel B</p> },
    { id: 'c', label: 'Third', panel: <p>Panel C</p> },
  ]

  it('selects with click and links tab to panel', async () => {
    render(<Tabs label="Sections" tabs={tabs} />)
    expect(screen.getByRole('tab', { name: 'First' })).toHaveAttribute('aria-selected', 'true')
    await userEvent.click(screen.getByRole('tab', { name: 'Second' }))
    expect(screen.getByRole('tabpanel')).toHaveTextContent('Panel B')
    expect(screen.getByRole('tabpanel')).toHaveAccessibleName('Second')
  })

  it('supports arrow, Home and End keys with a roving tabindex', async () => {
    render(<Tabs label="Sections" tabs={tabs} />)
    screen.getByRole('tab', { name: 'First' }).focus()
    await userEvent.keyboard('{ArrowRight}')
    expect(screen.getByRole('tab', { name: 'Second' })).toHaveFocus()
    expect(screen.getByRole('tab', { name: 'Second' })).toHaveAttribute('tabindex', '0')
    expect(screen.getByRole('tab', { name: 'First' })).toHaveAttribute('tabindex', '-1')
    await userEvent.keyboard('{End}')
    expect(screen.getByRole('tab', { name: 'Third' })).toHaveFocus()
    await userEvent.keyboard('{ArrowRight}')
    expect(screen.getByRole('tab', { name: 'First' })).toHaveFocus()
    await userEvent.keyboard('{ArrowLeft}')
    expect(screen.getByRole('tab', { name: 'Third' })).toHaveFocus()
    await userEvent.keyboard('{Home}')
    expect(screen.getByRole('tab', { name: 'First' })).toHaveFocus()
    expect(screen.getByRole('tabpanel')).toHaveTextContent('Panel A')
  })
})

describe('Dialog', () => {
  function Harness({ onClose }: { onClose: () => void }) {
    const [open, setOpen] = useState(false)
    return (
      <>
        <button onClick={() => setOpen(true)}>Open</button>
        <Dialog
          open={open}
          title="Confirm"
          onClose={() => {
            setOpen(false)
            onClose()
          }}
          actions={<button onClick={() => setOpen(false)}>Done</button>}
        >
          Body text
        </Dialog>
      </>
    )
  }

  it('opens as a labelled modal and closes through its actions', async () => {
    const onClose = vi.fn()
    render(<Harness onClose={onClose} />)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    await userEvent.click(screen.getByText('Open'))
    expect(screen.getByRole('dialog', { name: 'Confirm' })).toBeInTheDocument()
    await userEvent.click(screen.getByText('Done'))
    expect(onClose).toHaveBeenCalledTimes(1)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })
})

describe('Tooltip', () => {
  it('describes its trigger on focus and hides on blur and Escape', async () => {
    render(
      <Tooltip label="Explains the action">
        <button>Trigger</button>
      </Tooltip>,
    )
    const trigger = screen.getByRole('button', { name: 'Trigger' })
    expect(trigger).toHaveAccessibleDescription('Explains the action')
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument()
    await userEvent.tab()
    expect(screen.getByRole('tooltip')).toBeVisible()
    await userEvent.keyboard('{Escape}')
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument()
    fireEvent.mouseEnter(trigger.parentElement as HTMLElement)
    expect(screen.getByRole('tooltip')).toBeVisible()
    fireEvent.mouseLeave(trigger.parentElement as HTMLElement)
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument()
  })
})

describe('alerts, badges and states', () => {
  it('InlineAlert uses alert for errors and status for information', () => {
    const { rerender } = render(<InlineAlert tone="error">Broken</InlineAlert>)
    expect(screen.getByRole('alert')).toHaveTextContent('Broken')
    rerender(<InlineAlert tone="info">FYI</InlineAlert>)
    expect(screen.getByRole('status')).toHaveTextContent('FYI')
  })

  it('Badge carries its meaning in text', () => {
    render(<Badge tone="hostile">Hostile</Badge>)
    expect(screen.getByText('Hostile')).toBeInTheDocument()
  })

  it('EmptyState, LoadingState and ErrorState render their messages', async () => {
    const onRetry = vi.fn()
    render(
      <>
        <EmptyState title="Nothing yet" description="Come back later" />
        <LoadingState label="Loading data" />
        <ErrorState
          title="Failed"
          description="Try again"
          retryLabel="Retry"
          onRetry={onRetry}
          offline
        />
      </>,
    )
    expect(screen.getByText('Nothing yet')).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent('Loading data')
    expect(screen.getByRole('alert')).toHaveTextContent('Failed')
    await userEvent.click(screen.getByRole('button', { name: 'Retry' }))
    expect(onRetry).toHaveBeenCalled()
  })
})

describe('Segmented', () => {
  it('marks the selected option and reports changes', async () => {
    const onChange = vi.fn()
    render(
      <Segmented
        label="Theme"
        value="dark"
        options={[
          { value: 'dark', label: 'Dark' },
          { value: 'light', label: 'Light' },
        ]}
        onChange={onChange}
      />,
    )
    expect(screen.getByRole('group', { name: 'Theme' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Dark' })).toHaveAttribute('aria-pressed', 'true')
    await userEvent.click(screen.getByRole('button', { name: 'Light' }))
    expect(onChange).toHaveBeenCalledWith('light')
  })
})

describe('BrandMark', () => {
  it('takes its monogram and name from brand.json', () => {
    render(<BrandMark />)
    const mark = screen.getByRole('img', { name: brand.productName })
    expect(mark).toHaveTextContent(brand.productName.charAt(0).toUpperCase())
  })
})
