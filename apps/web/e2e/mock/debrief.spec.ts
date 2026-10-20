import { expect, test, type Page } from '@playwright/test'
import {
  debriefUrl,
  expectClean,
  installApi,
  installScore,
  sessionUrl,
  type ScoreReply,
} from './fixtures'

const OUT = 'test-results/shots'
const SIZES = [
  { name: '1920x1080', width: 1920, height: 1080 },
  { name: '1366x768', width: 1366, height: 768 },
] as const

async function open(
  page: Page,
  prefs: { language: 'en' | 'hi'; theme: 'dark' | 'light' },
  reply: ScoreReply = 'populated',
) {
  await installApi(page, prefs)
  const score = await installScore(page, reply)
  await page.goto(debriefUrl)
  return score
}

test.describe('debrief against the scripted score', () => {
  test('shows the record, the summary, the lessons and each contact', async ({ page }) => {
    await open(page, { language: 'en', theme: 'dark' })
    await expect(page.getByRole('heading', { name: 'Debrief', level: 1 })).toBeVisible()
    await expect(page.getByText('Harrier Field: afternoon watch').first()).toBeVisible()
    await expect(
      page.getByText('Built on published specifications and open research.'),
    ).toBeVisible()
    await expect(
      page.getByRole('table', { name: 'Session score and decision score' }),
    ).toContainText('34.6%')
    await expect(page.getByTestId('sdt-corrected')).toBeVisible()
    await expect(page.getByTestId('lesson')).toHaveCount(3)
    await expect(
      page.getByRole('heading', { name: 'Contact quad: Small rotary, hostile' }),
    ).toBeVisible()
    await expect(page.getByTestId('hard-fail')).toContainText(
      'Hard fail: rules of engagement breached',
    )
    await expect(page.getByTestId('report-grades')).toContainText('212 m off')
    await expect(page.getByTestId('not-scored')).toContainText('Contact flock: Bird, clutter')
    // every table has a caption
    const tables = page.getByRole('table')
    for (let i = 0; i < (await tables.count()); i++) {
      expect(await tables.nth(i).locator('caption').count()).toBe(1)
    }
  })

  test('is reached from the ended session with the mock query kept, and serves the scripted score', async ({
    page,
  }) => {
    await installApi(page, { language: 'en', theme: 'dark' })
    await page.goto(sessionUrl(20))
    await page.getByRole('button', { name: 'Begin session' }).waitFor()
    await page.keyboard.press('Enter')
    await expect(page.getByTestId('log-verification')).toBeVisible({ timeout: 30_000 })
    await page.getByTestId('open-debrief').click()
    await expect(page).toHaveURL(/\/train\/session\/mock-session\/debrief\?mock=1/)
    await expect(page.getByTestId('lesson')).toHaveCount(3)
  })

  test('says the session has not ended on a 409', async ({ page }) => {
    await open(page, { language: 'en', theme: 'dark' }, 'not-ended')
    const failure = page.getByTestId('debrief-failure')
    await expect(failure).toContainText('The session has not ended')
    await expect(failure).toHaveAttribute('data-failure', 'notEnded')
    await expectClean(page)
  })

  test('says there is no record on a 404', async ({ page }) => {
    await open(page, { language: 'en', theme: 'dark' }, 'not-found')
    await expect(page.getByTestId('debrief-failure')).toContainText(
      'No scored record for this session',
    )
    await expectClean(page)
  })

  test('says the server could not be reached on a network failure', async ({ page }) => {
    await open(page, { language: 'en', theme: 'dark' }, 'network')
    await expect(page.getByTestId('debrief-failure')).toContainText(
      'The server could not be reached',
    )
    await expectClean(page)
  })

  test('shows a loading state, then the record', async ({ page }) => {
    const score = await open(page, { language: 'en', theme: 'dark' }, 'slow')
    await expect(page.getByText('Reading the scored record')).toBeAttached()
    await expect(page.getByTestId('debrief-loading')).toBeVisible()
    await expectClean(page)
    score.release()
    await expect(page.getByTestId('lesson')).toHaveCount(3)
  })

  test('shows an empty state when no contact was presented', async ({ page }) => {
    await open(page, { language: 'en', theme: 'dark' }, 'empty')
    await expect(page.getByText('No contact was presented')).toBeVisible()
    await expectClean(page)
    await page.screenshot({ path: `${OUT}/debrief-empty-en-dark-1920x1080.png`, fullPage: true })
  })
})

const combos = [
  { language: 'en', theme: 'dark' },
  { language: 'en', theme: 'light' },
  { language: 'hi', theme: 'dark' },
  { language: 'hi', theme: 'light' },
] as const

for (const { language, theme } of combos) {
  test.describe(`debrief: ${language}, ${theme}`, () => {
    test('is axe-clean', async ({ page }) => {
      await open(page, { language, theme })
      await expect(page.getByTestId('lesson')).toHaveCount(3)
      await expect(page.locator('html')).toHaveAttribute('data-theme', theme)
      await expect(page.locator('html')).toHaveAttribute('lang', language)
      await expectClean(page)
    })

    for (const size of SIZES) {
      test(`screenshot at ${size.name}`, async ({ page }) => {
        await page.setViewportSize({ width: size.width, height: size.height })
        await open(page, { language, theme })
        await expect(page.getByTestId('lesson')).toHaveCount(3)
        await page.evaluate(() => document.fonts.ready)
        await page.screenshot({
          path: `${OUT}/debrief-${language}-${theme}-${size.name}.png`,
          fullPage: true,
        })
      })
    }
  })
}
