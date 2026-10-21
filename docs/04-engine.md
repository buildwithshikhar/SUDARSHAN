# 04 · Engine decision

Requirement: browser-based, runs on a laptop with 8 GB RAM and integrated graphics, **fully offline** (classroom or LAN, no internet), WebXR optional. Scenarios are local engagements (an area up to about 20 × 20 km around a defended site), not globe-scale.

## Candidates

| Criterion | **Three.js** | **CesiumJS** | **Babylon.js** | PlayCanvas (engine) | Godot 4 (web export) |
|---|---|---|---|---|---|
| Licence | MIT | Apache-2.0 (Cesium ion and ion Self-Hosted are commercial) | Apache-2.0 | MIT (editor is a hosted service) | MIT |
| Scale model | Local scene, any coordinates | WGS84 globe, geospatial-precise | Local scene | Local scene | Local scene |
| Offline | Trivial: all assets are bundled | Possible, but you must self-host terrain and imagery. The default World Terrain and Bing imagery are ion services. Self-hosted ion is paid. [1][2] | Trivial | Trivial | Trivial |
| WebXR | Built in (`renderer.xr`), mature, many examples | **Not officially supported.** The WebXR PR #11372 was still open at last check. [3][4] | First-class (`WebXRDefaultExperience`) [5] | Built in | Supported in Godot 4 web export, less mature |
| Integrated-GPU performance | Excellent; you control every draw call | Heavy: globe tile streaming and a high baseline cost | Good, with a higher baseline than Three.js | Good | Heavier WASM payload; slow first load |
| Night-vision / thermal looks | Custom post-processing passes (EffectComposer or TSL); full control | Post-process stages exist; harder to customise deeply | Strong post-process pipeline | Possible | Possible (shaders) |
| Terrain from SRTM / OSM | Pre-bake a local heightmap and buildings offline into glTF. Simple and fast. | Native (quantized-mesh, 3D Tiles). Best-in-class if you need the globe. | Pre-bake, as Three.js | Pre-bake | Pre-bake |
| WebGPU path | `WebGPURenderer` with automatic WebGL 2 fallback [6] | Experimental | WebGPU-first since v5 | Yes | Not on web |
| Ecosystem and tooling familiarity | Largest. Code generation is reliable. | Narrow, GIS-focused | Large | Small | Medium; GDScript does not fit our TS/Python stack |
| Testing in CI (headless, Playwright) | Works with SwiftShader WebGL | Works, but slow | Works | Works | Hard |
| Fit with React UI | Clean: an imperative renderer in a React host component | Clean (Resium) | Clean | Clean | Poor (separate canvas app) |

Sources: [1] [Cesium forum: completely offline mode](https://community.cesium.com/t/cesium-completely-offline-mode/36153) · [2] [Cesium forum: CesiumJS/ion offline](https://community.cesium.com/t/cesiumjs-ion-in-an-offline-environment/8738) · [3] [CesiumGS/cesium PR #11372](https://github.com/CesiumGS/cesium/pull/11372) (open; last activity Sep 2025 at check) · [4] [Cesium forum: WebXR in CesiumJS](https://community.cesium.com/t/webxr-in-cesiumjs/22948) · [5] [Babylon.js WebXRExperienceHelper (package source)](https://app.unpkg.com/@babylonjs/core@9.18.0/files/XR/webXRExperienceHelper.d.ts) · [6] [three.js manual: WebGPURenderer](https://threejs.org/manual/en/webgpurenderer). UNVERIFIED: exact performance numbers. The figures above are a qualitative engineering judgement until our own benchmark exists (see below).

## Recommendation: Three.js

1. **Three.js with `WebGLRenderer` as the shipping path.** This is the most mature WebXR path. `WebGPURenderer` sits behind a feature flag and is adopted only if our benchmark shows a gain on the floor laptop.
2. **CesiumJS is rejected for the simulator view.** The globe adds cost and an offline-tiles burden for no training value at a 20 km scale, and it has no official WebXR. The 2D tactical map uses **MapLibre GL** with an offline vector-tile pack (OSM extract), which is lighter than a globe.
3. **Babylon.js is the credible runner-up.** Choose it only if WebXR becomes a headline requirement and Three.js XR fails our tests. That is unlikely.
4. **Simulation is authoritative on the server, not in the renderer.** The Python sim core (numpy, fixed 20 Hz tick, seeded RNG) owns ground truth, threat behaviour and sensor models. The browser receives only what the trainee's sensors would report, plus visible entities in a camera field of view, over WebSocket, and interpolates at 60 fps. This gives us:
   - no cheating by reading ground truth from client memory;
   - instructor pause and event injection for free;
   - LAN team mode for free;
   - headless solvability checks that use the same code;
   - scoring computed from one trusted event log.

## Benchmark gate (wave 3 acceptance)

The reference scene is a rural 10 km² tile, 40 buildings, a 24-drone swarm plus 30 birds, with the thermal pass on.

- ≥ 45 fps median and ≥ 30 fps 5th-percentile at 1080p on the floor laptop (integrated graphics). If we miss it, the auto-quality tier must hold 30 fps.
- First load ≤ 8 s from the local server. JS bundle ≤ 1.5 MB gzipped, excluding assets.
- The result is logged in `docs/PERFORMANCE.md` with machine specs. This is the only performance claim we make.
