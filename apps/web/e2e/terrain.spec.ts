import { expect, test } from '@playwright/test'
import { PASSWORD, signIn } from './helpers'

// A scenario on a terrain pack against the real stack: the briefing names the pack, the API serves
// it through nginx, and the browser's Content-Security-Policy lets the 3D scene read the glTF
// textures (a blob: fetch). The dev-server mock has no CSP, so only this test can catch that.
test.skip(!PASSWORD, 'E2E_PASSWORD not set; run through make e2e')
test.use({ viewport: { width: 1920, height: 1080 } })
test.setTimeout(120_000)

test('a pack scenario loads its terrain through nginx without a policy violation', async ({
  page,
}) => {
  const violations: string[] = []
  page.on('console', (message) => {
    const text = message.text()
    if (/Content Security Policy|violates the following/i.test(text)) violations.push(text)
  })
  await signIn(page, 'trainee')
  const csrf = await page.evaluate(
    async () => ((await (await fetch('/api/v1/auth/me')).json()) as { csrf: string }).csrf,
  )
  const created = await page.request.post('/api/v1/sessions', {
    data: { scenario_id: 'heron-ridge-low-approach' },
    headers: { 'X-CSRF-Token': csrf },
  })
  expect(created.status()).toBe(201)
  const { id } = (await created.json()) as { id: string }
  await page.goto(`/train/session/${id}`)
  await page.getByRole('button', { name: 'Begin session' }).click()

  const eo = page.getByRole('region', { name: /EO view/ })
  await expect(eo.locator('[data-terrain]')).toHaveAttribute('data-terrain', 'pack', {
    timeout: 60_000,
  })
  await expect(eo.getByText('Terrain: Heron Ridge · reference data')).toBeVisible()
  await expect(eo.getByRole('alert')).toHaveCount(0)
  await expect(page.getByText('Connected')).toBeVisible()
  // give the glTF loader time to ask for its texture, then check nothing was refused
  await page.waitForTimeout(6000)
  expect(violations).toEqual([])
})
