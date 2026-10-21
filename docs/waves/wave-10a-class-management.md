# Wave 10a · Class management and rule packs

| | |
|---|---|
| Depends on | 5, 9a |
| Deployment | Keep the live build green. |

**Goal.** Instructors can manage cohorts, curricula and rule packs, and launch sessions.

## Scope

- Cohorts and trainees (list, detail, notes); curricula list and editor (stages and gates).
- Launch session: scenario, participants, mode (assessed or practice).
- Rule-pack list and editor (ROE rules, weights, thresholds, version diff).
- Team setup skeleton (role assignment, sector split) for wave 13a.
- Instructor actions are logged as events in the hash chain.

## Out of scope

- Live monitor and director mode (wave 10b).
- Handoff scoring (wave 13a), the full AAR (wave 12).

## Acceptance criteria

- Rule-pack edits create a new version; scores always record the version used.
- A curriculum gate blocks launch of a stage until the previous stage's threshold is met (test).
- RBAC tests for every instructor endpoint; screens axe-clean and bilingual.
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
ROLE: Build wave 10a (Class management and rule packs) of SUDARSHAN, an AI-enabled drone and counter-drone threat simulation TRAINER (SIH 2026, PS 26247). Follow the project rules in CONTRIBUTING.md, above all the content rules.

READ FIRST: docs/BUILD_LOG.md (confirm wave 9c is Done and main is green; if not, stop and tell me). Then: docs/07-ui-map.md (Instructor), docs/08-demo.md (beat 0:45–2:00).

GOAL: Instructors can manage cohorts, curricula and rule packs, and launch sessions.

STEP 1 — Class management (track A, worktree)
- Cohorts, trainees, curricula (stages and gates), launch session flow; API and screens.

STEP 2 — Rule packs and team skeleton (track B, worktree)
- Rule-pack list and editor with versioning and diff; team setup skeleton.

STEP 3 — Integration (main track)
- Instructor events in the hash chain; tests as in the acceptance criteria; update docs/TRACEABILITY.md (R4, R13).

OUT OF SCOPE (do not build):
- Live monitor and director mode (wave 10b).
- Handoff scoring (wave 13a), the full AAR (wave 12).

ACCEPTANCE (all must be true):
- Rule-pack edits create a new version; scores always record the version used.
- A curriculum gate blocks launch of a stage until the previous stage's threshold is met (test).
- RBAC tests for every instructor endpoint; screens axe-clean and bilingual.
- Every new user-facing string exists in EN and HI (key-parity check passes).
- Every new screen has populated, empty, loading and error states, works by keyboard, and is axe-clean.
- CI is green on `main` (lint, typecheck, unit, e2e, gitleaks, docker build).
- Every feature in this wave has tests; no existing test was skipped, disabled or weakened.
- Production images build and the production-mode compose stack passes `make smoke`.
- `docs/BUILD_LOG.md` is updated per its rules, including the deploy check and the next wave entry point.
- No credentials, secrets or real keys anywhere in git history; only `.env.example` placeholders.
- The deployed build still works: the commit to deploy is recorded in the build log, and after the user redeploys, `make smoke URL=<live url>` passes.

LOG: Follow the rules in docs/BUILD_LOG.md. Add a "Wave 10a" entry at the start, append each merged commit, record decisions, test counts and the deploy check, and write the exact first step of wave 10b.

STOP CONDITIONS — stop and report if:
- a step needs credentials, or network beyond package registries and GitHub;
- a Docker action would touch anything outside this repo's compose project;
- CI fails 3 times on the same cause;
- about 60% of the session is used before acceptance (commit green work, log it as wave 10a.2, stop);
- Never build features from later waves.

FINAL OUTPUT TO ME: at most 10 lines — commits, test counts, CI result, deploy check (and the commit for me to deploy), anything skipped and why, and the first step of wave 10b.
````
