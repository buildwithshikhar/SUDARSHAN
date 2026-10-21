# Wave 1 · Repo bootstrap

| | |
|---|---|
| Depends on | — |
| Deployment | Deploy-ready: production images and smoke test exist, nothing is hosted yet. |

**Goal.** A clean, production-shaped monorepo with CI green: health endpoints, admin bootstrap, a bilingual placeholder page, and Docker images ready to deploy.

## Scope

- Monorepo layout: `apps/web/`, `services/api/`, `packs/` (`rule-packs/`, `scenarios/`, `sensor-profiles/`, `terrain/`, each with a README stating "fictional / open-source parameters"), `infra/`, `Makefile`.
- `brand.json` at the root holding the product name (see CONTRIBUTING.md). Web and API read it; nothing else hard-codes the name.
- API skeleton: `/healthz`, `/readyz`, `/api/v1/version`; settings; production guard; User model and first migration; `create-admin` and `seed-demo` CLIs.
- Web skeleton: React + TS strict + Vite + Tailwind with the design tokens from `docs/07-ui-map.md` as CSS variables (dark default, light via `data-theme`); one placeholder route; i18n wired with EN and HI.
- Infra: multi-stage Dockerfiles, `docker compose` (web, api, db), a production compose override, `make demo` and `make smoke`.
- CI on GitHub Actions and Dependabot.
- Working docs: `docs/DESIGN.md` (tokens and banned list from 07), `docs/TRACEABILITY.md` (copy of the 06 table, proof column to be filled as features land), `CHANGELOG.md`, `SECURITY.md`, `docs/RELEASE.md` (stub).

## Out of scope

- Product features, auth UI and the design-system components (wave 2).
- Any hosting configuration for a specific provider (wave 2, once the host is chosen).

## Files to read

`CONTRIBUTING.md`, `docs/BUILD_LOG.md`, this file, `docs/05-architecture.md` (§1, §2, deployment view) and `docs/07-ui-map.md` (design-system direction and banned list). Skim `docs/DECISIONS.md`. Nothing else.

## Prerequisites on the build machine

Node 20+ and npm; Python 3.12 via `uv` (`make setup` installs `uv` from PyPI if missing and lets it fetch Python 3.12); Docker with a running daemon for the image, compose and production-mode checks. If Docker is not running, the code and tests can still be finished, but the wave is not Done until the Docker acceptance items pass.

## Deliverables

**Repository.** Layout as in the prompt; every `packs/*` directory has a README stating "fictional / open-source parameters"; `.env.example` has placeholders only; `.env` is generated locally by `make env` with random values and is git-ignored.

**API.**
- `GET /healthz` (no DB), `GET /readyz` (DB ping, 503 on failure), `GET /api/v1/version` (`productName`, `descriptor`, `version`, `gitSha`, `buildTime`, `env`), all reading the name from `brand.json`.
- Settings from environment; production guard at startup (missing, default or short `SECRET_KEY`; any user flagged `is_demo`).
- `User` model with `is_demo`, first Alembic migration, argon2 hashes, minimum password length 12 for admins.
- CLIs: `create-admin` (from `FIRST_ADMIN_*` or prompt, idempotent), `seed-demo` (refuses in production; creates one admin, one instructor, one trainee on reserved `.invalid` addresses with random passwords printed once).

**Web: the single placeholder screen, "Build status".**
- Top bar (40 px): signal-colour tick, product name from `brand.json`, descriptor in secondary text, language switch (EN / HI), theme switch (dark / light).
- Body: one bordered panel of labelled rows in Plex-style monospace tabular figures, filled from `/api/v1/version`: Service, Version, Commit, Built, Environment, API status. States: loading (skeleton rows), populated, error (message and retry), and empty is not applicable. No cards, KPI tiles, gradients or icons.
- Footer strip with the permanent label "FICTIONAL SCENARIOS · OPEN-SOURCE PARAMETERS" (translated).
- Design-system rules applied now: the token table in `docs/07-ui-map.md` as CSS variables (dark default, light via `data-theme`), 4 px grid, 2 px control radius, 1 px borders instead of shadows, system font stack with a Devanagari fallback until wave 2 self-hosts Plex and Noto, visible focus ring in the accent colour, `prefers-reduced-motion` respected, no emoji, no icon library yet.

**Infrastructure.** Multi-stage non-root Dockerfiles; nginx (unprivileged) serving the built client and proxying `/api`, `/healthz`, `/readyz`; compose with web, api, db (Postgres 16, named volume); production override with `APP_ENV=production`, required secrets, restart policies and healthchecks. The compose project name and image labels come from `brand.json` through the Makefile, not from hard-coded strings.

**Delivery.** CI workflow with api, web, e2e, secrets and docker jobs, caching on; Dependabot for pip, npm and GitHub Actions.

**Docs.** `docs/DESIGN.md`, `docs/TRACEABILITY.md`, `CHANGELOG.md`, `SECURITY.md`, `docs/RELEASE.md`, two ADRs (numbers 015 and 016, because 011–013 are taken and 014 is reserved for wave 3), `docs/README.md` index entries.

## Tests

- **Unit (api):** health, readyz up and down, version payload from `brand.json`, settings parsing, every production-guard branch, `create-admin` idempotency and password rule, `seed-demo` refusal in production and its output, migration up and down. Coverage ≥ 90% for this wave's code.
- **Unit (web, Vitest):** EN/HI key parity, token contrast (every text and UI pair meets WCAG AA in both themes), version panel in loading, populated and error states, language and theme switches, `brand.json` drives the title.
- **Integration:** API against SQLite in tests and against Postgres in the compose CI job.
- **End to end (Playwright):** load `/`, see name and live version, switch to HI and back, switch theme, keyboard-only reach of both switches.
- **Accessibility:** `@axe-core/playwright` with zero violations in EN and HI, dark and light.
- **Determinism:** nothing in this wave is simulated, so no determinism tests; the version payload is the only time-dependent output and tests inject the build time.
- **No snapshot tests yet:** visual regression starts in wave 2.

## Commit plan

1. `chore: scaffold monorepo layout, brand.json and pack READMEs`
2. `feat(api): add settings, brand loader and health endpoints`
3. `feat(api): add user model, migration and production guard`
4. `feat(api): add create-admin and seed-demo CLIs`
5. `feat(web): scaffold Vite app with tokens, i18n and build-status screen`
6. `test(web): add key parity, contrast and e2e/axe tests`
7. `build: add Dockerfiles, nginx, compose files and Makefile`
8. `ci: add workflow and dependabot`
9. `docs: add design, traceability, security, release docs and ADRs`
10. `docs: log wave 1`

## Model and effort

No design decision here is expensive to undo. The wave is large but linear; if the session passes about 60% before acceptance, stop at the next green commit and log the rest as wave 1.2.

## Stop conditions

Same as the prompt: credentials needed; network beyond package registries, GitHub and the test browser download; a Docker action outside this repo's compose project; CI failing 3 times on the same cause; about 60% of the session used.

## Verification checklist

1. `make setup && make lint typecheck test` exits 0 on a fresh clone.
2. `make demo && make smoke` exits 0; open http://localhost:8080 and confirm name, version rows, the EN/HI switch, the theme switch and the footer label (screenshot in dark, light and HI).
3. `APP_ENV=production` with no `SECRET_KEY`: the API exits non-zero with a message naming `SECRET_KEY`.
4. `make create-admin` twice in production mode: first creates, second reports "exists".
5. `seed-demo` with `APP_ENV=production` exits non-zero.
6. `make e2e` reports zero axe violations.
7. `make prod-check` builds the production images, starts the production stack on a throwaway project, passes `make smoke`, and removes only that project.
8. `git grep -n -i "$(node -p "require('./brand.json').productName")" -- apps services infra Makefile .github` finds nothing outside `brand.json`.
9. `gitleaks` (CI) and `git log -p | grep -i "password\|secret"` show no credentials.
10. CI is green on `main`.

## Acceptance criteria

- Fresh clone: `make setup && make lint typecheck test` passes (command check).
- `make demo` then `make smoke` passes; http://localhost:8080 shows the placeholder with live version info, and the EN/HI switch works (screenshot check).
- `make prod-check` passes: production images build and the production-mode stack passes `make smoke`.
- No occurrence of the product name outside `brand.json` in `apps/`, `services/`, `infra/`, `Makefile` and `.github/` (grep check).
- `APP_ENV=production` without `SECRET_KEY` fails to start with a clear message; with it and no admin, `make create-admin` creates one, idempotently.
- `seed-demo` refuses to run in production.
- API coverage ≥ 90% for this wave's code; Playwright smoke and axe report 0 violations.
- CI is green on `main` (lint, typecheck, unit, e2e, gitleaks, docker build).
- Every feature in this wave has tests; no existing test was skipped, disabled or weakened.
- Production images build and the production-mode compose stack passes `make smoke`.
- `docs/BUILD_LOG.md` is updated per its rules, including the deploy check and the next wave entry point.
- No credentials, secrets or real keys anywhere in git history; only `.env.example` placeholders.

## Brief

````text
ROLE: Build wave 1 (Repo bootstrap) of SUDARSHAN, an AI-enabled drone and counter-drone threat simulation TRAINER (SIH 2026, PS 26247). Follow the project rules in CONTRIBUTING.md, above all the content rules.

READ FIRST: docs/BUILD_LOG.md (confirm the build has not started; if it has, stop and tell me). Then: docs/05-architecture.md and docs/07-ui-map.md (design tokens). Skim docs/DECISIONS.md. Do not read the other planning docs unless a decision needs them.

GOAL: A clean, production-shaped monorepo with CI green: health endpoints, admin bootstrap, a bilingual placeholder page, and Docker images ready to deploy.

STEP 0 — Repo
- The repo already exists and is cloned; work on main. Do not create or rename repos.
- Conventional commits, small and focused.

STEP 1 — Layout
apps/web/        React 18 + TypeScript (strict) + Vite + Tailwind; Vitest; ESLint + Prettier; i18next (en, hi)
services/api/    Python 3.12, FastAPI, SQLAlchemy 2 + Alembic, Pydantic v2, uv; pytest, ruff, mypy --strict
packs/           rule-packs/, scenarios/, sensor-profiles/, terrain/ (README in each: "fictional / open-source parameters")
infra/           docker-compose.yml (compose project name derived from brand.json by the Makefile, never hard-coded; services web [nginx serving built client], api [uvicorn], db [postgres:16, named volume]); docker-compose.prod.yml; Dockerfiles (multi-stage, non-root); nginx.conf
brand.json       { "productName": "SUDARSHAN", "descriptor": "Counter-UAS Threat Recognition Trainer", "status": "confirmed" }
Makefile         setup, dev, lint, typecheck, test, e2e, build, up, down, demo, smoke, create-admin
.env.example     placeholders only

STEP 2 — API skeleton (track A, worktree)
- GET /healthz (liveness, no DB), GET /readyz (DB ping), GET /api/v1/version (git sha, build time, productName from brand.json).
- pydantic-settings: APP_ENV=demo|production, DATABASE_URL (default SQLite file), SECRET_KEY, CORS_ORIGINS, FIRST_ADMIN_EMAIL, FIRST_ADMIN_PASSWORD.
- Production guard: in production, refuse to start if SECRET_KEY is missing or default, or if any demo account exists; log a clear error.
- User model (id, email, argon2 password hash, role enum trainee|instructor|admin, created_at) + Alembic migration.
- typer CLI: create-admin (env or prompt; idempotent), seed-demo (refuses in production).
- Tests: health, readyz with and without DB, production guard, create-admin idempotency, seed-demo refusal. Coverage ≥ 90% for this wave's code.

STEP 3 — Web skeleton (track B, worktree)
- Tokens from docs/07-ui-map.md as CSS variables; dark default, light via data-theme. No component-library defaults, no gradients.
- Route "/" shows productName and descriptor from brand.json, the /api/v1/version result, a language switch (EN/HI) and the label "FICTIONAL SCENARIOS · OPEN-SOURCE PARAMETERS" (translated). It must look deliberate (system UI font stack until wave 2).
- i18next with en.json and hi.json; a unit test fails if any key is missing from either file.
- Vitest unit test; Playwright smoke + @axe-core/playwright with zero violations.

STEP 4 — Infra + CI (main track, after A and B merge)
- docker compose up builds and serves web on :8080, proxying /api, /healthz and /readyz to api.
- docker-compose.prod.yml: APP_ENV=production, no demo seed, persistent volume for the DB, restart policies, healthchecks.
- make demo: compose up in demo mode, run migrations, seed-demo (one admin, one instructor, one trainee; demo-only passwords printed to the console, never committed).
- make smoke: curl /healthz, /readyz, /api/v1/version against URL (default http://localhost:8080); exit non-zero on failure.
- .github/workflows/ci.yml: api (ruff, mypy, pytest), web (eslint, tsc, vitest, build), e2e (compose up → Playwright smoke + axe), secrets scan (gitleaks), docker build of both images. Cache dependencies.
- Dependabot for pip, npm and GitHub Actions.

STEP 5 — Working docs
- docs/DESIGN.md (tokens and banned list from 07), docs/TRACEABILITY.md (copy the table from docs/06-requirements-traceability.md), CHANGELOG.md (Keep a Changelog), SECURITY.md, docs/RELEASE.md (stub with the licence re-check step).
- Add ADR-015 (monorepo and stack) and ADR-016 (server-authoritative deterministic sim) to docs/DECISIONS.md (011–013 are taken; 014 is reserved for wave 3).
- Add the new docs to docs/README.md.

OUT OF SCOPE (do not build):
- Product features, auth UI and the design-system components (wave 2).
- Any hosting configuration for a specific provider (wave 2, once the host is chosen).

ACCEPTANCE (all must be true):
- Fresh clone: `make setup && make lint typecheck test` passes (command check).
- `make demo` then `make smoke` passes; http://localhost:8080 shows the placeholder with live version info, and the EN/HI switch works (screenshot check).
- `make prod-check` passes: production images build and the production-mode stack passes `make smoke`.
- No occurrence of the product name outside `brand.json` in `apps/`, `services/`, `infra/`, `Makefile` and `.github/` (grep check).
- `APP_ENV=production` without `SECRET_KEY` fails to start with a clear message; with it and no admin, `make create-admin` creates one, idempotently.
- `seed-demo` refuses to run in production.
- API coverage ≥ 90% for this wave's code; Playwright smoke and axe report 0 violations.
- CI is green on `main` (lint, typecheck, unit, e2e, gitleaks, docker build).
- Every feature in this wave has tests; no existing test was skipped, disabled or weakened.
- Production images build and the production-mode compose stack passes `make smoke`.
- `docs/BUILD_LOG.md` is updated per its rules, including the deploy check and the next wave entry point.
- No credentials, secrets or real keys anywhere in git history; only `.env.example` placeholders.

LOG: Follow the rules in docs/BUILD_LOG.md. Add a "Wave 1" entry at the start, append each merged commit, record decisions, test counts and the deploy check, and write the exact first step of wave 2.

STOP CONDITIONS — stop and report if:
- a step needs credentials, or network beyond package registries and GitHub;
- a Docker action would touch anything outside this repo's compose project;
- CI fails 3 times on the same cause;
- about 60% of the session is used before acceptance (commit green work, log it as wave 1.2, stop);
- Never build features from later waves.

FINAL OUTPUT TO ME: at most 10 lines — commits, test counts, CI result, deploy check (and the commit for me to deploy), anything skipped and why, and the first step of wave 2.
````
