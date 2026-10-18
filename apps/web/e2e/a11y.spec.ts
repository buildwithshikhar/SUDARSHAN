import AxeBuilder from '@axe-core/playwright'
import { expect, test, type Page } from '@playwright/test'
import { choose, LANGUAGES, PASSWORD, signIn, THEMES, type Role } from './helpers'

async function expectClean(page: Page) {
  await page.evaluate(() => document.fonts.ready)
  const results = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'])
    .analyze()
  expect(
    results.violations.map(
      (v) =>
        `${v.id}: ${v.nodes.map((n) => `${n.target.join(' ')} ${JSON.stringify(n.any[0]?.data ?? {})}`).join(', ')}`,
    ),
  ).toEqual([])
}

const publicPages = [
  { name: 'sign in', path: '/sign-in' },
  { name: 'about', path: '/about' },
  { name: 'not found', path: '/no/such/page' },
  { name: 'offline', path: '/offline' },
]

const roleModule: Record<Role, string> = {
  trainee: '/trainee/today',
  instructor: '/instructor/cohorts',
  admin: '/admin/backup',
}

for (const language of LANGUAGES) {
  for (const theme of THEMES) {
    const combo = `${language.code}, ${theme.code}`

    test.describe(`axe: ${combo}`, () => {
      for (const target of publicPages) {
        test(`${target.name}`, async ({ page }) => {
          await page.goto(target.path)
          await choose(page, language.code, theme.code)
          await expectClean(page)
        })
      }

      test.describe('signed in', () => {
        test.skip(!PASSWORD, 'E2E_PASSWORD not set; run through make e2e')

        for (const role of ['trainee', 'instructor', 'admin'] as const) {
          test(`${role}: status, module empty state, profile`, async ({ page }) => {
            await signIn(page, role)
            await choose(page, language.code, theme.code, true)
            await expectClean(page)
            await page.goto(roleModule[role])
            await expect(page.getByRole('main')).toBeVisible()
            await expectClean(page)
            await page.goto('/account/profile')
            await expect(page.getByRole('tablist')).toBeVisible()
            await expectClean(page)
            await page.getByRole('tab').nth(1).click()
            await expectClean(page)
          })
        }

        test('no access and components', async ({ page }) => {
          await signIn(page, 'trainee')
          await choose(page, language.code, theme.code, true)
          await page.goto('/admin/backup')
          await expect(page.getByRole('main')).toBeVisible()
          await expectClean(page)
          await page
            .getByRole('button', { name: language.code === 'en' ? 'Sign out' : 'साइन आउट' })
            .click()
          await signIn(page, 'admin')
          await choose(page, language.code, theme.code, true)
          await page.goto('/dev/components')
          await expect(page.getByRole('heading', { name: 'Components', level: 1 })).toBeVisible()
          await expectClean(page)
        })
      })
    })
  }
}
