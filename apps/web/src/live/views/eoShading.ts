/**
 * Shader patches shared by the EO scene's materials: a cheap height term for the exponential fog
 * (denser near the ground) and wind sway for instanced trees. Both are `onBeforeCompile` edits to
 * three's own Lambert shader, driven by uniform objects shared across materials, so changing a
 * value once updates every material and nothing is allocated per frame.
 */
import * as THREE from 'three'

export interface SharedUniforms {
  /** Extra fog density at ground level, as a multiple of the base density. */
  fogBoost: THREE.IUniform<number>
  /** Height in metres over which the ground fog fades out. */
  fogScale: THREE.IUniform<number>
  time: THREE.IUniform<number>
  /** Wind velocity in world x and z, m/s. */
  wind: THREE.IUniform<THREE.Vector2>
  /** Sway amplitude, 0..1. */
  sway: THREE.IUniform<number>
}

export function createSharedUniforms(): SharedUniforms {
  return {
    fogBoost: { value: 0.8 },
    fogScale: { value: 70 },
    time: { value: 0 },
    wind: { value: new THREE.Vector2(2.5, 0) },
    sway: { value: 0.2 },
  }
}

const FOG_VERTEX = /* glsl */ `
#ifdef USE_FOG
  vec4 hfPos = vec4( transformed, 1.0 );
  #ifdef USE_INSTANCING
    hfPos = instanceMatrix * hfPos;
  #endif
  hfPos = modelMatrix * hfPos;
  vFogDepth = - mvPosition.z * ( 1.0 + uFogBoost * exp( - max( hfPos.y, 0.0 ) / uFogScale ) );
#endif
`

const SWAY_VERTEX = /* glsl */ `
#include <begin_vertex>
#ifdef USE_INSTANCING
  {
    // Local height 0..1 of the unit tree geometry: the crown moves, the foot stays.
    float lean = transformed.y * transformed.y;
    float phase = instanceMatrix[3].x * 0.071 + instanceMatrix[3].z * 0.053;
    float gust = 0.65 + 0.35 * sin( uTime * 0.7 + phase * 0.4 );
    float wobble = sin( uTime * 2.3 + phase ) * 0.5 + sin( uTime * 3.7 + phase * 1.7 ) * 0.5;
    vec2 push = uWind * ( 0.045 * uSway ) * gust + normalize( uWind + vec2( 0.001 ) ) * wobble * 0.05 * uSway;
    transformed.xz += push * lean;
  }
#endif
`

/**
 * Patch a Lambert-family material. `sway` also bends instanced trees in the wind. A custom
 * program cache key keeps patched and plain programs apart.
 */
export function patchMaterial(
  material: THREE.Material,
  uniforms: SharedUniforms,
  options: { sway?: boolean } = {},
): void {
  const sway = options.sway === true
  material.onBeforeCompile = (shader) => {
    shader.uniforms.uFogBoost = uniforms.fogBoost
    shader.uniforms.uFogScale = uniforms.fogScale
    let vertex = shader.vertexShader
    let header = 'uniform float uFogBoost;\nuniform float uFogScale;\n'
    if (sway) {
      shader.uniforms.uTime = uniforms.time
      shader.uniforms.uWind = uniforms.wind
      shader.uniforms.uSway = uniforms.sway
      header += 'uniform float uTime;\nuniform vec2 uWind;\nuniform float uSway;\n'
      vertex = vertex.replace('#include <begin_vertex>', SWAY_VERTEX)
    }
    shader.vertexShader = header + vertex.replace('#include <fog_vertex>', FOG_VERTEX)
  }
  material.customProgramCacheKey = () => (sway ? 'eo-hf-sway' : 'eo-hf')
}
