import { act, fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { renderApp } from '../utils'
import { installScenarioFetch } from './helpers'

const seed = () => screen.getByRole<HTMLInputElement>('textbox', { name: 'Seed' })

async function ready() {
  expect(await screen.findByRole('heading', { name: 'Generator studio', level: 1 })).toBeVisible()
  await screen.findByTestId('heat-map')
}

describe('generator studio', () => {
  it('has five labelled ranges 0 to 100 with a numeric readout', async () => {
    installScenarioFetch()
    renderApp('/content/generator')
    await ready()
    for (const name of ['Threat load', 'Ambiguity', 'Speed', 'Stealth', 'Degradation']) {
      const range = screen.getByRole('slider', { name })
      expect(range).toHaveAttribute('min', '0')
      expect(range).toHaveAttribute('max', '100')
    }
    expect(screen.getByTestId('out-threat_load')).toHaveTextContent('40')
    fireEvent.change(screen.getByRole('slider', { name: 'Threat load' }), {
      target: { value: '73' },
    })
    expect(screen.getByTestId('out-threat_load')).toHaveTextContent('73')
  })

  it('validates the request and disables Generate while it is invalid', async () => {
    installScenarioFetch()
    const user = userEvent.setup()
    renderApp('/content/generator')
    await ready()
    const generate = screen.getByRole('button', { name: 'Generate' })
    expect(generate).toBeEnabled()
    await user.click(screen.getByRole('checkbox', { name: 'Single' }))
    await user.click(screen.getByRole('checkbox', { name: 'Swarm' }))
    expect(screen.getByText('Choose at least one threat type.')).toBeInTheDocument()
    expect(generate).toBeDisabled()
    await user.click(screen.getByRole('checkbox', { name: 'Silent raid' }))
    expect(generate).toBeEnabled()
    await user.clear(seed())
    await user.type(seed(), '12x')
    expect(screen.getByText('Enter a whole number from 0 to 4294967295.')).toBeInTheDocument()
    expect(generate).toBeDisabled()
    await user.clear(seed())
    await user.type(seed(), '99')
    await user.clear(screen.getByLabelText('Oracle minimum score (%)'))
    await user.type(screen.getByLabelText('Oracle minimum score (%)'), '40')
    expect(screen.getByText('Enter a whole number from 50 to 100.')).toBeInTheDocument()
    expect(generate).toBeDisabled()
  })

  it('randomises the seed', async () => {
    installScenarioFetch()
    const user = userEvent.setup()
    renderApp('/content/generator')
    await ready()
    const before = seed().value
    await user.click(screen.getByRole('button', { name: 'Randomise' }))
    expect(seed().value).toMatch(/^\d+$/)
    expect(seed().value).not.toBe(before)
  })

  it('sends the request, and shows checks, wording, relaxations and features', async () => {
    const { seen } = installScenarioFetch()
    const user = userEvent.setup()
    renderApp('/content/generator')
    await ready()
    expect(screen.getByText('Nothing generated yet')).toBeInTheDocument()
    await user.clear(screen.getByLabelText('Oracle minimum score (%)'))
    await user.type(screen.getByLabelText('Oracle minimum score (%)'), '95')
    await user.clear(seed())
    await user.type(seed(), '48213907')
    await user.click(screen.getByRole('button', { name: 'Generate' }))
    const result = await screen.findByTestId('result')
    expect(result).toHaveAttribute('data-id', expect.stringMatching(/^gen-48213907-/))
    expect(within(result).getByTestId('result-wording')).toHaveTextContent(
      'Verified solvable by test run',
    )
    expect(within(result).getByRole('table')).toHaveTextContent('Every hostile contact was engaged')
    expect(within(result).getByTestId('relaxations')).toHaveTextContent(
      'diversity threshold halved',
    )
    expect(within(result).getByRole('group', { name: 'Feature vector' })).toHaveTextContent(
      'Timing tightness',
    )
    const call = seen.find((s) => s.path === '/generator/generate')!
    expect(call.csrf).toBe('csrf-token-1')
    expect(call.body).toMatchObject({
      save: false,
      request: {
        seed: 48213907,
        terrain: 'heron-ridge',
        oracle_min_score: 95,
        threat_mix: ['single', 'swarm'],
        difficulty: { threat_load: 40, ambiguity: 35, speed: 45, stealth: 20, degradation: 25 },
      },
    })
  })

  it('keeps a result with the same request and a save flag', async () => {
    const { seen } = installScenarioFetch()
    const user = userEvent.setup()
    renderApp('/content/generator')
    await ready()
    await user.click(screen.getByRole('button', { name: 'Generate' }))
    const result = await screen.findByTestId('result')
    await user.click(within(result).getByRole('button', { name: 'Save to the library' }))
    expect(await within(result).findByText('Saved to the library')).toBeInTheDocument()
    const calls = seen.filter((s) => s.path === '/generator/generate')
    expect(calls).toHaveLength(2)
    expect(calls[1]!.body).toMatchObject({
      save: true,
      request: (calls[0]!.body as never as { request: unknown }).request,
    })
  })

  it('batch generates between 1 and 12', async () => {
    const { seen } = installScenarioFetch()
    const user = userEvent.setup()
    renderApp('/content/generator')
    await ready()
    const count = screen.getByLabelText('Batch size')
    await user.clear(count)
    await user.type(count, '13')
    expect(screen.getByRole('button', { name: 'Batch generate' })).toBeDisabled()
    await user.clear(count)
    await user.type(count, '3')
    await user.click(screen.getByRole('button', { name: 'Batch generate' }))
    await waitFor(() => expect(screen.getAllByTestId('result')).toHaveLength(3))
    expect(seen.find((s) => s.path === '/generator/batch')?.body).toMatchObject({ count: 3 })
  })

  it('encodes, decodes and refuses a bad code', async () => {
    installScenarioFetch()
    const user = userEvent.setup()
    renderApp('/content/generator')
    await ready()
    await user.clear(seed())
    await user.type(seed(), '77120045')
    await user.selectOptions(screen.getByLabelText('Terrain'), 'osprey-town')
    await user.click(screen.getByRole('button', { name: 'Encode' }))
    const code = screen.getByRole<HTMLInputElement>('textbox', { name: 'Share code' })
    await waitFor(() => expect(code.value).toMatch(/^SD1-/))
    await user.clear(seed())
    await user.type(seed(), '5')
    await user.selectOptions(screen.getByLabelText('Terrain'), 'flat')
    await user.click(screen.getByRole('button', { name: 'Decode' }))
    await waitFor(() => expect(seed().value).toBe('77120045'))
    expect(screen.getByLabelText('Terrain')).toHaveValue('osprey-town')
    await user.clear(code)
    await user.type(code, 'SD1-NOPE')
    await user.click(screen.getByRole('button', { name: 'Decode' }))
    expect(await screen.findByText('That share code is not valid.')).toBeInTheDocument()
  })

  it('generates from a share code', async () => {
    const { seen } = installScenarioFetch()
    const user = userEvent.setup()
    renderApp('/content/generator')
    await ready()
    await user.click(screen.getByRole('button', { name: 'Encode' }))
    await user.click(screen.getByRole('button', { name: 'Generate from the share code' }))
    await screen.findByTestId('result')
    expect(seen.find((s) => s.path === '/generator/generate')?.body).toMatchObject({
      code: expect.stringMatching(/^SD1-/),
    })
  })

  it('draws the archive: 36 cells, a numeric scale and the three metrics', async () => {
    installScenarioFetch()
    renderApp('/content/generator')
    await ready()
    expect(within(screen.getByTestId('heat-map')).getAllByRole('gridcell')).toHaveLength(36)
    expect(screen.getByTestId('heat-legend')).toHaveTextContent('0.00')
    expect(screen.getByTestId('heat-legend')).toHaveTextContent('1.00')
    expect(screen.getByTestId('metric-coverage').textContent).toMatch(/^\d+\.\d%$/)
    expect(screen.getByTestId('archive-metrics')).toHaveTextContent('of 144 cells')
    expect(screen.getByTestId('metric-qd').textContent).toMatch(/^\d+\.\d{3}$/)
    expect(screen.getByTestId('metric-pairwise').textContent).toMatch(/^0\.\d{3}$/)
  })

  it('moves between heat-map cells with the arrow keys and reads each cell', async () => {
    installScenarioFetch()
    const user = userEvent.setup()
    renderApp('/content/generator')
    await ready()
    const cell = (x: number, y: number) =>
      document.querySelector<SVGGElement>(`[data-x="${x}"][data-y="${y}"]`)!
    act(() => cell(0, 0).focus())
    expect(screen.getByTestId('heat-tip')).toHaveTextContent('Threat count 1')
    await user.keyboard('{ArrowRight}')
    expect(cell(1, 0)).toHaveFocus()
    expect(screen.getByTestId('heat-tip')).toHaveTextContent('Threat count 2')
    await user.keyboard('{ArrowUp}')
    expect(cell(1, 1)).toHaveFocus()
    await user.keyboard('{End}')
    expect(cell(5, 1)).toHaveFocus()
    await user.keyboard('{ArrowRight}')
    expect(cell(5, 1)).toHaveFocus()
    await user.keyboard('{Home}')
    expect(cell(0, 1)).toHaveFocus()
    // exactly one cell is in the tab order
    expect(document.querySelectorAll('[role="gridcell"][tabindex="0"]')).toHaveLength(1)
  })

  it('reads an empty cell as empty', async () => {
    installScenarioFetch()
    renderApp('/content/generator')
    await ready()
    const empty = document.querySelector<SVGGElement>('[role="gridcell"][data-quality=""]')!
    act(() => empty.focus())
    expect(screen.getByTestId('heat-tip')).toHaveTextContent('empty')
  })

  it('switches the pair of axes', async () => {
    installScenarioFetch()
    const user = userEvent.setup()
    renderApp('/content/generator')
    await ready()
    await user.selectOptions(screen.getByLabelText('Columns'), '2')
    expect(within(screen.getByTestId('heat-map')).getAllByRole('gridcell')).toHaveLength(24)
    // choosing the other axis for the same one moves it aside
    await user.selectOptions(screen.getByLabelText('Rows'), '2')
    expect(screen.getByLabelText('Columns')).not.toHaveValue('2')
  })

  it('shows the empty archive, with all cells empty', async () => {
    installScenarioFetch({ variant: 'empty' })
    renderApp('/content/generator')
    await ready()
    expect(screen.getByText(/The archive holds no scenario yet/)).toBeInTheDocument()
    expect(screen.getByTestId('metric-coverage')).toHaveTextContent('0.0%')
  })

  it('shows an archive error with Retry, and a generation error', async () => {
    installScenarioFetch({ variant: 'error' })
    const user = userEvent.setup()
    renderApp('/content/generator')
    expect(await screen.findByText('The archive could not be loaded')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Generate' }))
    expect(await screen.findByText('No scenario could be generated')).toBeInTheDocument()
    installScenarioFetch()
    await user.click(screen.getAllByRole('button', { name: 'Retry' }).at(-1)!)
    await screen.findByTestId('heat-map')
  })

  it('shows a loading state while generating', async () => {
    installScenarioFetch({
      override: {
        'POST /generator/generate': () => new Promise<Response>(() => undefined),
      },
    })
    const user = userEvent.setup()
    renderApp('/content/generator')
    await ready()
    await user.click(screen.getByRole('button', { name: 'Generate' }))
    expect(await screen.findByText('Generating and checking scenarios')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Generating' })).toBeDisabled()
  })

  it('shows the Hindi interface', async () => {
    installScenarioFetch({ language: 'hi' })
    renderApp('/content/generator')
    expect(await screen.findByRole('heading', { name: 'जनरेटर स्टूडियो', level: 1 })).toBeVisible()
    await screen.findByTestId('heat-map')
    expect(screen.getByText('विविधता रिपोर्ट')).toBeInTheDocument()
  })
})
