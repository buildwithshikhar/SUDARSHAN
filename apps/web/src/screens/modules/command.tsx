import { createContext, useContext, useMemo, useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import {
  INITIAL_ASSIGNMENT,
  INITIAL_TRACKS,
  SECTOR_IDS,
  TEAM,
  TEAM_SCORE,
  sectorOf,
  type SectorId,
  type TeamTrack,
} from '../../mock'
import { Button } from '../../ui/Button'
import { Select } from '../../ui/Field'
import { Panel } from '../../ui/Panel'
import { Table, type Column } from '../../ui/Table'
import { TrackSymbol } from './aar'
import { fmtClock, pct } from './format'
import { Bar, Grid, Mark, ModulePage } from './kit'

interface HandoverLog {
  id: number
  at: number
  trackId: string
  from: string
  to: string
  state: 'offered' | 'accepted'
  latencyS: number | null
}

interface TeamState {
  assignment: Record<SectorId, string>
  setSector: (sector: SectorId, member: string) => void
  tracks: TeamTrack[]
  offer: (trackId: string, to: string) => void
  acknowledge: (trackId: string) => void
  log: HandoverLog[]
  roles: Record<string, 'operator' | 'commander'>
  setRole: (member: string, role: 'operator' | 'commander') => void
}

const Ctx = createContext<TeamState | null>(null)

export function TeamProvider({ children }: { children: ReactNode }) {
  const [assignment, setAssignment] = useState(INITIAL_ASSIGNMENT)
  const [tracks, setTracks] = useState(INITIAL_TRACKS)
  const [log, setLog] = useState<HandoverLog[]>([
    { id: 1, at: 74, trackId: 'T-099', from: 't03', to: 't02', state: 'accepted', latencyS: 5.2 },
  ])
  const [roles, setRoles] = useState<Record<string, 'operator' | 'commander'>>(
    Object.fromEntries(TEAM.map((m) => [m.id, m.role])),
  )
  const value = useMemo<TeamState>(
    () => ({
      assignment,
      setSector: (sector, member) => setAssignment((a) => ({ ...a, [sector]: member })),
      tracks,
      offer: (trackId, to) => {
        setTracks((ts) =>
          ts.map((x) => (x.id === trackId ? { ...x, handover: 'offered', owner: x.owner } : x)),
        )
        setLog((l) => {
          const track = tracks.find((x) => x.id === trackId)
          return [
            ...l,
            {
              id: l.length + 1,
              at: 118 + l.length * 9,
              trackId,
              from: track?.owner ?? '',
              to,
              state: 'offered',
              latencyS: null,
            },
          ]
        })
      },
      acknowledge: (trackId) => {
        const entry = [...log].reverse().find((e) => e.trackId === trackId && e.state === 'offered')
        setTracks((ts) =>
          ts.map((x) =>
            x.id === trackId ? { ...x, handover: 'accepted', owner: entry?.to ?? x.owner } : x,
          ),
        )
        setLog((l) =>
          l.map((e) =>
            e.trackId === trackId && e.state === 'offered'
              ? { ...e, state: 'accepted', latencyS: 4.6 + (e.id % 3) * 1.7 }
              : e,
          ),
        )
      },
      log,
      roles,
      setRole: (member, role) => setRoles((r) => ({ ...r, [member]: role })),
    }),
    [assignment, tracks, log, roles],
  )
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

function useTeam(): TeamState {
  const value = useContext(Ctx)
  if (!value) throw new Error('TeamProvider missing')
  return value
}

const memberName = (id: string) => TEAM.find((m) => m.id === id)?.callSign ?? id

const SIZE = 300
const HALF = SIZE / 2
const RANGE = 2600
const SECTOR_PATH: Record<SectorId, string> = (() => {
  const r = HALF - 10
  const p = (deg: number) => {
    const a = ((deg - 90) * Math.PI) / 180
    return `${(HALF + r * Math.cos(a)).toFixed(1)} ${(HALF + r * Math.sin(a)).toFixed(1)}`
  }
  const wedge = (a0: number, a1: number) =>
    `M ${HALF} ${HALF} L ${p(a0)} A ${r} ${r} 0 0 1 ${p(a1)} Z`
  return {
    north: wedge(-45, 45),
    east: wedge(45, 135),
    south: wedge(135, 225),
    west: wedge(225, 315),
  }
})()

export function SectorAssignment({ editable = true }: { editable?: boolean }) {
  const { t } = useTranslation()
  const team = useTeam()
  const operators = TEAM.filter((m) => team.roles[m.id] === 'operator')
  const tint = (sector: SectorId) => {
    const idx = operators.findIndex((m) => m.id === team.assignment[sector])
    return idx === 0 ? 'var(--accent)' : idx === 1 ? 'var(--signal)' : 'var(--text-2)'
  }
  return (
    <Grid cols={2}>
      <Panel title={t('m.team.sectorMap')}>
        <svg
          viewBox={`0 0 ${SIZE} ${SIZE}`}
          role="img"
          aria-label={t('m.team.sectorAlt')}
          className="block h-auto w-full max-w-[360px] bg-bg"
        >
          {SECTOR_IDS.map((s) => (
            <path
              key={s}
              d={SECTOR_PATH[s]}
              fill={tint(s)}
              fillOpacity="0.14"
              stroke={tint(s)}
              strokeWidth="1.5"
            />
          ))}
          {SECTOR_IDS.map((s, i) => {
            const a = (i * Math.PI) / 2
            return (
              <text
                key={s}
                x={HALF + 62 * Math.sin(a)}
                y={HALF - 62 * Math.cos(a) + 4}
                fontSize="11"
                textAnchor="middle"
                fill="var(--text)"
              >
                {t(`m.team.sector.${s}`)} · {memberName(team.assignment[s])}
              </text>
            )
          })}
          <rect x={HALF - 4} y={HALF - 4} width="8" height="8" fill="var(--accent)" />
          {team.tracks.map((tr) => {
            const a = ((tr.bearing - 90) * Math.PI) / 180
            const r = (tr.rangeM / RANGE) * (HALF - 14)
            const x = HALF + r * Math.cos(a)
            const y = HALF + r * Math.sin(a)
            return (
              <g key={tr.id}>
                <TrackSymbol identity={tr.identity} x={x} y={y} />
                <text x={x + 9} y={y + 4} fontSize="10" fill="var(--text)">
                  {tr.id}
                </text>
              </g>
            )
          })}
        </svg>
      </Panel>
      <Panel title={t('m.team.assignment')}>
        <div className="flex max-w-[420px] flex-col gap-4">
          {SECTOR_IDS.map((s) => (
            <Select
              key={s}
              label={t('m.team.sectorOwner', { sector: t(`m.team.sector.${s}`) })}
              value={team.assignment[s]}
              disabled={!editable}
              options={operators.map((m) => ({ value: m.id, label: `${m.name} (${m.callSign})` }))}
              onChange={(e) => team.setSector(s, e.target.value)}
            />
          ))}
          <p className="num m-0 text-xs text-ink-2">
            {t('m.team.coverage', {
              count: new Set(Object.values(team.assignment)).size,
              total: operators.length,
            })}
          </p>
        </div>
      </Panel>
    </Grid>
  )
}

export function RoleAssignment() {
  const { t } = useTranslation()
  const team = useTeam()
  return (
    <Panel title={t('m.team.roles')} flush>
      <Table
        caption={t('m.team.roles')}
        columns={[
          {
            key: 'n',
            header: t('m.common.trainee'),
            render: (m: (typeof TEAM)[number]) => `${m.name} (${m.callSign})`,
          },
          {
            key: 'r',
            header: t('m.team.role'),
            render: (m: (typeof TEAM)[number]) => (
              <Select
                label={t('m.team.roleFor', { name: m.name })}
                value={team.roles[m.id] ?? m.role}
                options={[
                  { value: 'operator', label: t('m.team.operator') },
                  { value: 'commander', label: t('m.team.commander') },
                ]}
                onChange={(e) =>
                  team.setRole(m.id, e.target.value === 'commander' ? 'commander' : 'operator')
                }
              />
            ),
          },
        ]}
        rows={TEAM}
        rowKey={(m) => m.id}
        density="comfortable"
      />
    </Panel>
  )
}

export function TrackHandover({ role = 'commander' }: { role?: 'commander' | 'monitor' }) {
  const { t } = useTranslation()
  const team = useTeam()
  const [target, setTarget] = useState<Record<string, string>>({})
  const operators = TEAM.filter((m) => team.roles[m.id] === 'operator')
  const columns: Column<TeamTrack>[] = [
    { key: 'id', header: t('m.team.track'), mono: true, render: (r) => r.id },
    { key: 'cls', header: t('m.lib.class'), render: (r) => t(`live.class.${r.cls}`) },
    { key: 'idn', header: t('m.team.identity'), render: (r) => t(`live.identity.${r.identity}`) },
    {
      key: 'rng',
      header: t('m.team.range'),
      align: 'right',
      mono: true,
      render: (r) => `${r.rangeM} m`,
    },
    {
      key: 'brg',
      header: t('m.team.bearing'),
      align: 'right',
      mono: true,
      render: (r) => `${String(r.bearing).padStart(3, '0')}°`,
    },
    {
      key: 'sec',
      header: t('m.team.sectorCol'),
      render: (r) => t(`m.team.sector.${sectorOf(r.bearing)}`),
    },
    { key: 'own', header: t('m.team.owner'), render: (r) => memberName(r.owner) },
    {
      key: 'hist',
      header: t('m.team.history'),
      align: 'right',
      mono: true,
      render: (r) => r.history,
    },
    {
      key: 'state',
      header: t('m.team.handoverState'),
      render: (r) => (
        <Mark ok={r.handover === 'accepted'} label={t(`m.team.state.${r.handover}`)} />
      ),
    },
    {
      key: 'act',
      header: '',
      render: (r) => {
        if (role === 'monitor') return null
        if (r.handover === 'offered') {
          const to = [...team.log].reverse().find((e) => e.trackId === r.id)?.to ?? ''
          return (
            <Button
              onClick={() => team.acknowledge(r.id)}
              aria-label={t('m.team.acknowledgeNamed', { id: r.id, name: memberName(to) })}
            >
              {t('m.team.acknowledge')}
            </Button>
          )
        }
        const choices = operators.filter((m) => m.id !== r.owner)
        const to = target[r.id] ?? choices[0]?.id ?? ''
        return (
          <span className="flex items-center gap-2">
            <select
              aria-label={t('m.team.handTo', { id: r.id })}
              className="h-7 border border-line bg-bg px-2 text-sm"
              value={to}
              onChange={(e) => setTarget({ ...target, [r.id]: e.target.value })}
            >
              {choices.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.callSign}
                </option>
              ))}
            </select>
            <Button
              onClick={() => team.offer(r.id, to)}
              aria-label={t('m.team.handOverNamed', { id: r.id })}
            >
              {t('m.team.handOver')}
            </Button>
          </span>
        )
      },
    },
  ]
  return (
    <div className="flex flex-col gap-4">
      <Panel title={t('m.team.trackBoard')} flush>
        <Table
          caption={t('m.team.trackBoard')}
          columns={columns}
          rows={team.tracks}
          rowKey={(r) => r.id}
        />
      </Panel>
      <Panel title={t('m.team.handoverLog')} flush>
        <Table
          caption={t('m.team.handoverLog')}
          columns={[
            {
              key: 't',
              header: t('m.common.time'),
              mono: true,
              render: (e: HandoverLog) => fmtClock(e.at),
            },
            {
              key: 'tr',
              header: t('m.team.track'),
              mono: true,
              render: (e: HandoverLog) => e.trackId,
            },
            { key: 'f', header: t('m.team.from'), render: (e: HandoverLog) => memberName(e.from) },
            { key: 'to', header: t('m.team.to'), render: (e: HandoverLog) => memberName(e.to) },
            {
              key: 's',
              header: t('m.team.handoverState'),
              render: (e: HandoverLog) => t(`m.team.state.${e.state}`),
            },
            {
              key: 'l',
              header: t('m.team.latency'),
              align: 'right',
              mono: true,
              render: (e: HandoverLog) =>
                e.latencyS === null ? '—' : `${e.latencyS.toFixed(1)} s`,
            },
          ]}
          rows={team.log}
          rowKey={(e) => String(e.id)}
        />
      </Panel>
    </div>
  )
}

export function TeamScore() {
  const { t } = useTranslation()
  return (
    <Grid cols={2}>
      <Panel title={t('m.team.teamScore')}>
        <p className="num m-0 mb-3 text-lg font-semibold">{TEAM_SCORE.total.toFixed(1)}</p>
        {TEAM_SCORE.parts.map((p) => (
          <Bar
            key={p.id}
            label={t(`m.team.part.${p.id}`)}
            value={p.score}
            max={100}
            text={p.score.toFixed(1)}
          />
        ))}
      </Panel>
      <Panel title={t('m.team.roleScores')} flush>
        <Table
          caption={t('m.team.roleScores')}
          columns={[
            {
              key: 'n',
              header: t('m.team.member'),
              render: (r: (typeof TEAM_SCORE.roles)[number]) => memberName(r.id),
            },
            {
              key: 'r',
              header: t('m.team.role'),
              render: (r: (typeof TEAM_SCORE.roles)[number]) => t(`m.team.${r.role}`),
            },
            {
              key: 's',
              header: t('m.common.score'),
              align: 'right',
              mono: true,
              render: (r: (typeof TEAM_SCORE.roles)[number]) => r.score.toFixed(1),
            },
            {
              key: 'h',
              header: t('m.team.handoverTime'),
              align: 'right',
              mono: true,
              render: (r: (typeof TEAM_SCORE.roles)[number]) => `${r.handoverS.toFixed(1)} s`,
            },
          ]}
          rows={TEAM_SCORE.roles}
          rowKey={(r) => r.id}
        />
        <p className="num m-0 px-3 py-2 text-xs text-ink-2">
          {t('m.team.scoreNote', { share: pct(TEAM_SCORE.total / 100) })}
        </p>
      </Panel>
    </Grid>
  )
}

/** The detachment commander's module: sector assignment, track handover and team score. */
export function Command() {
  const { t } = useTranslation()
  return (
    <TeamProvider>
      <ModulePage
        group="command"
        module="command"
        tabs={[
          { id: 'sectors', label: t('m.team.sectors'), panel: <SectorAssignment /> },
          { id: 'handover', label: t('m.team.handover'), panel: <TrackHandover /> },
          { id: 'score', label: t('m.team.teamScore'), panel: <TeamScore /> },
        ]}
      />
    </TeamProvider>
  )
}
