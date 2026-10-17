# Wave 10 · Instructor console

| | |
|---|---|
| Depends on | 5, 9 |
| Recommended model | Sonnet |
| Deployment | Keep the live build green. |

**Goal.** Instructors can run a class: cohorts, launch, live monitor with ground truth, pause, inject and annotate.

## Scope

- Cohorts and trainees (list, detail, notes); curricula list and editor (stages and gates).
- Launch session: scenario, participants, mode (assessed or practice).
- Live monitor: class grid, trainee drill-down with ground-truth overlay, pause and resume, inject macros (time jump, weather, sensor outage, add threat), timeline annotations.
- Rule-pack list and editor (ROE rules, weights, thresholds, version diff).
- Team setup skeleton (role assignment, sector split) for wave 13.
- Instructor actions are logged as events in the hash chain.

## Out of scope

- Handoff scoring (wave 13), the full AAR (wave 12).

## Acceptance criteria

- Instructor frames carry ground truth; trainee frames still never do (test).
- One inject macro applies night + fog + radar sector outage + an RF-silent drone at once (the 08 demo beat) and is logged.
- Pause and resume keep determinism: replay of a paused session matches (test).
- Rule-pack edits create a new version; scores always record the version used.
- RBAC tests for every instructor endpoint; screens axe-clean and bilingual.
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
ROLE: You are building wave 10 (Instructor console) of SUDARSHAN, an AI-enabled drone and counter-drone threat simulation TRAINER (SIH 2026, PS 26247). CLAUDE.md is loaded: follow it, above all the LOCKED RULES.

READ FIRST: docs/BUILD_LOG.md (confirm wave 9 is Done and main is green; if not, stop and tell me). Then: docs/07-ui-map.md (Instructor), docs/08-demo.md (beats 0:45–7:00).

GOAL: Instructors can run a class: cohorts, launch, live monitor with ground truth, pause, inject and annotate.

STEP 1 — Class management (subagent A, worktree)
- Cohorts, trainees, curricula (stages and gates), launch session flow; API and screens.

STEP 2 — Live monitor (subagent B, worktree)
- Instructor WS channel with ground truth; class grid; drill-down overlay; pause/resume; inject macros; annotations, all logged as instructor events.

STEP 3 — Rule packs (main session)
- Rule-pack list and editor with versioning and diff; team setup skeleton.
- Tests as in the acceptance criteria. Update docs/TRACEABILITY.md (R4, R13).

OUT OF SCOPE (do not build):
- Handoff scoring (wave 13), the full AAR (wave 12).

ACCEPTANCE (all must be true):
- Instructor frames carry ground truth; trainee frames still never do (test).
- One inject macro applies night + fog + radar sector outage + an RF-silent drone at once (the 08 demo beat) and is logged.
- Pause and resume keep determinism: replay of a paused session matches (test).
- Rule-pack edits create a new version; scores always record the version used.
- RBAC tests for every instructor endpoint; screens axe-clean and bilingual.
- Every new user-facing string exists in EN and HI (key-parity check passes).
- Every new screen has populated, empty, loading and error states, works by keyboard, and is axe-clean.
- CI is green on `main` (lint, typecheck, unit, e2e, gitleaks, docker build).
- Every feature in this wave has tests; no existing test was skipped, disabled or weakened.
- Production images build and the production-mode compose stack passes `make smoke`.
- `docs/BUILD_LOG.md` is updated per its rules, including the deploy check and the next wave entry point.
- No credentials, secrets or real keys anywhere in git history; only `.env.example` placeholders.
- The deployed build still works: the commit to deploy is recorded in the build log, and after the user redeploys, `make smoke URL=<live url>` passes.

LOG: Follow the rules in docs/BUILD_LOG.md. Add a "Wave 10" entry at the start, append each merged commit, record decisions, test counts and the deploy check, and write the exact first step of wave 11.

STOP CONDITIONS — stop and report if:
- a step needs credentials, or network beyond package registries and GitHub;
- a Docker action would touch anything outside this repo's compose project;
- CI fails 3 times on the same cause;
- about 60% of the session is used before acceptance (commit green work, log it as wave 10.b, stop);
- Never build features from later waves.

FINAL OUTPUT TO ME: at most 10 lines — commits, test counts, CI result, deploy check (and the commit for me to deploy), anything skipped and why, and the first step of wave 11.
````
