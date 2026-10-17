# Wave 4b · Tracking, fusion and AI assist

| | |
|---|---|
| Depends on | 4a |
| Recommended model | Opus |
| Deployment | Keep the live build green. No new user-facing feature. |

**Goal.** A tracker that fuses the four sensors, fails in the ways real trackers fail (swaps, splits, merges), supports sensor cueing, and a seeded simulated AI assist.

## Scope

- Tracker and fusion: gated nearest-neighbour association with an alpha-beta or Kalman filter; track lifecycle (tentative, confirmed, coasting, dropped).
- Association errors: track swaps at crossings, split tracks and merged tracks, driven by geometry and clutter with a seeded RNG stream, each logged with the true identities.
- Track commands: merge, split, relabel and drop, applied through the action log and reversible only by a further logged command.
- Sensor cueing: cue a sensor onto a track (wave 4a cue input), logged as an action.
- Simulated AI assist: seeded, with configured hit and false-alarm rates and a confidence output. No real detector and no accuracy claim.

## Out of scope

- Track handover between operators (wave 13a).
- UI and WebSocket transport (wave 5).
- Scoring of unfixed errors (wave 6).

## Acceptance criteria

- Tracker tests: track initiation, association under clutter, coasting through a short outage.
- With a seeded crossing geometry the tracker produces a swap at a documented tick; a relabel command restores the true identity in the log (test).
- Association errors are deterministic for a given seed and never occur for well-separated targets.
- Over N seeded trials the AI assist's empirical hit and false-alarm rates fall within a stated tolerance of the configured values.
- `docs/SENSOR_MODELS.md` gains a tracking section describing the error model and its parameters.
- CI is green on `main` (lint, typecheck, unit, e2e, gitleaks, docker build).
- Every feature in this wave has tests; no existing test was skipped, disabled or weakened.
- Production images build and the production-mode compose stack passes `make smoke`.
- `docs/BUILD_LOG.md` is updated per its rules, including the deploy check and the next wave entry point.
- No credentials, secrets or real keys anywhere in git history; only `.env.example` placeholders.
- The deployed build still works: the commit to deploy is recorded in the build log, and after the user redeploys, `make smoke URL=<live url>` passes.

## Prompt (paste into Claude Code, Opus)

````text
ROLE: You are building wave 4b (Tracking, fusion and AI assist) of SUDARSHAN, an AI-enabled drone and counter-drone threat simulation TRAINER (SIH 2026, PS 26247). CLAUDE.md is loaded: follow it, above all the LOCKED RULES.

READ FIRST: docs/BUILD_LOG.md (confirm wave 4a is Done and main is green; if not, stop and tell me). Then: docs/10-differentiators.md (H5), docs/SENSOR_MODELS.md, docs/05-architecture.md §3.2.

GOAL: A tracker that fuses the four sensors, fails in the ways real trackers fail (swaps, splits, merges), supports sensor cueing, and a seeded simulated AI assist.

STEP 1 — Tracker (main session)
- services/api/sim/tracking/: gated nearest-neighbour association, alpha-beta or Kalman filter, track lifecycle.

STEP 2 — Association errors and commands (subagent A, worktree)
- Swap, split and merge modes from geometry and clutter, seeded; true-identity ground truth kept for scoring.
- Track command handlers (merge, split, relabel, drop) and cue-to-track, all as logged actions.

STEP 3 — AI assist (subagent B, worktree)
- Seeded classifier over fused tracks with configured hit / false-alarm rates and a confidence value.

STEP 4 — Tests and docs (main session)
- Tests as in the acceptance criteria; update docs/SENSOR_MODELS.md.

OUT OF SCOPE (do not build):
- Track handover between operators (wave 13a).
- UI and WebSocket transport (wave 5).
- Scoring of unfixed errors (wave 6).

ACCEPTANCE (all must be true):
- Tracker tests: track initiation, association under clutter, coasting through a short outage.
- With a seeded crossing geometry the tracker produces a swap at a documented tick; a relabel command restores the true identity in the log (test).
- Association errors are deterministic for a given seed and never occur for well-separated targets.
- Over N seeded trials the AI assist's empirical hit and false-alarm rates fall within a stated tolerance of the configured values.
- `docs/SENSOR_MODELS.md` gains a tracking section describing the error model and its parameters.
- CI is green on `main` (lint, typecheck, unit, e2e, gitleaks, docker build).
- Every feature in this wave has tests; no existing test was skipped, disabled or weakened.
- Production images build and the production-mode compose stack passes `make smoke`.
- `docs/BUILD_LOG.md` is updated per its rules, including the deploy check and the next wave entry point.
- No credentials, secrets or real keys anywhere in git history; only `.env.example` placeholders.
- The deployed build still works: the commit to deploy is recorded in the build log, and after the user redeploys, `make smoke URL=<live url>` passes.

LOG: Follow the rules in docs/BUILD_LOG.md. Add a "Wave 4b" entry at the start, append each merged commit, record decisions, test counts and the deploy check, and write the exact first step of wave 5.

STOP CONDITIONS — stop and report if:
- a step needs credentials, or network beyond package registries and GitHub;
- a Docker action would touch anything outside this repo's compose project;
- CI fails 3 times on the same cause;
- about 60% of the session is used before acceptance (commit green work, log it as wave 4b.2, stop);
- Never build features from later waves.

FINAL OUTPUT TO ME: at most 10 lines — commits, test counts, CI result, deploy check (and the commit for me to deploy), anything skipped and why, and the first step of wave 5.
````
