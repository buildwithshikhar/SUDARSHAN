import AxeBuilder from '@axe-core/playwright'
import { expect, test, type Page } from '@playwright/test'
import { choose, PASSWORD, signIn } from './helpers'

// Plays the scripted Harrier Field scenario against the real stack (nginx, API, Postgres) with the
// keyboard only. The session runs in real time, so these tests take a minute or two.
test.skip(!PASSWORD, 'E2E_PASSWORD not set; run through make e2e')
test.use({ viewport: { width: 1920, height: 1080 } })
test.setTimeout(240_000)

async function expectClean(page: Page) {
  await page.evaluate(() => document.fonts.ready)
  const results = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'])
    .analyze()
  expect(
    results.violations.map(
      (v) => `${v.id}: ${v.nodes.map((n) => `${n.target.join(' ')}`).join(', ')}`,
    ),
  ).toEqual([])
}

/** Sign in as a trainee, create a session of the first scenario and begin it from the keyboard. */
async function startSession(page: Page, errors?: string[]): Promise<string> {
  await signIn(page, 'trainee')
  errors?.splice(0) // the 401 from checking for a session before signing in is expected
  await page.goto('/train/lobby')
  await expect(page.getByRole('heading', { name: 'Session lobby' })).toBeVisible()
  await expect(page.getByText('training-baseline 1.0.0').first()).toBeVisible()
  await page.getByRole('button', { name: 'Create session' }).click()
  await expect(page).toHaveURL(/\/train\/session\/[0-9a-f-]{36}$/)
  const id = page.url().split('/').pop() ?? ''
  const begin = page.getByRole('button', { name: 'Begin session' })
  await expect(begin).toBeFocused()
  await page.keyboard.press('Enter')
  return id
}

/** The first confirmed track in the table, as its row. */
async function firstConfirmed(page: Page) {
  const rows = page.getByRole('table', { name: 'Tracks held by the tracker' }).locator('tbody tr')
  const confirmed = rows.filter({ hasText: 'Confirmed' }).first()
  await expect(confirmed).toBeVisible({ timeout: 90_000 })
  return confirmed
}

test('a trainee plays the scenario by keyboard: cue, relabel, a blocked response, finish, verify', async ({
  page,
}) => {
  const consoleErrors: string[] = []
  page.on('console', (message) => {
    if (message.type() === 'error') consoleErrors.push(message.text())
  })
  const id = await startSession(page, consoleErrors)

  // the top bar carries the permanent label, the rule pack and its version
  await expect(page.getByText('Fictional scenario · open-source parameters')).toBeVisible()
  await expect(page.getByText(/training-baseline/).first()).toBeVisible()

  await firstConfirmed(page)
  await page.keyboard.press('Tab') // selects the first track
  const selected = page
    .getByRole('table', { name: 'Tracks held by the tracker' })
    .getByRole('button', { pressed: true })
  await expect(selected).toBeVisible()
  const trackId = ((await selected.textContent()) ?? '').trim()
  expect(trackId).toMatch(/^T\d+$/)

  // 1. cue the EO sensor onto the track: logged by the server, shown in the log
  await page.keyboard.press('u')
  await expect(
    page.getByText(new RegExp(`Cue (accepted|refused): eo-1 onto ${trackId}`)),
  ).toBeVisible({ timeout: 15_000 })

  // 2. relabel the track: the table changes
  await page.keyboard.press('l')
  const dialog = page.getByRole('dialog', { name: `Relabel track ${trackId}` })
  await expect(dialog).toBeVisible()
  await dialog.getByLabel('New label').fill('ALPHA-1')
  await page.keyboard.press('Enter')
  const table = page.getByRole('table', { name: 'Tracks held by the tracker' })
  await expect(table.getByRole('button', { name: 'ALPHA-1' })).toBeVisible({ timeout: 15_000 })
  await expect(page.getByText(new RegExp(`Track ${trackId} relabelled 'ALPHA-1'`))).toBeVisible()

  // 3. classify and assess as neutral, then try a response: the rules block it and say why
  await page.keyboard.press('c')
  await expect(page.getByRole('list', { name: 'Classify' })).toBeVisible()
  await page.keyboard.press('3') // Bird
  await page.keyboard.press('Enter')
  await expect(page.getByText(/You classified .* as Bird\./)).toBeVisible({ timeout: 15_000 })
  await expect(page.getByRole('list', { name: 'Assess' })).toBeVisible()
  await page.keyboard.press('4') // Neutral
  await page.keyboard.press('Enter')
  await expect(page.getByText(/You assessed .* as Neutral\./)).toBeVisible({ timeout: 15_000 })
  await expect(page.getByRole('list', { name: 'Respond' })).toBeVisible()
  await page.keyboard.press('1')
  await page.keyboard.press('Enter')
  const verdict = page.getByTestId('verdict')
  await expect(verdict).toHaveAttribute('data-permitted', 'false', { timeout: 15_000 })
  await expect(verdict).toContainText('BLOCKED')
  await expect(verdict).toContainText('Suspect contact in the outer zone may receive a class A')
  await expect(verdict).toContainText('training-baseline 1.0.0')
  await expect(verdict).toContainText('Identity')
  await expectClean(page)

  // 4. the workspace is axe-clean in Hindi light too, with tracks on screen
  // (checked below on a fresh page load to keep this run in English)

  // 5. end the session from the keyboard; the stored log verifies
  await page.keyboard.press('x')
  await page.getByRole('button', { name: 'End session' }).focus()
  await page.keyboard.press('Enter')
  const confirm = page.getByRole('dialog', { name: 'End the session?' })
  await expect(confirm).toBeVisible()
  await confirm.getByRole('button', { name: 'End session' }).focus()
  await page.keyboard.press('Enter')
  await expect(page.getByText('Event log verified')).toBeVisible({ timeout: 30_000 })

  // 6. the server's log holds what the UI showed, and nothing it should not
  const response = await page.request.get(`/api/v1/sessions/${id}/log`)
  expect(response.ok()).toBe(true)
  const log = (await response.json()) as {
    verified: boolean
    events: { type: string; payload: Record<string, unknown> }[]
  }
  expect(log.verified).toBe(true)
  const types = log.events.map((e) => e.type)
  expect(types).toContain('track.relabel')
  expect(types).toContain('sensor.cue')
  expect(types).toContain('action.classify')
  expect(types).toContain('session.end')
  const blocked = log.events.find((e) => e.type === 'roe.verdict' && e.payload.permitted === false)
  expect(blocked?.payload.pack_version).toBe('1.0.0')
  expect(JSON.stringify(log)).not.toMatch(/contact-|truth|disposition/)
  expect(consoleErrors).toEqual([])
})

test('the workspace is axe-clean in Hindi light with tracks on screen', async ({ page }) => {
  await signIn(page, 'trainee')
  await choose(page, 'hi', 'light', true)
  // create the session through the API (the lobby's button is in Hindi here), then play from the page
  const me = (await (await page.request.get('/api/v1/auth/me')).json()) as { csrf: string }
  const created = await page.request.post('/api/v1/sessions', {
    headers: { 'X-CSRF-Token': me.csrf },
    data: { scenario_id: 'harrier-morning-watch' },
  })
  expect(created.ok()).toBe(true)
  const { id } = (await created.json()) as { id: string }
  await page.goto(`/train/session/${id}`)
  await expect(page.locator('html')).toHaveAttribute('lang', 'hi')
  await expect(page.getByRole('button').first()).toBeVisible()
  await page.keyboard.press('Enter') // the begin button holds the focus
  await expect(page.locator('table tbody tr').filter({ hasText: /\d/ }).first()).toBeVisible({
    timeout: 90_000,
  })
  await expectClean(page)
  // restore the account's preferences for the tests that follow (the workspace has no switcher)
  const restored = await page.request.patch('/api/v1/auth/me/preferences', {
    headers: { 'X-CSRF-Token': me.csrf },
    data: { language: 'en', theme: 'dark' },
  })
  expect(restored.ok()).toBe(true)
})

test('a trainee cannot open another account’s session', async ({ page, browser }) => {
  const id = await startSession(page)
  const other = await browser.newContext()
  const stranger = await other.newPage()
  await signIn(stranger, 'instructor')
  const response = await stranger.request.get(`/api/v1/sessions/${id}`)
  expect(response.status()).toBe(404)
  await other.close()
})
