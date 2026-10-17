# Wave 14 · WebXR + hardening

| | |
|---|---|
| Depends on | 7, 12 |
| Recommended model | Sonnet |
| Deployment | Keep the live build green. |

**Goal.** Optional VR mode tested in the emulator, and a hardened, accessible, fast product.

## Scope

- WebXR observer and EO-operator mode behind a flag, tested in a WebXR emulator.
- Accessibility pass on every screen (keyboard, labels, reduced motion, contrast).
- Performance pass on the floor laptop.
- Visual regression snapshots for the 12 key screens.
- Security review: OWASP ASVS level 1 checklist, dependency audit, rate limits, security headers and CSP.
- Offline test with networking disabled; two-laptop LAN join test.

## Out of scope

- New features.

## Acceptance criteria

- WebXR smoke test passes in the emulator; all copy says "VR mode, emulator-tested" unless a headset test is logged.
- axe clean on every route; keyboard-only Playwright run of the main trainee and instructor flows.
- 12 visual snapshots committed and reviewed against the banned list in `docs/DESIGN.md`.
- `docs/SECURITY_REVIEW.md` lists each ASVS L1 item as pass, fail-with-fix, or not applicable.
- The full app works with networking disabled (no CDN, fonts and tiles bundled).
- Two-laptop LAN join in under 30 s, documented in the instructor SOP draft.
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
ROLE: You are building wave 14 (WebXR + hardening) of SUDARSHAN, an AI-enabled drone and counter-drone threat simulation TRAINER (SIH 2026, PS 26247). CLAUDE.md is loaded: follow it, above all the LOCKED RULES.

READ FIRST: docs/BUILD_LOG.md (confirm wave 13 is Done and main is green; if not, stop and tell me). Then: docs/04-engine.md, docs/07-ui-map.md (banned list), docs/08-demo.md (must-work list).

GOAL: Optional VR mode tested in the emulator, and a hardened, accessible, fast product.

STEP 1 — WebXR (subagent A, worktree)
- renderer.xr behind a feature flag; observer and EO views; emulator-based smoke test.

STEP 2 — Security (subagent B, worktree)
- ASVS L1 checklist, dependency audit, rate limits, CSP and security headers; docs/SECURITY_REVIEW.md.

STEP 3 — Accessibility, performance, regression (main session)
- Accessibility fixes on every route; keyboard-only flows; 12 visual snapshots; offline test; LAN join test.
- Ask me to run the performance pass on the floor laptop and record it in docs/PERFORMANCE.md.

OUT OF SCOPE (do not build):
- New features.

ACCEPTANCE (all must be true):
- WebXR smoke test passes in the emulator; all copy says "VR mode, emulator-tested" unless a headset test is logged.
- axe clean on every route; keyboard-only Playwright run of the main trainee and instructor flows.
- 12 visual snapshots committed and reviewed against the banned list in `docs/DESIGN.md`.
- `docs/SECURITY_REVIEW.md` lists each ASVS L1 item as pass, fail-with-fix, or not applicable.
- The full app works with networking disabled (no CDN, fonts and tiles bundled).
- Two-laptop LAN join in under 30 s, documented in the instructor SOP draft.
- Every new user-facing string exists in EN and HI (key-parity check passes).
- Every new screen has populated, empty, loading and error states, works by keyboard, and is axe-clean.
- CI is green on `main` (lint, typecheck, unit, e2e, gitleaks, docker build).
- Every feature in this wave has tests; no existing test was skipped, disabled or weakened.
- Production images build and the production-mode compose stack passes `make smoke`.
- `docs/BUILD_LOG.md` is updated per its rules, including the deploy check and the next wave entry point.
- No credentials, secrets or real keys anywhere in git history; only `.env.example` placeholders.
- The deployed build still works: the commit to deploy is recorded in the build log, and after the user redeploys, `make smoke URL=<live url>` passes.

LOG: Follow the rules in docs/BUILD_LOG.md. Add a "Wave 14" entry at the start, append each merged commit, record decisions, test counts and the deploy check, and write the exact first step of wave 15.

STOP CONDITIONS — stop and report if:
- a step needs credentials, or network beyond package registries and GitHub;
- a Docker action would touch anything outside this repo's compose project;
- CI fails 3 times on the same cause;
- about 60% of the session is used before acceptance (commit green work, log it as wave 14.b, stop);
- Never build features from later waves.

FINAL OUTPUT TO ME: at most 10 lines — commits, test counts, CI result, deploy check (and the commit for me to deploy), anything skipped and why, and the first step of wave 15.
````
