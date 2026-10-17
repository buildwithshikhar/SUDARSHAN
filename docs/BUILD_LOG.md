# Build log

The resumable state of the build. After every `/clear`, Claude Code reads [CLAUDE.md](../CLAUDE.md), then this file, then the wave file named under **Current position**. If this file and the repo disagree, the repo (git history and CI) wins; fix this file first.

## Current position

- **Phase:** planning complete, build not started.
- **Next wave:** 1 · Repo bootstrap → [waves/wave-01-repo-bootstrap.md](waves/wave-01-repo-bootstrap.md)
- **Next step:** paste the wave 1 prompt into Claude Code (Sonnet).
- **Main is:** green (docs only, no CI yet).
- **Deployed build:** none yet. First live link is the wave 2 milestone.

## Waves

Status values: Not started · In progress · Blocked · Done. A wave is Done only when its acceptance criteria are met, CI is green on `main`, and (from wave 2 on) the deployed build is verified.

| Wave | Name | Depends on | Model | Deploy | Status |
|---|---|---|---|---|---|
| 1 | [Repo bootstrap](waves/wave-01-repo-bootstrap.md) | — | Sonnet | Deploy-ready (prod images, smoke test) | Not started |
| 2 | [Design system + app shell](waves/wave-02-design-system-shell.md) | 1 | Sonnet | **PRIORITY MILESTONE: first live link** | Not started |
| 3 | [Contracts + deterministic sim core](waves/wave-03-contracts-sim-core.md) | 1 | Opus | Keep live build green | Not started |
| 4 | [Sensor models + fusion + AI assist](waves/wave-04-sensors-fusion.md) | 3 | Opus | Keep live build green | Not started |
| 5 | [Live-session vertical slice](waves/wave-05-live-session-slice.md) | 2, 4 | Sonnet | Redeploy: playable slice | Not started |
| 6 | [Scoring + debrief](waves/wave-06-scoring-debrief.md) | 5 | Sonnet | Redeploy | Not started |
| 7 | [3D realism + terrain packs](waves/wave-07-3d-realism-terrain.md) | 5 | Sonnet (Opus if gate fails) | Keep live build green | Not started |
| 8 | [Threat breadth](waves/wave-08-threat-breadth.md) | 4, 7 | Sonnet | Keep live build green | Not started |
| 9 | [Scenario engine](waves/wave-09-scenario-engine.md) | 6, 8 | Opus | Redeploy | Not started |
| 10 | [Instructor console](waves/wave-10-instructor-console.md) | 5, 9 | Sonnet | Keep live build green | Not started |
| 11 | [Adaptive learning + recognition library](waves/wave-11-adaptive-learning.md) | 6, 9 | Sonnet | Keep live build green | Not started |
| 12 | [Full AAR + reports](waves/wave-12-aar-reports.md) | 6, 10, 11 | Sonnet | Redeploy: demo-complete | Not started |
| 13 | [Team mode, trust and admin](waves/wave-13-team-trust-admin.md) | 10, 12 | Sonnet | Keep live build green | Not started |
| 14 | [WebXR + hardening](waves/wave-14-webxr-hardening.md) | 7, 12 | Sonnet | Keep live build green | Not started |
| 15 | [Docs + release 1.0](waves/wave-15-docs-release.md) | all | Sonnet | Release 1.0 | Not started |

**Pilot** (the user's activity, not a wave): starts once wave 12 is Done. Waves 13–15 continue alongside it.

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
7. **On a split:** if about 60% of the session is used before acceptance, stop at the next green commit, set the status to In progress, and log the remainder as wave n.b with its first step.
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
