/**
 * The thermal and night-vision passes: the scene is drawn into a render target and one full-screen
 * shader turns it into the sensor picture. Hand-written ShaderMaterial, no post-processing library.
 *
 * Thermal is a rendering model, not radiometric (docs/SENSOR_MODELS.md). The scene is drawn with
 * per-class "apparent temperature" materials; this pass blurs it a little, adds sensor noise and
 * fixed-pattern columns, normalises it with an automatic gain and applies the polarity. Night
 * vision lifts the scene by a tube gain, tints it phosphor green and adds grain and a vignette.
 *
 * The automatic gain comes from a 32 x 18 downsample read back asynchronously every few frames,
 * so the GPU is never stalled; the range is eased so the picture does not pump.
 */
import * as THREE from 'three'
import { easeRange, gainPercent, lumaRange, nvGain, type EoMode, type GainRange } from './eoMode'

const SAMPLE_W = 32
const SAMPLE_H = 18
/** Sample the picture for the gain every this many frames. */
const SAMPLE_EVERY = 8

const VERTEX = /* glsl */ `
varying vec2 vUv;
void main() {
  vUv = uv;
  gl_Position = vec4( position.xy, 0.0, 1.0 );
}
`

const COMMON = /* glsl */ `
varying vec2 vUv;
uniform sampler2D tScene;
float luma( vec3 c ) { return dot( c, vec3( 0.2126, 0.7152, 0.0722 ) ); }
float hash( vec2 p ) {
  vec3 p3 = fract( vec3( p.xyx ) * 0.1031 );
  p3 += dot( p3, p3.yzx + 33.33 );
  return fract( ( p3.x + p3.y ) * p3.z );
}
`

/** Writes sqrt(luminance) so the 8-bit sample keeps precision in the dark. */
const SAMPLE_FRAGMENT = /* glsl */ `
${COMMON}
void main() {
  float s = 0.0;
  for ( int y = 0; y < 3; y++ ) {
    for ( int x = 0; x < 3; x++ ) {
      s += luma( texture2D( tScene, vUv + ( vec2( float( x ), float( y ) ) - 1.0 ) * 0.012 ).rgb );
    }
  }
  s /= 9.0;
  gl_FragColor = vec4( vec3( sqrt( clamp( s, 0.0, 1.0 ) ) ), 1.0 );
}
`

const PICTURE_FRAGMENT = /* glsl */ `
${COMMON}
uniform vec2 uTexel;
uniform vec2 uRes;
uniform float uFrame;
uniform float uMode;     // 1 thermal, 2 night vision
uniform float uInvert;   // 1 black-hot
uniform float uLo;
uniform float uHi;
uniform float uGain;
uniform float uAspect;

void main() {
  // a slight optical blur: centre plus four neighbours
  vec3 c = texture2D( tScene, vUv ).rgb * 0.36;
  c += texture2D( tScene, vUv + vec2( uTexel.x, 0.0 ) * 1.3 ).rgb * 0.16;
  c += texture2D( tScene, vUv - vec2( uTexel.x, 0.0 ) * 1.3 ).rgb * 0.16;
  c += texture2D( tScene, vUv + vec2( 0.0, uTexel.y ) * 1.3 ).rgb * 0.16;
  c += texture2D( tScene, vUv - vec2( 0.0, uTexel.y ) * 1.3 ).rgb * 0.16;
  float l = luma( c );
  vec2 cell = floor( vUv * uRes );
  float seed = fract( uFrame * 0.6180339 );
  float temporal = hash( cell + seed * 97.0 ) - 0.5;

  if ( uMode < 1.5 ) {
    // thermal: automatic gain, noise, fixed-pattern columns, polarity
    float v = ( l - uLo ) / max( uHi - uLo, 0.04 );
    float column = hash( vec2( cell.x, 3.0 ) ) - 0.5;
    v += temporal * 0.05 + column * 0.018;
    v = clamp( v, 0.0, 1.0 );
    v = v * v * ( 3.0 - 2.0 * v ) * 0.35 + v * 0.65;
    v = mix( v, 1.0 - v, uInvert );
    gl_FragColor = vec4( vec3( v ), 1.0 );
  } else {
    // night vision: tube gain, soft clip, grain strongest in the dark, green phosphor, scope vignette
    float s = l * uGain;
    float i = pow( 1.0 - exp( -1.4 * s ), 1.35 );
    i += temporal * 0.22 * ( 1.0 - i ) * ( 0.35 + 0.65 * exp( -3.0 * i ) );
    i = clamp( i, 0.0, 1.0 );
    vec2 q = ( vUv - 0.5 ) * vec2( uAspect, 1.0 );
    float vig = smoothstep( 0.98, 0.52, length( q ) );
    vec3 phosphor = vec3( 0.2, 1.0, 0.34 );
    gl_FragColor = vec4( pow( i, 0.85 ) * phosphor * mix( 0.35, 1.0, vig ), 1.0 );
  }
}
`

function fullscreenTriangle(): THREE.BufferGeometry {
  const g = new THREE.BufferGeometry()
  g.setAttribute(
    'position',
    new THREE.BufferAttribute(new Float32Array([-1, -1, 0, 3, -1, 0, -1, 3, 0]), 3),
  )
  g.setAttribute('uv', new THREE.BufferAttribute(new Float32Array([0, 0, 2, 0, 0, 2]), 2))
  return g
}

export interface LookReadout {
  mode: EoMode
  /** Gain readout 0..100 for thermal; tube gain (x) for night vision. */
  gainPct: number
  tubeGain: number
}

export class PostPass {
  private target: THREE.WebGLRenderTarget
  private readonly sample: THREE.WebGLRenderTarget
  private readonly geometry = fullscreenTriangle()
  private readonly picture: THREE.ShaderMaterial
  private readonly down: THREE.ShaderMaterial
  private readonly quad: THREE.Mesh
  private readonly stage = new THREE.Scene()
  private readonly camera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1)
  private readonly pixels = new Uint8Array(SAMPLE_W * SAMPLE_H * 4)
  private readonly u = {
    tScene: { value: null as THREE.Texture | null },
    uTexel: { value: new THREE.Vector2(1, 1) },
    uRes: { value: new THREE.Vector2(1, 1) },
    uFrame: { value: 0 },
    uMode: { value: 1 },
    uInvert: { value: 0 },
    uLo: { value: 0 },
    uHi: { value: 1 },
    uGain: { value: 1 },
    uAspect: { value: 16 / 9 },
  }
  private range: GainRange = { lo: 0, hi: 1, mean: 0.5 }
  private primed = false
  private reading = false
  private frame = 0
  private disposed = false
  private current: EoMode = 'thermal-white-hot'

  constructor(
    private readonly renderer: THREE.WebGLRenderer,
    private readonly onLook: (look: LookReadout) => void,
  ) {
    const half =
      renderer.extensions.has('EXT_color_buffer_half_float') ||
      renderer.extensions.has('EXT_color_buffer_float')
    this.target = new THREE.WebGLRenderTarget(2, 2, {
      type: half ? THREE.HalfFloatType : THREE.UnsignedByteType,
      depthBuffer: true,
      minFilter: THREE.LinearFilter,
      magFilter: THREE.LinearFilter,
      generateMipmaps: false,
    })
    this.sample = new THREE.WebGLRenderTarget(SAMPLE_W, SAMPLE_H, {
      type: THREE.UnsignedByteType,
      depthBuffer: false,
      minFilter: THREE.NearestFilter,
      magFilter: THREE.NearestFilter,
      generateMipmaps: false,
    })
    this.u.tScene.value = this.target.texture
    this.picture = new THREE.ShaderMaterial({
      vertexShader: VERTEX,
      fragmentShader: PICTURE_FRAGMENT,
      depthTest: false,
      depthWrite: false,
      uniforms: this.u,
    })
    this.down = new THREE.ShaderMaterial({
      vertexShader: VERTEX,
      fragmentShader: SAMPLE_FRAGMENT,
      depthTest: false,
      depthWrite: false,
      uniforms: { tScene: { value: this.target.texture } },
    })
    this.quad = new THREE.Mesh(this.geometry, this.picture)
    this.quad.frustumCulled = false
    this.stage.add(this.quad)
  }

  /** Match the target to the canvas: drawing-buffer pixels times the tier's resolution scale. */
  resize(drawingWidth: number, drawingHeight: number, scale: number, samples: number): void {
    const w = Math.max(2, Math.round(drawingWidth * scale))
    const h = Math.max(2, Math.round(drawingHeight * scale))
    this.target.setSize(w, h)
    this.target.samples = samples
    this.u.uTexel.value.set(1 / w, 1 / h)
    this.u.uRes.value.set(w, h)
    this.u.uAspect.value = drawingWidth / Math.max(1, drawingHeight)
  }

  setMode(mode: EoMode): void {
    if (mode === 'day') return
    this.current = mode
    this.u.uMode.value = mode === 'night-vision' ? 2 : 1
    this.u.uInvert.value = mode === 'thermal-black-hot' ? 1 : 0
    // The new picture needs a fresh gain, not an eased one from the previous mode.
    this.primed = false
  }

  /** Draw the scene through the pass to the canvas. */
  render(scene: THREE.Scene, camera: THREE.Camera): void {
    const r = this.renderer
    r.setRenderTarget(this.target)
    r.render(scene, camera)
    this.frame++
    this.u.uFrame.value = this.frame
    if (this.frame % SAMPLE_EVERY === 1 || !this.primed) this.measure()
    if (this.primed) {
      this.u.uLo.value = this.range.lo
      this.u.uHi.value = this.range.hi
      this.u.uGain.value = nvGain(this.range.mean)
    }
    r.setRenderTarget(null)
    r.render(this.stage, this.camera)
  }

  private measure(): void {
    if (this.reading || this.disposed) return
    const r = this.renderer
    this.quad.material = this.down
    r.setRenderTarget(this.sample)
    r.render(this.stage, this.camera)
    this.quad.material = this.picture
    r.setRenderTarget(this.target)
    this.reading = true
    const mode = this.current
    r.readRenderTargetPixelsAsync(this.sample, 0, 0, SAMPLE_W, SAMPLE_H, this.pixels).then(
      (data) => {
        this.reading = false
        if (this.disposed) return
        const next = lumaRange(data as Uint8Array)
        this.range = this.primed ? easeRange(this.range, next, 0.35) : next
        this.primed = true
        this.onLook({ mode, gainPct: gainPercent(this.range), tubeGain: nvGain(this.range.mean) })
      },
      () => {
        this.reading = false
      },
    )
  }

  dispose(): void {
    this.disposed = true
    this.target.dispose()
    this.sample.dispose()
    this.geometry.dispose()
    this.picture.dispose()
    this.down.dispose()
  }
}
