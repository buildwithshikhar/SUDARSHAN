import { expect, test } from '@playwright/test'
import { brand } from './brand'
import { choose, PASSWORD, savedPreferences, signIn, signInRaw, type Role } from './helpers'

test.describe('public', () => {
  test('sign-in page shows the brand and the permanent scenario label', async ({ page }) => {
    await page.goto('/')
    await expect(page).toHaveURL(/\/sign-in$/)
    await expect(page).toHaveTitle(brand.productName)
    await expect(page.getByRole('heading', { name: 'Sign in' })).toBeVisible()
    await expect(page.getByText('Fictional scenarios · open-source parameters')).toBeVisible()
  })

  test('About is public and states the data notice', async ({ page }) => {
    await page.goto('/about')
    await expect(page.getByText(/calibrated from open research datasets/)).toBeVisible()
  })

  test('unknown address shows Not found', async ({ page }) => {
    await page.goto('/nothing/here/at/all')
    await expect(page.getByRole('heading', { name: 'Page not found', level: 1 })).toBeVisible()
  })

  test('shows the unreachable screen when the API cannot be reached', async ({ page }) => {
    await page.route('**/api/v1/auth/me', (route) => route.abort())
    await page.goto('/')
    await expect(page.getByRole('alert')).toContainText('Server unreachable')
    await page.unroute('**/api/v1/auth/me')
    await page.getByRole('button', { name: 'Retry' }).click()
    await expect(page.getByRole('heading', { name: 'Sign in' })).toBeVisible()
  })

  test('a wrong password is refused with a uniform message', async ({ page }) => {
    await page.goto('/sign-in')
    await page.getByLabel('Email address').fill('nobody-here@demo.invalid')
    await page.getByLabel('Password').fill('not-the-password')
    await page.getByRole('button', { name: 'Sign in' }).click()
    await expect(page.getByRole('alert')).toContainText('Invalid email or password.')
  })

  test('language and theme persist across a reload while signed out', async ({ page }) => {
    await page.goto('/sign-in')
    await choose(page, 'hi', 'light')
    await page.reload()
    await expect(page.locator('html')).toHaveAttribute('lang', 'hi')
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'light')
  })
})

test.describe('signed in', () => {
  test.skip(!PASSWORD, 'E2E_PASSWORD not set; run through make e2e')

  const expected: Record<Role, { present: string[]; absent: string[]; forbidden: string }> = {
    trainee: {
      present: ['Today', 'Drills'],
      absent: ['Cohorts', 'Backup'],
      forbidden: '/admin/backup',
    },
    instructor: {
      present: ['Cohorts', 'Live sessions'],
      absent: ['Today', 'Backup'],
      forbidden: '/trainee/today',
    },
    admin: {
      present: ['Users and roles', 'Backup'],
      absent: ['Today', 'Cohorts'],
      forbidden: '/instructor/cohorts',
    },
  }

  for (const role of ['trainee', 'instructor', 'admin'] as const) {
    test(`${role}: role-based sidebar, honest empty state and No access`, async ({ page }) => {
      await signIn(page, role)
      const nav = page.getByRole('navigation', { name: 'Main navigation' })
      for (const name of expected[role].present)
        await expect(nav.getByRole('link', { name })).toBeVisible()
      for (const name of expected[role].absent)
        await expect(nav.getByRole('link', { name })).toHaveCount(0)
      await expect(page.getByRole('heading', { name: 'Status', level: 1 })).toBeVisible()
      await nav.getByRole('link', { name: expected[role].present[0] ?? '' }).click()
      await expect(page.getByText(/Arrives in wave \d+[abc]?/)).toBeVisible()
      await page.goto(expected[role].forbidden)
      await expect(page.getByRole('heading', { name: 'No access', level: 1 })).toBeVisible()
    })
  }

  test('sign out ends the session', async ({ page }) => {
    await signIn(page, 'trainee')
    await page.getByRole('button', { name: 'Sign out' }).click()
    await expect(page.getByRole('heading', { name: 'Sign in' })).toBeVisible()
    await page.goto('/status')
    await expect(page).toHaveURL(/\/sign-in$/)
  })

  test('preferences are saved to the account and follow the user to a new browser', async ({
    browser,
  }) => {
    const first = await browser.newPage()
    await signIn(first, 'instructor')
    await choose(first, 'hi', 'light')
    await expect.poll(async () => (await savedPreferences(first)).theme).toBe('light')
    await expect.poll(async () => (await savedPreferences(first)).language).toBe('hi')
    await first.close()
    const second = await browser.newPage()
    await signInRaw(second, 'instructor')
    await expect(second.locator('html')).toHaveAttribute('lang', 'hi')
    await expect(second.locator('html')).toHaveAttribute('data-theme', 'light')
    await choose(second, 'en', 'dark')
    await expect.poll(async () => (await savedPreferences(second)).language).toBe('en')
    await second.close()
  })

  test('the sign-in form and shell are operable by keyboard alone', async ({ page }) => {
    await page.goto('/sign-in')
    await page.keyboard.press('Tab') // skip link
    await page.keyboard.press('Tab') // brand link
    for (let i = 0; i < 4; i += 1) await page.keyboard.press('Tab') // language x2, theme x2
    await expect(page.getByLabel('Email address')).not.toBeFocused()
    await page.keyboard.press('Tab')
    await expect(page.getByLabel('Email address')).toBeFocused()
    await page.keyboard.type('trainee@demo.invalid')
    await page.keyboard.press('Tab')
    await page.keyboard.type(PASSWORD)
    await page.keyboard.press('Enter')
    await expect(page.getByRole('navigation', { name: 'Main navigation' })).toBeVisible()
    await page.keyboard.press('Tab')
    await expect(page.getByRole('link', { name: 'Skip to content' })).toBeFocused()
    await page.keyboard.press('Enter')
    await expect(page).toHaveURL(/#main$/)
  })

  test('the developer components route is available in demo mode', async ({ page }) => {
    await signIn(page, 'admin')
    await page.goto('/dev/components')
    await expect(page.getByRole('heading', { name: 'Components', level: 1 })).toBeVisible()
  })
})
