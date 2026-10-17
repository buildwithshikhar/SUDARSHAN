# Wave 12a · Full AAR and reports

| | |
|---|---|
| Depends on | 6, 10b, 11b |
| Recommended model | Sonnet |
| Deployment | Redeploy: pilot-ready live link. The pilot can start after this wave. |

**Goal.** Review a session as seen versus truth, see individual and unit performance over time, and export reports.

## Scope

- Seen-vs-truth split replay from the verified log, with bookmarks and one-click jump.
- Decision path per threat, contact-report grades, confusion matrix, reaction-time curves, miss-zone heat map.
- Individual progress and learning curves; unit readiness dashboard (weakness heat map, cohort trends, cohort comparison); compare trainees; annotated replay.
- PDF and CSV export; every chart has a data-table alternative.
- `make demo` seeds the hero-demo state from `docs/08-demo.md` with fixed seeds, labelled "reference data (seeded)"; the counterfactual beat is added in wave 12b.

## Out of scope

- Counterfactual branches, replay clip export and narration (wave 12b).
- Team handoff scoring (wave 13a).

## Acceptance criteria

- Replay refuses to play a log whose chain does not verify, and says so.
- Aggregate maths tests (confusion matrix, curves, heat-map binning); on the seeded demo cohort the heat map matches a hand-computed skill-by-trainee table and loads in under 2 s.
- PDF export completes in under 5 s for a 10-minute session.
- `make demo` from a clean clone produces the identical seeded state twice in a row (test compares hashes).
- Demo must-work items 1, 4, 5, 8 and 9 from 08 pass as automated checks.
- Screens axe-clean and bilingual; seeded data is labelled.
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
ROLE: You are building wave 12a (Full AAR and reports) of SUDARSHAN, an AI-enabled drone and counter-drone threat simulation TRAINER (SIH 2026, PS 26247). CLAUDE.md is loaded: follow it, above all the LOCKED RULES.

READ FIRST: docs/BUILD_LOG.md (confirm wave 11b is Done and main is green; if not, stop and tell me). Then: docs/05-architecture.md §3.4, docs/07-ui-map.md (My performance, Unit AAR, Reports), docs/08-demo.md, docs/10-differentiators.md (H9).

GOAL: Review a session as seen versus truth, see individual and unit performance over time, and export reports.

STEP 1 — Replay and per-session views (subagent A, worktree)
- Split replay (sensor frames vs ground truth), bookmarks, decision path, contact-report grades, confusion matrix, reaction-time curve, miss-zone heat map.

STEP 2 — Aggregates and export (subagent B, worktree)
- Individual and unit aggregates across sessions, readiness dashboard, compare trainees, PDF and CSV export, data-table alternatives.

STEP 3 — Demo seed (main session)
- make demo builds the 08 storyline state (Post KESARI, Demo Section, labelled bot seats) from fixed seeds.
- Automated must-work checks. Update docs/TRACEABILITY.md (R18).

OUT OF SCOPE (do not build):
- Counterfactual branches, replay clip export and narration (wave 12b).
- Team handoff scoring (wave 13a).

ACCEPTANCE (all must be true):
- Replay refuses to play a log whose chain does not verify, and says so.
- Aggregate maths tests (confusion matrix, curves, heat-map binning); on the seeded demo cohort the heat map matches a hand-computed skill-by-trainee table and loads in under 2 s.
- PDF export completes in under 5 s for a 10-minute session.
- `make demo` from a clean clone produces the identical seeded state twice in a row (test compares hashes).
- Demo must-work items 1, 4, 5, 8 and 9 from 08 pass as automated checks.
- Screens axe-clean and bilingual; seeded data is labelled.
- Every new user-facing string exists in EN and HI (key-parity check passes).
- Every new screen has populated, empty, loading and error states, works by keyboard, and is axe-clean.
- CI is green on `main` (lint, typecheck, unit, e2e, gitleaks, docker build).
- Every feature in this wave has tests; no existing test was skipped, disabled or weakened.
- Production images build and the production-mode compose stack passes `make smoke`.
- `docs/BUILD_LOG.md` is updated per its rules, including the deploy check and the next wave entry point.
- No credentials, secrets or real keys anywhere in git history; only `.env.example` placeholders.
- The deployed build still works: the commit to deploy is recorded in the build log, and after the user redeploys, `make smoke URL=<live url>` passes.

LOG: Follow the rules in docs/BUILD_LOG.md. Add a "Wave 12a" entry at the start, append each merged commit, record decisions, test counts and the deploy check, and write the exact first step of wave 12b.

STOP CONDITIONS — stop and report if:
- a step needs credentials, or network beyond package registries and GitHub;
- a Docker action would touch anything outside this repo's compose project;
- CI fails 3 times on the same cause;
- about 60% of the session is used before acceptance (commit green work, log it as wave 12a.2, stop);
- Never build features from later waves.

FINAL OUTPUT TO ME: at most 10 lines — commits, test counts, CI result, deploy check (and the commit for me to deploy), anything skipped and why, and the first step of wave 12b.
````
