/**
 * Rain as one LineSegments object. Every streak is two vertices holding a fixed random seed; the
 * vertex shader places it inside a box that follows the camera, lets it fall and drift with the
 * wind, and wraps it round the box, so nothing is updated per frame except three uniforms.
 */
import * as THREE from 'three'
import type { SharedUniforms } from './eoShading'

/** Streak capacity: the high tier's budget. Lower tiers draw a prefix of it. */
export const RAIN_CAPACITY = 2400

const BOX = new THREE.Vector3(26, 16, 26)
/** Terminal speed of a falling drop, m/s. */
const FALL_MPS = 9

const VERTEX = /* glsl */ `
uniform float uTime;
uniform vec3 uCam;
uniform vec3 uBox;
uniform vec2 uWind;
uniform float uFall;
attribute float aTip;
varying float vAlpha;
void main() {
  // drops drift with the wind but slower than it blows, and fall at terminal speed
  vec3 vel = vec3( uWind.x * 0.55, - uFall, uWind.y * 0.55 );
  vec3 p = position * uBox + vel * uTime;
  vec3 o = mod( p - uCam + uBox * 0.5, uBox ) - uBox * 0.5;
  vec3 world = uCam + o;
  // the trailing end is up-stream along the velocity
  world -= vel * 0.11 * aTip;
  float near = smoothstep( 0.8, 3.0, length( o ) );
  float far = 1.0 - smoothstep( 9.0, 14.0, length( o ) );
  vAlpha = near * far * mix( 1.0, 0.35, aTip );
  gl_Position = projectionMatrix * viewMatrix * vec4( world, 1.0 );
}
`

const FRAGMENT = /* glsl */ `
uniform vec3 uColor;
uniform float uOpacity;
varying float vAlpha;
void main() {
  gl_FragColor = vec4( uColor, uOpacity * vAlpha );
}
`

export class Rain {
  readonly object: THREE.LineSegments
  private readonly geometry = new THREE.BufferGeometry()
  private readonly material: THREE.ShaderMaterial
  private readonly cam = { value: new THREE.Vector3() }
  private readonly colour = { value: new THREE.Color(0.75, 0.8, 0.88) }
  private readonly opacity = { value: 0.5 }

  constructor(shared: SharedUniforms) {
    const seeds = new Float32Array(RAIN_CAPACITY * 2 * 3)
    const tips = new Float32Array(RAIN_CAPACITY * 2)
    let s = 91
    const rand = () => {
      s = (s * 16807) % 2147483647
      return s / 2147483647
    }
    for (let i = 0; i < RAIN_CAPACITY; i++) {
      const x = rand()
      const y = rand()
      const z = rand()
      seeds.set([x, y, z, x, y, z], i * 6)
      tips[i * 2] = 0
      tips[i * 2 + 1] = 1
    }
    this.geometry.setAttribute('position', new THREE.BufferAttribute(seeds, 3))
    this.geometry.setAttribute('aTip', new THREE.BufferAttribute(tips, 1))
    this.geometry.setDrawRange(0, 0)
    this.material = new THREE.ShaderMaterial({
      vertexShader: VERTEX,
      fragmentShader: FRAGMENT,
      transparent: true,
      depthWrite: false,
      fog: false,
      uniforms: {
        uTime: shared.time,
        uCam: this.cam,
        uBox: { value: BOX.clone() },
        uWind: shared.wind,
        uFall: { value: FALL_MPS },
        uColor: this.colour,
        uOpacity: this.opacity,
      },
    })
    this.object = new THREE.LineSegments(this.geometry, this.material)
    this.object.frustumCulled = false
    this.object.renderOrder = 20
    this.object.visible = false
  }

  /** Draw `count` streaks (0 hides the whole object). */
  setCount(count: number): void {
    const n = Math.max(0, Math.min(RAIN_CAPACITY, Math.round(count)))
    this.geometry.setDrawRange(0, n * 2)
    this.object.visible = n > 0
  }

  get drawn(): number {
    return this.object.visible ? this.geometry.drawRange.count / 2 : 0
  }

  setLook(r: number, g: number, b: number, opacity: number): void {
    this.colour.value.setRGB(r, g, b)
    this.opacity.value = opacity
  }

  follow(camera: THREE.Vector3): void {
    this.cam.value.copy(camera)
  }

  dispose(): void {
    this.geometry.dispose()
    this.material.dispose()
  }
}
