import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, vi } from 'vitest'
import brand from '../../../brand.json'
import App from '../src/App'
import i18n from '../src/i18n'

const info = {
  productName: brand.productName,
  descriptor: brand.descriptor,
  version: '0.1.0',
  gitSha: 'abc1234',
  buildTime: '2026-01-01T00:00:00Z',
  env: 'demo',
}

function mockFetch(impl: () => Promise<Response>) {
  vi.stubGlobal('fetch', vi.fn(impl))
}
const ok = () => Promise.resolve(new Response(JSON.stringify(info), { status: 200 }))

beforeEach(async () => {
  await i18n.changeLanguage('en')
})
afterEach(() => vi.unstubAllGlobals())

describe('build status screen', () => {
  it('shows loading rows, then the live version', async () => {
    mockFetch(ok)
    render(<App />)
    expect(screen.getByLabelText('Loading build information')).toBeInTheDocument()
    expect(await screen.findByText('abc1234')).toBeInTheDocument()
    expect(screen.getByText('Reachable')).toBeInTheDocument()
    expect(screen.getByText('2026-01-01T00:00:00Z')).toBeInTheDocument()
  })

  it('shows the error state and retries', async () => {
    let calls = 0
    mockFetch(() => (calls++ === 0 ? Promise.reject(new Error('down')) : ok()))
    render(<App />)
    expect(await screen.findByRole('alert')).toHaveTextContent('did not respond')
    await userEvent.click(screen.getByRole('button', { name: 'Retry' }))
    expect(await screen.findByText('abc1234')).toBeInTheDocument()
  })

  it('treats a non-200 response as an error', async () => {
    mockFetch(() => Promise.resolve(new Response('no', { status: 503 })))
    render(<App />)
    expect(await screen.findByRole('alert')).toBeInTheDocument()
  })

  it('reads the product name from brand.json', async () => {
    mockFetch(ok)
    render(<App />)
    expect(screen.getAllByText(brand.productName).length).toBeGreaterThan(0)
    expect(screen.getByText(brand.descriptor)).toBeInTheDocument()
    await screen.findByText('abc1234')
  })

  it('always shows the scenario label, in both languages', async () => {
    mockFetch(ok)
    render(<App />)
    expect(screen.getByText('Fictional scenarios · open-source parameters')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'हिन्दी' }))
    expect(screen.getByText('काल्पनिक परिदृश्य · ओपन-सोर्स पैरामीटर')).toBeInTheDocument()
    expect(document.documentElement.lang).toBe('hi')
    expect(window.localStorage.getItem('ui.language')).toBe('hi')
    await waitFor(() => expect(screen.getByRole('heading')).toHaveTextContent('बिल्ड स्थिति'))
  })

  it('switches theme and persists it', async () => {
    mockFetch(ok)
    render(<App />)
    expect(document.documentElement.dataset.theme).toBe('dark')
    await userEvent.click(screen.getByRole('button', { name: 'Light' }))
    expect(document.documentElement.dataset.theme).toBe('light')
    expect(window.localStorage.getItem('ui.theme')).toBe('light')
  })

  it('works when storage is blocked', async () => {
    mockFetch(ok)
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    render(<App />)
    await userEvent.click(screen.getByRole('button', { name: 'Light' }))
    expect(document.documentElement.dataset.theme).toBe('light')
    vi.restoreAllMocks()
  })
})
