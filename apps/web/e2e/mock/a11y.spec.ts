import { expect, test } from '@playwright/test'
import { beginSession, expectClean, installApi, sessionUrl, SCENARIO } from './fixtures'
import { MOCK_WELCOME } from '../../src/live/mock'

const combos = [
  { language: 'en', theme: 'dark' },
  { language: 'en', theme: 'light' },
  { language: 'hi', theme: 'dark' },
  { language: 'hi', theme: 'light' },
] as const

for (const { language, theme } of combos) {
  test.describe(`axe: ${language}, ${theme}`, () => {
    test.beforeEach(async ({ page }) => {
      await installApi(
        page,
        { language, theme },
        {
          scenarios: [
            {
              ...SCENARIO,
              briefing: MOCK_WELCOME.briefing,
              rule_pack: {
                id: 'training-baseline',
                version: '1.0.0',
                title: MOCK_WELCOME.rules.title,
              },
            },
          ],
        },
      )
    })

    test('session lobby', async ({ page }) => {
      await page.goto('/train/lobby')
      await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
      await expect(page.getByRole('table').first()).toBeVisible()
      await expect(page.locator('html')).toHaveAttribute('data-theme', theme)
      await expect(page.locator('html')).toHaveAttribute('lang', language)
      await expectClean(page)
    })

    test('workspace before the session begins', async ({ page }) => {
      await page.goto(sessionUrl())
      await expect(page.getByRole('button', { name: /Begin session|सत्र आरंभ करें/ })).toBeFocused()
      await expectClean(page)
    })

    test('workspace running, with a blocked response and an open step', async ({ page }) => {
      await beginSession(page, 4)
      for (let i = 0; i < 4; i++) await page.keyboard.press('Tab')
      await page.keyboard.press('r')
      await page.keyboard.press('2')
      await page.keyboard.press('Enter')
      await expect(page.getByTestId('verdict')).toHaveAttribute('data-permitted', 'false')
      await page.keyboard.press('c')
      await page.keyboard.press('1')
      await expect(page.getByRole('list').first()).toBeVisible()
      await expectClean(page)
    })

    test('workspace with the shortcut dialog open', async ({ page }) => {
      await beginSession(page, 4)
      await page.keyboard.press('?')
      await expect(page.getByRole('dialog')).toBeVisible()
      await expectClean(page)
    })

    test('workspace at 1366 by 768', async ({ page }) => {
      await page.setViewportSize({ width: 1366, height: 768 })
      await beginSession(page, 4)
      await page.keyboard.press('Tab')
      await expectClean(page)
    })

    test('session ended', async ({ page }) => {
      await page.goto(sessionUrl(20))
      await page.getByRole('button', { name: /Begin session|सत्र आरंभ करें/ }).waitFor()
      await page.keyboard.press('Enter')
      await expect(page.getByTestId('log-verification')).toBeVisible({ timeout: 30_000 })
      await expectClean(page)
    })
  })
}

test('lobby has an empty state, an error state and a loading state that are axe-clean', async ({
  page,
}) => {
  await installApi(page, { language: 'en', theme: 'dark' }, { scenarios: [] })
  await page.goto('/train/lobby')
  await expect(page.getByText('No scenarios available')).toBeVisible()
  await expectClean(page)
  await page.unroute('**/api/v1/scenarios')
  await page.route('**/api/v1/scenarios', (route) => route.fulfill({ status: 500, body: '{}' }))
  await page.reload()
  await expect(page.getByText('Scenarios could not be loaded')).toBeVisible()
  await expectClean(page)
})
