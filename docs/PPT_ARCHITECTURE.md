# One-page architecture slide

Source material for a single system-architecture slide of the final platform. It carries no status marks. Everything here is drawn from [05-architecture.md](05-architecture.md), [SIM_CORE.md](SIM_CORE.md), [SENSOR_MODELS.md](SENSOR_MODELS.md), [SCENARIO_ENGINE.md](SCENARIO_ENGINE.md), [SCORING.md](SCORING.md) and the files in [waves/](waves/). The platform is built from open research datasets and published specifications, in fictional scenarios.

## 1. Boxes by layer

Labels are at most 6 words. The ID is used by the arrow table in section 2.

### Users

| ID | Name | Tech | Label |
|---|---|---|---|
| U1 | Trainee Operator | Web browser | Recognises, classifies, responds to tracks |
| U2 | Detachment Commander | Web browser | Assigns sectors, accepts track handovers |
| U3 | Instructor | Web browser | Runs classes, injects events, reviews |
| U4 | Admin | Web browser | Manages users, packs, rule sets |

### Web client

| ID | Name | Tech | Label |
|---|---|---|---|
| W1 | React Console | React, TypeScript, MapLibre GL | Radar, RF, acoustic, track table |
| W2 | 3D Scene | Three.js | EO/IR views, weather, terrain |
| W3 | AAR Dashboard | React, TypeScript | Replay, decision path, exports |
| W4 | Instructor Console | React, TypeScript | Live monitor, director mode, admin |

### API

| ID | Name | Tech | Label |
|---|---|---|---|
| G1 | API Gateway | FastAPI, REST, WebSocket | Auth, roles, rate limits, audit |

### Simulation core

| ID | Name | Tech | Label |
|---|---|---|---|
| S1 | Simulation Core | Python 3.12, numpy, seeded RNG | Deterministic 20 Hz session ticks |
| S2 | Tracker and Fusion | Python, Kalman filter | Fuses reports into confirmed tracks |
| S3 | AI Detection Assist | Python | Modelled alerts with stated error rates |
| S4 | ROE Validator | Python, YAML rule pack | Checks actions against fictional rules |

### Sensor models

| ID | Name | Tech | Label |
|---|---|---|---|
| M1 | Radar Model | Python, numpy | Range, clutter, Doppler, terrain occlusion |
| M2 | EO/IR Model | Python, numpy | Contrast, range, thermal look |
| M3 | RF Model | Python, numpy | Bands, hop patterns, link loss |
| M4 | Acoustic Model | Python, numpy | Spectra, range, wind noise |

### Threat and clutter models

| ID | Name | Tech | Label |
|---|---|---|---|
| T1 | Threat Library | YAML packs, Python | Drone classes, envelopes, signatures |
| T2 | Behaviour Models | Python, numpy | Swarm, decoy, evasive route kinematics |
| T3 | Civil Clutter | YAML packs, Python | Birds, kites, balloons, civil drones |

### Scenario engine

| ID | Name | Tech | Label |
|---|---|---|---|
| E1 | Scenario Library | JSON, scenario schema | Scripted fictional scenarios |
| E2 | Seeded Generator | Python, seeded RNG | Difficulty-driven scenario sampling |
| E3 | Solvability and Diversity Check | Python, oracle-defender run | Verified solvable, varied scenarios |

### Scoring and learning

| ID | Name | Tech | Label |
|---|---|---|---|
| L1 | Decision-Tree Scorer | Python | Detect, Classify, Assess, Respond |
| L2 | Adaptive Proficiency Model | Python | Per-skill proficiency, next scenario |

### Records and audit

| ID | Name | Tech | Label |
|---|---|---|---|
| R1 | Hash-Chained Event Log | SHA-256 chain | Append-only, tamper-evident session record |
| R2 | Record Signer | Ed25519 | Signs chain head, verifies records |
| R3 | Audit Log | SQLAlchemy | Logs sign-ins and administrative actions |

### Data stores

| ID | Name | Tech | Label |
|---|---|---|---|
| D1 | Relational Database | SQLAlchemy, SQLite or Postgres 16 | Users, sessions, scores, records |
| D2 | Rule and Sensor Packs | YAML, JSON Schema | Versioned parameters with source IDs |

### Terrain packs

| ID | Name | Tech | Label |
|---|---|---|---|
| P1 | Terrain Packs | Baked SRTM and OSM data | Fictional rural and urban sites |

### Team mode

| ID | Name | Tech | Label |
|---|---|---|---|
| Q1 | Team Session Manager | Python, WebSocket | Sector split, scored track handover |

### Deployment

| ID | Name | Tech | Label |
|---|---|---|---|
| X1 | Docker Compose Stack | Docker, Caddy, nginx, uvicorn, Postgres 16 | One-laptop or single-host install |

## 2. Arrows

Label at most 3 words. "Web client" means W1 to W4 drawn as one group, and so on for the other layers, so the slide has a single arrow per layer pair and no crossings between boxes inside a layer.

| # | From | To | Label | Direction |
|---|---|---|---|---|
| 1 | Users (U1 to U4) | Web client (W1 to W4) | Browser over LAN | one way |
| 2 | Web client (W1 to W4) | G1 API Gateway | REST, WebSocket | both ways |
| 3 | G1 API Gateway | S1 Simulation Core | Session commands | one way |
| 4 | G1 API Gateway | Q1 Team Session Manager | Role actions | one way |
| 5 | Q1 Team Session Manager | S1 Simulation Core | Sectors, handovers | both ways |
| 6 | E1, E2 (via E3) | S1 Simulation Core | Verified scenario spec | one way |
| 7 | L2 Adaptive Proficiency Model | E2 Seeded Generator | Next difficulty | one way |
| 8 | Threat and clutter models (T1 to T3) | S1 Simulation Core | Entities, behaviours | one way |
| 9 | S1 Simulation Core | Sensor models (M1 to M4) | Entity states | one way |
| 10 | Sensor models (M1 to M4) | S2 Tracker and Fusion | Sensor reports | one way |
| 11 | S4 ROE Validator | S1 Simulation Core | Action verdicts | one way |
| 12 | P1 Terrain Packs, D2 Rule and Sensor Packs | S1 Simulation Core | Versioned parameters | one way |
| 13 | S1 Simulation Core | R1 Hash-Chained Event Log | Append events | one way |
| 14 | R1 Hash-Chained Event Log | R2 Record Signer | Chain head | one way |
| 15 | R1 Hash-Chained Event Log | L1 Decision-Tree Scorer | Logged actions | one way |
| 16 | L1 Decision-Tree Scorer | L2 Adaptive Proficiency Model | Skill observations | one way |
| 17 | L1, R1, R2, R3 | D1 Relational Database | Persist results | one way |
| 18 | D1 Relational Database | G1 API Gateway | Replays, reports | one way |
| 19 | X1 Docker Compose Stack | G1 API Gateway and D1 | Hosts services | one way |

S2 and S3 sit inside the Simulation Core group, so S2 feeds S3 and the track picture with no arrow between layers.

## 3. Bottom banner

Offline, LAN-served, on-premises, deterministic and replayable

## 4. Data flow of one training session

1. The Adaptive Proficiency Model (or the instructor) sets a difficulty and a seed; the Seeded Generator samples a scenario spec, or the Scenario Library supplies a scripted one.
2. The Solvability and Diversity Check runs an oracle defender through the spec and compares it with the trainee's history; the spec is stored with its seed and hash.
3. The instructor starts the session; the API Gateway loads the spec, terrain pack, rule pack and sensor profiles into the Simulation Core.
4. Every 50 ms tick, Behaviour Models move threats and clutter, the sensor models produce reports, and Tracker and Fusion with AI Detection Assist build the track picture.
5. Sensor frames, with no ground truth, stream over WebSocket to the React Console and 3D Scene; the Instructor Console receives the full picture.
6. Operator and commander actions pass through the API Gateway, the ROE Validator and the Team Session Manager, and each is appended to the Hash-Chained Event Log.
7. At session end the Record Signer signs the chain head, the Decision-Tree Scorer walks Detect, Classify, Assess and Respond for every threat, and the skill observations update the Adaptive Proficiency Model.
8. The AAR Dashboard replays the verified log against ground truth, with scores, reasons, exports and the next recommended scenario.

## 5. Image-generation prompt

```text
Create a clean, flat enterprise system-architecture diagram, portrait page (3:4), white background, a single blue palette (navy #0B2A4A, mid blue #1F5FA8, light blue tint #E6F0FA) plus dark grey text. No gradients, no shadows, no glow, no 3D, no emoji, no clip-art, no photographs. Large readable sans-serif text (IBM Plex Sans style), at least 20 pt equivalent for box names.

TITLE BAR: a full-width navy bar at the top with white text: "SUDARSHAN: Counter-UAS Threat Recognition Trainer · System Architecture".

BODY: stack the layers top to bottom as horizontal bands with a small blue label at the left edge of each band. Inside each band, draw rounded rectangles with a simple 1.5 px blue line icon at the top left, the bold box name, and the one-line label beneath it in grey. Use only these boxes, exactly as named:

Band "Users" (4 boxes): "Trainee Operator" / Recognises, classifies, responds to tracks. "Detachment Commander" / Assigns sectors, accepts track handovers. "Instructor" / Runs classes, injects events, reviews. "Admin" / Manages users, packs, rule sets.

Band "Web client" (4 boxes): "React Console" / Radar, RF, acoustic, track table. "3D Scene" / EO/IR views, weather, terrain. "AAR Dashboard" / Replay, decision path, exports. "Instructor Console" / Live monitor, director mode, admin.

Band "API" (1 wide box): "API Gateway" / Auth, roles, rate limits, audit. Under the name write "FastAPI · REST · WebSocket".

Band "Server core" containing three groups side by side:
 - Group "Simulation core" (4 boxes): "Simulation Core" / Deterministic 20 Hz session ticks. "Tracker and Fusion" / Fuses reports into confirmed tracks. "AI Detection Assist" / Modelled alerts with stated error rates. "ROE Validator" / Checks actions against fictional rules. Also "Team Session Manager" / Sector split, scored track handover.
 - Group "Sensor models" (4 boxes): "Radar Model", "EO/IR Model", "RF Model", "Acoustic Model".
 - Group "Threat and clutter models" (3 boxes): "Threat Library" / Drone classes, envelopes, signatures. "Behaviour Models" / Swarm, decoy, evasive route kinematics. "Civil Clutter" / Birds, kites, balloons, civil drones.

Band "Scenario, scoring and learning" containing three groups:
 - Group "Scenario engine" (3 boxes): "Scenario Library" / Scripted fictional scenarios. "Seeded Generator" / Difficulty-driven scenario sampling. "Solvability and Diversity Check" / Verified solvable, varied scenarios.
 - Group "Scoring and learning" (2 boxes): "Decision-Tree Scorer" / Detect, Classify, Assess, Respond. "Adaptive Proficiency Model" / Per-skill proficiency, next scenario.
 - Group "Records and audit" (3 boxes): "Hash-Chained Event Log" / Append-only, tamper-evident session record. "Record Signer" / Signs chain head, verifies records. "Audit Log" / Logs sign-ins and administrative actions.

Band "Data" (3 boxes, cylinder-style icons): "Relational Database" / Users, sessions, scores, records (SQLite or Postgres 16). "Rule and Sensor Packs" / Versioned parameters with source IDs. "Terrain Packs" / Fictional rural and urban sites.

Band "Deployment" (1 wide box): "Docker Compose Stack" / One-laptop or single-host install (Docker, Caddy, nginx, uvicorn, Postgres 16).

ARROWS: thin dark-blue orthogonal arrows with small arrowheads and short labels (max 3 words) on a white label background; draw group-to-group arrows, not one per box, and avoid crossings. Draw exactly these:
1. Users to Web client, "Browser over LAN", one way.
2. Web client to API Gateway, "REST, WebSocket", two-way.
3. API Gateway to Simulation Core, "Session commands".
4. API Gateway to Team Session Manager, "Role actions".
5. Team Session Manager and Simulation Core, "Sectors, handovers", two-way.
6. Scenario engine to Simulation Core, "Verified scenario spec".
7. Adaptive Proficiency Model to Seeded Generator, "Next difficulty".
8. Threat and clutter models to Simulation Core, "Entities, behaviours".
9. Simulation Core to Sensor models, "Entity states".
10. Sensor models to Tracker and Fusion, "Sensor reports".
11. ROE Validator to Simulation Core, "Action verdicts".
12. Rule and Sensor Packs and Terrain Packs to Simulation Core, "Versioned parameters".
13. Simulation Core to Hash-Chained Event Log, "Append events".
14. Hash-Chained Event Log to Record Signer, "Chain head".
15. Hash-Chained Event Log to Decision-Tree Scorer, "Logged actions".
16. Decision-Tree Scorer to Adaptive Proficiency Model, "Skill observations".
17. Scoring, records and audit boxes to Relational Database, "Persist results".
18. Relational Database to API Gateway, "Replays, reports".
19. Docker Compose Stack to API Gateway and Relational Database, "Hosts services".

BOTTOM BANNER: a full-width navy bar at the bottom with white text: "Offline, LAN-served, on-premises, deterministic and replayable".

Do not add any other boxes, logos, numbers, badges, status marks, URLs or decorative elements. Keep generous spacing so every label is legible.
```
