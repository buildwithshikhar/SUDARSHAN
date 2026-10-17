# Wave 8 · Threat breadth

| | |
|---|---|
| Depends on | 4, 7 |
| Recommended model | Sonnet |
| Deployment | Keep the live build green. |

**Goal.** The full threat and clutter library, including swarms, decoys and RF-silent threats, at behaviour level only.

## Scope

- Drone class catalogue: COTS quadcopter, FPV, fixed-wing one-way or loitering type (generic), Group 1–3 equivalents; envelopes from the UAV Database (X01) and the research brief, each parameter with a register ID.
- Swarm behaviours: boids base, Vicsek noise as a discipline knob, leader-follower or leaderless topology, consensus with link loss; intents (loiter, probe, saturation); decoys; RF-silent fraction; arrival profiles.
- Clutter: bird flocks with wing-beat signatures, kites, balloons, permitted civil drones with filed flights.
- Signatures feed every sensor model; low-poly instanced meshes in the 3D scene.

## Out of scope

- Scenario generation (wave 9).

## Acceptance criteria

- No guidance, targeting or terminal-attack logic anywhere; a code review note in the build log confirms it (locked rule 2).
- Every class instantiates in both terrain packs (test).
- Swarm determinism and cohesion-metric tests; removing a leader changes behaviour as specified.
- The benchmark scene with the real 24-drone swarm and 30 birds still meets the gate (re-run harness; user confirms on the floor laptop).
- `docs/THREAT_CATALOGUE.md` lists every class and clutter type with its parameters and register IDs.
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
ROLE: You are building wave 8 (Threat breadth) of SUDARSHAN, an AI-enabled drone and counter-drone threat simulation TRAINER (SIH 2026, PS 26247). CLAUDE.md is loaded: follow it, above all the LOCKED RULES.

READ FIRST: docs/BUILD_LOG.md (confirm wave 7 is Done and main is green; if not, stop and tell me). Then: docs/02-research.md §2 and §3, docs/DATA_REGISTER.md (X01), docs/SENSOR_MODELS.md.

GOAL: The full threat and clutter library, including swarms, decoys and RF-silent threats, at behaviour level only.

STEP 1 — Catalogue (subagent A, worktree)
- packs/threats/: YAML per class with kinematic envelope and signature parameters (each with source_id). Generic class names only; no real system names.
- Clutter types with their signatures (bird wing-beat, kite, balloon, permitted civil drone with a filed flight plan).

STEP 2 — Swarm behaviours (subagent B, worktree)
- services/api/sim/behaviours/: boids, Vicsek noise, leader-follower, leaderless consensus with link loss, intents, decoys, arrival profiles. Kinematics only.

STEP 3 — Integration (main session)
- Signatures wired into all four sensors; instanced meshes in the 3D scene.
- Tests as in the acceptance criteria; re-run the benchmark harness and ask me to confirm on the floor laptop.
- docs/THREAT_CATALOGUE.md.

OUT OF SCOPE (do not build):
- Scenario generation (wave 9).

ACCEPTANCE (all must be true):
- No guidance, targeting or terminal-attack logic anywhere; a code review note in the build log confirms it (locked rule 2).
- Every class instantiates in both terrain packs (test).
- Swarm determinism and cohesion-metric tests; removing a leader changes behaviour as specified.
- The benchmark scene with the real 24-drone swarm and 30 birds still meets the gate (re-run harness; user confirms on the floor laptop).
- `docs/THREAT_CATALOGUE.md` lists every class and clutter type with its parameters and register IDs.
- Every new user-facing string exists in EN and HI (key-parity check passes).
- Every new screen has populated, empty, loading and error states, works by keyboard, and is axe-clean.
- CI is green on `main` (lint, typecheck, unit, e2e, gitleaks, docker build).
- Every feature in this wave has tests; no existing test was skipped, disabled or weakened.
- Production images build and the production-mode compose stack passes `make smoke`.
- `docs/BUILD_LOG.md` is updated per its rules, including the deploy check and the next wave entry point.
- No credentials, secrets or real keys anywhere in git history; only `.env.example` placeholders.
- The deployed build still works: the commit to deploy is recorded in the build log, and after the user redeploys, `make smoke URL=<live url>` passes.

LOG: Follow the rules in docs/BUILD_LOG.md. Add a "Wave 8" entry at the start, append each merged commit, record decisions, test counts and the deploy check, and write the exact first step of wave 9.

STOP CONDITIONS — stop and report if:
- a step needs credentials, or network beyond package registries and GitHub;
- a Docker action would touch anything outside this repo's compose project;
- CI fails 3 times on the same cause;
- about 60% of the session is used before acceptance (commit green work, log it as wave 8.b, stop);
- Never build features from later waves.

FINAL OUTPUT TO ME: at most 10 lines — commits, test counts, CI result, deploy check (and the commit for me to deploy), anything skipped and why, and the first step of wave 9.
````
