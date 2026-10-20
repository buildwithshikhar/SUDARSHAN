import { expect, test, type Page } from '@playwright/test'
import { SAMPLE_YAML, SAMPLE_YAML_ERRORS, SAMPLE_YAML_LINT } from '../../src/scenarios/samples'
import { expectClean, installApi, type Prefs } from './fixtures'

// The scenario screens run against the scripted scenario API (`?mock=1`, dev server only); the
// `scn` query picks the state: empty, error, offline or slow. Sessions and sign-in are answered by
// installApi, as in the other mock specs.

const OUT = 'test-results/shots'
const instructor = { language: 'en', theme: 'dark', role: 'instructor' } as const satisfies Prefs

const combos = [
  { language: 'en', theme: 'dark' },
  { language: 'en', theme: 'light' },
  { language: 'hi', theme: 'dark' },
  { language: 'hi', theme: 'light' },
] as const

async function open(page: Page, path: string, prefs: Prefs = instructor, scn?: string) {
  await installApi(page, prefs)
  await page.goto(`${path}?mock=1${scn ? `&scn=${scn}` : ''}`)
}

const lineOf = (text: string, start: string) =>
  text.split('\n').findIndex((line) => line.startsWith(start)) + 1

const caretLine = (page: Page) =>
  page.evaluate(() => {
    const area = document.querySelector('textarea')!
    return area.value.slice(0, area.selectionStart).split('\n').length
  })

async function noPageOverflow(page: Page) {
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  )
  expect(overflow).toBeLessThanOrEqual(0)
}

async function noBannedWords(page: Page) {
  const text = await page.locator('body').innerText()
  expect(text).not.toMatch(/provabl|guarantee/i)
}

test.describe('scenario library', () => {
  test('lists every scenario with the three solvability wordings', async ({ page }) => {
    await open(page, '/content/scenarios')
    await expect(page.getByRole('heading', { name: 'Scenario library', level: 1 })).toBeVisible()
    const table = page.getByRole('table', { name: 'Scenarios held by this instance' })
    await expect(table.locator('tbody tr')).toHaveCount(14)
    await expect(page.getByTestId('library-count')).toHaveText('14 of 14 scenarios')
    await expect(
      page.getByText('Built on published specifications and open research.'),
    ).toBeVisible()
    for (const wording of ['Verified solvable by test run', 'Not verified solvable', 'Unchecked']) {
      await expect(table.getByText(wording, { exact: true }).first()).toBeVisible()
    }
    await expect(table.locator('[data-status="verified"]').first()).toContainText(
      'Verified solvable by test run',
    )
    await expect(table.locator('[data-status="failed"]')).toHaveCount(1)
    await expect(table.locator('[data-status="unchecked"]')).toHaveCount(2)
    // Delete is offered for saved scenarios only: 4 generated and 3 authored.
    await expect(page.getByRole('button', { name: /^Delete: / })).toHaveCount(7)
    await noBannedWords(page)
  })

  test('filters by origin, terrain, time of day and tag, searches, sorts, and clears', async ({
    page,
  }) => {
    await open(page, '/content/scenarios')
    const count = page.getByTestId('library-count')
    await page.getByLabel('Origin').selectOption('scripted')
    await expect(count).toHaveText('5 of 14 scenarios')
    await page.getByLabel('Time of day').selectOption('night')
    await expect(count).toHaveText('1 of 14 scenarios')
    await page.getByRole('button', { name: 'Clear filters' }).click()
    await expect(count).toHaveText('14 of 14 scenarios')
    await page.getByLabel('Terrain').selectOption('osprey-town')
    await expect(count).toHaveText('2 of 14 scenarios')
    await page.getByLabel('Terrain').selectOption('')
    await page.getByLabel('Tag', { exact: true }).selectOption('night')
    await expect(count).toHaveText('4 of 14 scenarios')
    await page.getByRole('button', { name: 'Clear filters' }).click()
    await page.getByLabel('Search by id, title or tag').fill('marlin')
    await expect(count).toHaveText('1 of 14 scenarios')
    await page.getByLabel('Search by id, title or tag').fill('zzz-no-such-scenario')
    await expect(page.getByText('No scenario matches these filters')).toBeVisible()
    await expectClean(page)
    await page.getByRole('button', { name: 'Clear filters' }).first().click()
    await page.getByLabel('Sort by').selectOption('difficultyDown')
    const firstRow = page.locator('tbody tr').first()
    await expect(firstRow).toContainText('gen-90814422-d27e18')
  })

  test('deletes a saved scenario after a confirmation, and Escape cancels', async ({ page }) => {
    await open(page, '/content/scenarios')
    const del = page.getByRole('button', { name: /^Delete: Ridge picket drill/ })
    await del.focus()
    await page.keyboard.press('Enter')
    const dialog = page.getByRole('dialog', { name: 'Delete scenario' })
    await expect(dialog).toBeVisible()
    await expect(dialog).toContainText('auth-ridge-picket-drill')
    await expectClean(page)
    await page.keyboard.press('Escape')
    await expect(dialog).toBeHidden()
    await expect(page.locator('tbody tr')).toHaveCount(14)
    await del.click()
    await dialog.getByRole('button', { name: 'Delete scenario' }).click()
    await expect(page.getByText('Deleted auth-ridge-picket-drill.')).toBeVisible()
    await expect(page.locator('tbody tr')).toHaveCount(13)
  })

  test('opens a scenario in the editor and starts a session', async ({ page }) => {
    await open(page, '/content/scenarios')
    await page.getByRole('button', { name: /^Open in editor: Marlin Hill/ }).click()
    await expect(page).toHaveURL(/\/content\/scenarios\/editor\/marlin-hill-evening-picket\?mock=1/)
    await expect(page.getByLabel('Scenario YAML text')).toHaveValue(
      /id: marlin-hill-evening-picket/,
    )
    await page.goBack()
    await page.getByRole('button', { name: /^Start a session: Marlin Hill/ }).click()
    await expect(page).toHaveURL(/\/train\/session\/mock-session\?mock=1/)
  })

  test('is operable from the keyboard: filters, then the table region, then a row action', async ({
    page,
  }) => {
    await open(page, '/content/scenarios')
    await page.getByLabel('Search by id, title or tag').focus()
    await page.keyboard.type('swarm')
    await expect(page.getByTestId('library-count')).toHaveText('2 of 14 scenarios')
    await page.keyboard.press('Tab') // Origin
    await expect(page.getByLabel('Origin')).toBeFocused()
    const edit = page.getByRole('button', { name: /^Open in editor: Town edge/ })
    await edit.focus()
    await expect(edit).toBeFocused()
    await page.keyboard.press('Enter')
    await expect(page).toHaveURL(/editor\/curriculum-05-town-edge-swarm/)
  })

  test('shows an empty state, an error with retry, an offline state and a loading state', async ({
    page,
  }) => {
    await open(page, '/content/scenarios', instructor, 'empty')
    await expect(page.getByText('The library holds no scenarios')).toBeVisible()
    await expectClean(page)

    await page.goto('/content/scenarios?mock=1&scn=error')
    await expect(page.getByText('The scenario library could not be loaded')).toBeVisible()
    await expect(page.getByRole('button', { name: 'Retry' })).toBeVisible()
    await expectClean(page)

    await page.goto('/content/scenarios?mock=1&scn=offline')
    await expect(page.getByText('The server is unreachable')).toBeVisible()
    await expectClean(page)

    await page.goto('/content/scenarios?mock=1&scn=slow')
    await expect(page.getByText('Loading the scenario library')).toBeAttached()
    await expectClean(page)
  })

  test('is closed to trainees and reachable from the instructor sidebar', async ({ page }) => {
    await installApi(page, { ...instructor, role: 'trainee' })
    await page.goto('/content/scenarios?mock=1')
    await expect(page.getByRole('heading', { name: 'No access', level: 1 })).toBeVisible()
    await page.unroute('**/api/v1/auth/me')
    await installApi(page, instructor)
    await page.goto('/status?mock=1')
    await page.getByRole('navigation').getByRole('link', { name: 'Scenarios' }).click()
    await expect(page).toHaveURL(/\/content\/scenarios/)
  })

  test('does not scroll the page sideways at 1024 px', async ({ page }) => {
    await page.setViewportSize({ width: 1024, height: 768 })
    await open(page, '/content/scenarios')
    await expect(page.locator('tbody tr')).toHaveCount(14)
    await noPageOverflow(page)
    await expectClean(page)
  })
})

test.describe('scenario editor', () => {
  test('opens by id, shows the four summaries and a clean validation', async ({ page }) => {
    await open(page, '/content/scenarios/editor/marlin-hill-evening-picket')
    await expect(page.getByRole('heading', { name: 'Scenario editor', level: 1 })).toBeVisible()
    await expect(page.getByTestId('validation-summary')).toHaveAttribute('data-valid', 'true')
    await expect(page.getByRole('heading', { name: 'Terrain and site' })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Threat timeline' })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Sensors and degradations' })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Weather and light' })).toBeVisible()
    await expect(page.getByRole('table', { name: 'Threats by spawn time' })).toContainText(
      'th-quad-a',
    )
    await expect(page.getByTestId('time-strip')).toBeVisible()
    await expect(page.getByRole('table', { name: 'Sensors placed in the scenario' })).toContainText(
      'radar-generic-s',
    )
    await expect(page.getByTestId('gutter').locator('[data-line]').first()).toHaveText('1')
    await noBannedWords(page)
  })

  test('reports errors with line numbers and jumps the caret to the line', async ({ page }) => {
    await open(page, '/content/scenarios/editor/marlin-hill-evening-picket')
    await expect(page.getByTestId('validation-summary')).toHaveAttribute('data-valid', 'true')
    await page.getByLabel('Scenario YAML text').fill(SAMPLE_YAML_ERRORS)
    await expect(page.getByTestId('validation-summary')).toHaveAttribute('data-valid', 'false')
    const durationLine = lineOf(SAMPLE_YAML_ERRORS, 'duration_s: soon')
    const tabLine = SAMPLE_YAML_ERRORS.split('\n').findIndex((l) => l.startsWith('\t')) + 1
    const item = page.locator(`[data-code="schema.type"]`)
    await expect(item).toContainText(`Line ${durationLine}`)
    await expect(page.locator(`[data-code="yaml.tab"]`)).toContainText(`Line ${tabLine}`)
    await expect(item).toContainText('A field is missing, unknown or has the wrong type.')
    // gutter markers are drawn on those lines, with an icon and not only a colour
    await expect(
      page.getByTestId('gutter').locator(`[data-line="${durationLine}"][data-marker="error"] svg`),
    ).toHaveCount(1)

    await item.click()
    expect(await caretLine(page)).toBe(durationLine)
    await expect(page.getByLabel('Scenario YAML text')).toBeFocused()
    await expect(page.getByTestId('caret')).toContainText(`Line ${durationLine},`)

    // keyboard: focus the other item and press Enter
    await page.locator('[data-code="yaml.tab"]').focus()
    await page.keyboard.press('Enter')
    expect(await caretLine(page)).toBe(tabLine)
    await expectClean(page)
  })

  test('lints a threat timed before the reaction window and a short link range', async ({
    page,
  }) => {
    await open(page, '/content/scenarios/editor')
    await page.getByLabel('Scenario YAML text').fill(SAMPLE_YAML_LINT)
    const reaction = page.locator('[data-code="timing.reaction-window"]')
    const spawnLine = lineOf(SAMPLE_YAML_LINT.replace(/^ {4}/gm, ''), 'spawn_s: 12')
    await expect(reaction).toBeVisible()
    await expect(reaction).toContainText(
      "A hostile contact reaches the inner zone before the rule pack's minimum reaction time.",
    )
    const shown = await reaction.locator('span').first().innerText()
    expect(shown).toBe(`Line ${spawnLine}`)
    await expect(reaction).toContainText('Error')
    await expect(page.locator('[data-code="group.link-range"]')).toContainText('Warning')
    await expect(page.getByTestId('validation-summary')).toContainText('Errors: 1 · Warnings: 1')
    await reaction.click()
    expect(await caretLine(page)).toBe(spawnLine)
    // The oracle is not run on a text with lint errors, and the panel says so
    await page.getByRole('button', { name: 'Run checks' }).click()
    await expect(page.getByText('The oracle did not run')).toBeVisible()
    await expect(page.getByTestId('solvability-wording')).toHaveCount(0)
  })

  test('runs the checks: four solvability checks, the exact wording and the diversity result', async ({
    page,
  }) => {
    await open(page, '/content/scenarios/editor/marlin-hill-evening-picket')
    await expect(page.getByTestId('validation-summary')).toHaveAttribute('data-valid', 'true')
    await page.getByRole('button', { name: 'Run checks' }).click()
    const wording = page.getByTestId('solvability-wording')
    await expect(wording).toHaveText('Verified solvable by test run')
    await expect(wording).toHaveAttribute('data-wording', 'verified solvable by test run')
    const checks = page.getByRole('table', { name: 'Solvability checks' })
    await expect(checks.locator('tbody tr')).toHaveCount(4)
    await expect(checks).toContainText('Every hostile contact was reported by a sensor')
    await expect(checks).toContainText('92.0%')
    const diversity = page.getByTestId('diversity')
    await expect(diversity).toContainText('Passes')
    await expect(diversity).toContainText('0.310')
    await expect(
      page.getByRole('table', { name: 'Nearest scenarios in your history' }),
    ).toBeVisible()
    await expect(page.getByTestId('check-result')).toContainText('Verified solvable by test run')
    await expectClean(page)
    await noBannedWords(page)
  })

  test('states plainly when a scenario is not verified solvable', async ({ page }) => {
    await open(page, '/content/scenarios/editor/marlin-hill-evening-picket')
    await page.getByLabel('Test seed').fill('14')
    await page.getByRole('button', { name: 'Run checks' }).click()
    await expect(page.getByTestId('solvability-wording')).toHaveText('Not verified solvable')
    await expect(page.getByRole('table', { name: 'Solvability checks' })).toContainText('Failed')
  })

  test('runs a preview: map, contacts and coverage', async ({ page }) => {
    await open(page, '/content/scenarios/editor/marlin-hill-evening-picket')
    await expect(page.getByTestId('validation-summary')).toHaveAttribute('data-valid', 'true')
    await page.getByRole('button', { name: 'Run preview' }).click()
    await expect(page.getByTestId('preview-map')).toBeVisible()
    await expect(page.locator('[data-path]')).toHaveCount(3)
    await expect(page.getByRole('table', { name: 'Contacts in the preview run' })).toContainText(
      'th-quad-a',
    )
    await expect(page.getByRole('table', { name: 'Sensor coverage of each threat' })).toContainText(
      'radar-1, eo-1, rf-1',
    )
    await expectClean(page)
  })

  test('saves a scenario with tags', async ({ page }) => {
    await open(page, '/content/scenarios/editor/marlin-hill-evening-picket')
    await expect(page.getByTestId('validation-summary')).toHaveAttribute('data-valid', 'true')
    await page.getByRole('button', { name: 'Save', exact: true }).click()
    const dialog = page.getByRole('dialog', { name: 'Save scenario' })
    await expect(dialog).toContainText('marlin-hill-evening-picket')
    await dialog.getByLabel('Tags').fill('rural, pair')
    await expectClean(page)
    await dialog.getByRole('button', { name: 'Save scenario' }).click()
    await expect(page.getByText('Saved marlin-hill-evening-picket to the library.')).toBeVisible()
  })

  test('opens another scenario by its id', async ({ page }) => {
    await open(page, '/content/scenarios/editor')
    await page.getByLabel('Open by scenario id').fill('example-minimal-single')
    await page.keyboard.press('Enter')
    await expect(page).toHaveURL(/editor\/example-minimal-single/)
    await expect(page.getByLabel('Scenario YAML text')).toHaveValue(/id: example-minimal-single/)
  })

  test('has an empty state, a not-found state, an error with retry and a loading state', async ({
    page,
  }) => {
    await open(page, '/content/scenarios/editor')
    await expect(page.getByText('No scenario text yet')).toBeVisible()
    await expect(page.getByText('Nothing to summarise yet').first()).toBeVisible()
    await expect(page.getByRole('button', { name: 'Save', exact: true })).toBeDisabled()
    await expectClean(page)

    await page.goto('/content/scenarios/editor/no-such-scenario?mock=1')
    await expect(page.getByText('No scenario with that id')).toBeVisible()
    await expectClean(page)

    await page.goto('/content/scenarios/editor/marlin-hill-evening-picket?mock=1&scn=error')
    await expect(page.getByText('The scenario could not be loaded')).toBeVisible()
    await expect(page.getByRole('button', { name: 'Retry' })).toBeVisible()
    await expectClean(page)

    await page.goto('/content/scenarios/editor/marlin-hill-evening-picket?mock=1&scn=slow')
    await expect(page.getByText('Loading the scenario', { exact: true })).toBeAttached()
    await expectClean(page)
  })

  test('is usable at 1366 by 768 and does not scroll sideways at 1024', async ({ page }) => {
    await page.setViewportSize({ width: 1366, height: 768 })
    await open(page, '/content/scenarios/editor/marlin-hill-evening-picket')
    await expect(page.getByTestId('validation-summary')).toHaveAttribute('data-valid', 'true')
    await expect(page.getByLabel('Scenario YAML text')).toBeVisible()
    await page.screenshot({ path: `${OUT}/editor-en-dark-1366x768.png` })
    await page.setViewportSize({ width: 1024, height: 768 })
    await page.getByRole('button', { name: 'Run preview' }).click()
    await expect(page.getByTestId('preview-map')).toBeVisible()
    await noPageOverflow(page)
  })
})

test.describe('generator studio', () => {
  test('shows the difficulty vector as five labelled ranges with a numeric readout', async ({
    page,
  }) => {
    await open(page, '/content/generator')
    await expect(page.getByRole('heading', { name: 'Generator studio', level: 1 })).toBeVisible()
    for (const name of ['Threat load', 'Ambiguity', 'Speed', 'Stealth', 'Degradation']) {
      const range = page.getByRole('slider', { name })
      await expect(range).toHaveAttribute('min', '0')
      await expect(range).toHaveAttribute('max', '100')
    }
    const load = page.getByRole('slider', { name: 'Threat load' })
    await load.focus()
    await expect(page.getByTestId('out-threat_load')).toHaveText('40')
    await page.keyboard.press('ArrowRight')
    await page.keyboard.press('ArrowRight')
    await expect(page.getByTestId('out-threat_load')).toHaveText('42')
    await page.keyboard.press('End')
    await expect(page.getByTestId('out-threat_load')).toHaveText('100')
    await page.keyboard.press('Home')
    await expect(page.getByTestId('out-threat_load')).toHaveText('0')
  })

  test('validates the request before it is sent', async ({ page }) => {
    await open(page, '/content/generator')
    const generate = page.getByRole('button', { name: 'Generate', exact: true })
    await expect(generate).toBeEnabled()
    for (const mix of ['Single', 'Swarm']) await page.getByLabel(mix, { exact: true }).uncheck()
    await expect(page.getByText('Choose at least one threat type.')).toBeVisible()
    await expect(generate).toBeDisabled()
    await page.getByLabel('Fast mover').check()
    await expect(generate).toBeEnabled()
    await page.getByLabel('Seed', { exact: true }).fill('abc')
    await expect(page.getByText('Enter a whole number from 0 to 4294967295.')).toBeVisible()
    await expect(generate).toBeDisabled()
    await page.getByRole('button', { name: 'Randomise' }).click()
    await expect(page.getByLabel('Seed', { exact: true })).toHaveValue(/^\d+$/)
    await expect(generate).toBeEnabled()
    await page.getByLabel('Oracle minimum score (%)').fill('30')
    await expect(page.getByText('Enter a whole number from 50 to 100.')).toBeVisible()
  })

  test('generates a scenario: checks, wording, relaxations, features, and keeps it', async ({
    page,
  }) => {
    await open(page, '/content/generator')
    await expect(page.getByText('Nothing generated yet')).toBeVisible()
    await page.getByLabel('Oracle minimum score (%)').fill('95')
    await page.getByLabel('Seed', { exact: true }).fill('48213907')
    await page.getByRole('button', { name: 'Generate', exact: true }).click()
    const result = page.getByTestId('result')
    await expect(result).toHaveCount(1)
    await expect(result).toHaveAttribute('data-id', /^gen-48213907-/)
    await expect(page.getByTestId('result-wording')).toHaveText('Verified solvable by test run')
    await expect(result.getByRole('table')).toContainText('Every hostile contact was engaged')
    await expect(page.getByTestId('relaxations')).toContainText('diversity threshold halved')
    await expect(result).toContainText('Attempts')
    await expect(result.getByRole('group', { name: 'Feature vector' })).toContainText(
      'Threat count',
    )
    await expect(page.getByTestId('result-code')).toHaveText(/^SD1-/)
    await result.getByRole('button', { name: 'Save to the library' }).click()
    await expect(result.getByText('Saved to the library')).toBeVisible()
    await expectClean(page)
    await noBannedWords(page)
  })

  test('batch generates up to 12 and refuses more', async ({ page }) => {
    await open(page, '/content/generator')
    await page.getByLabel('Batch size').fill('13')
    await expect(page.getByRole('button', { name: 'Batch generate' })).toBeDisabled()
    await page.getByLabel('Batch size').fill('3')
    await page.getByRole('button', { name: 'Batch generate' }).click()
    await expect(page.getByTestId('result')).toHaveCount(3)
    await expect(page.getByText('3 generated')).toBeVisible()
  })

  test('encodes the request to a share code and decodes it back', async ({ page }) => {
    await open(page, '/content/generator')
    await page.getByLabel('Seed', { exact: true }).fill('77120045')
    await page.getByLabel('Terrain', { exact: true }).selectOption('osprey-town')
    await page.getByLabel('Time of day', { exact: true }).selectOption('night')
    await page.getByRole('slider', { name: 'Stealth' }).fill('73')
    await page.getByRole('button', { name: 'Encode' }).click()
    const code = page.getByRole('textbox', { name: 'Share code' })
    await expect(code).toHaveValue(/^SD1-/)
    await page.getByLabel('Seed', { exact: true }).fill('1')
    await page.getByLabel('Terrain', { exact: true }).selectOption('flat')
    await page.getByRole('slider', { name: 'Stealth' }).fill('5')
    await page.getByRole('button', { name: 'Decode' }).click()
    await expect(page.getByLabel('Seed', { exact: true })).toHaveValue('77120045')
    await expect(page.getByLabel('Terrain', { exact: true })).toHaveValue('osprey-town')
    await expect(page.getByTestId('out-stealth')).toHaveText('73')
    await code.fill('SD1-NOT-A-CODE')
    await page.getByRole('button', { name: 'Decode' }).click()
    await expect(page.getByText('That share code is not valid.')).toBeVisible()
    await code.fill('')
    await expect(page.getByRole('button', { name: 'Decode' })).toBeDisabled()
  })

  test('copies the share code or selects it when the clipboard is closed', async ({ page }) => {
    await open(page, '/content/generator')
    await page.getByRole('button', { name: 'Encode' }).click()
    await expect(page.getByRole('textbox', { name: 'Share code' })).toHaveValue(/^SD1-/)
    await page.evaluate(() => {
      Object.defineProperty(navigator, 'clipboard', {
        value: { writeText: () => Promise.reject(new Error('denied')) },
        configurable: true,
      })
    })
    await page.getByRole('button', { name: 'Copy', exact: true }).click()
    await expect(page.getByText(/clipboard cannot be used here/)).toBeVisible()
  })

  test('draws the archive as a heat map with a numeric scale, metrics and keyboard cells', async ({
    page,
  }) => {
    await open(page, '/content/generator')
    const map = page.getByTestId('heat-map')
    await expect(map).toBeVisible()
    await expect(map.getByRole('gridcell')).toHaveCount(36)
    await expect(page.getByTestId('heat-legend')).toContainText('0.50')
    await expect(page.getByTestId('heat-legend')).toContainText('1.00')
    const coverage = await page.getByTestId('metric-coverage').innerText()
    expect(coverage).toMatch(/^\d+\.\d%$/)
    await expect(page.getByTestId('archive-metrics')).toContainText('of 144 cells')
    await expect(page.getByTestId('metric-qd')).toHaveText(/^\d+\.\d{3}$/)
    await expect(page.getByTestId('metric-pairwise')).toHaveText(/^0\.\d{3}$/)

    // keyboard: Tab reaches one cell, arrows move between cells, the tooltip follows
    const first = map.locator('[data-x="0"][data-y="0"]')
    await first.focus()
    await expect(page.getByTestId('heat-tip')).toContainText('Threat count 1')
    await page.keyboard.press('ArrowRight')
    await expect(map.locator('[data-x="1"][data-y="0"]')).toBeFocused()
    await expect(page.getByTestId('heat-tip')).toContainText('Threat count 2')
    await page.keyboard.press('ArrowUp')
    await expect(map.locator('[data-x="1"][data-y="1"]')).toBeFocused()
    await expect(page.getByTestId('heat-tip')).toContainText('Identification ambiguity 10 to 25%')
    await page.keyboard.press('End')
    await expect(map.locator('[data-x="5"][data-y="1"]')).toBeFocused()
    await page.keyboard.press('Home')
    await expect(map.locator('[data-x="0"][data-y="1"]')).toBeFocused()

    // a different pair of axes
    await page.getByLabel('Columns').selectOption('2')
    await expect(map.getByRole('gridcell')).toHaveCount(24)
    await expectClean(page)
  })

  test('shows the empty archive, an archive error with retry, and generation errors', async ({
    page,
  }) => {
    await open(page, '/content/generator', instructor, 'empty')
    await expect(page.getByText(/The archive holds no scenario yet/)).toBeVisible()
    await expect(page.getByTestId('metric-coverage')).toContainText('0.0%')
    await expect(page.getByTestId('heat-map').getByRole('gridcell')).toHaveCount(36)
    await expectClean(page)

    await page.goto('/content/generator?mock=1&scn=error')
    await expect(page.getByText('The archive could not be loaded')).toBeVisible()
    await page.getByRole('button', { name: 'Generate', exact: true }).click()
    await expect(page.getByText('No scenario could be generated')).toBeVisible()
    await expectClean(page)

    await page.goto('/content/generator?mock=1&scn=offline')
    await expect(page.getByText('The server is unreachable').first()).toBeVisible()
  })

  test('shows loading states for the archive and for generation', async ({ page }) => {
    await open(page, '/content/generator', instructor, 'slow')
    await expect(page.getByText('Loading the archive')).toBeAttached()
    await page.getByRole('button', { name: 'Generate', exact: true }).click()
    await expect(page.getByText('Generating and checking scenarios')).toBeAttached()
    await expect(page.getByRole('button', { name: 'Generating' })).toBeDisabled()
    await expectClean(page)
  })

  test('is usable at 1366 by 768 and does not scroll sideways at 1024', async ({ page }) => {
    await page.setViewportSize({ width: 1366, height: 768 })
    await open(page, '/content/generator')
    await page.getByRole('button', { name: 'Generate', exact: true }).click()
    await expect(page.getByTestId('result')).toHaveCount(1)
    await page.screenshot({ path: `${OUT}/generator-en-dark-1366x768.png`, fullPage: true })
    await page.setViewportSize({ width: 1024, height: 768 })
    await noPageOverflow(page)
  })
})

for (const { language, theme } of combos) {
  test.describe(`axe: ${language}, ${theme}`, () => {
    const prefs: Prefs = { language, theme, role: 'instructor' }

    test('library', async ({ page }) => {
      await open(page, '/content/scenarios', prefs)
      await expect(page.locator('tbody tr')).toHaveCount(14)
      await expect(page.locator('html')).toHaveAttribute('data-theme', theme)
      await expect(page.locator('html')).toHaveAttribute('lang', language)
      await expectClean(page)
      await page.screenshot({ path: `${OUT}/library-${language}-${theme}-1920x1080.png` })
    })

    test('editor with errors, checks and a preview', async ({ page }) => {
      await open(page, '/content/scenarios/editor/marlin-hill-evening-picket', prefs)
      await expect(page.getByTestId('validation-summary')).toHaveAttribute('data-valid', 'true')
      await page.getByRole('textbox', { name: /YAML/ }).fill(SAMPLE_YAML_LINT)
      await expect(page.locator('[data-code="timing.reaction-window"]')).toBeVisible()
      await expectClean(page)
      await page.getByRole('textbox', { name: /YAML/ }).fill(SAMPLE_YAML)
      await expect(page.getByTestId('validation-summary')).toHaveAttribute('data-valid', 'true')
      await expect(page.locator('[data-code]')).toHaveCount(0)
      await page
        .getByRole('button', { name: language === 'en' ? 'Run checks' : 'जाँच चलाएँ' })
        .click()
      await expect(page.getByTestId('check-result')).toBeVisible()
      await page
        .getByRole('button', { name: language === 'en' ? 'Run preview' : 'पूर्वावलोकन चलाएँ' })
        .click()
      await expect(page.getByTestId('preview-map')).toBeVisible()
      await expectClean(page)
      await page.screenshot({
        path: `${OUT}/editor-${language}-${theme}-1920x1080.png`,
        fullPage: true,
      })
    })

    test('generator with results and the heat map', async ({ page }) => {
      await open(page, '/content/generator', prefs)
      await expect(page.getByTestId('heat-map')).toBeVisible()
      await page
        .getByRole('button', { name: language === 'en' ? 'Batch generate' : 'बैच उत्पन्न करें' })
        .click()
      await expect(page.getByTestId('result').first()).toBeVisible()
      await page.getByTestId('heat-map').locator('[data-x="1"][data-y="1"]').focus()
      await expectClean(page)
      await page.screenshot({
        path: `${OUT}/generator-${language}-${theme}-1920x1080.png`,
        fullPage: true,
      })
    })
  })
}

test('Hindi shows the lint and error codes through the catalogue, with the line number', async ({
  page,
}) => {
  await open(page, '/content/scenarios/editor', {
    language: 'hi',
    theme: 'dark',
    role: 'instructor',
  })
  await page.getByRole('textbox', { name: /YAML/ }).fill(SAMPLE_YAML_LINT)
  const item = page.locator('[data-code="timing.reaction-window"]')
  await expect(item).toContainText('प्रतिक्रिया-समय')
  await expect(item).toContainText('पंक्ति')
  await expect(item.locator('[lang="en"]')).toContainText('Threat reaches the inner zone')
  await page.getByRole('textbox', { name: /YAML/ }).fill(SAMPLE_YAML_ERRORS)
  await expect(page.locator('[data-code="schema.type"]')).toContainText('गलत प्रकार')
})
