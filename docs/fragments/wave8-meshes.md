# Wave 8: EO target meshes and the nine-class vocabulary (web fragment)

Source: `apps/web/src/live/views/eoMeshes.ts`, `eoHold.ts`, `eoScene.ts`. For the main session to fold into the build log, the engine notes and the traceability matrix.

## Classification vocabulary

The Classify step offers nine classes, in the order the welcome message sends them (`operator_classes`): rotary-small, fixed-wing-small, bird, unknown, fpv-small, fixed-wing-medium, fixed-wing-large, kite, balloon. Keys 1 to 9 pick them in that order; the first four keep their old keys. English and Hindi labels exist for all nine under `live.class.*`. The Hindi strings are an unreviewed draft (Q-15) and are in `docs/i18n/HI_REVIEW.md`. Truth class ids (autonomous-small, decoy-small, civil-drone and so on) are never sent to the browser and have no label or mesh.

## Shapes

The EO view draws one low-poly model per reported class. A report with no class, a coarse family or any other value is drawn as a generic point, as before. Models are unit-size and flat-shaded; the scene scales each to the angular size its pixel count implies.

| Shape | Silhouette | Triangles | Animation | Thermal look |
|---|---|---|---|---|
| rotary-small | body, crossed arms, four rotors | 68 | rotor blades spin | rotors hot, body warm, frame cooler |
| fpv-small | elongated body, battery slab, short thick arms, small props | 80 | rotor blades spin | as rotary-small |
| fixed-wing-small | fuselage, wing, tailplane, fin, nose propeller | 52 | propeller spins | fuselage (engine) hot, wing and tail cool |
| fixed-wing-medium | longer fuselage, larger span | 52 | propeller spins | as small |
| fixed-wing-large | central pod, widest wing, twin booms, tail bridge | 88 | propeller spins | pod hot, booms and tail cool |
| bird | body and two wings | 36 | wings flap | warm body, mid wings |
| kite | diamond of cloth, faint tether, no body | 8 | slight roll | cold: nearly invisible in white-hot |
| balloon | ellipsoid | 80 | slow vertical bob | cold: nearly invisible in white-hot |
| point | icosahedron fallback | 20 | none | hot |

Thermal is a rendering model, not radiometric: the vertex heat factor scales the same emissive value the scene already derived from the clock.

## Instancing

- One `THREE.InstancedMesh` per shape (nine), each with capacity 64 (`TARGET_CAPACITY`), created once when the scene is built. A shape's mesh is hidden while it has no contacts, so a frame costs one draw call per shape in use.
- Each model is one merged, non-indexed geometry. Per-vertex attributes carry what moves and how warm it is: `aPart` (hub position and motion kind) and `aHeat`. One per-instance attribute, `aAngle`, carries the animation angle. A small `onBeforeCompile` patch on the shared target material rotates animated vertices about their hub and scales emission by heat; it is the only shader change.
- A frame is `begin()`, `place()` per report, `end()`. `place()` writes the instance matrix and angle in place from a reused `Object3D`. No geometry, material or vector is created or disposed per report or per frame; contacts beyond 64 in one shape are not drawn. Teardown disposes every geometry once.
- `SceneStats` gains `targetsDrawn`, `targetTriangles` and `targetShapes` (the existing `triangles` and `drawCalls` still come from the renderer). The EO view mirrors the shapes on screen in a `data-shapes` attribute, written only when the set changes, for the mock e2e specs and support.

## Animation

All of it is a pure function of the report key and the clock, so it is deterministic and replays identically.

- Bird wings: 12 Hz real wing-beat drawn at a quarter of the rate (3 Hz) so a 60 Hz screen can show it; angle from -0.35 to +0.8 rad, phase offset from the key.
- Rotors and propellers: 2.5 revolutions per second as a visual cue (a real rotor is far above frame rate).
- Balloon: 0.06 model units of vertical bob, 7 s period.

## Cost

The largest model is 88 triangles, so 64 contacts of any one shape submit at most 5,632 triangles (the unit test asserts under 6,000). Typical frames are a handful of contacts. Memory is nine small geometries and 9 x 64 matrices; there is no per-frame allocation. Triangles per frame are visible in `SceneStats` for the bench. No benchmark was run for this change; it adds no performance claim.

## Mock session

`MOCK_WELCOME.operator_classes` is the nine ids and the mock now refuses a classify whose class is not in that list (as the server does). The dev-only `?mock=1&eoclass=<id>` variant reports every EO contact as that class so each model can be exercised end to end (`e2e/mock/classes.spec.ts`); it is stripped from production builds with the rest of the mock.
