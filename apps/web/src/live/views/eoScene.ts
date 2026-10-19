/**
 * The EO view's three.js scene: terrain (a baked pack, or flat ground), buildings and trees, a sky
 * with sun, moon and stars driven by the scenario clock, height fog, rain, wind, the simple target
 * meshes drawn from EO reports, and a camera that sits on the EO sensor. Day, night-vision and
 * thermal pictures share the scene; the last two go through the post pass in eoPost.ts.
 *
 * Built for an 8 GB laptop with integrated graphics: pixel ratio capped by the quality tier,
 * instancing and shared geometry, no per-frame allocation in `update` and `render`, and every GPU
 * object disposed on teardown. Thermal is a rendering model, not radiometric.
 */
import * as THREE from 'three'
import { DEG, skyColours, verticalFovDeg } from '../geometry'
import { TIERS, type Tier, type TierSettings } from '../quality'
import type { Briefing, Vec3 } from '../protocol'
import { heightAt } from '../terrain/heightAt'
import type { TerrainPack } from '../terrain/types'
import { surfaceTemperature, type EoMode, type ThermalClass, isThermal } from './eoMode'
import type { HeldReport } from './eoHold'
import { parseGlb } from './eoGlb'
import { patchTargetMaterial, TargetField, bobOffset } from './eoMeshes'
import { PostPass, type LookReadout } from './eoPost'
import { Rain } from './eoRain'
import { createSharedUniforms, patchMaterial, type SharedUniforms } from './eoShading'
import {
  apronGeometry,
  buildingsGeometry,
  edgeMeanHeight,
  fillTrees,
  shuffledOrder,
  terrainGeometry,
  treeGeometry,
} from './eoTerrainMesh'
import {
  fogDensity,
  fogShape,
  rainIntensity,
  swayStrength,
  windOf,
  type WeatherLike,
} from './eoWeather'
import { celestial, lighting } from './sky'

/** Reports are drawn on a sphere of this radius around the camera. It is a drawing device, not a range. */
const DRAW_DISTANCE = 100
/** A target is never drawn smaller than this many canvas pixels, so a point stays visible. */
const MIN_DRAW_PX = 3
const SKY_RADIUS = 8000
/** The surrounding flat ground and the width of the apron that joins a pack to it. */
const GROUND_SIZE = 24000
const APRON_M = 1800

function srgb(r: number, g: number, b: number): THREE.Color {
  return new THREE.Color().setRGB(r, g, b, THREE.SRGBColorSpace)
}

/** Write the three.js unit vector for a compass bearing and elevation into `out`. */
function directionInto(
  out: THREE.Vector3,
  bearingDeg: number,
  elevationDeg: number,
): THREE.Vector3 {
  const az = bearingDeg * DEG
  const el = elevationDeg * DEG
  return out.set(Math.sin(az) * Math.cos(el), Math.sin(el), -Math.cos(az) * Math.cos(el))
}

/** A mesh with a daylight look and a thermal look; switching is a material swap, once. */
interface Skin {
  mesh: THREE.Mesh
  day: THREE.Material | THREE.Material[]
  thermal: THREE.Material | THREE.Material[]
}

interface ThermalMaterial {
  material: THREE.MeshLambertMaterial
  cls: ThermalClass
  boost: number
}

const MAP_BOOST = 3.6

export interface EoSceneOptions {
  tier: Tier
  /** Fix the renderer pixel ratio (the /bench route measures at exactly 1080p). */
  fixedPixelRatio?: number
  /** Called a few times a second in thermal and night-vision modes with the gain readout. */
  onLook?: (look: LookReadout) => void
}

export interface SceneStats {
  tier: Tier
  mode: EoMode
  terrain: 'flat' | 'heightmap' | 'glb'
  buildings: 'none' | 'json' | 'glb'
  treesDrawn: number
  rainDrawn: number
  shadows: boolean
  pixelRatio: number
  drawCalls: number
  triangles: number
  /** Target contacts drawn in the last update, and the triangles they submit. */
  targetsDrawn: number
  targetTriangles: number
  /** The shapes drawn in the last update, comma separated. */
  targetShapes: string
}

export class EoScene {
  readonly renderer: THREE.WebGLRenderer
  private readonly scene = new THREE.Scene()
  private readonly camera = new THREE.PerspectiveCamera(40, 16 / 9, 0.5, 20000)
  private readonly uniforms: SharedUniforms = createSharedUniforms()
  private readonly sky: THREE.Mesh
  private readonly skyColours: THREE.BufferAttribute
  private readonly sunDisc: THREE.Mesh
  private readonly sunHalo: THREE.Mesh
  private readonly moonDisc: THREE.Mesh
  private readonly moonHalo: THREE.Mesh
  private readonly stars: THREE.Points
  private readonly starMaterial: THREE.PointsMaterial
  private readonly sun = new THREE.DirectionalLight(0xffffff, 1)
  private readonly moon = new THREE.DirectionalLight(0x9fb4e0, 0)
  private readonly ambient = new THREE.AmbientLight(0xffffff, 0.6)
  private readonly fog = new THREE.FogExp2(0xaab4c0, 0.0002)
  private readonly disposables: { dispose(): void }[] = []
  private readonly litMaterials = new Set<THREE.Material>()
  private readonly geometry = new Map<string, THREE.BufferGeometry>()
  private readonly targetMaterial: THREE.MeshLambertMaterial
  private readonly targets: TargetField
  private readonly pose = new THREE.Object3D()
  private readonly groundMesh: THREE.Mesh
  private readonly groundThermal: THREE.MeshLambertMaterial
  private readonly terrainGroup = new THREE.Group()
  private readonly siteGroup = new THREE.Group()
  private readonly rain: Rain
  private readonly skins: Skin[] = []
  private readonly thermalMaterials: ThermalMaterial[] = []
  private siteMaterials: {
    box: THREE.Material
    mast: THREE.Material
    boxThermal: THREE.Material
    mastThermal: THREE.Material
  } | null = null
  private trees: THREE.InstancedMesh | null = null
  private pack: TerrainPack | null = null
  private terrainRequested = false
  private terrainToken = 0
  private terrainKind: SceneStats['terrain'] = 'flat'
  private buildingsKind: SceneStats['buildings'] = 'none'
  private briefing: Briefing | null = null
  private weather: WeatherLike = {}
  private post: PostPass | null = null
  private mode: EoMode = 'day'
  private tier: Tier
  private settings: TierSettings
  private shadowsOn = false
  private hours = 12
  private envKey = ''
  private width = 1
  private height = 1
  private lastRender = 0
  private startedAt = Number.NaN
  private disposed = false
  private readonly cam = new THREE.Vector3()
  private readonly dir = new THREE.Vector3()
  private readonly look = new THREE.Vector3()
  private readonly focus = new THREE.Vector3()
  private readonly sunVec = new THREE.Vector3()
  private readonly nightTint = new THREE.Color(0.6, 0.7, 1)
  private readonly moonVec = new THREE.Vector3()

  constructor(
    canvas: HTMLCanvasElement,
    private readonly options: EoSceneOptions,
  ) {
    this.tier = options.tier
    this.settings = TIERS[options.tier]
    this.renderer = new THREE.WebGLRenderer({
      canvas,
      antialias: this.settings.antialias,
      alpha: false,
      powerPreference: 'low-power',
    })
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping
    this.renderer.toneMappingExposure = 1
    this.renderer.shadowMap.type = THREE.PCFShadowMap
    this.scene.fog = this.fog

    // Sky dome with a vertical colour ramp, stars, and sun and moon discs with soft halos.
    const dome = new THREE.SphereGeometry(SKY_RADIUS, 24, 14)
    const count = dome.attributes.position?.count ?? 0
    this.skyColours = new THREE.BufferAttribute(new Float32Array(count * 3), 3)
    dome.setAttribute('color', this.skyColours)
    const skyMaterial = new THREE.MeshBasicMaterial({
      vertexColors: true,
      side: THREE.BackSide,
      fog: false,
      depthWrite: false,
    })
    this.sky = new THREE.Mesh(dome, skyMaterial)
    this.sky.renderOrder = -3
    this.scene.add(this.sky)
    this.disposables.push(dome, skyMaterial)

    const glow = this.glowTexture()
    this.disposables.push(glow)
    const disc = new THREE.CircleGeometry(1, 28)
    this.disposables.push(disc)
    const discMaterial = (colour: number) =>
      new THREE.MeshBasicMaterial({ color: colour, fog: false, toneMapped: false })
    const sunMaterial = discMaterial(0xfff4dc)
    const moonMaterial = discMaterial(0xdfe6f2)
    this.sunDisc = new THREE.Mesh(disc, sunMaterial)
    this.moonDisc = new THREE.Mesh(disc, moonMaterial)
    const haloMaterial = (colour: number) =>
      new THREE.MeshBasicMaterial({
        map: glow,
        color: colour,
        fog: false,
        transparent: true,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
        toneMapped: false,
      })
    const sunHaloMaterial = haloMaterial(0xffe2b0)
    const moonHaloMaterial = haloMaterial(0x9db4de)
    this.sunHalo = new THREE.Mesh(disc, sunHaloMaterial)
    this.moonHalo = new THREE.Mesh(disc, moonHaloMaterial)
    this.sunDisc.scale.setScalar(150)
    this.sunHalo.scale.setScalar(900)
    this.moonDisc.scale.setScalar(110)
    this.moonHalo.scale.setScalar(520)
    for (const m of [this.sunDisc, this.moonDisc]) m.renderOrder = -2
    for (const m of [this.sunHalo, this.moonHalo]) m.renderOrder = -1
    this.scene.add(this.sunDisc, this.sunHalo, this.moonDisc, this.moonHalo)
    this.disposables.push(sunMaterial, moonMaterial, sunHaloMaterial, moonHaloMaterial)

    const starGeometry = new THREE.BufferGeometry()
    const starPositions = new Float32Array(700 * 3)
    let seed = 4242
    const rand = () => {
      seed = (seed * 16807) % 2147483647
      return seed / 2147483647
    }
    for (let i = 0; i < 700; i++) {
      const az = rand() * Math.PI * 2
      const el = Math.asin(0.02 + 0.98 * rand())
      const r = SKY_RADIUS * 0.96
      starPositions.set(
        [Math.sin(az) * Math.cos(el) * r, Math.sin(el) * r, -Math.cos(az) * Math.cos(el) * r],
        i * 3,
      )
    }
    starGeometry.setAttribute('position', new THREE.BufferAttribute(starPositions, 3))
    this.starMaterial = new THREE.PointsMaterial({
      color: 0xdfe6ff,
      size: 1.6,
      sizeAttenuation: false,
      transparent: true,
      opacity: 0,
      depthWrite: false,
      fog: false,
      toneMapped: false,
    })
    this.stars = new THREE.Points(starGeometry, this.starMaterial)
    this.stars.renderOrder = -2
    this.stars.frustumCulled = false
    this.scene.add(this.stars)
    this.disposables.push(starGeometry, this.starMaterial)

    // Surrounding flat ground with a mottled texture, as the scenario terrain was before packs.
    const ground = new THREE.PlaneGeometry(GROUND_SIZE, GROUND_SIZE)
    ground.rotateX(-Math.PI / 2)
    const texture = this.groundTexture()
    const groundMaterial = new THREE.MeshLambertMaterial({ map: texture, color: 0xffffff })
    patchMaterial(groundMaterial, this.uniforms)
    this.groundThermal = this.makeThermal('terrain')
    this.groundMesh = new THREE.Mesh(ground, groundMaterial)
    this.groundMesh.renderOrder = -1
    this.groundMesh.receiveShadow = true
    this.scene.add(this.groundMesh)
    this.litMaterials.add(groundMaterial)
    this.disposables.push(ground, texture, groundMaterial)

    // A low, distant ridge line gives the horizon some depth.
    const ridge = new THREE.CylinderGeometry(7000, 7000, 260, 72, 1, true)
    const pos = ridge.attributes.position
    if (pos) {
      for (let i = 0; i < pos.count; i++) {
        if (pos.getY(i) > 0) {
          const a = Math.atan2(pos.getZ(i), pos.getX(i))
          pos.setY(
            i,
            40 +
              90 * Math.abs(Math.sin(a * 3.1 + 0.7) * Math.cos(a * 1.7)) +
              22 * Math.sin(a * 11.3),
          )
        } else pos.setY(i, -5)
      }
      ridge.computeVertexNormals()
    }
    const ridgeMaterial = new THREE.MeshLambertMaterial({ color: 0x59634f, side: THREE.BackSide })
    patchMaterial(ridgeMaterial, this.uniforms)
    const ridgeThermal = this.makeThermal('terrain')
    ridgeThermal.side = THREE.BackSide
    const ridgeMesh = new THREE.Mesh(ridge, ridgeMaterial)
    this.scene.add(ridgeMesh)
    this.skins.push({ mesh: ridgeMesh, day: ridgeMaterial, thermal: ridgeThermal })
    this.litMaterials.add(ridgeMaterial)
    this.disposables.push(ridge, ridgeMaterial)

    this.scene.add(this.terrainGroup, this.siteGroup)
    this.skins.push({ mesh: this.groundMesh, day: groundMaterial, thermal: this.groundThermal })

    // Lights: ambient fill, the sun (which casts shadows on the high tier) and a dim cool moon.
    this.sun.shadow.mapSize.set(2048, 2048)
    this.sun.shadow.camera.left = -330
    this.sun.shadow.camera.right = 330
    this.sun.shadow.camera.top = 330
    this.sun.shadow.camera.bottom = -330
    this.sun.shadow.camera.near = 10
    this.sun.shadow.camera.far = 2400
    this.sun.shadow.bias = -0.0004
    this.sun.shadow.normalBias = 0.6
    this.scene.add(this.ambient, this.sun, this.sun.target, this.moon, this.moon.target)
    this.disposables.push({ dispose: () => this.sun.shadow.dispose() })

    // Targets: dark silhouettes by day, hot by emission in thermal.
    this.targetMaterial = new THREE.MeshLambertMaterial({
      color: 0x22262b,
      flatShading: true,
      fog: false,
      depthTest: false,
    })
    patchTargetMaterial(this.targetMaterial)
    this.disposables.push(this.targetMaterial)
    this.targets = new TargetField(this.scene, this.targetMaterial)
    this.disposables.push({ dispose: () => this.targets.dispose(this.scene) })

    this.rain = new Rain(this.uniforms)
    this.scene.add(this.rain.object)
    this.disposables.push(this.rain)

    this.applyQuality()
    this.setTimeOfDay(12)
  }

  // ---------------------------------------------------------------- helpers

  private glowTexture(): THREE.CanvasTexture {
    const canvas = document.createElement('canvas')
    canvas.width = canvas.height = 64
    const ctx = canvas.getContext('2d')
    if (ctx) {
      const g = ctx.createRadialGradient(32, 32, 0, 32, 32, 32)
      g.addColorStop(0, 'rgba(255,255,255,0.9)')
      g.addColorStop(0.25, 'rgba(255,255,255,0.28)')
      g.addColorStop(1, 'rgba(255,255,255,0)')
      ctx.fillStyle = g
      ctx.fillRect(0, 0, 64, 64)
    }
    return new THREE.CanvasTexture(canvas)
  }

  private groundTexture(): THREE.CanvasTexture {
    const canvas = document.createElement('canvas')
    canvas.width = canvas.height = 128
    const ctx = canvas.getContext('2d')
    if (ctx) {
      ctx.fillStyle = '#6b7355'
      ctx.fillRect(0, 0, 128, 128)
      let seed = 7
      const rand = () => {
        seed = (seed * 16807) % 2147483647
        return seed / 2147483647
      }
      for (let i = 0; i < 700; i++) {
        const v = 88 + Math.floor(rand() * 40)
        ctx.fillStyle = `rgb(${v + 10}, ${v + 16}, ${v - 20})`
        ctx.fillRect(rand() * 128, rand() * 128, 1 + rand() * 4, 1 + rand() * 3)
      }
    }
    const texture = new THREE.CanvasTexture(canvas)
    texture.wrapS = texture.wrapT = THREE.RepeatWrapping
    texture.repeat.set(220, 220)
    texture.colorSpace = THREE.SRGBColorSpace
    return texture
  }

  /** A thermal-look material for a surface class: temperature as grey, texture as modulation. */
  private makeThermal(
    cls: ThermalClass,
    map: THREE.Texture | null = null,
  ): THREE.MeshLambertMaterial {
    const material = new THREE.MeshLambertMaterial({ color: 0x808080, map })
    patchMaterial(material, this.uniforms)
    // A landcover texture is dark (albedo about 0.2); lift the colour so the class temperature,
    // not the albedo, sets the level. The automatic gain removes the absolute scale anyway.
    this.thermalMaterials.push({ material, cls, boost: map ? MAP_BOOST : 1 })
    this.litMaterials.add(material)
    this.disposables.push(material)
    return material
  }

  private track<T extends THREE.Material>(material: T): T {
    this.litMaterials.add(material)
    this.disposables.push(material)
    return material
  }

  // ---------------------------------------------------------------- site and terrain

  /** Static fixtures from the briefing: the assets and the sensor masts (not the EO camera itself). */
  setSite(briefing: Briefing): void {
    this.briefing = briefing
    this.buildSite()
  }

  private groundAt(x: number, y: number): number {
    return this.pack ? heightAt(this.pack, x, y) : 0
  }

  private buildSite(): void {
    const briefing = this.briefing
    if (!briefing) return
    this.removeSkins((mesh) => mesh.parent === this.siteGroup, false)
    this.siteGroup.clear()
    const box = this.shared('site-box', () => new THREE.BoxGeometry(1, 1, 1))
    const mast = this.shared('site-mast', () => new THREE.CylinderGeometry(0.6, 0.9, 1, 8))
    this.siteMaterials ??= {
      box: this.track(new THREE.MeshLambertMaterial({ color: 0x8b9096 })),
      mast: this.track(new THREE.MeshLambertMaterial({ color: 0x6d7379 })),
      boxThermal: this.makeThermal('building'),
      mastThermal: this.makeThermal('metal'),
    }
    const m = this.siteMaterials
    for (const asset of briefing.assets) {
      const mesh = new THREE.Mesh(box, m.box)
      mesh.scale.set(34, 9, 20)
      mesh.position.set(
        asset.position.x,
        this.groundAt(asset.position.x, asset.position.y) + 4.5,
        -asset.position.y,
      )
      mesh.castShadow = mesh.receiveShadow = true
      this.siteGroup.add(mesh)
      this.skins.push({ mesh, day: m.box, thermal: m.boxThermal })
    }
    for (const sensor of briefing.sensors) {
      if (sensor.modality === 'eo' || sensor.modality === 'ir') continue
      const mesh = new THREE.Mesh(mast, m.mast)
      mesh.scale.set(1, 12, 1)
      mesh.position.set(
        sensor.position.x,
        this.groundAt(sensor.position.x, sensor.position.y) + 6,
        -sensor.position.y,
      )
      mesh.castShadow = true
      this.siteGroup.add(mesh)
      this.skins.push({ mesh, day: m.mast, thermal: m.mastThermal })
    }
    this.applySkins()
  }
  private shared(name: string, make: () => THREE.BufferGeometry): THREE.BufferGeometry {
    let g = this.geometry.get(name)
    if (!g) {
      g = make()
      this.geometry.set(name, g)
      this.disposables.push(g)
    }
    return g
  }

  /**
   * Draw a terrain pack, or flat ground for `null`. The pack's GLB meshes are used when they
   * parse; otherwise the heightmap and building footprints are meshed here. Resolves when drawn.
   */
  async setTerrain(pack: TerrainPack | null): Promise<void> {
    if (this.terrainRequested && pack === this.pack) return
    this.terrainRequested = true
    const token = ++this.terrainToken
    this.clearTerrain()
    this.pack = pack
    if (!pack) {
      this.groundMesh.position.y = 0
      this.buildSite()
      return
    }
    const outer = edgeMeanHeight(pack)
    this.groundMesh.position.y = outer - 0.6

    // terrain surface
    let surface: THREE.Object3D | null = null
    if (pack.terrainGlb) {
      try {
        surface = await parseGlb(pack.terrainGlb)
      } catch {
        surface = null
      }
    }
    if (this.disposed || token !== this.terrainToken) {
      if (surface) this.discard(surface)
      return
    }
    if (surface) {
      this.adoptGlb(surface, 'terrain')
      this.terrainKind = 'glb'
    } else {
      const g = terrainGeometry(pack)
      this.disposables.push(g)
      this.addSkinned(g, 'terrain', { vertexColors: true }, { receive: true })
      this.terrainKind = 'heightmap'
    }
    const apron = apronGeometry(pack, APRON_M)
    this.disposables.push(apron)
    this.addSkinned(apron, 'terrain', { vertexColors: true }, { receive: true })

    // buildings
    let built: THREE.Object3D | null = null
    if (pack.buildingsGlb) {
      try {
        built = await parseGlb(pack.buildingsGlb)
      } catch {
        built = null
      }
    }
    if (this.disposed || token !== this.terrainToken) {
      if (built) this.discard(built)
      return
    }
    if (built) {
      this.adoptGlb(built, 'building')
      this.buildingsKind = 'glb'
    } else {
      const g = buildingsGeometry(pack)
      if (g) {
        this.disposables.push(g)
        const mesh = new THREE.Mesh(g)
        const walls = this.track(new THREE.MeshLambertMaterial({ color: 0x77736c }))
        const roofs = this.track(new THREE.MeshLambertMaterial({ color: 0x4a4a4d }))
        patchMaterial(walls, this.uniforms)
        patchMaterial(roofs, this.uniforms)
        this.skinMesh(mesh, [walls, roofs], 'building', { cast: true, receive: true })
        this.terrainGroup.add(mesh)
        this.buildingsKind = 'json'
      }
    }

    // trees
    if (pack.trees.length >= 3) this.buildTrees(pack)

    this.buildSite()
    this.applySkins()
    this.applyEnvironment(true)
    this.applyQuality()
  }

  private clearTerrain(): void {
    this.removeSkins((mesh) => this.isInside(mesh, this.terrainGroup), true)
    this.terrainGroup.traverse((o) => {
      const mesh = o as THREE.Mesh
      if (mesh.isMesh) {
        mesh.geometry.dispose()
        for (const mat of Array.isArray(mesh.material) ? mesh.material : [mesh.material]) {
          mat.dispose()
        }
      }
    })
    this.terrainGroup.clear()
    this.trees?.dispose()
    this.trees = null
    this.terrainKind = 'flat'
    this.buildingsKind = 'none'
  }

  /** Forget the skins of meshes about to be removed, and the thermal materials that went with them. */
  private removeSkins(match: (mesh: THREE.Mesh) => boolean, release: boolean): void {
    const gone = this.skins.filter((skin) => match(skin.mesh))
    // The site's materials are shared and outlive its meshes; the terrain's go with it.
    for (const skin of release ? gone : []) {
      for (const m of Array.isArray(skin.thermal) ? skin.thermal : [skin.thermal]) {
        const at = this.thermalMaterials.findIndex((t) => t.material === m)
        if (at >= 0) this.thermalMaterials.splice(at, 1)
        this.litMaterials.delete(m)
        m.dispose()
      }
      for (const m of Array.isArray(skin.day) ? skin.day : [skin.day]) this.litMaterials.delete(m)
    }
    const keep = this.skins.filter((skin) => !gone.includes(skin))
    this.skins.length = 0
    this.skins.push(...keep)
  }

  /** Free a parsed GLB that was never added to the scene. */
  private discard(root: THREE.Object3D): void {
    root.traverse((o) => {
      const mesh = o as THREE.Mesh
      if (!mesh.isMesh) return
      mesh.geometry.dispose()
      for (const m of Array.isArray(mesh.material) ? mesh.material : [mesh.material]) {
        const standard = m as THREE.MeshStandardMaterial
        standard.map?.dispose()
        m.dispose()
      }
    })
  }

  private isInside(object: THREE.Object3D, ancestor: THREE.Object3D): boolean {
    for (let p = object.parent; p; p = p.parent) if (p === ancestor) return true
    return false
  }

  /** Move a parsed GLB into the scene, replacing its materials with the scene's own Lambert pair. */
  private adoptGlb(root: THREE.Object3D, cls: ThermalClass): void {
    root.traverse((o) => {
      const mesh = o as THREE.Mesh
      if (!mesh.isMesh) return
      const source = Array.isArray(mesh.material) ? mesh.material : [mesh.material]
      const day = source.map((s) => {
        const m = s as THREE.MeshStandardMaterial
        const lambert = new THREE.MeshLambertMaterial({
          color: m.color,
          map: m.map,
          vertexColors: m.vertexColors,
          side: m.side,
        })
        patchMaterial(lambert, this.uniforms)
        this.track(lambert)
        if (m.map) this.disposables.push(m.map)
        m.dispose()
        return lambert
      })
      this.skinMesh(mesh, day.length === 1 ? (day[0] as THREE.Material) : day, cls, {
        cast: cls === 'building',
        receive: true,
      })
    })
    this.terrainGroup.add(root)
  }

  private addSkinned(
    geometry: THREE.BufferGeometry,
    cls: ThermalClass,
    material: { vertexColors: boolean },
    shadows: { cast?: boolean; receive?: boolean },
  ): void {
    const day = this.track(new THREE.MeshLambertMaterial({ vertexColors: material.vertexColors }))
    patchMaterial(day, this.uniforms)
    const mesh = new THREE.Mesh(geometry, day)
    this.skinMesh(mesh, day, cls, shadows)
    this.terrainGroup.add(mesh)
  }

  private skinMesh(
    mesh: THREE.Mesh,
    day: THREE.Material | THREE.Material[],
    cls: ThermalClass,
    shadows: { cast?: boolean; receive?: boolean },
  ): void {
    const maps = (Array.isArray(day) ? day : [day]).map(
      (d) => (d as THREE.MeshLambertMaterial).map ?? null,
    )
    const thermal = maps.map((map) => this.makeThermal(cls, map))
    mesh.material = day
    mesh.castShadow = shadows.cast === true
    mesh.receiveShadow = shadows.receive === true
    this.skins.push({
      mesh,
      day,
      thermal: Array.isArray(day) ? thermal : (thermal[0] as THREE.Material),
    })
    for (const m of Array.isArray(day) ? day : [day]) this.litMaterials.add(m)
  }

  private buildTrees(pack: TerrainPack): void {
    const total = Math.floor(pack.trees.length / 3)
    const geometry = treeGeometry()
    this.disposables.push(geometry)
    const day = this.track(new THREE.MeshLambertMaterial({ vertexColors: true }))
    patchMaterial(day, this.uniforms, { sway: true })
    const thermal = this.makeThermal('vegetation')
    // the sway patch is shared with the thermal look through the same shader edit
    patchMaterial(thermal, this.uniforms, { sway: true })
    const mesh = new THREE.InstancedMesh(geometry, day, total)
    mesh.frustumCulled = false
    mesh.castShadow = true
    mesh.receiveShadow = false
    fillTrees(mesh, pack, shuffledOrder(total))
    this.trees = mesh
    this.skins.push({ mesh, day, thermal })
    this.terrainGroup.add(mesh)
  }

  // ---------------------------------------------------------------- weather, time, mode, quality

  /** The briefing's weather: fog, rain, wind and cloud. The frame carries none of these. */
  setWeather(weather: WeatherLike): void {
    this.weather = weather
    const wind = windOf(weather)
    this.uniforms.wind.value.set(wind.x, wind.z)
    this.uniforms.sway.value = swayStrength(wind.speedMps)
    const shape = fogShape(weather)
    this.uniforms.fogBoost.value = shape.groundBoost
    this.uniforms.fogScale.value = shape.scaleM
    this.fog.density = fogDensity(weather.visibility_m)
    this.applyQuality()
    this.applyEnvironment(true)
  }

  setTimeOfDay(hours: number): void {
    this.hours = hours
    this.applyEnvironment(false)
  }

  /** Sky, light, fog colour and thermal temperatures for the clock, weather and mode. */
  private applyEnvironment(force: boolean): void {
    const key = `${this.hours.toFixed(2)}|${this.mode}`
    if (!force && key === this.envKey) return
    this.envKey = key
    const hours = this.hours
    const cloud = this.weather.cloud_cover_pct ?? 0
    const thermal = isThermal(this.mode)
    const c = celestial(hours, cloud)
    const light = lighting(hours, cloud)

    // sky ramp and fog colour
    const pos = this.sky.geometry.attributes.position
    let horizon: [number, number, number]
    if (thermal) {
      const cold = surfaceTemperature('sky', hours, cloud)
      const lo = cold
      const hi = cold + 0.1
      horizon = [hi, hi, hi]
      if (pos) {
        for (let i = 0; i < pos.count; i++) {
          const k = Math.min(1, Math.max(0, pos.getY(i) / SKY_RADIUS))
          const v = hi + (lo - hi) * Math.pow(k, 0.55)
          this.skyColours.setXYZ(i, v, v, v)
        }
      }
      this.fog.color.setRGB(hi, hi, hi, THREE.LinearSRGBColorSpace)
    } else {
      const { zenith, horizon: h } = skyColours(hours)
      horizon = h
      const z = srgb(...zenith)
      const hz = srgb(...h)
      if (pos) {
        for (let i = 0; i < pos.count; i++) {
          const k = Math.min(1, Math.max(0, pos.getY(i) / SKY_RADIUS))
          const e = Math.pow(k, 0.55)
          this.skyColours.setXYZ(
            i,
            hz.r + (z.r - hz.r) * e,
            hz.g + (z.g - hz.g) * e,
            hz.b + (z.b - hz.b) * e,
          )
        }
      }
      const tint = fogShape(this.weather).tint
      this.fog.color.copy(hz).lerp(new THREE.Color(0.55, 0.42, 0.28), tint)
    }
    this.skyColours.needsUpdate = true

    // lights
    if (thermal) {
      // Relief shading only: temperature, not illumination, makes the picture.
      this.ambient.color.setRGB(1, 1, 1)
      this.ambient.intensity = 1.9
      this.sun.color.setRGB(1, 1, 1)
      this.sun.intensity = 1.5
      this.moon.intensity = 0
    } else {
      // the ambient colour carries the hue of the sky; its level is the light's intensity
      this.ambient.color.copy(srgb(...horizon))
      this.ambient.color.multiplyScalar(
        1 / Math.max(0.05, this.ambient.color.r, this.ambient.color.g, this.ambient.color.b),
      )
      this.ambient.color.lerp(this.nightTint, c.night * 0.5)
      this.ambient.intensity = light.ambientIntensity
      this.sun.color.copy(srgb(1, 0.93 - 0.2 * light.sunWarmth, 0.82 - 0.3 * light.sunWarmth))
      this.sun.intensity = light.sunIntensity
      this.moon.intensity = light.moonIntensity
    }
    this.renderer.toneMappingExposure = light.exposure
    this.sunVec.set(c.sunDir[0], Math.max(c.sunDir[1], 0.04), c.sunDir[2]).normalize()
    this.moonVec.set(c.moonDir[0], c.moonDir[1], c.moonDir[2])
    this.placeLights()

    // discs and stars
    const place = (disc: THREE.Mesh, halo: THREE.Mesh, dir: readonly [number, number, number]) => {
      disc.position.set(dir[0] * 7600, dir[1] * 7600, dir[2] * 7600)
      disc.lookAt(0, 0, 0)
      halo.position.copy(disc.position)
      halo.quaternion.copy(disc.quaternion)
    }
    place(this.sunDisc, this.sunHalo, c.sunDir)
    place(this.moonDisc, this.moonHalo, c.moonDir)
    const sunUp = c.sunDir[1] > -0.02
    const moonUp = c.moonDir[1] > -0.02 && !thermal
    this.sunDisc.visible = sunUp
    this.sunHalo.visible = sunUp && !thermal
    this.moonDisc.visible = moonUp
    this.moonHalo.visible = moonUp
    ;(this.sunDisc.material as THREE.MeshBasicMaterial).color.setRGB(
      1,
      thermal ? 1 : 0.96 - 0.1 * light.sunWarmth,
      thermal ? 1 : 0.88 - 0.25 * light.sunWarmth,
    )
    this.starMaterial.opacity = thermal ? 0 : c.stars
    this.stars.visible = !thermal && c.stars > 0.01

    // thermal temperatures follow the clock
    for (const { material, cls, boost } of this.thermalMaterials) {
      const t = surfaceTemperature(cls, hours, cloud) * boost
      material.color.setRGB(t, t, t, THREE.LinearSRGBColorSpace)
    }
    this.applyTarget()
    this.applyRain()
  }

  /** Put the directional lights on the focus point so the shadow box follows the camera. */
  private placeLights(): void {
    this.sun.target.position.copy(this.focus)
    this.sun.position.copy(this.focus).addScaledVector(this.sunVec, 1000)
    this.sun.target.updateMatrixWorld()
    this.moon.target.position.copy(this.focus)
    this.moon.position.copy(this.focus).addScaledVector(this.moonVec, 1000)
    this.moon.target.updateMatrixWorld()
  }

  private applyTarget(): void {
    const m = this.targetMaterial
    if (isThermal(this.mode)) {
      const t = surfaceTemperature('target', this.hours)
      m.color.setRGB(0, 0, 0)
      m.emissive.setRGB(t, t, t)
    } else {
      m.color.set(0x22262b)
      m.emissive.setRGB(0, 0, 0)
    }
  }

  private applyRain(): void {
    const share = rainIntensity(this.weather)
    this.rain.setCount(share * this.settings.rainParticles)
    if (isThermal(this.mode)) this.rain.setLook(0.18, 0.18, 0.18, 0.28)
    else this.rain.setLook(0.82, 0.88, 0.96, 0.75)
  }

  private applySkins(): void {
    const thermal = isThermal(this.mode)
    for (const skin of this.skins) skin.mesh.material = thermal ? skin.thermal : skin.day
  }

  /** Switch the picture. A mode that is not day or night vision draws through the post pass. */
  setMode(mode: EoMode): void {
    if (mode === this.mode) return
    this.mode = mode
    this.applySkins()
    if (mode === 'day') {
      this.post?.dispose()
      this.post = null
    } else {
      if (!this.post) {
        this.post = new PostPass(this.renderer, (look) => this.options.onLook?.(look))
        this.resizePost()
      }
      this.post.setMode(mode)
    }
    this.applyShadows()
    this.applyEnvironment(true)
  }

  /** Change the quality tier at run time. (Antialiasing is fixed when the context is created.) */
  setQuality(tier: Tier): void {
    if (tier === this.tier) return
    this.tier = tier
    this.settings = TIERS[tier]
    this.applyQuality()
  }

  private applyQuality(): void {
    const s = this.settings
    this.renderer.setPixelRatio(
      this.options.fixedPixelRatio ?? Math.min(window.devicePixelRatio || 1, s.pixelRatioCap),
    )
    this.renderer.setSize(this.width, this.height, false)
    if (this.trees) {
      this.trees.count = Math.floor(this.trees.instanceMatrix.count * s.treeFraction)
    }
    this.applyRain()
    this.applyShadows()
    this.resizePost()
  }

  private applyShadows(): void {
    const on = this.settings.shadows && !isThermal(this.mode)
    if (on === this.shadowsOn) return
    this.shadowsOn = on
    this.renderer.shadowMap.enabled = on
    this.sun.castShadow = on
    if (!on && this.sun.shadow.map) {
      this.sun.shadow.map.dispose()
      this.sun.shadow.map = null
    }
    for (const m of this.litMaterials) m.needsUpdate = true
    for (const t of this.thermalMaterials) t.material.needsUpdate = true
  }

  private resizePost(): void {
    if (!this.post) return
    const size = this.renderer.getDrawingBufferSize(new THREE.Vector2())
    this.post.resize(size.x, size.y, this.settings.postScale, this.tier === 'high' ? 2 : 0)
  }

  // ---------------------------------------------------------------- per frame

  resize(width: number, height: number): void {
    this.width = Math.max(1, Math.floor(width))
    this.height = Math.max(1, Math.floor(height))
    this.renderer.setSize(this.width, this.height, false)
    this.camera.aspect = this.width / this.height
    this.camera.updateProjectionMatrix()
    this.resizePost()
  }

  /** Point the camera and place the held reports. */
  update(opts: {
    position: Vec3
    bearingDeg: number
    elevationDeg: number
    fovDeg: number
    reports: readonly HeldReport[]
    nowMs: number
  }): void {
    const p = opts.position
    this.cam.set(p.x, p.z, -p.y)
    this.camera.position.copy(this.cam)
    directionInto(this.dir, opts.bearingDeg, opts.elevationDeg)
    this.look.copy(this.cam).add(this.dir)
    this.camera.lookAt(this.look)
    this.camera.fov = verticalFovDeg(opts.fovDeg, this.camera.aspect)
    this.camera.updateProjectionMatrix()
    this.rain.follow(this.cam)
    if (Math.hypot(this.focus.x - this.cam.x, this.focus.z - this.cam.z) > 25) {
      this.focus.set(this.cam.x, 0, this.cam.z)
      this.placeLights()
    }

    const tSec = opts.nowMs / 1000
    const pose = this.pose
    this.targets.begin()
    for (const report of opts.reports) {
      const d = directionInto(this.dir, report.azimuthDeg, report.elevationDeg)
      pose.position.set(
        this.cam.x + d.x * DRAW_DISTANCE,
        this.cam.y + d.y * DRAW_DISTANCE,
        this.cam.z + d.z * DRAW_DISTANCE,
      )
      // Angular size to world size at the drawing distance, with a floor of a few canvas pixels.
      const minDeg = (MIN_DRAW_PX / this.width) * opts.fovDeg
      const angle = Math.max(report.sizeDeg, minDeg) * DEG
      const world = 2 * DRAW_DISTANCE * Math.tan(angle / 2)
      pose.scale.setScalar(world)
      // Face the camera, then pose the model: aircraft seen from above at a slant, birds side on,
      // kites and balloons face-on.
      pose.rotation.set(0, 0, 0)
      pose.lookAt(this.cam)
      const spin = (report.key * 1.9) % (Math.PI * 2)
      switch (report.shape) {
        case 'bird':
          pose.rotateY(Math.PI / 2 + 0.3 * Math.sin(spin))
          break
        case 'kite':
          pose.rotateZ(0.35 * Math.sin(spin + tSec * 0.5))
          break
        case 'balloon':
          pose.translateY(bobOffset(report.key, tSec) * world)
          break
        case 'point':
          break
        default:
          pose.rotateX(Math.PI / 2 - 0.45)
          pose.rotateY(spin)
      }
      this.targets.place(report.shape, report.key, pose, tSec)
    }
    this.targets.end()
  }

  /** Render, at most once per `minIntervalMs`. */
  render(nowMs: number, minIntervalMs = 0): void {
    if (nowMs - this.lastRender < minIntervalMs) return
    this.lastRender = nowMs
    if (Number.isNaN(this.startedAt)) this.startedAt = nowMs
    this.uniforms.time.value = (nowMs - this.startedAt) / 1000
    if (this.post) this.post.render(this.scene, this.camera)
    else this.renderer.render(this.scene, this.camera)
  }

  /** The shapes drawn in the last update. */
  targetShapes(): string {
    return this.targets.shapesDrawn()
  }

  /** What is drawn and how, for tests, the debug overlay and the /bench harness. */
  stats(): SceneStats {
    const info = this.renderer.info.render
    return {
      tier: this.tier,
      mode: this.mode,
      terrain: this.terrainKind,
      buildings: this.buildingsKind,
      treesDrawn: this.trees?.count ?? 0,
      rainDrawn: this.rain.drawn,
      shadows: this.shadowsOn,
      pixelRatio: this.renderer.getPixelRatio(),
      drawCalls: info.calls,
      triangles: info.triangles,
      targetsDrawn: this.targets.drawn(),
      targetTriangles: this.targets.triangles(),
      targetShapes: this.targets.shapesDrawn(),
    }
  }

  dispose(): void {
    this.disposed = true
    this.clearTerrain()
    this.post?.dispose()
    this.post = null
    this.disposables.forEach((d) => d.dispose())
    this.disposables.length = 0
    this.renderer.dispose()
    this.renderer.forceContextLoss()
  }
}
