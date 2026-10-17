# Build waves

One file per wave, in dependency order. Each file has the scope, acceptance criteria, recommended model and a paste-ready prompt for Claude Code. Status lives in [../BUILD_LOG.md](../BUILD_LOG.md), not here.

How to run a wave: `/clear`, switch to the recommended model, paste the prompt, and review the 10-line summary against the acceptance criteria before starting the next wave.

| Wave | Name | Depends on | Model | Deployment |
|---|---|---|---|---|
| 1 | [Repo bootstrap](wave-01-repo-bootstrap.md) | — | Sonnet | Deploy-ready: production images and smoke test exist, nothing is hosted yet |
| 2 | [Design system + app shell](wave-02-design-system-shell.md) | 1 | Sonnet | **Priority milestone: first live link** |
| 3 | [Contracts + deterministic sim core](wave-03-contracts-sim-core.md) | 1 | Opus | Keep the live build green |
| 4a | [Sensor models](wave-04a-sensor-models.md) | 3 | Opus | Keep the live build green |
| 4b | [Tracking, fusion + AI assist](wave-04b-tracking-ai-assist.md) | 4a | Opus | Keep the live build green |
| 5 | [Live-session vertical slice](wave-05-live-session-slice.md) | 2, 4b | Sonnet | Redeploy: the live link becomes a playable slice |
| 6 | [Scoring + debrief](wave-06-scoring-debrief.md) | 5 | Sonnet | Redeploy: sessions on the live link now end with a scored debrief |
| 7 | [3D realism + terrain packs](wave-07-3d-realism-terrain.md) | 5 | Sonnet (Opus if gate fails) | Keep the live build green; the live link gains the realistic scene |
| 8 | [Threat breadth](wave-08-threat-breadth.md) | 4a, 7 | Sonnet | Keep the live build green |
| 9a | [Scenario engine](wave-09a-scenario-engine.md) | 6, 8 | Opus | Redeploy: generated and scripted scenarios on the live link |
| 9b | [Site builder](wave-09b-site-builder.md) | 9a, 7 | Sonnet | Redeploy: instructors can build sites |
| 9c | [Sensor placement trainer](wave-09c-sensor-placement.md) | 9b, 4a, 7 | Sonnet | Redeploy: sensor siting exercise |
| 10a | [Class management + rule packs](wave-10a-class-management.md) | 5, 9a | Sonnet | Keep the live build green |
| 10b | [Live monitor + director mode](wave-10b-director-mode.md) | 10a, 3, 6 | Sonnet | Keep the live build green |
| 11a | [Adaptive learning + adaptive adversary](wave-11a-adaptive-learning.md) | 6, 9a | Sonnet | Keep the live build green |
| 11b | [Recognition academy + progression](wave-11b-recognition-academy.md) | 4a, 8, 11a | Sonnet | Keep the live build green |
| 12a | [Full AAR + reports](wave-12a-aar-reports.md) | 6, 10b, 11b | Sonnet | Redeploy: pilot-ready live link; the pilot can start after this wave |
| 12b | [Counterfactual review + briefing export](wave-12b-counterfactual-aar.md) | 12a, 10b, 3 | Sonnet | Redeploy: demo-complete live link (signed-record beat lands in 13b) |
| 13a | [Team mode](wave-13a-team-mode.md) | 10b, 12a, 4b | Sonnet | Keep the live build green |
| 13b | [Signed records + competency matrix](wave-13b-trust-competency.md) | 12a, 11b | Sonnet | Keep the live build green |
| 13c | [Admin + pack manager](wave-13c-admin-packs.md) | 13b, 9a | Sonnet | Keep the live build green |
| 14a | [Hardening + accessibility](wave-14a-hardening.md) | 7, 12b, 13c | Sonnet | Keep the live build green |
| 14b | [WebXR (optional)](wave-14b-webxr.md) | 14a | Sonnet | Keep the live build green |
| 15a | [Submission documentation](wave-15a-submission-docs.md) | cut waves, 14a last | Sonnet | Redeploy: submission build |
| 15b | [Release 1.0 polish (depth)](wave-15b-release-polish.md) | 15a, plus any depth wave built | Sonnet | Release 1 |

Waves are split into lettered parts (for example 9a, 9b, 9c) where one session would be overloaded. A part is a full wave: its own acceptance, deploy check and log entry. If a session runs out before acceptance, the unfinished remainder is logged as `<wave>.2` (for example `9a.2`). Features beyond the problem statement are scheduled here from [../10-differentiators.md](../10-differentiators.md).
