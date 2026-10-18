# Changelog

All notable changes are recorded here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Wave 4b: tracker and fusion in `sim/tracking/` (six-state Kalman filter, gated nearest-neighbour association, track lifecycle with coasting, triangulation of bearing-only reports, duplicate-track folding, initiation-exclusion zone); seeded association errors (swap, split, merge) that can only occur where gates overlap; a ground-truth ledger that records them with the true identities and when an operator fix restores them; track commands (relabel, merge, split, drop) and cue-to-track as loggable actions (`action-record.v1` gains five values); the sensor picture wired into `World` (state, hash, snapshot and replay include it; a bare world hashes as before); a seeded simulated AI assist with configured hit, false-alarm and class rates. Every detection, track and assist view a trainee receives carries `data_status` and is labelled reference data while sensor parameters remain unverified (Q-20). No user-facing change yet.
- Wave 4a (step 4): acceptance pass; a cross-model test file pins P(d) monotonicity, weather and light effects, confusion normalisation, provenance and the SENSOR_MODELS.md contents across all six shipped profiles. Wave 4a complete locally; CI confirmation pending. No user-facing change.
- Wave 4a (steps 2 and 3): radar (RCS, aspect, micro-Doppler, clutter and rain), EO/IR (Johnson criteria, day, night-vision and thermal, haze and glare, cueing), RF (link budget, band plan, hopping, RF-silent targets, Wi-Fi and Bluetooth confusers, interference) and acoustic (blade-pass harmonics, spreading and absorption, wind noise) models, five cited fictional sensor profiles, and `docs/SENSOR_MODELS.md`. No user-facing change yet.
- Wave 4a (step 1): sensor framework in `sim/sensors/` (detect template, cueing, degradations, profile loader, confusion tables in `sensor-profile.v1`) and deterministic `atan2`, `exp`, `log` in the sim maths. No user-facing change yet. See `docs/SIM_CORE.md`.
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
