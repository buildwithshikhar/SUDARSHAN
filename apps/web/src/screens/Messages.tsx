import { useTranslation } from 'react-i18next'
import { Link, useNavigate } from 'react-router-dom'
import { PageHeader } from '../layout/PageHeader'
import { useAuth } from '../lib/auth'
import { EmptyState, ErrorState } from '../ui/States'
import { Badge } from '../ui/Badge'

export function NotFound() {
  const { t } = useTranslation()
  const { state } = useAuth()
  const signedIn = state.status === 'authenticated'
  return (
    <div className="max-w-[640px]">
      <PageHeader title={t('notFound.title')} />
      <EmptyState
        title={t('notFound.title')}
        description={t('notFound.body')}
        action={
          <Link to={signedIn ? '/status' : '/sign-in'}>
            {signedIn ? t('notFound.toStatus') : t('notFound.toSignIn')}
          </Link>
        }
      />
    </div>
  )
}

export function NoAccess() {
  const { t } = useTranslation()
  return (
    <div className="max-w-[640px]">
      <PageHeader title={t('noAccess.title')} />
      <EmptyState
        title={t('noAccess.title')}
        description={t('noAccess.body')}
        action={<Link to="/status">{t('noAccess.action')}</Link>}
      />
    </div>
  )
}

export function Offline({ onRetry }: { onRetry?: () => void }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const auth = useAuth()
  return (
    <div className="max-w-[640px]">
      <PageHeader title={t('offline.title')} />
      <ErrorState
        offline
        title={t('offline.title')}
        description={t('offline.body')}
        retryLabel={t('offline.retry')}
        onRetry={() => {
          if (onRetry) onRetry()
          else {
            auth.retry()
            navigate('/')
          }
        }}
      />
    </div>
  )
}

/** A module that exists in the UI map but is delivered by a later wave. */
export function ModulePlaceholder({
  slug,
  groupId,
  wave,
}: {
  slug: string
  groupId: string
  wave: string
}) {
  const { t } = useTranslation()
  return (
    <>
      <PageHeader
        title={t(`nav.module.${slug}`)}
        crumbs={[t(`nav.group.${groupId}`), t(`nav.module.${slug}`)]}
        actions={<Badge>{t('page.wave', { wave })}</Badge>}
      />
      <EmptyState title={t('module.arrives', { wave })} description={t('module.body')} />
    </>
  )
}
