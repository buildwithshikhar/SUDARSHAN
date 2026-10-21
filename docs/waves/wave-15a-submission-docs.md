# Wave 15a · Submission documentation

| | |
|---|---|
| Depends on | Every wave in the Submission-ready cut (1–12b, 13b, 13c, 14a); 14a is the last dependency. 13a and 14b are not required. |
| Deployment | Redeploy: the submission build, documented and rehearsed. |

**Goal.** Product-grade documentation, a completed traceability matrix and a rehearsed demo for the submission, covering what is built in the cut.

## Scope

- User manual (trainee), instructor SOP, admin SOP, API docs (OpenAPI export plus a guide).
- Cost sheet (`docs/COST_SHEET.md`): what the platform needs to run (hardware the unit already owns, open-source licences, no consumables), stated from facts, with no invented prices.
- Architecture doc brought up to date with the built system.
- Traceability matrix completed for every PS clause: a test ID, a measured metric or a demo timestamp. Clauses served by depth waves (R15 VR mode) state exactly what is built.
- Final report; pilot results appear only as measured, and the sections the pilot has not yet filled are labelled as pending.
- Release notes and CHANGELOG entry for the submission build.
- Dataset-licence re-check for every row used in the build, with the date.
- Demo rehearsal from `make demo`, plus a checklist for the fallback recording.

## Out of scope

- New features.
- Documentation of team mode (13a) and WebXR (14b); that belongs to wave 15b if they are built.
- Final 1.0 release polish (wave 15b).

## Acceptance criteria

- Every doc is linked from `docs/README.md`; no broken links (CI link check).
- `docs/TRACEABILITY.md` has no empty proof cell; each cell points to a test ID, a metric in `docs/PERFORMANCE.md` or pilot data, or a demo timestamp.
- `docs/COST_SHEET.md` exists and every figure in it is sourced or labelled as an assumption.
- The final report's numbers trace to pilot data files or to `docs/PERFORMANCE.md`; anything not measured is labelled.
- Licence re-check done for every register row the build uses, with the date recorded.
- A grep test finds none of: "validated", "doctrine-accurate", "real data", "trained on", "provably" in user-facing text, except where quoted as forbidden wording.
- The demo script runs end to end from `make demo` on the floor laptop with networking disabled, apart from any beat belonging to a depth wave, which the checklist lists as omitted.
- Release notes ready for the submission commit; the user tags and deploys it.
- CI is green on `main` (lint, typecheck, unit, e2e, gitleaks, docker build).
- Every feature in this wave has tests; no existing test was skipped, disabled or weakened.
- Production images build and the production-mode compose stack passes `make smoke`.
- `docs/BUILD_LOG.md` is updated per its rules, including the deploy check and the next wave entry point.
- No credentials, secrets or real keys anywhere in git history; only `.env.example` placeholders.
- The deployed build still works: the commit to deploy is recorded in the build log, and after the user redeploys, `make smoke URL=<live url>` passes.

## Brief

````text
ROLE: Build wave 15a (Submission documentation) of SUDARSHAN, an AI-enabled drone and counter-drone threat simulation TRAINER (SIH 2026, PS 26247). Follow the project rules in CONTRIBUTING.md, above all the content rules.

READ FIRST: docs/BUILD_LOG.md (confirm wave 14a is Done and main is green, and that every other wave in the Submission-ready cut is Done; if not, stop and tell me). Then: every doc in docs/README.md; docs/06-requirements-traceability.md; docs/08-demo.md.

GOAL: Product-grade documentation, a completed traceability matrix and a rehearsed demo for the submission, covering what is built in the cut.

STEP 1 — Manuals and SOPs (track A, worktree)
- docs/USER_MANUAL.md, docs/INSTRUCTOR_SOP.md, docs/ADMIN_SOP.md, bilingual where trainee-facing; build on the LAN-join draft from wave 14a.

STEP 2 — Reference docs and cost sheet (track B, worktree)
- docs/API.md from the OpenAPI export; docs/ARCHITECTURE.md updated from docs/05-architecture.md and the built system; docs/COST_SHEET.md.

STEP 3 — Traceability, report and release notes (main track)
- Complete docs/TRACEABILITY.md; write docs/FINAL_REPORT.md from measured data only; licence re-check; CHANGELOG entry; release notes; link check and wording grep in CI.
- Demo rehearsal checklist and fallback-recording checklist.
- Do not create tags or deploy; tell me the commit to tag.

OUT OF SCOPE (do not build):
- New features.
- Documentation of team mode (13a) and WebXR (14b); that belongs to wave 15b if they are built.
- Final 1.0 release polish (wave 15b).

ACCEPTANCE (all must be true):
- Every doc is linked from `docs/README.md`; no broken links (CI link check).
- `docs/TRACEABILITY.md` has no empty proof cell; each cell points to a test ID, a metric in `docs/PERFORMANCE.md` or pilot data, or a demo timestamp.
- `docs/COST_SHEET.md` exists and every figure in it is sourced or labelled as an assumption.
- The final report's numbers trace to pilot data files or to `docs/PERFORMANCE.md`; anything not measured is labelled.
- Licence re-check done for every register row the build uses, with the date recorded.
- A grep test finds none of: "validated", "doctrine-accurate", "real data", "trained on", "provably" in user-facing text, except where quoted as forbidden wording.
- The demo script runs end to end from `make demo` on the floor laptop with networking disabled, apart from any beat belonging to a depth wave, which the checklist lists as omitted.
- Release notes ready for the submission commit; the user tags and deploys it.
- CI is green on `main` (lint, typecheck, unit, e2e, gitleaks, docker build).
- Every feature in this wave has tests; no existing test was skipped, disabled or weakened.
- Production images build and the production-mode compose stack passes `make smoke`.
- `docs/BUILD_LOG.md` is updated per its rules, including the deploy check and the next wave entry point.
- No credentials, secrets or real keys anywhere in git history; only `.env.example` placeholders.
- The deployed build still works: the commit to deploy is recorded in the build log, and after the user redeploys, `make smoke URL=<live url>` passes.

LOG: Follow the rules in docs/BUILD_LOG.md. Add a "Wave 15a" entry at the start, append each merged commit, record decisions, test counts and the deploy check, and write the exact first step of wave 15b or the first depth wave you choose.

STOP CONDITIONS — stop and report if:
- a step needs credentials, or network beyond package registries and GitHub;
- a Docker action would touch anything outside this repo's compose project;
- CI fails 3 times on the same cause;
- about 60% of the session is used before acceptance (commit green work, log it as wave 15a.2, stop);
- Never build features from later waves.

FINAL OUTPUT TO ME: at most 10 lines — commits, test counts, CI result, deploy check (and the commit for me to deploy), anything skipped and why, and the first step of wave 15b or the first depth wave you choose.
````
