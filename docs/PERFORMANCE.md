# Performance

Measured results only. Each section says what was measured, on what, and how to repeat it. Nothing here is a claim about a different machine; the floor-laptop benchmark for the 3D view is wave 7 (Q-04).

## Live session load (wave 5)

12 scripted WebSocket clients, each with its own account and its own session of the Harrier Field scenario, running for 300 s against one API process (uvicorn, one worker, SQLite). Each client starts the session, plays a scripted sequence through the real protocol (classify, assess, hold, cue and relabel on whatever tracks appear) and pings once a second. At the end every session is stored, read back and its event chain verified.

| Measure | Result |
|---|---|
| Sessions dropped | 0 (12 of 12 completed and verified) |
| Frame rate per client | 20.0 Hz, 0 tick gaps (71,988 frames) |
| Inter-frame arrival (client) | p50 50.06 ms, p95 54.62, p99 63.70, max 213.23 |
| Arrival jitter, absolute difference from 50 ms | p50 0.81 ms, p95 9.36, p99 19.49, max 163.23 |
| Ping round trip (message latency) | p50 3.15 ms, p95 14.31, p99 19.30, max 36.09 |
| Server tick lateness | p50 0.67 ms, p95 3.86, p99 10.12, max 146.15 |
| Server tick cost (step, frame build, encode, send) | p50 0.67 ms, p95 1.59, p99 2.64, max 119.37 |
| Server lag drops, frames dropped | 0, 0 |
| Server process | 25.4 % of one core, 90 MB resident |
| Actions | 648 sent, 0 refused |

Machine: the build laptop (Apple silicon, other applications open), clients and server on one host over the loopback interface, so network latency is not represented. Measured 2026-10-18. A first run on the same laptop while two build agents were running showed 24 lag drops of about 0.5 s and a p99 tick lateness of 34 ms; the figures above are from a quiet run. The simulation step alone costs 0.13 ms per tick with the sensor picture and the rules attached.

Repeat: `cd services/api && uv run python -m tests.load.run_load --clients 12 --seconds 300 [--url http://host:port] [--json out.json]`. With no `--url` the script starts its own server on a free port with a temporary database. A 3-client, 4-second version runs in the normal test suite (`tests/test_load_smoke.py`). Re-run it against the deployed host and on the two-laptop LAN before quoting it for those.

## Web bundle (wave 5)

The main bundle is 129 kB gzipped. The EO view (Three.js) is a separate lazy chunk of 545 kB, 138 kB gzipped, loaded only when a session opens. Production builds contain no mock transport (`tests/live/prodBuild.test.ts`).

## 3D scene benchmark (wave 7)

**Status: harness built, not yet run on the floor laptop.** No frame-rate figure is claimed. The gate (docs/04-engine.md): at 1920 × 1080, at least 45 fps median and at least 30 fps 5th percentile, or an auto tier that holds 30 fps; first load at most 8 s from the local server; JS at most 1.5 MB gzipped excluding assets.

The harness is the `/bench` route (demo mode only; sign in, then open `/bench`). It loads the rural pack "Heron Ridge" from the API, draws the reference scene through the production EO scene code (41 buildings, a 24-drone placeholder swarm and 30 birds drawn as EO markers, terrain, trees, sky, fog) at exactly 1920 × 1080 with the pixel ratio fixed at 1, and measures five phases of 15 to 20 s each after a warm-up: High, Medium and Low tiers with the thermal pass on, the Auto controller, and High in daylight. It shows the percentiles and the verdict and saves a JSON file (`bench-result.v1`) with the device facts (GPU renderer string, cores, reported memory, display) and the scene counts. Frame times are animation-frame intervals, so a 60 Hz display caps results at 60 fps.

To record a result: close other applications, run the demo stack (`make demo`, or the instructor laptop serving it on the LAN; the production host does not serve `/bench`), open it in Chrome on the floor laptop, sign in as a demo account, open `/bench`, run it, download the JSON and paste its `phases` and `device` blocks here with the date and the commit (`build.gitSha`). If the gate is not met, stop and say so (the fix continues on Opus, wave file 7).

Measured on the build laptop (Apple silicon, Python 3.12, numpy): the line-of-sight query costs about 0.04 to 0.08 ms per segment over the shipped packs (500 random segments each). Only a detection that already passed its probability draw is tested, so the worst case for 24 contacts and two line-of-sight sensors is about 48 queries, roughly 2 to 4 ms, per sensor update.

**Web bundle (wave 7).** JavaScript is 143.8 kB gzipped for the first load and 319.4 kB gzipped in total including the lazy 3D scene chunk (`npm run bundle:check`, enforced in CI at 1.5 MB). Headless Chromium on software rendering (SwiftShader) picks the Low tier in Auto; that is a property of the CI renderer and says nothing about a real GPU.

