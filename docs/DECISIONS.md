# Decision log

ADR-style, one short entry per decision. Newest at the bottom. A changed decision gets a new entry that supersedes the old one; old entries are not edited.

Status values: **Accepted**, **Superseded by ADR-n**.

---

## ADR-001 · Platform name: SUDARSHAN

- **Date:** 2026-10-17 · **Status:** Accepted · **Decided by:** user
- **Context:** The naming check ([01-naming.md](01-naming.md)) found strong overlap with Mission Sudarshan Chakra and the IAF S-400 "Sudarshan", and recommended NIGAH. The user chose to keep SUDARSHAN.
- **Decision:** The platform is SUDARSHAN. In code the name is one value, `productName` in `brand.json` at the repo root (created in wave 1); nothing else hard-codes it. Descriptor line: "Counter-UAS Threat Recognition Trainer".
- **Consequences:**
  - A rename is a one-line `brand.json` change plus a find-and-replace in docs prose.
  - The association risk stays, so every surface carries the line "independent student project, no official affiliation" and avoids chakra, shield, crest, tricolour and emblem imagery.
  - The IP India trade-mark search (Classes 9, 41, 42) is still open; see [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md).

## ADR-002 · Engine: Three.js

- **Date:** 2026-10-17 · **Status:** Accepted · **Decided by:** user, on the analysis in [04-engine.md](04-engine.md)
- **Context:** Browser-based, offline, 8 GB integrated-graphics floor, local scenes up to about 20 × 20 km, WebXR optional.
- **Decision:** Three.js with `WebGLRenderer` as the shipping path; `WebGPURenderer` only behind a flag and only if our benchmark shows a gain. MapLibre GL with offline vector tiles for the 2D map. CesiumJS rejected (offline-tiles burden, no official WebXR); Babylon.js is the fallback only if Three.js XR fails our tests.
- **Consequences:** The benchmark gate in 04 is a wave 7 acceptance criterion, and its result in `docs/PERFORMANCE.md` is the only performance claim we make.

## ADR-003 · Trainee model: operator plus detachment commander

- **Date:** 2026-10-17 · **Status:** Accepted · **Decided by:** user
- **Context:** DSSC trains staff officers, but the PS says "usable at unit level" ([00-gap-check.md](00-gap-check.md) Q1).
- **Decision:** The core trainee is the sensor operator. The detachment commander is a second role in team mode (sector split, handoff). A staff-planning layer (sensor siting, coverage gaps) is a stretch module, not core.
- **Consequences:** Scoring, the UI map and the hero demo target the operator first; team mode (waves 10 and 13) adds the commander.

## ADR-004 · Hardware floor: 8 GB laptop, integrated graphics; VR deferred

- **Date:** 2026-10-17 · **Status:** Accepted · **Decided by:** user
- **Context:** The PS asks for minimal specialised hardware ([00-gap-check.md](00-gap-check.md) Q2).
- **Decision:** The floor is an 8 GB RAM laptop with integrated graphics (Intel Iris Xe class) and no internet. No VR headset is assumed. WebXR stays optional and deferred to wave 14.
- **Consequences:** Without a headset, the only VR claim allowed is "VR mode, emulator-tested". Quality tiers and the benchmark gate are tuned to this floor.

## ADR-005 · Hindi UI from the first wave

- **Date:** 2026-10-17 · **Status:** Accepted · **Decided by:** user
- **Context:** i18n is cheap when wired in early and painful to retrofit ([00-gap-check.md](00-gap-check.md) Q6).
- **Decision:** English and Hindi from wave 1. Wave 1 wires the i18n framework with EN and HI strings for its placeholder page; wave 2 makes it a requirement for every trainee-facing string, with Noto Sans Devanagari self-hosted.
- **Consequences:** No hard-coded user-facing strings. CI checks that every EN key has an HI entry.

## ADR-006 · Deployment is first-class; host must be Docker-capable with persistent storage

- **Date:** 2026-10-17 · **Status:** Accepted · **Decided by:** user
- **Context:** The next SIH milestone is a deployable live link of the platform.
- **Decision:** The first deployable slice (wave 2) goes live early, and every later wave keeps the deployed build working. Hosting needs a Docker-capable host with persistent storage. Render free is unsuitable (no persistent disk, sleeps). A Vercel frontend needs `VITE_API_URL` at build time and `CORS_ORIGINS` on the backend. Health is verified at `/healthz`.
- **Consequences:** Every wave's acceptance includes production images building and `make smoke` passing in production mode. The user deploys; Claude Code never does. The host choice is open ([OPEN_QUESTIONS.md](OPEN_QUESTIONS.md)).

## ADR-007 · Data licence policy: "calibrated from", never "trained on"

- **Date:** 2026-10-17 · **Status:** Accepted · **Decided by:** project standard, from [02-research.md](02-research.md) §7 and [03-data-register.md](03-data-register.md)
- **Context:** Most open drone datasets are research-only, non-commercial, or state no data licence.
- **Decision:** Datasets are used to derive and cite numeric parameters. Raw samples ship only under a confirmed open licence. Non-commercial, research-only and "not stated" sources are never redistributed and never shown as clips. Licence status is re-checked before each release.
- **Consequences:** Every parameter carries a register ID from [DATA_REGISTER.md](DATA_REGISTER.md). Pitch wording: "parameters calibrated from published open research datasets".

## ADR-008 · Scenarios are "verified solvable by test run", not "provably solvable"

- **Date:** 2026-10-17 · **Status:** Accepted · **Decided by:** project standard, from [02-research.md](02-research.md) §6
- **Context:** The generator accepts a scenario only if a headless oracle defender wins it within the time budget. That is a practical check; a formal guarantee would need a constraint encoding we are not building.
- **Decision:** All docs, UI and slides say "verified solvable by test run" (or "verified solvable by an oracle run"). Never "provably solvable" or "guaranteed solvable".
- **Consequences:** The scenario record stores the seed, generator version and every check result, so the AAR can show what was verified.

## ADR-009 · Team: solo, with Claude Code for all coding

- **Date:** 2026-10-17 · **Status:** Accepted · **Decided by:** user
- **Decision:** One person; Claude Code writes all code. Waves run in strict dependency order, with at most 2 worktree subagents per wave.
- **Consequences:** `docs/BUILD_LOG.md` must carry all state across `/clear`.

## ADR-010 · Pilot: 12 civilian volunteers × 4 sessions

- **Date:** 2026-10-17 · **Status:** Accepted · **Decided by:** user
- **Decision:** 12 civilian student volunteers, 4 sessions each (about 30 minutes), starting once wave 12 is green. Consent form, pseudonymous IDs, no personal data beyond a call-sign and cohort.
- **Consequences:** Effectiveness claims are limited to what this pilot measures (learning curves, a new-seed rote-learning test), at Kirkpatrick levels 1–2. With fewer than 8 volunteers we report case studies, not curves.

## ADR-011 · Headline differentiators and README direction

- **Date:** 2026-10-17 · **Status:** Accepted · **Decided by:** user
- **Context:** The PS items are the floor; evaluators need visible capability beyond them. The README also needed to read as a product page, not a planning note.
- **Decision:** Twelve headline features (H1–H12 in [10-differentiators.md](10-differentiators.md)), with five in the 10-minute demo: sensor placement trainer, contact-report scoring, adaptive adversary, counterfactual AAR, signed record with competency matrix. The README is product-led, lists every capability as Planned until merged and deployed, and keeps one neutral data line; the earlier "Honest data", "Scope and safety" and "Affiliation" sections are removed from it. The locked rules in CLAUDE.md are unchanged and still govern the UI labels and wording.
- **Consequences:** Headline features are scheduled into existing waves, not new ones, and wave files change only when each wave starts. The README capability and status tables are updated as waves land.

## ADR-012 · Headline features scheduled into waves; overloaded waves split

- **Date:** 2026-10-17 · **Status:** Accepted · **Decided by:** user
- **Context:** ADR-011 chose twelve headline features. Placing them in the existing 15 waves overloaded several, and the user asked for site builder and sensor placement trainer in separate waves.
- **Decision:** Wave files now carry the headline features. Split waves: 4 → 4a sensor models, 4b tracking and AI assist; 9 → 9a scenario engine, 9b site builder, 9c sensor placement trainer; 10 → 10a class management and rule packs, 10b live monitor and director mode; 11 → 11a adaptive learning with adversary and fatigue, 11b recognition academy and progression; 12 → 12a full AAR and reports, 12b counterfactual review; 13 → 13a team mode, 13b signed records and competency matrix, 13c admin and pack manager; 14 → 14a hardening, 14b WebXR (optional). Waves 3, 5, 6 and 15 gained scope or edits; 1, 2, 7 and 8 are unchanged. Remainder of an unfinished session is logged as `<wave>.2`.
- **Consequences:** The pilot (ADR-010) starts once wave 12a is Done, not 12. The demo-complete live link is 12b; the signed-record beat of the demo needs 13b. Wave 9a stays on Opus; 9b and 9c are Sonnet. Wave 14b may be skipped without blocking release 1.0. Narration (12b) ships as a template narrator only; a local-model backend is an open question.

## ADR-013 · Wave 15 split into 15a (in the cut) and 15b (depth); review checkpoints

- **Date:** 2026-10-17 · **Status:** Accepted · **Decided by:** user
- **Context:** Wave 15 depended on all waves, so the documentation a submission needs (manuals, SOPs, cost sheet, traceability, final report) sat outside the Submission-ready cut (Q-18).
- **Decision:** 15a covers those documents, release notes for the submission and the demo rehearsal; it depends only on the cut waves, with 14a last, and joins the cut (22 of 25 waves). 15b covers the 1.0 polish, documentation of any depth wave built, and pilot results; it is depth, with 13a and 14b. Three review checkpoints are defined in the build log: A after wave 8, B after wave 12b, C after the cut and 15a.
- **Consequences:** The cut ends at 15a. The wave 3 ADR for the RNG scheme and tick model is now ADR-014. Any depth wave built must be documented in 15b, and the manuals state what is not built.

## ADR-014 · RNG scheme and tick model

- **Date:** 2026-10-18 · **Status:** Accepted · **Decided by:** Claude Code in wave 3 (recommended model: Opus), within ADR-016
- **Context:** Replay, snapshots for director mode, counterfactual review, re-scoring and solvability checks need the same spec, seed and action log to give the same result on any machine. Golden files written on macOS (arm64) are checked in CI on Linux (x86_64).
- **Decision:** A fixed 20 Hz tick; time is `tick / 20` from an integer counter, and pause stops ticking instead of being an action. Each tick runs a fixed order: actions, spawns, wind gust, drones in scenario order, tick increment. Randomness comes from one numpy PCG64 stream per subsystem, seeded by `SeedSequence(seed, spawn_key=(first 8 bytes of SHA-256 of the stream name,))`, so streams are independent and adding one never shifts another. Hashed state uses only correctly rounded IEEE operations (`+ - * /`, `sqrt`) and polynomial sin and cos: headings are unit vectors, and noise is a sum of uniforms instead of numpy's normal sampler. State and event hashes are SHA-256 over canonical JSON. The rules are in [SIM_CORE.md](SIM_CORE.md).
- **Alternatives:** One global generator (rejected: any new draw shifts every later number). Python's `random` (rejected: no independent streams, and `hash()`-based seeding is salted per process). Variable time step (rejected: not reproducible). Plain `math.sin` and numpy normals (rejected: platform maths libraries may differ in the last bit, which grows into different hashes over thousands of ticks).
- **Consequences:** Contributors follow the determinism rules in SIM_CORE.md. A change to a physics constant or the tick order is deliberate and regenerates the golden files. Vectorising with numpy later must avoid reductions and transcendentals on hashed state, or prove bit-equality across platforms first.

## ADR-015 · Monorepo and stack

- **Date:** 2026-10-17 · **Status:** Accepted · **Decided by:** project standard (CLAUDE.md), recorded in wave 1
- **Context:** One person builds everything with Claude Code, and the deliverable is a deployable live link.
- **Decision:** One repository with `apps/web` (React, TypeScript strict, Vite, Tailwind, Vitest, Playwright), `services/api` (Python 3.12, FastAPI, SQLAlchemy 2, Alembic, Pydantic v2, uv), `packs/`, `infra/` and `docs/`. SQLite by default and Postgres 16 in compose. The product name lives only in `brand.json`; the Makefile derives the compose project name and image labels from it. Docker build context is the repository root so both images can read `brand.json`. Secrets come from the environment, and `make env` generates a git-ignored `.env`.
- **Consequences:** Renaming the product is a one-line change plus a prose find-and-replace. Hosts must run Docker with persistent storage (ADR-006).

## ADR-016 · Server-authoritative deterministic simulation

- **Date:** 2026-10-17 · **Status:** Accepted · **Decided by:** project standard (CLAUDE.md), recorded in wave 1
- **Context:** Replay, re-scoring, solvability checks, pause, branching and team mode all need one source of truth, and trainees must not be able to see ground truth.
- **Decision:** The simulation runs on the server as a seeded, deterministic Python core at 20 Hz. The browser receives only what its sensors would report. Given the same scenario, seed and action log, the result is identical tick for tick.
- **Consequences:** No simulation logic runs in the client. Determinism is tested in CI from wave 3, and snapshots enable branching and counterfactual review later.

## ADR-017 · Sensor framework: fixed draw budget, profile-borne confusion tables

- **Date:** 2026-10-18 · **Status:** Accepted · **Decided by:** Claude Code in wave 4a (recommended model: Opus), within ADR-014 and ADR-016
- **Context:** Four sensor modalities will be built by separate agents and must behave alike, stay deterministic across platforms, and carry a data-register ID on every parameter. Detections feed the event log, so their maths is subject to the ADR-014 rules.
- **Decision:** One `Sensor` template method owns interval, coverage, draws, degradations and cueing; a model supplies only `p_detect` and `measure`. Each candidate target takes a fixed 18 uniforms from the `sensors` stream whatever happens to it. Bearings and elevations use new polynomial `atan2`, `exp` and `log` in `detmath`. Class confusion tables are an optional `confusion` object in `sensor-profile.v1` (additive, so still v1), with one register ID and `verified` flag per table and rows that must sum to 1. Per-class signature figures are ordinary parameters named `<prefix>_<class_id>` with a `<prefix>_default` fallback.
- **Alternatives:** Per-sensor RNG streams (rejected: the wave and ADR-014 name one `sensors` stream, and a fixed per-candidate budget already stops outcome-dependent drift). Encoding the matrix as flat numbered parameters (rejected: needs up to n² names against a 64-parameter limit, and loses the row check). Draws only for detected targets (rejected: any change to detection probability would shift every later number).
- **Consequences:** A new `sensor-profile.v1` schema and TypeScript type (regenerated, drift-checked). A model that needs more than four noise draws or more than one classification draw per target must extend `Draws` and record a behaviour change. Adding a sensor to a scenario shifts the `sensors` numbers of later sensors, as editing a scenario does.

## ADR-018 · Sensor models: closed-form P(d), shared profile conventions, honest provenance

- **Date:** 2026-10-18 · **Status:** Accepted · **Decided by:** Claude Code in wave 4a, within ADR-017
- **Context:** Radar, EO/IR, RF and acoustic models were built in parallel and must read alike, stay inside the ADR-014 maths rules, and not overstate where a number came from.
- **Decision:** Each model gives `P(d)` as a closed-form, monotonic function of range (radar equation margin, Johnson pixel thresholds, link budget, acoustic signal-to-noise) passed through a logistic (EO/IR: the equivalent power-law form r^k/(1+r^k)), with weather, light and degradations as dB or ratio terms; none uses a lookup that could rise with range. RF-silent classes return exactly 0 before any draw is compared. Profiles are named `<id>.v1.yaml`; `tests/test_contracts.py` still expects exactly one example per contract except `sensor-profile.v1`. A figure that is only consistent with a published range (radar RCS) is cited F01 with `verified: false`, not attributed to a dataset it was not extracted from; `verified: true` is used only where the profile holds the figure stated in docs/02-research.md (Johnson criteria and the thermal camera field and pixel count, from D12). Framework fixes made while integrating: the false-alarm hook now runs during an outage (discarded), so the stream never shifts, and `cue` applies the zoom at once.
- **Alternatives:** Lookup tables of range (rejected: not guaranteed monotonic, more parameters to cite). Attributing RCS to D14 (rejected: overstates provenance, against locked rule 1).
- **Consequences:** Register rows for the published sources are Q-20; extending to more threat classes is Q-21 (wave 8). Radar, RF and acoustic confusion tables are F01 until calibrated.

## ADR-019 · Tracking: errors only where gates overlap, ground truth beside the tracker, reference-data labels

- **Date:** 2026-10-18 · **Status:** Accepted · **Decided by:** Claude Code in wave 4b (recommended model: Opus), within ADR-014, ADR-016 and ADR-017
- **Context:** The tracker must fail the way real ones do (swaps, splits, merges) yet never mix up well-separated targets, the errors must be scoreable with true identities, replay and snapshots must stay exact, and no sensor-derived figure may reach a trainee as if it were measured (locked rule 1, Q-20).
- **Decision:** (1) The tracker's only input is `Detection.trainee_view()` through `Measurement.from_view`, which refuses a ground-truth reference; ground truth reaches a separate `TruthLedger` through a per-report reference number and never flows back. (2) Association is gated nearest-neighbour on a pure-Python six-state Kalman filter (only `+ - * /` and `sqrt`, so state is hashable across platforms). Gated pairs form components; only a component with two tracks or two reports is *ambiguous* and goes to a seeded `ErrorPolicy` (swap, split or merge cut from one `tracking` draw per report), so errors are structurally impossible for targets that stay apart. (3) An initiation-exclusion zone keeps a lone target's gate-edge outlier from starting a second track. (4) Duplicate tracks fold by a statistical test on position and velocity, not a fixed distance. (5) Track commands and sensor cues are ordinary logged actions (`action-record.v1` widened by five values, additive); there is no undo, only a further command. (6) The sensor picture attaches to `World` optionally and adds a `picture` key to the state only when present, so existing golden files and hashes are unchanged. (7) `Detection.reference_data` is stamped by the sensor template method from the profile, so every trainee-visible detection, track and assist view carries `data_status`, `reference` unless every parameter of the profile is `verified: true`. (8) The AI assist uses stateless keyed SHA-256 draws rather than a stream, so it cannot shift another subsystem and needs no draw-position snapshot.
- **Alternatives:** Letting the tracker see `truth_id` to "cheat" association (rejected: the algorithm would depend on what a trainee cannot know). Random swaps at any crossing regardless of geometry (rejected: breaks "never for well-separated targets"). A numpy filter (rejected: BLAS can differ in the last bit and the state is hashed). Adding an `assist` RNG stream (rejected: it would change every existing golden hash). Waiting for the Q-20 register rows before showing any figure (rejected: blocks wave 5; labelling meets the rule now).
- **Consequences:** Wave 5 must send a trainee only `TRAINEE_EVENT_TYPES` and `trainee_frame()`. Wave 6 scores unfixed errors from `ledger.*` events and `open_errors()`. `replay` needs to be told whether a session had a picture until the session record says so. The tracker, error and assist parameters are F01 (`verified: false`); they stay labelled reference data. Swaps are rare at the default maxima (4 of 300 seeds on the documented crossing); a scenario raises `swap_max` for more.


## ADR-020 · Live session: operators act on tracks, rules cite the closest rule, one allow-list for what a trainee sees

- **Date:** 2026-10-18 · **Status:** Accepted · **Decided by:** Claude Code in wave 5, within ADR-016 and ADR-019
- **Context:** The live slice needs a trainee who works with tracks (the only thing they can see), rules of engagement that explain themselves, a log that replays, and a hard guarantee that no ground truth reaches a trainee.
- **Decision:** (1) A trainee action names a track, never a drone; the world resolves the real drone through the ledger and logs it as `target` for scoring. (2) `sim/roe.py` is a pure function of the rule pack and the track's context (the operator's own assessment, the zone, the class support). Rules only permit; the verdict cites the permitting rule, or the *closest* rule with what is missing (unmet conditions, effector class, authority), and always the pack version. `hold` is always permitted. A commander-authority rule is unavailable to a single operator (team mode is wave 13a). A blocked response changes nothing and is logged as `roe.verdict` only. (3) `sim/audience.py` is the single allow-list of event types a trainee sees, with `target` removed; the socket and the stored-log endpoint both use it. (4) The EO view is drawn from EO and IR reports at the sensor's angular resolution, so no server-side "entities in view" list is needed and none can leak. (5) `scenario.v1` gains two optional fields, `Threat.disposition` (ground truth, default `hostile`) and `filed_flights` (told to the trainee, never linked to a contact), and `session-record.v1` gains a `roe` flag, all additive with defaults. (6) The live protocol is two further contracts, `live-client.v1` and `live-server.v1`, typed in Pydantic, exported as JSON Schema and generated as TypeScript like the others. (7) One API worker holds all running sessions in memory; a disconnect pauses the session until a grace period ends.
- **Alternatives:** Letting the client send drone IDs (rejected: the action log would be the client's word about ground truth). A `forbids` list in the rule pack to give blocked responses a rule to cite (rejected for now: a contract change for little gain; the closest-rule explanation shows the same facts). Sending the server's idea of which entities are in the EO field of view (rejected: a second channel that must be kept leak-free). Tick loops per client or a shared worker pool (rejected: sessions are cheap, about 0.1 ms per tick).
- **Consequences:** Wave 6 scores from `roe.verdict`, `action.*` with `target`, and `ledger.*`. Wave 10b adds instructor frames beside the trainee frame. Running more than one API worker needs session affinity or a shared store and is out of scope. The three rules in the baseline pack are the only ROE text a trainee sees; richer packs are wave 10a.

## ADR-021 · Terrain: baked packs, a datum at the lowest post, line of sight after the draw

- **Date:** 2026-10-18 · **Status:** Accepted · **Decided by:** Claude Code in wave 7, within ADR-014 and ADR-020
- **Context:** The scene needs real-shaped terrain and buildings offline, the sim needs line of sight from the same data, and detections must still replay bit for bit on every platform.
- **Decision:** (1) Terrain is baked offline by `tools/terrain` (own uv project, reproducible: two bakes are byte-identical and every file is hashed in the manifest) into read-only packs under `packs/terrain/<id>/`; raw SRTM and OSM files stay in `data/raw/`. (2) The pack datum is the lowest SRTM post, so every height is at least 0 and a scenario's `z` is never negative; `z` is metres above the datum. (3) `scenario.v1` terrain is a discriminated union of `flat` and `pack`; flat scenarios, logs and hashes are unchanged, and a pack scenario's `session.start` event carries the pack's hash. (4) Line of sight is `sim/terrain.py`: bilinear ground plus a 5 m building-roof raster, sampled every 5 m with `+ - * /`, `sqrt` and `floor` only, endpoints excluded. Sensors with `needs_line_of_sight` (radar, EO/IR) test it after the detection draw, so hiding a target never shifts a random stream. Acoustic needs none; RF is not occluded (Q-25). (5) The API serves pack files from an allow-list to signed-in users; the client loads them from the briefing's terrain descriptor and falls back to flat ground with a notice. (6) The benchmark is a demo-mode `/bench` route using the production scene code; a pass is "High holds median 45 and 5th-percentile 30 fps in thermal, or Auto holds 30", exactly the gate in docs/04-engine.md, and no figure is quoted until the owner runs it on the floor laptop.
- **Alternatives:** Datum at the pack centre (rejected: negative heights, and threat class altitude bands start at 5 m). Triangle-exact ray casting against the render mesh (rejected: slower and no closer to the truth than 31 m SRTM posts). Letting the client decide visibility (rejected: the server is authoritative). A shared Python and TypeScript LOS (rejected: nothing in the client needs it).
- **Consequences:** Heights and roofs are open reference data a few metres off (building heights are mostly defaults, counted in each manifest). A play area larger than its pack is refused. Scenarios on a pack author `z` as height above the datum, so a drone at "ground plus 12 m" is written as that sum. Multipath and RF shadowing are later work.


## ADR-022 · Threat catalogue: eleven truth classes, nine recognition classes

- **Date:** 2026-10-19 · **Status:** Accepted · **Decided by:** Claude Code in wave 8, within ADR-017, ADR-018 and locked rules 1 and 2
- **Context:** Wave 8 adds FPV, medium and large fixed-wing, RF-silent and decoy drones, a permitted civil drone, kites and balloons. The sensors key per-class figures by class ID, the trainee classifies from a short list, and a trainee who says "quadcopter" about an RF-silent quadcopter or a decoy is right.
- **Decision:** (1) The catalogue is a pack contract, `threat-class.v1`, one YAML per class in `packs/threats/`, loaded by `sim/catalogue.py`. It holds the kinematic envelope and the sensor signature of each class, every value with a register ID and a `verified` flag. (2) Eleven truth classes (`class_id` in a scenario): rotary-small, fpv-small, autonomous-small, decoy-small, civil-drone, fixed-wing-small, fixed-wing-medium, fixed-wing-large, bird, kite, balloon. (3) Each maps to one of nine **recognition classes**, which are the operator's vocabulary and what scoring, the contact report and the assist compare against: `autonomous-small`, `decoy-small` and `civil-drone` are scored as `rotary-small`. Nine fit the decision panel's keys 1 to 9; the first four keep their old positions. (4) Sensor confusion tables gain the new labels by appending columns and rows, so every earlier row and every golden hash is unchanged. Sensor labels are coarse look-alike families; the trainee separates FPV, quadcopter and the three fixed-wing sizes from features (speed, size, harmonics, band). (5) The sensor profile limit of 64 parameters becomes 128 (additive). Profile versions are not bumped, as for the rule pack in wave 6, because nothing has been stored in the field; from the first pilot session a content change bumps the version. (6) Envelope and signature values are project-authored (F01, `verified: false`) because the UAV Database (X01) has not been downloaded; Q-11 stays open. (7) The assist treats kite and balloon as non-threats; a civil drone is a quadcopter to it, since it cannot see a filed flight.
- **Alternatives:** One truth class per operator class with a flag for silent, decoy and civil (rejected: the sensor models read per-class figures, so a flag would need a second lookup in every model). Letting the trainee name `decoy-small` (rejected: it looks like a quadcopter; whether it is a decoy is an assessment, not a recognition). Full-width label sets per sensor (rejected: radar cannot tell an FPV from a quadcopter, so the table says so).
- **Consequences:** A scenario threat's limits must lie within its class envelope (`Catalogue.check_scenario`, run by `sim-check` and in tests). A new class cannot ship without rows in every profile (test). The class table is generated into docs/THREAT_CATALOGUE.md and a test fails if it drifts.

## ADR-023 · Behaviours: groups steer members inside their own envelopes, keyed draws, kinematics only

- **Date:** 2026-10-19 · **Status:** Accepted · **Decided by:** Claude Code in wave 8, within ADR-003 (server-authoritative sim) and locked rule 2
- **Context:** Swarms, flocks, kites and balloons must exist at behaviour level, deterministically, without any guidance, targeting or terminal-attack logic, and without changing a single existing hash.
- **Decision:** (1) `scenario.v1` gains `groups` (swarm or flock: members, topology, intent, route, discipline, link loss, leader-loss mode) and `Threat.motion` (tether or drift), all additive with defaults. (2) A group plans once per tick and returns a heading, airspeed and altitude per member; each member is then moved by `kinematics.step_steered`, the code a route follower uses, so every member keeps its own class envelope. (3) Boids (separation, alignment as a consensus step over linked neighbours, cohesion, goal), Vicsek heading noise as the "discipline" knob (held for a second per member, otherwise the turn-rate limit averages it away), leader-follower slots, a leaderless virtual guide, and link loss drawn per link epoch (1 s) instead of per tick. (4) Randomness is keyed SHA-256 draws (`seed, group, member, tick, purpose`), not a new stream, so `rng.STREAMS` and every other hash are untouched; group state sits in `World.state()` only when the scenario has groups. (5) Leader loss is specified: a `group.leader_lost` event, a hold of `leader_loss_hold_s` at the last formation heading and speed, then `elect` (lowest ID leads), `disperse` (leaderless) or `loiter` (circle the centroid). (6) Intents are route shapes: loiter (orbit a point), probe (out to a standoff and back, repeated), saturation (parallel lanes arriving together), transit. (7) Rule 2 is enforced by construction and by a source-reading test: nothing in `sim/behaviours/` takes or reads an asset, zone, sensor, operator, tracker or rule pack, and the words guidance, target, attack, engage, impact, dive, terminal, pursuit and intercept may not appear in it. (8) Decoy and RF-silent fractions and arrival profiles are authoring helpers (`arrival.py`), not world logic; `spawn_s` stays authoritative. (9) All numbers are project-authored (F01, `verified: false`); the cited models are the basis, not validation. Stigmergy is not implemented.
- **Alternatives:** A new RNG stream (rejected: it changes every state hash). Per-tick link draws (rejected: about 40,000 hashes a second at 64 members). Group members flying their own routes with an offset (rejected: no cohesion, no leader to remove). A numpy-vectorised swarm (rejected: reductions can differ between platforms).
- **Consequences:** 57 contacts with the full sensor picture cost about 6 to 7 ms a tick on the build laptop (one API process serves many sessions, so this is the number to watch in the load test). A follower out of link range of the leader's component falls back to flocking, so a scenario's `link_range_m` must cover its formation. The effector wave will set a member's status to remove it; tests set it directly. Wave 9a generates scenarios with these helpers.
