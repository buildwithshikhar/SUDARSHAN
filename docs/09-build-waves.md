# 09 · Build waves (dependency order)

> **Execution note (2026-10-17):** the per-wave files in [waves/](waves/) and the resumable [BUILD_LOG.md](BUILD_LOG.md) are what the team runs. They apply the recorded decisions (repo already exists, one `docs/BUILD_LOG.md` instead of `ROUND_<n>_LOG.md`, deployment as a first-class requirement). This file is kept as the original plan.

Each wave is sized for one work session. You a work session between waves; `docs/ROUND_<n>_LOG.md` carries state. Each wave ends with CI green on `main`, the log updated, and the verification checklist ticked. At most 2 parallel tracks run per wave.


| Wave | Name | Depends on | Delivers | Thin-slice deploy? |
|---|---|---|---|---|
| 1 | **Repo bootstrap** | — | Private repo, monorepo, tooling, CI, Docker skeleton, `/healthz` and `/readyz`, prod/demo modes, `create-admin`, docs skeleton, brand constant | — |
| 2 | **Design system + app shell** | 1 | Tokens (07), self-hosted Plex and Devanagari fonts, Carbon icons, role-based sidebar, auth and RBAC, i18n EN/HI, theme switch, empty/loading/error states, axe in CI, first visual snapshots | **Yes: first deploy (shell + login + health)** |
| 3 | **Contracts + deterministic sim core** | 1 | Pydantic + JSON Schema for scenario spec, rule pack, sensor profile, event record; fixed-tick engine with seeded RNG; flat-terrain world; single-drone kinematics; hash-chained event log; determinism and replay tests; TS type codegen | — |
| 4 | **Sensor models + fusion + AI assist** | 3 | Radar, EO/IR, RF, acoustic detection models (probability of detection vs range/aspect/weather/time-of-day), degradations, simple tracker/fusion, simulated AI assist with set error rates; each parameter carries a data-register ID | — |
| 5 | **Live-session vertical slice** | 2, 4 | WebSocket protocol, session manager, Three.js EO view (basic), radar PPI, track table, decision panel, ROE validator, one scripted scenario end-to-end, 12-client LAN load test | **Yes: playable slice** |
| 6 | **Scoring + debrief** | 5 | Decision-tree evaluator (Detect → Classify → Assess → Respond with an ROE hard-fail gate), node explanations, SDT metrics, golden-log tests, debrief screen | Yes |
| 7 | **3D realism + terrain packs** | 5 | Offline SRTM/OSM bake pipeline (rural + urban packs), time of day, NV and thermal passes, weather, HUD, quality tiers, **benchmark gate (04)** in `docs/PERFORMANCE.md` | — |
| 8 | **Threat breadth** | 4, 7 | Drone class catalogue, swarm behaviours (boids / Vicsek noise / leader-follower), decoys, RF-silent threats, birds, kites, balloons, permitted civil drones | — |
| 9 | **Scenario engine** | 6, 8 | Seeded generator, hard constraints, oracle-defender solvability check, MAP-Elites diversity grid + novelty filter, scripted library, scenario editor UI | Yes |
| 10 | **Instructor console** | 5, 9 | Cohorts, launch, live monitor with ground-truth overlay, pause, inject macros, annotate, team setup | — |
| 11 | **Adaptive learning + recognition library** | 6, 9 | Per-skill Elo + BKT display, next-scenario policy (~85% predicted success, heuristic), Leitner/SM-2 signature drills, threat and clutter catalogue | — |
| 12 | **Full AAR + reports** | 6, 10, 11 | Seen-vs-truth replay, decision path, confusion matrix, reaction-time curves, miss-zone heat map, unit trends, PDF and CSV export | **Yes: demo-complete** |
| 13 | **Team mode, trust and admin** | 10, 12 | Multi-operator roles and handoff scoring, Ed25519-signed chain head plus verify CLI, users and units admin, pack manager, data-register viewer, audit log, backup/restore | — |
| 14 | **WebXR + hardening** | 7, 12 | WebXR observer/EO mode (emulator-tested), accessibility pass, performance pass, visual regression for the 12 key screens, security review | — |
| 15 | **Docs + release 1.0** | all | User manual, instructor and admin SOPs, API docs, traceability matrix completed (06), final report, release process, changelog, demo rehearsal from `make demo` | Release |

**Pilot** (your activity, not a wave): starts once wave 12 is green. Waves 13–15 continue in parallel, so pilot data reaches the AAR screens and the final report.

**Split rule:** if a wave's log shows more than about 60% of the session used before acceptance, stop at the next green commit and continue as wave n.b. Never carry a red build across a a work session.

---

## Wave 1 brief

Before pasting: create an empty folder, put the planning files (01–09 from the project library) in `docs/planning/`, and open the project in that folder.

````text
ROLE: Build wave 1 (repo bootstrap) of SIH26247, an AI-enabled drone and counter-drone threat simulation TRAINER (SIH 2026, PS 26247, MoD / DSSC). Planning docs are in docs/planning/ — read 05-architecture.md and 07-ui-map.md (design tokens) only; skim others if a decision needs them.

LOCKED RULES (never break):
1. Honesty: no claims of real operational data, validated effectiveness or doctrine accuracy. Standard wording: "built from open research datasets and published specifications, in fictional scenarios."
2. Defensive training only. No content on building, arming or operating attack drones.
3. Stay inside this repo. Touch no Docker objects outside this compose project (project name: sih26247). Push only to main. Never deploy. Never put credentials in the repo; use .env.example with placeholders only.

GOAL: a clean, production-shaped monorepo with CI green and nothing product-specific yet beyond health endpoints and admin bootstrap.

STEP 0 — Repo
- git init; create a PRIVATE GitHub repo "sih26247" with gh (gh repo create sih26247 --private --source . --push) after the first commit. If gh is not authenticated, stop and tell me.
- Conventional commits, small and focused (chore:, build:, ci:, feat:, docs:, test:).

STEP 1 — Layout
apps/web/            React 18 + TypeScript (strict) + Vite + Tailwind; Vitest; ESLint + Prettier
services/api/        Python 3.12, FastAPI, SQLAlchemy 2 + Alembic, Pydantic v2, uv for deps; pytest, ruff, mypy --strict
packs/               rule-packs/, scenarios/, sensor-profiles/, terrain/  (each with a README stating "fictional / open-source parameters")
infra/               docker-compose.yml (services: web [nginx serving built client], api [uvicorn], db [postgres:16]); Dockerfiles; nginx.conf
docs/                README links + ARCHITECTURE.md (from planning/05), DECISIONS/ADR-0001-stack.md, ADR-0002-server-authoritative-sim.md, ADR-0003-threejs.md, DATA_REGISTER.md (stub table), TRACEABILITY.md (copy table from planning/06), DESIGN.md (tokens from planning/07), CHANGELOG.md (Keep a Changelog), RELEASE.md, SECURITY.md, ROUND_1_LOG.md
brand.json           { "productName": "SUDARSHAN", "descriptor": "Counter-UAS Threat Recognition Trainer", "status": "confirmed" } — the ONLY place the name lives; web and api read it.
Makefile             setup, dev, lint, typecheck, test, e2e, build, up, down, demo, smoke, create-admin

STEP 2 — API skeleton (track A, worktree)
- GET /healthz (liveness, no DB), GET /readyz (DB ping), GET /api/v1/version (git sha, build time, productName).
- Settings via pydantic-settings: APP_ENV=demo|production, DATABASE_URL (default sqlite file), SECRET_KEY, CORS_ORIGINS, FIRST_ADMIN_EMAIL, FIRST_ADMIN_PASSWORD.
- Production guard: in production, refuse to start if SECRET_KEY is missing/default or any demo account exists; log a clear error.
- User model (id, email, password hash argon2, role enum trainee|instructor|admin, created_at) + Alembic migration.
- CLI (typer): `create-admin` (reads env or prompts; idempotent), `seed-demo` (refuses in production).
- Tests: health, readyz with/without DB, production guard, create-admin idempotency, seed-demo refusal. Coverage ≥ 90% for this wave's code.

STEP 3 — Web skeleton (track B, worktree)
- Vite + React + TS strict + Tailwind with design tokens from planning/07 as CSS variables (dark default, light via data-theme). No component library styling defaults left in; no gradients.
- One placeholder route "/" showing productName + descriptor from brand.json, API /version result, and a "FICTIONAL SCENARIOS · OPEN-SOURCE PARAMETERS" label. Must look deliberate (Plex fonts are wave 2; use system UI stack for now).
- Vitest unit test; Playwright smoke test + @axe-core/playwright with zero violations.

STEP 4 — Infra + CI (main track, after A and B merge)
- docker compose up builds and serves web on :8080 proxying /api and /healthz to api.
- `make demo`: compose up in APP_ENV=demo, run migrations, seed-demo (one admin, one instructor, one trainee, demo-only passwords printed to console, never committed).
- `make smoke`: curl /healthz, /readyz, /api/v1/version; exit non-zero on failure.
- GitHub Actions (.github/workflows/ci.yml): jobs for api (ruff, mypy, pytest), web (eslint, tsc, vitest, build), e2e (compose up → Playwright smoke + axe), secrets scan (gitleaks), docker build. Cache deps. Must pass on main.
- Dependabot config for pip/npm/actions.

STEP 5 — Log
docs/ROUND_1_LOG.md: sections — Goal, Decisions (with reasons), Done (commit hashes), Tests (counts), Open issues, Next wave entry point (exact first step for wave 2). Update it after every merged step so a /clear can resume.

ACCEPTANCE (all must be true)
- Fresh clone: `make setup && make lint typecheck test` passes.
- `make demo` then `make smoke` passes; web at http://localhost:8080 shows the placeholder with live version info.
- APP_ENV=production without SECRET_KEY fails to start with a clear message; with SECRET_KEY and no admin, `make create-admin` creates one.
- CI green on main; gitleaks clean; axe 0 violations.
- No credentials or real secrets in git history.

STOP CONDITIONS
- Stop and report if: gh is not authenticated; a step needs credentials or network beyond package registries/GitHub; a Docker action would touch anything outside compose project "sih26247"; CI fails 3 times on the same cause; or the session is ~60% used before acceptance (commit green work, update the log, stop).
- Do not build features from later waves.

FINAL OUTPUT TO ME: a 10-line summary — commits, test counts, CI link, anything skipped and why, and the first step of wave 2.
````

---

## Verification checklist (planning phase)

- [ ] 01: answers to Q1–Q6 given, or defaults accepted.
- [ ] 02: name chosen. IP India TM search run for Classes 9, 41, 42 and logged.
- [ ] 03: every dataset licence in the register confirmed on its source page before use. Non-commercial or research-only items flagged.
- [ ] 04: floor laptop identified for the benchmark gate.
- [ ] 05: architecture diagram rendered (Mermaid Live or the repo) and the slide built from §6.
- [ ] 06: every PS clause has a mechanism and a proof. The honest-wording hotspots (R0, R8, R18, R19) are agreed.
- [ ] 07: tokens copied into `docs/DESIGN.md` in wave 1. Banned list reviewed.
- [ ] 08: fictional names checked against real places and units (no accidental real match).
- [ ] 09: wave 1 brief run. BUILD_LOG.md reviewed here before wave 2.
