# Wave 13b · Signed records and competency matrix

| | |
|---|---|
| Depends on | 12a, 11b |
| Deployment | Keep the live build green. |

**Goal.** Training records can be verified, and trainee and unit competency is shown as a matrix with exportable certificates.

## Scope

- Ed25519 signature over the chain head at session end; `verify-record` CLI; record verification screen; audit log.
- Competency matrix: skills against qualification levels per trainee and per unit, from assessed sessions only.
- Certificates exported as PDF with a verification code that the record screen and CLI can check.

## Out of scope

- Admin screens and the pack manager (wave 13c).

## Acceptance criteria

- A modified record fails signature or chain verification in both the CLI and the screen, and the failure names the first broken event (test).
- The signing key comes from an env var or a mounted secret file; production refuses to start without it; no key in git.
- The matrix matches a hand-computed table for the seeded demo cohort; practice sessions never count (tests).
- A certificate's verification code validates, and fails after any change to the underlying record (test).
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
ROLE: Build wave 13b (Signed records and competency matrix) of SUDARSHAN, an AI-enabled drone and counter-drone threat simulation TRAINER (SIH 2026, PS 26247). Follow the project rules in CONTRIBUTING.md, above all the content rules.

READ FIRST: docs/BUILD_LOG.md (confirm wave 13a is Done and main is green; if not, stop and tell me). Then: docs/05-architecture.md (session records), docs/DECISIONS.md ADR-003, docs/LEARNER_MODEL.md, docs/10-differentiators.md (H8).

GOAL: Training records can be verified, and trainee and unit competency is shown as a matrix with exportable certificates.

STEP 1 — Signing and verification (track A, worktree)
- Ed25519 signing of the chain head, verify-record CLI, verification screen, audit log.

STEP 2 — Matrix and certificates (track B, worktree)
- Competency matrix, unit view, certificate PDF with verification code.

STEP 3 — Integration (main track)
- Tests as in the acceptance criteria; docs/TRUST.md; demo state shows "Record chain verified".

OUT OF SCOPE (do not build):
- Admin screens and the pack manager (wave 13c).

ACCEPTANCE (all must be true):
- A modified record fails signature or chain verification in both the CLI and the screen, and the failure names the first broken event (test).
- The signing key comes from an env var or a mounted secret file; production refuses to start without it; no key in git.
- The matrix matches a hand-computed table for the seeded demo cohort; practice sessions never count (tests).
- A certificate's verification code validates, and fails after any change to the underlying record (test).
- Screens axe-clean and bilingual.
- Every new user-facing string exists in EN and HI (key-parity check passes).
- Every new screen has populated, empty, loading and error states, works by keyboard, and is axe-clean.
- CI is green on `main` (lint, typecheck, unit, e2e, gitleaks, docker build).
- Every feature in this wave has tests; no existing test was skipped, disabled or weakened.
- Production images build and the production-mode compose stack passes `make smoke`.
- `docs/BUILD_LOG.md` is updated per its rules, including the deploy check and the next wave entry point.
- No credentials, secrets or real keys anywhere in git history; only `.env.example` placeholders.
- The deployed build still works: the commit to deploy is recorded in the build log, and after the user redeploys, `make smoke URL=<live url>` passes.

LOG: Follow the rules in docs/BUILD_LOG.md. Add a "Wave 13b" entry at the start, append each merged commit, record decisions, test counts and the deploy check, and write the exact first step of wave 13c.

STOP CONDITIONS — stop and report if:
- a step needs credentials, or network beyond package registries and GitHub;
- a Docker action would touch anything outside this repo's compose project;
- CI fails 3 times on the same cause;
- about 60% of the session is used before acceptance (commit green work, log it as wave 13b.2, stop);
- Never build features from later waves.

FINAL OUTPUT TO ME: at most 10 lines — commits, test counts, CI result, deploy check (and the commit for me to deploy), anything skipped and why, and the first step of wave 13c.
````
