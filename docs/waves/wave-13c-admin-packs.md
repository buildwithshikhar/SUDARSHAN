# Wave 13c · Admin and pack manager

| | |
|---|---|
| Depends on | 13b, 9a |
| Recommended model | Sonnet |
| Deployment | Keep the live build green. |

**Goal.** Administrators manage users, units, instance settings and packs, and can back up and restore.

## Scope

- Admin: users and roles, units, data-register viewer, instance settings, system health, backup and restore.
- Pack manager: import and export of scenario, rule and site packs, signed with the key from wave 13b; manifest of file hashes verified on import.

## Out of scope

- WebXR (wave 14b).
- New features.

## Acceptance criteria

- A pack with one tampered file is rejected on import, naming the file (test); an unsigned pack is flagged as unsigned.
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
ROLE: You are building wave 13c (Admin and pack manager) of SUDARSHAN, an AI-enabled drone and counter-drone threat simulation TRAINER (SIH 2026, PS 26247). CLAUDE.md is loaded: follow it, above all the LOCKED RULES.

READ FIRST: docs/BUILD_LOG.md (confirm wave 13b is Done and main is green; if not, stop and tell me). Then: docs/07-ui-map.md (Admin), docs/TRUST.md, docs/SCENARIO_ENGINE.md, docs/10-differentiators.md (H10).

GOAL: Administrators manage users, units, instance settings and packs, and can back up and restore.

STEP 1 — Users, units and settings (subagent A, worktree)
- Users and roles, units, instance settings, system health.

STEP 2 — Packs and backup (subagent B, worktree)
- Pack manager with signing and verification, backup and restore.

STEP 3 — Integration (main session)
- Data-register viewer (from a machine-readable copy of docs/DATA_REGISTER.md); tests as in the acceptance criteria.

OUT OF SCOPE (do not build):
- WebXR (wave 14b).
- New features.

ACCEPTANCE (all must be true):
- A pack with one tampered file is rejected on import, naming the file (test); an unsigned pack is flagged as unsigned.
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

LOG: Follow the rules in docs/BUILD_LOG.md. Add a "Wave 13c" entry at the start, append each merged commit, record decisions, test counts and the deploy check, and write the exact first step of wave 14a.

STOP CONDITIONS — stop and report if:
- a step needs credentials, or network beyond package registries and GitHub;
- a Docker action would touch anything outside this repo's compose project;
- CI fails 3 times on the same cause;
- about 60% of the session is used before acceptance (commit green work, log it as wave 13c.2, stop);
- Never build features from later waves.

FINAL OUTPUT TO ME: at most 10 lines — commits, test counts, CI result, deploy check (and the commit for me to deploy), anything skipped and why, and the first step of wave 14a.
````
