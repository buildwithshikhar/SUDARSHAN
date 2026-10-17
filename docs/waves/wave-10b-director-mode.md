# Wave 10b · Live monitor and director mode

| | |
|---|---|
| Depends on | 10a, 3, 6 |
| Recommended model | Sonnet |
| Deployment | Keep the live build green. |

**Goal.** An instructor runs a drill like an exercise controller: watch the class with ground truth, inject, pause, branch, annotate and see scores as they happen.

## Scope

- Instructor WebSocket channel with ground truth; live monitor with class grid and trainee drill-down with ground-truth overlay.
- Pause and resume; inject macros (time jump, weather, sensor outage, add threat); timeline annotations.
- Branch: fork a running or paused session from a snapshot (wave 3) into a new practice session, marked as a branch of its parent in the record.
- Score-while-watching: the evaluator from wave 6 runs incrementally on the instructor channel and shows node results as events occur.
- Every instructor action is an event with author and tick in the hash chain.

## Out of scope

- Counterfactual review of finished sessions (wave 12b).
- Handoff scoring (wave 13a).

## Acceptance criteria

- Instructor frames carry ground truth; trainee frames still never do (test).
- One inject macro applies night + fog + radar sector outage + an RF-silent drone at once (the 08 demo beat) and is logged; two runs from the same seed give identical state (test).
- Pause and resume keep determinism: replay of a paused session matches (test).
- A branch restored from a snapshot and given no changes reproduces the parent's later events exactly (test).
- Live node scores equal the post-hoc scores for the same log (test).
- RBAC tests for every instructor endpoint; screens axe-clean and bilingual.
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
ROLE: You are building wave 10b (Live monitor and director mode) of SUDARSHAN, an AI-enabled drone and counter-drone threat simulation TRAINER (SIH 2026, PS 26247). CLAUDE.md is loaded: follow it, above all the LOCKED RULES.

READ FIRST: docs/BUILD_LOG.md (confirm wave 10a is Done and main is green; if not, stop and tell me). Then: docs/07-ui-map.md (Instructor), docs/08-demo.md (beats 4:15–7:00), docs/SIM_CORE.md (snapshots), docs/10-differentiators.md (H11).

GOAL: An instructor runs a drill like an exercise controller: watch the class with ground truth, inject, pause, branch, annotate and see scores as they happen.

STEP 1 — Instructor channel and monitor (subagent A, worktree)
- Instructor WS channel with ground truth; class grid; drill-down overlay; pause/resume; annotations, all logged as instructor events.

STEP 2 — Injects, branch and live scoring (subagent B, worktree)
- Inject macros incl. the demo macro; branch from snapshot; incremental evaluator feed.

STEP 3 — Integration (main session)
- Tests as in the acceptance criteria; update docs/TRACEABILITY.md (R4, R13); docs/DIRECTOR_MODE.md.

OUT OF SCOPE (do not build):
- Counterfactual review of finished sessions (wave 12b).
- Handoff scoring (wave 13a).

ACCEPTANCE (all must be true):
- Instructor frames carry ground truth; trainee frames still never do (test).
- One inject macro applies night + fog + radar sector outage + an RF-silent drone at once (the 08 demo beat) and is logged; two runs from the same seed give identical state (test).
- Pause and resume keep determinism: replay of a paused session matches (test).
- A branch restored from a snapshot and given no changes reproduces the parent's later events exactly (test).
- Live node scores equal the post-hoc scores for the same log (test).
- RBAC tests for every instructor endpoint; screens axe-clean and bilingual.
- Every new user-facing string exists in EN and HI (key-parity check passes).
- Every new screen has populated, empty, loading and error states, works by keyboard, and is axe-clean.
- CI is green on `main` (lint, typecheck, unit, e2e, gitleaks, docker build).
- Every feature in this wave has tests; no existing test was skipped, disabled or weakened.
- Production images build and the production-mode compose stack passes `make smoke`.
- `docs/BUILD_LOG.md` is updated per its rules, including the deploy check and the next wave entry point.
- No credentials, secrets or real keys anywhere in git history; only `.env.example` placeholders.
- The deployed build still works: the commit to deploy is recorded in the build log, and after the user redeploys, `make smoke URL=<live url>` passes.

LOG: Follow the rules in docs/BUILD_LOG.md. Add a "Wave 10b" entry at the start, append each merged commit, record decisions, test counts and the deploy check, and write the exact first step of wave 11a.

STOP CONDITIONS — stop and report if:
- a step needs credentials, or network beyond package registries and GitHub;
- a Docker action would touch anything outside this repo's compose project;
- CI fails 3 times on the same cause;
- about 60% of the session is used before acceptance (commit green work, log it as wave 10b.2, stop);
- Never build features from later waves.

FINAL OUTPUT TO ME: at most 10 lines — commits, test counts, CI result, deploy check (and the commit for me to deploy), anything skipped and why, and the first step of wave 11a.
````
