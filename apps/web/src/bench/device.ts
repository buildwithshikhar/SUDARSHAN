import type { SceneStats } from '../live/views/eoScene'
import { BENCH_FORMAT, CANVAS, SWARM, BIRDS, BENCH_HOUR, GATE, evaluateGate } from './plan'
import type { GateOutcome, PhaseResult } from './plan'

export interface DeviceInfo {
  userAgent: string
  platform: string
  hardwareConcurrency: number | null
  /** Approximate GB of RAM as the browser reports it (capped at 8); null where unsupported. */
  deviceMemoryGb: number | null
  screen: { width: number; height: number }
  devicePixelRatio: number
  webgl: { version: 1 | 2 | null; vendor: string | null; renderer: string | null }
}

export interface BenchResult {
  format: typeof BENCH_FORMAT
  startedAt: string
  build: { version: string; gitSha: string; env: string } | null
  device: DeviceInfo
  scene: {
    pack: string
    packVersion: string
    buildings: number
    trees: number
    swarm: number
    birds: number
    hour: number
    canvas: { width: number; height: number }
    pixelRatio: number
    stats: SceneStats | null
  }
  phases: PhaseResult[]
  gate: GateOutcome & { criteria: typeof GATE }
  notes: string[]
}

/** The facts about the machine that explain a result. Nothing here identifies a person. */
export function collectDevice(
  gl: WebGLRenderingContext | WebGL2RenderingContext | null,
): DeviceInfo {
  let vendor: string | null = null
  let renderer: string | null = null
  if (gl) {
    const ext = gl.getExtension('WEBGL_debug_renderer_info')
    vendor = ext ? String(gl.getParameter(ext.UNMASKED_VENDOR_WEBGL)) : null
    renderer = ext ? String(gl.getParameter(ext.UNMASKED_RENDERER_WEBGL)) : null
  }
  const nav = navigator as Navigator & { deviceMemory?: number }
  return {
    userAgent: navigator.userAgent,
    platform: navigator.platform,
    hardwareConcurrency: navigator.hardwareConcurrency ?? null,
    deviceMemoryGb: nav.deviceMemory ?? null,
    screen: { width: screen.width, height: screen.height },
    devicePixelRatio: window.devicePixelRatio || 1,
    webgl: {
      version: gl
        ? typeof WebGL2RenderingContext !== 'undefined' && gl instanceof WebGL2RenderingContext
          ? 2
          : 1
        : null,
      vendor,
      renderer,
    },
  }
}

export const NOTES = [
  'Measured at 1920 x 1080 with the renderer pixel ratio fixed at 1.',
  'Frame times are requestAnimationFrame intervals, so a 60 Hz display caps the figures at 60 fps.',
  'Antialiasing is fixed when the WebGL context is created (high tier), so the medium and low phases keep it on.',
  'The scene replays a recorded run of the real swarm (24 drones, leader-follower) and flock (30 birds) behaviours, plus two kites and a balloon, drawn as EO reports through the instanced meshes.',
  'Thermal is a rendering model, not radiometric.',
]

export function assemble(args: {
  startedAt: string
  build: BenchResult['build']
  device: DeviceInfo
  pack: { id: string; version: string; buildings: number; trees: number }
  pixelRatio: number
  stats: SceneStats | null
  phases: PhaseResult[]
}): BenchResult {
  return {
    format: BENCH_FORMAT,
    startedAt: args.startedAt,
    build: args.build,
    device: args.device,
    scene: {
      pack: args.pack.id,
      packVersion: args.pack.version,
      buildings: args.pack.buildings,
      trees: args.pack.trees,
      swarm: SWARM,
      birds: BIRDS,
      hour: BENCH_HOUR,
      canvas: { ...CANVAS },
      pixelRatio: args.pixelRatio,
      stats: args.stats,
    },
    phases: args.phases,
    gate: { ...evaluateGate(args.phases), criteria: GATE },
    notes: NOTES,
  }
}
