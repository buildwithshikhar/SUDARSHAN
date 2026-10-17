import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const css = readFileSync(resolve(__dirname, '../src/styles/tokens.css'), 'utf-8')

type Tokens = Record<string, string>

function theme(selector: string): Tokens {
  const block = css.split('}').find((b) => b.includes(selector))
  if (!block) throw new Error(`no block for ${selector}`)
  return Object.fromEntries(
    [...block.matchAll(/--([a-z0-9-]+):\s*(#[0-9a-f]{6})/gi)].map((m) => [m[1], m[2]]),
  ) as Tokens
}

function colour(tokens: Tokens, key: string): string {
  const value = tokens[key]
  if (!value) throw new Error(`missing token ${key}`)
  return value
}

function luminance(hex: string): number {
  const [r = 0, g = 0, b = 0] = [1, 3, 5]
    .map((i) => parseInt(hex.slice(i, i + 2), 16) / 255)
    .map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4))
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}

function contrast(tokens: Tokens, a: string, b: string): number {
  const [light = 0, dark = 0] = [luminance(colour(tokens, a)), luminance(colour(tokens, b))].sort(
    (x, y) => y - x,
  )
  return (light + 0.05) / (dark + 0.05)
}

const grounds = ['bg', 'surface-1', 'surface-2'] as const
const trackKeys = ['hostile', 'suspect', 'unknown', 'neutral', 'friend'].map((k) => `track-${k}`)

describe.each([
  ['dark', ":root,\n[data-theme='dark']"],
  ['light', "[data-theme='light'] {\n  --bg"],
])('%s theme tokens', (_name, selector) => {
  const t = theme(selector)

  it('defines every token', () => {
    for (const key of [
      'bg',
      'surface-1',
      'surface-2',
      'border',
      'text',
      'text-2',
      'accent',
      'signal',
      ...trackKeys,
    ]) {
      expect(t[key], key).toMatch(/^#[0-9a-f]{6}$/i)
    }
  })

  it.each(grounds)('text and secondary text meet 4.5:1 on %s', (ground) => {
    expect(contrast(t, 'text', ground)).toBeGreaterThanOrEqual(4.5)
    expect(contrast(t, 'text-2', ground)).toBeGreaterThanOrEqual(4.5)
  })

  it('text on an accent fill meets 4.5:1', () => {
    expect(contrast(t, 'on-accent', 'accent')).toBeGreaterThanOrEqual(4.5)
  })

  it.each(grounds)('accent text meets 4.5:1 on %s', (ground) => {
    expect(contrast(t, 'accent', ground)).toBeGreaterThanOrEqual(4.5)
  })

  it('UI marks (signal and track colours) meet 3:1 on the panel surface', () => {
    for (const key of ['signal', ...trackKeys]) {
      expect(contrast(t, key, 'surface-1'), key).toBeGreaterThanOrEqual(3)
    }
  })
})
