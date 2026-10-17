import en from '../src/i18n/en.json'
import hi from '../src/i18n/hi.json'

function keys(node: unknown, prefix = ''): string[] {
  if (typeof node !== 'object' || node === null) return [prefix]
  return Object.entries(node).flatMap(([key, value]) =>
    keys(value, prefix ? `${prefix}.${key}` : key),
  )
}

function leaves(node: unknown): string[] {
  if (typeof node === 'string') return [node]
  if (typeof node !== 'object' || node === null) return []
  return Object.values(node).flatMap(leaves)
}

describe('translation files', () => {
  it('have exactly the same keys in English and Hindi', () => {
    expect(keys(hi).sort()).toEqual(keys(en).sort())
  })

  it('have no empty strings', () => {
    for (const value of [...leaves(en), ...leaves(hi)]) expect(value.trim()).not.toBe('')
  })

  it('keep the same interpolation placeholders', () => {
    const placeholders = (s: string) => (s.match(/{{\w+}}/g) ?? []).sort().join()
    const enFlat = Object.fromEntries(
      keys(en).map((k) => [
        k,
        k.split('.').reduce<unknown>((n, p) => (n as Record<string, unknown>)[p], en),
      ]),
    )
    const hiFlat = Object.fromEntries(
      keys(hi).map((k) => [
        k,
        k.split('.').reduce<unknown>((n, p) => (n as Record<string, unknown>)[p], hi),
      ]),
    )
    for (const key of Object.keys(enFlat)) {
      expect(placeholders(String(hiFlat[key])), key).toBe(placeholders(String(enFlat[key])))
    }
  })

  it('never describe the Hindi as verified or reviewed', () => {
    const all = [...leaves(en), ...leaves(hi)].join(' ')
    expect(all).not.toMatch(/(translation|hindi)[^.]*\b(verified|reviewed)\b/i)
  })
})
