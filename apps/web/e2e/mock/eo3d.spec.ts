import { expect, test } from '@playwright/test'
import {
  beginSession,
  expectClean,
  installApi,
  installTerrain,
  trackRows,
  variantUrl,
} from './fixtures'

test.use({ viewport: { width: 1920, height: 1080 } })

const eoRegion = (page: import('@playwright/test').Page) =>
  page.getByRole('region', { name: /EO view/ })

test.describe('EO view: terrain pack, thermal and night vision, graphics tier', () => {
  test.beforeEach(async ({ page }) => {
    await installApi(page, { language: 'en', theme: 'dark' })
  })

  test('loads the terrain pack: loading, then ready, with the pack named', async ({ page }) => {
    const terrain = await installTerrain(page, 'slow')
    await beginSession(page, 4, variantUrl({ terrain: 'fixture-ridge' }))
    const eo = eoRegion(page)
    const box = eo.locator('[data-terrain]')
    await expect(box).toHaveAttribute('data-terrain', 'loading')
    await expect(eo.getByRole('status').filter({ hasText: 'Loading terrain' })).toBeVisible()
    // the session runs while the pack downloads
    await expect(eo.getByText(/BRG\s+038°/)).toBeVisible()
    terrain.release()
    await expect(box).toHaveAttribute('data-terrain', 'pack')
    await expect(eo.getByText('Terrain: Fixture Ridge')).toBeVisible()
    await expect(eo.getByRole('alert')).toHaveCount(0)
    await expect(eo.locator('canvas')).toHaveCount(1)
    await expectClean(page)
  })

  test('falls back to flat ground with an inline notice when the pack cannot load', async ({
    page,
  }) => {
    await installTerrain(page, 'missing')
    await beginSession(page, 4, variantUrl({ terrain: 'no-such-pack' }))
    const eo = eoRegion(page)
    await expect(eo.locator('[data-terrain]')).toHaveAttribute('data-terrain', 'error')
    const notice = eo.getByRole('alert')
    await expect(notice).toContainText('Terrain could not be loaded')
    await expect(notice).toContainText('flat ground')
    // the picture, the reticle and the rest of the workspace carry on
    await expect(eo.locator('canvas')).toHaveCount(1)
    await expect(eo.getByText(/BRG\s+038°/)).toBeVisible()
    await expect(trackRows(page).first()).toBeVisible()
    await expectClean(page)
  })

  test('flat ground needs no download and shows no terrain notice', async ({ page }) => {
    await beginSession(page, 4, variantUrl({}))
    const eo = eoRegion(page)
    await expect(eo.locator('[data-terrain]')).toHaveAttribute('data-terrain', 'flat')
    await expect(eo.getByRole('alert')).toHaveCount(0)
    await expect(eo.getByTestId('terrain-loading')).toHaveCount(0)
  })

  test('a thermal camera switches polarity with the keyboard and shows its gain readout', async ({
    page,
  }) => {
    await installTerrain(page, 'ok')
    await beginSession(page, 4, variantUrl({ terrain: 'fixture-ridge', eo: 'thermal', hour: 14 }))
    const eo = eoRegion(page)
    const box = eo.locator('[data-mode]')
    const mode = page.getByRole('group', { name: 'Mode' })
    await expect(mode.getByRole('button')).toHaveText(['White-hot', 'Black-hot'])
    await expect(box).toHaveAttribute('data-mode', 'thermal-white-hot')
    await expect(eo.getByText(/IR WHT/)).toBeVisible()
    await expect(eo.getByText(/AGC\s+(\d+%|—)\s+MODEL/)).toBeVisible()
    // the gain readout fills in once the picture has been sampled
    await expect(eo.getByText(/AGC\s+\d+%\s+MODEL/)).toBeVisible({ timeout: 20_000 })

    await mode.getByRole('button', { name: 'Black-hot' }).focus()
    await page.keyboard.press('Enter')
    await expect(box).toHaveAttribute('data-mode', 'thermal-black-hot')
    await expect(mode.getByRole('button', { name: 'Black-hot' })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
    await expect(eo.getByText(/IR BLK/)).toBeVisible()
    await page.keyboard.press('Shift+Tab')
    await page.keyboard.press('Enter')
    await expect(box).toHaveAttribute('data-mode', 'thermal-white-hot')

    // the note that thermal is a model is reachable from the keyboard
    await page.getByRole('button', { name: 'About this picture' }).focus()
    await expect(page.getByRole('tooltip')).toContainText('rendering model, not radiometric')
    await expectClean(page)
  })

  test('a night-vision camera offers its own picture and shows tube gain', async ({ page }) => {
    await beginSession(page, 4, variantUrl({ eo: 'nv', hour: 23 }))
    const eo = eoRegion(page)
    await expect(page.getByRole('group', { name: 'Mode' }).getByRole('button')).toHaveText([
      'Night vision',
    ])
    await expect(eo.locator('[data-mode]')).toHaveAttribute('data-mode', 'night-vision')
    await expect(eo.getByText(/GAIN\s+×\d+\.\d/)).toBeVisible({ timeout: 20_000 })
  })

  test('the graphics tier is chosen with the keyboard and remembered', async ({ page }) => {
    await beginSession(page, 4, variantUrl({}))
    const graphics = page.getByRole('group', { name: 'Graphics' })
    await expect(graphics.getByRole('button')).toHaveText(['Auto', 'High', 'Medium', 'Low'])
    await expect(graphics.getByRole('button', { name: 'Auto' })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
    await graphics.getByRole('button', { name: 'Medium' }).focus()
    await page.keyboard.press('Enter')
    const box = eoRegion(page).locator('[data-tier]')
    await expect(box).toHaveAttribute('data-tier', 'medium')
    expect(await page.evaluate(() => window.localStorage.getItem('ui.quality'))).toBe('medium')
    await page.reload()
    await expect(
      page.getByRole('group', { name: 'Graphics' }).getByRole('button', { name: 'Medium' }),
    ).toHaveAttribute('aria-pressed', 'true')
  })
})

test.describe('Hindi', () => {
  test('labels the modes, the graphics control and the terrain notice in Hindi', async ({
    page,
  }) => {
    await installApi(page, { language: 'hi', theme: 'dark' })
    await installTerrain(page, 'missing')
    await beginSession(page, 4, variantUrl({ eo: 'thermal', terrain: 'no-such-pack' }))
    await expect(page.getByRole('button', { name: 'सफ़ेद-गर्म' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'काला-गर्म' })).toBeVisible()
    await expect(page.getByRole('group', { name: 'ग्राफ़िक्स' })).toBeVisible()
    await expect(page.getByText('भूभाग लोड नहीं हो सका')).toBeVisible()
  })
})
