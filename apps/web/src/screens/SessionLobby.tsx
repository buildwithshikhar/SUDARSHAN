import { CheckmarkFilled, WarningFilled } from '@carbon/icons-react'
import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useLocation, useNavigate } from 'react-router-dom'
import { PageHeader } from '../layout/PageHeader'
import { useAuth } from '../lib/auth'
import { ApiError, NetworkError } from '../lib/api'
import { fmtElapsed, fmtHours, useLang } from '../live/format'
import { createSession, listScenarios, localised, type ScenarioItem } from '../live/restApi'
import { webglAvailable } from '../live/views/eoScene'
import { Badge } from '../ui/Badge'
import { Button } from '../ui/Button'
import { InlineAlert } from '../ui/InlineAlert'
import { Panel } from '../ui/Panel'
import { EmptyState, ErrorState, LoadingState } from '../ui/States'
import { Table, type Column } from '../ui/Table'

type Load =
  | { state: 'loading' }
  | { state: 'error'; offline: boolean }
  | { state: 'ready'; scenarios: ScenarioItem[] }

function Fact({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid min-h-6 grid-cols-[148px_1fr] items-baseline gap-2 border-b border-line px-3 py-0.5 last:border-b-0">
      <dt className="text-sm text-ink-2">{label}</dt>
      <dd className="num m-0 text-sm">{children}</dd>
    </div>
  )
}

function Briefing({ scenario }: { scenario: ScenarioItem }) {
  const { t } = useTranslation()
  const lang = useLang()
  const b = scenario.briefing
  const w = b?.weather
  return (
    <Panel title={t('live.lobby.briefing')} flush>
      <div className="border-b border-line px-3 py-3">
        <h3 className="m-0 text-md font-semibold">{localised(scenario.title, lang)}</h3>
        <p className="mb-0 mt-1 max-w-[640px] text-sm text-ink-2">
          {localised(scenario.summary, lang)}
        </p>
      </div>
      <dl className="m-0">
        <Fact label={t('live.lobby.duration')}>{fmtElapsed(scenario.duration_s)}</Fact>
        <Fact label={t('live.lobby.light')}>{fmtHours(scenario.start_time_of_day_h)}</Fact>
        <Fact label={t('live.lobby.weather')}>
          {t(`live.weather.${scenario.weather_condition}`, {
            defaultValue: scenario.weather_condition,
          })}
          {w
            ? ` · ${t('live.top.vis')} ${(w.visibility_m / 1000).toFixed(1)} km · ${Math.round(w.wind_from_deg)}°/${w.wind_speed_mps.toFixed(1)} ${t('live.units.mps')} · ${Math.round(w.temperature_c)} °C`
            : ''}
        </Fact>
        <Fact label={t('live.lobby.rules')}>
          {scenario.rule_pack
            ? `${localised(scenario.rule_pack.title, lang) || scenario.rule_pack.id} · ${scenario.rule_pack.id} ${scenario.rule_pack.version}`
            : t('live.lobby.rulesLater')}
        </Fact>
        <Fact label={t('live.lobby.version')}>
          {scenario.id} {scenario.version} · {t('live.lobby.seed')} {scenario.default_seed}
        </Fact>
        {b && (
          <>
            <Fact label={t('live.lobby.site')}>
              {b.zones
                .map((z) => `${localised(z.label, lang)} ${(z.radius_m / 1000).toFixed(1)} km`)
                .join(' · ')}
            </Fact>
            <Fact label={t('live.lobby.sensors')}>
              {b.sensors.map((s) => `${s.id} (${t(`live.modality.${s.modality}`)})`).join(' · ')}
            </Fact>
            <Fact label={t('live.lobby.flights')}>
              {b.filed_flights.length === 0
                ? t('live.lobby.noFlights')
                : b.filed_flights
                    .map(
                      (f) =>
                        `${localised(f.label, lang)} · ${f.id} · r ${(f.radius_m / 1000).toFixed(2)} km`,
                    )
                    .join(' | ')}
            </Fact>
          </>
        )}
      </dl>
      {!b && (
        <p className="m-0 border-t border-line px-3 py-2 text-xs text-ink-2">
          {t('live.lobby.briefingLater')}
        </p>
      )}
    </Panel>
  )
}

function KitCheck() {
  const { t } = useTranslation()
  const auth = useAuth()
  const [size] = useState({ w: window.innerWidth, h: window.innerHeight })
  const role = auth.state.status === 'authenticated' ? auth.state.user.role : 'trainee'
  const gl = webglAvailable()
  const big = size.w >= 1366 && size.h >= 700
  const items = [
    { id: 'role', ok: true, label: t('live.kit.role'), value: t(`roles.${role}`) },
    {
      id: 'webgl',
      ok: gl,
      label: t('live.kit.webgl'),
      value: gl ? t('live.kit.available') : t('live.kit.missing'),
    },
    {
      id: 'display',
      ok: big,
      label: t('live.kit.display'),
      value: `${size.w} × ${size.h} · ${big ? t('live.kit.meets') : t('live.kit.below')}`,
    },
    { id: 'keyboard', ok: true, label: t('live.kit.keyboard'), value: t('live.kit.keyboardValue') },
  ]
  return (
    <Panel title={t('live.lobby.kit')} flush>
      <ul className="m-0 list-none p-0">
        {items.map((item) => (
          <li
            key={item.id}
            className="grid min-h-7 grid-cols-[148px_1fr] items-center gap-2 border-b border-line px-3 last:border-b-0"
          >
            <span className="text-sm text-ink-2">{item.label}</span>
            <span className="flex items-center gap-2 text-sm">
              {item.ok ? (
                <CheckmarkFilled size={16} aria-hidden="true" className="text-track-neutral" />
              ) : (
                <WarningFilled size={16} aria-hidden="true" className="text-signal" />
              )}
              <span className="num">{item.value}</span>
            </span>
          </li>
        ))}
      </ul>
    </Panel>
  )
}

export function SessionLobby() {
  const { t } = useTranslation()
  const lang = useLang()
  const navigate = useNavigate()
  const location = useLocation()
  const [load, setLoad] = useState<Load>({ state: 'loading' })
  const [attempt, setAttempt] = useState(0)
  const [chosen, setChosen] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)

  const retry = useCallback(() => {
    setLoad({ state: 'loading' })
    setAttempt((n) => n + 1)
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    listScenarios(controller.signal)
      .then((scenarios) => {
        setLoad({ state: 'ready', scenarios })
        setChosen((current) => current ?? scenarios[0]?.id ?? null)
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return
        setLoad({ state: 'error', offline: error instanceof NetworkError })
      })
    return () => controller.abort()
  }, [attempt])

  const scenarios = load.state === 'ready' ? load.scenarios : []
  const scenario = scenarios.find((s) => s.id === chosen) ?? null

  const create = async () => {
    if (!scenario) return
    setCreating(true)
    setCreateError(null)
    try {
      const row = await createSession(scenario.id)
      navigate(`/train/session/${row.id}${location.search}`)
    } catch (error) {
      setCreating(false)
      setCreateError(
        error instanceof ApiError
          ? error.status === 403
            ? t('live.lobby.createForbidden')
            : t('live.lobby.createFailed', { detail: error.message })
          : t('live.lobby.createUnreachable'),
      )
    }
  }

  const columns: Column<ScenarioItem>[] = [
    {
      key: 'title',
      header: t('live.lobby.scenario'),
      render: (s) => (
        <button
          type="button"
          aria-pressed={chosen === s.id}
          onClick={() => setChosen(s.id)}
          className="h-6 border-0 bg-transparent p-0 text-left text-sm text-ink underline decoration-dotted underline-offset-4"
        >
          {localised(s.title, lang)}
        </button>
      ),
    },
    {
      key: 'duration',
      header: t('live.lobby.duration'),
      mono: true,
      render: (s) => fmtElapsed(s.duration_s),
    },
    {
      key: 'light',
      header: t('live.lobby.light'),
      mono: true,
      render: (s) => fmtHours(s.start_time_of_day_h),
    },
  ]

  return (
    <>
      <PageHeader
        title={t('live.lobby.title')}
        crumbs={[t('nav.group.train'), t('nav.module.drills'), t('live.lobby.title')]}
        actions={<Badge>{t('live.lobby.reference')}</Badge>}
      />
      {load.state === 'loading' && <LoadingState label={t('live.lobby.loading')} />}
      {load.state === 'error' && (
        <div className="max-w-[640px]">
          <ErrorState
            offline={load.offline}
            title={t(load.offline ? 'live.lobby.unreachable' : 'live.lobby.error')}
            description={t('live.lobby.errorBody')}
            retryLabel={t('app.retry')}
            onRetry={retry}
          />
        </div>
      )}
      {load.state === 'ready' && scenarios.length === 0 && (
        <div className="max-w-[640px]">
          <EmptyState title={t('live.lobby.empty')} description={t('live.lobby.emptyBody')} />
        </div>
      )}
      {load.state === 'ready' && scenarios.length > 0 && (
        <div className="grid grid-cols-1 items-start gap-4 xl:grid-cols-12">
          <div className="flex flex-col gap-4 xl:col-span-5">
            <Panel title={t('live.lobby.scenarios')} flush>
              <Table
                caption={t('live.lobby.scenarios')}
                columns={columns}
                rows={scenarios}
                rowKey={(s) => s.id}
                selectedKey={chosen}
                onRowClick={(s) => setChosen(s.id)}
              />
            </Panel>
            <KitCheck />
          </div>
          <div className="flex flex-col gap-4 xl:col-span-7">
            {scenario && <Briefing scenario={scenario} />}
            {createError && <InlineAlert tone="error">{createError}</InlineAlert>}
            <div className="flex items-center gap-4">
              <Button
                variant="primary"
                disabled={!scenario || creating}
                onClick={() => void create()}
              >
                {creating ? t('live.lobby.creating') : t('live.lobby.create')}
              </Button>
              <p className="m-0 text-xs text-ink-2">{t('live.lobby.createNote')}</p>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
