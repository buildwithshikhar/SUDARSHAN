# 05 · Technical architecture

Platform: SUDARSHAN. Stack per project instructions; engine per 04.

## 1. Principles

1. **Server-authoritative simulation.** The Python sim core owns ground truth. The browser sees only what its sensors would report. This prevents cheating, and pause, inject, team mode and replay all come from one code path.
2. **Deterministic by construction.** Given the same scenario spec, seed and trainee-action log, the result is the same, tick for tick. Every replay, re-score and solvability check depends on this, and it is tested in CI.
3. **Everything versioned.** Scenario packs, rule packs (ROE plus scoring weights), sensor profiles and the learner model each carry a version. Every score records the versions that produced it.
4. **Offline first.** No CDN and no online tiles. One `docker compose up` on the instructor laptop serves the whole classroom over LAN.
5. **Honest by design.** Every reference value carries its source ID from the data register, and the UI shows a "fictional scenario · open-source parameters" label permanently.

## 2. Component diagram

```mermaid
flowchart LR
  subgraph Client["Browser client · React + TS + Vite + Tailwind"]
    UI["App shell · RBAC routes · i18n EN/HI"]
    SV["Sim view · Three.js<br/>EO/IR camera · NV/thermal passes · weather"]
    MAP["Tactical map · MapLibre<br/>offline OSM vector tiles"]
    CON["Sensor consoles<br/>radar PPI · RF waterfall · acoustic spectrogram · track table"]
    ACT["Decision panel<br/>classify · assess · respond per ROE"]
    INS["Instructor console<br/>live monitor · pause · inject · annotate"]
    AAR["AAR dashboard<br/>replay · decision path · confusion matrix · heat map"]
    ED["Scenario & rule-pack editor"]
    WS["WS client · 20 Hz state → 60 fps interpolation"]
  end

  subgraph API["FastAPI service"]
    GW["REST + WebSocket gateway<br/>auth · RBAC · rate limit · audit"]
    SCN["Scenario service<br/>library · procedural generator<br/>solvability check · diversity check"]
    SIM["Sim runtime<br/>session manager · 20 Hz tick"]
    subgraph Core["Sim core · numpy · seeded RNG"]
      WRLD["World<br/>terrain · buildings · weather · light"]
      THR["Threat models<br/>drone classes · behaviours · swarms · civil clutter"]
      SEN["Sensor models<br/>radar · EO/IR · RF · acoustic · degradation"]
      FUS["Tracker / fusion<br/>+ simulated AI detection assist"]
      EFF["Effects<br/>fictional effector classes from rule pack"]
    end
    SCO["Scoring engine<br/>decision tree Detect→Classify→Assess→Respond"]
    LRN["Learner model<br/>per-skill proficiency · recommender · spaced repetition"]
    AARS["AAR service<br/>aggregates · replay · PDF/CSV export"]
    REC["Session records<br/>hash-chained event log · Ed25519 signature"]
  end

  DB[("SQLAlchemy<br/>SQLite default · Postgres 16")]
  PK[("Packs on disk<br/>terrain · scenarios · rule packs · sensor profiles")]

  UI --> GW
  WS <--> GW
  GW --> SCN & SIM & SCO & LRN & AARS
  SIM --> Core
  SCN --> Core
  SIM --> REC --> DB
  SCO --> DB
  LRN --> DB
  AARS --> DB
  SCN --> PK
  SIM --> PK
```

## 3. Data flows

### 3.1 Scenario generation (procedural, solvable, diverse)

```mermaid
flowchart TD
  A["Request: difficulty vector + terrain + time of day + weather + threat mix + seed<br/>(from instructor, curriculum or learner model)"] --> B["Sample candidate spec<br/>(seeded RNG)"]
  B --> C{"Hard constraints<br/>ROE-consistent · sensor coverage exists · timing windows ≥ min reaction time"}
  C -- fail --> B
  C -- pass --> D["Headless run with oracle defender<br/>(perfect-policy agent, same sim core)"]
  D --> E{"Solvable?<br/>oracle reaches max score within time"}
  E -- no --> B
  E -- yes --> F["Feature vector<br/>threat mix · approach bearings · clutter density · sensor degradations · timing"]
  F --> G{"Diversity vs trainee history<br/>min distance ≥ threshold · cell novelty"}
  G -- too similar --> B
  G -- ok --> H["Store spec + hash · attach to session"]
```

Retry budget: N attempts, then relax the softest constraint and log it. The spec stores the seed, generator version and every check result, so the AAR can show "this scenario was verified solvable".

### 3.2 Live session

```mermaid
sequenceDiagram
  participant T as Trainee browser
  participant G as Gateway (WS)
  participant S as Sim runtime
  participant R as Event log
  participant I as Instructor console
  T->>G: join(session, role)
  G->>S: load spec + seed + rule pack
  loop every 50 ms tick
    S->>S: threat behaviours → sensor models (noise, degradation) → tracker/fusion → AI assist
    S-->>T: sensor frame (tracks, detections, visible entities in FOV only)
    S-->>I: full picture incl. ground truth
  end
  T->>G: action (designate / classify / assess / engage / hold / report)
  G->>S: validate against ROE rule pack
  S->>R: append event (prev-hash, payload) 
  S-->>T: outcome + feedback (per training mode)
  I->>G: pause / inject event / annotate
  G->>S: apply, logged as instructor event
  S->>R: end-of-session marker · sign chain head
```

### 3.3 Scoring

The event log and ground truth go into the decision-tree evaluator, which walks each threat's tree:

- **Detect**: time from first detectable moment to first designation.
- **Classify**: class correct? False alarms on clutter?
- **Assess**: threat level and intent correct?
- **Respond**: ROE-compliant action, effector choice and timing; hold fire on civil traffic.

Each node gets a score and a plain-language reason ("Detected 14 s after first radar return; standard 10 s"). The session score is the weighted sum, using rule-pack weights. Signal-detection metrics (hit rate, false-alarm rate, d′) are computed per class.

### 3.4 After-action review

The AAR replays the hash-verified log in a split view of **what you saw** (sensor frames) against **ground truth**. Beside the replay it shows the decision-tree path per threat, a confusion matrix, reaction-time curves and a miss-zone heat map. Aggregates roll up to trainee, cohort and unit across sessions, and export to PDF and CSV.

### 3.5 Adaptive difficulty loop

```mermaid
flowchart LR
  S["Scored nodes<br/>tagged by skill"] --> O["Observations per skill<br/>(e.g. classify-FPV-at-night)"]
  O --> M["Learner model update<br/>(Elo/BKT per skill; see 03)"]
  M --> P["Policy: aim at ~85% predicted success (heuristic)<br/>+ spaced-repetition due skills"]
  P --> Q["Next difficulty vector + skill focus"]
  Q --> GEN["Scenario generator (3.1)"]
  GEN --> SES["Next session"] --> S
```

## 4. Deployment view

```mermaid
flowchart LR
  subgraph Laptop["Instructor laptop (Docker)"]
    N["web: nginx · static client + offline tiles + assets"]
    A["api: uvicorn FastAPI · sim runtime"]
    P[("db: Postgres 16 (or SQLite file)")]
    N --> A --> P
  end
  T1["Trainee browser 1"] & T2["Trainee browser 2"] & T3["… up to 12"] -->|LAN http/ws| N
```

Production mode refuses demo accounts. The first admin is created from environment variables or `create-admin`. `/healthz` and `/readyz` are available. `make demo` seeds reference data from fixed seeds. the team prepares config and the owner deploys; you handle hosting (for a public demo: a Docker host with persistent storage; Vercel for the frontend needs `VITE_API_URL` at build time and `CORS_ORIGINS` set on the backend).

## 5. Key interfaces (contracts fixed in wave 1–2)

| Contract | Format | Versioned |
|---|---|---|
| Scenario spec | JSON Schema (`scenario.v1.json`) | yes |
| Rule pack (ROE + weights + thresholds) | YAML with JSON Schema validation | yes |
| Sensor profile | YAML, each parameter carrying a data-register source ID | yes |
| Sensor frame (WS) | MessagePack, typed in TS from Pydantic via codegen | yes |
| Event log record | `{seq, t, type, actor, payload, prev_hash, hash}` | yes |

## 6. PPT-ready slide description (one slide, 16:9)

- **Title:** "Architecture: one authoritative simulation, many views".
- **Layout:** three columns on a graphite background.
  - **Left column, "Classroom":** trainee and instructor browser tiles.
  - **Centre, a large box, "SUDARSHAN server":** the sim core drawn as four stacked bands (World, Threats, Sensors, Fusion + AI assist). On its right edge sit Scoring, Learner model and AAR. Across the bottom is a hash-chained log drawn as linked blocks.
  - **Right column, "Packs":** Scenario packs, Rule packs (ROE), Sensor profiles, Terrain.
- **Arrows:** a thin amber loop around the centre labelled "adaptive loop: score → skill model → next scenario". The only other arrows are grey.
- **Footer line:** "Runs offline on one laptop · LAN for 12 trainees · deterministic, replayable, signed".
- **Avoid:** cloud icons, 3D isometric clip-art and gradients. Use flat outlines with 1.5 px strokes and one accent colour.
