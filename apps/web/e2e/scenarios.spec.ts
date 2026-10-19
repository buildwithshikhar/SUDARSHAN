import AxeBuilder from '@axe-core/playwright'
import { expect, test, type Page } from '@playwright/test'
import { PASSWORD, signIn } from './helpers'

// The instructor's scenario screens on the real stack: the library with the curriculum, the editor
// running the oracle defender on a shipped scenario, and the generator studio making one.
test.skip(!PASSWORD, 'E2E_PASSWORD not set; run through make e2e')
test.use({ viewport: { width: 1920, height: 1080 } })
test.setTimeout(240_000)

async function expectClean(page: Page) {
  await page.evaluate(() => document.fonts.ready)
  const results = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'])
    .analyze()
  expect(
    results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(', ')}`),
  ).toEqual([])
}

test('the library lists the curriculum and the shipped scenarios, axe-clean', async ({ page }) => {
  await signIn(page, 'instructor')
  await page.goto('/content/scenarios')
  await expect(page.getByRole('heading', { name: 'Scenario library', level: 1 })).toBeVisible()
  const table = page.getByRole('table', { name: 'Scenarios held by this instance' })
  await expect(table.getByText('curriculum-01-first-contact')).toBeVisible()
  await expect(table.getByText('harrier-morning-watch')).toBeVisible()
  await expect(page.getByText(/provably|guaranteed/i)).toHaveCount(0)
  await expectClean(page)
})

test('a trainee cannot open the scenario tools', async ({ page }) => {
  await signIn(page, 'trainee')
  await page.goto('/content/scenarios')
  await expect(page.getByRole('heading', { name: 'No access', level: 1 })).toBeVisible()
})

test('the editor validates a shipped scenario and the oracle verifies it solvable by test run', async ({
  page,
}) => {
  await signIn(page, 'instructor')
  await page.goto('/content/scenarios/editor/curriculum-01-first-contact')
  await expect(page.getByTestId('validation-summary')).toHaveAttribute('data-valid', 'true', {
    timeout: 30_000,
  })
  await page.getByRole('button', { name: 'Run checks' }).click()
  const result = page.getByTestId('check-result')
  await expect(result).toBeVisible({ timeout: 120_000 })
  await expect(result).toContainText(/verified solvable by test run/i)
  await page.getByRole('button', { name: 'Run preview' }).click()
  await expect(page.getByTestId('preview-map')).toBeVisible({ timeout: 120_000 })
  await expectClean(page)
})

test('the editor reports a broken scenario with its line number', async ({ page }) => {
  await signIn(page, 'instructor')
  await page.goto('/content/scenarios/editor/curriculum-01-first-contact')
  const text = page.getByLabel('Scenario YAML text')
  await expect(text).toHaveValue(/scenario\.v1/, { timeout: 30_000 })
  const value = await text.inputValue()
  await text.fill(value.replace(/duration_s: .*/, 'duration_s: not-a-number'))
  await expect(page.getByTestId('validation-summary')).toHaveAttribute('data-valid', 'false')
  const line = value.split('\n').findIndex((l) => l.startsWith('duration_s:')) + 1
  await expect(
    page.getByTestId('gutter').locator(`[data-line="${line}"][data-marker="error"]`),
  ).toBeVisible()
})

test('the generator studio makes a scenario verified solvable by test run and shows the archive', async ({
  page,
}) => {
  await signIn(page, 'instructor')
  await page.goto('/content/generator')
  await expect(page.getByRole('heading', { name: 'Generator studio', level: 1 })).toBeVisible()
  await page.getByLabel('Seed', { exact: true }).fill('4242')
  await page.getByRole('button', { name: 'Generate', exact: true }).click()
  await expect(page.getByTestId('result')).toBeVisible({ timeout: 180_000 })
  await expect(page.getByTestId('result-wording')).toHaveText(/verified solvable by test run/i)
  await expect(page.getByTestId('result-code')).toHaveText(/^SD1-/)
  await expect(page.getByTestId('heat-map')).toBeVisible()
  await expectClean(page)
})
