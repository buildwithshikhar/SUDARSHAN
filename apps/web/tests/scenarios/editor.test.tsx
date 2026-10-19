import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { SAMPLE_YAML, SAMPLE_YAML_ERRORS, SAMPLE_YAML_LINT } from '../../src/scenarios/samples'
import { renderApp } from '../utils'
import { installScenarioFetch } from './helpers'

const area = () => screen.getByRole<HTMLTextAreaElement>('textbox', { name: 'Scenario YAML text' })
const lineAtCaret = () => area().value.slice(0, area().selectionStart).split('\n').length
const lineOf = (text: string, start: string) =>
  text.split('\n').findIndex((l) => l.trimStart().startsWith(start)) + 1

/** Replace the whole text at once, as a paste would. */
async function paste(text: string) {
  const field = await screen.findByRole('textbox', { name: /YAML/ })
  fireEvent.change(field, { target: { value: text } })
}

describe('scenario editor', () => {
  it('opens a scenario by id and summarises it', async () => {
    installScenarioFetch()
    renderApp('/content/scenarios/editor/marlin-hill-evening-picket')
    await waitFor(() => expect(area().value).toContain('id: marlin-hill-evening-picket'))
    const summary = await screen.findByTestId('validation-summary')
    expect(summary).toHaveAttribute('data-valid', 'true')
    expect(summary).toHaveTextContent('Errors: 0 · Warnings: 0')
    expect(screen.getByRole('table', { name: 'Threats by spawn time' })).toHaveTextContent(
      'th-quad-a',
    )
    expect(screen.getByTestId('time-strip')).toBeInTheDocument()
    expect(screen.getByRole('table', { name: 'Sensors placed in the scenario' })).toHaveTextContent(
      'radar-generic-s 0.2.0',
    )
    expect(screen.getByRole('heading', { name: 'Weather and light' })).toBeInTheDocument()
    expect(screen.getByRole('table', { name: 'Zones' })).toHaveTextContent('500 m')
  })

  it('draws a line-number gutter that follows the text', async () => {
    installScenarioFetch()
    renderApp('/content/scenarios/editor')
    await paste('a\nb\nc')
    const gutter = await screen.findByTestId('gutter')
    expect(
      within(gutter)
        .getAllByText(/^\d+$/)
        .map((n) => n.textContent),
    ).toEqual(['1', '2', '3'])
    expect(screen.getByTestId('caret').textContent).toContain('Lines: 3')
  })

  it('reports errors with their line numbers, in the catalogue wording, and jumps to the line', async () => {
    installScenarioFetch()
    const user = userEvent.setup()
    renderApp('/content/scenarios/editor')
    await paste(SAMPLE_YAML_ERRORS)
    const durationLine = lineOf(SAMPLE_YAML_ERRORS, 'duration_s: soon')
    const item = await screen.findByRole('button', {
      name: new RegExp(`Line ${durationLine}(?!\\d)`),
    })
    expect(item).toHaveAttribute('data-code', 'schema.type')
    expect(item).toHaveTextContent('A field is missing, unknown or has the wrong type.')
    expect(item).toHaveTextContent('Input should be a valid number.')
    expect(screen.getByTestId('validation-summary')).toHaveAttribute('data-valid', 'false')
    await user.click(item)
    expect(lineAtCaret()).toBe(durationLine)
    expect(area()).toHaveFocus()
    expect(screen.getByTestId('caret')).toHaveTextContent(`Line ${durationLine},`)
    // the gutter marks the line with an icon
    expect(
      screen.getByTestId('gutter').querySelector(`[data-line="${durationLine}"] svg`),
    ).not.toBeNull()
  })

  it('jumps with Enter from the keyboard', async () => {
    installScenarioFetch()
    const user = userEvent.setup()
    renderApp('/content/scenarios/editor')
    await paste(SAMPLE_YAML_ERRORS)
    const tabLine = SAMPLE_YAML_ERRORS.split('\n').findIndex((l) => l.startsWith('\t')) + 1
    const item = await screen.findByRole('button', { name: new RegExp(`Line ${tabLine}(?!\\d)`) })
    item.focus()
    await user.keyboard('{Enter}')
    expect(lineAtCaret()).toBe(tabLine)
  })

  it('lints a threat timed before the reaction window with the offending line', async () => {
    installScenarioFetch()
    renderApp('/content/scenarios/editor')
    await paste(SAMPLE_YAML_LINT)
    const line = lineOf(SAMPLE_YAML_LINT, 'spawn_s: 12')
    const item = await screen.findByRole('button', {
      name: new RegExp(`Line ${line}(?!\\d).*Error`),
    })
    expect(item).toHaveAttribute('data-code', 'timing.reaction-window')
    expect(item).toHaveTextContent(
      "A hostile contact reaches the inner zone before the rule pack's minimum reaction time.",
    )
    const warning = screen.getByRole('button', { name: /Warning/ })
    expect(warning).toHaveAttribute('data-code', 'group.link-range')
    expect(screen.getByTestId('validation-summary')).toHaveTextContent('Errors: 1 · Warnings: 1')
  })

  it('falls back to the server message when a code has no catalogue entry', async () => {
    installScenarioFetch({
      override: {
        'POST /scenario-tools/validate': () =>
          new Response(
            JSON.stringify({
              valid: false,
              errors: [
                {
                  line: 3,
                  column: 2,
                  path: 'x',
                  message: 'Odd new problem.',
                  code: 'future.thing',
                },
              ],
              lint: [
                {
                  code: 'future.lint',
                  severity: 'warning',
                  line: 5,
                  column: 1,
                  message: 'New lint rule fired.',
                  params: {},
                },
              ],
              spec: null,
            }),
          ),
      },
    })
    renderApp('/content/scenarios/editor')
    await paste('contract: scenario.v1\nx: 1\ny: 2\nz: 3\nw: 4\n')
    expect(await screen.findByText('Odd new problem.')).toBeInTheDocument()
    expect(screen.getByText('New lint rule fired.')).toBeInTheDocument()
    expect(screen.getByText('Line 3')).toBeInTheDocument()
    expect(screen.getByText('Line 5')).toBeInTheDocument()
  })

  it('debounces validation: one request after typing stops', async () => {
    const { seen } = installScenarioFetch()
    renderApp('/content/scenarios/editor')
    await paste('c')
    await paste('co')
    await paste('con')
    await screen.findByTestId('validation-summary')
    expect(seen.filter((s) => s.path === '/scenario-tools/validate')).toHaveLength(1)
  })

  it('runs the checks and shows the four checks, the wording and the diversity result', async () => {
    const { seen } = installScenarioFetch()
    const user = userEvent.setup()
    renderApp('/content/scenarios/editor/marlin-hill-evening-picket')
    await screen.findByTestId('validation-summary')
    await user.click(screen.getByRole('button', { name: 'Run checks' }))
    const wording = await screen.findByTestId('solvability-wording')
    expect(wording).toHaveTextContent('Verified solvable by test run')
    expect(wording).toHaveAttribute('data-wording', 'verified solvable by test run')
    const checks = screen.getByRole('table', { name: 'Solvability checks' })
    expect(within(checks).getAllByRole('row')).toHaveLength(5)
    expect(checks).toHaveTextContent('Every hostile contact was reported by a sensor')
    expect(checks).toHaveTextContent('92.0%')
    expect(screen.getByTestId('diversity')).toHaveTextContent('Passes')
    expect(screen.getByTestId('check-result')).toHaveTextContent('reference data')
    const call = seen.find((s) => s.path === '/scenario-tools/check')!
    expect(call.csrf).toBe('csrf-token-1')
  })

  it('sends the test seed and shows "Not verified solvable" when the oracle fails', async () => {
    const { seen } = installScenarioFetch()
    const user = userEvent.setup()
    renderApp('/content/scenarios/editor/marlin-hill-evening-picket')
    await screen.findByTestId('validation-summary')
    await user.type(screen.getByLabelText('Test seed'), '14')
    await user.click(screen.getByRole('button', { name: 'Run checks' }))
    expect(await screen.findByTestId('solvability-wording')).toHaveTextContent(
      'Not verified solvable',
    )
    expect(seen.find((s) => s.path === '/scenario-tools/check')?.body).toMatchObject({ seed: 14 })
  })

  it('says the oracle did not run when the text has lint errors', async () => {
    installScenarioFetch()
    const user = userEvent.setup()
    renderApp('/content/scenarios/editor')
    await paste(SAMPLE_YAML_LINT)
    await screen.findByTestId('validation-summary')
    await user.click(screen.getByRole('button', { name: 'Run checks' }))
    expect(await screen.findByText('The oracle did not run')).toBeInTheDocument()
    expect(screen.queryByTestId('solvability-wording')).toBeNull()
  })

  it('previews the run on a top-down map with the contact table', async () => {
    installScenarioFetch()
    const user = userEvent.setup()
    renderApp('/content/scenarios/editor/marlin-hill-evening-picket')
    await screen.findByTestId('validation-summary')
    await user.click(screen.getByRole('button', { name: 'Run preview' }))
    expect(await screen.findByTestId('preview-map')).toBeInTheDocument()
    expect(document.querySelectorAll('[data-path]')).toHaveLength(3)
    expect(screen.getByRole('table', { name: 'Contacts in the preview run' })).toHaveTextContent(
      '61.4 s',
    )
    expect(screen.getByRole('table', { name: 'Sensor coverage of each threat' })).toHaveTextContent(
      'radar-1, eo-1, rf-1',
    )
  })

  it('saves with tags, and the id and title come from the text', async () => {
    const { seen } = installScenarioFetch()
    const user = userEvent.setup()
    renderApp('/content/scenarios/editor/marlin-hill-evening-picket')
    await screen.findByTestId('validation-summary')
    await user.click(screen.getByRole('button', { name: 'Save' }))
    const dialog = await screen.findByRole('dialog', { name: 'Save scenario' })
    expect(dialog).toHaveTextContent('marlin-hill-evening-picket')
    await user.type(within(dialog).getByLabelText('Tags'), 'rural, pair ,')
    await user.click(within(dialog).getByRole('button', { name: 'Save scenario' }))
    expect(
      await screen.findByText('Saved marlin-hill-evening-picket to the library.'),
    ).toBeVisible()
    const call = seen.find((s) => s.method === 'POST' && s.path === '/scenario-library')!
    expect(call.body).toMatchObject({ tags: ['rural', 'pair'] })
    expect((call.body as { yaml: string }).yaml).toBe(SAMPLE_YAML)
    expect(call.csrf).toBe('csrf-token-1')
  })

  it('keeps Save closed until the text validates', async () => {
    installScenarioFetch()
    renderApp('/content/scenarios/editor')
    expect(await screen.findByRole('button', { name: 'Save' })).toBeDisabled()
    await paste(SAMPLE_YAML_ERRORS)
    await screen.findByTestId('validation-summary')
    expect(screen.getByRole('button', { name: 'Save' })).toBeDisabled()
  })

  it('shows an empty state with no text', async () => {
    installScenarioFetch()
    renderApp('/content/scenarios/editor')
    expect(await screen.findByText('No scenario text yet')).toBeInTheDocument()
    expect(screen.getAllByText('Nothing to summarise yet')).toHaveLength(4)
  })

  it('shows a not-found state for an unknown id and an error state with retry', async () => {
    installScenarioFetch()
    renderApp('/content/scenarios/editor/nope')
    expect(await screen.findByText('No scenario with that id')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Open the scenario library' })).toBeInTheDocument()
  })

  it('shows an error state with Retry when the load fails', async () => {
    installScenarioFetch({ variant: 'error' })
    const user = userEvent.setup()
    renderApp('/content/scenarios/editor/marlin-hill-evening-picket')
    expect(await screen.findByText('The scenario could not be loaded')).toBeInTheDocument()
    installScenarioFetch()
    await user.click(screen.getByRole('button', { name: 'Retry' }))
    await waitFor(() => expect(area().value).toContain('marlin-hill-evening-picket'))
  })

  it('shows a loading state while the scenario is fetched', async () => {
    let release: () => void = () => undefined
    installScenarioFetch({ gate: new Promise<void>((r) => (release = r)) })
    renderApp('/content/scenarios/editor/marlin-hill-evening-picket')
    expect(await screen.findByText('Loading the scenario')).toBeInTheDocument()
    release()
    await waitFor(() => expect(area().value).toContain('marlin-hill-evening-picket'))
  })

  it('shows an error with Retry when validation cannot be reached', async () => {
    installScenarioFetch({
      override: {
        'POST /scenario-tools/validate': () => new Response('{}', { status: 500 }),
      },
    })
    renderApp('/content/scenarios/editor')
    await paste(SAMPLE_YAML)
    expect(await screen.findByText('The text could not be validated')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument()
  })

  it('opens another scenario by id from the toolbar', async () => {
    installScenarioFetch()
    const user = userEvent.setup()
    renderApp('/content/scenarios/editor')
    await user.type(
      await screen.findByLabelText('Open by scenario id'),
      'example-minimal-single{Enter}',
    )
    await waitFor(() => expect(area().value).toContain('id: example-minimal-single'))
  })

  it('renders the Hindi catalogue text with the line number and the English server detail', async () => {
    installScenarioFetch({ language: 'hi' })
    renderApp('/content/scenarios/editor')
    await paste(SAMPLE_YAML_LINT)
    const line = lineOf(SAMPLE_YAML_LINT, 'spawn_s: 12')
    const item = await screen.findByRole('button', { name: new RegExp(`पंक्ति ${line}(?!\\d)`) })
    expect(item).toHaveTextContent('प्रतिक्रिया-समय')
    expect(item.querySelector('[lang="en"]')).toHaveTextContent('Threat reaches the inner zone')
  })
})
