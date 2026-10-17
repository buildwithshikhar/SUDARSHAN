# Wave 11 · Adaptive learning + recognition library

| | |
|---|---|
| Depends on | 6, 9 |
| Recommended model | Sonnet |
| Deployment | Keep the live build green. |

**Goal.** Per-skill proficiency, next-drill recommendation and spaced-repetition signature drills.

## Scope

- Skill tags on scored nodes (for example classify-FPV-at-night).
- Elo per skill with decaying K; BKT with hand-set parameters for the "mastered" display only.
- Policy: aim at ~85% predicted success (a heuristic) plus spaced-repetition due skills → next difficulty vector and focus → generator.
- Trainee screens: Today (recommended drill, skills due, last session), Quick drill, Progress (skill proficiency).
- Recognition library: threat and clutter catalogues with signature views generated from our own models (no restricted clips), and Leitner/SM-2 signature drills.

## Out of scope

- Learning curves and unit trends (wave 12).

## Acceptance criteria

- Simulated-learner test: Elo skill estimates correlate with true skill after about 10 observations, at the level reported in the research brief.
- The policy's predicted success stays near the target on simulated learners; the UI calls the target a heuristic.
- SM-2 scheduling tests.
- No NC/R or licence-not-stated media appears in the library (test over the asset manifest).
- Screens axe-clean and bilingual.
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
ROLE: You are building wave 11 (Adaptive learning + recognition library) of SUDARSHAN, an AI-enabled drone and counter-drone threat simulation TRAINER (SIH 2026, PS 26247). CLAUDE.md is loaded: follow it, above all the LOCKED RULES.

READ FIRST: docs/BUILD_LOG.md (confirm wave 10 is Done and main is green; if not, stop and tell me). Then: docs/02-research.md §5, docs/05-architecture.md §3.5, docs/07-ui-map.md (Today, Recognition library, Progress).

GOAL: Per-skill proficiency, next-drill recommendation and spaced-repetition signature drills.

STEP 1 — Learner model (subagent A, worktree)
- services/api/app/learner/: skill taxonomy, Elo with decaying K, BKT display, policy, recommendation endpoint.

STEP 2 — Recognition library (subagent B, worktree)
- Threat and clutter catalogues with generated signature views (radar micro-Doppler sketch, RF waterfall, spectrogram, EO/thermal renders) and SM-2 drills.

STEP 3 — Trainee screens (main session)
- Today, Quick drill, Progress. Tests as in the acceptance criteria. docs/LEARNER_MODEL.md with the heuristic labelled as such.

OUT OF SCOPE (do not build):
- Learning curves and unit trends (wave 12).

ACCEPTANCE (all must be true):
- Simulated-learner test: Elo skill estimates correlate with true skill after about 10 observations, at the level reported in the research brief.
- The policy's predicted success stays near the target on simulated learners; the UI calls the target a heuristic.
- SM-2 scheduling tests.
- No NC/R or licence-not-stated media appears in the library (test over the asset manifest).
- Screens axe-clean and bilingual.
- Every new user-facing string exists in EN and HI (key-parity check passes).
- Every new screen has populated, empty, loading and error states, works by keyboard, and is axe-clean.
- CI is green on `main` (lint, typecheck, unit, e2e, gitleaks, docker build).
- Every feature in this wave has tests; no existing test was skipped, disabled or weakened.
- Production images build and the production-mode compose stack passes `make smoke`.
- `docs/BUILD_LOG.md` is updated per its rules, including the deploy check and the next wave entry point.
- No credentials, secrets or real keys anywhere in git history; only `.env.example` placeholders.
- The deployed build still works: the commit to deploy is recorded in the build log, and after the user redeploys, `make smoke URL=<live url>` passes.

LOG: Follow the rules in docs/BUILD_LOG.md. Add a "Wave 11" entry at the start, append each merged commit, record decisions, test counts and the deploy check, and write the exact first step of wave 12.

STOP CONDITIONS — stop and report if:
- a step needs credentials, or network beyond package registries and GitHub;
- a Docker action would touch anything outside this repo's compose project;
- CI fails 3 times on the same cause;
- about 60% of the session is used before acceptance (commit green work, log it as wave 11.b, stop);
- Never build features from later waves.

FINAL OUTPUT TO ME: at most 10 lines — commits, test counts, CI result, deploy check (and the commit for me to deploy), anything skipped and why, and the first step of wave 12.
````
