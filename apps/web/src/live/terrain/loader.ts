/**
 * Fetches a terrain pack from `/api/v1/terrain/{id}/{file}` (docs/TERRAIN_PACKS.md) and checks it.
 * A failure never blocks the session: callers fall back to flat ground and say so.
 */
import { useEffect, useState } from 'react'
import type {
  TerrainBuilding,
  TerrainDescriptor,
  TerrainManifest,
  TerrainPack,
  TerrainState,
} from './types'

const apiBase = (): string => (import.meta.env.VITE_API_URL as string | undefined) ?? ''

export type FetchLike = (input: string, init?: RequestInit) => Promise<Response>

export class TerrainError extends Error {}

export function terrainUrl(id: string, file: string, base: string = apiBase()): string {
  return `${base.replace(/\/$/, '')}/api/v1/terrain/${encodeURIComponent(id)}/${file}`
}

interface Options {
  fetch?: FetchLike
  signal?: AbortSignal
  base?: string
}

async function get(id: string, file: string, o: Options): Promise<Response> {
  const fetcher = o.fetch ?? ((input, init) => fetch(input, init))
  const base = o.base ?? apiBase()
  let response: Response
  try {
    response = await fetcher(terrainUrl(id, file, base), {
      credentials: base ? 'include' : 'same-origin',
      signal: o.signal,
    })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    throw new TerrainError(`${file}: network error`)
  }
  if (!response.ok) throw new TerrainError(`${file}: HTTP ${response.status}`)
  return response
}

async function json<T>(id: string, file: string, o: Options): Promise<T> {
  const response = await get(id, file, o)
  try {
    return (await response.json()) as T
  } catch {
    throw new TerrainError(`${file}: not valid JSON`)
  }
}

const isNum = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v)

function checkManifest(m: TerrainManifest, id: string): void {
  if (m?.format !== 'terrain-pack.v1') throw new TerrainError('manifest.json: unknown format')
  if (m.id !== id) throw new TerrainError('manifest.json: id does not match')
  const h = m.heightmap
  if (
    !h ||
    !Number.isInteger(h.size) ||
    h.size < 2 ||
    !isNum(h.scale_m) ||
    !isNum(h.cell_m) ||
    typeof h.file !== 'string' ||
    !isNum(m.frame?.half_extent_m) ||
    !isNum(m.frame?.datum_m)
  ) {
    throw new TerrainError('manifest.json: heightmap or frame missing')
  }
  if (typeof m.buildings?.file !== 'string' || typeof m.vegetation?.file !== 'string') {
    throw new TerrainError('manifest.json: file list incomplete')
  }
}

function parseBuildings(data: unknown): TerrainBuilding[] {
  const list = (data as { format?: unknown; buildings?: unknown } | null)?.buildings
  if (
    (data as { format?: unknown } | null)?.format !== 'terrain-buildings.v1' ||
    !Array.isArray(list)
  ) {
    throw new TerrainError('buildings.json: unknown format')
  }
  const out: TerrainBuilding[] = []
  for (const b of list as TerrainBuilding[]) {
    if (
      Array.isArray(b.footprint) &&
      b.footprint.length >= 3 &&
      isNum(b.base_m) &&
      isNum(b.height_m)
    ) {
      out.push(b)
    }
  }
  return out
}

function parseTrees(data: unknown): Float32Array {
  const trees = (data as { format?: unknown; trees?: unknown } | null)?.trees
  if (
    (data as { format?: unknown } | null)?.format !== 'terrain-vegetation.v1' ||
    !Array.isArray(trees)
  ) {
    throw new TerrainError('vegetation.json: unknown format')
  }
  const out = new Float32Array(trees.length * 3)
  trees.forEach((t, i) => {
    const row = t as number[]
    out[i * 3] = row[0] ?? 0
    out[i * 3 + 1] = row[1] ?? 0
    out[i * 3 + 2] = row[2] ?? 6
  })
  return out
}

/** A mesh the scene can do without: a pack is usable from its heightmap alone. */
async function optionalMesh(id: string, file: string | undefined, o: Options) {
  if (!file) return null
  try {
    return await (await get(id, file, o)).arrayBuffer()
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    return null
  }
}

/** Download and validate one pack. Rejects with a `TerrainError` for anything wrong with it. */
export async function loadTerrainPack(
  descriptor: Extract<TerrainDescriptor, { kind: 'pack' }>,
  options: Options = {},
): Promise<TerrainPack> {
  const id = descriptor.id
  const manifest = await json<TerrainManifest>(id, 'manifest.json', options)
  checkManifest(manifest, id)
  if (descriptor.version && manifest.version !== descriptor.version) {
    throw new TerrainError(
      `manifest.json: version ${manifest.version}, expected ${descriptor.version}`,
    )
  }
  const [heightsBuffer, buildingsJson, vegetationJson, terrainGlb, buildingsGlb] =
    await Promise.all([
      get(id, manifest.heightmap.file, options).then((r) => r.arrayBuffer()),
      json<unknown>(id, manifest.buildings.file, options),
      json<unknown>(id, manifest.vegetation.file, options),
      optionalMesh(id, manifest.meshes?.terrain, options),
      optionalMesh(id, manifest.meshes?.buildings, options),
    ])
  const size = manifest.heightmap.size
  if (heightsBuffer.byteLength !== size * size * 2) {
    throw new TerrainError(
      `heights.i16: ${heightsBuffer.byteLength} bytes, expected ${size * size * 2}`,
    )
  }
  // int16 little-endian regardless of the host: decode explicitly rather than view the buffer.
  const view = new DataView(heightsBuffer)
  const heights = new Int16Array(size * size)
  for (let i = 0; i < heights.length; i++) heights[i] = view.getInt16(i * 2, true)

  return {
    id: manifest.id,
    version: manifest.version,
    name: manifest.name,
    label: manifest.label,
    manifest,
    heights,
    size,
    cellM: manifest.heightmap.cell_m,
    scaleM: manifest.heightmap.scale_m,
    halfExtentM: manifest.frame.half_extent_m,
    datumM: manifest.frame.datum_m,
    minM: manifest.heightmap.min_m,
    maxM: manifest.heightmap.max_m,
    buildings: parseBuildings(buildingsJson),
    trees: parseTrees(vegetationJson),
    terrainGlb,
    buildingsGlb,
  }
}

type Listener = (state: TerrainState) => void

/**
 * The load as a small state machine: `loading`, then `ready` or `error`. Flat ground is ready at
 * once. `dispose` aborts a download in flight, so a view that unmounts leaves nothing running.
 */
export class TerrainLoader {
  private current: TerrainState = { status: 'loading' }
  private readonly listeners = new Set<Listener>()
  private readonly abort = new AbortController()

  constructor(
    readonly descriptor: TerrainDescriptor,
    private readonly options: Omit<Options, 'signal'> = {},
  ) {}

  get state(): TerrainState {
    return this.current
  }

  subscribe(listener: Listener): () => void {
    this.listeners.add(listener)
    return () => this.listeners.delete(listener)
  }

  private set(state: TerrainState): void {
    this.current = state
    this.listeners.forEach((l) => l(state))
  }

  start(): void {
    const d = this.descriptor
    if (d.kind === 'flat') {
      this.set({ status: 'ready', pack: null, elevationM: d.elevation_m })
      return
    }
    this.set({ status: 'loading' })
    loadTerrainPack(d, { ...this.options, signal: this.abort.signal }).then(
      (pack) => {
        if (!this.abort.signal.aborted) this.set({ status: 'ready', pack, elevationM: 0 })
      },
      (error: unknown) => {
        if (this.abort.signal.aborted) return
        this.set({
          status: 'error',
          message: error instanceof Error ? error.message : 'terrain pack failed to load',
        })
      },
    )
  }

  dispose(): void {
    this.abort.abort()
    this.listeners.clear()
  }
}

/** The terrain state for a descriptor; reloads when the pack id or version changes. */
export function useTerrain(descriptor: TerrainDescriptor, fetcher?: FetchLike): TerrainState {
  const key =
    descriptor.kind === 'pack'
      ? `${descriptor.id}@${descriptor.version}`
      : `flat:${descriptor.elevation_m}`
  const [state, setState] = useState<{ key: string; value: TerrainState }>(() => ({
    key,
    value:
      descriptor.kind === 'flat'
        ? { status: 'ready', pack: null, elevationM: descriptor.elevation_m }
        : { status: 'loading' },
  }))

  useEffect(() => {
    const loader = new TerrainLoader(descriptor, { fetch: fetcher })
    const unsubscribe = loader.subscribe((value) => setState({ key, value }))
    loader.start()
    return () => {
      unsubscribe()
      loader.dispose()
    }
    // the descriptor is identified by its key
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, fetcher])

  return state.key === key
    ? state.value
    : descriptor.kind === 'flat'
      ? { status: 'ready', pack: null, elevationM: descriptor.elevation_m }
      : { status: 'loading' }
}
