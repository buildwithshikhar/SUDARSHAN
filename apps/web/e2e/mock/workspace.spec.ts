import { expect, test, type Page } from '@playwright/test'
import { beginSession, installApi, sessionUrl } from './fixtures'

test.use({ viewport: { width: 1920, height: 1080 } })

/** The tracks are T011 to T014 in the order they start; T014 is the closing rotary contact. */
async function selectHostile(page: Page) {
  for (let i = 0; i < 4; i++) await page.keyboard.press('Tab')
  await expect(page.getByRole('button', { name: 'T014', pressed: true })).toBeVisible()
}

/** A cue needs a confirmed track: the sensor refuses one that is still tentative. */
async function waitConfirmed(page: Page, id: string) {
  const row = page.getByRole('button', { name: id }).locator('xpath=ancestor::tr')
  await expect(row).toContainText('Confirmed', { timeout: 20_000 })
}

const classSupport = async (page: Page) => {
  const text =
    (await page
      .getByRole('button', { name: /^T014/ })
      .locator('xpath=ancestor::tr')
      .textContent()) ?? ''
  const match = /Small rotary\s*(\d+)%|Unknown\s*(\d+)%/.exec(text)
  return Number(match?.[1] ?? match?.[2] ?? 0)
}

test.describe('workspace against the scripted session', () => {
  test.beforeEach(async ({ page }) => {
    await installApi(page, { language: 'en', theme: 'dark' })
  })

  test('keyboard only: classify, assess, a blocked response, then a permitted one', async ({
    page,
  }) => {
    await beginSession(page, 4)
    await selectHostile(page)

    // Classify (1 = Small rotary), Assess (1 = Hostile)
    await page.keyboard.press('c')
    await expect(page.getByRole('list', { name: 'Classify' })).toBeVisible()
    await page.keyboard.press('1')
    await page.keyboard.press('Enter')
    await expect(page.getByText('You classified T014 as Small rotary.')).toBeVisible()
    await expect(page.getByRole('list', { name: 'Assess' })).toBeVisible()
    await page.keyboard.press('1')
    await page.keyboard.press('Enter')
    await expect(page.getByText('You assessed T014 as Hostile.')).toBeVisible()

    // Respond with effector class B: no rule allows it for this contact
    await expect(page.getByRole('list', { name: 'Respond' })).toBeVisible()
    await page.keyboard.press('2')
    await expect(page.getByText(/Permitted by/)).toBeVisible()
    await page.keyboard.press('Enter')
    const verdict = page.getByTestId('verdict')
    await expect(verdict).toHaveAttribute('data-permitted', 'false')
    await expect(verdict).toContainText('BLOCKED')
    await expect(verdict).toContainText(
      'Suspect contact in the outer zone may receive a class A response',
    )
    await expect(verdict).toContainText('training-baseline 1.0.0')
    // what is missing is named: an unmet condition or the effector the rule does not list
    await expect(verdict).toContainText(/Confidence|Effector class B/)

    // The class estimate firms up as the contact is tracked; then a class A response is allowed
    await expect.poll(() => classSupport(page), { timeout: 30_000 }).toBeGreaterThanOrEqual(66)
    await page.keyboard.press('r')
    await page.keyboard.press('1')
    await page.keyboard.press('Enter')
    await expect(verdict).toHaveAttribute('data-permitted', 'true')
    await expect(verdict).toContainText('PERMITTED')
    await expect(verdict).toContainText(
      'Suspect contact in the outer zone may receive a class A response',
    )
    await expect(verdict).toContainText('training-baseline 1.0.0')
    await expect(page.getByText(/Response issued on T014 with ec-a\./)).toBeVisible()
  })

  test('a blocked response stays on screen until dismissed', async ({ page }) => {
    await beginSession(page, 4)
    await selectHostile(page)
    await page.keyboard.press('r')
    await page.keyboard.press('2')
    await page.keyboard.press('Enter')
    const verdict = page.getByTestId('verdict')
    await expect(verdict).toHaveAttribute('data-permitted', 'false')
    await page.waitForTimeout(1500)
    await expect(verdict).toBeVisible()
    await page.keyboard.press('x')
    await expect(verdict).toHaveCount(0)
  })

  test('cue and relabel change the track table, and a refused relabel says why', async ({
    page,
  }) => {
    await beginSession(page, 4)
    await waitConfirmed(page, 'T014')
    await selectHostile(page)

    await page.keyboard.press('u')
    await expect(page.getByText(/Cue accepted: eo-1 onto T014/)).toBeVisible()
    const sensors = page.getByRole('region', { name: 'Radar PPI' })
    await expect(sensors.getByText('Cued')).toBeVisible()
    // the zoom ladder follows the real field of view the sensor reports, not a client-side zoom
    await expect(
      page
        .getByRole('region', { name: /EO view/ })
        .locator('svg text', { hasText: /FOV\s+[1-6]\.\d°/ }),
    ).toBeVisible({ timeout: 20_000 })

    await page.keyboard.press('l')
    const dialog = page.getByRole('dialog', { name: 'Relabel track T014' })
    await expect(dialog).toBeVisible()
    await dialog.getByLabel('New label').fill('LEAD-1')
    await page.keyboard.press('Enter')
    const table = page.getByRole('table', { name: 'Tracks held by the tracker' })
    await expect(table.getByRole('button', { name: 'LEAD-1' })).toBeVisible()
    await expect(table.getByRole('button', { name: 'T014' })).toHaveCount(0)
    await expect(page.getByText("Track T014 relabelled 'LEAD-1' (was 'T014').")).toBeVisible()

    // another track cannot take the same label without exchanging
    await page.keyboard.press('Shift+Tab')
    await page.keyboard.press('l')
    await page.getByRole('dialog').getByLabel('New label').fill('LEAD-1')
    await page.keyboard.press('Enter')
    await expect(
      page.getByText(
        /Refused: Relabel\. label 'LEAD-1' is on track T014; exchange labels to take it/,
      ),
    ).toBeVisible()
  })

  test('merges two tracks and shows them as one', async ({ page }) => {
    await beginSession(page, 4)
    await page.keyboard.press('Tab')
    await page.keyboard.press('m')
    await expect(page.getByText('MERGE', { exact: true })).toBeVisible()
    await page.keyboard.press('Tab')
    await page.keyboard.press('m')
    await expect(page.getByText(/Tracks merged: T012 folded into T011\./)).toBeVisible()
    await expect(page.getByRole('button', { name: 'T012' })).toHaveCount(0)
  })

  test('draws the EO view in WebGL with its reticle, and the radar on a canvas', async ({
    page,
  }) => {
    await beginSession(page, 4)
    const eo = page.getByRole('region', { name: /EO view/ })
    await expect(eo.locator('canvas')).toHaveCount(1)
    await expect(eo.getByText(/BRG\s+038°\s+EL\s+\+04\.2°/)).toBeVisible()
    await expect(eo.getByText(/RNG\s+n\/a/)).toBeVisible()
    await expect(page.getByRole('img', { name: /Radar plan position indicator/ })).toBeVisible()
    await expect(page.getByText('EO view needs WebGL')).toHaveCount(0)
    // no night-vision or thermal mode is offered in this wave
    await expect(page.getByRole('group', { name: 'Mode' }).getByRole('button')).toHaveText([
      'Day TV',
    ])
  })

  test('ends with the event log verified', async ({ page }) => {
    await page.goto(sessionUrl(20))
    await expect(page.getByRole('button', { name: 'Begin session' })).toBeFocused()
    await page.keyboard.press('Enter')
    await expect(page.getByRole('heading', { name: 'Session ended', level: 1 })).toBeVisible({
      timeout: 30_000,
    })
    await expect(page.getByText('Event log verified')).toBeVisible()
  })

  test('shows the shortcut list with ? and closes it with Escape', async ({ page }) => {
    await beginSession(page, 4)
    await page.keyboard.press('?')
    const dialog = page.getByRole('dialog', { name: 'Keyboard shortcuts' })
    await expect(dialog).toBeVisible()
    await expect(dialog).toContainText('Space is not used in this build.')
    await page.keyboard.press('Escape')
    await expect(dialog).toBeHidden()
  })
})
