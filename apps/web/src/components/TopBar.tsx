import { useTranslation } from 'react-i18next'
import brand from '../../../../brand.json'
import { LANGUAGE_KEY, type Language } from '../i18n'
import { writeSetting } from '../lib/storage'

export type Theme = 'dark' | 'light'

interface Props {
  theme: Theme
  onTheme: (theme: Theme) => void
}

export function TopBar({ theme, onTheme }: Props) {
  const { t, i18n } = useTranslation()
  const language = i18n.language as Language

  const setLanguage = (next: Language) => {
    writeSetting(LANGUAGE_KEY, next)
    void i18n.changeLanguage(next)
  }

  return (
    <header className="flex h-10 items-center justify-between border-b border-line bg-surface-1 px-4">
      <div className="flex items-center gap-3">
        <span aria-hidden="true" className="block h-4 w-0.5 bg-signal" />
        <span className="text-base font-semibold" style={{ letterSpacing: '0.14em' }}>
          {brand.productName}
        </span>
        <span aria-hidden="true" className="h-4 w-px bg-line" />
        <span className="hidden text-sm text-ink-2 sm:inline">{brand.descriptor}</span>
      </div>
      <div className="flex items-center gap-4">
        <div role="group" aria-label={t('controls.language')} className="flex">
          <button
            type="button"
            className="seg rounded-none"
            aria-pressed={language === 'en'}
            lang="en"
            onClick={() => setLanguage('en')}
          >
            English
          </button>
          <button
            type="button"
            className="seg -ml-px rounded-none"
            aria-pressed={language === 'hi'}
            lang="hi"
            onClick={() => setLanguage('hi')}
          >
            हिन्दी
          </button>
        </div>
        <div role="group" aria-label={t('controls.theme')} className="flex">
          <button
            type="button"
            className="seg rounded-none"
            aria-pressed={theme === 'dark'}
            onClick={() => onTheme('dark')}
          >
            {t('controls.dark')}
          </button>
          <button
            type="button"
            className="seg -ml-px rounded-none"
            aria-pressed={theme === 'light'}
            onClick={() => onTheme('light')}
          >
            {t('controls.light')}
          </button>
        </div>
      </div>
    </header>
  )
}
