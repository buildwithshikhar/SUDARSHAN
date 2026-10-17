import { execFileSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const root = resolve(import.meta.dirname, '../../..')

describe('Hindi review sheet', () => {
  it('is up to date with the translation files', () => {
    expect(() =>
      execFileSync('node', ['scripts/hi-review.mjs', '--check'], {
        cwd: resolve(root, 'apps/web'),
        stdio: 'pipe',
      }),
    ).not.toThrow()
  })

  it('states that the Hindi is unreviewed and never calls it verified', () => {
    const sheet = readFileSync(resolve(root, 'docs/i18n/HI_REVIEW.md'), 'utf-8')
    expect(sheet).toContain('Status: unreviewed')
    expect(sheet).not.toMatch(/\b(reviewed by|verified by|approved by)\b/i)
  })
})
