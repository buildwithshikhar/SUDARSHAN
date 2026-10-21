# SUDARSHAN · Final project report

**Counter-UAS Threat Recognition Trainer**
Smart India Hackathon 2026 · Problem statement 26247 · Ministry of Defence, Defence Services Staff College · Category Software · Theme Robotics and Drones

| | |
|---|---|
| Report date | 2026-10-20 |
| Repository state | `main` at `07c971d` (288 commits, 17 to 20 October 2026) |
| Live link | https://sudarshan.centralindia.cloudapp.azure.com (running the wave 2 build, commit `b722313`; later builds are ready to deploy) |
| Team | The SUDARSHAN team (see Team) |
| Affiliation | Independent student project. No official affiliation with any ministry, service or programme. |

> **Honesty statement.** SUDARSHAN is built from open research datasets and published specifications, in fictional scenarios. It contains no operational or classified data, makes no claim of validated training effectiveness and makes no claim of doctrinal accuracy. Rules of engagement and effector classes are a fictional, editable rule set. Several screens show seeded demonstration data (section 13.5); those figures are not measurements. The pilot with volunteers has not run yet, so this report gives no effectiveness result.

---

## Team

SUDARSHAN is a hackathon team project. Fields below are for the owner to complete before submission.

| Field | Entry |
|---|---|
| Team name | _to be filled in_ |
| Team lead | _to be filled in_ |
| Members and roles | _to be filled in_ |
| Institute | _to be filled in_ |
| Mentor | _to be filled in_ |

## Contents

1. [Executive summary](#1-executive-summary)
2. [The problem](#2-the-problem)
3. [The solution](#3-the-solution)
4. [Requirement coverage](#4-requirement-coverage)
5. [System architecture](#5-system-architecture)
6. [Deterministic simulation core](#6-deterministic-simulation-core)
7. [Sensor models](#7-sensor-models)
8. [Tracking, fusion and the simulated AI assist](#8-tracking-fusion-and-the-simulated-ai-assist)
9. [Threat catalogue and behaviours](#9-threat-catalogue-and-behaviours)
10. [Scenario engine](#10-scenario-engine)
11. [Scoring and debrief](#11-scoring-and-debrief)
12. [Terrain and the 3D scene](#12-terrain-and-the-3d-scene)
13. [The application, seat by seat](#13-the-application-seat-by-seat)
14. [Security and deployment](#14-security-and-deployment)
15. [Quality engineering](#15-quality-engineering)
16. [Performance](#16-performance)
17. [Data policy, honesty and safety](#17-data-policy-honesty-and-safety)
18. [Build progress](#18-build-progress)
19. [Limitations and open items](#19-limitations-and-open-items)
20. [Next steps](#20-next-steps)
21. [Appendix A · Screenshot gallery](#appendix-a--screenshot-gallery)
22. [Appendix B · Document index](#appendix-b--document-index)

---

## 1. Executive summary

Small, cheap drones, used alone or in swarms, are now a decisive factor in conflict, and the troops who must recognise them get few repetitions: classroom slides and occasional live drills that are costly and weather-bound. SUDARSHAN is a browser-based trainer in which an operator watches simulated radar, EO/IR, RF and acoustic sensors, builds a fused track picture, classifies each contact, assesses its intent and chooses a response that a rule engine checks against an editable, fictional rule pack. Every decision is scored on an explainable Detect → Classify → Assess → Respond tree, and the trainee gets a debrief that says why marks were lost.

What makes it credible as engineering:

- **Server-authoritative and deterministic.** A Python simulation core ticks at 20 Hz on the server. The browser never receives ground truth, only sensor reports. The same scenario, seed and actions give the same result tick for tick, on macOS and on Linux, which makes replay, re-scoring and tamper-evident records possible.
- **Sensors that fail like sensors.** Closed-form detection probabilities fall with range, weather and light; terrain and buildings block line of sight; a tracker produces real track swaps, splits and merges at deterministic, documented ticks.
- **Breadth.** Eleven threat and clutter classes (quadcopter, FPV, fixed-wing small/medium/large, autonomous, decoy, civil drone, bird, kite, balloon), 24-drone swarms with leader loss and link loss, 30-bird flocks, two real-shaped terrain packs, day, night vision and thermal looks, modelled weather.
- **Procedural scenarios that are verified solvable by test run.** A generator samples scenarios under hard constraints, runs a perfect-policy oracle defender on each one and keeps only those it clears, then filters for diversity.
- **Enterprise-grade delivery.** Docker images, production guard rails, HTTPS, backup and restore scripts, CI with six jobs, about 6,000 automated tests, accessibility checks (axe) in English and Hindi, dark and light.

**Where it stands.** Waves 1 to 8 of a 25-wave plan are built and green on CI, and the scenario engine (wave 9a) is built on `main`. The front end now has a populated screen behind every sidebar item for all four seats (trainee, detachment commander, instructor, administrator); screens whose backend lands in later waves read a seeded module. Outstanding: the floor-laptop 3D benchmark, the redeploy of the current build to the live link, the volunteer pilot, and waves 9b to 15a.

## 2. The problem

Problem statement 26247, *AI-Enabled Drone & Counter-Drone Threat Simulation Trainer* (full text in [PS-26247.md](PS-26247.md)):

- **Background.** Low-cost commercial and military-grade drones, individually and in swarms, have become decisive. Training relies on classroom instruction and limited live-fire drills, which are costly, weather-dependent and do not scale to give adequate repetitions.
- **Required.** A software platform that trains personnel to recognise, classify and respond to drone and swarm threats across varied, realistic scenarios: day and night, degraded sensors, urban and rural terrain, single drones and swarms. Usable at unit level with minimal specialised hardware.
- **Expected outcomes.**
  1. A desktop or VR-capable simulator with scripted and procedurally generated scenarios.
  2. Decision-tree scoring on detection time, classification accuracy and engagement decisions.
  3. An after-action review (AAR) dashboard tracking individual and unit performance over repeated sessions.
  4. Adjustable difficulty and scenario randomisation to prevent rote learning.

The gap analysis behind the plan is in [00-gap-check.md](00-gap-check.md) and the background research in [02-research.md](02-research.md).

## 3. The solution

### 3.1 Who trains

| Seat | Does what |
|---|---|
| **Operator** (trainee) | Works the sensor consoles, cues sensors, manages tracks, classifies, assesses, responds and files contact reports. |
| **Detachment commander** (a seat of a trainee account) | Assigns sectors, hands tracks over and holds the commander-authority responses. |
| **Instructor** | Runs cohorts, launches and monitors sessions with ground truth, injects events, authors scenarios and rule packs, reviews unit results. |
| **Administrator** | Users and units, packs, data provenance, signed records, system health, settings, backup. |

### 3.2 A session, end to end

1. The trainee opens **Drills**, picks a scenario in the **Session lobby** and reads the briefing (terrain, time, weather, rule pack and version).
2. On **Begin session** the server builds the world and starts ticking at 20 Hz. The client receives sensor frames only.
3. The workspace shows the EO/IR camera view, the radar PPI, the RF spectrum and acoustic spectrogram consoles, the fused track table with the simulated AI assist, the selected-track strip, the decision panel, the rules verdict and the event log.
4. The trainee cues the EO camera onto a track (`U`), fixes swaps and splits, classifies (`C`), assesses (`A`) and responds (`R`). A blocked response shows the rule text and pack version.
5. At the end the event log is stored as a hash chain and verified on read; the debrief shows the score, the decision path per contact, the first three lessons and the report grade.

![Live workspace, day](report/screenshots/live-workspace-day.png)
*Live workspace during a Harrier Field session: EO camera (day TV), radar PPI with identity symbols, RF spectrum, fused track table with the simulated AI assist, decision panel and rules verdict.*

## 4. Requirement coverage

The full matrix is [06-requirements-traceability.md](06-requirements-traceability.md); test-level proofs are in [TRACEABILITY.md](TRACEABILITY.md). Status here uses three values: **Built** (backend and front end, tested), **Screen** (front end populated from the seeded module, backend in a later wave), **Planned**.

| ID | Requirement | What SUDARSHAN does | Status |
|---|---|---|---|
| R0 | AI-enabled | Simulated AI detection assist with measured hit and false-alarm rates; behaviour models for swarms; constrained procedural generation with an oracle. Adaptive learner model and adversary in wave 11a. | Built (assist, behaviours, generator); learner model Planned |
| R1, R12 | Single drones and swarms | Eleven classes; swarms of 6 to 48 with formation, flocking, leader loss, link loss, decoys and saturation lanes, all kinematics only. | Built |
| R2 | Low cost | Runs on existing laptops and a browser; open-source stack; no licences or consumables. Cost sheet in wave 15a. | Built (design); document Planned |
| R3, R9 | Weather, day and night | Weather (clear, haze, rain, fog, wind) and light drive both the sensor models and the 3D look; day TV, night vision, thermal white-hot and black-hot. | Built |
| R4 | Repetitions at scale | Short drills, unlimited generated variants, 12 clients per server measured with no dropped session. The repetitions-per-hour figure comes from the pilot. | Mechanism built; figure pending pilot |
| R5 | Recognise | Radar, EO/IR, RF and acoustic consoles with a fused track table; detection time scored. | Built |
| R6 | Classify | Nine recognition classes, confusion matrix and d′ with the log-linear correction. | Built |
| R7 | Respond | Fictional effector classes and an editable ROE rule pack; the rule engine blocks forbidden responses and cites the rule and version. | Built |
| R8, R16 | Varied scenarios, scripted and generated | 15 scripted scenarios including a 12-step curriculum; seeded generator with hard constraints, oracle check, diversity filter, MAP-Elites archive and share codes. | Built (wave 9a) |
| R10 | Degraded sensors | Outages, sector outages, haze, glare, rain, wind noise, interference, assist false alarms; scenario-borne degradations. Instructor injects in wave 10b. | Built; live injects Screen |
| R11 | Urban and rural terrain | Two baked packs from SRTM and OSM: Heron Ridge (rural) and Osprey Town (urban, 1,125 buildings), with line-of-sight occlusion. | Built |
| R13 | Unit level, offline | One `docker compose` stack on an instructor laptop serves a classroom over LAN with no internet. Cohorts and unit tools are populated screens. | Stack built; class tools Screen |
| R14 | Minimal hardware | Floor: 8 GB laptop with integrated graphics. Quality tiers with an fps probe; `/bench` harness. | Harness built; floor-laptop run pending |
| R15 | Desktop or VR-capable | Desktop meets the clause. WebXR is an optional depth wave (14b); no VR claim is made. | Desktop Built |
| R17 | Decision-tree scoring | Per-contact Detect → Classify → Assess → Respond tree with rule-pack weights, hard fails and explanations; 37 hand-derived golden cases. | Built |
| R18 | AAR, individual and unit | Debrief per session is built. Replay, decision path, confusion matrix, learning curves, miss-zone heat map, unit dashboard and report builder are populated screens; their backend is wave 12a. | Debrief Built; AAR dashboard Screen |
| R19 | Difficulty and anti-rote | Difficulty vector and randomised seeds in the generator; diversity check against history. Adaptive difficulty in wave 11a. | Generator Built; adaptive Planned |

## 5. System architecture

Principles (from [05-architecture.md](05-architecture.md)): server-authoritative simulation; deterministic by construction; everything versioned; offline first; honest by design.

```mermaid
flowchart LR
  subgraph Client["Browser · React + TypeScript + Vite + Tailwind"]
    UI["App shell · role-based routes · EN/HI"]
    SV["EO/IR view · Three.js<br/>day · NV · thermal · weather"]
    CON["Consoles<br/>radar PPI · RF spectrum · acoustic spectrogram · track table"]
    ACT["Decision panel · rules verdict · contact report"]
    WS["WebSocket client · MessagePack · 20 Hz frames"]
  end

  subgraph API["FastAPI service · Python 3.12"]
    GW["REST + WebSocket gateway<br/>sessions · CSRF · rate limit · roles"]
    LIVE["Live session manager · 20 Hz tick"]
    SCN["Scenario service<br/>library · linter · generator · oracle"]
    SCO["Scoring engine<br/>Detect → Classify → Assess → Respond"]
    subgraph Core["Sim core · seeded, deterministic"]
      WRLD["World · terrain · weather · light"]
      THR["Threats · catalogue · behaviours · groups"]
      SEN["Sensors · radar · EO/IR · RF · acoustic"]
      TRK["Tracker · error policy · ledger · AI assist"]
      ROE["ROE engine · fictional rule pack"]
      LOG["Hash-chained event log"]
    end
  end

  DB[("SQLAlchemy 2 + Alembic<br/>SQLite · Postgres 16")]
  PK[("Packs<br/>terrain · scenarios · rule packs · sensor profiles · threats")]

  UI --> GW
  WS <--> GW
  GW --> LIVE & SCN & SCO
  LIVE --> Core
  SCN --> Core
  LIVE --> DB
  SCO --> DB
  SCN --> DB
  Core --> PK
```

### 5.1 Stack

| Layer | Technology |
|---|---|
| Web | React, TypeScript (strict), Vite, Tailwind with project tokens, Three.js (`WebGLRenderer`), i18n (English and Hindi), IBM Plex Sans and Plex Mono, Noto Sans Devanagari (self-hosted), IBM Carbon icons |
| API | Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic (5 migrations), uv, MessagePack on the socket |
| Simulation | Pure Python with numpy, named seeded RNG streams, deterministic maths library |
| Data | SQLite by default, Postgres 16 in compose and production |
| Delivery | Docker, docker compose (demo, production, CI overrides), nginx, Caddy for HTTPS, GitHub Actions |
| Quality | pytest, hypothesis, ruff, mypy `--strict`, Vitest, ESLint, Prettier, Playwright, @axe-core/playwright, gitleaks |

### 5.2 Repository layout

| Path | Contents |
|---|---|
| `apps/web/` | The web app (about 28,000 lines of TypeScript), unit tests, Playwright specs (real stack and mock) |
| `services/api/app/` | API: auth, users, sessions, live manager, scoring, scenarios, contracts, CLI |
| `services/api/sim/` | Simulation core: world, kinematics, detmath, sensors, tracking, behaviours, catalogue, terrain, ROE, event log, replay |
| `packs/` | Versioned content: 6 sensor profiles, 11 threat classes, 1 rule pack, 15 scenarios, 2 terrain packs, JSON Schemas, `versions.lock.json` |
| `tools/terrain/` | Reproducible terrain bake pipeline (SRTM + OSM to heightmap, buildings, trees, manifest, attribution) |
| `infra/` | Dockerfiles, compose files, nginx, Caddy, deploy, backup and restore scripts, smoke and e2e scripts |
| `brand.json` | The product name, read by the web app, the API, page titles and image labels |

### 5.3 Contracts

Every artefact that crosses a boundary has a versioned Pydantic contract with exported JSON Schema, and the web types are generated from those schemas with a CI drift check: `scenario.v1`, `rulepack.v1`, `sensor-profile.v1`, `threat-class.v1`, `action-record.v1`, `session-record.v1`, `score-result.v1` and the live protocol messages. Pack content is locked by SHA-256 in `packs/versions.lock.json`, so a changed profile without a version bump fails CI, and every session and score records the exact profile and class versions it ran with (ADR-024).

## 6. Deterministic simulation core

Reference: [SIM_CORE.md](SIM_CORE.md), ADR-014 and ADR-016.

- **Fixed 20 Hz tick.** The world advances in fixed steps; pause and resume are not sim actions, so they cannot change a replay.
- **Named RNG streams** (`kinematics`, `sensors`, `tracking` and others), each seeded from the session seed, so adding draws in one subsystem never shifts another. Every sensor candidate takes a fixed budget of 18 uniforms whatever happens to it.
- **Cross-platform determinism.** Hashed state uses only correctly rounded IEEE operations: headings are unit vectors, sine and cosine are polynomials, noise is a sum of uniforms. Golden files written on macOS arm64 pass on Linux x86-64 in CI. Two processes with different hash salts give identical state hashes after 10,000 ticks.
- **Snapshot, restore and replay.** Restore at tick N and run to M equals a straight run. A session record holds inputs and outputs; replay reproduces every event and the final state hash.
- **Hash-chained event log.** Each event carries the hash of the previous one; editing one byte is detected at that event. The log is stored at session end and verified on every read.
- **Cost.** 10,000 ticks of a two-drone scenario run in 0.064 s (6.4 µs per tick). The full breadth scene (57 contacts, six sensors, tracker and assist) costs 6 to 7 ms per tick against a 50 ms budget.

## 7. Sensor models

Reference: [SENSOR_MODELS.md](SENSOR_MODELS.md), ADR-017 and ADR-018.

| Sensor | Model |
|---|---|
| Radar (S-band, generic) | Closed-form P(d) from radar cross-section and range, clutter, multipath and weather; micro-Doppler cue reusing the detect draw; occluded by terrain and buildings. |
| EO/IR (day TV, night vision, thermal) | Johnson-criteria style recognition from apparent size, pixel count and field of view; light model with sunrise, sunset and twilight; haze, rain and glare; cueing narrows the field and improves precision. Thermal is a rendering model, not radiometric. |
| RF (passive) | Band plan (433 MHz to 5.8 GHz), control and video links, hopping; RF-silent classes are never detected. Not occluded by terrain in this build (Q-25). |
| Acoustic (array) | Fundamental and harmonic bands, wind noise and range loss; birds separated from rotors by band. |

Every parameter in a sensor profile carries a register ID from [DATA_REGISTER.md](DATA_REGISTER.md) and a `verified` flag; the loader refuses a parameter without provenance. Class confusion tables are row-normalised and checked to 1e-9. Acceptance tests prove that P(d) never rises with range, that no weather improves on clear air, that night never helps, and that the models are deterministic for a seed (439 cross-model tests).

![Thermal look](report/screenshots/live-workspace-thermal.png)
*EO view in thermal white-hot at 22:00, with automatic gain readout; the RF console shows hopping control links around 2.4 GHz.*

## 8. Tracking, fusion and the simulated AI assist

Reference: [SENSOR_MODELS.md](SENSOR_MODELS.md) "Tracking", ADR-019.

- **Tracker.** Six-state Kalman filter, gated nearest-neighbour association by components, tentative and confirmed lifecycle, coasting through short outages, bearing-only triangulation, an initiation-exclusion zone around live tracks.
- **Errors where real trackers err.** Swaps, splits and merges can occur only when two tracks or two reports share gates, driven by one `tracking` draw per report. Separated targets never err (300 seeds, zero errors). A documented crossing swaps at a fixed tick, and a relabel logged as an action restores the true identity in the ledger.
- **Ground truth stays beside the tracker.** The tracker sees only `Detection.trainee_view()`; a truth ledger links reports to drones by reference for scoring and never flows back. A test plays a whole session over a real socket and scans every frame for drone IDs, truth fields and ledger data.
- **Simulated AI assist.** A seeded assist suggests a class and a threat assessment with configured hit and false-alarm rates. Measured over 40,000 trials: hit 0.9005 against 0.90, false alarm 0.0804 against 0.08, within five standard errors. It is labelled "simulated AI" in the track table and is not a trained model.

## 9. Threat catalogue and behaviours

Reference: [THREAT_CATALOGUE.md](THREAT_CATALOGUE.md), ADR-022 and ADR-023.

**Eleven truth classes:** rotary-small, FPV-small, fixed-wing small, medium and large, autonomous-small, decoy-small, civil drone, bird, kite, balloon. The operator chooses among **nine recognition classes**. Every envelope and signature value is project-authored (register F01, `verified: false`) and generic; no real system is named.

**Behaviours** (`sim/behaviours/`): routes with loiter, loop or despawn; tethered flight; formation following with link range; flocking; leader loss with hold or election; link loss; saturation as parallel lanes along an authored route; out-and-back probes. A member's inputs are only its group's authored route and its group-mates' positions; nothing reads an asset, zone, sensor or operator. There is no pursuit, aiming, closing-rate or terminal-phase logic, and `tests/test_behaviours_rule2.py` reads the source and fails on forbidden words, imports or arguments that could supply a destination.

**Breadth scene:** a 24-drone swarm, a 30-bird flock, two kites and a balloon with six sensors, run on both terrain packs, recorded for the `/bench` harness.

## 10. Scenario engine

Reference: [SCENARIO_ENGINE.md](SCENARIO_ENGINE.md), ADR-008 and ADR-025. Built on `main` (commits `c0b19ec` to `20d7f27`).

- **Scenario language.** A YAML form of `scenario.v1` with line-accurate validation and a linter with coded findings.
- **Generator.** A request (difficulty vector, terrain, time, weather, threat mix, seed) is sampled under hard constraints: rule-pack consistency, sensor coverage, timing windows above minimum reaction time, a minimum stand-off from the defended place.
- **Oracle defender.** A perfect-policy agent on the same sim core reads ground truth, classifies, reports and engages each hostile contact as soon as the rules permit, and repairs track errors. A scenario is "solved" when every hostile contact is presented and answered, no failure finding is raised, and each contact scores at least the request's minimum (default 80%). Each check is stored. The wording is always "verified solvable by test run"; a test fails on "provably" or "guaranteed".
- **Diversity.** A feature vector per scenario, a distance filter against history and a MAP-Elites archive.
- **Share codes.** A checksummed code regenerates a scenario exactly from its request and generator version.
- **Library.** 15 scripted scenarios, among them a 12-step curriculum from "First contact" to a night swarm capstone, each linted, playable and solved by the oracle in CI.

![Scenario library](report/screenshots/instructor-content-scenarios.png)
*Scenario library (instructor), backed by the scenario API.*

![Generator studio](report/screenshots/instructor-content-generator.png)
*Generator studio: request, constraints, oracle result and diversity map.*

## 11. Scoring and debrief

Reference: [SCORING.md](SCORING.md).

- **Decision tree per contact.** Detect (weight 0.25), Classify (0.25), Assess (0.15), Respond (0.20), Report (0.15), with timing standards and partial credit from the rule pack. A rules breach scores 0 and earns nothing in Respond; a blocked attempt is not a breach but costs marks once.
- **Signal detection measures.** Hit rate, false-alarm rate, d′ and criterion c, with the log-linear correction when a rate is 0 or 1.
- **Contact report grading.** Class, position within tolerance, count, heading and timeliness, each with its own mark.
- **Explainable.** 71 reason keys with English and Hindi templates; the first three lessons rank the largest losses.
- **Verified.** 37 golden cases derived by hand with exact fractions; a hypothesis property proves a rushed breach never beats a slower compliant response; an unfixed seeded track swap lowers the affected contact's score and fixing it does not.

![Debrief](report/screenshots/debrief.png)
*Debrief: session, decision and report scores, d′ and criterion, the first three lessons, the record (scenario version, rule pack, seed) and the per-node decision path. Ground truth is shown only after the session has ended.*

## 12. Terrain and the 3D scene

Reference: [TERRAIN_PACKS.md](TERRAIN_PACKS.md), [04-engine.md](04-engine.md), ADR-021.

- **Bake pipeline** (`tools/terrain`): SRTM relief and an OSM extract baked to a heightmap mesh, building glTF, trees and a manifest with attribution. Two bakes are byte-identical. Raw downloads stay outside git.
- **Packs.** Heron Ridge (rural, 1.9 MB, 41 buildings, 704 trees, 141 m relief) and Osprey Town (urban, 2.6 MB, 1,125 buildings). Site names are fictional; no pack file or screen names a place.
- **Line of sight.** Radar and EO/IR detections are blocked by terrain and buildings after the probability draw, so RNG streams are unchanged. In the Heron Ridge scenario the village delays the hostile track from 31 s to 58 s.
- **3D look.** Terrain, buildings, trees with wind sway, sun, moon and stars, ACES tone mapping, height fog, rain, night vision and thermal passes, instanced meshes for every class, a reticle with bearing, elevation, field-of-view and zoom readouts, and quality tiers chosen by an fps probe.

| Night vision | Rain at dusk |
|---|---|
| ![Night vision](report/screenshots/live-workspace-nv.png) | ![Rain](report/screenshots/live-workspace-rain.png) |

## 13. The application, seat by seat

Design system ([07-ui-map.md](07-ui-map.md), [DESIGN.md](DESIGN.md)): graphite palette tokens with one interactive accent, IBM Plex Sans and Plex Mono with tabular numerals, Noto Sans Devanagari, a 4 px grid, IBM Carbon icons only. Dark operations theme first, with a tested light theme. Every screen has populated, empty, loading and error states, keyboard operation and is axe-clean. Colour is never the only cue: identity symbols differ in shape, and states carry text.

### 13.1 Sign-in and shell

| Sign in | Status (light theme) |
|---|---|
| ![Sign in](report/screenshots/sign-in.png) | ![Status light](report/screenshots/status-light.png) |

The sign-in page offers a seat switcher in demo mode only; production mode refuses demo accounts at start-up and at sign-in.

### 13.2 Trainee

| Today | Drills · Session lobby |
|---|---|
| ![Today](report/screenshots/trainee-trainee-today-t0.png) | ![Lobby](report/screenshots/trainee-trainee-drills-t2.png) |
| **Recognition library · Threat catalogue** | **My performance · Progress** |
| ![Threat catalogue](report/screenshots/trainee-trainee-recognition-library-t0.png) | ![Progress](report/screenshots/trainee-trainee-my-performance-t1.png) |

### 13.3 Detachment commander

| Sector assignment | Track handover |
|---|---|
| ![Sector assignment](report/screenshots/commander-commander-command-t0.png) | ![Track handover](report/screenshots/commander-commander-command-t1.png) |

### 13.4 Instructor

| Live monitor (ground truth, inject, annotate) | Unit AAR · Unit dashboard |
|---|---|
| ![Live monitor](report/screenshots/instructor-instructor-live-sessions-t1.png) | ![Unit dashboard](report/screenshots/instructor-instructor-unit-aar-t0.png) |
| **Rule-pack editor** | **Report builder** |
| ![Rule-pack editor](report/screenshots/instructor-instructor-rule-packs-t1.png) | ![Report builder](report/screenshots/instructor-instructor-reports-t0.png) |

### 13.5 Administrator

| Data register · Parameter provenance | Records · Audit log |
|---|---|
| ![Provenance](report/screenshots/admin-admin-data-register-t1.png) | ![Audit log](report/screenshots/admin-admin-records-t0.png) |
| **Health · Services** | **Backup and restore** |
| ![Health](report/screenshots/admin-admin-health-t0.png) | ![Backup](report/screenshots/admin-admin-backup-t0.png) |

### 13.6 Bilingual

![Hindi workspace](report/screenshots/live-workspace-hindi.png)
*The live workspace in Hindi. 1,733 strings are translated; all Hindi is a draft awaiting a native reviewer (Q-15).*

### 13.7 What is real and what is seeded

| Backed by the real API | Populated from the seeded module (`apps/web/src/mock/`) until its wave lands |
|---|---|
| Sign-in, sessions, preferences, Status, Session lobby, live workspace, debrief, Scenario library, Scenario editor, Generator studio, terrain packs | Today, Curriculum, Recognition library, My performance (11a, 11b, 12a); Cohorts, Trainees, Live sessions, Rule packs, Curricula (10a, 10b); Team exercise and Command (13a); Unit AAR and Reports (12a, 12b); Users, Organisation, Packs, Data register, Health, Settings, Backup (13c); Records (13b) |

The seeded module holds 12 trainees with 4 sessions each, 20 scenarios and a 48-entry audit chain that verifies in the browser. **These tables, curves and rankings are illustrative and must not be presented as measured results** (ADR-026).

## 14. Security and deployment

Reference: [DEPLOY.md](DEPLOY.md), [HOSTING_OPTIONS.md](HOSTING_OPTIONS.md), [../SECURITY.md](../SECURITY.md).

**Security controls**

- Server-side sessions storing only the SHA-256 of the cookie token; `HttpOnly`, `SameSite=Lax`, `Secure` in production.
- CSRF token on every unsafe request; failed-login limit (5 per 15 minutes per address and per account).
- Role guards on every route; a trainee cannot open another account's session.
- WebSocket origin check (cross-site and `null` origins refused), 64 KB message cap.
- Strict Content Security Policy from nginx; HSTS and HTTP-to-HTTPS redirect through Caddy.
- Production refuses to start with a missing or default `SECRET_KEY` and refuses demo accounts. The first admin comes from `FIRST_ADMIN_*` environment variables or the `create-admin` CLI, which never accepts a password as an argument.
- gitleaks in CI; only `.env.example` with placeholders is committed.

**Deployment**

- Host: Azure for Students Linux VM (Ubuntu 24.04 LTS, Central India), Docker and compose, persistent volumes.
- `infra/deploy.sh` (up, update, rollback), `backup.sh`, `restore.sh`; `make backup-test` proves a restore.
- `make prod-check` brings up the production stack in a throwaway compose project with HTTPS through Caddy and checks page load, admin bootstrap, cookie flags, CSRF, terrain pack serving and access, CSP, the sim inside the API image (`sim-check`), memory, and `make smoke` (`/healthz`, `/readyz`, `/api/v1/version`).
- Memory measured locally: four production containers at 285 MiB after `sim-check`.
- The same stack runs on an instructor laptop for a classroom over LAN with no internet.

## 15. Quality engineering

| Suite | Count (last full run) |
|---|---|
| API and simulation (pytest, hypothesis) | 3,705 passed at the wave 8 acceptance, coverage 99.24%, every `sim/` module 100%; the wave 9a scenario tests were added after that count |
| Terrain tools | 69 |
| Web unit and component (Vitest) | 621 |
| Real-stack end-to-end (Playwright against nginx, API, Postgres) | 51 |
| Mock end-to-end (Playwright against the dev server) | 148, including every seat × every sidebar item × every tab with axe and zero console errors |
| Visual snapshots | 4 tests |

Codebase: about 17,500 lines of Python in the API and simulation, 23,000 lines of Python tests, 28,000 lines of TypeScript in the web app and 12,000 lines of web tests.

**CI** (GitHub Actions, six jobs: api, web, e2e, docker, terrain, secrets) is green on `main` for the wave 8 build (run 39207730379). A red period in waves 5 to 7 was traced to test pacing over an in-process WebSocket, reproduced on x86-64 Linux, and fixed with flow control without loosening any test (BUILD_LOG, CI status).

**Other gates:** mypy `--strict` and TypeScript strict; ruff, ESLint and Prettier; JS bundle budget (356 KB initial, 414 KB total gzipped, limit 1.5 MB); contract drift check; Hindi key parity; a wording test that fails on development-phase phrases in visible strings; a source test for locked rule 2 in the behaviours and scenario code.

## 16. Performance

Measured only; details in [PERFORMANCE.md](PERFORMANCE.md).

| Measure | Result | Conditions |
|---|---|---|
| 12 clients × 300 s live load | 0 sessions dropped, 20.0 Hz, 0 tick gaps (71,988 frames) | Build laptop, loopback, one API process |
| Message round trip | p50 3.1 ms, p95 14.3 ms, p99 19.3 ms | as above |
| Server tick cost | p50 0.7 ms, p99 2.6 ms; 25% of one core, 90 MB | as above |
| Breadth scene sim cost | 6 to 7 ms per tick (57 contacts, six sensors) | Build laptop |
| Line-of-sight query | 0.04 to 0.08 ms per segment | Shipped packs |
| 3D benchmark gate (≥ 45 fps median, ≥ 30 fps p5 at 1080p) | **Not yet run on the floor laptop.** No figure is claimed. | `/bench` harness ready (Q-04) |

## 17. Data policy, honesty and safety

- **Calibrated from, never trained on.** Datasets supply numeric parameters, cited by register ID. Raw samples ship only under a confirmed open licence; none ship today. Raw downloads stay outside git.
- **Provenance in the data.** Every sensor and threat parameter cites a row of [DATA_REGISTER.md](DATA_REGISTER.md). Project-authored values use F01 and are `verified: false`. The administrator's Data register screens show sources and per-parameter provenance.
- **Defensive only.** Threat behaviour is kinematics only. No guidance, targeting or terminal-attack logic; effectors are generic fictional classes with fictional numbers; terrain is generic; site and unit names are fictional. Enforced by source-reading tests.
- **Measured claims only.** No effectiveness claim is made. Scenarios are "verified solvable by test run". The ~85% success target is a heuristic. Thermal is a rendering model; weather is modelled.
- **Labelling.** A footer line on every page and the About page state the basis: "Built on published specifications and open research." The per-screen labels were removed for the demo build by the owner's decision (ADR-026); this report restates the full honesty wording at the top.

## 18. Build progress

The plan has 25 waves ([09-build-waves.md](09-build-waves.md), [waves/](waves/)). The submission-ready cut is 22 of them.

| Wave | Name | State on `main` |
|---|---|---|
| 1 | Repo bootstrap | Done |
| 2 | Design system and app shell | Built; deployed as the first live link |
| 3 | Contracts and deterministic sim core | Built, CI green |
| 4a | Sensor models | Built, CI green |
| 4b | Tracking, fusion and AI assist | Built, CI green |
| 5 | Live-session vertical slice | Built, CI green; redeploy pending |
| 6 | Scoring and debrief | Built, CI green; redeploy pending |
| 7 | 3D realism and terrain packs | Built, CI green; floor-laptop gate pending |
| 8 | Threat breadth | Built, CI green; floor-laptop gate pending |
| 9a | Scenario engine | Built on `main`; build-log entry and acceptance record to write |
| — | Demo-complete front end | Done: every seat and sidebar item populated (ADR-026) |
| 9b to 15b | Site builder, sensor placement, class management, director mode, adaptive learning, recognition academy, full AAR, counterfactual AAR, team mode, signed records, admin, hardening, WebXR, submission docs, release | Not started (screens exist for many; backends do not) |

Key design decisions are recorded as ADR-001 to ADR-026 in [DECISIONS.md](DECISIONS.md).

## 19. Limitations and open items

| Item | Status |
|---|---|
| Floor-laptop benchmark (Q-04) | Harness built; owner to run `/bench` on the 8 GB integrated-graphics laptop and record the JSON. |
| Live link | Runs the wave 2 build. Waves 3 to 9a and the demo front end are ready to deploy; post-deploy checks are listed in BUILD_LOG. |
| Pilot (12 volunteers × 4 sessions) | Not run; logistics and consent open (Q-13). No effectiveness figure exists. |
| Hindi review (Q-15) | All 1,733 Hindi strings are unreviewed drafts. |
| Parameter sources (Q-09, Q-11, Q-20, Q-22) | Many figures are project-authored (F01, `verified: false`); register rows for published RCS, micro-Doppler and RF tables are still to add. |
| RF occlusion (Q-25) | RF is not shadowed by terrain. |
| Terrain content (Q-26, Q-27) | Thin OSM building heights use defaults; pack source coordinates live in `tools/terrain/areas.json`. |
| Seeded screens | Instructor, AAR, team and admin screens read the seeded module until waves 10a to 13c land. |
| Licence (Q-01), trade-mark search (Q-07), name association (Q-08) | Owner decisions open. |
| Labelling rule | The honesty rule in CONTRIBUTING.md still describes per-screen labels; the owner decides whether to reconcile it with ADR-026. |

## 20. Next steps

1. Run `/bench` on the floor laptop and record the result (closes the waves 7 and 8 gate).
2. Redeploy `main` to the live link and run `make smoke` and `make check-deploy` against it.
3. Record the wave 9a entry and acceptance map in BUILD_LOG.
4. Waves 9b and 9c: site builder and sensor placement trainer (demo feature H2).
5. Waves 10a, 10b: class management and director mode, replacing the seeded instructor screens.
6. Waves 11a, 11b, 12a: adaptive learning and adversary, recognition academy, full AAR; then start the pilot.
7. Waves 12b, 13b, 13c, 14a, 15a: counterfactual AAR, signed records and competency matrix, admin, hardening, submission documents and the final pilot figures.

---

## Appendix A · Screenshot gallery

All screenshots were captured on 2026-10-20 at 1920 × 1080 from the web app on the Vite dev server with the scripted session and the seeded module (headless Chromium, software rendering, so the 3D scene uses the Low tier). Files are in [report/screenshots/](report/screenshots/); `index.json` lists each file with its seat and route.


### Public

**Sign in with seat switcher**

![Sign in with seat switcher](report/screenshots/sign-in.png)


### Trainee

**Status**

![Status](report/screenshots/trainee-status.png)

**Today · Today overview**

![Today · Today overview](report/screenshots/trainee-trainee-today-t0.png)

**Drills · Curriculum**

![Drills · Curriculum](report/screenshots/trainee-trainee-drills-t0.png)

**Drills · Quick drill**

![Drills · Quick drill](report/screenshots/trainee-trainee-drills-t1.png)

**Drills · Session lobby**

![Drills · Session lobby](report/screenshots/trainee-trainee-drills-t2.png)

**Recognition library · Threat catalogue**

![Recognition library · Threat catalogue](report/screenshots/trainee-trainee-recognition-library-t0.png)

**Recognition library · Clutter catalogue**

![Recognition library · Clutter catalogue](report/screenshots/trainee-trainee-recognition-library-t1.png)

**Recognition library · Signature drills**

![Recognition library · Signature drills](report/screenshots/trainee-trainee-recognition-library-t2.png)

**My performance · Sessions**

![My performance · Sessions](report/screenshots/trainee-trainee-my-performance-t0.png)

**My performance · Progress**

![My performance · Progress](report/screenshots/trainee-trainee-my-performance-t1.png)

**My performance · Reports**

![My performance · Reports](report/screenshots/trainee-trainee-my-performance-t2.png)

**Profile and preferences · Language and theme**

![Profile and preferences · Language and theme](report/screenshots/trainee-account-profile-t0.png)

**Profile and preferences · Accessibility**

![Profile and preferences · Accessibility](report/screenshots/trainee-account-profile-t1.png)

**Help and SOPs · Keyboard shortcuts**

![Help and SOPs · Keyboard shortcuts](report/screenshots/trainee-account-help-t0.png)

**Help and SOPs · Standard procedures**

![Help and SOPs · Standard procedures](report/screenshots/trainee-account-help-t1.png)

**Help and SOPs · About**

![Help and SOPs · About](report/screenshots/trainee-account-help-t2.png)

**Live workspace · day EO**

![Live workspace · day EO](report/screenshots/live-workspace-day.png)

**Live workspace · night vision**

![Live workspace · night vision](report/screenshots/live-workspace-nv.png)

**Live workspace · thermal**

![Live workspace · thermal](report/screenshots/live-workspace-thermal.png)

**Live workspace · rain at dusk**

![Live workspace · rain at dusk](report/screenshots/live-workspace-rain.png)

**Session debrief**

![Session debrief](report/screenshots/debrief.png)

**Live workspace · Hindi**

![Live workspace · Hindi](report/screenshots/live-workspace-hindi.png)

**Status · light theme**

![Status · light theme](report/screenshots/status-light.png)


### Detachment commander

**Team command · Sector assignment**

![Team command · Sector assignment](report/screenshots/commander-commander-command-t0.png)

**Team command · Track handover**

![Team command · Track handover](report/screenshots/commander-commander-command-t1.png)

**Team command · Team score**

![Team command · Team score](report/screenshots/commander-commander-command-t2.png)


### Instructor

**Cohorts · Cohort list**

![Cohorts · Cohort list](report/screenshots/instructor-instructor-cohorts-t0.png)

**Cohorts · Cohort detail**

![Cohorts · Cohort detail](report/screenshots/instructor-instructor-cohorts-t1.png)

**Trainees · Trainee list**

![Trainees · Trainee list](report/screenshots/instructor-instructor-trainees-t0.png)

**Trainees · Trainee profile**

![Trainees · Trainee profile](report/screenshots/instructor-instructor-trainees-t1.png)

**Live sessions · Launch session**

![Live sessions · Launch session](report/screenshots/instructor-instructor-live-sessions-t0.png)

**Live sessions · Live monitor**

![Live sessions · Live monitor](report/screenshots/instructor-instructor-live-sessions-t1.png)

**Live sessions · Compare sessions**

![Live sessions · Compare sessions](report/screenshots/instructor-instructor-live-sessions-t2.png)

**Team exercise · Team setup**

![Team exercise · Team setup](report/screenshots/instructor-instructor-team-exercise-t0.png)

**Team exercise · Team monitor**

![Team exercise · Team monitor](report/screenshots/instructor-instructor-team-exercise-t1.png)

**Scenario library**

![Scenario library](report/screenshots/instructor-content-scenarios.png)

**Generator studio**

![Generator studio](report/screenshots/instructor-content-generator.png)

**Rule packs · Rule-pack list**

![Rule packs · Rule-pack list](report/screenshots/instructor-instructor-rule-packs-t0.png)

**Rule packs · Rule-pack editor**

![Rule packs · Rule-pack editor](report/screenshots/instructor-instructor-rule-packs-t1.png)

**Curricula · Curriculum list**

![Curricula · Curriculum list](report/screenshots/instructor-instructor-curricula-t0.png)

**Curricula · Curriculum editor**

![Curricula · Curriculum editor](report/screenshots/instructor-instructor-curricula-t1.png)

**Unit AAR · Unit dashboard**

![Unit AAR · Unit dashboard](report/screenshots/instructor-instructor-unit-aar-t0.png)

**Unit AAR · Compare trainees**

![Unit AAR · Compare trainees](report/screenshots/instructor-instructor-unit-aar-t1.png)

**Unit AAR · Annotated replay**

![Unit AAR · Annotated replay](report/screenshots/instructor-instructor-unit-aar-t2.png)

**Reports · Report builder**

![Reports · Report builder](report/screenshots/instructor-instructor-reports-t0.png)


### Administrator

**Users and roles · User list**

![Users and roles · User list](report/screenshots/admin-admin-users-and-roles-t0.png)

**Users and roles · User detail**

![Users and roles · User detail](report/screenshots/admin-admin-users-and-roles-t1.png)

**Organisation · Units**

![Organisation · Units](report/screenshots/admin-admin-organisation-t0.png)

**Packs · Pack manager**

![Packs · Pack manager](report/screenshots/admin-admin-packs-t0.png)

**Data register · Sources**

![Data register · Sources](report/screenshots/admin-admin-data-register-t0.png)

**Data register · Parameter provenance**

![Data register · Parameter provenance](report/screenshots/admin-admin-data-register-t1.png)

**Records · Audit log**

![Records · Audit log](report/screenshots/admin-admin-records-t0.png)

**Records · Record verification**

![Records · Record verification](report/screenshots/admin-admin-records-t1.png)

**Health · Services**

![Health · Services](report/screenshots/admin-admin-health-t0.png)

**Health · Performance**

![Health · Performance](report/screenshots/admin-admin-health-t1.png)

**Health · Storage**

![Health · Storage](report/screenshots/admin-admin-health-t2.png)

**Settings · Instance settings**

![Settings · Instance settings](report/screenshots/admin-admin-settings-t0.png)

**Backup · Backup and restore**

![Backup · Backup and restore](report/screenshots/admin-admin-backup-t0.png)


## Appendix B · Document index

| Document | Purpose |
|---|---|
| [PS-26247.md](PS-26247.md) | Problem statement text |
| [00-gap-check.md](00-gap-check.md) to [10-differentiators.md](10-differentiators.md) | Planning and research (gap check, naming, research, data register plan, engine, architecture, requirements, UI map, demo, build waves, differentiators) |
| [BUILD_LOG.md](BUILD_LOG.md) | Resumable build state, wave entries, CI status |
| [DECISIONS.md](DECISIONS.md) | ADR-001 to ADR-026 |
| [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md) | Open and closed questions |
| [TRACEABILITY.md](TRACEABILITY.md) | Requirement-to-test proofs |
| [SIM_CORE.md](SIM_CORE.md), [SENSOR_MODELS.md](SENSOR_MODELS.md), [THREAT_CATALOGUE.md](THREAT_CATALOGUE.md), [SCENARIO_ENGINE.md](SCENARIO_ENGINE.md), [SCORING.md](SCORING.md), [TERRAIN_PACKS.md](TERRAIN_PACKS.md), [LIVE_SESSION.md](LIVE_SESSION.md) | Technical references |
| [DATA_REGISTER.md](DATA_REGISTER.md) | Every cited source with licence and use |
| [DESIGN.md](DESIGN.md), [FONTS.md](FONTS.md) | Design system |
| [DEPLOY.md](DEPLOY.md), [HOSTING_OPTIONS.md](HOSTING_OPTIONS.md), [RELEASE.md](RELEASE.md) | Deployment and release |
| [PERFORMANCE.md](PERFORMANCE.md) | Measured performance |
| [PPT_ARCHITECTURE.md](PPT_ARCHITECTURE.md) | Architecture slide source |
