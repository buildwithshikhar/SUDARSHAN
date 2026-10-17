# Wave 15b · Release 1.0 polish (depth)

| | |
|---|---|
| Depends on | 15a, plus any depth wave built (13a, 14b); none is required |
| Recommended model | Sonnet |
| Deployment | Release 1.0: the user deploys the release commit and tags it. |

**Goal.** The 1.0 release: documentation brought up to date with any depth waves built, pilot results included as measured, and a rehearsed final polish.

## Scope

- Documentation for every depth wave that was built (13a team mode, 14b WebXR): manual, SOP, API, architecture and traceability updates. Depth waves not built are listed as not built, with no claim made for them.
- Pilot results added to the final report, only as measured; unmeasured sections stay labelled.
- Final dataset-licence re-check for every row in `docs/DATA_REGISTER.md`, with the date.
- Release process, CHANGELOG 1.0.0 and release notes.
- Final polish pass: every screen against the banned list in `docs/07-ui-map.md`, copy and translation review, demo rehearsal from `make demo` and the fallback-recording checklist re-run.

## Out of scope

- New features.
- Any depth wave not yet built.

## Acceptance criteria

- Every doc is linked from `docs/README.md`; no broken links (CI link check).
- `docs/TRACEABILITY.md` has no empty proof cell, including clauses served by depth waves built since 15a.
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
ROLE: You are building wave 15b (Release 1.0 polish) of SUDARSHAN, an AI-enabled drone and counter-drone threat simulation TRAINER (SIH 2026, PS 26247). CLAUDE.md is loaded: follow it, above all the LOCKED RULES.

READ FIRST: docs/BUILD_LOG.md (confirm wave 15a is Done and main is green; note which depth waves 13a and 14b are Done; if 15a is not Done, stop and tell me). Then: every doc in docs/README.md; docs/TRACEABILITY.md; docs/FINAL_REPORT.md.

GOAL: The 1.0 release: documentation brought up to date with any depth waves built, pilot results included as measured, and a rehearsed final polish.

STEP 1 — Depth documentation (subagent A, worktree)
- Update the manuals, SOPs, API and architecture docs for each depth wave that is Done; add a "not built" note for any that is not.

STEP 2 — Pilot and licences (subagent B, worktree)
- Add pilot results to docs/FINAL_REPORT.md from data files only; re-run the licence check across docs/DATA_REGISTER.md.

STEP 3 — Release (main session)
- Final polish pass; complete docs/TRACEABILITY.md; CHANGELOG 1.0.0; release notes; link check and wording grep.
- Do not create tags or deploy; tell me the commit to tag.

OUT OF SCOPE (do not build):
- New features.
- Any depth wave not yet built.

ACCEPTANCE (all must be true):
- Every doc is linked from `docs/README.md`; no broken links (CI link check).
- `docs/TRACEABILITY.md` has no empty proof cell, including clauses served by depth waves built since 15a.
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

LOG: Follow the rules in docs/BUILD_LOG.md. Add a "Wave 15b" entry at the start, append each merged commit, record decisions, test counts and the deploy check, and write the exact first step of the pilot report and presentation.

STOP CONDITIONS — stop and report if:
- a step needs credentials, or network beyond package registries and GitHub;
- a Docker action would touch anything outside this repo's compose project;
- CI fails 3 times on the same cause;
- about 60% of the session is used before acceptance (commit green work, log it as wave 15b.2, stop);
- Never build features from later waves.

FINAL OUTPUT TO ME: at most 10 lines — commits, test counts, CI result, deploy check (and the commit for me to deploy), anything skipped and why, and the first step of the pilot report and presentation.
````
