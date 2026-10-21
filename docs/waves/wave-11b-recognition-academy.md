# Wave 11b · Recognition academy and progression

| | |
|---|---|
| Depends on | 4a, 8, 11a |
| Deployment | Keep the live build green. |

**Goal.** A study-and-quiz library for drone and clutter signatures built from our own sensor models, plus professional competency levels.

## Scope

- Recognition library: threat and clutter catalogues with signature views generated from our own models (radar micro-Doppler, RF waterfall, acoustic spectrogram, EO and thermal renders); no restricted clips.
- Signature explorer (study mode) and quiz mode with Leitner/SM-2 scheduling, feeding the skill model from wave 11a.
- Professional progression: competency levels per skill with stated thresholds, changing only from assessed sessions; no points, badges or leaderboards. The signed matrix and certificates come in wave 13b.

## Out of scope

- Signed records, competency matrix and certificates (wave 13b).
- Learning curves and unit trends (wave 12a).

## Acceptance criteria

- Each catalogued class has at least three generated signature views, and a 10-question quiz is reproducible from its seed and records per-class accuracy (tests).
- SM-2 scheduling tests.
- No NC/R or licence-not-stated media appears in the library (test over the asset manifest).
- A level changes only from assessed sessions meeting the documented threshold; practice sessions never change it (test).
- Screens axe-clean and bilingual.
- Every new user-facing string exists in EN and HI (key-parity check passes).
- Every new screen has populated, empty, loading and error states, works by keyboard, and is axe-clean.
- CI is green on `main` (lint, typecheck, unit, e2e, gitleaks, docker build).
- Every feature in this wave has tests; no existing test was skipped, disabled or weakened.
- Production images build and the production-mode compose stack passes `make smoke`.
- `docs/BUILD_LOG.md` is updated per its rules, including the deploy check and the next wave entry point.
- No credentials, secrets or real keys anywhere in git history; only `.env.example` placeholders.
- The deployed build still works: the commit to deploy is recorded in the build log, and after the user redeploys, `make smoke URL=<live url>` passes.

## Brief

````text
ROLE: Build wave 11b (Recognition academy and progression) of SUDARSHAN, an AI-enabled drone and counter-drone threat simulation TRAINER (SIH 2026, PS 26247). Follow the project rules in CONTRIBUTING.md, above all the content rules.

READ FIRST: docs/BUILD_LOG.md (confirm wave 11a is Done and main is green; if not, stop and tell me). Then: docs/07-ui-map.md (Recognition library, Progress), docs/DATA_REGISTER.md, docs/SENSOR_MODELS.md, docs/10-differentiators.md (H7).

GOAL: A study-and-quiz library for drone and clutter signatures built from our own sensor models, plus professional competency levels.

STEP 1 — Signature generation (track A, worktree)
- Signature renderers from the sensor models, reproducible from a seed; asset manifest with licence status.

STEP 2 — Academy screens and drills (track B, worktree)
- Explorer, quiz, SM-2 drills; Recognition library per docs/07-ui-map.md.

STEP 3 — Progression (main track)
- Level model and thresholds in the rule pack; display on Progress; tests; update docs/LEARNER_MODEL.md.

OUT OF SCOPE (do not build):
- Signed records, competency matrix and certificates (wave 13b).
- Learning curves and unit trends (wave 12a).

ACCEPTANCE (all must be true):
- Each catalogued class has at least three generated signature views, and a 10-question quiz is reproducible from its seed and records per-class accuracy (tests).
- SM-2 scheduling tests.
- No NC/R or licence-not-stated media appears in the library (test over the asset manifest).
- A level changes only from assessed sessions meeting the documented threshold; practice sessions never change it (test).
- Screens axe-clean and bilingual.
- Every new user-facing string exists in EN and HI (key-parity check passes).
- Every new screen has populated, empty, loading and error states, works by keyboard, and is axe-clean.
- CI is green on `main` (lint, typecheck, unit, e2e, gitleaks, docker build).
- Every feature in this wave has tests; no existing test was skipped, disabled or weakened.
- Production images build and the production-mode compose stack passes `make smoke`.
- `docs/BUILD_LOG.md` is updated per its rules, including the deploy check and the next wave entry point.
- No credentials, secrets or real keys anywhere in git history; only `.env.example` placeholders.
- The deployed build still works: the commit to deploy is recorded in the build log, and after the user redeploys, `make smoke URL=<live url>` passes.

LOG: Follow the rules in docs/BUILD_LOG.md. Add a "Wave 11b" entry at the start, append each merged commit, record decisions, test counts and the deploy check, and write the exact first step of wave 12a.

STOP CONDITIONS — stop and report if:
- a step needs credentials, or network beyond package registries and GitHub;
- a Docker action would touch anything outside this repo's compose project;
- CI fails 3 times on the same cause;
- about 60% of the session is used before acceptance (commit green work, log it as wave 11b.2, stop);
- Never build features from later waves.

FINAL OUTPUT TO ME: at most 10 lines — commits, test counts, CI result, deploy check (and the commit for me to deploy), anything skipped and why, and the first step of wave 12a.
````
