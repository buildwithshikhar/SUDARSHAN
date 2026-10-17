import { useState } from 'react'
import { PageHeader } from '../layout/PageHeader'
import { Badge } from '../ui/Badge'
import { Button } from '../ui/Button'
import { Dialog } from '../ui/Dialog'
import { Checkbox, Input, Select } from '../ui/Field'
import { InlineAlert } from '../ui/InlineAlert'
import { Panel } from '../ui/Panel'
import { EmptyState, ErrorState, LoadingState } from '../ui/States'
import { Table } from '../ui/Table'
import { Tabs } from '../ui/Tabs'
import { Tooltip } from '../ui/Tooltip'

// Developer route, available only when the API reports demo mode. Text here is not product copy.
const rows = [
  { id: 'T-0412', range: '3 412 m', bearing: '047°', cls: 'Unknown' },
  { id: 'T-0413', range: '1 208 m', bearing: '112°', cls: 'Bird' },
  { id: 'T-0417', range: '5 960 m', bearing: '301°', cls: 'Civil' },
]

export function DevComponents() {
  const [open, setOpen] = useState(false)
  const [density, setDensity] = useState<'compact' | 'comfortable'>('compact')
  return (
    <>
      <PageHeader title="Components" crumbs={['dev']} />
      <div className="flex flex-col gap-4">
        <Panel title="Buttons and badges">
          <div className="flex flex-wrap items-center gap-3">
            <Button variant="primary">Primary</Button>
            <Button>Secondary</Button>
            <Button variant="ghost">Ghost</Button>
            <Button disabled>Disabled</Button>
            <Badge>Neutral</Badge>
            <Badge tone="accent">Accent</Badge>
            <Badge tone="warning">Warning</Badge>
            <Badge tone="hostile">Hostile</Badge>
            <Tooltip label="Describes the control it is attached to">
              <Button>With tooltip</Button>
            </Tooltip>
          </div>
        </Panel>
        <Panel title="Fields">
          <div className="grid max-w-[640px] grid-cols-2 gap-4">
            <Input label="Text" hint="Helper text" />
            <Input label="Invalid" error="Error text" defaultValue="x" />
            <Select
              label="Select"
              options={[
                { value: 'a', label: 'Option A' },
                { value: 'b', label: 'Option B' },
              ]}
            />
            <Checkbox label="Checkbox" />
          </div>
        </Panel>
        <Panel
          title="Table"
          flush
          actions={
            <Button
              variant="ghost"
              onClick={() => setDensity(density === 'compact' ? 'comfortable' : 'compact')}
            >
              {density}
            </Button>
          }
        >
          <Table
            caption="Sample tracks"
            density={density}
            rows={rows}
            rowKey={(row) => row.id}
            columns={[
              { key: 'id', header: 'Track', render: (row) => row.id, mono: true },
              {
                key: 'range',
                header: 'Range',
                render: (row) => row.range,
                mono: true,
                align: 'right',
              },
              {
                key: 'bearing',
                header: 'Bearing',
                render: (row) => row.bearing,
                mono: true,
                align: 'right',
              },
              { key: 'cls', header: 'Class', render: (row) => row.cls },
            ]}
          />
        </Panel>
        <Panel title="Tabs, alerts, dialog">
          <Tabs
            label="Sample tabs"
            tabs={[
              { id: 'a', label: 'First', panel: <p>First panel</p> },
              { id: 'b', label: 'Second', panel: <p>Second panel</p> },
            ]}
          />
          <div className="mt-3 flex flex-col gap-2">
            <InlineAlert tone="info">Information</InlineAlert>
            <InlineAlert tone="success">Success</InlineAlert>
            <InlineAlert tone="warning">Warning</InlineAlert>
            <InlineAlert tone="error">Error</InlineAlert>
          </div>
          <div className="mt-3">
            <Button onClick={() => setOpen(true)}>Open dialog</Button>
            <Dialog
              open={open}
              title="Dialog"
              onClose={() => setOpen(false)}
              actions={
                <Button variant="primary" onClick={() => setOpen(false)}>
                  Close
                </Button>
              }
            >
              Focus is trapped here; Escape closes.
            </Dialog>
          </div>
        </Panel>
        <Panel title="States">
          <div className="grid grid-cols-3 gap-4">
            <EmptyState title="Empty" description="Nothing here yet." />
            <LoadingState label="Loading" />
            <ErrorState
              title="Error"
              description="Something failed."
              retryLabel="Retry"
              onRetry={() => undefined}
            />
          </div>
        </Panel>
      </div>
    </>
  )
}
