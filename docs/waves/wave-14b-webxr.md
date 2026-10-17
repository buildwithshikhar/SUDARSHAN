# Wave 14b · WebXR (optional)

| | |
|---|---|
| Depends on | 14a |
| Recommended model | Sonnet |
| Deployment | Keep the live build green. |

**Goal.** An optional VR observer and EO-operator mode behind a flag, tested in an emulator. May be skipped without blocking release 1.0.

## Scope

- WebXR observer and EO-operator mode behind a feature flag, tested in a WebXR emulator.
- Comfort defaults (snap turn, vignette off by default, fixed horizon) and a clear fallback to the desktop view.

## Out of scope

- Any claim of headset testing unless a headset test is logged (see OPEN_QUESTIONS Q-14).
- New features.

## Acceptance criteria

- WebXR smoke test passes in the emulator; all copy says "VR mode, emulator-tested" unless a headset test is logged.
- With the flag off, the bundle and the desktop path are unchanged (size check and e2e).
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
ROLE: You are building wave 14b (WebXR (optional)) of SUDARSHAN, an AI-enabled drone and counter-drone threat simulation TRAINER (SIH 2026, PS 26247). CLAUDE.md is loaded: follow it, above all the LOCKED RULES.

READ FIRST: docs/BUILD_LOG.md (confirm wave 14a is Done and main is green; if not, stop and tell me). Then: docs/04-engine.md, docs/OPEN_QUESTIONS.md (Q-14).

GOAL: An optional VR observer and EO-operator mode behind a flag, tested in an emulator. May be skipped without blocking release 1.0.

STEP 1 — WebXR (main session)
- renderer.xr behind a feature flag; observer and EO views; emulator-based smoke test; comfort defaults.

OUT OF SCOPE (do not build):
- Any claim of headset testing unless a headset test is logged (see OPEN_QUESTIONS Q-14).
- New features.

ACCEPTANCE (all must be true):
- WebXR smoke test passes in the emulator; all copy says "VR mode, emulator-tested" unless a headset test is logged.
- With the flag off, the bundle and the desktop path are unchanged (size check and e2e).
- Every new user-facing string exists in EN and HI (key-parity check passes).
- Every new screen has populated, empty, loading and error states, works by keyboard, and is axe-clean.
- CI is green on `main` (lint, typecheck, unit, e2e, gitleaks, docker build).
- Every feature in this wave has tests; no existing test was skipped, disabled or weakened.
- Production images build and the production-mode compose stack passes `make smoke`.
- `docs/BUILD_LOG.md` is updated per its rules, including the deploy check and the next wave entry point.
- No credentials, secrets or real keys anywhere in git history; only `.env.example` placeholders.
- The deployed build still works: the commit to deploy is recorded in the build log, and after the user redeploys, `make smoke URL=<live url>` passes.

LOG: Follow the rules in docs/BUILD_LOG.md. Add a "Wave 14b" entry at the start, append each merged commit, record decisions, test counts and the deploy check, and write the exact first step of wave 15.

STOP CONDITIONS — stop and report if:
- a step needs credentials, or network beyond package registries and GitHub;
- a Docker action would touch anything outside this repo's compose project;
- CI fails 3 times on the same cause;
- about 60% of the session is used before acceptance (commit green work, log it as wave 14b.2, stop);
- Never build features from later waves.

FINAL OUTPUT TO ME: at most 10 lines — commits, test counts, CI result, deploy check (and the commit for me to deploy), anything skipped and why, and the first step of wave 15.
````
