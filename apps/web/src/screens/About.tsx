import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { PageHeader } from '../layout/PageHeader'
import { useAuth } from '../lib/auth'
import { Panel } from '../ui/Panel'

export function About() {
  const { t } = useTranslation()
  const { state } = useAuth()
  const signedIn = state.status === 'authenticated'
  return (
    <div className="max-w-[760px]">
      <PageHeader title={t('about.title')} />
      <div className="flex flex-col gap-4">
        <Panel title={t('about.dataTitle')}>
          <p className="m-0 mb-2 text-sm">{t('about.data1')}</p>
          <p className="m-0 text-sm">{t('about.data2')}</p>
        </Panel>
        <Panel title={t('about.scopeTitle')}>
          <p className="m-0 mb-2 text-sm">{t('about.scope1')}</p>
          <p className="m-0 text-sm">{t('about.scope2')}</p>
        </Panel>
        <Panel title={t('about.affiliationTitle')}>
          <p className="m-0 text-sm">{t('about.affiliation')}</p>
        </Panel>
      </div>
      <p className="mt-4 text-sm">
        <Link to={signedIn ? '/status' : '/sign-in'}>{t('about.back')}</Link>
      </p>
    </div>
  )
}
