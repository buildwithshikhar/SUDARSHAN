import * as THREE from 'three'
import { describe, expect, it, vi } from 'vitest'
import { shapeFor, type EoShape } from '../../src/live/views/eoHold'
import {
  BIRD_FLAP_HZ,
  FLAP_VISUAL_SCALE,
  SHAPES,
  TARGET_CAPACITY,
  TargetField,
  bobOffset,
  buildShapeGeometry,
  flapAngle,
  keyPhase,
  patchTargetMaterial,
  rotorAngle,
  shapeTriangles,
} from '../../src/live/views/eoMeshes'

describe('shape selection from the reported class', () => {
  it.each([
    ['rotary-small', 'rotary-small'],
    ['fixed-wing-small', 'fixed-wing-small'],
    ['bird', 'bird'],
    ['fpv-small', 'fpv-small'],
    ['fixed-wing-medium', 'fixed-wing-medium'],
    ['fixed-wing-large', 'fixed-wing-large'],
    ['kite', 'kite'],
    ['balloon', 'balloon'],
  ])('%s is drawn as %s', (reported, shape) => {
    expect(shapeFor(reported)).toBe(shape)
  })

  it('falls back to a point for no class, a coarse family, an unknown class and a truth id', () => {
    for (const reported of [null, '', 'unknown', 'rotary', 'autonomous-small', 'decoy-small', 'x'])
      expect(shapeFor(reported)).toBe('point')
  })

  it('has a model for every shape', () => {
    const named: EoShape[] = [
      'rotary-small',
      'fixed-wing-small',
      'bird',
      'fpv-small',
      'fixed-wing-medium',
      'fixed-wing-large',
      'kite',
      'balloon',
      'point',
    ]
    expect([...SHAPES].sort()).toEqual([...named].sort())
  })
})

describe('model geometry', () => {
  it.each(SHAPES)('%s has consistent attributes and unit normals', (shape) => {
    const g = buildShapeGeometry(shape)
    const n = g.getAttribute('position').count
    expect(n).toBeGreaterThan(0)
    expect(n % 3).toBe(0)
    expect(g.getAttribute('normal').count).toBe(n)
    expect(g.getAttribute('aPart').count).toBe(n)
    expect(g.getAttribute('aHeat').count).toBe(n)
    const normal = g.getAttribute('normal')
    for (let i = 0; i < n; i++)
      expect(Math.hypot(normal.getX(i), normal.getY(i), normal.getZ(i))).toBeCloseTo(1, 4)
    g.dispose()
  })

  it('keeps 64 contacts of any one shape under 6,000 triangles', () => {
    const counts = SHAPES.map((s) => shapeTriangles(s))
    expect(Math.max(...counts) * TARGET_CAPACITY).toBeLessThan(6000)
    expect(TARGET_CAPACITY).toBe(64)
  })

  it('makes the fixed-wing classes grow in span and the large one the widest', () => {
    const span = (shape: EoShape) => {
      const g = buildShapeGeometry(shape)
      g.computeBoundingBox()
      const size = g.boundingBox!.getSize(new THREE.Vector3())
      g.dispose()
      return size.x
    }
    expect(span('fixed-wing-small')).toBeLessThan(span('fixed-wing-medium'))
    expect(span('fixed-wing-medium')).toBeLessThan(span('fixed-wing-large'))
  })

  it('gives birds two flapping wings, drones spinning rotors and aircraft a propeller', () => {
    const kinds = (shape: EoShape) => {
      const g = buildShapeGeometry(shape)
      const part = g.getAttribute('aPart')
      const set = new Set<number>()
      for (let i = 0; i < part.count; i++) set.add(part.getW(i))
      g.dispose()
      return [...set].sort()
    }
    expect(kinds('bird')).toEqual([0, 2, 3])
    expect(kinds('rotary-small')).toEqual([0, 1])
    expect(kinds('fpv-small')).toEqual([0, 1])
    expect(kinds('fixed-wing-small')).toEqual([0, 4])
    expect(kinds('fixed-wing-large')).toEqual([0, 4])
    expect(kinds('kite')).toEqual([0])
    expect(kinds('balloon')).toEqual([0])
  })

  it('draws kites and balloons cold, rotors and engines warm', () => {
    const heat = (shape: EoShape, kind?: number) => {
      const g = buildShapeGeometry(shape)
      const h = g.getAttribute('aHeat')
      const part = g.getAttribute('aPart')
      const values: number[] = []
      for (let i = 0; i < h.count; i++)
        if (kind === undefined || part.getW(i) === kind) values.push(h.getX(i))
      g.dispose()
      return values
    }
    for (const shape of ['kite', 'balloon'] as const)
      expect(Math.max(...heat(shape))).toBeLessThanOrEqual(0.2)
    for (const shape of ['rotary-small', 'fpv-small'] as const) {
      expect(Math.min(...heat(shape, 1))).toBe(1)
      expect(Math.min(...heat(shape, 1))).toBeGreaterThan(Math.min(...heat(shape, 0)))
    }
    for (const shape of ['fixed-wing-small', 'fixed-wing-medium', 'fixed-wing-large'] as const)
      expect(Math.max(...heat(shape, 0))).toBeGreaterThanOrEqual(0.89)
  })
})

describe('animation phase functions', () => {
  it('is deterministic in the key and time', () => {
    expect(flapAngle(7, 1.234)).toBe(flapAngle(7, 1.234))
    expect(rotorAngle(7, 1.234)).toBe(rotorAngle(7, 1.234))
    expect(bobOffset(7, 1.234)).toBe(bobOffset(7, 1.234))
    expect(keyPhase(7)).toBe(keyPhase(7))
  })

  it('gives different contacts different phases', () => {
    const phases = new Set([1, 2, 3, 4, 5, 6, 7, 8].map((k) => keyPhase(k).toFixed(4)))
    expect(phases.size).toBe(8)
    expect(flapAngle(1, 0.3)).not.toBeCloseTo(flapAngle(2, 0.3), 3)
  })

  it('beats at 12 Hz scaled down, between wing-down and wing-up limits', () => {
    const hz = BIRD_FLAP_HZ * FLAP_VISUAL_SCALE
    expect(hz).toBeCloseTo(3)
    const period = 1 / hz
    for (const t of [0, 0.11, 0.5, 2.7])
      expect(flapAngle(5, t + period)).toBeCloseTo(flapAngle(5, t), 6)
    let lo = Infinity
    let hi = -Infinity
    for (let t = 0; t < period; t += period / 200) {
      lo = Math.min(lo, flapAngle(5, t))
      hi = Math.max(hi, flapAngle(5, t))
    }
    expect(lo).toBeGreaterThanOrEqual(-0.35 - 1e-9)
    expect(lo).toBeLessThan(-0.33)
    expect(hi).toBeLessThanOrEqual(0.8 + 1e-9)
    expect(hi).toBeGreaterThan(0.79)
  })

  it('keeps the rotor angle wrapped and the balloon bob small and slow', () => {
    for (let t = 0; t < 50; t += 0.37) {
      const a = rotorAngle(3, t)
      expect(a).toBeGreaterThanOrEqual(0)
      expect(a).toBeLessThan(Math.PI * 2)
      expect(Math.abs(bobOffset(3, t))).toBeLessThanOrEqual(0.06 + 1e-9)
    }
    expect(Math.abs(bobOffset(3, 0.05) - bobOffset(3, 0))).toBeLessThan(0.01)
  })
})

describe('TargetField', () => {
  const material = new THREE.MeshLambertMaterial()
  const pose = new THREE.Object3D()
  const frame = (field: TargetField, reports: [EoShape, number][], t = 0) => {
    field.begin()
    let drawn = 0
    for (const [shape, key] of reports) if (field.place(shape, key, pose, t)) drawn++
    field.end()
    return drawn
  }

  it('makes one instanced mesh per shape, hidden until used, never frustum culled', () => {
    const scene = new THREE.Scene()
    const field = new TargetField(scene, material)
    expect(scene.children).toHaveLength(SHAPES.length)
    for (const child of scene.children) {
      expect(child).toBeInstanceOf(THREE.InstancedMesh)
      expect(child.visible).toBe(false)
      expect(child.frustumCulled).toBe(false)
    }
    frame(field, [['kite', 1]])
    expect(field.meshOf('kite')!.visible).toBe(true)
    expect(field.meshOf('bird')!.visible).toBe(false)
    expect(field.shapesDrawn()).toBe('kite')
    field.dispose(scene)
  })

  it('caps each shape at its capacity and counts what it draws', () => {
    const scene = new THREE.Scene()
    const field = new TargetField(scene, material)
    const many: [EoShape, number][] = Array.from({ length: 70 }, (_, i) => ['bird', i + 1])
    expect(frame(field, many)).toBe(TARGET_CAPACITY)
    expect(field.drawn('bird')).toBe(TARGET_CAPACITY)
    expect(field.triangles()).toBe(TARGET_CAPACITY * shapeTriangles('bird'))
    expect(
      frame(field, [
        ['balloon', 1],
        ['bird', 2],
      ]),
    ).toBe(2)
    expect(field.drawn()).toBe(2)
    field.dispose(scene)
  })

  it('reuses its geometry, buffers and meshes across frames: nothing is created or disposed', () => {
    const scene = new THREE.Scene()
    const field = new TargetField(scene, material)
    const ids = () =>
      scene.children.map((c) => {
        const m = c as THREE.InstancedMesh
        return [m, m.geometry, m.instanceMatrix, m.geometry.getAttribute('aAngle')]
      })
    const before = ids()
    const disposed = vi.spyOn(THREE.BufferGeometry.prototype, 'dispose')
    const shapes: EoShape[] = ['bird', 'rotary-small', 'kite', 'balloon', 'fpv-small', 'point']
    for (let f = 0; f < 200; f++)
      frame(
        field,
        shapes.map((s, i): [EoShape, number] => [s, i + 1 + (f % 3)]),
        f / 20,
      )
    const after = ids()
    after.forEach((row, i) => row.forEach((object, j) => expect(object).toBe(before[i]![j])))
    expect(scene.children).toHaveLength(SHAPES.length)
    expect(disposed).not.toHaveBeenCalled()
    disposed.mockRestore()
    field.dispose(scene)
  })

  it('writes the animation angle per instance from the key and the time', () => {
    const scene = new THREE.Scene()
    const field = new TargetField(scene, material)
    frame(
      field,
      [
        ['bird', 4],
        ['rotary-small', 4],
      ],
      1.5,
    )
    const bird = field.meshOf('bird')!.geometry.getAttribute('aAngle')
    const rotary = field.meshOf('rotary-small')!.geometry.getAttribute('aAngle')
    expect(bird.getX(0)).toBeCloseTo(flapAngle(4, 1.5), 6)
    expect(rotary.getX(0)).toBeCloseTo(rotorAngle(4, 1.5), 5)
    field.dispose(scene)
  })

  it('stores the pose matrix of each contact', () => {
    const scene = new THREE.Scene()
    const field = new TargetField(scene, material)
    const p = new THREE.Object3D()
    p.position.set(1, 2, 3)
    p.scale.setScalar(2)
    field.begin()
    field.place('kite', 1, p, 0)
    field.end()
    const m = new THREE.Matrix4()
    field.meshOf('kite')!.getMatrixAt(0, m)
    expect(m.elements[12]).toBe(1)
    expect(m.elements[13]).toBe(2)
    expect(m.elements[14]).toBe(3)
    expect(m.elements[0]).toBe(2)
    field.dispose(scene)
  })

  it('removes its meshes and disposes every geometry on dispose', () => {
    const scene = new THREE.Scene()
    const field = new TargetField(scene, material)
    const geometries = scene.children.map((c) => (c as THREE.Mesh).geometry)
    const disposed = new Set<unknown>()
    for (const g of geometries) g.addEventListener('dispose', () => disposed.add(g))
    field.dispose(scene)
    expect(scene.children).toHaveLength(0)
    expect(disposed.size).toBe(geometries.length)
  })
})

describe('patchTargetMaterial', () => {
  it('adds the part, heat and angle attributes and scales emission by heat', () => {
    const material = new THREE.MeshLambertMaterial()
    patchTargetMaterial(material)
    const shader = {
      vertexShader: 'void main() {\n#include <begin_vertex>\n}',
      fragmentShader: 'void main() {\n#include <emissivemap_fragment>\n}',
    }
    material.onBeforeCompile(
      shader as unknown as THREE.WebGLProgramParametersWithUniforms,
      undefined as never,
    )
    expect(shader.vertexShader).toContain('attribute vec4 aPart;')
    expect(shader.vertexShader).toContain('attribute float aAngle;')
    expect(shader.vertexShader).toContain('vHeat = aHeat;')
    expect(shader.fragmentShader).toContain('totalEmissiveRadiance *= vHeat;')
    expect(material.customProgramCacheKey()).toBe('eo-target')
  })
})
