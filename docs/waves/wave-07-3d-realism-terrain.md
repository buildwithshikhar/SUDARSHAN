# Wave 7 · 3D realism + terrain packs

| | |
|---|---|
| Depends on | 5 |
| Recommended model | Sonnet (switch to Opus only if the benchmark gate fails) |
| Deployment | Keep the live build green; the live link gains the realistic scene. |

**Goal.** A convincing offline 3D scene on real-shaped generic terrain that meets the benchmark gate on the floor laptop.

## Scope

- Offline bake pipeline: SRTM → heightmap mesh, OSM buildings → extruded glTF, producing a rural pack and an urban pack of generic or fictionalised areas, each with an attribution file (SRTM, © OpenStreetMap contributors, ODbL).
- Line-of-sight occlusion in the sim core from the same heightmap and buildings, so server and client agree.
- Time-of-day sky with sun and moon driving light, ACES tone mapping, height fog, rain, wind.
- NV and thermal post-processing passes (per-material temperature, noise, blur, auto-gain); SVG reticle HUD.
- Quality tiers chosen by an fps probe; the benchmark scene from `docs/04-engine.md` with a harness that records fps percentiles to JSON.

## Out of scope

- New threat classes (wave 8).

## Acceptance criteria

- Packs are reproducible from the bake scripts; raw SRTM/OSM downloads stay outside git; attribution ships with each pack.
- LOS tests: a target behind terrain or a building is not detected by line-of-sight sensors.
- JS bundle ≤ 1.5 MB gzipped excluding assets (CI check); first load ≤ 8 s from the local server.
- Benchmark gate from 04 on the floor laptop: ≥ 45 fps median and ≥ 30 fps 5th percentile at 1080p, or the auto tier holds 30 fps. The user runs the harness on the floor laptop; results and machine specs go in `docs/PERFORMANCE.md`.
- If the gate fails, stop and say so; the fix continues on Opus.
- Every new user-facing string exists in EN and HI (key-parity check passes).
- Every new screen has populated, empty, loading and error states, works by keyboard, and is axe-clean.
- CI is green on `main` (lint, typecheck, unit, e2e, gitleaks, docker build).
- Every feature in this wave has tests; no existing test was skipped, disabled or weakened.
- Production images build and the production-mode compose stack passes `make smoke`.
- `docs/BUILD_LOG.md` is updated per its rules, including the deploy check and the next wave entry point.
- No credentials, secrets or real keys anywhere in git history; only `.env.example` placeholders.
- The deployed build still works: the commit to deploy is recorded in the build log, and after the user redeploys, `make smoke URL=<live url>` passes.

## Prompt (paste into Claude Code, Sonnet)

````text
ROLE: You are building wave 7 (3D realism + terrain packs) of SUDARSHAN, an AI-enabled drone and counter-drone threat simulation TRAINER (SIH 2026, PS 26247). CLAUDE.md is loaded: follow it, above all the LOCKED RULES.

READ FIRST: docs/BUILD_LOG.md (confirm wave 6 is Done and main is green; if not, stop and tell me). Then: docs/04-engine.md (benchmark gate), docs/07-ui-map.md (3D look), docs/DATA_REGISTER.md (G01, G02).

GOAL: A convincing offline 3D scene on real-shaped generic terrain that meets the benchmark gate on the floor laptop.

STEP 1 — Terrain pipeline (subagent A, worktree)
- tools/terrain/: scripts that take an SRTM tile and an OSM extract (downloaded by the user into data/raw/, which git ignores) and bake a heightmap mesh and building glTF, plus a pack manifest with attribution.
- Choose generic, non-sensitive areas; give sites fictional names. No identifiable military or sensitive installations.
- LOS occlusion in the sim core from the baked heightmap and building footprints.

STEP 2 — Look and feel (subagent B, worktree)
- Sky, sun and moon, ACES tone mapping, height fog, rain streaks, wind on trees and drift.
- Thermal (white-hot and black-hot) and NV passes; reticle HUD in SVG over the canvas.
- Quality tiers with an fps probe at session start.

STEP 3 — Benchmark (main session)
- The reference scene from docs/04-engine.md (a placeholder swarm and birds are fine until wave 8) and a /bench route in demo mode that writes fps percentiles and device info to JSON.
- Bundle-size CI check. Then stop and ask me to run the bench on the floor laptop; record my results in docs/PERFORMANCE.md.

OUT OF SCOPE (do not build):
- New threat classes (wave 8).

ACCEPTANCE (all must be true):
- Packs are reproducible from the bake scripts; raw SRTM/OSM downloads stay outside git; attribution ships with each pack.
- LOS tests: a target behind terrain or a building is not detected by line-of-sight sensors.
- JS bundle ≤ 1.5 MB gzipped excluding assets (CI check); first load ≤ 8 s from the local server.
- Benchmark gate from 04 on the floor laptop: ≥ 45 fps median and ≥ 30 fps 5th percentile at 1080p, or the auto tier holds 30 fps. The user runs the harness on the floor laptop; results and machine specs go in `docs/PERFORMANCE.md`.
- If the gate fails, stop and say so; the fix continues on Opus.
- Every new user-facing string exists in EN and HI (key-parity check passes).
- Every new screen has populated, empty, loading and error states, works by keyboard, and is axe-clean.
- CI is green on `main` (lint, typecheck, unit, e2e, gitleaks, docker build).
- Every feature in this wave has tests; no existing test was skipped, disabled or weakened.
- Production images build and the production-mode compose stack passes `make smoke`.
- `docs/BUILD_LOG.md` is updated per its rules, including the deploy check and the next wave entry point.
- No credentials, secrets or real keys anywhere in git history; only `.env.example` placeholders.
- The deployed build still works: the commit to deploy is recorded in the build log, and after the user redeploys, `make smoke URL=<live url>` passes.

LOG: Follow the rules in docs/BUILD_LOG.md. Add a "Wave 7" entry at the start, append each merged commit, record decisions, test counts and the deploy check, and write the exact first step of wave 8.

STOP CONDITIONS — stop and report if:
- a step needs credentials, or network beyond package registries and GitHub;
- a Docker action would touch anything outside this repo's compose project;
- CI fails 3 times on the same cause;
- about 60% of the session is used before acceptance (commit green work, log it as wave 7.b, stop);
- the benchmark gate fails (report the numbers; do not tune endlessly).
- Never build features from later waves.

FINAL OUTPUT TO ME: at most 10 lines — commits, test counts, CI result, deploy check (and the commit for me to deploy), anything skipped and why, and the first step of wave 8.
````
