import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import { readSetting } from '../lib/storage'
import en from './en.json'
import hi from './hi.json'

export const LANGUAGES = ['en', 'hi'] as const
export type Language = (typeof LANGUAGES)[number]
export const LANGUAGE_KEY = 'ui.language'

export function isLanguage(value: string | null): value is Language {
  return value !== null && (LANGUAGES as readonly string[]).includes(value)
}

const stored = readSetting(LANGUAGE_KEY)

void i18n.use(initReactI18next).init({
  resources: { en: { translation: en }, hi: { translation: hi } },
  lng: isLanguage(stored) ? stored : 'en',
  fallbackLng: 'en',
  interpolation: { escapeValue: false },
})

export default i18n
