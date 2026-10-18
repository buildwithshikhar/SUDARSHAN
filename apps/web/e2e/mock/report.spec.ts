import { expect, test, type Page } from '@playwright/test'
import { beginSession, expectClean, installApi } from './fixtures'

test.use({ viewport: { width: 1920, height: 1080 } })

const OUT = 'test-results/shots'

/** Select T014, the closing rotary contact, open Respond and choose "Report up the chain". */
async function openForm(page: Page, name = 'Contact report: T014') {
  await beginSession(page, 4)
  for (let i = 0; i < 4; i++) await page.keyboard.press('Tab')
  await page.keyboard.press('r')
  await page.keyboard.press('3')
  await page.keyboard.press('Enter')
  const dialog = page.getByRole('dialog', { name })
  await expect(dialog).toBeVisible()
  return dialog
}

test.describe('contact report form against the scripted session', () => {
  test.beforeEach(async ({ page }) => {
    await installApi(page, { language: 'en', theme: 'dark' })
  })

  test('keyboard only: choose a class, keep the track values, state a confidence, file', async ({
    page,
  }) => {
    const dialog = await openForm(page)
    // focus lands in the form, on the class select
    await expect(dialog.getByLabel('What')).toBeFocused()
    // bearing, range and heading came from the track; count starts at 1
    await expect(dialog.getByLabel('Bearing (°)')).toHaveValue(/^\d{1,3}$/)
    await expect(dialog.getByLabel('Range (m)')).toHaveValue(/^\d+$/)
    await expect(dialog.getByLabel('How many')).toHaveValue('1')
    await expect(dialog.getByLabel('Heading (°)')).toHaveValue(/^\d{1,3}$/)
    await page.keyboard.press('1')
    await expect(dialog.getByLabel('What')).toHaveValue('rotary-small')
    for (let i = 0; i < 5; i++) await page.keyboard.press('Tab')
    await expect(dialog.getByLabel('Confidence (%)')).toBeFocused()
    await page.keyboard.type('70')
    await page.keyboard.press('Enter')
    await expect(dialog).toBeHidden()
    // the outcome is in the event log and the verdict area
    await expect(
      page.getByText(
        /T014 reported: Small rotary, count 1, bearing \d{3}°, range .*confidence 70%\./,
      ),
    ).toBeVisible()
    await expect(page.getByTestId('verdict')).toHaveAttribute('data-permitted', 'true')
    await expect(page.getByTestId('verdict')).toContainText('Report')
  })

  test('shows an inline error for each bad field and files nothing until they are fixed', async ({
    page,
  }) => {
    const dialog = await openForm(page)
    await dialog.getByLabel('Bearing (°)').fill('400')
    await dialog.getByLabel('How many').fill('0')
    await dialog.getByLabel('Confidence (%)').fill('150')
    await page.keyboard.press('Enter')
    await expect(dialog.getByText('Enter a bearing from 0 to under 360.')).toBeVisible()
    await expect(dialog.getByText('Enter a whole number from 1 to 99.')).toBeVisible()
    await expect(dialog.getByText('Enter a percentage from 0 to 100.')).toBeVisible()
    await expect(dialog.getByLabel('Bearing (°)')).toBeFocused()
    await expect(page.getByText(/reported/)).toHaveCount(0)
    await expectClean(page)
    await page.screenshot({ path: `${OUT}/report-form-errors-en-dark-1920x1080.png` })
    await dialog.getByLabel('Bearing (°)').fill('48')
    await dialog.getByLabel('How many').fill('2')
    await dialog.getByLabel('Confidence (%)').fill('80')
    await page.keyboard.press('Enter')
    await expect(dialog).toBeHidden()
    await expect(page.getByText(/T014 reported: .*count 2, bearing 048°/)).toBeVisible()
  })

  test('Escape cancels without filing, and Skip details files a bare report', async ({ page }) => {
    const dialog = await openForm(page)
    await page.keyboard.press('Escape')
    await expect(dialog).toBeHidden()
    await expect(page.getByText(/T014 reported/)).toHaveCount(0)
    // back in the workspace: the same keys open it again
    await page.keyboard.press('r')
    await page.keyboard.press('3')
    await page.keyboard.press('Enter')
    await expect(dialog).toBeVisible()
    await dialog.getByRole('button', { name: 'Skip details' }).click()
    await expect(dialog).toBeHidden()
    await expect(page.getByText('T014 reported.')).toBeVisible()
  })
})

const combos = [
  { language: 'en', theme: 'dark', title: 'Contact report: T014' },
  { language: 'en', theme: 'light', title: 'Contact report: T014' },
  { language: 'hi', theme: 'dark', title: 'संपर्क रिपोर्ट: T014' },
  { language: 'hi', theme: 'light', title: 'संपर्क रिपोर्ट: T014' },
] as const

for (const { language, theme, title } of combos) {
  test(`report form is axe-clean: ${language}, ${theme}`, async ({ page }) => {
    await installApi(page, { language, theme })
    await openForm(page, title)
    await expectClean(page)
    await page.screenshot({ path: `${OUT}/report-form-${language}-${theme}-1920x1080.png` })
  })
}

test('report form at 1366 by 768 fits the screen', async ({ page }) => {
  await page.setViewportSize({ width: 1366, height: 768 })
  await installApi(page, { language: 'en', theme: 'dark' })
  const dialog = await openForm(page)
  const box = await dialog.boundingBox()
  expect(box).not.toBeNull()
  expect(box!.y).toBeGreaterThanOrEqual(0)
  expect(box!.y + box!.height).toBeLessThanOrEqual(768)
  await page.screenshot({ path: `${OUT}/report-form-en-dark-1366x768.png` })
})
