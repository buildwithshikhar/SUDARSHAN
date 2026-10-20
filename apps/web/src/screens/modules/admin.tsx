import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  AUDIT,
  BACKUPS,
  COHORTS,
  PACKS,
  PERFORMANCE,
  PROVENANCE,
  SERVICES,
  SIGNING_KEY_ID,
  SOURCES,
  STORAGE,
  TRAINEES,
  UNITS,
  USERS,
  at,
  verifyChain,
  type AccountRole,
  type AuditEntry,
  type PackRow,
  type UserRow,
} from '../../mock'
import { Badge } from '../../ui/Badge'
import { EVALUATION_MODE } from '../../lib/evaluation'
import { Button } from '../../ui/Button'
import { Dialog } from '../../ui/Dialog'
import { Checkbox, Input, Select } from '../../ui/Field'
import { InlineAlert } from '../../ui/InlineAlert'
import { Panel } from '../../ui/Panel'
import { Segmented } from '../../ui/Segmented'
import { Table, type Column } from '../../ui/Table'
import { shortTime } from './format'
import { Bar, Facts, Grid, LineChart, Mark, ModulePage } from './kit'

// -- Users and roles ---------------------------------------------------------------------------

function UserList({
  rows,
  selected,
  onSelect,
}: {
  rows: UserRow[]
  selected: string
  onSelect: (id: string) => void
}) {
  const { t } = useTranslation()
  const [role, setRole] = useState<'all' | AccountRole>('all')
  const [query, setQuery] = useState('')
  const shown = rows.filter(
    (u) =>
      (role === 'all' || u.role === role) &&
      `${u.name} ${u.email}`.toLowerCase().includes(query.toLowerCase()),
  )
  const columns: Column<UserRow>[] = [
    { key: 'n', header: t('m.users.name'), render: (u) => u.name },
    { key: 'e', header: t('m.users.email'), mono: true, render: (u) => u.email },
    { key: 'r', header: t('m.users.role'), render: (u) => t(`roles.${u.role}`) },
    {
      key: 'u',
      header: t('m.cohorts.unit'),
      render: (u) => UNITS.find((x) => x.id === u.unitId)?.name ?? '',
    },
    {
      key: 'l',
      header: t('m.users.lastSignIn'),
      mono: true,
      render: (u) => shortTime(u.lastSignIn),
    },
    {
      key: 's',
      header: t('m.users.status'),
      render: (u) => (
        <Mark ok={u.active} label={t(u.active ? 'm.users.active' : 'm.users.deactivated')} />
      ),
    },
  ]
  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end gap-4">
        <div className="w-[240px]">
          <Select
            label={t('m.users.role')}
            value={role}
            options={[
              { value: 'all', label: t('m.common.all') },
              { value: 'trainee', label: t('roles.trainee') },
              { value: 'instructor', label: t('roles.instructor') },
              { value: 'admin', label: t('roles.admin') },
            ]}
            onChange={(e) => setRole(e.target.value as 'all' | AccountRole)}
          />
        </div>
        <div className="w-[260px]">
          <Input
            label={t('m.common.search')}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
      </div>
      <Panel title={t('m.users.list', { count: shown.length })} flush>
        <Table
          caption={t('m.users.list', { count: shown.length })}
          columns={columns}
          rows={shown}
          rowKey={(u) => u.id}
          selectedKey={selected}
          onRowClick={(u) => onSelect(u.id)}
        />
      </Panel>
    </div>
  )
}

function UserDetail({
  users,
  id,
  onPick,
  onChange,
}: {
  users: UserRow[]
  id: string
  onPick: (id: string) => void
  onChange: (u: UserRow) => void
}) {
  const { t } = useTranslation()
  const user = users.find((u) => u.id === id) ?? at(users, 0)
  const [confirm, setConfirm] = useState(false)
  const [done, setDone] = useState<string | null>(null)
  return (
    <div className="flex flex-col gap-4">
      <div className="max-w-[320px]">
        <Select
          label={t('m.users.name')}
          value={user.id}
          options={users.map((u) => ({ value: u.id, label: u.name }))}
          onChange={(e) => {
            onPick(e.target.value)
            setDone(null)
          }}
        />
      </div>
      <Grid cols={2}>
        <Panel title={t('m.users.account')}>
          <Facts
            rows={[
              { label: t('m.users.name'), value: user.name },
              { label: t('m.users.email'), value: user.email },
              {
                label: t('m.cohorts.unit'),
                value: UNITS.find((x) => x.id === user.unitId)?.name ?? '',
              },
              { label: t('m.users.lastSignIn'), value: shortTime(user.lastSignIn) },
              {
                label: t('m.users.status'),
                value: t(user.active ? 'm.users.active' : 'm.users.deactivated'),
              },
            ]}
          />
        </Panel>
        <Panel title={t('m.users.roles')}>
          <div className="flex max-w-[320px] flex-col gap-4">
            <Select
              label={t('m.users.role')}
              value={user.role}
              options={(['trainee', 'instructor', 'admin'] as const).map((r) => ({
                value: r,
                label: t(`roles.${r}`),
              }))}
              disabled={EVALUATION_MODE}
              onChange={(e) => {
                onChange({ ...user, role: e.target.value as AccountRole })
                setDone(t('m.users.roleSaved'))
              }}
            />
            <Checkbox
              label={t('m.users.active')}
              checked={user.active}
              disabled={EVALUATION_MODE}
              onChange={(e) => {
                onChange({ ...user, active: e.target.checked })
                setDone(t('m.users.statusSaved'))
              }}
            />
            <div>
              <Button disabled={EVALUATION_MODE} onClick={() => setConfirm(true)}>
                {t('m.users.reset')}
              </Button>
            </div>
            {EVALUATION_MODE && <InlineAlert>{t('m.evaluation.disabled')}</InlineAlert>}
            {done && <InlineAlert tone="success">{done}</InlineAlert>}
          </div>
        </Panel>
      </Grid>
      <Dialog
        open={confirm}
        title={t('m.users.resetTitle', { name: user.name })}
        onClose={() => setConfirm(false)}
      >
        <p className="m-0 mb-4 text-sm">{t('m.users.resetBody')}</p>
        <div className="flex justify-end gap-2">
          <Button onClick={() => setConfirm(false)}>{t('m.common.cancel')}</Button>
          <Button
            variant="primary"
            onClick={() => {
              setConfirm(false)
              setDone(t('m.users.resetDone'))
            }}
          >
            {t('m.users.resetConfirm')}
          </Button>
        </div>
      </Dialog>
    </div>
  )
}

export function UsersAndRoles() {
  const { t } = useTranslation()
  const [users, setUsers] = useState(USERS)
  const [id, setId] = useState(at(USERS, 0).id)
  return (
    <ModulePage
      group="administration"
      module="users-and-roles"
      tabs={[
        {
          id: 'list',
          label: t('m.users.listTab'),
          panel: <UserList rows={users} selected={id} onSelect={setId} />,
        },
        {
          id: 'detail',
          label: t('m.users.detail'),
          panel: (
            <UserDetail
              users={users}
              id={id}
              onPick={setId}
              onChange={(u) => setUsers((all) => all.map((x) => (x.id === u.id ? u : x)))}
            />
          ),
        },
      ]}
    />
  )
}

// -- Organisation ------------------------------------------------------------------------------

export function Organisation() {
  const { t } = useTranslation()
  const [id, setId] = useState(at(UNITS, 0).id)
  const unit = UNITS.find((u) => u.id === id) ?? at(UNITS, 0)
  const cohorts = COHORTS.filter((c) => c.unitId === unit.id)
  return (
    <ModulePage
      group="administration"
      module="organisation"
      tabs={[
        {
          id: 'units',
          label: t('m.org.units'),
          panel: (
            <Grid cols={2}>
              <Panel title={t('m.org.units')} flush>
                <Table
                  caption={t('m.org.units')}
                  columns={[
                    {
                      key: 'n',
                      header: t('m.org.unit'),
                      render: (u: (typeof UNITS)[number]) => u.name,
                    },
                    {
                      key: 'l',
                      header: t('m.org.location'),
                      render: (u: (typeof UNITS)[number]) => u.location,
                    },
                    {
                      key: 'm',
                      header: t('m.cohorts.members'),
                      align: 'right',
                      mono: true,
                      render: (u: (typeof UNITS)[number]) => u.members,
                    },
                  ]}
                  rows={UNITS}
                  rowKey={(u) => u.id}
                  selectedKey={id}
                  onRowClick={(u) => setId(u.id)}
                />
              </Panel>
              <Panel title={t('m.org.detail', { name: unit.name })}>
                <Facts
                  rows={[
                    { label: t('m.org.location'), value: unit.location },
                    { label: t('m.cohorts.members'), value: unit.members },
                    {
                      label: t('m.org.users'),
                      value: USERS.filter((u) => u.unitId === unit.id).length,
                    },
                    {
                      label: t('m.org.cohorts'),
                      value: cohorts.length ? cohorts.map((c) => c.name).join(', ') : '—',
                    },
                    {
                      label: t('m.org.trainees'),
                      value: TRAINEES.filter((x) => x.unitId === unit.id).length,
                    },
                  ]}
                />
              </Panel>
            </Grid>
          ),
        },
      ]}
    />
  )
}

// -- Packs -------------------------------------------------------------------------------------

export function Packs() {
  const { t } = useTranslation()
  const [kind, setKind] = useState<'all' | PackRow['kind']>('all')
  const [note, setNote] = useState<string | null>(null)
  const rows = PACKS.filter((p) => kind === 'all' || p.kind === kind)
  return (
    <ModulePage
      group="administration"
      module="packs"
      tabs={[
        {
          id: 'manager',
          label: t('m.packs.manager'),
          panel: (
            <div className="flex flex-col gap-4">
              <div className="flex flex-wrap items-end justify-between gap-4">
                <Segmented
                  label={t('m.packs.kind')}
                  value={kind}
                  options={[
                    { value: 'all', label: t('m.common.all') },
                    { value: 'terrain', label: t('m.packs.terrain') },
                    { value: 'sensor', label: t('m.packs.sensor') },
                    { value: 'scenario', label: t('m.packs.scenario') },
                    { value: 'rule', label: t('m.packs.rule') },
                  ]}
                  onChange={setKind}
                />
                <div className="flex gap-2">
                  <Button onClick={() => setNote(t('m.packs.importDone'))}>
                    {t('m.packs.import')}
                  </Button>
                  <Button onClick={() => setNote(t('m.packs.exportDone'))}>
                    {t('m.packs.export')}
                  </Button>
                </div>
              </div>
              {note && <InlineAlert tone="success">{note}</InlineAlert>}
              <Panel title={t('m.packs.list', { count: rows.length })} flush>
                <Table
                  caption={t('m.packs.list', { count: rows.length })}
                  columns={[
                    { key: 'n', header: t('m.packs.name'), render: (p: PackRow) => p.name },
                    {
                      key: 'k',
                      header: t('m.packs.kind'),
                      render: (p: PackRow) => t(`m.packs.${p.kind}`),
                    },
                    {
                      key: 'v',
                      header: t('m.common.version'),
                      mono: true,
                      render: (p: PackRow) => p.version,
                    },
                    {
                      key: 'e',
                      header: t('m.packs.entries'),
                      align: 'right',
                      mono: true,
                      render: (p: PackRow) => p.entries,
                    },
                    {
                      key: 's',
                      header: t('m.packs.size'),
                      align: 'right',
                      mono: true,
                      render: (p: PackRow) => p.size,
                    },
                    {
                      key: 'u',
                      header: t('m.common.updated'),
                      mono: true,
                      render: (p: PackRow) => p.updated,
                    },
                    { key: 'l', header: t('m.packs.licence'), render: (p: PackRow) => p.licence },
                  ]}
                  rows={rows}
                  rowKey={(p) => p.id}
                />
              </Panel>
            </div>
          ),
        },
      ]}
    />
  )
}

// -- Data register -----------------------------------------------------------------------------

export function DataRegister() {
  const { t } = useTranslation()
  const [id, setId] = useState('D14')
  const src = SOURCES.find((s) => s.id === id) ?? at(SOURCES, 0)
  return (
    <ModulePage
      group="trust"
      module="data-register"
      tabs={[
        {
          id: 'sources',
          label: t('m.register.sources'),
          panel: (
            <Grid cols={2}>
              <Panel title={t('m.register.sources')} flush>
                <Table
                  caption={t('m.register.sources')}
                  columns={[
                    {
                      key: 'i',
                      header: 'ID',
                      mono: true,
                      render: (s: (typeof SOURCES)[number]) => s.id,
                    },
                    {
                      key: 'n',
                      header: t('m.register.dataset'),
                      render: (s: (typeof SOURCES)[number]) => s.name,
                    },
                    {
                      key: 'l',
                      header: t('m.packs.licence'),
                      render: (s: (typeof SOURCES)[number]) => s.licence,
                    },
                    {
                      key: 'p',
                      header: t('m.register.parameters'),
                      align: 'right',
                      mono: true,
                      render: (s: (typeof SOURCES)[number]) => s.parameters,
                    },
                  ]}
                  rows={SOURCES}
                  rowKey={(s) => s.id}
                  selectedKey={id}
                  onRowClick={(s) => setId(s.id)}
                />
              </Panel>
              <Panel title={t('m.register.detail', { id: src.id })}>
                <Facts
                  rows={[
                    { label: t('m.register.dataset'), value: src.name },
                    { label: t('m.register.modality'), value: src.modality },
                    { label: t('m.packs.licence'), value: src.licence },
                    { label: t('m.register.use'), value: src.use },
                    {
                      label: t('m.register.shipped'),
                      value: t(src.ships ? 'm.common.yes' : 'm.register.calibrationOnly'),
                    },
                    { label: t('m.register.parameters'), value: src.parameters },
                  ]}
                />
              </Panel>
            </Grid>
          ),
        },
        {
          id: 'provenance',
          label: t('m.register.provenance'),
          panel: (
            <Panel title={t('m.register.provenance')} flush>
              <Table
                caption={t('m.register.provenance')}
                columns={[
                  {
                    key: 'p',
                    header: t('m.register.parameter'),
                    mono: true,
                    render: (r: (typeof PROVENANCE)[number]) => r.parameter,
                  },
                  {
                    key: 's',
                    header: t('m.register.source'),
                    mono: true,
                    render: (r: (typeof PROVENANCE)[number]) => r.source,
                  },
                  {
                    key: 'v',
                    header: t('m.register.checked'),
                    render: (r: (typeof PROVENANCE)[number]) => (
                      <Mark
                        ok={r.verified}
                        label={t(r.verified ? 'm.register.verified' : 'm.register.toCheck')}
                      />
                    ),
                  },
                ]}
                rows={PROVENANCE}
                rowKey={(r) => r.parameter}
              />
            </Panel>
          ),
        },
      ]}
    />
  )
}

// -- Records -----------------------------------------------------------------------------------

function AuditLog({ entries, intact }: { entries: AuditEntry[]; intact: boolean }) {
  const { t } = useTranslation()
  const [action, setAction] = useState('all')
  const actions = [...new Set(AUDIT.map((e) => e.action))]
  const shown = [...entries].reverse().filter((e) => action === 'all' || e.action === action)
  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="w-[260px]">
          <Select
            label={t('m.audit.action')}
            value={action}
            options={[
              { value: 'all', label: t('m.common.all') },
              ...actions.map((a) => ({ value: a, label: a })),
            ]}
            onChange={(e) => setAction(e.target.value)}
          />
        </div>
        <Mark ok={intact} label={t(intact ? 'm.audit.intact' : 'm.audit.broken')} />
      </div>
      <Panel title={t('m.audit.log', { count: shown.length })} flush>
        <Table
          caption={t('m.audit.log', { count: shown.length })}
          columns={[
            { key: 'q', header: '#', mono: true, render: (e: AuditEntry) => e.seq },
            {
              key: 'a',
              header: t('m.common.time'),
              mono: true,
              render: (e: AuditEntry) => shortTime(e.at),
            },
            { key: 'u', header: t('m.audit.actor'), render: (e: AuditEntry) => e.actor },
            {
              key: 'c',
              header: t('m.audit.action'),
              mono: true,
              render: (e: AuditEntry) => e.action,
            },
            { key: 't', header: t('m.audit.target'), render: (e: AuditEntry) => e.target },
            {
              key: 'r',
              header: t('m.audit.result'),
              render: (e: AuditEntry) => (
                <Mark ok={e.result === 'ok'} label={t(`m.audit.${e.result}`)} />
              ),
            },
            {
              key: 'h',
              header: t('m.audit.hash'),
              mono: true,
              render: (e: AuditEntry) => e.hash.slice(0, 8),
            },
          ]}
          rows={shown}
          rowKey={(e) => String(e.seq)}
        />
      </Panel>
    </div>
  )
}

function RecordVerification({ entries }: { entries: AuditEntry[] }) {
  const { t } = useTranslation()
  const [result, setResult] = useState<ReturnType<typeof verifyChain> | null>(null)
  const [sig, setSig] = useState<boolean | null>(null)
  const sessions = TRAINEES.slice(0, 6).map((x) => at(x.sessions, 3))
  const [id, setId] = useState(at(sessions, 0).id)
  const head = at(entries, entries.length - 1)
  return (
    <Grid cols={2}>
      <Panel title={t('m.verify.record')}>
        <div className="flex max-w-[420px] flex-col gap-4">
          <Select
            label={t('m.verify.session')}
            value={id}
            options={sessions.map((s) => ({ value: s.id, label: `${s.id} · ${s.date}` }))}
            onChange={(e) => {
              setId(e.target.value)
              setResult(null)
              setSig(null)
            }}
          />
          <Facts
            rows={[
              { label: t('m.verify.events'), value: entries.length },
              { label: t('m.verify.head'), value: head.hash },
              { label: t('m.verify.key'), value: SIGNING_KEY_ID },
              { label: t('m.verify.algorithm'), value: 'Ed25519' },
            ]}
          />
          <div className="flex gap-2">
            <Button variant="primary" onClick={() => setResult(verifyChain(entries))}>
              {t('m.verify.checkChain')}
            </Button>
            <Button onClick={() => setSig(true)}>{t('m.verify.checkSignature')}</Button>
          </div>
        </div>
      </Panel>
      <Panel title={t('m.verify.results')}>
        <ul className="m-0 flex list-none flex-col gap-3 p-0 text-sm">
          <li>
            <p className="micro-label m-0 mb-1">{t('m.verify.chain')}</p>
            {result === null ? (
              <span className="text-ink-2">{t('m.verify.notRun')}</span>
            ) : (
              <Mark
                ok={result.ok}
                label={t(result.ok ? 'm.verify.chainOk' : 'm.verify.chainBroken', {
                  seq: result.brokenSeq ?? 0,
                  count: entries.length,
                })}
              />
            )}
          </li>
          <li>
            <p className="micro-label m-0 mb-1">{t('m.verify.signature')}</p>
            {sig === null ? (
              <span className="text-ink-2">{t('m.verify.notRun')}</span>
            ) : (
              <Mark ok={sig} label={t('m.verify.signatureOk')} />
            )}
          </li>
        </ul>
      </Panel>
    </Grid>
  )
}

export function Records() {
  const { t } = useTranslation()
  const entries = useMemo(() => AUDIT, [])
  const intact = verifyChain(entries).ok
  return (
    <ModulePage
      group="trust"
      module="records"
      tabs={[
        {
          id: 'audit',
          label: t('m.audit.tab'),
          panel: <AuditLog entries={entries} intact={intact} />,
        },
        { id: 'verify', label: t('m.verify.tab'), panel: <RecordVerification entries={entries} /> },
      ]}
    />
  )
}

// -- Health, settings, backup ------------------------------------------------------------------

export function Health() {
  const { t } = useTranslation()
  return (
    <ModulePage
      group="system"
      module="health"
      tabs={[
        {
          id: 'services',
          label: t('m.health.services'),
          panel: (
            <Panel title={t('m.health.services')} flush>
              <Table
                caption={t('m.health.services')}
                columns={[
                  {
                    key: 'n',
                    header: t('m.health.service'),
                    render: (s: (typeof SERVICES)[number]) => t(`m.health.name.${s.id}`),
                  },
                  {
                    key: 'v',
                    header: t('m.common.version'),
                    mono: true,
                    render: (s: (typeof SERVICES)[number]) => s.version,
                  },
                  {
                    key: 's',
                    header: t('m.users.status'),
                    render: () => <Mark ok label={t('m.health.running')} />,
                  },
                  {
                    key: 'u',
                    header: t('m.health.uptime'),
                    align: 'right',
                    mono: true,
                    render: (s: (typeof SERVICES)[number]) => `${s.uptimeH} h`,
                  },
                  {
                    key: 'l',
                    header: t('m.health.latency'),
                    align: 'right',
                    mono: true,
                    render: (s: (typeof SERVICES)[number]) => `${s.latencyMs} ms`,
                  },
                ]}
                rows={SERVICES}
                rowKey={(s) => s.id}
              />
            </Panel>
          ),
        },
        {
          id: 'performance',
          label: t('m.health.performance'),
          panel: (
            <Grid cols={2}>
              <Panel title={t('m.health.tick')}>
                <LineChart
                  alt={t('m.health.tickAlt')}
                  xTitle={t('m.health.minutesAgo')}
                  yTitle="ms"
                  yMin={0}
                  yMax={PERFORMANCE.tickBudgetMs / 5}
                  series={[{ id: 'tick', label: 'p50', points: PERFORMANCE.tickSeries }]}
                  tableLabel={t('m.common.dataTable')}
                />
              </Panel>
              <Panel title={t('m.health.load')}>
                <Facts
                  rows={[
                    { label: t('m.health.tickP50'), value: `${PERFORMANCE.tickP50Ms} ms` },
                    { label: t('m.health.tickP95'), value: `${PERFORMANCE.tickP95Ms} ms` },
                    { label: t('m.health.tickBudget'), value: `${PERFORMANCE.tickBudgetMs} ms` },
                    {
                      label: t('m.health.clients'),
                      value: `${PERFORMANCE.clients} / ${PERFORMANCE.clientCap}`,
                    },
                    {
                      label: t('m.health.memory'),
                      value: `${PERFORMANCE.memoryMb} / ${PERFORMANCE.memoryCapMb} MB`,
                    },
                  ]}
                />
              </Panel>
            </Grid>
          ),
        },
        {
          id: 'storage',
          label: t('m.health.storage'),
          panel: (
            <Panel title={t('m.health.storage')}>
              {STORAGE.map((s) => (
                <Bar
                  key={s.id}
                  label={t(`m.health.store.${s.id}`)}
                  value={s.usedMb}
                  max={s.capMb}
                  text={`${s.usedMb} MB`}
                />
              ))}
            </Panel>
          ),
        },
      ]}
    />
  )
}

export function Settings() {
  const { t } = useTranslation()
  const [language, setLanguage] = useState('en')
  const [retention, setRetention] = useState('365')
  const [session, setSession] = useState('480')
  const [saved, setSaved] = useState(false)
  return (
    <ModulePage
      group="system"
      module="settings"
      tabs={[
        {
          id: 'instance',
          label: t('m.settings.instance'),
          panel: (
            <Grid cols={2}>
              <Panel title={t('m.settings.mode')}>
                <Facts
                  rows={[
                    {
                      label: t('m.settings.mode'),
                      value: <Badge tone="accent">{t('m.settings.production')}</Badge>,
                    },
                    { label: t('m.settings.demoAccounts'), value: t('m.settings.blocked') },
                    { label: t('m.settings.firstAdmin'), value: t('m.settings.fromEnv') },
                    { label: t('m.settings.signing'), value: SIGNING_KEY_ID },
                  ]}
                />
              </Panel>
              <Panel title={t('m.settings.defaults')}>
                <form
                  className="flex max-w-[360px] flex-col gap-4"
                  onSubmit={(e) => {
                    e.preventDefault()
                    setSaved(true)
                  }}
                >
                  <fieldset
                    disabled={EVALUATION_MODE}
                    className="m-0 flex flex-col gap-4 border-0 p-0"
                  >
                    <Select
                      label={t('m.settings.defaultLanguage')}
                      value={language}
                      options={[
                        { value: 'en', label: 'English', lang: 'en' },
                        { value: 'hi', label: 'हिन्दी', lang: 'hi' },
                      ]}
                      onChange={(e) => {
                        setLanguage(e.target.value)
                        setSaved(false)
                      }}
                    />
                    <Input
                      label={t('m.settings.retention')}
                      inputMode="numeric"
                      className="num"
                      value={retention}
                      onChange={(e) => {
                        setRetention(e.target.value)
                        setSaved(false)
                      }}
                      hint={t('m.settings.days')}
                    />
                    <Input
                      label={t('m.settings.sessionLength')}
                      inputMode="numeric"
                      className="num"
                      value={session}
                      onChange={(e) => {
                        setSession(e.target.value)
                        setSaved(false)
                      }}
                      hint={t('m.settings.minutes')}
                    />
                    <div className="flex items-center gap-3">
                      <Button type="submit" variant="primary">
                        {t('m.settings.save')}
                      </Button>
                      {saved && <InlineAlert tone="success">{t('m.settings.saved')}</InlineAlert>}
                    </div>
                  </fieldset>
                  {EVALUATION_MODE && <InlineAlert>{t('m.evaluation.disabled')}</InlineAlert>}
                </form>
              </Panel>
            </Grid>
          ),
        },
      ]}
    />
  )
}

export function Backup() {
  const { t } = useTranslation()
  const [rows, setRows] = useState(BACKUPS)
  const [confirm, setConfirm] = useState<string | null>(null)
  const [note, setNote] = useState<string | null>(null)
  return (
    <ModulePage
      group="system"
      module="backup"
      tabs={[
        {
          id: 'backups',
          label: t('m.backup.tab'),
          panel: (
            <div className="flex flex-col gap-4">
              <div className="flex items-center gap-3">
                <Button
                  variant="primary"
                  onClick={() => {
                    setRows([
                      {
                        id: `bk-${rows.length + 1}`,
                        at: '2026-10-12T09:30:00Z',
                        sizeMb: 169.4,
                        verified: true,
                        kind: 'incremental',
                      },
                      ...rows,
                    ])
                    setNote(t('m.backup.created'))
                  }}
                >
                  {t('m.backup.run')}
                </Button>
                {note && <InlineAlert tone="success">{note}</InlineAlert>}
              </div>
              {EVALUATION_MODE && <InlineAlert>{t('m.evaluation.disabled')}</InlineAlert>}
              <Panel title={t('m.backup.list')} flush>
                <Table
                  caption={t('m.backup.list')}
                  columns={[
                    {
                      key: 'a',
                      header: t('m.common.time'),
                      mono: true,
                      render: (b: (typeof BACKUPS)[number]) => shortTime(b.at),
                    },
                    {
                      key: 'k',
                      header: t('m.backup.kind'),
                      render: (b: (typeof BACKUPS)[number]) => t(`m.backup.${b.kind}`),
                    },
                    {
                      key: 's',
                      header: t('m.packs.size'),
                      align: 'right',
                      mono: true,
                      render: (b: (typeof BACKUPS)[number]) => `${b.sizeMb} MB`,
                    },
                    {
                      key: 'v',
                      header: t('m.register.checked'),
                      render: (b: (typeof BACKUPS)[number]) => (
                        <Mark ok={b.verified} label={t('m.register.verified')} />
                      ),
                    },
                    {
                      key: 'r',
                      header: '',
                      render: (b: (typeof BACKUPS)[number]) => (
                        <Button
                          disabled={EVALUATION_MODE}
                          onClick={() => setConfirm(b.id)}
                          aria-label={t('m.backup.restoreNamed', { when: shortTime(b.at) })}
                        >
                          {t('m.backup.restore')}
                        </Button>
                      ),
                    },
                  ]}
                  rows={rows}
                  rowKey={(b) => b.id}
                />
              </Panel>
              <Dialog
                open={confirm !== null}
                title={t('m.backup.restoreTitle')}
                onClose={() => setConfirm(null)}
              >
                <p className="m-0 mb-4 text-sm">{t('m.backup.restoreBody')}</p>
                <div className="flex justify-end gap-2">
                  <Button onClick={() => setConfirm(null)}>{t('m.common.cancel')}</Button>
                  <Button
                    variant="primary"
                    onClick={() => {
                      setConfirm(null)
                      setNote(t('m.backup.restored'))
                    }}
                  >
                    {t('m.backup.restoreConfirm')}
                  </Button>
                </div>
              </Dialog>
            </div>
          ),
        },
      ]}
    />
  )
}
