import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import brand from '../../../../brand.json'
import { BrandMark } from '../ui/BrandMark'
import { PreferenceControls } from './PreferenceControls'

export function StatusStrip({ children }: { children?: ReactNode }) {
  const { t } = useTranslation()
  return (
    <footer className="flex min-h-8 items-center justify-between gap-4 border-t border-line bg-surface-1 px-4 py-1">
      <p className="micro-label m-0">{t('app.scenarioLabel')}</p>
      {children}
    </footer>
  )
}

/** Frame for pages shown without a session: sign in, About, Not found, Offline. */
export function PublicFrame({ children }: { children: ReactNode }) {
  const { t } = useTranslation()
  return (
    <div className="flex min-h-screen flex-col">
      <a
        href="#main"
        className="absolute left-2 top-2 -translate-y-12 bg-surface-2 px-3 py-2 text-sm focus:translate-y-0"
      >
        {t('app.skip')}
      </a>
      <header className="flex h-10 items-center justify-between border-b border-line bg-surface-1 px-4">
        <Link to="/" className="flex items-center gap-3 text-ink no-underline">
          <BrandMark />
          <span className="text-base font-semibold tracking-[0.14em]">{brand.productName}</span>
        </Link>
        <PreferenceControls />
      </header>
      <main id="main" className="flex flex-1 flex-col px-6 py-8">
        {children}
      </main>
      <StatusStrip />
    </div>
  )
}
