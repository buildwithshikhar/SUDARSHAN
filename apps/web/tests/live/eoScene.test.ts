import * as THREE from 'three'
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import { MOCK_WELCOME } from '../../src/live/mock'
import { loadTerrainPack } from '../../src/live/terrain/loader'
import type { TerrainPack } from '../../src/live/terrain/types'
import type { HeldReport } from '../../src/live/views/eoHold'
import { EoScene } from '../../src/live/views/eoScene'
import { fixtureFetch } from './terrainFixture'

/**
 * The scene is driven here with a stand-in for WebGLRenderer, so the suite needs no GPU and no
 * software WebGL: what is checked is what the scene builds, how it reacts to tier, mode and
 * weather, and that it gives every GPU object back.
 */
const fake = vi.hoisted(() => ({ last: null as unknown, created: [] as unknown[] }))

vi.mock('three', async (importOriginal) => {
  const actual = await importOriginal<typeof import('three')>()
  class FakeRenderer {
    shadowMap = { enabled: false, type: 0 }
    toneMapping = 0
    toneMappingExposure = 1
    extensions = { has: () => true }
    info = { render: { calls: 0, triangles: 0 } }
    ratio = 1
    width = 1
    height = 1
    renders = 0
    targets: unknown[] = []
    disposed = false
    lost = false
    constructor(readonly options: { antialias?: boolean }) {
      fake.last = this
      fake.created.push(this)
    }
    setPixelRatio(v: number) {
      this.ratio = v
    }
    getPixelRatio() {
      return this.ratio
    }
    setSize(w: number, h: number) {
      this.width = w
      this.height = h
    }
    getDrawingBufferSize(v: THREE.Vector2) {
      return v.set(this.width * this.ratio, this.height * this.ratio)
    }
    setRenderTarget(t: unknown) {
      this.targets.push(t)
    }
    render() {
      this.renders++
    }
    readRenderTargetPixelsAsync() {
      return Promise.resolve(new Uint8Array(32 * 18 * 4).fill(128))
    }
    dispose() {
      this.disposed = true
    }
    forceContextLoss() {
      this.lost = true
    }
  }
  return { ...actual, WebGLRenderer: FakeRenderer }
})

type Fake = {
  options: { antialias?: boolean }
  ratio: number
  renders: number
  targets: unknown[]
  disposed: boolean
  lost: boolean
  shadowMap: { enabled: boolean }
}
const renderer = () => fake.last as Fake

/** Everything the scene created that holds GPU memory, found through its graph and its skins. */
function gpuObjects(scene: EoScene) {
  const inner = scene as unknown as {
    scene: THREE.Scene
    skins: { day: THREE.Material | THREE.Material[]; thermal: THREE.Material | THREE.Material[] }[]
    thermalMaterials: { material: THREE.Material }[]
  }
  const geometries = new Set<THREE.BufferGeometry>()
  const materials = new Set<THREE.Material>()
  const textures = new Set<THREE.Texture>()
  const addMaterial = (m: THREE.Material) => {
    materials.add(m)
    for (const v of Object.values(m)) if (v instanceof THREE.Texture) textures.add(v)
  }
  inner.scene.traverse((o) => {
    const mesh = o as THREE.Mesh
    if (mesh.geometry) geometries.add(mesh.geometry)
    for (const m of Array.isArray(mesh.material)
      ? mesh.material
      : mesh.material
        ? [mesh.material]
        : [])
      addMaterial(m)
  })
  for (const s of inner.skins) for (const m of [s.day, s.thermal].flat()) addMaterial(m)
  for (const t of inner.thermalMaterials) addMaterial(t.material)
  return { geometries, materials, textures }
}

const briefing = MOCK_WELCOME.briefing
const canvas = () => document.createElement('canvas')
let pack: TerrainPack

beforeAll(async () => {
  pack = await loadTerrainPack(
    { kind: 'pack', id: 'fixture-ridge', version: '1.0.0' },
    { fetch: fixtureFetch(), base: '' },
  )
})

beforeEach(() => {
  fake.created.length = 0
  fake.last = null
  Object.defineProperty(window, 'devicePixelRatio', { value: 3, configurable: true })
})

afterEach(() => {
  Object.defineProperty(window, 'devicePixelRatio', { value: 1, configurable: true })
  vi.restoreAllMocks()
})

describe('EoScene construction and quality', () => {
  it('caps the pixel ratio by tier and passes antialiasing to the renderer', () => {
    const high = new EoScene(canvas(), { tier: 'high' })
    expect(renderer().ratio).toBe(1.5)
    expect(renderer().options.antialias).toBe(true)
    high.dispose()
    const low = new EoScene(canvas(), { tier: 'low' })
    expect(renderer().ratio).toBe(1)
    expect(renderer().options.antialias).toBe(false)
    low.dispose()
  })

  it('draws shadows only on the high tier, and changes tier at run time', async () => {
    const scene = new EoScene(canvas(), { tier: 'high' })
    scene.setWeather({ condition: 'rain', visibility_m: 4000 })
    await scene.setTerrain(pack)
    expect(scene.stats()).toMatchObject({ tier: 'high', shadows: true, treesDrawn: 60 })
    expect(renderer().shadowMap.enabled).toBe(true)
    const rainHigh = scene.stats().rainDrawn
    expect(rainHigh).toBeGreaterThan(300)
    scene.setQuality('medium')
    expect(scene.stats()).toMatchObject({ tier: 'medium', shadows: false, treesDrawn: 36 })
    expect(renderer().shadowMap.enabled).toBe(false)
    expect(renderer().ratio).toBe(1.25)
    expect(scene.stats().rainDrawn).toBeLessThan(rainHigh)
    scene.setQuality('low')
    expect(scene.stats()).toMatchObject({ treesDrawn: 15, pixelRatio: 1 })
    expect(scene.stats().rainDrawn).toBeLessThan(450 + 1)
    scene.dispose()
  })
})

describe('EoScene terrain', () => {
  it('uses the pack meshes, instances the trees and keeps flat ground without a pack', async () => {
    const scene = new EoScene(canvas(), { tier: 'high' })
    scene.setSite(briefing)
    expect(scene.stats()).toMatchObject({ terrain: 'flat', buildings: 'none', treesDrawn: 0 })
    await scene.setTerrain(pack)
    expect(scene.stats()).toMatchObject({ terrain: 'glb', buildings: 'glb', treesDrawn: 60 })
    await scene.setTerrain(null)
    expect(scene.stats()).toMatchObject({ terrain: 'flat', buildings: 'none', treesDrawn: 0 })
    scene.dispose()
  })

  it('builds terrain and buildings from the data when the meshes are missing or broken', async () => {
    const scene = new EoScene(canvas(), { tier: 'medium' })
    await scene.setTerrain({ ...pack, terrainGlb: null, buildingsGlb: null })
    expect(scene.stats()).toMatchObject({ terrain: 'heightmap', buildings: 'json' })
    await scene.setTerrain({
      ...pack,
      terrainGlb: new Uint8Array([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]).buffer,
      buildingsGlb: new Uint8Array(16).buffer,
    })
    expect(scene.stats()).toMatchObject({ terrain: 'heightmap', buildings: 'json' })
    scene.dispose()
  })

  it('draws one terrain when the same pack is requested twice at once', async () => {
    const scene = new EoScene(canvas(), { tier: 'low' })
    const group = (scene as unknown as { terrainGroup: THREE.Group }).terrainGroup
    await Promise.all([scene.setTerrain(pack), scene.setTerrain(pack)])
    const once = group.children.length
    expect(once).toBeGreaterThan(0)
    await scene.setTerrain(null)
    await Promise.all([scene.setTerrain(pack), scene.setTerrain(null)])
    expect(group.children.length).toBe(0)
    scene.dispose()
  })

  it('does not leak skins when the terrain is replaced', async () => {
    const scene = new EoScene(canvas(), { tier: 'low' })
    scene.setSite(briefing)
    const skins = (scene as unknown as { skins: unknown[] }).skins
    const thermal = (scene as unknown as { thermalMaterials: unknown[] }).thermalMaterials
    const baseline = [skins.length, thermal.length]
    await scene.setTerrain(pack)
    const loaded = [skins.length, thermal.length]
    expect(loaded[0]).toBeGreaterThan(baseline[0] ?? 0)
    await scene.setTerrain(null)
    await scene.setTerrain(pack)
    expect([skins.length, thermal.length]).toEqual(loaded)
    await scene.setTerrain(null)
    expect([skins.length, thermal.length]).toEqual(baseline)
    scene.dispose()
  })

  it('places assets and masts on the terrain surface', async () => {
    const scene = new EoScene(canvas(), { tier: 'low' })
    await scene.setTerrain(pack)
    scene.setSite(briefing)
    const site = (scene as unknown as { siteGroup: THREE.Group }).siteGroup
    const asset = briefing.assets[0]
    const block = site.children[0]
    expect(block?.position.y).toBeGreaterThan(4.5 - 5)
    expect(block?.position.x).toBe(asset?.position.x)
    scene.dispose()
  })
})

describe('EoScene modes', () => {
  it('draws day straight to the canvas and thermal and night vision through the post pass', async () => {
    const scene = new EoScene(canvas(), { tier: 'medium' })
    scene.render(10)
    expect(renderer().renders).toBe(1)
    expect(renderer().targets).toHaveLength(0)

    scene.setMode('thermal-white-hot')
    expect(scene.stats().mode).toBe('thermal-white-hot')
    scene.render(20)
    // the scene into the target, a gain sample, then the picture to the canvas
    expect(renderer().targets.some((t) => t !== null)).toBe(true)
    expect(renderer().targets.at(-1)).toBeNull()

    scene.setMode('night-vision')
    scene.render(30)
    expect(scene.stats().mode).toBe('night-vision')

    const before = renderer().targets.length
    scene.setMode('day')
    scene.render(40)
    expect(renderer().targets).toHaveLength(before)
    scene.dispose()
  })

  it('swaps materials and light for the thermal look and restores them', () => {
    const scene = new EoScene(canvas(), { tier: 'low' })
    const inner = scene as unknown as {
      skins: { mesh: THREE.Mesh; day: THREE.Material; thermal: THREE.Material }[]
      ambient: THREE.AmbientLight
      targetMaterial: THREE.MeshLambertMaterial
    }
    const dayAmbient = inner.ambient.intensity
    scene.setMode('thermal-black-hot')
    for (const s of inner.skins) expect(s.mesh.material).toBe(s.thermal)
    expect(inner.ambient.intensity).toBeGreaterThan(dayAmbient)
    // targets glow by emission, so they read hot whatever the light
    expect(inner.targetMaterial.emissive.r).toBeGreaterThan(0.8)
    scene.setMode('day')
    for (const s of inner.skins) expect(s.mesh.material).toBe(s.day)
    expect(inner.targetMaterial.emissive.r).toBe(0)
    scene.dispose()
  })

  it('heats the ground in the afternoon and cools it at night in thermal', () => {
    const scene = new EoScene(canvas(), { tier: 'low' })
    const inner = scene as unknown as {
      thermalMaterials: { material: THREE.MeshLambertMaterial; cls: string }[]
    }
    const ground = () =>
      inner.thermalMaterials.find((t) => t.cls === 'terrain')?.material.color.r ?? 0
    scene.setMode('thermal-white-hot')
    scene.setTimeOfDay(14.5)
    const afternoon = ground()
    scene.setTimeOfDay(2.5)
    expect(afternoon).toBeGreaterThan(ground() + 0.2)
    scene.dispose()
  })

  it('reports the gain through the look callback', async () => {
    const looks: { mode: string; gainPct: number }[] = []
    const scene = new EoScene(canvas(), { tier: 'low', onLook: (l) => looks.push(l) })
    scene.setMode('thermal-white-hot')
    scene.render(10)
    await new Promise((r) => setTimeout(r, 0))
    expect(looks.at(-1)?.mode).toBe('thermal-white-hot')
    expect(looks.at(-1)?.gainPct).toBeGreaterThanOrEqual(0)
    scene.dispose()
  })
})

describe('EoScene weather and sky', () => {
  it('rains only when the briefing says so, and drifts with the wind', () => {
    const scene = new EoScene(canvas(), { tier: 'high' })
    expect(scene.stats().rainDrawn).toBe(0)
    scene.setWeather({
      condition: 'rain',
      visibility_m: 3000,
      wind_from_deg: 270,
      wind_speed_mps: 8,
    })
    expect(scene.stats().rainDrawn).toBeGreaterThan(1000)
    const uniforms = (scene as unknown as { uniforms: { wind: { value: THREE.Vector2 } } }).uniforms
    // from the west: the air moves east
    expect(uniforms.wind.value.x).toBeCloseTo(8, 5)
    expect(uniforms.wind.value.y).toBeCloseTo(0, 5)
    scene.setWeather({ condition: 'clear', visibility_m: 9000 })
    expect(scene.stats().rainDrawn).toBe(0)
    scene.dispose()
  })

  it('sets the fog from the visibility', () => {
    const scene = new EoScene(canvas(), { tier: 'low' })
    const fog = (scene as unknown as { fog: THREE.FogExp2 }).fog
    scene.setWeather({ visibility_m: 9000 })
    const clear = fog.density
    scene.setWeather({ condition: 'fog', visibility_m: 800 })
    expect(fog.density).toBeGreaterThan(clear * 5)
    scene.dispose()
  })

  it('shows the sun by day, and the moon and stars at night', () => {
    const scene = new EoScene(canvas(), { tier: 'low' })
    const inner = scene as unknown as {
      sunDisc: THREE.Mesh
      moonDisc: THREE.Mesh
      stars: THREE.Points
      moon: THREE.DirectionalLight
    }
    scene.setTimeOfDay(12)
    expect(inner.sunDisc.visible).toBe(true)
    expect(inner.moonDisc.visible).toBe(false)
    expect(inner.stars.visible).toBe(false)
    expect(inner.moon.intensity).toBe(0)
    scene.setTimeOfDay(0)
    expect(inner.sunDisc.visible).toBe(false)
    expect(inner.moonDisc.visible).toBe(true)
    expect(inner.stars.visible).toBe(true)
    expect(inner.moon.intensity).toBeGreaterThan(0)
    // the moon stands opposite the sun
    scene.setTimeOfDay(0)
    expect(inner.moonDisc.position.y).toBeGreaterThan(0)
    scene.dispose()
  })

  it('uses filmic tone mapping with an exposure that rises at night', () => {
    const scene = new EoScene(canvas(), { tier: 'low' })
    const r = scene.renderer as unknown as { toneMapping: number; toneMappingExposure: number }
    expect(r.toneMapping).toBe(THREE.ACESFilmicToneMapping)
    scene.setTimeOfDay(12)
    const noon = r.toneMappingExposure
    scene.setTimeOfDay(1)
    expect(r.toneMappingExposure).toBeGreaterThan(noon)
    scene.dispose()
  })
})

describe('EoScene targets', () => {
  const report = (key: number, shape: HeldReport['shape'] = 'rotary-small'): HeldReport => ({
    key,
    sensorId: 'eo-1',
    azimuthDeg: 38,
    elevationDeg: 4,
    sizeDeg: 0.4,
    apparentPx: 20,
    shape,
    seenAt: 0,
  })
  const pose = {
    position: { x: -126, y: 92, z: 9 },
    bearingDeg: 38,
    elevationDeg: 4,
    fovDeg: 24,
    nowMs: 0,
  }

  it('places a mesh per held report and drops it when the report goes', () => {
    const scene = new EoScene(canvas(), { tier: 'low' })
    const placed = (scene as unknown as { placed: Map<number, unknown> }).placed
    scene.update({ ...pose, reports: [report(1), report(2, 'bird')] })
    expect(placed.size).toBe(2)
    scene.update({ ...pose, reports: [report(2, 'bird')] })
    expect([...placed.keys()]).toEqual([2])
    scene.update({ ...pose, reports: [report(2, 'point')] })
    expect(placed.size).toBe(1)
    scene.dispose()
  })

  it('keeps the camera on the sensor and does not allocate a vector per update', () => {
    const scene = new EoScene(canvas(), { tier: 'low' })
    const camera = (scene as unknown as { camera: THREE.PerspectiveCamera }).camera
    scene.update({ ...pose, reports: [report(1)] })
    expect(camera.position.toArray()).toEqual([-126, 9, -92])
    const make = vi.spyOn(THREE, 'Vector3')
    for (let i = 0; i < 20; i++) scene.update({ ...pose, reports: [report(1)], nowMs: i })
    expect(make).not.toHaveBeenCalled()
    scene.dispose()
  })
})

describe('EoScene teardown', () => {
  it('disposes every geometry, material and texture it made, and the renderer', async () => {
    const disposed = new Set<unknown>()
    for (const proto of [
      THREE.BufferGeometry.prototype,
      THREE.Material.prototype,
      THREE.Texture.prototype,
      THREE.WebGLRenderTarget.prototype,
    ]) {
      const original = proto.dispose
      vi.spyOn(proto, 'dispose').mockImplementation(function (this: unknown) {
        disposed.add(this)
        original.call(this as never)
      })
    }
    const scene = new EoScene(canvas(), { tier: 'high' })
    scene.setSite(briefing)
    scene.setWeather({ condition: 'rain', visibility_m: 5000 })
    await scene.setTerrain(pack)
    scene.setMode('thermal-white-hot')
    scene.update({
      position: { x: 0, y: 0, z: 9 },
      bearingDeg: 0,
      elevationDeg: 0,
      fovDeg: 24,
      reports: [
        {
          key: 1,
          sensorId: 'eo-1',
          azimuthDeg: 0,
          elevationDeg: 0,
          sizeDeg: 0.3,
          apparentPx: 12,
          shape: 'fixed-wing-small',
          seenAt: 0,
        },
      ],
      nowMs: 0,
    })
    scene.render(10)
    const { geometries, materials, textures } = gpuObjects(scene)
    expect(geometries.size).toBeGreaterThan(10)
    expect(materials.size).toBeGreaterThan(10)
    scene.dispose()
    for (const g of geometries) expect(disposed.has(g), 'geometry').toBe(true)
    for (const m of materials) expect(disposed.has(m), `material ${m.type}`).toBe(true)
    for (const t of textures) expect(disposed.has(t), 'texture').toBe(true)
    expect(renderer().disposed).toBe(true)
    expect(renderer().lost).toBe(true)
  })

  it('drops a terrain that finishes parsing after the scene was disposed', async () => {
    const scene = new EoScene(canvas(), { tier: 'low' })
    const pending = scene.setTerrain(pack)
    scene.dispose()
    await pending
    expect(scene.stats().terrain).toBe('flat')
  })
})
