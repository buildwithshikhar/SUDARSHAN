# Wave 13a · Team mode

| | |
|---|---|
| Depends on | 10b, 12a, 4b |
| Deployment | Keep the live build green. |

**Goal.** An operator and a detachment commander work one picture with sector split and track handover, and the handover is scored.

## Scope

- Team mode: operator and detachment-commander roles, sector split, per-role sensor frames.
- Track handover: handing a track to the other role carries its identity and history; the receiving role acknowledges it.
- Handoff scoring nodes; team monitor view for the instructor.

## Out of scope

- Signed records and certificates (wave 13b).
- Admin and pack manager (wave 13c).

## Acceptance criteria

- A handed-over track keeps its ID and history in the receiving operator's track table (test).
- Per-role frames still contain no ground truth, and a role sees only its sector plus handed tracks (test).
- Handoff scoring golden-log tests.
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
ROLE: Build wave 13a (Team mode) of SUDARSHAN, an AI-enabled drone and counter-drone threat simulation TRAINER (SIH 2026, PS 26247). Follow the project rules in CONTRIBUTING.md, above all the content rules.

READ FIRST: docs/BUILD_LOG.md (confirm wave 12b is Done and main is green; if not, stop and tell me). Then: docs/07-ui-map.md (Team exercise), docs/05-architecture.md, docs/SENSOR_MODELS.md (tracking), docs/10-differentiators.md (H5).

GOAL: An operator and a detachment commander work one picture with sector split and track handover, and the handover is scored.

STEP 1 — Roles and sectors (track A, worktree)
- Roles, sector split, per-role frames over WS.

STEP 2 — Handover and scoring (track B, worktree)
- Handover protocol with history, acknowledgement, handoff scoring nodes, team monitor view.

STEP 3 — Integration (main track)
- Tests as in the acceptance criteria; docs/TEAM_MODE.md.

OUT OF SCOPE (do not build):
- Signed records and certificates (wave 13b).
- Admin and pack manager (wave 13c).

ACCEPTANCE (all must be true):
- A handed-over track keeps its ID and history in the receiving operator's track table (test).
- Per-role frames still contain no ground truth, and a role sees only its sector plus handed tracks (test).
- Handoff scoring golden-log tests.
- Screens axe-clean and bilingual.
- Every new user-facing string exists in EN and HI (key-parity check passes).
- Every new screen has populated, empty, loading and error states, works by keyboard, and is axe-clean.
- CI is green on `main` (lint, typecheck, unit, e2e, gitleaks, docker build).
- Every feature in this wave has tests; no existing test was skipped, disabled or weakened.
- Production images build and the production-mode compose stack passes `make smoke`.
- `docs/BUILD_LOG.md` is updated per its rules, including the deploy check and the next wave entry point.
- No credentials, secrets or real keys anywhere in git history; only `.env.example` placeholders.
- The deployed build still works: the commit to deploy is recorded in the build log, and after the user redeploys, `make smoke URL=<live url>` passes.

LOG: Follow the rules in docs/BUILD_LOG.md. Add a "Wave 13a" entry at the start, append each merged commit, record decisions, test counts and the deploy check, and write the exact first step of wave 13b.

STOP CONDITIONS — stop and report if:
- a step needs credentials, or network beyond package registries and GitHub;
- a Docker action would touch anything outside this repo's compose project;
- CI fails 3 times on the same cause;
- about 60% of the session is used before acceptance (commit green work, log it as wave 13a.2, stop);
- Never build features from later waves.

FINAL OUTPUT TO ME: at most 10 lines — commits, test counts, CI result, deploy check (and the commit for me to deploy), anything skipped and why, and the first step of wave 13b.
````
