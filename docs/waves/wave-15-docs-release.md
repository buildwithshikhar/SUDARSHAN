# Wave 15 · Docs + release 1.0

| | |
|---|---|
| Depends on | all (14b is optional) |
| Recommended model | Sonnet |
| Deployment | Release 1.0: the user deploys the release commit and tags it. |

**Goal.** Product-grade documentation, a completed traceability matrix and a rehearsed release.

## Scope

- User manual (trainee), instructor SOP, admin SOP, API docs (OpenAPI export plus a guide).
- Architecture doc brought up to date with the built system.
- Traceability matrix completed: every PS clause has a test ID, a measured metric or a demo timestamp.
- Final report with pilot results reported only as measured.
- Release process with the dataset-licence re-check; CHANGELOG 1.0.0; release notes.
- Demo rehearsal from `make demo`, plus a checklist for the fallback recording.

## Out of scope

- New features.

## Acceptance criteria

- Every doc is linked from `docs/README.md`; no broken links (CI link check).
- `docs/TRACEABILITY.md` has no empty proof cell.
- The final report's numbers trace to pilot data files or to `docs/PERFORMANCE.md`; anything not measured is labelled.
- Licence re-check done for every row in `docs/DATA_REGISTER.md`, with the date recorded.
- A grep test finds none of: "validated", "doctrine-accurate", "real data", "trained on", "provably" in user-facing text, except where quoted as forbidden wording.
- Release notes ready; the user tags and deploys the release commit.
- CI is green on `main` (lint, typecheck, unit, e2e, gitleaks, docker build).
- Every feature in this wave has tests; no existing test was skipped, disabled or weakened.
- Production images build and the production-mode compose stack passes `make smoke`.
- `docs/BUILD_LOG.md` is updated per its rules, including the deploy check and the next wave entry point.
- No credentials, secrets or real keys anywhere in git history; only `.env.example` placeholders.
- The deployed build still works: the commit to deploy is recorded in the build log, and after the user redeploys, `make smoke URL=<live url>` passes.

## Prompt (paste into Claude Code, Sonnet)

````text
ROLE: You are building wave 15 (Docs + release 1.0) of SUDARSHAN, an AI-enabled drone and counter-drone threat simulation TRAINER (SIH 2026, PS 26247). CLAUDE.md is loaded: follow it, above all the LOCKED RULES.

READ FIRST: docs/BUILD_LOG.md (confirm wave 14a is Done and main is green; if not, stop and tell me). Then: every doc in docs/README.md; docs/06-requirements-traceability.md; docs/08-demo.md.

GOAL: Product-grade documentation, a completed traceability matrix and a rehearsed release.

STEP 1 — Manuals and SOPs (subagent A, worktree)
- docs/USER_MANUAL.md, docs/INSTRUCTOR_SOP.md, docs/ADMIN_SOP.md, bilingual where trainee-facing.

STEP 2 — Reference docs (subagent B, worktree)
- docs/API.md from the OpenAPI export; docs/ARCHITECTURE.md updated from docs/05-architecture.md and the built system.

STEP 3 — Release (main session)
- Complete docs/TRACEABILITY.md; write docs/FINAL_REPORT.md from measured data only; licence re-check; CHANGELOG 1.0.0; release notes; link check and wording grep in CI.
- Do not create tags or deploy; tell me the commit to tag.

OUT OF SCOPE (do not build):
- New features.

ACCEPTANCE (all must be true):
- Every doc is linked from `docs/README.md`; no broken links (CI link check).
- `docs/TRACEABILITY.md` has no empty proof cell.
- The final report's numbers trace to pilot data files or to `docs/PERFORMANCE.md`; anything not measured is labelled.
- Licence re-check done for every row in `docs/DATA_REGISTER.md`, with the date recorded.
- A grep test finds none of: "validated", "doctrine-accurate", "real data", "trained on", "provably" in user-facing text, except where quoted as forbidden wording.
- Release notes ready; the user tags and deploys the release commit.
- CI is green on `main` (lint, typecheck, unit, e2e, gitleaks, docker build).
- Every feature in this wave has tests; no existing test was skipped, disabled or weakened.
- Production images build and the production-mode compose stack passes `make smoke`.
- `docs/BUILD_LOG.md` is updated per its rules, including the deploy check and the next wave entry point.
- No credentials, secrets or real keys anywhere in git history; only `.env.example` placeholders.
- The deployed build still works: the commit to deploy is recorded in the build log, and after the user redeploys, `make smoke URL=<live url>` passes.

LOG: Follow the rules in docs/BUILD_LOG.md. Add a "Wave 15" entry at the start, append each merged commit, record decisions, test counts and the deploy check, and write the exact first step of the pilot report and presentation.

STOP CONDITIONS — stop and report if:
- a step needs credentials, or network beyond package registries and GitHub;
- a Docker action would touch anything outside this repo's compose project;
- CI fails 3 times on the same cause;
- about 60% of the session is used before acceptance (commit green work, log it as wave 15.2, stop);
- Never build features from later waves.

FINAL OUTPUT TO ME: at most 10 lines — commits, test counts, CI result, deploy check (and the commit for me to deploy), anything skipped and why, and the first step of the pilot report and presentation.
````
