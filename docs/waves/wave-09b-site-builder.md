# Wave 9b · Site builder

| | |
|---|---|
| Depends on | 9a, 7 |
| Recommended model | Sonnet |
| Deployment | Redeploy: instructors can build sites and generate scenarios for them. |

**Goal.** An instructor draws a fictional site (perimeter, protected assets, approach routes) on the map, and the generator builds verified-solvable scenarios that respect it.

## Scope

- Map-based site editor (MapLibre over a terrain pack): draw a perimeter, place protected assets and draw approach routes; snap to terrain; undo and redo.
- `site.v1` pack format (JSON Schema, TS types, example site with fictional names) stored under packs/sites/.
- Generator integration: a site constrains threat paths to the declared approach routes and aims intents at declared assets; the oracle check and diversity check still run.
- Site validation: perimeter closed, assets inside, routes reach the perimeter, sensors can be sited (hand-off point for wave 9c).

## Out of scope

- Sensor placement and viewshed (wave 9c).
- Importing real survey or cadastral data; sites are drawn or fictional.

## Acceptance criteria

- A drawn site with two approach routes yields 20 generated scenarios whose threat paths all follow one of the two routes and all pass the solvability check.
- Invalid sites (open perimeter, asset outside, unreachable route) are rejected with a message naming the fault (tests).
- Site files round-trip through the schema and TS types; the drift check passes.
- The editor is operable by keyboard (vertex add, move and delete without a pointer) and axe-clean.
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
ROLE: You are building wave 9b (Site builder) of SUDARSHAN, an AI-enabled drone and counter-drone threat simulation TRAINER (SIH 2026, PS 26247). CLAUDE.md is loaded: follow it, above all the LOCKED RULES.

READ FIRST: docs/BUILD_LOG.md (confirm wave 9a is Done and main is green; if not, stop and tell me). Then: docs/10-differentiators.md (H3), docs/SCENARIO_ENGINE.md, docs/07-ui-map.md (Scenarios), docs/DATA_REGISTER.md (G01, G02).

GOAL: An instructor draws a fictional site (perimeter, protected assets, approach routes) on the map, and the generator builds verified-solvable scenarios that respect it.

STEP 1 — Site format (main session)
- site.v1 schema, Pydantic model, TS types, example fictional site, validation rules.

STEP 2 — Site editor (subagent A, worktree)
- Map editor screen with draw, edit, snap, undo; keyboard alternatives; empty, loading and error states; EN and HI.

STEP 3 — Generator integration (subagent B, worktree)
- Site-constrained sampling in the generator; tests on 20 seeds; docs update in docs/SCENARIO_ENGINE.md.

OUT OF SCOPE (do not build):
- Sensor placement and viewshed (wave 9c).
- Importing real survey or cadastral data; sites are drawn or fictional.

ACCEPTANCE (all must be true):
- A drawn site with two approach routes yields 20 generated scenarios whose threat paths all follow one of the two routes and all pass the solvability check.
- Invalid sites (open perimeter, asset outside, unreachable route) are rejected with a message naming the fault (tests).
- Site files round-trip through the schema and TS types; the drift check passes.
- The editor is operable by keyboard (vertex add, move and delete without a pointer) and axe-clean.
- Every new user-facing string exists in EN and HI (key-parity check passes).
- Every new screen has populated, empty, loading and error states, works by keyboard, and is axe-clean.
- CI is green on `main` (lint, typecheck, unit, e2e, gitleaks, docker build).
- Every feature in this wave has tests; no existing test was skipped, disabled or weakened.
- Production images build and the production-mode compose stack passes `make smoke`.
- `docs/BUILD_LOG.md` is updated per its rules, including the deploy check and the next wave entry point.
- No credentials, secrets or real keys anywhere in git history; only `.env.example` placeholders.
- The deployed build still works: the commit to deploy is recorded in the build log, and after the user redeploys, `make smoke URL=<live url>` passes.

LOG: Follow the rules in docs/BUILD_LOG.md. Add a "Wave 9b" entry at the start, append each merged commit, record decisions, test counts and the deploy check, and write the exact first step of wave 9c.

STOP CONDITIONS — stop and report if:
- a step needs credentials, or network beyond package registries and GitHub;
- a Docker action would touch anything outside this repo's compose project;
- CI fails 3 times on the same cause;
- about 60% of the session is used before acceptance (commit green work, log it as wave 9b.2, stop);
- Never build features from later waves.

FINAL OUTPUT TO ME: at most 10 lines — commits, test counts, CI result, deploy check (and the commit for me to deploy), anything skipped and why, and the first step of wave 9c.
````
