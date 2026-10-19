import { expect, test, type Page } from '@playwright/test'
import en from '../../src/i18n/en.json' with { type: 'json' }
import hi from '../../src/i18n/hi.json' with { type: 'json' }
import { MOCK_WELCOME } from '../../src/live/mock'
import { beginSession, expectClean, installApi, variantUrl } from './fixtures'

test.use({ viewport: { width: 1920, height: 1080 } })

const CLASSES = MOCK_WELCOME.operator_classes
const label = (lang: typeof en, id: string): string =>
  (lang.live.class as Record<string, string>)[id] ?? ''

/** The tracks are T011 to T014 in the order they start; four Tabs select T014. */
async function selectHostile(page: Page) {
  for (let i = 0; i < 4; i++) await page.keyboard.press('Tab')
  await expect(page.getByRole('button', { name: 'T014', pressed: true })).toBeVisible()
}

test.describe('nine classes in the Classify step', () => {
  test('the welcome offers nine classes in a fixed order, each with an English and a Hindi label', () => {
    expect(CLASSES).toEqual([
      'rotary-small',
      'fixed-wing-small',
      'bird',
      'unknown',
      'fpv-small',
      'fixed-wing-medium',
      'fixed-wing-large',
      'kite',
      'balloon',
    ])
    for (const id of CLASSES) {
      expect(label(en, id), id).not.toBe('')
      expect(label(hi, id), id).not.toBe('')
    }
  })

  test('keys 1 to 9 each choose and commit their class, by keyboard only', async ({ page }) => {
    await installApi(page, { language: 'en', theme: 'dark' })
    await beginSession(page, 4)
    await selectHostile(page)
    for (const [index, id] of CLASSES.entries()) {
      await page.keyboard.press('c')
      const list = page.getByRole('list', { name: 'Classify' })
      await expect(list.getByRole('listitem')).toHaveCount(9)
      await page.keyboard.press(String(index + 1))
      await expect(list.getByRole('button', { pressed: true })).toContainText(label(en, id))
      await page.keyboard.press('Enter')
      await expect(page.getByText(`You classified T014 as ${label(en, id)}.`)).toBeVisible()
      await expect(page.getByRole('list', { name: 'Assess' })).toBeVisible()
    }
  })

  test('a zero key does nothing, and the ninth option is reachable at 1366 by 768', async ({
    page,
  }) => {
    await installApi(page, { language: 'en', theme: 'dark' })
    await page.setViewportSize({ width: 1366, height: 768 })
    await beginSession(page, 4)
    await selectHostile(page)
    await page.keyboard.press('c')
    await page.keyboard.press('0')
    const list = page.getByRole('list', { name: 'Classify' })
    await expect(list.getByRole('button', { pressed: true })).toHaveCount(0)
    await page.keyboard.press('9')
    const ninth = list.getByRole('button', { name: /Balloon/ })
    await expect(ninth).toHaveAttribute('aria-pressed', 'true')
    await ninth.scrollIntoViewIfNeeded()
    await expect(ninth).toBeInViewport()
  })

  for (const language of ['en', 'hi'] as const) {
    test(`lists all nine labels and is axe-clean in ${language}`, async ({ page }) => {
      await installApi(page, { language, theme: 'dark' })
      await beginSession(page, 4)
      await selectHostile(page)
      await page.keyboard.press('c')
      await page.keyboard.press('9')
      const strings = language === 'en' ? en : hi
      const list = page.getByRole('list').filter({ hasText: label(strings, 'balloon') })
      for (const id of CLASSES) await expect(list.first()).toContainText(label(strings, id))
      await expectClean(page)
    })
  }
})

/** Cue the EO sensor onto T014 once it is confirmed, so the sensor has a contact in its picture. */
async function cueEo(page: Page) {
  const row = page.getByRole('button', { name: 'T014' }).locator('xpath=ancestor::tr')
  await expect(row).toContainText('Confirmed', { timeout: 20_000 })
  await selectHostile(page)
  await page.keyboard.press('u')
}

test.describe('EO view draws each target model', () => {
  test.beforeEach(async ({ page }) => {
    await installApi(page, { language: 'en', theme: 'dark' })
  })

  const SHAPES = [
    'rotary-small',
    'fixed-wing-small',
    'bird',
    'fpv-small',
    'fixed-wing-medium',
    'fixed-wing-large',
    'kite',
    'balloon',
  ]
  for (const shape of SHAPES) {
    test(`a ${shape} report is drawn as that shape`, async ({ page }) => {
      await beginSession(page, 4, variantUrl({ eoClass: shape }))
      await cueEo(page)
      const box = page.getByRole('region', { name: /EO view/ }).locator('[data-shapes]')
      await expect(box).toHaveAttribute('data-shapes', new RegExp(`(^|,)${shape}(,|$)`), {
        timeout: 20_000,
      })
      await expect(box.locator('canvas')).toHaveCount(1)
    })
  }

  test('a class outside the set falls back to a point', async ({ page }) => {
    await beginSession(page, 4, variantUrl({ eoClass: 'something-else' }))
    await cueEo(page)
    const box = page.getByRole('region', { name: /EO view/ }).locator('[data-shapes]')
    await expect(box).toHaveAttribute('data-shapes', /(^|,)point(,|$)/, { timeout: 20_000 })
  })

  for (const eo of ['thermal', 'nv'] as const) {
    test(`a balloon draws in the ${eo} picture without errors`, async ({ page }) => {
      const errors: string[] = []
      page.on('console', (m) => m.type() === 'error' && errors.push(m.text()))
      page.on('pageerror', (e) => errors.push(e.message))
      await beginSession(page, 4, variantUrl({ eo, hour: 14, eoClass: 'balloon' }))
      await cueEo(page)
      const box = page.getByRole('region', { name: /EO view/ }).locator('[data-shapes]')
      await expect(box).toHaveAttribute('data-shapes', /balloon/, { timeout: 20_000 })
      expect(errors).toEqual([])
    })
  }
})
