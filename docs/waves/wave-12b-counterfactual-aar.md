# Wave 12b · Counterfactual review and briefing export

| | |
|---|---|
| Depends on | 12a, 10b, 3 |
| Deployment | Redeploy: **demo-complete** live link (the signed-record beat lands with wave 13b). |

**Goal.** From any moment in a replay, branch the run with one changed action and compare the outcome; export clips and optional narration for briefings.

## Scope

- Counterfactual branches: from a bookmark, change one action or its timing (for example classify 12 s earlier, hold fire), restore the snapshot, replay forward deterministically, and show original and branch side by side with score differences. Branches are marked in the record and never replace the original.
- Replay clip export of a bookmarked moment (client-side WebM; GIF optional) and a branch comparison page in the PDF report.
- Optional offline narration, off by default: a deterministic template narrator that cites log event IDs for every sentence. A local language-model backend is not built here (see OPEN_QUESTIONS).
- `make demo` extended with the counterfactual beat from `docs/08-demo.md`; demo must-work items 1–9 pass as automated checks.

## Out of scope

- Team handoff scoring (wave 13a).
- Any narration backend that needs a network or a model download.

## Acceptance criteria

- Branching at a bookmark with an unchanged action reproduces the original score exactly; branching with an earlier classification changes only downstream events and is marked as a branch (tests).
- A branch never mutates the parent's chain; the parent still verifies (test).
- With narration off the AAR output is byte-identical to before; with it on, every sentence cites an existing event ID (tests).
- A clip of a bookmarked moment exports in under 15 s on the floor laptop; the PDF with the comparison builds in under 5 s.
- Screens axe-clean and bilingual; branches are visibly labelled as hypothetical.
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
ROLE: Build wave 12b (Counterfactual review and briefing export) of SUDARSHAN, an AI-enabled drone and counter-drone threat simulation TRAINER (SIH 2026, PS 26247). Follow the project rules in CONTRIBUTING.md, above all the content rules.

READ FIRST: docs/BUILD_LOG.md (confirm wave 12a is Done and main is green; if not, stop and tell me). Then: docs/05-architecture.md §3.4, docs/08-demo.md, docs/SIM_CORE.md (snapshots), docs/DIRECTOR_MODE.md, docs/10-differentiators.md (H6).

GOAL: From any moment in a replay, branch the run with one changed action and compare the outcome; export clips and optional narration for briefings.

STEP 1 — Branch engine (main track)
- Snapshot restore, action edit, deterministic forward run, comparison model and API; branch marking in the record.

STEP 2 — Branch UI and export (track A, worktree)
- Counterfactual panel in the replay, side-by-side comparison, clip export, PDF page.

STEP 3 — Narration and demo (track B, worktree)
- Template narrator with event-ID citations, settings switch; extend make demo and the must-work checks. Add the narration-backend question to docs/OPEN_QUESTIONS.md.

OUT OF SCOPE (do not build):
- Team handoff scoring (wave 13a).
- Any narration backend that needs a network or a model download.

ACCEPTANCE (all must be true):
- Branching at a bookmark with an unchanged action reproduces the original score exactly; branching with an earlier classification changes only downstream events and is marked as a branch (tests).
- A branch never mutates the parent's chain; the parent still verifies (test).
- With narration off the AAR output is byte-identical to before; with it on, every sentence cites an existing event ID (tests).
- A clip of a bookmarked moment exports in under 15 s on the floor laptop; the PDF with the comparison builds in under 5 s.
- Screens axe-clean and bilingual; branches are visibly labelled as hypothetical.
- Every new user-facing string exists in EN and HI (key-parity check passes).
- Every new screen has populated, empty, loading and error states, works by keyboard, and is axe-clean.
- CI is green on `main` (lint, typecheck, unit, e2e, gitleaks, docker build).
- Every feature in this wave has tests; no existing test was skipped, disabled or weakened.
- Production images build and the production-mode compose stack passes `make smoke`.
- `docs/BUILD_LOG.md` is updated per its rules, including the deploy check and the next wave entry point.
- No credentials, secrets or real keys anywhere in git history; only `.env.example` placeholders.
- The deployed build still works: the commit to deploy is recorded in the build log, and after the user redeploys, `make smoke URL=<live url>` passes.

LOG: Follow the rules in docs/BUILD_LOG.md. Add a "Wave 12b" entry at the start, append each merged commit, record decisions, test counts and the deploy check, and write the exact first step of wave 13a.

STOP CONDITIONS — stop and report if:
- a step needs credentials, or network beyond package registries and GitHub;
- a Docker action would touch anything outside this repo's compose project;
- CI fails 3 times on the same cause;
- about 60% of the session is used before acceptance (commit green work, log it as wave 12b.2, stop);
- Never build features from later waves.

FINAL OUTPUT TO ME: at most 10 lines — commits, test counts, CI result, deploy check (and the commit for me to deploy), anything skipped and why, and the first step of wave 13a.
````
