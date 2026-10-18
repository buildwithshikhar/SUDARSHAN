import { expect, test, type Page } from '@playwright/test'
import { MOCK_WELCOME } from '../../src/live/mock'
import { beginSession, installApi, SCENARIO } from './fixtures'

// Screenshots for review, written to a git-ignored folder. They are looked at, not compared:
// the visual baselines for these screens belong to the main session.
const SIZES = [
  { name: '1920x1080', width: 1920, height: 1080 },
  { name: '1366x768', width: 1366, height: 768 },
] as const

const OUT = 'test-results/shots'

async function stage(page: Page) {
  await beginSession(page, 4)
  const row = page.getByRole('button', { name: 'T014' }).locator('xpath=ancestor::tr')
  await expect(row).toContainText(/Confirmed|पुष्ट/, { timeout: 20_000 })
  for (let i = 0; i < 4; i++) await page.keyboard.press('Tab')
  await page.keyboard.press('u')
  await page.keyboard.press('c')
  await page.keyboard.press('1')
  await page.keyboard.press('Enter')
  await page.keyboard.press('1')
  await page.keyboard.press('Enter')
  await page.keyboard.press('2')
  await page.keyboard.press('Enter')
  await expect(page.getByTestId('verdict')).toHaveAttribute('data-permitted', 'false')
  // let the camera settle on the cue and the sweep light some plots
  await page.waitForTimeout(1800)
  await page.keyboard.press('r')
}

for (const size of SIZES) {
  for (const { language, theme } of [
    { language: 'en', theme: 'dark' },
    { language: 'hi', theme: 'light' },
  ] as const) {
    test(`workspace ${language} ${theme} at ${size.name}`, async ({ page }) => {
      await page.setViewportSize({ width: size.width, height: size.height })
      await installApi(page, { language, theme })
      await stage(page)
      await page.screenshot({ path: `${OUT}/workspace-${language}-${theme}-${size.name}.png` })
    })
  }

  test(`lobby at ${size.name}`, async ({ page }) => {
    await page.setViewportSize({ width: size.width, height: size.height })
    await installApi(
      page,
      { language: 'en', theme: 'dark' },
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
    await page.goto('/train/lobby')
    await expect(page.getByRole('button', { name: 'Create session' })).toBeVisible()
    await page.screenshot({ path: `${OUT}/lobby-en-dark-${size.name}.png` })
  })

  test(`session ended at ${size.name}`, async ({ page }) => {
    await page.setViewportSize({ width: size.width, height: size.height })
    await installApi(page, { language: 'en', theme: 'dark' })
    await page.goto('/train/session/mock-session?mock=1&speed=20')
    await page.getByRole('button', { name: 'Begin session' }).waitFor()
    await page.keyboard.press('Enter')
    await expect(page.getByTestId('log-verification')).toBeVisible({ timeout: 30_000 })
    await page.screenshot({ path: `${OUT}/ended-en-dark-${size.name}.png` })
  })
}
