import { execFileSync } from 'node:child_process'
import { mkdtempSync, readdirSync, readFileSync, rmSync, statSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const webDir = resolve(import.meta.dirname, '../..')

function files(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name)
    return statSync(path).isDirectory() ? files(path) : [path]
  })
}

describe('the scripted scenario API is development only', () => {
  it('is absent from a production build, while the screens and the real client are present, in lazy chunks', () => {
    const out = mkdtempSync(join(tmpdir(), 'scenarios-build-'))
    try {
      execFileSync(
        'npx',
        ['vite', 'build', '--outDir', out, '--emptyOutDir', '--logLevel', 'error'],
        {
          cwd: webDir,
          stdio: 'pipe',
          env: { ...process.env, NODE_ENV: 'production' },
        },
      )
      const js = files(out).filter((f) => f.endsWith('.js'))
      const text = js.map((f) => readFileSync(f, 'utf-8')).join('\n')
      for (const marker of [
        'marlin-hill-evening-picket',
        'Marlin Hill',
        'curriculum-05-town-edge-swarm',
        'gen-48213907',
        'createMockBackend',
        'th-quad-a',
      ])
        expect(text, marker).not.toContain(marker)
      // the real client and the screens are there
      expect(text).toContain('/scenario-library')
      expect(text).toContain('/generator/archive')
      expect(text).toContain('/scenario-tools/check')
      // the three screens are not in the entry chunk that index.html loads first
      const html = readFileSync(join(out, 'index.html'), 'utf-8')
      const entry = /src="\/?(assets\/[^"]+\.js)"/.exec(html)?.[1]
      expect(entry).toBeDefined()
      const entryText = readFileSync(join(out, entry!), 'utf-8')
      expect(entryText).not.toContain('/generator/archive')
      expect(entryText).not.toContain('/scenario-tools/preview')
    } finally {
      rmSync(out, { recursive: true, force: true })
    }
  }, 120_000)
})
