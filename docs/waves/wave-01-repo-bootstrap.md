# Wave 1 · Repo bootstrap

| | |
|---|---|
| Depends on | — |
| Recommended model | Sonnet |
| Deployment | Deploy-ready: production images and smoke test exist, nothing is hosted yet. |

**Goal.** A clean, production-shaped monorepo with CI green: health endpoints, admin bootstrap, a bilingual placeholder page, and Docker images ready to deploy.

## Scope

- Monorepo layout: `apps/web/`, `services/api/`, `packs/` (`rule-packs/`, `scenarios/`, `sensor-profiles/`, `terrain/`, each with a README stating "fictional / open-source parameters"), `infra/`, `Makefile`.
- `brand.json` at the root holding the product name (see CLAUDE.md). Web and API read it; nothing else hard-codes the name.
- API skeleton: `/healthz`, `/readyz`, `/api/v1/version`; settings; production guard; User model and first migration; `create-admin` and `seed-demo` CLIs.
- Web skeleton: React + TS strict + Vite + Tailwind with the design tokens from `docs/07-ui-map.md` as CSS variables (dark default, light via `data-theme`); one placeholder route; i18n wired with EN and HI.
- Infra: multi-stage Dockerfiles, `docker compose` (web, api, db), a production compose override, `make demo` and `make smoke`.
- CI on GitHub Actions and Dependabot.
- Working docs: `docs/DESIGN.md` (tokens and banned list from 07), `docs/TRACEABILITY.md` (copy of the 06 table, proof column to be filled as features land), `CHANGELOG.md`, `SECURITY.md`, `docs/RELEASE.md` (stub).

## Out of scope

- Product features, auth UI and the design-system components (wave 2).
- Any hosting configuration for a specific provider (wave 2, once the host is chosen).

## Acceptance criteria

- Fresh clone: `make setup && make lint typecheck test` passes.
- `make demo` then `make smoke` passes; http://localhost:8080 shows the placeholder with live version info, and the EN/HI switch works.
- `APP_ENV=production` without `SECRET_KEY` fails to start with a clear message; with it and no admin, `make create-admin` creates one, idempotently.
- `seed-demo` refuses to run in production.
- API coverage ≥ 90% for this wave's code; Playwright smoke and axe report 0 violations.
- CI is green on `main` (lint, typecheck, unit, e2e, gitleaks, docker build).
- Every feature in this wave has tests; no existing test was skipped, disabled or weakened.
- Production images build and the production-mode compose stack passes `make smoke`.
- `docs/BUILD_LOG.md` is updated per its rules, including the deploy check and the next wave entry point.
- No credentials, secrets or real keys anywhere in git history; only `.env.example` placeholders.

## Prompt (paste into Claude Code, Sonnet)

````text
ROLE: You are building wave 1 (Repo bootstrap) of SUDARSHAN, an AI-enabled drone and counter-drone threat simulation TRAINER (SIH 2026, PS 26247). CLAUDE.md is loaded: follow it, above all the LOCKED RULES.

READ FIRST: docs/BUILD_LOG.md (confirm the build has not started; if it has, stop and tell me). Then: docs/05-architecture.md and docs/07-ui-map.md (design tokens). Skim docs/DECISIONS.md. Do not read the other planning docs unless a decision needs them.

GOAL: A clean, production-shaped monorepo with CI green: health endpoints, admin bootstrap, a bilingual placeholder page, and Docker images ready to deploy.

STEP 0 — Repo
- The repo already exists and is cloned; work on main. Do not create or rename repos.
- Conventional commits, small and focused.

STEP 1 — Layout
apps/web/        React 18 + TypeScript (strict) + Vite + Tailwind; Vitest; ESLint + Prettier; i18next (en, hi)
services/api/    Python 3.12, FastAPI, SQLAlchemy 2 + Alembic, Pydantic v2, uv; pytest, ruff, mypy --strict
packs/           rule-packs/, scenarios/, sensor-profiles/, terrain/ (README in each: "fictional / open-source parameters")
infra/           docker-compose.yml (compose project name: sudarshan; services web [nginx serving built client], api [uvicorn], db [postgres:16, named volume]); docker-compose.prod.yml; Dockerfiles (multi-stage, non-root); nginx.conf
brand.json       { "productName": "SUDARSHAN", "descriptor": "Counter-UAS Threat Recognition Trainer", "status": "confirmed" }
Makefile         setup, dev, lint, typecheck, test, e2e, build, up, down, demo, smoke, create-admin
.env.example     placeholders only

STEP 2 — API skeleton (subagent A, worktree)
- GET /healthz (liveness, no DB), GET /readyz (DB ping), GET /api/v1/version (git sha, build time, productName from brand.json).
- pydantic-settings: APP_ENV=demo|production, DATABASE_URL (default SQLite file), SECRET_KEY, CORS_ORIGINS, FIRST_ADMIN_EMAIL, FIRST_ADMIN_PASSWORD.
- Production guard: in production, refuse to start if SECRET_KEY is missing or default, or if any demo account exists; log a clear error.
- User model (id, email, argon2 password hash, role enum trainee|instructor|admin, created_at) + Alembic migration.
- typer CLI: create-admin (env or prompt; idempotent), seed-demo (refuses in production).
- Tests: health, readyz with and without DB, production guard, create-admin idempotency, seed-demo refusal. Coverage ≥ 90% for this wave's code.

STEP 3 — Web skeleton (subagent B, worktree)
- Tokens from docs/07-ui-map.md as CSS variables; dark default, light via data-theme. No component-library defaults, no gradients.
- Route "/" shows productName and descriptor from brand.json, the /api/v1/version result, a language switch (EN/HI) and the label "FICTIONAL SCENARIOS · OPEN-SOURCE PARAMETERS" (translated). It must look deliberate (system UI font stack until wave 2).
- i18next with en.json and hi.json; a unit test fails if any key is missing from either file.
- Vitest unit test; Playwright smoke + @axe-core/playwright with zero violations.

STEP 4 — Infra + CI (main session, after A and B merge)
- docker compose up builds and serves web on :8080, proxying /api, /healthz and /readyz to api.
- docker-compose.prod.yml: APP_ENV=production, no demo seed, persistent volume for the DB, restart policies, healthchecks.
- make demo: compose up in demo mode, run migrations, seed-demo (one admin, one instructor, one trainee; demo-only passwords printed to the console, never committed).
- make smoke: curl /healthz, /readyz, /api/v1/version against URL (default http://localhost:8080); exit non-zero on failure.
- .github/workflows/ci.yml: api (ruff, mypy, pytest), web (eslint, tsc, vitest, build), e2e (compose up → Playwright smoke + axe), secrets scan (gitleaks), docker build of both images. Cache dependencies.
- Dependabot for pip, npm and GitHub Actions.

STEP 5 — Working docs
- docs/DESIGN.md (tokens and banned list from 07), docs/TRACEABILITY.md (copy the table from docs/06-requirements-traceability.md), CHANGELOG.md (Keep a Changelog), SECURITY.md, docs/RELEASE.md (stub with the licence re-check step).
- Add ADR-011 (monorepo and stack) and ADR-012 (server-authoritative deterministic sim) to docs/DECISIONS.md.
- Add the new docs to docs/README.md.

OUT OF SCOPE (do not build):
- Product features, auth UI and the design-system components (wave 2).
- Any hosting configuration for a specific provider (wave 2, once the host is chosen).

ACCEPTANCE (all must be true):
- Fresh clone: `make setup && make lint typecheck test` passes.
- `make demo` then `make smoke` passes; http://localhost:8080 shows the placeholder with live version info, and the EN/HI switch works.
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
- about 60% of the session is used before acceptance (commit green work, log it as wave 1.b, stop);
- Never build features from later waves.

FINAL OUTPUT TO ME: at most 10 lines — commits, test counts, CI result, deploy check (and the commit for me to deploy), anything skipped and why, and the first step of wave 2.
````
