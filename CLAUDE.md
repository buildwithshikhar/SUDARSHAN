# CLAUDE.md

Standing instructions for Claude Code in this repository. Read this first every session, then [docs/BUILD_LOG.md](docs/BUILD_LOG.md) to find where the build stands.

## Project

SUDARSHAN is an AI-enabled drone and counter-drone threat simulation **trainer** for Smart India Hackathon 2026, problem statement 26247 (Ministry of Defence / Defence Services Staff College; category Software; theme Robotics and Drones). The PS text is in [docs/PS-26247.md](docs/PS-26247.md). This is an independent student project with no official affiliation.

Planning is complete; the documents are indexed in [docs/README.md](docs/README.md). Do not rewrite research documents (docs/00–09). Record new decisions in [docs/DECISIONS.md](docs/DECISIONS.md) and open items in [docs/OPEN_QUESTIONS.md](docs/OPEN_QUESTIONS.md).

### Product name is one configuration value

- In code the name lives only in `brand.json` at the repo root, created in wave 1:
  `{ "productName": "SUDARSHAN", "descriptor": "Counter-UAS Threat Recognition Trainer", "status": "confirmed" }`
- The web app, the API, page titles, PDF reports and the Docker image labels read it from there. Never hard-code the name in source, tests, templates or config.
- A rename is a one-line change to `brand.json` plus a find-and-replace in docs prose.

## LOCKED RULES (cannot be relaxed, even by an upgrade)

1. Honesty. Never claim real operational or classified data, validated training effectiveness, or doctrine accuracy. Standard wording: "built from open research datasets and published specifications, in fictional scenarios." Any effectiveness claim must come from our own measured pilot. Show uncertainty explicitly. Label reference/generated data honestly.
2. Defensive training only. Recognise / classify / respond. No instructions for building, arming or operating attack drones; no real-world targeting detail. ROE are a fictional, editable rule set.
3. Claude Code stays inside the repo, touches no Docker objects outside it, pushes only main, never deploys, and never puts credentials in the repo or slides. Production mode blocks demo accounts; credentials come from first-admin env vars / CLI.

What these mean in practice:
- Threat behaviour is kinematics only: no guidance, terminal-attack or targeting logic. Effectors are generic fictional classes with fictional numbers. No real system names or performance figures.
- Terrain is generic or fictionalised. No identifiable sensitive installations. Site and unit names are fictional.
- The UI shows a permanent "fictional scenario · open-source parameters" label. Seeded data is labelled "reference data".
- Docker commands use only this repo's compose project. Secrets come from environment variables; commit only `.env.example` with placeholders.

## Recorded decisions

Full entries in [docs/DECISIONS.md](docs/DECISIONS.md).

| Topic | Decision |
|---|---|
| Name | SUDARSHAN, held in `brand.json` |
| Trainee model | Operator plus detachment commander (team mode). Staff-planning layer is a stretch module. |
| Hardware floor | 8 GB RAM laptop, integrated graphics, no internet. No VR headset assumed; WebXR optional and deferred. |
| Next SIH milestone | A deployable live link. Deployment is a first-class requirement. |
| Team | Solo, Claude Code writes all code. |
| Pilot | 12 civilian volunteers × 4 sessions. |
| Language | English and Hindi from the first wave. |
| Engine | Three.js (`WebGLRenderer`); MapLibre GL for the 2D map. |
| Simulation | Server-authoritative, deterministic Python sim core (numpy, seeded RNG, 20 Hz tick). The client receives sensor frames only. |

## Stack

- Web: React + TypeScript (strict) + Vite + Tailwind; Three.js; MapLibre GL; i18n (EN/HI); Vitest.
- API: Python 3.12, FastAPI, SQLAlchemy 2 + Alembic, Pydantic v2, uv; pytest, ruff, mypy --strict.
- Database: SQLite by default, Postgres 16 in compose and production.
- Quality: Playwright + @axe-core/playwright, visual snapshots, gitleaks.
- Delivery: Docker + docker compose, GitHub Actions CI.
- Optional, deferred: WebXR.

Repo layout (created in wave 1): `apps/web/`, `services/api/`, `packs/` (rule packs, scenarios, sensor profiles, terrain), `infra/`, `docs/`, `brand.json`, `Makefile`.

## How to work a wave

1. Read `docs/BUILD_LOG.md`, then the current wave file in [docs/waves/](docs/waves/). Do only that wave's scope.
2. At most 2 subagents at once, each in its own git worktree. Merge each back to `main` only when its tests pass.
3. Small conventional commits (`feat:`, `fix:`, `test:`, `docs:`, `chore:`, `build:`, `ci:`, `refactor:`, `perf:`). One logical change per commit. See [CONTRIBUTING.md](CONTRIBUTING.md).
4. Every feature ships with tests. CI must be green on `main` before the wave is marked done.
5. Update `docs/BUILD_LOG.md` after every merged step, so a `/clear` can resume from the log alone.
6. Never carry a red build across a `/clear`. If about 60% of the session is used before acceptance, stop at the next green commit, log it, and continue as wave n.2 (for example 9a.2).
7. Stop and report instead of guessing when a step needs credentials, network beyond package registries and GitHub, a Docker action outside this compose project, or when CI fails 3 times on the same cause.
8. Do not build features from later waves.

Model choice: Sonnet by default. Opus only where a wrong design is expensive to undo (waves 3, 4a, 4b and 9a, or wave 7 if the benchmark gate fails).

## Wave execution protocol

1. Read `docs/BUILD_LOG.md` first, then only the files the current wave file lists. Do not read other docs unless a step needs them.
2. Make small conventional commits, one logical change per commit.
3. Update `docs/BUILD_LOG.md` after every merged step.
4. Before finishing, run the full test suite and `make smoke` against the production-mode stack.
5. From wave 2 on, never leave the deployable build broken; fix or revert before stopping.
6. Finish with a summary of at most 10 lines: what changed, test and smoke results, commit to deploy, open items, next step.

## Deployment is first-class

- The first deployable slice (wave 2) goes live early. After that, every wave keeps the deployed build working.
- Each wave's acceptance includes: production images build, the production-mode compose stack starts, and `make smoke` passes against it (`/healthz`, `/readyz`, `/api/v1/version`).
- Hosting needs a Docker-capable host with persistent storage. Render free has no persistent disk and sleeps, so it is not suitable.
- A Vercel frontend needs `VITE_API_URL` at build time and `CORS_ORIGINS` on the backend.
- The user deploys. Claude Code prepares config, docs and smoke tests, and never deploys.
- Production mode refuses to start with a missing or default `SECRET_KEY` and refuses demo accounts. The first admin comes from `FIRST_ADMIN_*` env vars or the `create-admin` CLI.

## Data policy

- Datasets are "calibrated from", never "trained on". We derive numeric parameters and cite them.
- Every sensor-profile or threat parameter carries a register ID from [docs/DATA_REGISTER.md](docs/DATA_REGISTER.md).
- Raw samples ship only under a confirmed open licence (CC0, CC BY, ODbL with attribution and share-alike, or equivalent). Non-commercial, research-only and "licence not stated" sources are never shipped and never shown as clips.
- Raw downloads stay outside git (`data/raw/` is ignored).
- Scenarios are "verified solvable by test run" (an oracle-defender run), never "provably solvable".
- The ~85% target success rate is a heuristic. Thermal is a rendering model, not radiometric. Weather is "modelled".

## Quality bar

The product must look and feel like enterprise, defence-grade software and must not look AI-generated.

Banned:
- Purple/blue gradient heroes, gradient text, glow borders, glassmorphism.
- Emoji as icons, sparkle "AI" badges, generic three-card feature grids, bento grids, KPI tiles everywhere.
- Default Tailwind or shadcn look shipped unchanged; lorem ipsum, "John Doe", round-number fake data.
- Mixed icon sets, cartoon illustrations, marketing copy, confetti, toast spam.
- Generic labels ("Dashboard", "Insights") instead of domain nouns ("Live monitor", "Unit AAR", "Track table").

Required:
- The design system in [docs/07-ui-map.md](docs/07-ui-map.md): graphite palette tokens, one interactive accent, IBM Plex Sans / Plex Mono with tabular numerals, Noto Sans Devanagari, 4 px spacing grid, IBM Carbon icons only.
- Dark operations theme as primary, with a tested light theme.
- Dense but readable operational layouts. Every screen has populated, empty, loading and error states.
- Keyboard navigation everywhere. WCAG AA, axe-clean in CI. Colour is never the only cue.
- Sensor consoles that look like instruments, not charts.
- A convincing 3D scene (lighting, NV and thermal looks, weather, terrain) that meets the benchmark gate in [docs/04-engine.md](docs/04-engine.md) on the floor laptop.
- Realistic seeded data on every screen; `make demo` reproduces it from fixed seeds.

## Documentation

Maintain docs like a product: README, architecture, user manual, instructor and admin SOPs, API docs, final report, requirement-traceability matrix, release process, changelog, plus `docs/PERFORMANCE.md` for benchmark results. Update the traceability proof column as features land.

## Working rules

- No calendar timelines unless asked. Work in dependency order; deploy a thin working slice early, then layer.
- Token discipline: be concise, no recaps, no repeated context. Say when a task should be split.
- Chase perfection: every screen, doc and commit message is polished.
- When something is missing from the requirements or plan, say so and add it to `docs/OPEN_QUESTIONS.md`.

## Upgrade clause

Everything above except the LOCKED RULES is a baseline. A change that clearly raises quality, rigour, speed or reliability may be adopted:
- Upgrades only. Never lower the bar or remove a quality requirement.
- Never touch the LOCKED RULES.
- Tell the user in one or two lines what changed and why, and add a line to the Standards changelog below.
- Ask first if the upgrade costs significant extra effort or tokens.
- If it is only a preference between equal options, change nothing.

## Standards changelog

- 2026-10-17: Instructions created.
- 2026-10-17: Platform name confirmed as SUDARSHAN, held in one config value. Recorded decisions: operator plus detachment commander, 8 GB integrated-graphics floor, deployable live link as the next milestone, solo with Claude Code, 12 × 4 pilot, Hindi UI from wave 1, Three.js.
- 2026-10-17: One resumable `docs/BUILD_LOG.md` replaces per-wave round logs; per-wave prompts live in `docs/waves/`. Reason: a single log is easier to resume after `/clear`.
- 2026-10-17: Added the wave execution protocol. Reason: a short fixed checklist keeps every wave resumable and the deployed build green.
