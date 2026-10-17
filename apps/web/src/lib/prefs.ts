import { useSyncExternalStore } from 'react'
import i18n, { isLanguage, LANGUAGE_KEY, type Language } from '../i18n'
import { readSetting, writeSetting } from './storage'

export type Theme = 'dark' | 'light'
export const THEME_KEY = 'ui.theme'

const listeners = new Set<() => void>()
const emit = () => listeners.forEach((listener) => listener())

function isTheme(value: string | null): value is Theme {
  return value === 'dark' || value === 'light'
}

const stored = readSetting(THEME_KEY)
let theme: Theme = isTheme(stored) ? stored : 'dark'
document.documentElement.dataset.theme = theme
document.documentElement.lang = isLanguage(i18n.language) ? i18n.language : 'en'

export function getTheme(): Theme {
  return theme
}

export function setTheme(next: Theme): void {
  theme = next
  document.documentElement.dataset.theme = next
  writeSetting(THEME_KEY, next)
  emit()
}

export function setLanguage(next: Language): void {
  writeSetting(LANGUAGE_KEY, next)
  document.documentElement.lang = next
  void i18n.changeLanguage(next)
}

/** Apply the stored preferences of a signed-in user. Unknown values are ignored. */
export function applyUserPreferences(prefs: { language: string; theme: string }): void {
  if (isLanguage(prefs.language)) setLanguage(prefs.language)
  if (isTheme(prefs.theme)) setTheme(prefs.theme)
}

export function useTheme(): Theme {
  return useSyncExternalStore(
    (listener) => {
      listeners.add(listener)
      return () => listeners.delete(listener)
    },
    getTheme,
    getTheme,
  )
}
