# Wave 9c · Sensor placement trainer

| | |
|---|---|
| Depends on | 9b, 4a, 7 |
| Deployment | Redeploy: sensor siting exercise on the live link. |

**Goal.** Trainees place sensors on terrain, see computed coverage and blind spots, then run a scenario against that layout and get a layout score.

## Scope

- Viewshed and coverage computation in the sim core from the same heightmap and building data as the line-of-sight model, per sensor type with range from the sensor profile; blind-spot polygons and coverage percentage.
- `layout.v1` format: sensor type, position, orientation and height; a layout hash recorded in the session spec and event log.
- Siting screen: place, move and remove sensors on the site map, live coverage overlay, blind-spot list.
- Run-against-layout: the scenario runs with the trainee's layout in place of the default one; the layout scorecard compares detections gained and missed against the reference layout from the same oracle run.
- Instructor assignment of a siting exercise to a cohort (uses the launch flow from wave 10a once it exists; until then via the scenario library).

## Out of scope

- Optimising layouts automatically for the trainee.
- Real-world sensor performance claims; coverage uses the fictional sensor profiles.

## Acceptance criteria

- On a fixed terrain pack, moving a radar behind a ridge changes the computed blind-spot area, and the scenario run on the two layouts gives different, reproducible detection times (tests).
- Viewshed agrees with the sim's line-of-sight model on 1,000 random point pairs (test).
- Same layout, scenario and seed give an identical score (test); the layout hash appears in the event log.
- Placement is operable by keyboard (coordinates and nudge keys) and axe-clean; coverage is also available as a data table.
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
ROLE: Build wave 9c (Sensor placement trainer) of SUDARSHAN, an AI-enabled drone and counter-drone threat simulation TRAINER (SIH 2026, PS 26247). Follow the project rules in CONTRIBUTING.md, above all the content rules.

READ FIRST: docs/BUILD_LOG.md (confirm wave 9b is Done and main is green; if not, stop and tell me). Then: docs/10-differentiators.md (H2), docs/SENSOR_MODELS.md, docs/SCENARIO_ENGINE.md, docs/07-ui-map.md.

GOAL: Trainees place sensors on terrain, see computed coverage and blind spots, then run a scenario against that layout and get a layout score.

STEP 1 — Viewshed and layout model (main track)
- Vectorised viewshed over the heightmap with building occlusion; coverage and blind-spot polygons; layout.v1 schema and TS types.

STEP 2 — Siting screen (track A, worktree)
- Placement UI with coverage overlay, blind-spot list, keyboard alternatives; EN and HI.

STEP 3 — Run-against-layout and scorecard (track B, worktree)
- Layout injected into the session spec; reference-layout comparison from the oracle run; scorecard screen; docs/SENSOR_SITING.md.

OUT OF SCOPE (do not build):
- Optimising layouts automatically for the trainee.
- Real-world sensor performance claims; coverage uses the fictional sensor profiles.

ACCEPTANCE (all must be true):
- On a fixed terrain pack, moving a radar behind a ridge changes the computed blind-spot area, and the scenario run on the two layouts gives different, reproducible detection times (tests).
- Viewshed agrees with the sim's line-of-sight model on 1,000 random point pairs (test).
- Same layout, scenario and seed give an identical score (test); the layout hash appears in the event log.
- Placement is operable by keyboard (coordinates and nudge keys) and axe-clean; coverage is also available as a data table.
- Every new user-facing string exists in EN and HI (key-parity check passes).
- Every new screen has populated, empty, loading and error states, works by keyboard, and is axe-clean.
- CI is green on `main` (lint, typecheck, unit, e2e, gitleaks, docker build).
- Every feature in this wave has tests; no existing test was skipped, disabled or weakened.
- Production images build and the production-mode compose stack passes `make smoke`.
- `docs/BUILD_LOG.md` is updated per its rules, including the deploy check and the next wave entry point.
- No credentials, secrets or real keys anywhere in git history; only `.env.example` placeholders.
- The deployed build still works: the commit to deploy is recorded in the build log, and after the user redeploys, `make smoke URL=<live url>` passes.

LOG: Follow the rules in docs/BUILD_LOG.md. Add a "Wave 9c" entry at the start, append each merged commit, record decisions, test counts and the deploy check, and write the exact first step of wave 10a.

STOP CONDITIONS — stop and report if:
- a step needs credentials, or network beyond package registries and GitHub;
- a Docker action would touch anything outside this repo's compose project;
- CI fails 3 times on the same cause;
- about 60% of the session is used before acceptance (commit green work, log it as wave 9c.2, stop);
- Never build features from later waves.

FINAL OUTPUT TO ME: at most 10 lines — commits, test counts, CI result, deploy check (and the commit for me to deploy), anything skipped and why, and the first step of wave 10a.
````
