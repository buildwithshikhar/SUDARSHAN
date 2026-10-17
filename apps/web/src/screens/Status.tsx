import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { useAuth } from '../lib/auth'
import { useVersion } from '../lib/version'
import { ACCOUNT_BUILT, modulePath, sidebarGroups } from '../nav/modules'
import { PageHeader } from '../layout/PageHeader'
import { Badge } from '../ui/Badge'
import { Panel } from '../ui/Panel'
import { ErrorState, LoadingState } from '../ui/States'
import { Table, type Column } from '../ui/Table'
import { Tooltip } from '../ui/Tooltip'

interface RowItem {
  id: string
  label: ReactNode
  value: ReactNode
}

function Rows({ rows }: { rows: RowItem[] }) {
  return (
    <dl className="m-0">
      {rows.map(({ id, label, value }) => (
        <div
          key={id}
          className="grid min-h-7 grid-cols-[148px_1fr] items-center border-b border-line px-3 last:border-b-0"
        >
          <dt className="text-sm text-ink-2">{label}</dt>
          <dd className="num m-0 text-sm">{value}</dd>
        </div>
      ))}
    </dl>
  )
}

interface ModuleRow {
  key: string
  slug: string
  group: string
  wave: string
  path: string
}

export function Status() {
  const { t } = useTranslation()
  const auth = useAuth()
  const version = useVersion()
  if (auth.state.status !== 'authenticated') return null
  const { user, expiresAt } = auth.state

  const rows: ModuleRow[] = sidebarGroups(user.role).flatMap((group) =>
    group.modules.map((module) => ({
      key: `${group.id}/${module.slug}`,
      slug: module.slug,
      group: group.id,
      wave: module.wave,
      path: modulePath(user.role, group.id, module.slug),
    })),
  )

  const columns: Column<ModuleRow>[] = [
    {
      key: 'module',
      header: t('status.moduleCol'),
      render: (row) => <Link to={row.path}>{t(`nav.module.${row.slug}`)}</Link>,
    },
    { key: 'group', header: t('status.groupCol'), render: (row) => t(`nav.group.${row.group}`) },
    {
      key: 'wave',
      header: t('status.arrivesCol'),
      mono: true,
      render: (row) => (ACCOUNT_BUILT.has(row.slug) ? '—' : t('page.wave', { wave: row.wave })),
    },
    {
      key: 'state',
      header: t('status.stateCol'),
      render: (row) =>
        ACCOUNT_BUILT.has(row.slug) ? (
          <Badge tone="neutralTrack">{t('status.available')}</Badge>
        ) : (
          <Badge>{t('status.planned')}</Badge>
        ),
    },
  ]

  return (
    <>
      <PageHeader title={t('status.title')} />
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <Panel title={t('status.build')} flush>
          {version.state.status === 'loading' && <LoadingState label={t('status.loading')} />}
          {version.state.status === 'error' && (
            <ErrorState
              offline
              title={t('status.error')}
              retryLabel={t('app.retry')}
              onRetry={version.retry}
            />
          )}
          {version.state.status === 'ready' && (
            <Rows
              rows={[
                { id: 'version', label: t('status.version'), value: version.state.info.version },
                { id: 'commit', label: t('status.commit'), value: version.state.info.gitSha },
                { id: 'built', label: t('status.built'), value: version.state.info.buildTime },
                { id: 'env', label: t('status.environment'), value: version.state.info.env },
                {
                  id: 'api',
                  label: t('status.apiStatus'),
                  value: (
                    <span>
                      <span
                        aria-hidden="true"
                        className="mr-2 inline-block h-2 w-2 bg-track-neutral"
                      />
                      {t('status.reachable')}
                    </span>
                  ),
                },
              ]}
            />
          )}
        </Panel>

        <Panel title={t('status.session')} flush>
          <Rows
            rows={[
              { id: 'account', label: t('status.account'), value: user.email },
              { id: 'role', label: t('status.role'), value: t(`roles.${user.role}`) },
              {
                id: 'language',
                label: t('status.language'),
                value: user.language === 'hi' ? 'हिन्दी' : 'English',
              },
              {
                id: 'theme',
                label: t('status.theme'),
                value: t(user.theme === 'light' ? 'controls.light' : 'controls.dark'),
              },
              {
                id: 'expires',
                label: (
                  <Tooltip label={t('status.expiresHint')}>
                    <button
                      type="button"
                      className="border-0 bg-transparent p-0 text-left text-sm text-ink-2 underline decoration-dotted"
                    >
                      {t('status.expires')}
                    </button>
                  </Tooltip>
                ),
                value: `${expiresAt.replace('T', ' ').slice(0, 19)}Z`,
              },
            ]}
          />
        </Panel>
      </div>

      <Panel title={t('status.modules')} className="mt-4" flush>
        <Table
          caption={t('status.modules')}
          columns={columns}
          rows={rows}
          rowKey={(row) => row.key}
        />
      </Panel>
    </>
  )
}
