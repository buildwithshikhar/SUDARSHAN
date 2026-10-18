import { execFileSync } from 'node:child_process'
import { mkdtempSync, readdirSync, readFileSync, rmSync, statSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { createTransport } from '../../src/live/createTransport'
import { MOCK_MARKER, ScriptedTransport } from '../../src/live/mock'
import { MOCK_SCORE_MARKER } from '../../src/live/mockScore'
import { WebSocketTransport } from '../../src/live/transport'

const webDir = resolve(import.meta.dirname, '../..')

function files(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name)
    return statSync(path).isDirectory() ? files(path) : [path]
  })
}

describe('the scripted session is development only', () => {
  afterEach(() => vi.unstubAllEnvs())

  it('is chosen by ?mock=1 in the dev server', async () => {
    expect(await createTransport('s1', '?mock=1&speed=4')).toBeInstanceOf(ScriptedTransport)
    expect(await createTransport('s1', '')).toBeInstanceOf(WebSocketTransport)
    expect(await createTransport('s1', '?mock=0')).toBeInstanceOf(WebSocketTransport)
  })

  it('is never chosen when DEV is off, whatever the address says', async () => {
    vi.stubEnv('DEV', false)
    expect(await createTransport('s1', '?mock=1')).toBeInstanceOf(WebSocketTransport)
  })

  it('is absent from a production build, while the real transport and the EO view are present', () => {
    const out = mkdtempSync(join(tmpdir(), 'live-build-'))
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
      const text = files(out)
        .filter((f) => /\.(js|css|html)$/.test(f))
        .map((f) => readFileSync(f, 'utf-8'))
        .join('\n')
      expect(text).not.toContain(MOCK_MARKER)
      expect(text).not.toContain('ScriptedTransport')
      expect(text).not.toContain('mock-session')
      // nor is the scripted score the debrief shows for ?mock=1
      expect(text).not.toContain(MOCK_SCORE_MARKER)
      expect(text).not.toContain('th-quad')
      expect(text).not.toContain('mockScore')
      // sanity: the debrief itself is in the bundle
      expect(text).toContain('/score')
      // the demo scenario's own text is not in the bundle either
      expect(text).not.toContain('Harrier Field')
      // sanity: the build is a real one with the live code in it
      expect(text).toContain('WebGLRenderer')
      expect(text).toMatch(/\/ws/)
    } finally {
      rmSync(out, { recursive: true, force: true })
    }
  }, 180_000)
})
