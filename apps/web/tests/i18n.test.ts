import en from '../src/i18n/en.json'
import hi from '../src/i18n/hi.json'

function keys(node: unknown, prefix = ''): string[] {
  if (typeof node !== 'object' || node === null) return [prefix]
  return Object.entries(node).flatMap(([key, value]) =>
    keys(value, prefix ? `${prefix}.${key}` : key),
  )
}

describe('translation files', () => {
  it('have exactly the same keys in English and Hindi', () => {
    expect(keys(hi).sort()).toEqual(keys(en).sort())
  })

  it('have no empty strings', () => {
    for (const value of [...keys(en), ...keys(hi)]) expect(value).not.toBe('')
    const flat = JSON.stringify([en, hi])
    expect(flat).not.toMatch(/:\s*""/)
  })
})
