import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { BuildStatus } from './components/BuildStatus'
import { TopBar, type Theme } from './components/TopBar'
import { readSetting, writeSetting } from './lib/storage'

const THEME_KEY = 'ui.theme'

function initialTheme(): Theme {
  const stored = readSetting(THEME_KEY)
  return stored === 'light' ? 'light' : 'dark'
}

export default function App() {
  const { t, i18n } = useTranslation()
  const [theme, setTheme] = useState<Theme>(initialTheme)

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    writeSetting(THEME_KEY, theme)
  }, [theme])

  useEffect(() => {
    document.documentElement.lang = i18n.language
  }, [i18n.language])

  return (
    <div className="flex min-h-screen flex-col">
      <a
        href="#main"
        className="absolute left-2 top-2 -translate-y-12 bg-surface-2 px-3 py-2 text-sm focus:translate-y-0"
      >
        {t('app.skip')}
      </a>
      <TopBar theme={theme} onTheme={setTheme} />
      <main id="main" className="flex flex-1 items-start px-6 py-8">
        <BuildStatus />
      </main>
      <footer className="border-t border-line bg-surface-1 px-4 py-2">
        <p className="micro-label m-0">{t('app.scenarioLabel')}</p>
      </footer>
    </div>
  )
}
