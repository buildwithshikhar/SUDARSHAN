# Wave 6 · Scoring + debrief

| | |
|---|---|
| Depends on | 5 |
| Recommended model | Sonnet |
| Deployment | Redeploy: sessions on the live link now end with a scored debrief. |

**Goal.** Explainable decision-tree scoring for every threat and a debrief screen that says why.

## Scope

- Per-threat evaluator: Detect (time from first detectable moment to designation, in capped bands against a per-scenario standard), Classify (correct class, false alarms on clutter), Assess (threat level and intent), Respond (ROE-compliant action, effector choice and timing; hold fire on civil traffic).
- ROE hard-fail gate: engaging without positive ID, or engaging a neutral or friend, fails that threat.
- Plain-language node explanations from EN/HI templates; weights and thresholds from the rule pack; each score records the rule-pack and scenario versions.
- Signal-detection metrics per session: hit rate, false-alarm rate, d′ with a log-linear correction for 0 and 1 rates.
- Debrief screen: score summary, node-by-node path per threat, first three lessons.

## Out of scope

- The full AAR (wave 12).

## Acceptance criteria

- Golden event-log fixtures (at least 10, covering each node outcome and each hard-fail case) produce exactly the expected scores and explanations.
- Property test: rushing into an ROE breach never scores higher than a compliant slower response.
- d′ matches reference values for known hit and false-alarm rates.
- Debrief screen is axe-clean, bilingual, and shows rule-pack version and scenario seed.
- `docs/TRACEABILITY.md` proof cells for R5, R6, R7 and R17 point to test IDs.
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
ROLE: You are building wave 6 (Scoring + debrief) of SUDARSHAN, an AI-enabled drone and counter-drone threat simulation TRAINER (SIH 2026, PS 26247). CLAUDE.md is loaded: follow it, above all the LOCKED RULES.

READ FIRST: docs/BUILD_LOG.md (confirm wave 5 is Done and main is green; if not, stop and tell me). Then: docs/02-research.md §4 (scoring and ROE), docs/05-architecture.md §3.3, docs/07-ui-map.md (Debrief).

GOAL: Explainable decision-tree scoring for every threat and a debrief screen that says why.

STEP 1 — Evaluator (main session)
- services/api/app/scoring/: tree walk per threat over the event log and ground truth; node results with score, reason key and parameters.
- ROE hard-fail gate; capped timing bands; weights from the rule pack.
- SDT metrics with a log-linear correction.

STEP 2 — Fixtures and tests (subagent A, worktree)
- At least 10 golden logs with expected outputs; hypothesis property test for the no-reward-for-breach rule.

STEP 3 — Debrief UI (subagent B, worktree)
- Debrief screen per docs/07-ui-map.md; explanations rendered from EN/HI templates; empty, loading and error states.

STEP 4 — Docs
- docs/SCORING.md (tree, weights, explanation templates, honesty note that timing standards are fictional and editable). Update docs/TRACEABILITY.md proof cells.

OUT OF SCOPE (do not build):
- The full AAR (wave 12).

ACCEPTANCE (all must be true):
- Golden event-log fixtures (at least 10, covering each node outcome and each hard-fail case) produce exactly the expected scores and explanations.
- Property test: rushing into an ROE breach never scores higher than a compliant slower response.
- d′ matches reference values for known hit and false-alarm rates.
- Debrief screen is axe-clean, bilingual, and shows rule-pack version and scenario seed.
- `docs/TRACEABILITY.md` proof cells for R5, R6, R7 and R17 point to test IDs.
- Every new user-facing string exists in EN and HI (key-parity check passes).
- Every new screen has populated, empty, loading and error states, works by keyboard, and is axe-clean.
- CI is green on `main` (lint, typecheck, unit, e2e, gitleaks, docker build).
- Every feature in this wave has tests; no existing test was skipped, disabled or weakened.
- Production images build and the production-mode compose stack passes `make smoke`.
- `docs/BUILD_LOG.md` is updated per its rules, including the deploy check and the next wave entry point.
- No credentials, secrets or real keys anywhere in git history; only `.env.example` placeholders.
- The deployed build still works: the commit to deploy is recorded in the build log, and after the user redeploys, `make smoke URL=<live url>` passes.

LOG: Follow the rules in docs/BUILD_LOG.md. Add a "Wave 6" entry at the start, append each merged commit, record decisions, test counts and the deploy check, and write the exact first step of wave 7.

STOP CONDITIONS — stop and report if:
- a step needs credentials, or network beyond package registries and GitHub;
- a Docker action would touch anything outside this repo's compose project;
- CI fails 3 times on the same cause;
- about 60% of the session is used before acceptance (commit green work, log it as wave 6.b, stop);
- Never build features from later waves.

FINAL OUTPUT TO ME: at most 10 lines — commits, test counts, CI result, deploy check (and the commit for me to deploy), anything skipped and why, and the first step of wave 7.
````
