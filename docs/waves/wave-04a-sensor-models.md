# Wave 4a · Sensor models

| | |
|---|---|
| Depends on | 3 |
| Recommended model | Opus |
| Deployment | Keep the live build green. No new user-facing feature. |

**Goal.** Physically-motivated radar, EO/IR, RF and acoustic detection models with degradations, every parameter sourced from the data register.

## Scope

- Detection models as probability of detection and measurement noise vs range, aspect, weather and time of day: radar (RCS ranges, clutter, a micro-Doppler cue), EO/IR (Johnson-criteria pixel thresholds, apparent size = size ÷ (range × IFOV), day, NV and thermal modes), RF (bands, hop-pattern presence, RF-silent targets), acoustic (blade-pass harmonics, range limit, wind noise).
- A class-confusion matrix per sensor.
- Degradations: radar sector outage and clutter, EO haze and glare, RF interference, acoustic wind noise, full sensor outage.
- Every parameter lives in sensor-profile YAML with a register ID; the loader rejects parameters without one and flags `verified: false` values.
- Sensor interface exposes a cue input (slew or narrow-field request) that wave 4b wires to tracks.

## Out of scope

- Tracker, fusion, association errors and the simulated AI assist (wave 4b).
- UI, WebSocket transport, new threat classes beyond what tests need.

## Acceptance criteria

- P(d) is monotonic non-increasing in range for every sensor, and weather and time of day shift it in the direction the model specifies (tests).
- Confusion matrices are row-normalised; RF-silent targets are never detected by RF.
- All sensor outputs are deterministic for a given seed.
- A cue request narrows the EO/IR field of view and improves its measurement precision, deterministically (test).
- `docs/SENSOR_MODELS.md` gives each model's equations, parameters with register IDs, and its honesty note (for example, thermal is a rendering model, not radiometric).
- CI is green on `main` (lint, typecheck, unit, e2e, gitleaks, docker build).
- Every feature in this wave has tests; no existing test was skipped, disabled or weakened.
- Production images build and the production-mode compose stack passes `make smoke`.
- `docs/BUILD_LOG.md` is updated per its rules, including the deploy check and the next wave entry point.
- No credentials, secrets or real keys anywhere in git history; only `.env.example` placeholders.
- The deployed build still works: the commit to deploy is recorded in the build log, and after the user redeploys, `make smoke URL=<live url>` passes.

## Prompt (paste into Claude Code, Opus)

````text
ROLE: You are building wave 4a (Sensor models) of SUDARSHAN, an AI-enabled drone and counter-drone threat simulation TRAINER (SIH 2026, PS 26247). CLAUDE.md is loaded: follow it, above all the LOCKED RULES.

READ FIRST: docs/BUILD_LOG.md (confirm wave 3 is Done and main is green; if not, stop and tell me). Then: docs/02-research.md §2 (sensor appearance and figures), docs/DATA_REGISTER.md, docs/05-architecture.md §3.2.

GOAL: Physically-motivated radar, EO/IR, RF and acoustic detection models with degradations, every parameter sourced from the data register.

STEP 1 — Sensor framework (main session)
- services/api/sim/sensors/: a Sensor interface (detect(world, t, rng) → detections with measurement noise), shared degradation hooks, a cue input, and a profile loader that rejects any parameter without a source_id.

STEP 2 — Radar and EO/IR (subagent A, worktree)
- Radar: RCS ranges, range-dependent P(d), clutter false plots, micro-Doppler cue as a classification feature (rotor vs wing-beat), sector outage.
- EO/IR: Johnson-criteria detection and recognition pixel thresholds, apparent size vs range and IFOV, day / NV / thermal modes, haze and glare.
- Values from docs/02-research.md §2 with register IDs; secondary or UNVERIFIED figures carry verified: false.

STEP 3 — RF and acoustic (subagent B, worktree)
- RF: band plan, hop-pattern presence, RF-silent flag, Wi-Fi/Bluetooth confusers, interference.
- Acoustic: blade-pass frequency and harmonics, range limit, wind-noise degradation.

STEP 4 — Tests and docs (main session)
- Tests as in the acceptance criteria.
- docs/SENSOR_MODELS.md. Add any parameter source not yet in docs/DATA_REGISTER.md to docs/OPEN_QUESTIONS.md instead of inventing an ID.

OUT OF SCOPE (do not build):
- Tracker, fusion, association errors and the simulated AI assist (wave 4b).
- UI, WebSocket transport, new threat classes beyond what tests need.

ACCEPTANCE (all must be true):
- P(d) is monotonic non-increasing in range for every sensor, and weather and time of day shift it in the direction the model specifies (tests).
- Confusion matrices are row-normalised; RF-silent targets are never detected by RF.
- All sensor outputs are deterministic for a given seed.
- A cue request narrows the EO/IR field of view and improves its measurement precision, deterministically (test).
- `docs/SENSOR_MODELS.md` gives each model's equations, parameters with register IDs, and its honesty note (for example, thermal is a rendering model, not radiometric).
- CI is green on `main` (lint, typecheck, unit, e2e, gitleaks, docker build).
- Every feature in this wave has tests; no existing test was skipped, disabled or weakened.
- Production images build and the production-mode compose stack passes `make smoke`.
- `docs/BUILD_LOG.md` is updated per its rules, including the deploy check and the next wave entry point.
- No credentials, secrets or real keys anywhere in git history; only `.env.example` placeholders.
- The deployed build still works: the commit to deploy is recorded in the build log, and after the user redeploys, `make smoke URL=<live url>` passes.

LOG: Follow the rules in docs/BUILD_LOG.md. Add a "Wave 4a" entry at the start, append each merged commit, record decisions, test counts and the deploy check, and write the exact first step of wave 4b.

STOP CONDITIONS — stop and report if:
- a step needs credentials, or network beyond package registries and GitHub;
- a Docker action would touch anything outside this repo's compose project;
- CI fails 3 times on the same cause;
- about 60% of the session is used before acceptance (commit green work, log it as wave 4a.2, stop);
- Never build features from later waves.

FINAL OUTPUT TO ME: at most 10 lines — commits, test counts, CI result, deploy check (and the commit for me to deploy), anything skipped and why, and the first step of wave 4b.
````
