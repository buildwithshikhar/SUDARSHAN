/**
 * The EO view's three.js scene: flat ground, a sky dome driven by the time of day, simple
 * low-poly target meshes drawn from EO reports, and a camera that sits on the EO sensor.
 * Built for an 8 GB laptop with integrated graphics: capped pixel ratio, no postprocessing,
 * shared geometry, every GPU object disposed on teardown.
 */
import * as THREE from 'three'
import { DEG, directionThree, skyColours, verticalFovDeg } from '../geometry'
import type { Briefing, Vec3 } from '../protocol'
import type { EoShape, HeldReport } from './eoHold'

/** Reports are drawn on a sphere of this radius around the camera. It is a drawing device, not a range. */
const DRAW_DISTANCE = 100
const MAX_PIXEL_RATIO = 1.5
/** A target is never drawn smaller than this many canvas pixels, so a point stays visible. */
const MIN_DRAW_PX = 3

export function webglAvailable(): boolean {
  try {
    const canvas = document.createElement('canvas')
    return !!(canvas.getContext('webgl2') ?? canvas.getContext('webgl'))
  } catch {
    return false
  }
}

const enu = (v: Vec3): THREE.Vector3 => new THREE.Vector3(v.x, v.z, -v.y)

function srgb(r: number, g: number, b: number): THREE.Color {
  return new THREE.Color().setRGB(r, g, b, THREE.SRGBColorSpace)
}

interface Placed {
  group: THREE.Group
  shape: EoShape
  wings: THREE.Object3D[]
}

export class EoScene {
  readonly renderer: THREE.WebGLRenderer
  private readonly scene = new THREE.Scene()
  private readonly camera = new THREE.PerspectiveCamera(40, 16 / 9, 0.5, 20000)
  private readonly sky: THREE.Mesh
  private readonly skyColours: THREE.BufferAttribute
  private readonly sun = new THREE.DirectionalLight(0xffffff, 1)
  private readonly ambient = new THREE.AmbientLight(0xffffff, 0.6)
  private readonly fog = new THREE.Fog(0xaab4c0, 1200, 9000)
  private readonly disposables: { dispose(): void }[] = []
  private readonly geometry = new Map<string, THREE.BufferGeometry>()
  private readonly material: THREE.MeshLambertMaterial
  private readonly placed = new Map<number, Placed>()
  private width = 1
  private height = 1
  private skyKey = ''
  private lastRender = 0

  constructor(canvas: HTMLCanvasElement) {
    this.renderer = new THREE.WebGLRenderer({
      canvas,
      antialias: true,
      alpha: false,
      powerPreference: 'low-power',
    })
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, MAX_PIXEL_RATIO))
    this.scene.fog = this.fog

    // Sky dome with a vertical colour ramp.
    const dome = new THREE.SphereGeometry(8000, 24, 14)
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
    this.sky.renderOrder = -2
    this.scene.add(this.sky)
    this.disposables.push(dome, skyMaterial)

    // Ground with a mottled texture; flat, as the scenario terrain is.
    const ground = new THREE.PlaneGeometry(24000, 24000)
    ground.rotateX(-Math.PI / 2)
    const texture = this.groundTexture()
    const groundMaterial = new THREE.MeshLambertMaterial({ map: texture, color: 0xffffff })
    const groundMesh = new THREE.Mesh(ground, groundMaterial)
    groundMesh.renderOrder = -1
    this.scene.add(groundMesh)
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
    const ridgeMesh = new THREE.Mesh(ridge, ridgeMaterial)
    this.scene.add(ridgeMesh)
    this.disposables.push(ridge, ridgeMaterial)

    this.scene.add(this.ambient, this.sun, this.sun.target)
    this.material = new THREE.MeshLambertMaterial({
      color: 0x22262b,
      flatShading: true,
      fog: false,
      depthTest: false,
    })
    this.disposables.push(this.material)
    this.setTimeOfDay(12, 9000)
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

  /** Static fixtures from the briefing: the assets and the sensor masts (not the EO camera itself). */
  setSite(briefing: Briefing): void {
    const box = new THREE.BoxGeometry(1, 1, 1)
    const mast = new THREE.CylinderGeometry(0.6, 0.9, 1, 8)
    const boxMaterial = new THREE.MeshLambertMaterial({ color: 0x8b9096 })
    const mastMaterial = new THREE.MeshLambertMaterial({ color: 0x6d7379 })
    this.disposables.push(box, mast, boxMaterial, mastMaterial)
    for (const asset of briefing.assets) {
      const mesh = new THREE.Mesh(box, boxMaterial)
      mesh.scale.set(34, 9, 20)
      mesh.position.set(asset.position.x, 4.5, -asset.position.y)
      this.scene.add(mesh)
    }
    for (const sensor of briefing.sensors) {
      if (sensor.modality === 'eo') continue
      const mesh = new THREE.Mesh(mast, mastMaterial)
      mesh.scale.set(1, 12, 1)
      mesh.position.set(sensor.position.x, 6, -sensor.position.y)
      this.scene.add(mesh)
    }
  }

  setTimeOfDay(hours: number, visibilityM: number): void {
    const key = `${hours.toFixed(2)}|${Math.round(visibilityM / 100)}`
    if (key === this.skyKey) return
    this.skyKey = key
    const { zenith, horizon } = skyColours(hours)
    const pos = this.sky.geometry.attributes.position
    if (pos) {
      for (let i = 0; i < pos.count; i++) {
        const k = Math.min(1, Math.max(0, pos.getY(i) / 8000))
        const e = Math.pow(k, 0.55)
        this.skyColours.setXYZ(
          i,
          horizon[0] + (zenith[0] - horizon[0]) * e,
          horizon[1] + (zenith[1] - horizon[1]) * e,
          horizon[2] + (zenith[2] - horizon[2]) * e,
        )
      }
      this.skyColours.needsUpdate = true
    }
    this.fog.color.copy(srgb(...horizon))
    this.fog.far = Math.max(2500, visibilityM * 1.1)
    this.fog.near = this.fog.far * 0.12
    const sunHeight = Math.sin(((hours - 6) / 12) * Math.PI)
    const azimuth = (90 + ((hours - 6) / 12) * 180) * DEG
    const elevation = Math.max(0.05, sunHeight) * (Math.PI / 2.2)
    this.sun.position
      .set(
        Math.sin(azimuth) * Math.cos(elevation),
        Math.sin(elevation),
        -Math.cos(azimuth) * Math.cos(elevation),
      )
      .multiplyScalar(1000)
    this.sun.intensity = 0.15 + 1.1 * Math.max(0, sunHeight)
    this.sun.color.copy(
      srgb(
        1,
        0.93 - 0.2 * (1 - Math.min(1, sunHeight * 2)),
        0.82 - 0.3 * (1 - Math.min(1, sunHeight * 2)),
      ),
    )
    this.ambient.color.copy(srgb(...horizon))
    this.ambient.intensity = 0.35 + 0.5 * Math.max(0, sunHeight)
  }

  resize(width: number, height: number): void {
    this.width = Math.max(1, Math.floor(width))
    this.height = Math.max(1, Math.floor(height))
    this.renderer.setSize(this.width, this.height, false)
    this.camera.aspect = this.width / this.height
    this.camera.updateProjectionMatrix()
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
    const cam = enu(opts.position)
    this.camera.position.copy(cam)
    const dir = directionThree(opts.bearingDeg, opts.elevationDeg)
    this.camera.lookAt(cam.x + dir[0], cam.y + dir[1], cam.z + dir[2])
    this.camera.fov = verticalFovDeg(opts.fovDeg, this.camera.aspect)
    this.camera.updateProjectionMatrix()

    const seen = new Set<number>()
    for (const report of opts.reports) {
      seen.add(report.key)
      let entry = this.placed.get(report.key)
      if (!entry || entry.shape !== report.shape) {
        if (entry) this.scene.remove(entry.group)
        entry = this.build(report.shape)
        this.placed.set(report.key, entry)
        this.scene.add(entry.group)
      }
      const d = directionThree(report.azimuthDeg, report.elevationDeg)
      entry.group.position.set(
        cam.x + d[0] * DRAW_DISTANCE,
        cam.y + d[1] * DRAW_DISTANCE,
        cam.z + d[2] * DRAW_DISTANCE,
      )
      // Angular size to world size at the drawing distance, with a floor of a few canvas pixels.
      const minDeg = (MIN_DRAW_PX / this.width) * opts.fovDeg
      const angle = Math.max(report.sizeDeg, minDeg) * DEG
      const world = 2 * DRAW_DISTANCE * Math.tan(angle / 2)
      entry.group.scale.setScalar(world)
      entry.group.rotation.set(0.35, (report.key * 1.9) % (Math.PI * 2), 0)
      const flap = Math.sin(opts.nowMs / 70 + report.key)
      entry.wings.forEach((wing, i) => {
        wing.rotation.z = (i === 0 ? 1 : -1) * (0.35 + 0.45 * flap)
      })
    }
    for (const [key, entry] of this.placed) {
      if (!seen.has(key)) {
        this.scene.remove(entry.group)
        this.placed.delete(key)
      }
    }
  }

  private geometryFor(name: string, make: () => THREE.BufferGeometry): THREE.BufferGeometry {
    let g = this.geometry.get(name)
    if (!g) {
      g = make()
      this.geometry.set(name, g)
      this.disposables.push(g)
    }
    return g
  }

  /** Low-poly meshes of unit span. */
  private build(shape: EoShape): Placed {
    const group = new THREE.Group()
    const wings: THREE.Object3D[] = []
    const box = (w: number, h: number, d: number) =>
      this.geometryFor(`box-${w}-${h}-${d}`, () => new THREE.BoxGeometry(w, h, d))
    const add = (g: THREE.BufferGeometry, x = 0, y = 0, z = 0, ry = 0) => {
      const m = new THREE.Mesh(g, this.material)
      m.position.set(x, y, z)
      m.rotation.y = ry
      m.renderOrder = 10
      group.add(m)
      return m
    }
    switch (shape) {
      case 'rotary-small': {
        add(box(0.22, 0.1, 0.22))
        add(box(0.95, 0.035, 0.05), 0, 0, 0, Math.PI / 4)
        add(box(0.95, 0.035, 0.05), 0, 0, 0, -Math.PI / 4)
        const disc = this.geometryFor(
          'rotor',
          () => new THREE.CylinderGeometry(0.17, 0.17, 0.012, 10),
        )
        for (const [x, z] of [
          [0.34, 0.34],
          [-0.34, 0.34],
          [0.34, -0.34],
          [-0.34, -0.34],
        ] as const)
          add(disc, x, 0.05, z)
        break
      }
      case 'fixed-wing-small': {
        add(box(0.09, 0.09, 0.78))
        add(box(1, 0.025, 0.16), 0, 0.01, 0.05)
        add(box(0.34, 0.025, 0.1), 0, 0.02, -0.34)
        add(box(0.025, 0.14, 0.1), 0, 0.07, -0.34)
        break
      }
      case 'bird': {
        add(box(0.16, 0.1, 0.34))
        for (const side of [-1, 1] as const) {
          const wingGroup = new THREE.Group()
          wingGroup.position.set(side * 0.06, 0.02, 0)
          const wing = new THREE.Mesh(box(0.5, 0.02, 0.2), this.material)
          wing.position.x = side * 0.25
          wing.renderOrder = 10
          wingGroup.add(wing)
          group.add(wingGroup)
          wings.push(wingGroup)
        }
        break
      }
      case 'point': {
        add(this.geometryFor('point', () => new THREE.IcosahedronGeometry(0.4, 0)))
        break
      }
    }
    return { group, shape, wings }
  }

  /** Render, at most once per `minIntervalMs`. */
  render(nowMs: number, minIntervalMs = 0): void {
    if (nowMs - this.lastRender < minIntervalMs) return
    this.lastRender = nowMs
    this.renderer.render(this.scene, this.camera)
  }

  dispose(): void {
    this.placed.forEach((p) => this.scene.remove(p.group))
    this.placed.clear()
    this.disposables.forEach((d) => d.dispose())
    this.disposables.length = 0
    this.renderer.dispose()
    this.renderer.forceContextLoss()
  }
}
