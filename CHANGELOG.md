# Changelog

All notable changes are recorded here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Wave 3: versioned contracts (`scenario.v1`, `rulepack.v1`, `sensor-profile.v1`, event, action and session records) with exported JSON Schemas, generated TypeScript types and drift checks; one fictional example of each pack.
- Wave 3: deterministic sim core (fixed 20 Hz tick, named PCG64 streams, waypoint kinematics inside class limits), hash-chained event log, snapshot and restore, replay, and golden-file tests. See `docs/SIM_CORE.md`.
- Wave 2: sign-in with server-side sessions, CSRF protection and a login rate limit; role guards; `create-user` command; per-user language and theme.
- Wave 2: self-hosted IBM Plex Sans, IBM Plex Mono and Noto Sans Devanagari; UI primitives; a role-based shell with Status, Profile, About and system-state screens in English and Hindi (Hindi is an unreviewed draft).
- Wave 2: deployment kit for a Linux VM (Caddy automatic HTTPS from `DOMAIN` and `ACME_EMAIL`, deploy, update, rollback, backup and restore scripts), `make check-deploy`, and the runbook `docs/DEPLOY.md`.
- Wave 2: `make prod-check` now covers page load, bootstrap, cookies, CSRF, HTTPS and memory; `make backup-test` and `make visual`.

- Monorepo layout, product identity in `brand.json`, and pack directories.
- API: `/healthz`, `/readyz`, `/api/v1/version`, settings, production start-up guard, user model with first migration, `create-admin` and `seed-demo` commands.
- Web: build-status screen with design tokens, English and Hindi, dark and light themes.
- Docker images, compose stack with a production override, `make demo`, `make smoke` and `make prod-check`.
- CI workflow (lint, types, tests, end-to-end with axe, secrets scan, image build) and Dependabot.
- Working documents: design system, requirements traceability, security policy and release process.
