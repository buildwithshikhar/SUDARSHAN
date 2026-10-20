import AxeBuilder from '@axe-core/playwright'
import { expect, test, type Page } from '@playwright/test'
import { installApi, type Prefs } from './fixtures'

/**
 * Smoke test for the role-based sidebars: signs in as each seat, opens every sidebar item and every
 * tab on it, fails on any console error, and runs axe on each screen for serious and critical issues.
 */
const SEATS = [
  { id: 'trainee', role: 'trainee', team: 'operator' },
  { id: 'commander', role: 'trainee', team: 'commander' },
  { id: 'instructor', role: 'instructor', team: 'operator' },
  { id: 'admin', role: 'admin', team: 'operator' },
] as const satisfies readonly { id: string; role: NonNullable<Prefs['role']>; team: string }[]

async function openAs(page: Page, seat: (typeof SEATS)[number], prefs: Omit<Prefs, 'role'>) {
  const errors: string[] = []
  page.on('console', (message) => {
    if (message.type() === 'error') errors.push(`console: ${message.text()}`)
  })
  page.on('pageerror', (error) => errors.push(`page: ${error.message}`))
  await page.addInitScript((team) => window.localStorage.setItem('ui.teamRole', team), seat.team)
  await installApi(page, { ...prefs, role: seat.role })
  await page.goto('/status?mock=1')
  await expect(page.getByRole('navigation', { name: /Main navigation|मुख्य/ })).toBeVisible()
  return errors
}

async function serious(page: Page) {
  await page.evaluate(() => document.fonts.ready)
  const results = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'])
    .analyze()
  return results.violations
    .filter((v) => v.impact === 'serious' || v.impact === 'critical')
    .map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(' | ')}`)
}

for (const seat of SEATS) {
  test(`${seat.id}: every sidebar item and tab opens a screen without console errors`, async ({
    page,
  }) => {
    test.setTimeout(240_000)
    const errors = await openAs(page, seat, { language: 'en', theme: 'dark' })
    const nav = page.getByRole('navigation', { name: 'Main navigation' })
    const hrefs = await nav
      .getByRole('link')
      .evaluateAll((links) => links.map((a) => a.getAttribute('href') ?? ''))
    expect(hrefs.length).toBeGreaterThan(5)
    const problems: string[] = []
    const heading = page.locator('main h1').first()
    for (const href of hrefs.filter((h) => h !== '/status')) {
      const before = (await heading.textContent()) ?? ''
      // The scenario screens read the scripted API from the address (?mock=1), which a click drops.
      if (href.startsWith('/content/')) await page.goto(`${href}?mock=1`)
      else await nav.locator(`a[href="${href}"]`).click()
      // the router keeps the old screen up until the next one has loaded
      await expect
        .poll(async () => (await heading.textContent()) ?? '', { timeout: 45_000 })
        .not.toBe(before)
      await expect(heading).toBeVisible()
      await expect(page.locator('main')).not.toContainText(/Page not found|No access/)
      const tabs = page.locator('main [role="tab"]')
      const count = await tabs.count()
      for (let i = 0; i < Math.max(count, 1); i += 1) {
        if (count > 0) {
          await tabs.nth(i).click()
          await expect(page.locator('main [role="tabpanel"]:not([hidden])').first()).toBeVisible()
        }
        const found = await serious(page)
        if (found.length > 0) problems.push(`${href} tab ${i}: ${found.join('; ')}`)
      }
    }
    expect(problems).toEqual([])
    expect(errors).toEqual([])
  })
}

test('the sign-in page offers the four seats in demo mode', async ({ page }) => {
  await page.route('**/api/v1/auth/me', (route) =>
    route.fulfill({ status: 401, contentType: 'application/json', body: '{"detail":"x"}' }),
  )
  await page.route('**/api/v1/version', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        productName: 'SUDARSHAN',
        descriptor: 'Counter-UAS Threat Recognition Trainer',
        version: '0.1.0',
        gitSha: 'abc1234',
        buildTime: '2026-10-18T00:00:00Z',
        env: 'demo',
      }),
    }),
  )
  await page.goto('/sign-in')
  const group = page.getByRole('group', { name: 'Open as' })
  for (const name of ['Trainee operator', 'Detachment commander', 'Instructor', 'Administrator'])
    await expect(group.getByRole('button', { name })).toBeVisible()
  await group.getByRole('button', { name: 'Instructor' }).click()
  await expect(page.getByLabel('Email address')).toHaveValue('instructor@demo.invalid')
})

test('Hindi and the light theme render the busiest screens without serious accessibility issues', async ({
  page,
}) => {
  test.setTimeout(120_000)
  const errors = await openAs(page, SEATS[2], { language: 'hi', theme: 'light' })
  for (const path of [
    '/instructor/unit-aar',
    '/instructor/live-sessions?s=monitor',
    '/instructor/rule-packs?s=editor',
  ]) {
    await page.goto(path)
    await expect(page.locator('main h1').first()).toBeVisible()
    expect(await serious(page)).toEqual([])
  }
  expect(errors).toEqual([])
})
