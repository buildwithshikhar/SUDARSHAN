import { execFileSync } from 'node:child_process'
import { cpSync, mkdtempSync, readdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'
import type {
  ActionRecordV1,
  EventRecordV1,
  RulePackV1,
  ScenarioV1,
  SensorProfileV1,
  SessionRecordV1,
  Vec3,
} from '../src/contracts'

const root = resolve(import.meta.dirname, '../../..')
const webDir = resolve(root, 'apps/web')
const contractsDir = resolve(webDir, 'src/contracts')

function runCheck(...extra: string[]): string {
  return execFileSync('node', ['scripts/contracts.mjs', '--check', ...extra], {
    cwd: webDir,
    encoding: 'utf-8',
    stdio: 'pipe',
  })
}

// Narrow helper: the parsed JSON is accepted as a scenario only after its contract tag matches.
function asScenario(value: unknown): ScenarioV1 {
  if (typeof value !== 'object' || value === null || !('contract' in value)) {
    throw new Error('not a scenario document')
  }
  if (value.contract !== 'scenario.v1') throw new Error('unexpected contract tag')
  return value as ScenarioV1
}

describe('contract types', () => {
  it('are up to date with packs/schemas', () => {
    expect(runCheck()).toMatch(/^\d+ contract type files up to date/)
  })

  it('exposes a stable public name for every schema', () => {
    // Compile-time only: every alias must resolve, otherwise typecheck fails.
    type Names = [
      ScenarioV1,
      RulePackV1,
      SensorProfileV1,
      EventRecordV1,
      ActionRecordV1,
      SessionRecordV1,
    ]
    const count: Names['length'] = 6
    expect(count).toBe(6)
  })

  it('types the example scenario', () => {
    const scenario = asScenario(
      JSON.parse(
        readFileSync(resolve(root, 'packs/scenarios/kestrel-dawn-approach.v1.json'), 'utf-8'),
      ),
    )
    expect(scenario.contract).toBe('scenario.v1')
    expect(scenario.fictional).toBe(true)
    expect(scenario.threats).toHaveLength(2)
    const position: Vec3 | undefined = scenario.assets?.[0]?.position
    expect(position).toBeDefined()
  })

  describe('drift check', () => {
    let dir = ''
    beforeEach(() => {
      dir = mkdtempSync(join(tmpdir(), 'contracts-'))
      cpSync(contractsDir, dir, { recursive: true })
    })
    afterEach(() => rmSync(dir, { recursive: true, force: true }))

    it('passes on an untouched copy', () => {
      expect(runCheck('--out', dir)).toContain('up to date')
    })

    it('fails and names the file when a generated file is altered', () => {
      const target = join(dir, 'scenario.v1.ts')
      writeFileSync(target, readFileSync(target, 'utf-8') + '\nexport type Extra = string\n')
      let stderr = ''
      let status: number | null = null
      try {
        runCheck('--out', dir)
      } catch (error) {
        const failure = error as { status: number | null; stderr: Buffer | string }
        status = failure.status
        stderr = failure.stderr.toString()
      }
      expect(status).toBe(1)
      expect(stderr).toContain('scenario.v1.ts')
      expect(stderr).toContain('make schemas')
    })

    it('fails on an extra file no schema produces', () => {
      writeFileSync(join(dir, 'orphan.v1.ts'), 'export type Orphan = string\n')
      expect(readdirSync(dir)).toContain('orphan.v1.ts')
      expect(() => runCheck('--out', dir)).toThrow()
    })
  })
})
