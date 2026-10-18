import type { Group } from 'three'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'

/** Parse a binary glTF held in memory. The pack's meshes are self-contained, so no base path. */
export async function parseGlb(buffer: ArrayBuffer): Promise<Group> {
  const gltf = await new GLTFLoader().parseAsync(buffer, '')
  return gltf.scene
}
