# Wave 13 · Team mode, trust and admin

| | |
|---|---|
| Depends on | 10, 12 |
| Recommended model | Sonnet |
| Deployment | Keep the live build green. |

**Goal.** Operator plus detachment-commander team play, signed session records, and full administration.

## Scope

- Team mode: operator and detachment-commander roles, sector split, track handoff, handoff scoring.
- Ed25519 signature over the chain head at session end; `verify-record` CLI; record verification screen.
- Admin: users and roles, units, pack manager (import and export), data-register viewer, audit log, instance settings, system health, backup and restore.

## Out of scope

- WebXR (wave 14).

## Acceptance criteria

- Handoff scoring golden-log tests.
- A modified record fails signature or chain verification in both the CLI and the screen (test).
- The signing key comes from an env var or a mounted secret file; production refuses to start without it; no key in git.
- Backup then restore into an empty database reproduces all sessions (test).
- Admin cannot see trainee scores unless also an instructor (RBAC test).
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
ROLE: You are building wave 13 (Team mode, trust and admin) of SUDARSHAN, an AI-enabled drone and counter-drone threat simulation TRAINER (SIH 2026, PS 26247). CLAUDE.md is loaded: follow it, above all the LOCKED RULES.

READ FIRST: docs/BUILD_LOG.md (confirm wave 12 is Done and main is green; if not, stop and tell me). Then: docs/07-ui-map.md (Admin, Team exercise), docs/05-architecture.md (session records), docs/DECISIONS.md ADR-003.

GOAL: Operator plus detachment-commander team play, signed session records, and full administration.

STEP 1 — Team mode (subagent A, worktree)
- Roles, sector split, handoff protocol over WS, handoff scoring nodes, team monitor view.

STEP 2 — Trust (subagent B, worktree)
- Ed25519 signing of the chain head, verify-record CLI, record verification screen, audit log.

STEP 3 — Admin (main session)
- Users and roles, units, pack manager, data-register viewer (from a machine-readable copy of docs/DATA_REGISTER.md), instance settings, system health, backup and restore.
- Tests as in the acceptance criteria.

OUT OF SCOPE (do not build):
- WebXR (wave 14).

ACCEPTANCE (all must be true):
- Handoff scoring golden-log tests.
- A modified record fails signature or chain verification in both the CLI and the screen (test).
- The signing key comes from an env var or a mounted secret file; production refuses to start without it; no key in git.
- Backup then restore into an empty database reproduces all sessions (test).
- Admin cannot see trainee scores unless also an instructor (RBAC test).
- Screens axe-clean and bilingual.
- Every new user-facing string exists in EN and HI (key-parity check passes).
- Every new screen has populated, empty, loading and error states, works by keyboard, and is axe-clean.
- CI is green on `main` (lint, typecheck, unit, e2e, gitleaks, docker build).
- Every feature in this wave has tests; no existing test was skipped, disabled or weakened.
- Production images build and the production-mode compose stack passes `make smoke`.
- `docs/BUILD_LOG.md` is updated per its rules, including the deploy check and the next wave entry point.
- No credentials, secrets or real keys anywhere in git history; only `.env.example` placeholders.
- The deployed build still works: the commit to deploy is recorded in the build log, and after the user redeploys, `make smoke URL=<live url>` passes.

LOG: Follow the rules in docs/BUILD_LOG.md. Add a "Wave 13" entry at the start, append each merged commit, record decisions, test counts and the deploy check, and write the exact first step of wave 14.

STOP CONDITIONS — stop and report if:
- a step needs credentials, or network beyond package registries and GitHub;
- a Docker action would touch anything outside this repo's compose project;
- CI fails 3 times on the same cause;
- about 60% of the session is used before acceptance (commit green work, log it as wave 13.b, stop);
- Never build features from later waves.

FINAL OUTPUT TO ME: at most 10 lines — commits, test counts, CI result, deploy check (and the commit for me to deploy), anything skipped and why, and the first step of wave 14.
````
