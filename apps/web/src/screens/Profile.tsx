import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { PageHeader } from '../layout/PageHeader'
import type { Language } from '../i18n'
import { ApiError, NetworkError } from '../lib/api'
import { useAuth } from '../lib/auth'
import { setLanguage, setTheme, useTheme, type Theme } from '../lib/prefs'
import { setTeamRole, useViewRole } from '../lib/viewRole'
import { InlineAlert } from '../ui/InlineAlert'
import { Panel } from '../ui/Panel'
import { Select } from '../ui/Field'
import { Tabs } from '../ui/Tabs'

export function Profile() {
  const { t, i18n } = useTranslation()
  const auth = useAuth()
  const theme = useTheme()
  const view = useViewRole()
  const [notice, setNotice] = useState<'saved' | 'failed' | null>(null)
  const language: Language = i18n.language === 'hi' ? 'hi' : 'en'

  const save = async (prefs: { language?: Language; theme?: Theme }) => {
    try {
      await auth.savePreferences(prefs)
      setNotice('saved')
    } catch (error) {
      if (error instanceof ApiError || error instanceof NetworkError) setNotice('failed')
      else throw error
    }
  }

  const preferences = (
    <div className="flex max-w-[360px] flex-col gap-4">
      <Select
        label={t('profile.language')}
        value={language}
        options={[
          { value: 'en', label: 'English', lang: 'en' },
          { value: 'hi', label: 'हिन्दी', lang: 'hi' },
        ]}
        onChange={(event) => {
          const value = event.target.value === 'hi' ? 'hi' : 'en'
          setLanguage(value)
          void save({ language: value })
        }}
      />
      <Select
        label={t('profile.theme')}
        value={theme}
        options={[
          { value: 'dark', label: t('controls.dark') },
          { value: 'light', label: t('controls.light') },
        ]}
        onChange={(event) => {
          const value = event.target.value === 'light' ? 'light' : 'dark'
          setTheme(value)
          void save({ theme: value })
        }}
      />
      {auth.state.status === 'authenticated' && auth.state.user.role === 'trainee' && (
        <Select
          label={t('profile.teamRole')}
          hint={t('profile.teamRoleHint')}
          value={view === 'commander' ? 'commander' : 'operator'}
          options={[
            { value: 'operator', label: t('roles.trainee') },
            { value: 'commander', label: t('roles.commander') },
          ]}
          onChange={(event) =>
            setTeamRole(event.target.value === 'commander' ? 'commander' : 'operator')
          }
        />
      )}
      {notice === 'saved' && <InlineAlert tone="success">{t('profile.saved')}</InlineAlert>}
      {notice === 'failed' && <InlineAlert tone="warning">{t('profile.saveFailed')}</InlineAlert>}
    </div>
  )

  const accessibility = (
    <div className="max-w-[640px]">
      <p className="m-0 mb-3 text-sm text-ink-2">{t('profile.accessibilityIntro')}</p>
      <ul className="m-0 flex list-none flex-col gap-2 p-0 text-sm">
        {['accKeyboard', 'accContrast', 'accMotion', 'accLanguage'].map((key) => (
          <li key={key} className="border-l-2 border-line pl-3">
            {t(`profile.${key}`)}
          </li>
        ))}
      </ul>
    </div>
  )

  return (
    <>
      <PageHeader
        title={t('profile.title')}
        crumbs={[t('nav.group.account'), t('nav.module.profile')]}
      />
      <Panel title={t('profile.title')}>
        <Tabs
          label={t('profile.tabs')}
          tabs={[
            { id: 'preferences', label: t('profile.tabPreferences'), panel: preferences },
            { id: 'accessibility', label: t('profile.tabAccessibility'), panel: accessibility },
          ]}
        />
      </Panel>
    </>
  )
}
