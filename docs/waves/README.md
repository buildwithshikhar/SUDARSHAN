# Build waves

One file per wave, in dependency order. Each file has the scope, acceptance criteria, and a paste-ready brief. Status lives in [../BUILD_LOG.md](../BUILD_LOG.md), not here.

How to run a wave: open a work session, paste the brief, and review the 10-line summary against the acceptance criteria before starting the next wave.

| Wave | Name | Depends on | Deployment |
|---|---|---|---|
| 1 | [Repo bootstrap](wave-01-repo-bootstrap.md) | — | Deploy-ready: production images and smoke test exist, nothing is hosted yet |
| 2 | [Design system + app shell](wave-02-design-system-shell.md) | 1 | **Priority milestone: first live link** |
| 3 | [Contracts + deterministic sim core](wave-03-contracts-sim-core.md) | 1 | Keep the live build green |
| 4a | [Sensor models](wave-04a-sensor-models.md) | 3 | Keep the live build green |
| 4b | [Tracking, fusion + AI assist](wave-04b-tracking-ai-assist.md) | 4a | Keep the live build green |
| 5 | [Live-session vertical slice](wave-05-live-session-slice.md) | 2, 4b | Redeploy: the live link becomes a playable slice |
| 6 | [Scoring + debrief](wave-06-scoring-debrief.md) | 5 | Redeploy: sessions on the live link now end with a scored debrief |
| 7 | [3D realism + terrain packs](wave-07-3d-realism-terrain.md) | 5 | Keep the live build green; the live link gains the realistic scene |
| 8 | [Threat breadth](wave-08-threat-breadth.md) | 4a, 7 | Keep the live build green |
| 9a | [Scenario engine](wave-09a-scenario-engine.md) | 6, 8 | Redeploy: generated and scripted scenarios on the live link |
| 9b | [Site builder](wave-09b-site-builder.md) | 9a, 7 | Redeploy: instructors can build sites |
| 9c | [Sensor placement trainer](wave-09c-sensor-placement.md) | 9b, 4a, 7 | Redeploy: sensor siting exercise |
| 10a | [Class management + rule packs](wave-10a-class-management.md) | 5, 9a | Keep the live build green |
| 10b | [Live monitor + director mode](wave-10b-director-mode.md) | 10a, 3, 6 | Keep the live build green |
| 11a | [Adaptive learning + adaptive adversary](wave-11a-adaptive-learning.md) | 6, 9a | Keep the live build green |
| 11b | [Recognition academy + progression](wave-11b-recognition-academy.md) | 4a, 8, 11a | Keep the live build green |
| 12a | [Full AAR + reports](wave-12a-aar-reports.md) | 6, 10b, 11b | Redeploy: pilot-ready live link; the pilot can start after this wave |
| 12b | [Counterfactual review + briefing export](wave-12b-counterfactual-aar.md) | 12a, 10b, 3 | Redeploy: demo-complete live link (signed-record beat lands in 13b) |
| 13a | [Team mode](wave-13a-team-mode.md) | 10b, 12a, 4b | Keep the live build green |
| 13b | [Signed records + competency matrix](wave-13b-trust-competency.md) | 12a, 11b | Keep the live build green |
| 13c | [Admin + pack manager](wave-13c-admin-packs.md) | 13b, 9a | Keep the live build green |
| 14a | [Hardening + accessibility](wave-14a-hardening.md) | 7, 12b, 13c | Keep the live build green |
| 14b | [WebXR (optional)](wave-14b-webxr.md) | 14a | Keep the live build green |
| 15a | [Submission documentation](wave-15a-submission-docs.md) | cut waves, 14a last | Redeploy: submission build |
| 15b | [Release 1.0 polish (depth)](wave-15b-release-polish.md) | 15a, plus any depth wave built | Release 1 |

Waves are split into lettered parts (for example 9a, 9b, 9c) where one session would be overloaded. A part is a full wave: its own acceptance, deploy check and log entry. If a session runs out before acceptance, the unfinished remainder is logged as `<wave>.2` (for example `9a.2`). Features beyond the problem statement are scheduled here from [../10-differentiators.md](../10-differentiators.md).
