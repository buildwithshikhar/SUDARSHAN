/**
 * Geometry for a terrain pack, built in three.js axes (three = (x, z, -y), docs/TERRAIN_PACKS.md).
 * The pack's own GLB meshes are used when they download and parse; the builders here make the same
 * things from `heights.i16`, `buildings.json` and `vegetation.json` when they do not, so a pack
 * with a missing or broken mesh still draws.
 */
import * as THREE from 'three'
import { mergeGeometries } from 'three/examples/jsm/utils/BufferGeometryUtils.js'
import { heightAt } from '../terrain/heightAt'
import type { TerrainPack } from '../terrain/types'

// ---------------------------------------------------------------------- terrain

/** Linear-space ground colour from height above the local range and slope (0 flat, 1 steep). */
export function groundColour(
  height01: number,
  slope: number,
  out: [number, number, number] = [0, 0, 0],
): [number, number, number] {
  const rock = Math.min(1, Math.max(0, (slope - 0.18) / 0.35))
  const high = Math.min(1, Math.max(0, height01))
  const r = 0.13 + 0.07 * high
  const g = 0.17 + 0.05 * high
  const b = 0.07 + 0.05 * high
  out[0] = r + (0.27 - r) * rock
  out[1] = g + (0.25 - g) * rock
  out[2] = b + (0.22 - b) * rock
  return out
}

/** The heightmap as a mesh: one vertex per heightmap sample, vertex-coloured by height and slope. */
export function terrainGeometry(pack: TerrainPack): THREE.BufferGeometry {
  const n = pack.size
  const half = pack.halfExtentM
  const cell = (2 * half) / (n - 1)
  const positions = new Float32Array(n * n * 3)
  const colours = new Float32Array(n * n * 3)
  const span = Math.max(1, pack.maxM - pack.minM)
  const rgb: [number, number, number] = [0, 0, 0]
  for (let j = 0; j < n; j++) {
    for (let i = 0; i < n; i++) {
      const x = -half + i * cell
      const y = -half + j * cell
      const h = (pack.heights[j * n + i] ?? 0) * pack.scaleM
      const k = (j * n + i) * 3
      positions[k] = x
      positions[k + 1] = h
      positions[k + 2] = -y
      const dx = (heightAt(pack, x + cell, y) - heightAt(pack, x - cell, y)) / (2 * cell)
      const dy = (heightAt(pack, x, y + cell) - heightAt(pack, x, y - cell)) / (2 * cell)
      groundColour((h - pack.minM) / span, Math.hypot(dx, dy), rgb)
      colours.set(rgb, k)
    }
  }
  const indices = new Uint32Array((n - 1) * (n - 1) * 6)
  let w = 0
  for (let j = 0; j < n - 1; j++) {
    for (let i = 0; i < n - 1; i++) {
      const a = j * n + i
      const b = a + 1
      const c = a + n
      const d = c + 1
      indices[w++] = a
      indices[w++] = b
      indices[w++] = c
      indices[w++] = b
      indices[w++] = d
      indices[w++] = c
    }
  }
  const g = new THREE.BufferGeometry()
  g.setAttribute('position', new THREE.BufferAttribute(positions, 3))
  g.setAttribute('color', new THREE.BufferAttribute(colours, 3))
  g.setIndex(new THREE.BufferAttribute(indices, 1))
  g.computeVertexNormals()
  return g
}

/** Mean height of the pack's outer ring of samples, in metres above the datum. */
export function edgeMeanHeight(pack: TerrainPack): number {
  const n = pack.size
  let sum = 0
  let count = 0
  for (let k = 0; k < n; k++) {
    for (const idx of [k, (n - 1) * n + k, k * n, k * n + n - 1]) {
      sum += (pack.heights[idx] ?? 0) * pack.scaleM
      count++
    }
  }
  return sum / Math.max(1, count)
}

/**
 * A skirt that carries the pack's edge height out to the surrounding flat ground over `widthM`,
 * so the square of terrain does not end in a cliff.
 */
export function apronGeometry(pack: TerrainPack, widthM: number): THREE.BufferGeometry {
  const n = pack.size
  const half = pack.halfExtentM
  const cell = (2 * half) / (n - 1)
  const outerH = edgeMeanHeight(pack)
  // boundary samples in order round the square
  const ring: [number, number][] = []
  for (let i = 0; i < n; i++) ring.push([i, 0])
  for (let j = 1; j < n; j++) ring.push([n - 1, j])
  for (let i = n - 2; i >= 0; i--) ring.push([i, n - 1])
  for (let j = n - 2; j >= 1; j--) ring.push([0, j])
  const positions = new Float32Array(ring.length * 2 * 3)
  const colours = new Float32Array(ring.length * 2 * 3)
  const rgb: [number, number, number] = [0, 0, 0]
  const span = Math.max(1, pack.maxM - pack.minM)
  ring.forEach(([i, j], r) => {
    const x = -half + i * cell
    const y = -half + j * cell
    const h = (pack.heights[j * n + i] ?? 0) * pack.scaleM
    const ox = i === 0 ? -1 : i === n - 1 ? 1 : 0
    const oy = j === 0 ? -1 : j === n - 1 ? 1 : 0
    const len = Math.hypot(ox, oy) || 1
    const inner = r * 2
    const outer = inner + 1
    positions.set([x, h, -y], inner * 3)
    positions.set([x + (ox / len) * widthM, outerH, -(y + (oy / len) * widthM)], outer * 3)
    groundColour((h - pack.minM) / span, 0, rgb)
    colours.set(rgb, inner * 3)
    colours.set(rgb, outer * 3)
  })
  const indices: number[] = []
  const m = ring.length
  for (let r = 0; r < m; r++) {
    const a = r * 2
    const b = a + 1
    const c = ((r + 1) % m) * 2
    const d = c + 1
    indices.push(a, c, b, c, d, b)
  }
  const g = new THREE.BufferGeometry()
  g.setAttribute('position', new THREE.BufferAttribute(positions, 3))
  g.setAttribute('color', new THREE.BufferAttribute(colours, 3))
  g.setIndex(indices)
  g.computeVertexNormals()
  // the ring is wound one way; make every normal point up whichever way it came out
  const normal = g.getAttribute('normal')
  for (let i = 0; i < normal.count; i++) {
    if (normal.getY(i) < 0) normal.setXYZ(i, -normal.getX(i), -normal.getY(i), -normal.getZ(i))
  }
  return g
}

// ---------------------------------------------------------------------- buildings

function pushTriangle(
  out: number[],
  normals: number[],
  a: THREE.Vector3,
  b: THREE.Vector3,
  c: THREE.Vector3,
  want: THREE.Vector3,
): void {
  const ab = new THREE.Vector3().subVectors(b, a)
  const ac = new THREE.Vector3().subVectors(c, a)
  const n = new THREE.Vector3().crossVectors(ab, ac)
  const flip = n.dot(want) < 0
  const order = flip ? [a, c, b] : [a, b, c]
  for (const v of order) {
    out.push(v.x, v.y, v.z)
    normals.push(want.x, want.y, want.z)
  }
}

export interface BuildingMeshes {
  /** Positions and normals for walls (group 0) and roofs (group 1). */
  geometry: THREE.BufferGeometry
}

/** Extruded footprints as one geometry: walls in group 0, roofs in group 1. */
export function buildingsGeometry(pack: TerrainPack): THREE.BufferGeometry | null {
  const wallPos: number[] = []
  const wallNor: number[] = []
  const roofPos: number[] = []
  const roofNor: number[] = []
  const up = new THREE.Vector3(0, 1, 0)
  for (const b of pack.buildings) {
    const ring = b.footprint
    const bottom = b.base_m
    const top = b.base_m + b.height_m
    for (let i = 0; i < ring.length; i++) {
      const p = ring[i]
      const q = ring[(i + 1) % ring.length]
      if (!p || !q) continue
      // the footprint is counter-clockwise, so the outside is to the right of the edge
      const out = new THREE.Vector3(q[1] - p[1], 0, q[0] - p[0]).normalize()
      const p0 = new THREE.Vector3(p[0], bottom, -p[1])
      const q0 = new THREE.Vector3(q[0], bottom, -q[1])
      const p1 = new THREE.Vector3(p[0], top, -p[1])
      const q1 = new THREE.Vector3(q[0], top, -q[1])
      pushTriangle(wallPos, wallNor, p0, q0, q1, out)
      pushTriangle(wallPos, wallNor, p0, q1, p1, out)
    }
    const contour = ring.map(([x, y]) => new THREE.Vector2(x, y))
    for (const [i, j, k] of THREE.ShapeUtils.triangulateShape(contour, [])) {
      const v = (idx: number | undefined) => {
        const c = contour[idx ?? 0] ?? new THREE.Vector2()
        return new THREE.Vector3(c.x, top, -c.y)
      }
      pushTriangle(roofPos, roofNor, v(i), v(j), v(k), up)
    }
  }
  if (wallPos.length === 0) return null
  const g = new THREE.BufferGeometry()
  g.setAttribute('position', new THREE.Float32BufferAttribute([...wallPos, ...roofPos], 3))
  g.setAttribute('normal', new THREE.Float32BufferAttribute([...wallNor, ...roofNor], 3))
  g.addGroup(0, wallPos.length / 3, 0)
  g.addGroup(wallPos.length / 3, roofPos.length / 3, 1)
  return g
}

// ---------------------------------------------------------------------- trees

/** One low-poly conifer of unit height: trunk and two cones, vertex-coloured. */
export function treeGeometry(): THREE.BufferGeometry {
  const parts: THREE.BufferGeometry[] = []
  const part = (g: THREE.BufferGeometry, y: number, r: number, gr: number, b: number) => {
    g.translate(0, y, 0)
    const count = g.getAttribute('position').count
    const colours = new Float32Array(count * 3)
    for (let i = 0; i < count; i++) colours.set([r, gr, b], i * 3)
    g.setAttribute('color', new THREE.BufferAttribute(colours, 3))
    g.deleteAttribute('uv')
    parts.push(g)
  }
  part(new THREE.CylinderGeometry(0.035, 0.05, 0.3, 5), 0.15, 0.1, 0.06, 0.03)
  part(new THREE.ConeGeometry(0.34, 0.6, 7), 0.5, 0.045, 0.1, 0.04)
  part(new THREE.ConeGeometry(0.26, 0.48, 7), 0.82, 0.055, 0.12, 0.05)
  const merged = mergeGeometries(parts, false)
  parts.forEach((p) => p.dispose())
  if (!merged) throw new Error('tree geometry could not be merged')
  return merged
}

/** A fixed shuffle of 0..count-1, so the first N of it is a uniform thinning of the trees. */
export function shuffledOrder(count: number, seed = 20261018): Uint32Array {
  const order = new Uint32Array(count)
  for (let i = 0; i < count; i++) order[i] = i
  let s = seed % 2147483647 || 1
  for (let i = count - 1; i > 0; i--) {
    s = (s * 16807) % 2147483647
    const j = s % (i + 1)
    const t = order[i] ?? 0
    order[i] = order[j] ?? 0
    order[j] = t
  }
  return order
}

/** Fill the instance matrices (and a little colour variation) for the trees, in shuffled order. */
export function fillTrees(mesh: THREE.InstancedMesh, pack: TerrainPack, order: Uint32Array): void {
  const m = new THREE.Matrix4()
  const pos = new THREE.Vector3()
  const scale = new THREE.Vector3()
  const quat = new THREE.Quaternion()
  const colour = new THREE.Color()
  for (let k = 0; k < order.length; k++) {
    const t = (order[k] ?? 0) * 3
    const x = pack.trees[t] ?? 0
    const y = pack.trees[t + 1] ?? 0
    const h = pack.trees[t + 2] ?? 8
    // a stable per-tree variation from its position, so the stand is not uniform
    const v = Math.abs(Math.sin(x * 12.9898 + y * 78.233) * 43758.5453) % 1
    const height = h * (0.88 + 0.24 * v)
    pos.set(x, heightAt(pack, x, y) - 0.1, -y)
    scale.set(height * 0.7, height, height * 0.7)
    m.compose(pos, quat, scale)
    mesh.setMatrixAt(k, m)
    const shade = 0.88 + 0.24 * ((v * 7.31) % 1)
    mesh.setColorAt(k, colour.setRGB(shade, shade * (0.92 + 0.16 * v), shade * 0.95))
  }
  mesh.instanceMatrix.needsUpdate = true
  if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true
}
