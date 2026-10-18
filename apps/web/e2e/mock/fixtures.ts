import AxeBuilder from '@axe-core/playwright'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { expect, type Page } from '@playwright/test'

import { MOCK_SCORE, MOCK_SCORE_EMPTY } from '../../src/live/mockScore'

export interface Prefs {
  language: 'en' | 'hi'
  theme: 'dark' | 'light'
  role?: 'trainee' | 'instructor' | 'admin'
}

const json = (body: unknown, status = 200) => ({
  status,
  contentType: 'application/json',
  body: JSON.stringify(body),
})

export const SCENARIO = {
  id: 'harrier-field-afternoon-watch',
  version: '0.3.1-mock',
  title: { en: 'Harrier Field: afternoon watch', hi: 'हैरियर फील्ड: दोपहर की निगरानी' },
  summary: {
    en: 'A small rotary contact closes on the field from the north-east while a civil survey flight and a bird flock work the outer zone.',
    hi: 'एक छोटा रोटरी संपर्क उत्तर-पूर्व से मैदान की ओर आता है, जबकि एक नागरिक सर्वे उड़ान और पक्षियों का झुंड बाहरी क्षेत्र में हैं।',
  },
  duration_s: 64,
  default_seed: 240117,
  start_time_of_day_h: 15.6,
  weather_condition: 'clear',
}

/** Answers the REST calls the signed-in app makes; nothing leaves the dev server. */
export async function installApi(
  page: Page,
  prefs: Prefs,
  options: { scenarios?: unknown[]; scenariosStatus?: number; logVerified?: boolean } = {},
) {
  const user = {
    id: 'u-trainee',
    email: 'trainee@demo.invalid',
    role: prefs.role ?? 'trainee',
    language: prefs.language,
    theme: prefs.theme,
  }
  await page.route('**/api/v1/version', (route) =>
    route.fulfill(
      json({
        productName: 'SUDARSHAN',
        descriptor: 'Counter-UAS Threat Recognition Trainer',
        version: '0.1.0',
        gitSha: 'abc1234',
        buildTime: '2026-10-18T00:00:00Z',
        env: 'demo',
      }),
    ),
  )
  await page.route('**/api/v1/auth/me', (route) =>
    route.fulfill(json({ user, csrf: 'csrf-mock', expiresAt: '2026-10-18T23:00:00+00:00' })),
  )
  await page.route('**/api/v1/auth/me/preferences', (route) => route.fulfill(json(user)))
  await page.route('**/api/v1/scenarios', (route) =>
    options.scenariosStatus && options.scenariosStatus !== 200
      ? route.fulfill(json({ detail: 'down' }, options.scenariosStatus))
      : route.fulfill(json(options.scenarios ?? [SCENARIO])),
  )
  await page.route('**/api/v1/sessions', (route) =>
    route.fulfill(
      json({
        id: 'mock-session',
        scenario_id: SCENARIO.id,
        scenario_version: SCENARIO.version,
        seed: SCENARIO.default_seed,
        status: 'lobby',
        created_at: '2026-10-18T09:00:00+00:00',
        started_at: null,
        ended_at: null,
        ticks: 0,
      }),
    ),
  )
  await page.route('**/api/v1/sessions/*/log', (route) =>
    route.fulfill(
      json(
        options.logVerified === false
          ? {
              verified: false,
              first_bad_seq: 41,
              event_count: 88,
              head: 'ab'.repeat(32),
              final_state_hash: 'cd'.repeat(32),
              events: [],
            }
          : {
              verified: true,
              first_bad_seq: null,
              event_count: 112,
              head: 'c41f09a7d3e85b62f01a9c7e3d54b8a60e2f719cd8350a46b7e91f2c05d38a14',
              final_state_hash: '7be2d05a91c4f836e0b1a7d92c5f4803ad61e97b2c08f5d34a1e6b90c7d2f853',
              events: [],
            },
      ),
    ),
  )
  await page.route('**/api/v1/sessions/mock-session', (route) =>
    route.fulfill(
      json({
        id: 'mock-session',
        scenario_id: SCENARIO.id,
        scenario_version: SCENARIO.version,
        seed: SCENARIO.default_seed,
        status: 'ended',
        created_at: '2026-10-18T09:00:00+00:00',
        started_at: '2026-10-18T09:01:00+00:00',
        ended_at: '2026-10-18T09:02:04+00:00',
        ticks: 1280,
      }),
    ),
  )
}

export type ScoreReply = 'populated' | 'empty' | 'not-ended' | 'not-found' | 'network' | 'slow'

/**
 * Serves `GET /api/v1/sessions/{id}/score` from the scripted record. Load the page without
 * `?mock=1` so the request goes through the route; 'slow' holds the reply until `release()`.
 */
export async function installScore(page: Page, reply: ScoreReply = 'populated') {
  let release: () => void = () => undefined
  const gate = new Promise<void>((resolve) => (release = resolve))
  await page.route('**/api/v1/sessions/*/score', async (route) => {
    switch (reply) {
      case 'not-ended':
        return route.fulfill(json({ detail: 'the session has not ended' }, 409))
      case 'not-found':
        return route.fulfill(json({ detail: 'session not found' }, 404))
      case 'network':
        return route.abort('failed')
      case 'empty':
        return route.fulfill(json(MOCK_SCORE_EMPTY))
      case 'slow':
        await gate
        return route.fulfill(json(MOCK_SCORE))
      default:
        return route.fulfill(json(MOCK_SCORE))
    }
  })
  return { release }
}

export type TerrainReply = 'ok' | 'missing' | 'slow'

const FIXTURE_TERRAIN = resolve(import.meta.dirname, '../../tests/fixtures/terrain')

/**
 * Serves `GET /api/v1/terrain/{id}/{file}` from the checked-in fixture pack. 'missing' answers
 * 404 for every file (the pack failed); 'slow' holds the manifest until `release()` so the
 * loading state can be seen.
 */
export async function installTerrain(page: Page, reply: TerrainReply = 'ok') {
  let release: () => void = () => undefined
  const gate = new Promise<void>((done) => (release = done))
  await page.route('**/api/v1/terrain/**', async (route) => {
    if (reply === 'missing') return route.fulfill(json({ detail: 'terrain pack not found' }, 404))
    const match = /\/api\/v1\/terrain\/([^/]+)\/([^/?]+)/.exec(route.request().url())
    if (!match) return route.fulfill(json({ detail: 'not found' }, 404))
    if (reply === 'slow' && match[2] === 'manifest.json') await gate
    try {
      const body = readFileSync(resolve(FIXTURE_TERRAIN, match[1] ?? '', match[2] ?? ''))
      return route.fulfill({ status: 200, body })
    } catch {
      return route.fulfill(json({ detail: 'terrain file not found' }, 404))
    }
  })
  return { release }
}

/** The workspace URL with scripted-session variants: camera, terrain, rain and hour. */
export const variantUrl = (variant: {
  eo?: 'day' | 'nv' | 'thermal'
  terrain?: string
  rain?: boolean
  hour?: number
  speed?: number
}) => {
  const q = new URLSearchParams({ mock: '1', speed: String(variant.speed ?? 4) })
  if (variant.eo) q.set('eo', variant.eo)
  if (variant.terrain) q.set('terrain', variant.terrain)
  if (variant.rain) q.set('rain', '1')
  if (variant.hour !== undefined) q.set('hour', String(variant.hour))
  return `/train/session/mock-session?${q.toString()}`
}

export const debriefUrl = '/train/session/mock-session/debrief'

export const sessionUrl = (speed = 4) => `/train/session/mock-session?mock=1&speed=${speed}`

/** Open the workspace, begin the session with the keyboard and wait for the first contacts. */
export async function beginSession(page: Page, contacts = 4, url = sessionUrl()) {
  await page.goto(url)
  const begin = page.getByRole('button', { name: /Begin session|सत्र आरंभ करें/ })
  await expect(begin).toBeFocused()
  await page.keyboard.press('Enter')
  await expect(page.locator('table').first().locator('tbody tr')).toHaveCount(contacts, {
    timeout: 30_000,
  })
}

export async function expectClean(page: Page) {
  await page.evaluate(() => document.fonts.ready)
  const results = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'])
    .analyze()
  expect(
    results.violations.map(
      (v) =>
        `${v.id}: ${v.nodes.map((n) => `${n.target.join(' ')} ${JSON.stringify(n.any[0]?.data ?? {})}`).join(', ')}`,
    ),
  ).toEqual([])
}
