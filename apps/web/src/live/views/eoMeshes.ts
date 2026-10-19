/**
 * The EO view's target meshes: one low-poly model per reported shape, drawn with one
 * THREE.InstancedMesh per shape (one draw call each, whatever the number of contacts).
 *
 * Every model is a single merged geometry of unit size, built once. Per-vertex attributes carry
 * the animation and the thermal look so that nothing is created or disposed per report:
 *   aPart   (hub xyz, kind)  which vertices move: 0 fixed, 1 rotor spin about hub Y, 2 and 3 wing
 *                            flap about hub Z (right, left), 4 propeller spin about hub Z;
 *   aHeat   0..1             how warm the vertex is in a thermal picture (motors and engines warm,
 *                            kite cloth and balloon skin cold);
 *   aAngle  per instance     the animation angle in radians, written each frame from the report
 *                            key and the clock by flapAngle and rotorAngle.
 * Thermal is a rendering model, not radiometric.
 *
 * Triangle budget: the largest model is 88 triangles, so 64 contacts of any one shape stay under
 * 5,700 triangles. TARGET_CAPACITY is a hard cap per shape; contacts beyond it are not drawn.
 */
import * as THREE from 'three'
import type { EoShape } from './eoHold'

export const TARGET_CAPACITY = 64

/** Real bird wing-beat of a small bird, and the share of it drawn so a 60 Hz screen can show it. */
export const BIRD_FLAP_HZ = 12
export const FLAP_VISUAL_SCALE = 0.25
/** Visual rotor and propeller rate in revolutions per second (a real rotor is far above frame rate). */
export const ROTOR_VISUAL_HZ = 2.5
/** Balloon bob: period in seconds and amplitude in model units. */
const BOB_PERIOD_S = 7
const BOB_AMPLITUDE = 0.06

const TAU = Math.PI * 2

/** A phase in [0, 2 pi) that depends only on the report key. */
export function keyPhase(key: number): number {
  const h = Math.imul(key | 0, 0x9e3779b1) >>> 0
  return (h / 0x100000000) * TAU
}

function wrapTau(x: number): number {
  return ((x % TAU) + TAU) % TAU
}

/** Wing angle in radians for a bird, from -0.35 (down) to 0.8 (up). Deterministic in key and time. */
export function flapAngle(key: number, tSec: number): number {
  const phase = TAU * BIRD_FLAP_HZ * FLAP_VISUAL_SCALE * tSec + keyPhase(key)
  return 0.225 + 0.575 * Math.sin(wrapTau(phase))
}

/** Rotor or propeller angle in radians, wrapped to [0, 2 pi). Deterministic in key and time. */
export function rotorAngle(key: number, tSec: number): number {
  return wrapTau(TAU * ROTOR_VISUAL_HZ * tSec + keyPhase(key))
}

/** Vertical bob of a balloon in model units. */
export function bobOffset(key: number, tSec: number): number {
  return BOB_AMPLITUDE * Math.sin(wrapTau((TAU * tSec) / BOB_PERIOD_S + keyPhase(key)))
}

export const SHAPES: readonly EoShape[] = [
  'rotary-small',
  'fpv-small',
  'fixed-wing-small',
  'fixed-wing-medium',
  'fixed-wing-large',
  'bird',
  'kite',
  'balloon',
  'point',
]

type Vec = readonly [number, number, number]

const Kind = { Fixed: 0, RotorSpin: 1, FlapRight: 2, FlapLeft: 3, PropSpin: 4 } as const
type Kind = (typeof Kind)[keyof typeof Kind]

interface PartStyle {
  heat: number
  kind?: Kind
  hub?: Vec
}

/** Accumulates non-indexed, flat-shaded triangles with their animation and heat attributes. */
class ModelBuilder {
  private readonly position: number[] = []
  private readonly normal: number[] = []
  private readonly part: number[] = []
  private readonly heat: number[] = []

  triangles(): number {
    return this.position.length / 9
  }

  private tri(a: Vec, b: Vec, c: Vec, style: PartStyle, hubFallback: Vec): void {
    const ux = b[0] - a[0]
    const uy = b[1] - a[1]
    const uz = b[2] - a[2]
    const vx = c[0] - a[0]
    const vy = c[1] - a[1]
    const vz = c[2] - a[2]
    let nx = uy * vz - uz * vy
    let ny = uz * vx - ux * vz
    let nz = ux * vy - uy * vx
    const len = Math.hypot(nx, ny, nz) || 1
    nx /= len
    ny /= len
    nz /= len
    const hub = style.hub ?? hubFallback
    for (const p of [a, b, c]) {
      this.position.push(p[0], p[1], p[2])
      this.normal.push(nx, ny, nz)
      this.part.push(hub[0], hub[1], hub[2], style.kind ?? Kind.Fixed)
      this.heat.push(style.heat)
    }
  }

  /** A triangle wound so that its normal points away from `centre`. */
  outward(a: Vec, b: Vec, c: Vec, centre: Vec, style: PartStyle, hubFallback: Vec): void {
    const ux = b[0] - a[0]
    const uy = b[1] - a[1]
    const uz = b[2] - a[2]
    const vx = c[0] - a[0]
    const vy = c[1] - a[1]
    const vz = c[2] - a[2]
    const nx = uy * vz - uz * vy
    const ny = uz * vx - ux * vz
    const nz = ux * vy - uy * vx
    const mx = (a[0] + b[0] + c[0]) / 3 - centre[0]
    const my = (a[1] + b[1] + c[1]) / 3 - centre[1]
    const mz = (a[2] + b[2] + c[2]) / 3 - centre[2]
    if (nx * mx + ny * my + nz * mz >= 0) this.tri(a, b, c, style, hubFallback)
    else this.tri(a, c, b, style, hubFallback)
  }

  /** An axis-aligned box turned about Y by `ry` about its own centre: 12 triangles. */
  box(w: number, h: number, d: number, at: Vec, style: PartStyle, ry = 0): this {
    const c = Math.cos(ry)
    const s = Math.sin(ry)
    const corner = (sx: number, sy: number, sz: number): Vec => {
      const x = (sx * w) / 2
      const z = (sz * d) / 2
      return [at[0] + c * x + s * z, at[1] + (sy * h) / 2, at[2] - s * x + c * z]
    }
    const v = [
      corner(-1, -1, -1),
      corner(1, -1, -1),
      corner(1, 1, -1),
      corner(-1, 1, -1),
      corner(-1, -1, 1),
      corner(1, -1, 1),
      corner(1, 1, 1),
      corner(-1, 1, 1),
    ] as const
    const faces: readonly (readonly [number, number, number, number])[] = [
      [0, 1, 2, 3],
      [4, 5, 6, 7],
      [0, 1, 5, 4],
      [3, 2, 6, 7],
      [0, 3, 7, 4],
      [1, 2, 6, 5],
    ]
    for (const [i, j, k, l] of faces) {
      const [a, b, c, d] = [i, j, k, l].map((n): Vec => v[n] ?? at) as [Vec, Vec, Vec, Vec]
      this.outward(a, b, c, at, style, at)
      this.outward(a, c, d, at, style, at)
    }
    return this
  }

  /** A flat bar in the XZ plane, visible from both sides: 4 triangles. Used for blades. */
  bar(length: number, width: number, at: Vec, style: PartStyle, ry = 0): this {
    const c = Math.cos(ry)
    const s = Math.sin(ry)
    const p = (x: number, z: number): Vec => [at[0] + c * x + s * z, at[1], at[2] - s * x + c * z]
    const a = p(-length / 2, -width / 2)
    const b = p(length / 2, -width / 2)
    const cc = p(length / 2, width / 2)
    const d = p(-length / 2, width / 2)
    this.tri(a, b, cc, style, at)
    this.tri(a, cc, d, style, at)
    this.tri(a, cc, b, style, at)
    this.tri(a, d, cc, style, at)
    return this
  }

  /** A flat triangle fan in the XY plane, visible from both sides. */
  flatQuad(a: Vec, b: Vec, c: Vec, d: Vec, style: PartStyle): this {
    const at: Vec = [(a[0] + c[0]) / 2, (a[1] + c[1]) / 2, (a[2] + c[2]) / 2]
    this.tri(a, b, c, style, at)
    this.tri(a, c, d, style, at)
    this.tri(a, c, b, style, at)
    this.tri(a, d, c, style, at)
    return this
  }

  /** An ellipsoid from a coarse sphere, with its poles on the Y axis. */
  ellipsoid(rx: number, ry: number, rz: number, at: Vec, style: PartStyle): this {
    const sphere = new THREE.SphereGeometry(1, 8, 6).toNonIndexed()
    const pos = sphere.getAttribute('position')
    const p = (i: number): Vec => [
      at[0] + pos.getX(i) * rx,
      at[1] + pos.getY(i) * ry,
      at[2] + pos.getZ(i) * rz,
    ]
    for (let i = 0; i < pos.count; i += 3) this.outward(p(i), p(i + 1), p(i + 2), at, style, at)
    sphere.dispose()
    return this
  }

  build(): THREE.BufferGeometry {
    const g = new THREE.BufferGeometry()
    g.setAttribute('position', new THREE.Float32BufferAttribute(this.position, 3))
    g.setAttribute('normal', new THREE.Float32BufferAttribute(this.normal, 3))
    g.setAttribute('aPart', new THREE.Float32BufferAttribute(this.part, 4))
    g.setAttribute('aHeat', new THREE.Float32BufferAttribute(this.heat, 1))
    return g
  }
}

const FRAME = 0.45
const BODY = 0.8
const HOT = 1

/** A rotor: two crossed blades spinning about the hub's vertical axis. 8 triangles. */
function rotor(m: ModelBuilder, x: number, y: number, z: number, length: number): void {
  const style = { heat: HOT, kind: Kind.RotorSpin, hub: [x, y, z] as Vec }
  m.bar(length, 0.03, [x, y, z], style, 0)
  m.bar(length, 0.03, [x, y, z], style, Math.PI / 2)
}

function propeller(m: ModelBuilder, z: number, length: number): void {
  const style = { heat: 0.8, kind: Kind.PropSpin, hub: [0, 0, z] as Vec }
  // A flat blade in the XY plane, spun about Z.
  m.flatQuad(
    [0, -length / 2, z],
    [0.025, -length / 2, z],
    [0.025, length / 2, z],
    [0, length / 2, z],
    style,
  )
}

function buildModel(shape: EoShape): ModelBuilder {
  const m = new ModelBuilder()
  switch (shape) {
    case 'rotary-small': {
      m.box(0.22, 0.1, 0.22, [0, 0, 0], { heat: BODY })
      m.box(0.95, 0.035, 0.05, [0, 0, 0], { heat: FRAME }, Math.PI / 4)
      m.box(0.95, 0.035, 0.05, [0, 0, 0], { heat: FRAME }, -Math.PI / 4)
      for (const [x, z] of [
        [0.34, 0.34],
        [-0.34, 0.34],
        [0.34, -0.34],
        [-0.34, -0.34],
      ] as const)
        rotor(m, x, 0.05, z, 0.34)
      break
    }
    case 'fpv-small': {
      // A compact racing frame: elongated body with a battery slab, short thick arms, small props.
      m.box(0.15, 0.1, 0.36, [0, 0, 0], { heat: BODY })
      m.box(0.11, 0.05, 0.22, [0, 0.075, -0.02], { heat: 0.9 })
      m.box(0.78, 0.045, 0.06, [0, 0, 0], { heat: FRAME }, Math.PI / 4.6)
      m.box(0.78, 0.045, 0.06, [0, 0, 0], { heat: FRAME }, -Math.PI / 4.6)
      for (const [x, z] of [
        [0.28, 0.3],
        [-0.28, 0.3],
        [0.28, -0.3],
        [-0.28, -0.3],
      ] as const)
        rotor(m, x, 0.04, z, 0.26)
      break
    }
    case 'fixed-wing-small': {
      m.box(0.09, 0.09, 0.78, [0, 0, 0], { heat: 0.9 })
      m.box(1, 0.025, 0.16, [0, 0.01, 0.05], { heat: 0.4 })
      m.box(0.34, 0.025, 0.1, [0, 0.02, -0.34], { heat: 0.4 })
      m.box(0.025, 0.14, 0.1, [0, 0.07, -0.34], { heat: 0.4 })
      propeller(m, 0.4, 0.24)
      break
    }
    case 'fixed-wing-medium': {
      // Longer fuselage and a larger span than the small class.
      m.box(0.1, 0.1, 1.05, [0, 0, 0], { heat: 0.95 })
      m.box(1.3, 0.03, 0.2, [0, 0.02, 0.06], { heat: 0.4 })
      m.box(0.46, 0.03, 0.12, [0, 0.03, -0.46], { heat: 0.4 })
      m.box(0.03, 0.18, 0.12, [0, 0.1, -0.46], { heat: 0.4 })
      propeller(m, 0.54, 0.3)
      break
    }
    case 'fixed-wing-large': {
      // The largest silhouette: a central pod, a wide wing and twin booms joined by a tailplane.
      m.box(0.13, 0.13, 0.5, [0, 0, 0.05], { heat: 1 })
      m.box(1.55, 0.035, 0.24, [0, 0.04, 0.05], { heat: 0.4 })
      for (const side of [-1, 1] as const) {
        m.box(0.045, 0.045, 0.85, [side * 0.34, 0.04, -0.28], { heat: 0.5 })
        m.box(0.03, 0.18, 0.12, [side * 0.34, 0.12, -0.66], { heat: 0.4 })
      }
      m.box(0.78, 0.03, 0.12, [0, 0.2, -0.66], { heat: 0.4 })
      propeller(m, 0.32, 0.32)
      break
    }
    case 'bird': {
      m.box(0.16, 0.1, 0.34, [0, 0, 0], { heat: 0.6 })
      m.box(0.5, 0.02, 0.2, [0.31, 0.02, 0], {
        heat: 0.5,
        kind: Kind.FlapRight,
        hub: [0.06, 0.02, 0],
      })
      m.box(0.5, 0.02, 0.2, [-0.31, 0.02, 0], {
        heat: 0.5,
        kind: Kind.FlapLeft,
        hub: [-0.06, 0.02, 0],
      })
      break
    }
    case 'kite': {
      // A diamond of cloth and a faint tether line below it; no body.
      m.flatQuad([0, 0.5, 0], [0.34, 0.12, 0], [0, -0.5, 0], [-0.34, 0.12, 0], { heat: 0.12 })
      m.flatQuad([-0.008, -0.5, 0], [0.008, -0.5, 0], [0.1, -1.5, 0], [0.084, -1.5, 0], {
        heat: 0.06,
      })
      break
    }
    case 'balloon': {
      m.ellipsoid(0.4, 0.5, 0.4, [0, 0, 0], { heat: 0.15 })
      break
    }
    case 'point': {
      const ico = new THREE.IcosahedronGeometry(0.4, 0)
      const pos = ico.getAttribute('position')
      const p = (i: number): Vec => [pos.getX(i), pos.getY(i), pos.getZ(i)]
      for (let i = 0; i < pos.count; i += 3)
        m.outward(p(i), p(i + 1), p(i + 2), [0, 0, 0], { heat: HOT }, [0, 0, 0])
      ico.dispose()
      break
    }
  }
  return m
}

/** Build the merged geometry of one shape. Called once per shape per scene. */
export function buildShapeGeometry(shape: EoShape): THREE.BufferGeometry {
  return buildModel(shape).build()
}

/** Triangles in one instance of a shape. */
export function shapeTriangles(shape: EoShape): number {
  return buildModel(shape).triangles()
}

/**
 * Patch the shared target material (a flat-shaded Lambert) to read the three attributes above:
 * rotate animated vertices about their hub, and scale the thermal emission by vertex heat.
 */
export function patchTargetMaterial(material: THREE.Material): void {
  material.onBeforeCompile = (shader) => {
    shader.vertexShader =
      'attribute vec4 aPart;\nattribute float aHeat;\nattribute float aAngle;\nvarying float vHeat;\n' +
      shader.vertexShader.replace(
        '#include <begin_vertex>',
        /* glsl */ `
#include <begin_vertex>
vHeat = aHeat;
{
  float kind = aPart.w;
  if ( kind > 0.5 ) {
    vec3 q = transformed - aPart.xyz;
    float a = ( kind > 2.5 && kind < 3.5 ) ? - aAngle : aAngle;
    float ca = cos( a );
    float sa = sin( a );
    if ( kind < 1.5 ) q = vec3( ca * q.x + sa * q.z, q.y, - sa * q.x + ca * q.z );
    else q = vec3( ca * q.x - sa * q.y, sa * q.x + ca * q.y, q.z );
    transformed = q + aPart.xyz;
  }
}
`,
      )
    shader.fragmentShader =
      'varying float vHeat;\n' +
      shader.fragmentShader.replace(
        '#include <emissivemap_fragment>',
        '#include <emissivemap_fragment>\ntotalEmissiveRadiance *= vHeat;',
      )
  }
  material.customProgramCacheKey = () => 'eo-target'
}

interface Slot {
  shape: EoShape
  mesh: THREE.InstancedMesh
  angle: THREE.InstancedBufferAttribute
  triangles: number
}

/**
 * One InstancedMesh per shape, created once. A frame is `begin()`, then `place()` for each report,
 * then `end()`; nothing is created or disposed in between.
 */
export class TargetField {
  private readonly slots = new Map<EoShape, Slot>()
  private readonly geometries: THREE.BufferGeometry[] = []

  constructor(
    parent: THREE.Object3D,
    material: THREE.Material,
    private readonly capacity = TARGET_CAPACITY,
  ) {
    for (const shape of SHAPES) {
      const geometry = buildShapeGeometry(shape)
      const angle = new THREE.InstancedBufferAttribute(new Float32Array(capacity), 1)
      angle.setUsage(THREE.DynamicDrawUsage)
      geometry.setAttribute('aAngle', angle)
      const mesh = new THREE.InstancedMesh(geometry, material, capacity)
      mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage)
      mesh.count = 0
      mesh.visible = false
      mesh.frustumCulled = false
      mesh.renderOrder = 10
      parent.add(mesh)
      this.geometries.push(geometry)
      this.slots.set(shape, {
        shape,
        mesh,
        angle,
        triangles: geometry.getAttribute('position').count / 3,
      })
    }
  }

  /** Start a frame: every shape is empty until reports are placed. */
  begin(): void {
    for (const slot of this.slots.values()) slot.mesh.count = 0
  }

  /**
   * Draw one contact. `pose` carries the position, rotation and scale (its matrix is updated here).
   * Returns false when the shape's capacity is full and the contact is not drawn.
   */
  place(shape: EoShape, key: number, pose: THREE.Object3D, tSec: number): boolean {
    const slot = this.slots.get(shape)
    if (!slot) return false
    const i = slot.mesh.count
    if (i >= this.capacity) return false
    pose.updateMatrix()
    slot.mesh.setMatrixAt(i, pose.matrix)
    slot.angle.setX(i, shape === 'bird' ? flapAngle(key, tSec) : rotorAngle(key, tSec))
    slot.mesh.count = i + 1
    return true
  }

  /** Finish a frame: upload what changed and hide empty shapes. */
  end(): void {
    for (const slot of this.slots.values()) {
      const n = slot.mesh.count
      slot.mesh.visible = n > 0
      if (n === 0) continue
      slot.mesh.instanceMatrix.clearUpdateRanges()
      slot.mesh.instanceMatrix.addUpdateRange(0, n * 16)
      slot.mesh.instanceMatrix.needsUpdate = true
      slot.angle.clearUpdateRanges()
      slot.angle.addUpdateRange(0, n)
      slot.angle.needsUpdate = true
    }
  }

  /** Contacts drawn this frame. */
  drawn(shape?: EoShape): number {
    if (shape) return this.slots.get(shape)?.mesh.count ?? 0
    let n = 0
    for (const slot of this.slots.values()) n += slot.mesh.count
    return n
  }

  /** The shapes drawn this frame, comma separated in a fixed order ("" when none). */
  shapesDrawn(): string {
    let out = ''
    for (const slot of this.slots.values())
      if (slot.mesh.count > 0) out += (out ? ',' : '') + slot.shape
    return out
  }

  /** Triangles submitted for contacts this frame. */
  triangles(): number {
    let n = 0
    for (const slot of this.slots.values()) n += slot.mesh.count * slot.triangles
    return n
  }

  /** The instanced mesh of a shape, for tests. */
  meshOf(shape: EoShape): THREE.InstancedMesh | undefined {
    return this.slots.get(shape)?.mesh
  }

  dispose(parent: THREE.Object3D): void {
    for (const slot of this.slots.values()) {
      parent.remove(slot.mesh)
      slot.mesh.dispose()
    }
    for (const g of this.geometries) g.dispose()
    this.geometries.length = 0
    this.slots.clear()
  }
}
