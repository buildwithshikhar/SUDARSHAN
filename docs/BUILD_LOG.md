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

| Wave | Name | Depends on | Model | Deploy | Cut | Status |
|---|---|---|---|---|---|---|
| 1 | [Repo bootstrap](waves/wave-01-repo-bootstrap.md) | — | Sonnet | Deploy-ready (prod images, smoke test) | Cut | Not started |
| 2 | [Design system + app shell](waves/wave-02-design-system-shell.md) | 1 | Sonnet | **PRIORITY MILESTONE: first live link** | Cut | Not started |
| 3 | [Contracts + deterministic sim core](waves/wave-03-contracts-sim-core.md) | 1 | Opus | Keep live build green | Cut | Not started |
| 4a | [Sensor models](waves/wave-04a-sensor-models.md) | 3 | Opus | Keep live build green | Cut | Not started |
| 4b | [Tracking, fusion + AI assist](waves/wave-04b-tracking-ai-assist.md) | 4a | Opus | Keep live build green | Cut | Not started |
| 5 | [Live-session vertical slice](waves/wave-05-live-session-slice.md) | 2, 4b | Sonnet | Redeploy: playable slice | Cut | Not started |
| 6 | [Scoring + debrief](waves/wave-06-scoring-debrief.md) | 5 | Sonnet | Redeploy | Cut | Not started |
| 7 | [3D realism + terrain packs](waves/wave-07-3d-realism-terrain.md) | 5 | Sonnet (Opus if gate fails) | Keep live build green | Cut | Not started |
| 8 | [Threat breadth](waves/wave-08-threat-breadth.md) | 4a, 7 | Sonnet | Keep live build green | Cut | Not started |
| 9a | [Scenario engine](waves/wave-09a-scenario-engine.md) | 6, 8 | Opus | Redeploy: generated scenarios | Cut | Not started |
| 9b | [Site builder](waves/wave-09b-site-builder.md) | 9a, 7 | Sonnet | Redeploy | Cut | Not started |
| 9c | [Sensor placement trainer](waves/wave-09c-sensor-placement.md) | 9b, 4a, 7 | Sonnet | Redeploy | Cut | Not started |
| 10a | [Class management + rule packs](waves/wave-10a-class-management.md) | 5, 9a | Sonnet | Keep live build green | Cut | Not started |
| 10b | [Live monitor + director mode](waves/wave-10b-director-mode.md) | 10a, 3, 6 | Sonnet | Keep live build green | Cut | Not started |
| 11a | [Adaptive learning + adaptive adversary](waves/wave-11a-adaptive-learning.md) | 6, 9a | Sonnet | Keep live build green | Cut | Not started |
| 11b | [Recognition academy + progression](waves/wave-11b-recognition-academy.md) | 4a, 8, 11a | Sonnet | Keep live build green | Cut | Not started |
| 12a | [Full AAR + reports](waves/wave-12a-aar-reports.md) | 6, 10b, 11b | Sonnet | Redeploy: pilot-ready | Cut | Not started |
| 12b | [Counterfactual review + briefing export](waves/wave-12b-counterfactual-aar.md) | 12a, 10b, 3 | Sonnet | Redeploy: demo-complete (signed-record beat in 13b) | Cut | Not started |
| 13a | [Team mode](waves/wave-13a-team-mode.md) | 10b, 12a, 4b | Sonnet | Keep live build green | Depth | Not started |
| 13b | [Signed records + competency matrix](waves/wave-13b-trust-competency.md) | 12a, 11b | Sonnet | Keep live build green | Cut | Not started |
| 13c | [Admin + pack manager](waves/wave-13c-admin-packs.md) | 13b, 9a | Sonnet | Keep live build green | Cut | Not started |
| 14a | [Hardening + accessibility](waves/wave-14a-hardening.md) | 7, 12b, 13c | Sonnet | Keep live build green | Cut | Not started |
| 14b | [WebXR (optional)](waves/wave-14b-webxr.md) | 14a | Sonnet | Keep live build green | Depth | Not started |
| 15a | [Submission documentation](waves/wave-15a-submission-docs.md) | cut waves, 14a last | Sonnet | Redeploy: submission build | Cut | Not started |
| 15b | [Release 1.0 polish](waves/wave-15b-release-polish.md) | 15a, plus any depth wave built | Sonnet | Release 1.0 | Depth | Not started |

**Pilot** (the user's activity, not a wave): starts once wave 12a is Done. Waves 12b onward continue alongside it. The demo-complete live link is wave 12b.

## Submission-ready cut

The smallest ordered set of waves that gives a complete, polished, demoable live link covering every problem-statement requirement (R0–R19 in [06-requirements-traceability.md](06-requirements-traceability.md)), the five demo features from [10-differentiators.md](10-differentiators.md) and the documentation a submission needs. Waves marked **Depth** in the table above come after the cut.

**Order:** 1 → 2 → 3 → 4a → 4b → 5 → 6 → 7 → 8 → 9a → 9b → 9c → 10a → 10b → 11a → 11b → 12a → 12b → 13b → 13c → 14a → 15a. That is 22 of 25 waves. The live link exists from wave 2, becomes playable at 5, pilot-ready at 12a (pilot starts), demo-complete at 12b, and submission-ready at 15a; 13b adds the signed-record beat.

**Why it is not smaller.** Every wave in the cut is either a requirement or a dependency of one, as the wave files state them. Examples: the sensor placement trainer (9c) needs the site builder (9b); the full AAR (12a) needs the recognition academy (11b); the signed record and competency matrix (13b) need 12a and 11b; the offline and LAN checks the demo relies on (14a) need the admin wave (13c); the submission documentation (15a) depends on the cut waves with 14a last, and not on 13a or 14b.

**PS coverage in the cut**

| Requirement | Waves |
|---|---|
| R0 AI elements | 4b (AI assist), 11a (learner model, adaptive adversary) |
| R1, R12 single and swarm threats | 8 |
| R2 low cost | 15a (cost sheet), 14a |
| R3, R9 weather, day/night, NV and thermal | 4a, 7 |
| R5, R6, R7 recognise, classify, respond | 4a, 4b, 5, 6 |
| R8, R16 varied scenarios, scripted and generated | 9a (with 9b for sites) |
| R10 degraded sensors | 4a, injects in 10b |
| R11 urban and rural terrain | 7 |
| R13 unit level, offline | 10a, 10b, 13c, 14a (offline and LAN tests), 15a (instructor SOP) |
| R14 minimal hardware | 7 (floor-laptop benchmark), 14a |
| R17 decision-tree scoring | 6 |
| R18 AAR, individual and unit | 12a |
| R19 adjustable difficulty, anti-rote | 9a, 11a |
| R15 desktop or VR-capable | Desktop in the cut; the VR mode is 14b (Depth). The PS says "desktop or VR-capable", so desktop meets it; no VR claim is made. |
| R4 repetitions at scale | Mechanism in the cut; the measured figure comes from the pilot. |
| Traceability, manuals, SOPs, final report | 15a |

**Demo features in the cut (all five):** sensor placement trainer (9b, 9c), contact-report scoring (6), adaptive adversary (11a), counterfactual review (12b), signed record and competency matrix (13b). Director mode (10b) covers the inject beat.

**Depth (after the cut):** 13a team mode, 14b WebXR, 15b release 1.0 polish. Team mode is not needed by any PS clause or demo feature, so the demo's sector-handoff moment (7:00) is dropped or shown as a single-operator swarm run until 13a lands, and track handover (H5 second half) waits with it. Wave 15b documents whichever depth waves were built and adds pilot results.

### Checkpoints

Three points where a reviewer can look at the live link and check what has been built. At each, `make smoke URL=<live url>` passes (`/healthz`, `/readyz`, `/api/v1/version`) and the permanent "fictional scenario · open-source parameters" label is visible.

**Checkpoint A · after wave 8.** Playable single-operator trainer.
- Sign in as a trainee, play the scripted day scenario on radar, EO/IR, RF and acoustic consoles with a fused track table and the simulated AI assist, then finish.
- Rural and urban terrain, day, night, NV and thermal looks, modelled weather and degraded sensors.
- Single drones, swarms, decoys and clutter (birds, kites, balloons, permitted civil drones).
- Cue a sensor, fix a track swap, file a structured contact report, and see the ROE rule text and version when a response is blocked.
- Scored debrief with the decision path and report grades; the same seed and actions reproduce the same result.
- Verify: no ground truth reaches a trainee socket (test); the 12-client load test and the floor-laptop benchmark are recorded in `docs/PERFORMANCE.md`.
- Not yet: generated scenarios, instructor tools, full AAR, adaptive drills.

**Checkpoint B · after wave 12b.** Demo-complete, pilot running.
- Instructor console: cohorts, launch, live monitor with ground truth, inject macros, annotations, pause and branch.
- Generated scenarios marked "verified solvable by test run" with a novelty check; scripted library; scenario editor; site builder; sensor siting with coverage and blind spots.
- Adaptive drills, weakness-biased adversary, stress and fatigue profiles, recognition academy and progression levels.
- Seen-versus-truth replay, unit readiness dashboard, PDF and CSV export, counterfactual branches, clip export. `make demo` reproduces the seeded state labelled "reference data (seeded)".
- Verify: demo must-work items pass as automated checks; the counterfactual with no change reproduces the original score.
- Not yet: signed-record verification, competency matrix, admin tools, security review, submission documents.

**Checkpoint C · after the full cut and wave 15a.** Submission-ready.
- Signed records with a "Record chain verified" screen and CLI, competency matrix, PDF certificates with verification codes.
- Admin: users, units, signed packs, backup and restore.
- Accessibility pass with high-contrast and colour-blind-safe themes, low-bandwidth mode, recorded-feed adapter, security review, offline and two-laptop LAN tests.
- User manual, instructor and admin SOPs, API docs, cost sheet, completed traceability matrix, final report with pilot figures only as measured (pending sections labelled), release notes and the demo rehearsal checklist.
- Verify: tamper one byte of a record and verification fails at that event; the traceability matrix has no empty proof cell; the wording grep passes.
- Not yet: team mode, WebXR, release 1.0 polish (depth).

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
