// Writes the tiny hand-made terrain pack used by the unit tests and the mock e2e.
// Usage: node tests/fixtures/terrain/make-fixture.mjs   (from apps/web)
//
// It follows docs/TERRAIN_PACKS.md at a toy scale: a 9 x 9 heightmap over an 800 m square, three
// buildings and sixty trees, a terrain mesh and a buildings mesh as GLB. Generic and fictional;
// it is not a bake of any real place. Output is deterministic.
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { createHash } from 'node:crypto'
import { resolve } from 'node:path'

const ID = 'fixture-ridge'
const out = resolve(import.meta.dirname, ID)
mkdirSync(out, { recursive: true })

const HALF = 400
const SIZE = 9
const CELL = (2 * HALF) / (SIZE - 1)
const SCALE = 0.1

// ---- heights: a low ridge to the north-west and a shallow bowl around the origin
const heights = new Int16Array(SIZE * SIZE)
const heightM = (x, y) =>
  14 * Math.exp(-(((x + 260) ** 2 + (y - 220) ** 2) / 150 ** 2)) +
  0.004 * (x * x + y * y) ** 0.5 * 2 -
  4
for (let j = 0; j < SIZE; j++) {
  for (let i = 0; i < SIZE; i++) {
    heights[j * SIZE + i] = Math.round(heightM(-HALF + i * CELL, -HALF + j * CELL) / SCALE)
  }
}
const bytes = Buffer.alloc(heights.length * 2)
heights.forEach((v, i) => bytes.writeInt16LE(v, i * 2))
writeFileSync(resolve(out, 'heights.i16'), bytes)
const hAt = (x, y) => {
  const u = (x + HALF) / CELL
  const v = (y + HALF) / CELL
  const i = Math.min(SIZE - 2, Math.max(0, Math.floor(u)))
  const j = Math.min(SIZE - 2, Math.max(0, Math.floor(v)))
  const fx = u - i
  const fy = v - j
  const g = (a, b) => heights[b * SIZE + a] * SCALE
  const s = g(i, j) + (g(i + 1, j) - g(i, j)) * fx
  const n = g(i, j + 1) + (g(i + 1, j + 1) - g(i, j + 1)) * fx
  return s + (n - s) * fy
}

// ---- buildings
const boxes = [
  { id: 'f001', x0: 60, y0: 40, x1: 100, y1: 64, h: 7.5 },
  { id: 'f002', x0: -150, y0: -90, x1: -118, y1: -70, h: 4.2 },
  { id: 'f003', x0: 150, y0: -160, x1: 190, y1: -118, h: 12 },
]
const buildings = boxes.map((b) => {
  const base = Math.min(
    ...[
      [b.x0, b.y0],
      [b.x1, b.y0],
      [b.x1, b.y1],
      [b.x0, b.y1],
    ].map(([x, y]) => hAt(x, y)),
  )
  return {
    id: b.id,
    footprint: [
      [b.x0, b.y0],
      [b.x1, b.y0],
      [b.x1, b.y1],
      [b.x0, b.y1],
    ],
    base_m: Math.round(base * 10) / 10,
    height_m: b.h,
    height_source: 'tag',
  }
})
writeFileSync(
  resolve(out, 'buildings.json'),
  JSON.stringify({ format: 'terrain-buildings.v1', buildings }, null, 1) + '\n',
)

// ---- trees (seeded scatter, sorted by (y, x))
let seed = 20261018
const rand = () => {
  seed = (seed * 16807) % 2147483647
  return seed / 2147483647
}
const trees = []
while (trees.length < 60) {
  const x = Math.round((rand() * 760 - 380) * 10) / 10
  const y = Math.round((rand() * 760 - 380) * 10) / 10
  if (Math.hypot(x, y) < 70) continue
  trees.push([x, y, Math.round((6 + rand() * 6) * 10) / 10])
}
trees.sort((a, b) => a[1] - b[1] || a[0] - b[0])
writeFileSync(
  resolve(out, 'vegetation.json'),
  JSON.stringify({ format: 'terrain-vegetation.v1', trees }) + '\n',
)

// ---- GLB writer: one mesh, N primitives, Y-up with three = (x, z, -y)
function glb(primitives) {
  const chunks = []
  const views = []
  const accessors = []
  const push = (array, target, type, componentType, count, minmax) => {
    const buf = Buffer.from(array.buffer, array.byteOffset, array.byteLength)
    const pad = (4 - (buf.length % 4)) % 4
    const offset = chunks.reduce((n, c) => n + c.length, 0)
    chunks.push(Buffer.concat([buf, Buffer.alloc(pad)]))
    views.push({ buffer: 0, byteOffset: offset, byteLength: buf.length, target })
    accessors.push({ bufferView: views.length - 1, componentType, count, type, ...minmax })
    return accessors.length - 1
  }
  const meshPrimitives = []
  const materials = []
  for (const p of primitives) {
    const min = [Infinity, Infinity, Infinity]
    const max = [-Infinity, -Infinity, -Infinity]
    for (let i = 0; i < p.positions.length; i += 3) {
      for (let k = 0; k < 3; k++) {
        min[k] = Math.min(min[k], p.positions[i + k])
        max[k] = Math.max(max[k], p.positions[i + k])
      }
    }
    const attributes = {
      POSITION: push(p.positions, 34962, 'VEC3', 5126, p.positions.length / 3, { min, max }),
      NORMAL: push(p.normals, 34962, 'VEC3', 5126, p.normals.length / 3, {}),
    }
    if (p.colors) attributes.COLOR_0 = push(p.colors, 34962, 'VEC3', 5126, p.colors.length / 3, {})
    const indices = push(p.indices, 34963, 'SCALAR', 5123, p.indices.length, {})
    materials.push({
      pbrMetallicRoughness: { baseColorFactor: p.color, metallicFactor: 0, roughnessFactor: 1 },
      doubleSided: true,
    })
    meshPrimitives.push({ attributes, indices, material: materials.length - 1 })
  }
  const bin = Buffer.concat(chunks)
  const json = Buffer.from(
    JSON.stringify({
      asset: { version: '2.0', generator: 'terrain fixture' },
      scene: 0,
      scenes: [{ nodes: [0] }],
      nodes: [{ mesh: 0 }],
      meshes: [{ primitives: meshPrimitives }],
      materials,
      buffers: [{ byteLength: bin.length }],
      bufferViews: views,
      accessors,
    }),
  )
  const jsonPad = Buffer.concat([json, Buffer.alloc((4 - (json.length % 4)) % 4, 0x20)])
  const total = 12 + 8 + jsonPad.length + 8 + bin.length
  const header = Buffer.alloc(12)
  header.writeUInt32LE(0x46546c67, 0)
  header.writeUInt32LE(2, 4)
  header.writeUInt32LE(total, 8)
  const chunkHead = (len, type) => {
    const b = Buffer.alloc(8)
    b.writeUInt32LE(len, 0)
    b.writeUInt32LE(type, 4)
    return b
  }
  return Buffer.concat([
    header,
    chunkHead(jsonPad.length, 0x4e4f534a),
    jsonPad,
    chunkHead(bin.length, 0x004e4942),
    bin,
  ])
}

// terrain mesh
{
  const positions = new Float32Array(SIZE * SIZE * 3)
  const normals = new Float32Array(SIZE * SIZE * 3)
  const colors = new Float32Array(SIZE * SIZE * 3)
  for (let j = 0; j < SIZE; j++) {
    for (let i = 0; i < SIZE; i++) {
      const x = -HALF + i * CELL
      const y = -HALF + j * CELL
      const h = heights[j * SIZE + i] * SCALE
      const k = (j * SIZE + i) * 3
      positions.set([x, h, -y], k)
      const dhx = (hAt(x + CELL, y) - hAt(x - CELL, y)) / (2 * CELL)
      const dhy = (hAt(x, y + CELL) - hAt(x, y - CELL)) / (2 * CELL)
      const len = Math.hypot(dhx, 1, dhy)
      normals.set([-dhx / len, 1 / len, dhy / len], k)
      const t = Math.min(1, Math.max(0, (h + 4) / 18))
      colors.set([0.2 + 0.18 * t, 0.26 + 0.1 * t, 0.12 + 0.08 * t], k)
    }
  }
  const indices = new Uint16Array((SIZE - 1) * (SIZE - 1) * 6)
  let n = 0
  for (let j = 0; j < SIZE - 1; j++) {
    for (let i = 0; i < SIZE - 1; i++) {
      const a = j * SIZE + i
      const b = a + 1
      const c = a + SIZE
      const d = c + 1
      indices.set([a, b, c, b, d, c], n)
      n += 6
    }
  }
  writeFileSync(
    resolve(out, 'terrain.glb'),
    glb([{ positions, normals, colors, indices, color: [1, 1, 1, 1] }]),
  )
}

// buildings mesh: walls and roofs as separate primitives
{
  const walls = { p: [], n: [], i: [] }
  const roofs = { p: [], n: [], i: [] }
  const quad = (target, corners, normal) => {
    const base = target.p.length / 3
    for (const [x, y, z] of corners) {
      target.p.push(x, z, -y)
      target.n.push(normal[0], normal[2], -normal[1])
    }
    target.i.push(base, base + 1, base + 2, base, base + 2, base + 3)
  }
  for (const b of buildings) {
    const [x0, y0] = b.footprint[0]
    const [x1] = b.footprint[1]
    const [, y1] = b.footprint[3]
    const z0 = b.base_m
    const z1 = b.base_m + b.height_m
    quad(
      walls,
      [
        [x0, y0, z0],
        [x1, y0, z0],
        [x1, y0, z1],
        [x0, y0, z1],
      ],
      [0, -1, 0],
    )
    quad(
      walls,
      [
        [x1, y0, z0],
        [x1, y1, z0],
        [x1, y1, z1],
        [x1, y0, z1],
      ],
      [1, 0, 0],
    )
    quad(
      walls,
      [
        [x1, y1, z0],
        [x0, y1, z0],
        [x0, y1, z1],
        [x1, y1, z1],
      ],
      [0, 1, 0],
    )
    quad(
      walls,
      [
        [x0, y1, z0],
        [x0, y0, z0],
        [x0, y0, z1],
        [x0, y1, z1],
      ],
      [-1, 0, 0],
    )
    quad(
      roofs,
      [
        [x0, y0, z1],
        [x1, y0, z1],
        [x1, y1, z1],
        [x0, y1, z1],
      ],
      [0, 0, 1],
    )
  }
  const prim = (t, color) => ({
    positions: new Float32Array(t.p),
    normals: new Float32Array(t.n),
    indices: new Uint16Array(t.i),
    color,
  })
  writeFileSync(
    resolve(out, 'buildings.glb'),
    glb([prim(walls, [0.55, 0.53, 0.5, 1]), prim(roofs, [0.34, 0.33, 0.33, 1])]),
  )
}

// ---- manifest
const sha = (file) =>
  createHash('sha256')
    .update(readFileSync(resolve(out, file)))
    .digest('hex')
const files = Object.fromEntries(
  ['heights.i16', 'buildings.json', 'vegetation.json', 'terrain.glb', 'buildings.glb'].map((f) => [
    f,
    sha(f),
  ]),
)
const hmin = Math.min(...heights) * SCALE
const hmax = Math.max(...heights) * SCALE
const manifest = {
  format: 'terrain-pack.v1',
  id: ID,
  version: '1.0.0',
  name: 'Fixture Ridge',
  kind: 'rural',
  label: 'reference data · test fixture',
  frame: { half_extent_m: HALF, datum_m: 100 },
  heightmap: {
    file: 'heights.i16',
    size: SIZE,
    cell_m: CELL,
    scale_m: SCALE,
    min_m: Math.round(hmin * 10) / 10,
    max_m: Math.round(hmax * 10) / 10,
  },
  buildings: { file: 'buildings.json', count: buildings.length },
  vegetation: { file: 'vegetation.json', count: trees.length },
  meshes: { terrain: 'terrain.glb', buildings: 'buildings.glb' },
  files,
}
writeFileSync(resolve(out, 'manifest.json'), JSON.stringify(manifest, null, 2) + '\n')
console.log(`wrote ${ID}: heights ${hmin.toFixed(1)}..${hmax.toFixed(1)} m`)
