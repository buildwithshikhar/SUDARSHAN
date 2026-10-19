import { expect, test, type Page } from '@playwright/test'
import { beginSession, expectClean, installApi, sessionUrl } from './fixtures'

test.use({ viewport: { width: 1920, height: 1080 } })

/** How many pixels of the canvas differ from its dark background: zero means nothing was drawn. */
async function inkOf(page: Page, selector: string): Promise<number> {
  return page.evaluate((sel) => {
    const canvas = document.querySelector<HTMLCanvasElement>(sel)
    const ctx = canvas?.getContext('2d')
    if (!canvas || !ctx) return -1
    const { data } = ctx.getImageData(0, 0, canvas.width, canvas.height)
    let n = 0
    for (let i = 0; i < data.length; i += 4) {
      // anything brighter than the plot's graticule grey
      if ((data[i] ?? 0) + (data[i + 1] ?? 0) + (data[i + 2] ?? 0) > 330) n++
    }
    return n
  }, selector)
}

const consoles = (page: Page) => page.getByTestId('sensor-consoles')

test.describe('RF and acoustic consoles in the scripted session', () => {
  test.beforeEach(async ({ page }) => {
    await installApi(page, { language: 'en', theme: 'dark' })
  })

  test('sit under the radar PPI and above the track table, as tabs', async ({ page }) => {
    await beginSession(page, 4)
    const ppi = await page.getByRole('region', { name: 'Radar PPI' }).boundingBox()
    const box = await consoles(page).boundingBox()
    const table = await page.getByRole('region', { name: 'Track table' }).boundingBox()
    expect(ppi && box && table).toBeTruthy()
    expect(box!.y).toBeGreaterThanOrEqual(ppi!.y + ppi!.height - 1)
    expect(table!.y).toBeGreaterThanOrEqual(box!.y + box!.height - 1)
    // the same column
    expect(Math.abs(box!.x - ppi!.x)).toBeLessThan(2)
    await expect(page.getByRole('tab')).toHaveText(['RF spectrum', 'Acoustic spectrogram'])
  })

  test('RF: keyboard tabs, honesty text, report table and a drawn canvas', async ({ page }) => {
    await beginSession(page, 4)
    const region = consoles(page)
    await expect(region.getByTestId('synth-label')).toHaveText(
      'Synthesised from sensor reports · reference data',
    )
    await expect(region.getByTestId('rf-open-note')).toContainText(
      'A link behind a ridge or building is still heard here',
    )
    // the scripted RF sensor hears the civil flight (fixed, 5.8 GHz) and the hostile (hopping, 2.4 GHz)
    const table = region.getByRole('table', { name: 'Latest RF reports' })
    await expect(table.getByRole('row').nth(1)).toContainText(/GHz/, { timeout: 20_000 })
    await expect(table).toContainText('5.8 GHz')
    await expect(region.getByTestId('console-status')).toHaveAttribute('data-state', 'heard')
    await expect
      .poll(() => inkOf(page, '[aria-label^="RF spectrum and waterfall"]'))
      .toBeGreaterThan(200)

    // keyboard: focus the tab list, move with the arrows, Home and End
    await region.getByRole('tab', { name: 'RF spectrum' }).focus()
    await page.keyboard.press('ArrowRight')
    await expect(region.getByRole('tab', { name: 'Acoustic spectrogram' })).toBeFocused()
    await expect(region.getByRole('tab', { name: 'Acoustic spectrogram' })).toHaveAttribute(
      'aria-selected',
      'true',
    )
    await page.keyboard.press('Home')
    await expect(region.getByRole('tab', { name: 'RF spectrum' })).toHaveAttribute(
      'aria-selected',
      'true',
    )
    await page.keyboard.press('End')
    await expect(region.getByRole('tab', { name: 'Acoustic spectrogram' })).toBeFocused()
  })

  test('acoustic: listens first, then hears the closing rotary; the cursor reads out harmonics', async ({
    page,
  }) => {
    await page.goto(sessionUrl(6))
    await page.getByRole('button', { name: 'Begin session' }).waitFor()
    await page.keyboard.press('Enter')
    const region = consoles(page)
    await region.getByRole('tab', { name: 'Acoustic spectrogram' }).click()
    const status = region.getByTestId('console-status')
    await expect(status).toHaveAttribute('data-state', 'listening')
    await expect(status).toHaveText('Listening: nothing heard yet')
    await expect(region.getByTestId('synth-label')).toContainText('reference data')
    // the RF-only note is not shown here
    await expect(region.getByTestId('rf-open-note')).toHaveCount(0)

    await expect(status).toHaveAttribute('data-state', 'heard', { timeout: 30_000 })
    const table = region.getByRole('table', { name: 'Latest acoustic reports' })
    await expect(table.getByRole('row').nth(1)).toContainText(/Yes|No/)
    await expect
      .poll(() => inkOf(page, '[aria-label^="Acoustic spectrogram from"]'))
      .toBeGreaterThan(200)

    // Tab reaches the cursor group; Left and Right move it
    const spectrogram = region.getByTestId('spectrogram')
    await spectrogram.focus()
    await expect(spectrogram).toBeFocused()
    const before = Number(await spectrogram.getAttribute('data-cursor'))
    await page.keyboard.press('ArrowRight')
    await expect(spectrogram).toHaveAttribute('data-cursor', String(before + 5))
    await page.keyboard.press('Shift+ArrowLeft')
    await expect(spectrogram).toHaveAttribute('data-cursor', String(before - 45))
    await expect(region.getByTestId('cursor-readout')).toContainText(`${before - 45} Hz`)
    await expect(region.getByTestId('cursor-nearest')).toContainText(/order \d+ at/)
    await expect(region.getByTestId('cursor-implied')).toContainText('Hz (cursor ÷ order)')
  })

  test('the shortcut list documents the console keys', async ({ page }) => {
    await beginSession(page, 4)
    await page.keyboard.press('?')
    const dialog = page.getByRole('dialog', { name: 'Keyboard shortcuts' })
    await expect(dialog).toContainText('Switch between the RF and acoustic console tabs')
    await expect(dialog).toContainText('Move the acoustic cursor 5 Hz')
  })

  test('fits the 1366 by 768 layout: consoles keep a usable plot and the table stays reachable', async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1366, height: 768 })
    await beginSession(page, 4)
    const plot = await page.locator('[aria-label^="RF spectrum and waterfall"]').boundingBox()
    expect(plot!.height).toBeGreaterThan(90)
    expect(plot!.width).toBeGreaterThan(280)
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
    )
    expect(overflow).toBe(false)
    await expect(page.getByRole('table', { name: 'Tracks held by the tracker' })).toBeVisible()
  })

  test('Hindi: the honesty text and the unavailable wording are in Hindi', async ({ page }) => {
    await installApi(page, { language: 'hi', theme: 'dark' })
    await beginSession(page, 4)
    const region = consoles(page)
    await expect(region.getByTestId('synth-label')).toHaveText(
      'सेंसर रिपोर्टों से संश्लेषित · संदर्भ डेटा',
    )
    await expect(region.getByTestId('rf-open-note')).toContainText('भूभाग से रुकावट नहीं')
  })

  test('both themes: axe-clean with the RF and the acoustic tab showing', async ({ page }) => {
    for (const language of ['en', 'hi'] as const) {
      for (const theme of ['dark', 'light'] as const) {
        await installApi(page, { language, theme })
        await beginSession(page, 4)
        await expect(page.locator('html')).toHaveAttribute('data-theme', theme)
        const region = consoles(page)
        await expect(region.getByTestId('rf-reports').getByRole('row').nth(1)).toContainText(
          'GHz',
          {
            timeout: 20_000,
          },
        )
        await expectClean(page)
        await region.getByRole('tab').nth(1).click()
        await expect(region.getByTestId('spectrogram')).toBeVisible()
        await expectClean(page)
      }
    }
  })
})
