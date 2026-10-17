import { Logout } from '@carbon/icons-react'
import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, NavLink } from 'react-router-dom'
import brand from '../../../../brand.json'
import { useAuth } from '../lib/auth'
import { useVersion } from '../lib/version'
import { modulePath, sidebarGroups } from '../nav/modules'
import { Badge } from '../ui/Badge'
import { BrandMark } from '../ui/BrandMark'
import { Button } from '../ui/Button'
import { PreferenceControls } from './PreferenceControls'
import { StatusStrip } from './PublicFrame'

const itemClass = ({ isActive }: { isActive: boolean }) =>
  `flex h-7 items-center border-l-2 px-3 text-sm no-underline ${
    isActive
      ? 'border-accent bg-surface-2 text-ink'
      : 'border-transparent text-ink-2 hover:text-ink'
  }`

/** Signed-in frame: top bar, role-based sidebar, content area and status strip. */
export function Shell({ children }: { children: ReactNode }) {
  const { t } = useTranslation()
  const auth = useAuth()
  const version = useVersion()
  if (auth.state.status !== 'authenticated') return null
  const { user } = auth.state
  const info = version.state.status === 'ready' ? version.state.info : null

  return (
    <div className="flex min-h-screen flex-col">
      <a
        href="#main"
        className="absolute left-2 top-2 -translate-y-12 bg-surface-2 px-3 py-2 text-sm focus:translate-y-0"
      >
        {t('app.skip')}
      </a>
      <header className="flex h-10 items-center justify-between border-b border-line bg-surface-1 px-4">
        <Link to="/status" className="flex items-center gap-3 text-ink no-underline">
          <BrandMark />
          <span className="text-base font-semibold tracking-[0.14em]">{brand.productName}</span>
        </Link>
        <div className="flex items-center gap-4">
          <Badge tone="accent">{t(`roles.${user.role}`)}</Badge>
          <span className="num hidden text-sm text-ink-2 lg:inline">{user.email}</span>
          <PreferenceControls />
          <Button variant="ghost" onClick={() => void auth.logout()}>
            <Logout size={16} aria-hidden="true" />
            {t('controls.signOut')}
          </Button>
        </div>
      </header>

      <div className="flex flex-1">
        <nav
          aria-label={t('nav.aria')}
          className="w-[232px] shrink-0 border-r border-line bg-surface-1 py-3"
        >
          <NavLink to="/status" className={itemClass} end>
            {t('nav.status')}
          </NavLink>
          {sidebarGroups(user.role).map((group) => (
            <div key={group.id} className="mt-4">
              <h2 className="micro-label m-0 mb-1 px-3">{t(`nav.group.${group.id}`)}</h2>
              <ul className="m-0 list-none p-0">
                {group.modules.map((module) => (
                  <li key={module.slug}>
                    <NavLink
                      to={modulePath(user.role, group.id, module.slug)}
                      className={itemClass}
                    >
                      {t(`nav.module.${module.slug}`)}
                    </NavLink>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </nav>
        <main id="main" className="min-w-0 flex-1 px-6 py-6">
          {children}
        </main>
      </div>

      <StatusStrip>
        <div className="num flex items-center gap-4 text-xs text-ink-2">
          <Link to="/about" className="text-ink-2">
            {t('nav.about')}
          </Link>
          {info && (
            <span>
              {info.version} · {info.gitSha} · {info.env}
            </span>
          )}
        </div>
      </StatusStrip>
    </div>
  )
}
