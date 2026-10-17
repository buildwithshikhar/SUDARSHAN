# Build waves

One file per wave, in dependency order. Each file has the scope, acceptance criteria, recommended model and a paste-ready prompt for Claude Code. Status lives in [../BUILD_LOG.md](../BUILD_LOG.md), not here.

How to run a wave: `/clear`, switch to the recommended model, paste the prompt, and review the 10-line summary against the acceptance criteria before starting the next wave.

| Wave | Name | Depends on | Model | Deployment |
|---|---|---|---|---|
| 1 | [Repo bootstrap](wave-01-repo-bootstrap.md) | — | Sonnet | Deploy-ready: production images and smoke test exist, nothing is hosted yet |
| 2 | [Design system + app shell](wave-02-design-system-shell.md) | 1 | Sonnet | **Priority milestone: first live link** |
| 3 | [Contracts + deterministic sim core](wave-03-contracts-sim-core.md) | 1 | Opus | Keep the live build green |
| 4 | [Sensor models + fusion + AI assist](wave-04-sensors-fusion.md) | 3 | Opus | Keep the live build green |
| 5 | [Live-session vertical slice](wave-05-live-session-slice.md) | 2, 4 | Sonnet | Redeploy: the live link becomes a playable slice |
| 6 | [Scoring + debrief](wave-06-scoring-debrief.md) | 5 | Sonnet | Redeploy: sessions on the live link now end with a scored debrief |
| 7 | [3D realism + terrain packs](wave-07-3d-realism-terrain.md) | 5 | Sonnet | Keep the live build green; the live link gains the realistic scene |
| 8 | [Threat breadth](wave-08-threat-breadth.md) | 4, 7 | Sonnet | Keep the live build green |
| 9 | [Scenario engine](wave-09-scenario-engine.md) | 6, 8 | Opus | Redeploy: generated and scripted scenarios on the live link |
| 10 | [Instructor console](wave-10-instructor-console.md) | 5, 9 | Sonnet | Keep the live build green |
| 11 | [Adaptive learning + recognition library](wave-11-adaptive-learning.md) | 6, 9 | Sonnet | Keep the live build green |
| 12 | [Full AAR + reports](wave-12-aar-reports.md) | 6, 10, 11 | Sonnet | Redeploy: demo-complete live link |
| 13 | [Team mode, trust and admin](wave-13-team-trust-admin.md) | 10, 12 | Sonnet | Keep the live build green |
| 14 | [WebXR + hardening](wave-14-webxr-hardening.md) | 7, 12 | Sonnet | Keep the live build green |
| 15 | [Docs + release 1.0](wave-15-docs-release.md) | all | Sonnet | Release 1 |
