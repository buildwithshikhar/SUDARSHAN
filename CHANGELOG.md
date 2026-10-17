# Changelog

All notable changes are recorded here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Monorepo layout, product identity in `brand.json`, and pack directories.
- API: `/healthz`, `/readyz`, `/api/v1/version`, settings, production start-up guard, user model with first migration, `create-admin` and `seed-demo` commands.
- Web: build-status screen with design tokens, English and Hindi, dark and light themes.
- Docker images, compose stack with a production override, `make demo`, `make smoke` and `make prod-check`.
- CI workflow (lint, types, tests, end-to-end with axe, secrets scan, image build) and Dependabot.
- Working documents: design system, requirements traceability, security policy and release process.
