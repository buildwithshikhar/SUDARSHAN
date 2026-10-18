import { renderHook, waitFor } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { heightAt } from '../../src/live/terrain/heightAt'
import {
  loadTerrainPack,
  TerrainError,
  TerrainLoader,
  terrainUrl,
  useTerrain,
} from '../../src/live/terrain/loader'
import { terrainOf, type HeightField, type TerrainState } from '../../src/live/terrain/types'
import { fixtureFetch } from './terrainFixture'

/** 3 x 3 grid over [-100, 100]: row 0 is the south edge. Heights in units of 0.5 m. */
const field: HeightField = {
  size: 3,
  halfExtentM: 100,
  scaleM: 0.5,
  // prettier-ignore
  heights: Int16Array.from([
     0,  2,  4,   // y = -100 (south)
     2,  4,  6,   // y =    0
     4,  6, 20,   // y = +100 (north)
  ]),
}

describe('heightAt', () => {
  it('returns the stored value on grid vertices, scaled to metres', () => {
    expect(heightAt(field, -100, -100)).toBe(0)
    expect(heightAt(field, 100, -100)).toBe(2)
    expect(heightAt(field, -100, 100)).toBe(2)
    expect(heightAt(field, 100, 100)).toBe(10)
    expect(heightAt(field, 0, 0)).toBe(2)
  })

  it('reads row 0 as the south edge and column 0 as the west edge', () => {
    expect(heightAt(field, 50, -100)).toBeGreaterThan(heightAt(field, -50, -100))
    expect(heightAt(field, -100, 50)).toBeGreaterThan(heightAt(field, -100, -50))
  })

  it('interpolates bilinearly inside a cell', () => {
    // south-west cell corners are 0, 1, 1, 2 m: its centre is their mean
    expect(heightAt(field, -50, -50)).toBeCloseTo((0 + 1 + 1 + 2) / 4, 10)
    // along the south edge between 0 m and 1 m
    expect(heightAt(field, -75, -100)).toBeCloseTo(0.25, 10)
    // a quarter of the way in both directions in the north-east cell (corners 2, 3, 3, 10)
    expect(heightAt(field, 25, 25)).toBeCloseTo(
      (1 - 0.25) * ((1 - 0.25) * 2 + 0.25 * 3) + 0.25 * ((1 - 0.25) * 3 + 0.25 * 10),
      10,
    )
  })

  it('clamps points outside the square to the nearest edge', () => {
    expect(heightAt(field, -500, -500)).toBe(0)
    expect(heightAt(field, 500, 500)).toBe(10)
    expect(heightAt(field, 0, 900)).toBe(heightAt(field, 0, 100))
  })

  it('reads int16 values as signed', () => {
    const below: HeightField = { ...field, heights: new Int16Array(9).fill(-100), scaleM: 0.1 }
    expect(heightAt(below, 10, 10)).toBeCloseTo(-10, 6)
  })
})

describe('terrainOf', () => {
  it('reads flat and pack descriptors', () => {
    expect(terrainOf({ terrain: { kind: 'flat', elevation_m: 12 } })).toEqual({
      kind: 'flat',
      elevation_m: 12,
    })
    expect(terrainOf({ terrain: { kind: 'pack', id: 'heron-ridge', version: '1.0.0' } })).toEqual({
      kind: 'pack',
      id: 'heron-ridge',
      version: '1.0.0',
    })
  })

  it('treats a missing or malformed field as flat ground', () => {
    const flat = { kind: 'flat', elevation_m: 0 }
    expect(terrainOf({})).toEqual(flat)
    expect(terrainOf(null)).toEqual(flat)
    expect(terrainOf({ terrain: 'pack' })).toEqual(flat)
    expect(terrainOf({ terrain: { kind: 'pack', id: '' } })).toEqual(flat)
    expect(terrainOf({ terrain: { kind: 'mesh' } })).toEqual(flat)
  })
})

describe('loadTerrainPack', () => {
  const pack = { kind: 'pack', id: 'fixture-ridge', version: '1.0.0' } as const

  it('builds a typed pack from the fixture files', async () => {
    const fetcher = fixtureFetch()
    const loaded = await loadTerrainPack(pack, { fetch: fetcher, base: '' })
    expect(loaded.id).toBe('fixture-ridge')
    expect(loaded.size).toBe(9)
    expect(loaded.heights).toHaveLength(81)
    expect(loaded.halfExtentM).toBe(400)
    expect(loaded.buildings).toHaveLength(3)
    expect(loaded.buildings[0]?.footprint).toHaveLength(4)
    expect(loaded.trees).toHaveLength(60 * 3)
    expect(loaded.terrainGlb?.byteLength).toBeGreaterThan(100)
    expect(loaded.buildingsGlb?.byteLength).toBeGreaterThan(100)
    expect(loaded.label).toMatch(/reference data/)
    expect(fetcher.calls[0]).toBe('/api/v1/terrain/fixture-ridge/manifest.json')
    // the corner of the heightmap is the first stored value
    expect(heightAt(loaded, -400, -400)).toBeCloseTo((loaded.heights[0] ?? 0) * 0.1, 10)
    // the manifest's own range matches the data
    const hs = Array.from(loaded.heights, (v) => v * 0.1)
    expect(Math.min(...hs)).toBeCloseTo(loaded.minM, 0)
    expect(Math.max(...hs)).toBeCloseTo(loaded.maxM, 0)
  })

  it('builds the URL from the API base', () => {
    expect(terrainUrl('a b', 'heights.i16', '')).toBe('/api/v1/terrain/a%20b/heights.i16')
    expect(terrainUrl('x', 'manifest.json', 'https://api.example.test/')).toBe(
      'https://api.example.test/api/v1/terrain/x/manifest.json',
    )
  })

  it('rejects an unknown pack, a wrong id or version, and a bad format', async () => {
    await expect(
      loadTerrainPack(
        { kind: 'pack', id: 'nope', version: '' },
        { fetch: fixtureFetch(), base: '' },
      ),
    ).rejects.toThrow(/manifest.json: HTTP 404/)
    await expect(
      loadTerrainPack({ ...pack, version: '9.9.9' }, { fetch: fixtureFetch(), base: '' }),
    ).rejects.toThrow(/version/)
    const wrongId = fixtureFetch({
      'manifest.json': () =>
        Response.json({ format: 'terrain-pack.v1', id: 'other', version: '1.0.0' }),
    })
    await expect(loadTerrainPack(pack, { fetch: wrongId, base: '' })).rejects.toThrow(
      /id does not match/,
    )
    const badFormat = fixtureFetch({ 'manifest.json': () => Response.json({ format: 'v0' }) })
    await expect(loadTerrainPack(pack, { fetch: badFormat, base: '' })).rejects.toThrow(/format/)
    const notJson = fixtureFetch({ 'manifest.json': () => new Response('<html>') })
    await expect(loadTerrainPack(pack, { fetch: notJson, base: '' })).rejects.toBeInstanceOf(
      TerrainError,
    )
  })

  it('rejects a truncated heightmap', async () => {
    const fetcher = fixtureFetch({ 'heights.i16': () => new Response(new Uint8Array(40)) })
    await expect(loadTerrainPack(pack, { fetch: fetcher, base: '' })).rejects.toThrow(
      /heights.i16: 40 bytes/,
    )
  })

  it('still loads when a mesh is missing: the heightmap is enough', async () => {
    const fetcher = fixtureFetch({
      'terrain.glb': () => new Response('gone', { status: 404 }),
    })
    const loaded = await loadTerrainPack(pack, { fetch: fetcher, base: '' })
    expect(loaded.terrainGlb).toBeNull()
    expect(loaded.buildingsGlb).not.toBeNull()
  })

  it('reports a network failure as a terrain error', async () => {
    const down = (() => Promise.reject(new TypeError('failed'))) as unknown as typeof fetch
    await expect(loadTerrainPack(pack, { fetch: down, base: '' })).rejects.toThrow(/network error/)
  })
})

describe('TerrainLoader', () => {
  it('goes loading then ready for a pack', async () => {
    const loader = new TerrainLoader(
      { kind: 'pack', id: 'fixture-ridge', version: '1.0.0' },
      { fetch: fixtureFetch(), base: '' },
    )
    const seen: TerrainState['status'][] = []
    loader.subscribe((s) => seen.push(s.status))
    expect(loader.state.status).toBe('loading')
    loader.start()
    await waitFor(() => expect(loader.state.status).toBe('ready'))
    expect(seen).toEqual(['loading', 'ready'])
    const state = loader.state
    expect(state.status === 'ready' && state.pack?.id).toBe('fixture-ridge')
  })

  it('goes loading then error without throwing, and keeps the message', async () => {
    const loader = new TerrainLoader(
      { kind: 'pack', id: 'missing', version: '1' },
      { fetch: fixtureFetch(), base: '' },
    )
    loader.start()
    await waitFor(() => expect(loader.state.status).toBe('error'))
    expect(loader.state).toMatchObject({ status: 'error', message: expect.stringContaining('404') })
  })

  it('is ready at once for flat ground, with its elevation', () => {
    const loader = new TerrainLoader({ kind: 'flat', elevation_m: 35 })
    loader.start()
    expect(loader.state).toEqual({ status: 'ready', pack: null, elevationM: 35 })
  })

  it('aborts and goes quiet when disposed mid-download', async () => {
    let release: () => void = () => undefined
    const gate = new Promise<void>((r) => (release = r))
    const fetcher = fixtureFetch({
      'manifest.json': async () => {
        await gate
        return new Response('{}')
      },
    })
    const loader = new TerrainLoader(
      { kind: 'pack', id: 'fixture-ridge', version: '1.0.0' },
      { fetch: fetcher, base: '' },
    )
    const seen: string[] = []
    loader.subscribe((s) => seen.push(s.status))
    loader.start()
    loader.dispose()
    release()
    await new Promise((r) => setTimeout(r, 20))
    expect(seen).toEqual(['loading'])
  })
})

describe('useTerrain', () => {
  it('follows the loader: loading, then ready', async () => {
    const fetcher = fixtureFetch()
    const { result } = renderHook(() =>
      useTerrain({ kind: 'pack', id: 'fixture-ridge', version: '1.0.0' }, fetcher),
    )
    expect(result.current.status).toBe('loading')
    await waitFor(() => expect(result.current.status).toBe('ready'))
  })

  it('falls back to an error state for a bad pack', async () => {
    const fetcher = fixtureFetch()
    const { result } = renderHook(() =>
      useTerrain({ kind: 'pack', id: 'nope', version: '1' }, fetcher),
    )
    await waitFor(() => expect(result.current.status).toBe('error'))
  })
})
