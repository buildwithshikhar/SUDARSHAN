import AxeBuilder from '@axe-core/playwright'
import { expect, test, type Page } from '@playwright/test'
import { choose, PASSWORD, signIn } from './helpers'

// Plays a short session on the real stack, files a contact report from the keyboard, ends it and
// reads the scored debrief. The session runs in real time.
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

interface Score {
  contract: string
  scenario: { id: string; version: string }
  scenario_title: { en: string; hi: string }
  rule_pack: { id: string; version: string }
  report_weight: number
  seed: number
  event_head: string
  threats: { threat_id: string; presented: boolean; worked?: boolean; score: number | null }[]
  sdt: { signal_trials: number; noise_trials: number }
  lessons: unknown[]
  score: number | null
}

test('a trainee files a report, ends the session and reads the scored debrief', async ({
  page,
}) => {
  await signIn(page, 'trainee')
  await page.goto('/train/lobby')
  await page.getByRole('button', { name: 'Create session' }).click()
  await expect(page).toHaveURL(/\/train\/session\/[0-9a-f-]{36}$/)
  const id = page.url().split('/').pop() ?? ''
  await expect(page.getByRole('button', { name: 'Begin session' })).toBeFocused()
  await page.keyboard.press('Enter')

  // work the first confirmed track: classify, assess, then file a contact report
  const table = page.getByRole('table', { name: 'Tracks held by the tracker' })
  await expect(table.locator('tbody tr').filter({ hasText: 'Confirmed' }).first()).toBeVisible({
    timeout: 90_000,
  })
  await page.keyboard.press('Tab')
  const trackId = ((await table.getByRole('button', { pressed: true }).textContent()) ?? '').trim()
  expect(trackId).toMatch(/^T\d+$/)
  await page.keyboard.press('c')
  await page.keyboard.press('3') // Bird
  await page.keyboard.press('Enter')
  await expect(page.getByText(/You classified .* as Bird\./)).toBeVisible({ timeout: 15_000 })
  await page.keyboard.press('4') // Neutral
  await page.keyboard.press('Enter')
  await expect(page.getByText(/You assessed .* as Neutral\./)).toBeVisible({ timeout: 15_000 })
  await page.keyboard.press('r')
  await page.keyboard.press('3') // Report up the chain
  await page.keyboard.press('Enter')
  const form = page.getByRole('dialog', { name: `Contact report: ${trackId}` })
  await expect(form).toBeVisible()
  await expect(form.getByLabel('Bearing (°)')).toHaveValue(/^\d{1,3}$/) // prefilled from the track
  await page.keyboard.press('3') // Bird
  for (let i = 0; i < 5; i++) await page.keyboard.press('Tab')
  await page.keyboard.type('60')
  await page.keyboard.press('Enter')
  await expect(form).toBeHidden()
  await expect(page.getByText(new RegExp(`${trackId} reported: Bird, count 1`))).toBeVisible({
    timeout: 15_000,
  })

  // end the session from the keyboard and follow the way into the debrief
  await page.keyboard.press('x')
  await page.getByRole('button', { name: 'End session' }).focus()
  await page.keyboard.press('Enter')
  const confirm = page.getByRole('dialog', { name: 'End the session?' })
  await confirm.getByRole('button', { name: 'End session' }).focus()
  await page.keyboard.press('Enter')
  await expect(page.getByText('Event log verified')).toBeVisible({ timeout: 30_000 })
  await page.getByRole('link', { name: 'Open the debrief' }).focus()
  await page.keyboard.press('Enter')
  await expect(page).toHaveURL(new RegExp(`/train/session/${id}/debrief$`))

  const debrief = page.getByTestId('debrief')
  await expect(debrief).toBeVisible({ timeout: 15_000 })
  await expect(page.getByRole('heading', { name: 'Debrief', level: 1 })).toBeVisible()
  await expect(debrief).toContainText('training-baseline 1.0.0')
  await expect(debrief).toContainText('Harrier Field: morning watch')
  await expect(page.getByRole('heading', { name: 'Score summary' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'First three lessons' })).toBeVisible()

  // what the screen shows is what the server stored
  const response = await page.request.get(`/api/v1/sessions/${id}/score`)
  expect(response.ok()).toBe(true)
  const score = (await response.json()) as Score
  expect(score.contract).toBe('score-result.v1')
  expect(score.scenario).toEqual({ id: 'harrier-morning-watch', version: '1.0.0' })
  expect(score.rule_pack).toEqual({ id: 'training-baseline', version: '1.0.0' })
  expect(score.report_weight).toBe(0.15)
  expect(debrief).toContainText(String(score.seed))
  const log = (await (await page.request.get(`/api/v1/sessions/${id}/log`)).json()) as {
    head: string
    events: { type: string; payload: Record<string, unknown> }[]
  }
  expect(score.event_head).toBe(log.head)
  // the report is in the trainee's log with its fields, and without the ground truth
  const filed = log.events.find((e) => e.type === 'action.report')
  expect(filed?.payload.class_id).toBe('bird')
  expect(filed?.payload.confidence).toBeCloseTo(0.6)
  expect(JSON.stringify(log)).not.toMatch(/"truth"|"target"|contact-/)
  // every scored contact has its four nodes on screen
  for (const contact of await page.getByTestId('contact').all()) {
    await expect(contact.locator('tbody tr').first()).toBeVisible()
  }
  await expectClean(page)

  // a stranger cannot read it
  const other = await page.context().browser()!.newContext()
  const stranger = await other.newPage()
  await signIn(stranger, 'instructor')
  expect((await stranger.request.get(`/api/v1/sessions/${id}/score`)).status()).toBe(404)
  await other.close()

  // the same debrief in Hindi, light theme
  await page.goto('/profile')
  await choose(page, 'hi', 'light', true)
  await page.goto(`/train/session/${id}/debrief`)
  await expect(page.getByTestId('debrief')).toBeVisible({ timeout: 15_000 })
  await expect(page.locator('html')).toHaveAttribute('lang', 'hi')
  await expect(page.getByTestId('debrief')).not.toContainText('{{')
  await expectClean(page)
  await page.goto('/profile')
  await choose(page, 'en', 'dark', true)
})

test('the debrief of a session that has not ended says so', async ({ page }) => {
  await signIn(page, 'trainee')
  const me = (await (await page.request.get('/api/v1/auth/me')).json()) as { csrf: string }
  const created = await page.request.post('/api/v1/sessions', {
    headers: { 'X-CSRF-Token': me.csrf },
    data: { scenario_id: 'harrier-morning-watch' },
  })
  const { id } = (await created.json()) as { id: string }
  await page.goto(`/train/session/${id}/debrief`)
  await expect(page.getByTestId('debrief-failure')).toHaveAttribute('data-failure', 'notEnded')
  await expectClean(page)
})
