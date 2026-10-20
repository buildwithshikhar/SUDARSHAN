import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { expect, test } from '@playwright/test'
import { expectClean, installApi } from './fixtures'

const PACKS = resolve(process.cwd(), '../../packs/terrain')

test.describe('/bench: the render benchmark harness (demo mode)', () => {
  test.beforeEach(async ({ page }) => {
    await installApi(page, { language: 'en', theme: 'dark' })
  })

  test('starts empty and says what it will do', async ({ page }) => {
    await page.goto('/bench')
    await expect(page.getByRole('heading', { name: 'Render benchmark' })).toBeVisible()
    await expect(page.getByTestId('bench-status')).toHaveText('Not started.')
    await expect(page.getByText('No result yet')).toBeVisible()
    await expect(page.getByRole('button', { name: 'Run benchmark' })).toBeVisible()
    await expectClean(page)
  })

  test('runs against the real baked pack and offers the JSON, by keyboard', async ({ page }) => {
    await page.route('**/api/v1/terrain/heron-ridge/*', (route) => {
      const file = /\/heron-ridge\/([^/?]+)/.exec(route.request().url())?.[1] ?? ''
      try {
        return route.fulfill({
          status: 200,
          body: readFileSync(resolve(PACKS, 'heron-ridge', file)),
        })
      } catch {
        return route.fulfill({ status: 404, body: '{}' })
      }
    })
    await page.goto('/bench?quick=1')
    const run = page.getByRole('button', { name: 'Run benchmark' })
    await run.focus()
    await page.keyboard.press('Enter')
    await expect(page.getByTestId('bench-status')).toContainText('Measuring', { timeout: 30_000 })
    await expect(page.getByRole('button', { name: 'Cancel' })).toBeVisible()
    await expect(page.getByTestId('bench-status')).toContainText('Finished', { timeout: 120_000 })

    const table = page.getByRole('table', { name: 'Frame rate by stage' })
    await expect(table.locator('tbody tr')).toHaveCount(5)
    await expect(page.getByRole('heading', { name: 'Gate', exact: true })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'This machine' })).toBeVisible()

    // The last frame stays on screen as a preview, and a second run starts on a fresh canvas.
    await expect(page.getByRole('img', { name: /Benchmark scene preview/ })).toBeVisible()
    await page.getByRole('button', { name: 'Run again' }).click()
    await expect(page.getByTestId('bench-status')).toContainText('Measuring', { timeout: 30_000 })
    await page.getByRole('button', { name: 'Cancel' }).click()
    await expect(page.getByTestId('bench-status')).toHaveText('Not started.')
    await page.getByRole('button', { name: 'Run benchmark' }).click()
    await expect(page.getByTestId('bench-status')).toContainText('Finished', { timeout: 120_000 })

    const download = page.waitForEvent('download')
    await page.getByRole('button', { name: 'Download JSON' }).click()
    const file = await download
    expect(file.suggestedFilename()).toMatch(/^bench-.*\.json$/)
    const body = JSON.parse(readFileSync((await file.path()) ?? '', 'utf8'))
    expect(body.format).toBe('bench-result.v1')
    expect(body.scene).toMatchObject({ pack: 'heron-ridge', swarm: 24, birds: 30 })
    expect(body.scene.canvas).toEqual({ width: 1920, height: 1080 })
    expect(body.phases.map((p: { id: string }) => p.id)).toEqual([
      'high',
      'medium',
      'low',
      'auto',
      'high-day',
    ])
    expect(body.phases.every((p: { frames: number }) => p.frames > 0)).toBe(true)
    expect(body.device.webgl.version).not.toBeNull()
    await expectClean(page)
  })

  test('shows an error and stays usable when the terrain pack cannot load', async ({ page }) => {
    await page.route('**/api/v1/terrain/**', (route) =>
      route.fulfill({ status: 404, contentType: 'application/json', body: '{"detail":"no"}' }),
    )
    await page.goto('/bench?quick=1')
    await page.getByRole('button', { name: 'Run benchmark' }).click()
    await expect(page.getByRole('alert')).toBeVisible()
    await expect(page.getByRole('button', { name: 'Run benchmark' })).toBeEnabled()
    await expectClean(page)
  })

  test('Hindi labels', async ({ page }) => {
    await installApi(page, { language: 'hi', theme: 'light' })
    await page.goto('/bench')
    await expect(page.getByRole('heading', { name: 'रेंडर बेंचमार्क' })).toBeVisible()
    await expectClean(page)
  })
})
