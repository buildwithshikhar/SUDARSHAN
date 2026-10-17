import { useTranslation } from 'react-i18next'
import type { Language } from '../i18n'
import { persistPreference, useAuth } from '../lib/auth'
import { setLanguage, setTheme, useTheme, type Theme } from '../lib/prefs'
import { Segmented } from '../ui/Segmented'

/** Language and theme switches: applied at once, and saved to the account when signed in. */
export function PreferenceControls() {
  const { t, i18n } = useTranslation()
  const auth = useAuth()
  const theme = useTheme()
  const language: Language = i18n.language === 'hi' ? 'hi' : 'en'

  return (
    <div className="flex items-center gap-4">
      <Segmented<Language>
        label={t('controls.language')}
        value={language}
        options={[
          { value: 'en', label: 'English', lang: 'en' },
          { value: 'hi', label: 'हिन्दी', lang: 'hi' },
        ]}
        onChange={(value) => {
          setLanguage(value)
          void persistPreference(auth, { language: value })
        }}
      />
      <Segmented<Theme>
        label={t('controls.theme')}
        value={theme}
        options={[
          { value: 'dark', label: t('controls.dark') },
          { value: 'light', label: t('controls.light') },
        ]}
        onChange={(value) => {
          setTheme(value)
          void persistPreference(auth, { theme: value })
        }}
      />
    </div>
  )
}
