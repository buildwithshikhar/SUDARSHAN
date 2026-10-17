import { vi } from 'vitest'

describe('stored preferences on load', () => {
  it('sets the html lang and theme from storage before the first render', async () => {
    window.localStorage.setItem('ui.language', 'hi')
    window.localStorage.setItem('ui.theme', 'light')
    vi.resetModules()
    await import('../src/i18n')
    await import('../src/lib/prefs')
    expect(document.documentElement.lang).toBe('hi')
    expect(document.documentElement.dataset.theme).toBe('light')
  })

  it('ignores unknown stored values', async () => {
    window.localStorage.setItem('ui.language', 'xx')
    window.localStorage.setItem('ui.theme', 'neon')
    vi.resetModules()
    await import('../src/i18n')
    await import('../src/lib/prefs')
    expect(document.documentElement.lang).toBe('en')
    expect(document.documentElement.dataset.theme).toBe('dark')
  })
})
