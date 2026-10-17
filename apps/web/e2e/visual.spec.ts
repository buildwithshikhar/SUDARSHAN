import { expect, test } from '@playwright/test'
import { choose, PASSWORD, signIn } from './helpers'

// Run with `make visual`. Baselines are per platform (e2e/__screenshots__/<platform>/).
test.use({ viewport: { width: 1440, height: 900 } })

const options = { maxDiffPixelRatio: 0.02, animations: 'disabled' as const }

test('sign in @visual', async ({ page }) => {
  await page.goto('/sign-in')
  await choose(page, 'en', 'dark')
  await expect(page).toHaveScreenshot('sign-in-en-dark.png', options)
  await choose(page, 'hi', 'light')
  await expect(page).toHaveScreenshot('sign-in-hi-light.png', options)
})

test('about @visual', async ({ page }) => {
  await page.goto('/about')
  await choose(page, 'en', 'dark')
  await expect(page).toHaveScreenshot('about-en-dark.png', options)
})

test('shell @visual', async ({ page }) => {
  test.skip(!PASSWORD, 'E2E_PASSWORD not set; run through make visual')
  await signIn(page, 'instructor')
  await choose(page, 'en', 'dark', true)
  const dynamic = [page.locator('dd'), page.getByRole('contentinfo')]
  await expect(page).toHaveScreenshot('shell-instructor-en-dark.png', { ...options, mask: dynamic })
  await choose(page, 'hi', 'light', true)
  await expect(page).toHaveScreenshot('shell-instructor-hi-light.png', {
    ...options,
    mask: dynamic,
  })
  await choose(page, 'en', 'dark', true)
})
