# Wave 9a · Scenario engine

| | |
|---|---|
| Depends on | 6, 8 |
| Deployment | Redeploy: generated and scripted scenarios on the live link. |

**Goal.** A seeded procedural generator whose scenarios are verified solvable by test run and diverse against each trainee's history, a YAML scenario language with validator and linter, plus the scripted library and editor.

## Scope

- Generator: request (difficulty vector, terrain, time of day, weather, threat mix, seed) → seeded sample → hard constraints by rejection → headless oracle-defender run → accept only if the oracle reaches max score in time → feature vector → diversity check against the trainee's history → store spec, hash and every check result.
- Retry budget, then relax the softest constraint and log it.
- MAP-Elites archive over 2–3 features; coverage, QD-score and mean pairwise distance; expressive-range heat-map data.
- Scenario authoring language: a YAML form of `scenario.v1` with a schema validator, a linter (timings below the minimum reaction window, missing sensor coverage, ROE inconsistencies, unreachable waypoints) that reports line numbers, and seed sharing (a short code carrying request, seed and generator version).
- Scripted library: a curriculum pack covering day/night, degraded sensors, urban/rural, single drone and swarm.
- Instructor screens: scenario library, scenario editor (terrain pack, threat timeline, sensors and degradations, weather and light, validation, preview run), generator studio.

## Out of scope

- Site builder (wave 9b) and sensor placement trainer (wave 9c).
- Adaptive selection of the difficulty vector (wave 11a).
- Signed scenario packs (wave 13c).

## Acceptance criteria

- Same seed and generator version give a byte-identical spec (test).
- Oracle solvability check passes on 1,000 seeds (nightly CI job; a 50-seed subset on every push).
- Diversity filter rejects a candidate closer than the threshold to the trainee's history (test).
- A scenario with a threat timed before the minimum reaction window fails lint with the offending line number; a seed-share code round-trips to an identical spec (tests).
- Every UI, doc and API string says "verified solvable by test run"; a test greps for "provably" and "guaranteed" and fails if found.
- Editor and studio are axe-clean and bilingual; the validation panel shows solvability, diversity and lint results.
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
ROLE: Build wave 9a (Scenario engine) of SUDARSHAN, an AI-enabled drone and counter-drone threat simulation TRAINER (SIH 2026, PS 26247). Follow the project rules in CONTRIBUTING.md, above all the content rules.

READ FIRST: docs/BUILD_LOG.md (confirm wave 8 is Done and main is green; if not, stop and tell me). Then: docs/02-research.md §6, docs/05-architecture.md §3.1, docs/07-ui-map.md (Scenarios, Generator), docs/DECISIONS.md ADR-008, docs/10-differentiators.md (H10).

GOAL: A seeded procedural generator whose scenarios are verified solvable by test run and diverse against each trainee's history, a YAML scenario language with validator and linter, plus the scripted library and editor.

STEP 1 — Generator core (main track)
- services/api/app/scenarios/generator.py: request model, seeded sampler, hard constraints (ROE-consistent, sensor coverage exists, timing windows ≥ minimum reaction time), retry budget with logged relaxation.
- Oracle defender: a perfect-policy agent using the same sim core and the ROE tree.

STEP 2 — Diversity and language (track A, worktree)
- Feature vector, kNN distance to the trainee's history, MAP-Elites archive, coverage / QD-score / mean pairwise distance, heat-map data endpoint.
- YAML scenario format, validator, linter with line numbers, seed-share codes.

STEP 3 — Library and UI (track B, worktree)
- Scripted curriculum pack in packs/scenarios/ (fictional sites and names).
- Scenario library, editor and generator studio per docs/07-ui-map.md.

STEP 4 — CI and docs (main track)
- Nightly 1,000-seed job; 50-seed subset on push; wording grep test.
- docs/SCENARIO_ENGINE.md. Update docs/TRACEABILITY.md (R8, R16, R19).

OUT OF SCOPE (do not build):
- Site builder (wave 9b) and sensor placement trainer (wave 9c).
- Adaptive selection of the difficulty vector (wave 11a).
- Signed scenario packs (wave 13c).

ACCEPTANCE (all must be true):
- Same seed and generator version give a byte-identical spec (test).
- Oracle solvability check passes on 1,000 seeds (nightly CI job; a 50-seed subset on every push).
- Diversity filter rejects a candidate closer than the threshold to the trainee's history (test).
- A scenario with a threat timed before the minimum reaction window fails lint with the offending line number; a seed-share code round-trips to an identical spec (tests).
- Every UI, doc and API string says "verified solvable by test run"; a test greps for "provably" and "guaranteed" and fails if found.
- Editor and studio are axe-clean and bilingual; the validation panel shows solvability, diversity and lint results.
- Every new user-facing string exists in EN and HI (key-parity check passes).
- Every new screen has populated, empty, loading and error states, works by keyboard, and is axe-clean.
- CI is green on `main` (lint, typecheck, unit, e2e, gitleaks, docker build).
- Every feature in this wave has tests; no existing test was skipped, disabled or weakened.
- Production images build and the production-mode compose stack passes `make smoke`.
- `docs/BUILD_LOG.md` is updated per its rules, including the deploy check and the next wave entry point.
- No credentials, secrets or real keys anywhere in git history; only `.env.example` placeholders.
- The deployed build still works: the commit to deploy is recorded in the build log, and after the user redeploys, `make smoke URL=<live url>` passes.

LOG: Follow the rules in docs/BUILD_LOG.md. Add a "Wave 9a" entry at the start, append each merged commit, record decisions, test counts and the deploy check, and write the exact first step of wave 9b.

STOP CONDITIONS — stop and report if:
- a step needs credentials, or network beyond package registries and GitHub;
- a Docker action would touch anything outside this repo's compose project;
- CI fails 3 times on the same cause;
- about 60% of the session is used before acceptance (commit green work, log it as wave 9a.2, stop);
- Never build features from later waves.

FINAL OUTPUT TO ME: at most 10 lines — commits, test counts, CI result, deploy check (and the commit for me to deploy), anything skipped and why, and the first step of wave 9b.
````
