import { describe, expect, it, vi } from 'vitest'
import { ApiError, setCsrfToken } from '../../src/lib/api'
import { scenarioApi } from '../../src/scenarios/api'
import { heatMapFor, tint } from '../../src/scenarios/heatModel'
import {
  checkText,
  createMockBackend,
  decodeCode,
  encodeRequest,
  generateFrom,
  mockArchive,
  MOCK_LIBRARY,
  previewText,
  validateText,
} from '../../src/scenarios/mock'
import { SAMPLE_YAML, SAMPLE_YAML_ERRORS, SAMPLE_YAML_LINT } from '../../src/scenarios/samples'
import { positionOf } from '../../src/scenarios/CodeEditor'
import { flightTimeS } from '../../src/scenarios/charts'
import { SAMPLE_SPEC } from '../../src/scenarios/mock'
import { DIFFICULTY_AXES, type GeneratorRequest } from '../../src/scenarios/types'
import { mockApi } from '../utils'

const REQUEST: GeneratorRequest = {
  seed: 77120045,
  terrain: 'osprey-town',
  time_of_day: 'night',
  weather: 'fog',
  difficulty: { threat_load: 61, ambiguity: 44, speed: 29, stealth: 73, degradation: 52 },
  threat_mix: ['swarm', 'silent-raid'],
  oracle_min_score: 85,
  max_attempts: 16,
}

describe('the REST client', () => {
  it('reads the library from a bare list or a wrapped one', async () => {
    mockApi({ 'GET /api/v1/scenario-library': { body: { scenarios: MOCK_LIBRARY } } })
    expect(await scenarioApi('').list()).toHaveLength(14)
    mockApi({ 'GET /api/v1/scenario-library': { body: MOCK_LIBRARY } })
    expect(await scenarioApi('').list()).toHaveLength(14)
  })

  it('sends writes with the CSRF header and a JSON body, and reads never do', async () => {
    setCsrfToken('tok-9')
    const calls = mockApi({
      'GET /api/v1/scenario-library/a%2Fb': { body: {} },
      'POST /api/v1/scenario-tools/check': { body: {} },
      'POST /api/v1/scenario-tools/preview': { body: {} },
      'POST /api/v1/scenario-library': { body: {} },
      'DELETE /api/v1/scenario-library/x': { status: 204 },
    })
    const api = scenarioApi('')
    await api.get('a/b')
    await api.check('k: v', 7)
    await api.preview('k: v')
    await api.save({ yaml: 'k: v', tags: ['t'] })
    await api.remove('x')
    const [get, check, preview, save, del] = calls
    expect(new Headers(get!.init?.headers).get('X-CSRF-Token')).toBeNull()
    for (const c of [check!, preview!, save!, del!])
      expect(new Headers(c.init?.headers).get('X-CSRF-Token')).toBe('tok-9')
    expect(JSON.parse(String(check!.init?.body))).toEqual({ yaml: 'k: v', seed: 7 })
    expect(JSON.parse(String(preview!.init?.body))).toEqual({ yaml: 'k: v' })
    expect(JSON.parse(String(save!.init?.body))).toEqual({ yaml: 'k: v', tags: ['t'] })
    expect(del!.init?.method).toBe('DELETE')
  })

  it('talks to the generator endpoints', async () => {
    const calls = mockApi({
      'POST /api/v1/generator/generate': { body: { id: 'g' } },
      'POST /api/v1/generator/batch': { body: [{ id: 'g' }] },
      'GET /api/v1/generator/archive': { body: { cells: [] } },
      'GET /api/v1/generator/code?code=SD1-A%20B': { body: REQUEST },
      'POST /api/v1/generator/code': { body: { code: 'SD1-XYZ' } },
    })
    const api = scenarioApi('')
    await api.generate({ code: 'SD1-A', save: true })
    expect(await api.batch({ request: REQUEST, count: 2 })).toHaveLength(1)
    await api.archive()
    expect((await api.decode('SD1-A B')).request.seed).toBe(77120045)
    expect(await api.encode(REQUEST)).toBe('SD1-XYZ')
    expect(JSON.parse(String(calls[0]!.init?.body))).toEqual({ code: 'SD1-A', save: true })
    expect(JSON.parse(String(calls[4]!.init?.body))).toEqual({ request: REQUEST })
  })

  it('accepts a decoded code that carries a warning', async () => {
    mockApi({
      'GET /api/v1/generator/code?code=c': {
        body: { request: REQUEST, warning: 'made by 0.9', generator_version: '0.9' },
      },
    })
    expect(await scenarioApi('').decode('c')).toMatchObject({ warning: 'made by 0.9' })
  })

  it('turns validation-style error bodies into one message', async () => {
    mockApi({
      'POST /api/v1/scenario-tools/validate': {
        status: 422,
        body: {
          detail: [
            { loc: ['body', 'yaml'], msg: 'Field required' },
            { loc: [], msg: 'Bad' },
          ],
        },
      },
    })
    await expect(scenarioApi('').validate('x')).rejects.toMatchObject({
      status: 422,
      message: 'Field required; Bad',
    })
    mockApi({ 'GET /api/v1/generator/archive': { status: 403, body: { detail: 'forbidden' } } })
    await expect(scenarioApi('').archive()).rejects.toBeInstanceOf(ApiError)
  })

  it('is the scripted backend only for ?mock=1 in the dev server', async () => {
    const fetchSpy = vi.fn(() => Promise.reject(new TypeError('no network')))
    vi.stubGlobal('fetch', fetchSpy)
    expect(await scenarioApi('?mock=1').list()).toHaveLength(14)
    expect(fetchSpy).not.toHaveBeenCalled()
    expect(await scenarioApi('?mock=1&scn=empty').list()).toHaveLength(0)
    await expect(scenarioApi('').list()).rejects.toThrow()
    expect(fetchSpy).toHaveBeenCalledTimes(1)
    vi.stubEnv('DEV', false)
    await expect(scenarioApi('?mock=1').list()).rejects.toThrow()
    expect(fetchSpy).toHaveBeenCalledTimes(2)
    vi.unstubAllEnvs()
  })
})

describe('the scripted fixtures', () => {
  it('cover every origin, solvability status, terrain and time of day', () => {
    const has = <K extends keyof (typeof MOCK_LIBRARY)[number]>(key: K) =>
      new Set(MOCK_LIBRARY.map((r) => r[key]))
    expect(MOCK_LIBRARY).toHaveLength(14)
    expect(has('origin')).toEqual(new Set(['scripted', 'generated', 'authored', 'example']))
    expect(new Set(MOCK_LIBRARY.map((r) => r.solvability.status))).toEqual(
      new Set(['verified', 'failed', 'unchecked']),
    )
    expect(has('terrain')).toEqual(new Set(['flat', 'heron-ridge', 'osprey-town']))
    expect(has('time_of_day')).toEqual(new Set(['dawn', 'day', 'dusk', 'night']))
    expect(MOCK_LIBRARY.filter((r) => r.can_delete).every((r) => r.origin !== 'scripted')).toBe(
      true,
    )
    expect(new Set(MOCK_LIBRARY.map((r) => r.id)).size).toBe(14)
  })

  it('validates the sample, and reports line numbers for errors and lint', () => {
    expect(validateText(SAMPLE_YAML)).toMatchObject({ valid: true, errors: [], lint: [] })
    const bad = validateText(SAMPLE_YAML_ERRORS)
    const lines = SAMPLE_YAML_ERRORS.split('\n')
    expect(bad.valid).toBe(false)
    expect(bad.errors.map((e) => e.code)).toContain('schema.type')
    for (const e of bad.errors) expect(lines[e.line - 1]).toBeDefined()
    expect(lines[bad.errors.find((e) => e.code === 'schema.type')!.line - 1]).toBe(
      'duration_s: soon',
    )
    const lint = validateText(SAMPLE_YAML_LINT)
    expect(lint.valid).toBe(true)
    const reaction = lint.lint.find((l) => l.code === 'timing.reaction-window')!
    expect(SAMPLE_YAML_LINT.split('\n')[reaction.line - 1]).toContain('spawn_s: 12')
    expect(reaction.severity).toBe('error')
    expect(lint.lint.find((l) => l.code === 'group.link-range')?.severity).toBe('warning')
    expect(validateText('').errors[0]?.code).toBe('yaml.empty')
    expect(validateText('id: x').errors.map((e) => e.code)).toContain('contract.missing')
  })

  it('answers checks and previews as the engine does', () => {
    const ok = checkText(SAMPLE_YAML)
    expect(ok.solvability).toMatchObject({
      ran: true,
      solved: true,
      wording: 'verified solvable by test run',
    })
    expect(ok.solvability.checks.map((c) => c.code)).toEqual([
      'solvability.presented',
      'solvability.answered',
      'solvability.failures',
      'solvability.score',
    ])
    expect(Object.keys(ok.features)).toHaveLength(8)
    expect(checkText(SAMPLE_YAML, 14).solvability.wording).toBe('not verified solvable')
    expect(checkText(SAMPLE_YAML_LINT).solvability.ran).toBe(false)
    expect(previewText(SAMPLE_YAML).path.threats).toHaveLength(3)
    expect(previewText(SAMPLE_YAML_ERRORS).ok).toBe(false)
  })

  it('round-trips a share code and refuses a bad one', () => {
    const code = encodeRequest(REQUEST)
    expect(code).toMatch(/^SD1-[0-9A-Z]{4}(-[0-9A-Z]{1,4})+$/)
    expect(decodeCode(code).request).toEqual(REQUEST)
    expect(() => decodeCode('SD1-NOPE')).toThrow(ApiError)
    expect(generateFrom(REQUEST, false).spec).toEqual(generateFrom(REQUEST, false).spec)
    expect(generateFrom(REQUEST, true).saved).toBe(true)
    expect(generateFrom(REQUEST, false).solvability_wording).toBe('verified solvable by test run')
  })

  it('fills a 6 x 6 x 4 archive plausibly, and its heat map takes the best over the third axis', () => {
    const archive = mockArchive()
    expect(archive.axes.map((a) => a.bins)).toEqual([6, 6, 4])
    expect(archive.metrics.total).toBe(144)
    expect(archive.metrics.filled).toBe(archive.cells.length)
    expect(archive.metrics.filled).toBeGreaterThan(40)
    expect(archive.metrics.filled).toBeLessThan(110)
    expect(archive.metrics.coverage).toBeCloseTo(archive.metrics.filled / 144, 10)
    expect(archive.metrics.qd_score).toBeCloseTo(
      archive.cells.reduce((s, c) => s + c.quality, 0),
      2,
    )
    const map = heatMapFor(archive, 0, 1)
    expect(map.cells).toHaveLength(6)
    expect(map.cells[0]).toHaveLength(6)
    for (const row of map.cells)
      for (const cell of row) {
        const mine = archive.cells.filter((c) => c.index[0] === cell.x && c.index[1] === cell.y)
        expect(cell.filled).toBe(mine.length)
        expect(cell.quality).toBe(mine.length ? Math.max(...mine.map((c) => c.quality)) : null)
      }
    expect(archive.heatmap.values).toEqual(map.cells.map((r) => r.map((c) => c.quality)))
    expect(heatMapFor(archive, 2, 0).cells).toHaveLength(6)
    expect(heatMapFor(archive, 2, 0).cells[0]).toHaveLength(4)
    expect(tint(null)).toBe(0)
    expect(tint(1)).toBeLessThan(0.4)
    expect(tint(0.2)).toBeLessThan(tint(0.9))
  })

  it('keeps saves and deletes for the life of the backend', async () => {
    const backend = createMockBackend()
    const row = await backend.save({
      yaml: SAMPLE_YAML.replace('marlin-hill-evening-picket', 'my-own'),
      tags: ['x'],
    })
    expect(row).toMatchObject({ id: 'my-own', origin: 'authored', can_delete: true })
    expect((await backend.list())[0]!.id).toBe('my-own')
    expect((await backend.get('my-own')).yaml).toContain('id: my-own')
    await backend.remove('my-own')
    await expect(backend.get('my-own')).rejects.toMatchObject({ status: 404 })
    await expect(backend.remove('curriculum-01-first-light')).rejects.toMatchObject({ status: 403 })
    await expect(backend.save({ yaml: SAMPLE_YAML_ERRORS })).rejects.toMatchObject({ status: 422 })
    expect((await backend.batch({ request: REQUEST, count: 99 })).length).toBe(12)
    expect(DIFFICULTY_AXES).toHaveLength(5)
  })
})

describe('small helpers', () => {
  it('maps an offset to a line and column', () => {
    expect(positionOf('ab\ncd\nef', 0)).toEqual({ line: 1, column: 1 })
    expect(positionOf('ab\ncd\nef', 4)).toEqual({ line: 2, column: 2 })
    expect(positionOf('ab\ncd\nef', 8)).toEqual({ line: 3, column: 3 })
  })

  it('computes route time from distance and waypoint speeds, holds included', () => {
    const threat = SAMPLE_SPEC.threats[0]!
    expect(flightTimeS({ ...threat, route: [threat.route[0]!] as never })).toBe(0)
    const t = flightTimeS(threat)
    expect(t).toBeGreaterThan(80)
    expect(t).toBeLessThan(100)
    const held = {
      ...threat,
      route: threat.route.map((w, i) => (i === 0 ? { ...w, hold_s: 10 } : w)) as never,
    }
    expect(flightTimeS(held)).toBeCloseTo(t + 10, 6)
  })
})
