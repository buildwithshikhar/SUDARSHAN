# Wave 11a · Adaptive learning and adaptive adversary

| | |
|---|---|
| Depends on | 6, 9a |
| Deployment | Keep the live build green. |

**Goal.** The platform models each trainee's skills, picks the next drill, biases scenario generation toward their weaknesses, and models workload and fatigue conditions.

## Scope

- Skill tags on scored nodes (for example classify-FPV-at-night), including approach sector and altitude band as tag dimensions.
- Elo per skill with decaying K; BKT with hand-set parameters for the "mastered" display only.
- Policy: aim at ~85% predicted success (a heuristic) plus spaced-repetition due skills → next difficulty vector and focus → generator.
- Adaptive adversary: the focus feeds the generator as weakness biases (approach sector, altitude, timing, clutter use, known sensor degradations); behaviour stays kinematic. Each choice carries a plain-language reason shown to the instructor.
- Stress and fatigue profiles: nuisance-alarm rate, long night-shift workload and time-pressure modes as scenario parameters, recorded with the session. They model conditions, not the trainee's physiology.
- Trainee screens: Today (recommended drill, skills due, last session), Quick drill, Progress (skill proficiency).

## Out of scope

- Recognition academy and progression levels (wave 11b).
- Learning curves and unit trends (wave 12a).

## Acceptance criteria

- Simulated-learner test: Elo skill estimates correlate with true skill after about 10 observations, at the level reported in the research brief.
- The policy's predicted success stays near the target on simulated learners; the UI calls the target a heuristic.
- Given a seeded history with a weak NE low-altitude skill, the next generated scenario has its main approach in that sector with probability ≥ 0.7 over 100 seeds, and still passes the oracle solvability check.
- A 40-minute night profile with a raised nuisance-alarm rate lowers late-shift detection in a headless population of seeded policy agents, and the profile is stored with the session (test).
- Screens axe-clean and bilingual.
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
ROLE: Build wave 11a (Adaptive learning and adaptive adversary) of SUDARSHAN, an AI-enabled drone and counter-drone threat simulation TRAINER (SIH 2026, PS 26247). Follow the project rules in CONTRIBUTING.md, above all the content rules.

READ FIRST: docs/BUILD_LOG.md (confirm wave 10b is Done and main is green; if not, stop and tell me). Then: docs/02-research.md §5, docs/05-architecture.md §3.5, docs/07-ui-map.md (Today, Progress), docs/10-differentiators.md (H1, H12).

GOAL: The platform models each trainee's skills, picks the next drill, biases scenario generation toward their weaknesses, and models workload and fatigue conditions.

STEP 1 — Learner model and adaptive adversary (track A, worktree)
- services/api/app/learner/: skill taxonomy with sector and altitude dimensions, Elo with decaying K, BKT display, policy, recommendation endpoint, weakness-biased generator requests with reasons.

STEP 2 — Stress and fatigue profiles (track B, worktree)
- Profile parameters in the scenario spec, generator support, nuisance-alarm and workload models, recorded with the session.

STEP 3 — Trainee screens (main track)
- Today, Quick drill, Progress. Tests as in the acceptance criteria. docs/LEARNER_MODEL.md with the heuristic labelled as such, and the adversary and fatigue models described.

OUT OF SCOPE (do not build):
- Recognition academy and progression levels (wave 11b).
- Learning curves and unit trends (wave 12a).

ACCEPTANCE (all must be true):
- Simulated-learner test: Elo skill estimates correlate with true skill after about 10 observations, at the level reported in the research brief.
- The policy's predicted success stays near the target on simulated learners; the UI calls the target a heuristic.
- Given a seeded history with a weak NE low-altitude skill, the next generated scenario has its main approach in that sector with probability ≥ 0.7 over 100 seeds, and still passes the oracle solvability check.
- A 40-minute night profile with a raised nuisance-alarm rate lowers late-shift detection in a headless population of seeded policy agents, and the profile is stored with the session (test).
- Screens axe-clean and bilingual.
- Every new user-facing string exists in EN and HI (key-parity check passes).
- Every new screen has populated, empty, loading and error states, works by keyboard, and is axe-clean.
- CI is green on `main` (lint, typecheck, unit, e2e, gitleaks, docker build).
- Every feature in this wave has tests; no existing test was skipped, disabled or weakened.
- Production images build and the production-mode compose stack passes `make smoke`.
- `docs/BUILD_LOG.md` is updated per its rules, including the deploy check and the next wave entry point.
- No credentials, secrets or real keys anywhere in git history; only `.env.example` placeholders.
- The deployed build still works: the commit to deploy is recorded in the build log, and after the user redeploys, `make smoke URL=<live url>` passes.

LOG: Follow the rules in docs/BUILD_LOG.md. Add a "Wave 11a" entry at the start, append each merged commit, record decisions, test counts and the deploy check, and write the exact first step of wave 11b.

STOP CONDITIONS — stop and report if:
- a step needs credentials, or network beyond package registries and GitHub;
- a Docker action would touch anything outside this repo's compose project;
- CI fails 3 times on the same cause;
- about 60% of the session is used before acceptance (commit green work, log it as wave 11a.2, stop);
- Never build features from later waves.

FINAL OUTPUT TO ME: at most 10 lines — commits, test counts, CI result, deploy check (and the commit for me to deploy), anything skipped and why, and the first step of wave 11b.
````
