import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { useVersion } from '../lib/version'

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid min-h-7 grid-cols-[160px_1fr] items-center border-b border-line px-3 last:border-b-0">
      <dt className="text-sm text-ink-2">{label}</dt>
      <dd className="num m-0 text-sm">{children}</dd>
    </div>
  )
}

function Skeleton() {
  return <span aria-hidden="true" className="block h-2 w-24 bg-surface-2" />
}

export function BuildStatus() {
  const { t } = useTranslation()
  const { state, retry } = useVersion()

  return (
    <section aria-labelledby="build-title" className="w-full max-w-[640px]">
      <h1 id="build-title" className="micro-label mb-2 font-normal">
        {t('build.title')}
      </h1>

      {state.status === 'error' ? (
        <div role="alert" className="border border-line bg-surface-1 p-4">
          <p className="m-0 mb-3 text-sm">{t('build.error')}</p>
          <button type="button" className="seg" onClick={retry}>
            {t('build.retry')}
          </button>
        </div>
      ) : (
        <dl
          className="m-0 border border-line bg-surface-1"
          aria-busy={state.status === 'loading'}
          aria-label={state.status === 'loading' ? t('build.loading') : undefined}
        >
          {state.status === 'loading' ? (
            <>
              {(['service', 'version', 'commit', 'built', 'environment', 'apiStatus'] as const).map(
                (key) => (
                  <Row key={key} label={t(`build.${key}`)}>
                    <Skeleton />
                  </Row>
                ),
              )}
            </>
          ) : (
            <>
              <Row label={t('build.service')}>
                {state.info.productName} · {state.info.descriptor}
              </Row>
              <Row label={t('build.version')}>{state.info.version}</Row>
              <Row label={t('build.commit')}>{state.info.gitSha}</Row>
              <Row label={t('build.built')}>{state.info.buildTime}</Row>
              <Row label={t('build.environment')}>{state.info.env}</Row>
              <Row label={t('build.apiStatus')}>
                <span aria-hidden="true" className="mr-2 inline-block h-2 w-2 bg-track-neutral" />
                {t('build.reachable')}
              </Row>
            </>
          )}
        </dl>
      )}
    </section>
  )
}
