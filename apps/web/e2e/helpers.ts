import { expect, type Page } from '@playwright/test'

export type Role = 'trainee' | 'instructor' | 'admin'
export const PASSWORD = process.env.E2E_PASSWORD ?? ''
export const email = (role: Role) => `${role}@demo.invalid`

export const LANGUAGES = [
  { code: 'en', button: 'English' },
  { code: 'hi', button: 'हिन्दी' },
] as const
export const THEMES = [
  { code: 'dark', en: 'Dark', hi: 'गहरा' },
  { code: 'light', en: 'Light', hi: 'हल्का' },
] as const

/** Sign in and leave the page on whatever language and theme the account has saved. */
export async function signInRaw(page: Page, role: Role) {
  await page.goto('/sign-in')
  // start from the default language so the form labels below are in English
  await page.evaluate(() => window.localStorage.clear())
  await page.reload()
  await page.getByLabel('Email address').fill(email(role))
  await page.getByLabel('Password').fill(PASSWORD)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page.locator('nav').first()).toBeVisible()
}

/** Sign in, then normalise to English and dark so tests do not depend on saved preferences. */
export async function signIn(page: Page, role: Role) {
  await signInRaw(page, role)
  await choose(page, 'en', 'dark', true)
}

/** Pick language and theme; with `saved`, also wait until the account has stored them. */
export async function choose(
  page: Page,
  language: 'en' | 'hi',
  theme: 'dark' | 'light',
  saved = false,
) {
  await page.getByRole('button', { name: language === 'en' ? 'English' : 'हिन्दी' }).click()
  const label = THEMES.find((t) => t.code === theme)?.[language] ?? ''
  await page.getByRole('button', { name: label, exact: true }).click()
  await expect(page.locator('html')).toHaveAttribute('data-theme', theme)
  await expect(page.locator('html')).toHaveAttribute('lang', language)
  await page.evaluate(() => document.fonts.ready)
  if (saved) {
    await expect.poll(async () => (await savedPreferences(page)).language).toBe(language)
    await expect.poll(async () => (await savedPreferences(page)).theme).toBe(theme)
  }
}

/** The preferences stored on the signed-in account, read from the API. */
export async function savedPreferences(page: Page) {
  const response = await page.request.get('/api/v1/auth/me')
  const body = (await response.json()) as { user: { language: string; theme: string } }
  return body.user
}
