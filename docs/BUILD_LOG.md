# Build log

The resumable state of the build. After every `/clear`, Claude Code reads [CLAUDE.md](../CLAUDE.md), then this file, then the wave file named under **Current position**. If this file and the repo disagree, the repo (git history and CI) wins; fix this file first.

## Current position

- **Phase:** planning complete, build not started.
- **Next wave:** 1 · Repo bootstrap → [waves/wave-01-repo-bootstrap.md](waves/wave-01-repo-bootstrap.md)
- **Next step:** paste the wave 1 prompt into Claude Code (Sonnet).
- **Main is:** green (docs only, no CI yet).
- **Deployed build:** none yet. First live link is the wave 2 milestone.

## Planning updates

- 2026-10-17: README rewritten as a product README (banner in `docs/assets/`, status table mirrors the wave table above, capabilities all Planned). Update its status table and capability states whenever a wave is marked Done.
- 2026-10-17: [10-differentiators.md](10-differentiators.md) added. Headline features: H1 adaptive adversary, H2 sensor placement trainer, H3 site builder, H4 contact-report scoring, H5 track management with association errors, H6 counterfactual AAR, H7 recognition academy, H8 competency matrix with signed records, H9 unit readiness dashboard, H10 scenario language and signed packs, H11 director mode, H12 stress and fatigue modelling. Demo five: H2, H4, H1, H6, H8. The wave files are not yet changed; pull an entry into its wave only when that wave starts and record it in the wave entry.
- 2026-10-17: Wave execution protocol added to CLAUDE.md.
- 2026-10-17: Headline features folded into the wave files and overloaded waves split (4a/4b, 9a/9b/9c, 10a/10b, 11a/11b, 12a/12b, 13a/13b/13c, 14a/14b); see ADR-012. Waves 1, 2, 3, 5, 6, 7, 8 and 15 keep their numbers; 3, 5, 6 and 15 gained scope or edits.

## Waves

Status values: Not started · In progress · Blocked · Done. A wave is Done only when its acceptance criteria are met, CI is green on `main`, and (from wave 2 on) the deployed build is verified.

| Wave | Name | Depends on | Model | Deploy | Status |
|---|---|---|---|---|---|
| 1 | [Repo bootstrap](waves/wave-01-repo-bootstrap.md) | — | Sonnet | Deploy-ready (prod images, smoke test) | Not started |
| 2 | [Design system + app shell](waves/wave-02-design-system-shell.md) | 1 | Sonnet | **PRIORITY MILESTONE: first live link** | Not started |
| 3 | [Contracts + deterministic sim core](waves/wave-03-contracts-sim-core.md) | 1 | Opus | Keep live build green | Not started |
| 4a | [Sensor models](waves/wave-04a-sensor-models.md) | 3 | Opus | Keep live build green | Not started |
| 4b | [Tracking, fusion + AI assist](waves/wave-04b-tracking-ai-assist.md) | 4a | Opus | Keep live build green | Not started |
| 5 | [Live-session vertical slice](waves/wave-05-live-session-slice.md) | 2, 4b | Sonnet | Redeploy: playable slice | Not started |
| 6 | [Scoring + debrief](waves/wave-06-scoring-debrief.md) | 5 | Sonnet | Redeploy | Not started |
| 7 | [3D realism + terrain packs](waves/wave-07-3d-realism-terrain.md) | 5 | Sonnet (Opus if gate fails) | Keep live build green | Not started |
| 8 | [Threat breadth](waves/wave-08-threat-breadth.md) | 4a, 7 | Sonnet | Keep live build green | Not started |
| 9a | [Scenario engine](waves/wave-09a-scenario-engine.md) | 6, 8 | Opus | Redeploy: generated scenarios | Not started |
| 9b | [Site builder](waves/wave-09b-site-builder.md) | 9a, 7 | Sonnet | Redeploy | Not started |
| 9c | [Sensor placement trainer](waves/wave-09c-sensor-placement.md) | 9b, 4a, 7 | Sonnet | Redeploy | Not started |
| 10a | [Class management + rule packs](waves/wave-10a-class-management.md) | 5, 9a | Sonnet | Keep live build green | Not started |
| 10b | [Live monitor + director mode](waves/wave-10b-director-mode.md) | 10a, 3, 6 | Sonnet | Keep live build green | Not started |
| 11a | [Adaptive learning + adaptive adversary](waves/wave-11a-adaptive-learning.md) | 6, 9a | Sonnet | Keep live build green | Not started |
| 11b | [Recognition academy + progression](waves/wave-11b-recognition-academy.md) | 4a, 8, 11a | Sonnet | Keep live build green | Not started |
| 12a | [Full AAR + reports](waves/wave-12a-aar-reports.md) | 6, 10b, 11b | Sonnet | Redeploy: pilot-ready | Not started |
| 12b | [Counterfactual review + briefing export](waves/wave-12b-counterfactual-aar.md) | 12a, 10b, 3 | Sonnet | Redeploy: demo-complete (signed-record beat in 13b) | Not started |
| 13a | [Team mode](waves/wave-13a-team-mode.md) | 10b, 12a, 4b | Sonnet | Keep live build green | Not started |
| 13b | [Signed records + competency matrix](waves/wave-13b-trust-competency.md) | 12a, 11b | Sonnet | Keep live build green | Not started |
| 13c | [Admin + pack manager](waves/wave-13c-admin-packs.md) | 13b, 9a | Sonnet | Keep live build green | Not started |
| 14a | [Hardening + accessibility](waves/wave-14a-hardening.md) | 7, 12b, 13c | Sonnet | Keep live build green | Not started |
| 14b | [WebXR (optional)](waves/wave-14b-webxr.md) | 14a | Sonnet | Keep live build green | Not started |
| 15 | [Docs + release 1.0](waves/wave-15-docs-release.md) | all (14b optional) | Sonnet | Release 1.0 | Not started |

**Pilot** (the user's activity, not a wave): starts once wave 12a is Done. Waves 12b onward continue alongside it. The demo-complete live link is wave 12b.

## Deployed build

The user deploys; Claude Code never does. Fill this in when a deploy happens.

| Field | Value |
|---|---|
| Host | not chosen (see [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md)) |
| Live URL | — |
| Deployed commit | — |
| Last verified (`/healthz`, `/readyz`, `/api/v1/version`) | — |

## Rules for updating this log

Every wave follows these rules. They are part of each wave's acceptance criteria.

1. **On wave start:** set the wave to In progress, update **Current position**, and add a wave entry under **Wave entries** from the template below.
2. **After every merged step:** append the commit hash and one line to the wave entry's **Done** list, in the same commit or the one right after. A `/clear` must be able to resume from this file alone.
3. **Decisions:** any design decision made during the wave goes in the entry with its reason. If it changes a recorded decision, also add an ADR to [DECISIONS.md](DECISIONS.md).
4. **Open items:** anything unresolved goes in the entry and, if it needs the user, in [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md).
5. **Deploy check:** before a wave is Done, record that the production images built and `make smoke` passed in production mode. From wave 2 on, record the commit the user should deploy and leave **Deployed build** for the user to confirm.
6. **On wave end:** set the status to Done only when CI is green on `main`. Write the exact first step of the next wave under **Next wave entry point**, and update **Current position**.
7. **On a split:** if about 60% of the session is used before acceptance, stop at the next green commit, set the status to In progress, and log the remainder as wave n.2 (for example 9a.2) with its first step.
8. **Blocked:** set the status to Blocked, state the cause and what is needed in one line, and stop.
9. Never mark a step done that is not merged and green. Never record a red build as a resume point.

## Wave entry template

```markdown
### Wave N · Name

- Status: In progress | Blocked | Done
- Started from commit: <hash>
- Goal: <one line from the wave file>

**Done**
- <hash> <conventional commit subject>

**Decisions**
- <decision> because <reason>

**Tests**
- api: <count> passed · web: <count> passed · e2e: <count> passed · coverage: <n>%

**Deploy check**
- Production images built: yes/no · `make smoke` (production mode): pass/fail
- Commit to deploy: <hash>

**Open issues**
- <item>

**Next wave entry point**
- <exact first step>
```

## Wave entries

None yet.
