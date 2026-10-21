# Wave 5 · Live-session vertical slice

| | |
|---|---|
| Depends on | 2, 4b |
| Deployment | Redeploy: the live link becomes a playable slice. |

**Goal.** One scripted scenario playable end to end in the browser, server-authoritative, on the live link.

## Scope

- WebSocket protocol (MessagePack, typed from the contracts), session manager (create, join, leave), 20 Hz server loop, client interpolation to 60 fps.
- Live session workspace layout from `docs/07-ui-map.md`: top bar, basic Three.js EO view (flat terrain, sky, drone and bird meshes, zoom), radar PPI on canvas, track table, decision panel (classify, assess, respond; keyboard-driven).
- Server-side ROE validator from the rule pack; the decision panel shows the rule that permits or forbids each response, with its version.
- One scripted scenario: day, rural flat terrain, one quadcopter, a bird flock and one permitted civil drone.
- Session end stores the hash-chained event log.
- Track-management controls in the track table and decision panel: cue a sensor onto a track, and merge, split, relabel or drop a track, as logged actions from wave 4b.
- 12-client LAN load test with scripted WebSocket clients.

## Out of scope

- Scoring and debrief (wave 6), terrain packs and visual effects (wave 7).

## Acceptance criteria

- A trainee can sign in, start the scripted scenario, detect, classify and respond, and finish; the event log verifies.
- A test asserts that no ground-truth field ever reaches a trainee socket.
- Load test: 12 clients for 5 minutes with tick jitter and message latency reported in the build log, and no dropped session.
- The ROE validator blocks a forbidden response and shows the rule text and version.
- A cue and a track relabel issued from the UI appear in the event log and change the track table (e2e).
- Workspace is keyboard-operable (Tab, C, A, R, H, ?) and axe-clean.
- After the user redeploys, an admin-created trainee account can play the scenario on the live link.
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
ROLE: Build wave 5 (Live-session vertical slice) of SUDARSHAN, an AI-enabled drone and counter-drone threat simulation TRAINER (SIH 2026, PS 26247). Follow the project rules in CONTRIBUTING.md, above all the content rules.

READ FIRST: docs/BUILD_LOG.md (confirm wave 4b is Done and main is green; if not, stop and tell me). Then: docs/07-ui-map.md (live session workspace), docs/05-architecture.md §3.2, docs/08-demo.md (Run 1, for the scenario shape).

GOAL: One scripted scenario playable end to end in the browser, server-authoritative, on the live link.

STEP 1 — Transport (track A, worktree)
- WS endpoint with auth, MessagePack frames typed from the contracts, session manager with an asyncio 20 Hz loop calling the sim core.
- Trainee frames contain only sensor detections, tracks and entities inside the EO field of view. Instructor frames are not built yet.
- Load-test script (12 clients, 5 minutes) under services/api/tests/load/.

STEP 2 — Workspace UI (track B, worktree)
- Layout grid per docs/07-ui-map.md at 1920×1080 degrading to 1366×768.
- EO view in Three.js (flat ground, sky, simple drone and bird meshes, reticle, zoom ladder).
- Radar PPI on canvas (sweep with phosphor decay, range rings, bearing ticks, plots and track symbols).
- Track table and decision panel with the keyboard flow, including cue and track commands. All strings EN and HI.

STEP 3 — Integration (main track)
- ROE validator server-side; responses carry the rule ID, text and pack version.
- Scripted scenario in packs/scenarios/ (fictional names), end-to-end Playwright test that plays it with keyboard only.
- Event log stored at session end; verify on read.

OUT OF SCOPE (do not build):
- Scoring and debrief (wave 6), terrain packs and visual effects (wave 7).

ACCEPTANCE (all must be true):
- A trainee can sign in, start the scripted scenario, detect, classify and respond, and finish; the event log verifies.
- A test asserts that no ground-truth field ever reaches a trainee socket.
- Load test: 12 clients for 5 minutes with tick jitter and message latency reported in the build log, and no dropped session.
- The ROE validator blocks a forbidden response and shows the rule text and version.
- A cue and a track relabel issued from the UI appear in the event log and change the track table (e2e).
- Workspace is keyboard-operable (Tab, C, A, R, H, ?) and axe-clean.
- After the user redeploys, an admin-created trainee account can play the scenario on the live link.
- Every new user-facing string exists in EN and HI (key-parity check passes).
- Every new screen has populated, empty, loading and error states, works by keyboard, and is axe-clean.
- CI is green on `main` (lint, typecheck, unit, e2e, gitleaks, docker build).
- Every feature in this wave has tests; no existing test was skipped, disabled or weakened.
- Production images build and the production-mode compose stack passes `make smoke`.
- `docs/BUILD_LOG.md` is updated per its rules, including the deploy check and the next wave entry point.
- No credentials, secrets or real keys anywhere in git history; only `.env.example` placeholders.
- The deployed build still works: the commit to deploy is recorded in the build log, and after the user redeploys, `make smoke URL=<live url>` passes.

LOG: Follow the rules in docs/BUILD_LOG.md. Add a "Wave 5" entry at the start, append each merged commit, record decisions, test counts and the deploy check, and write the exact first step of wave 6.

STOP CONDITIONS — stop and report if:
- a step needs credentials, or network beyond package registries and GitHub;
- a Docker action would touch anything outside this repo's compose project;
- CI fails 3 times on the same cause;
- about 60% of the session is used before acceptance (commit green work, log it as wave 5.2, stop);
- Never build features from later waves.

FINAL OUTPUT TO ME: at most 10 lines — commits, test counts, CI result, deploy check (and the commit for me to deploy), anything skipped and why, and the first step of wave 6.
````
