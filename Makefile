# Common tasks. The product name comes from brand.json; nothing here hard-codes it.
SHELL := /bin/bash
PRODUCT_NAME := $(shell node -p "require('./brand.json').productName")
PROJECT ?= $(shell echo '$(PRODUCT_NAME)' | tr '[:upper:]' '[:lower:]')
GIT_SHA := $(shell git rev-parse --short HEAD 2>/dev/null || echo dev)
BUILD_TIME := $(shell date -u +%Y-%m-%dT%H:%M:%SZ)
export PRODUCT_NAME GIT_SHA BUILD_TIME
# Host port for the stack: environment or command line first, then .env, then 8080.
# Example when 8080 is taken: `WEB_PORT=8090 make demo visual`.
WEB_PORT ?= $(or $(shell grep -s '^WEB_PORT=' .env | cut -d= -f2),8080)
URL ?= http://localhost:$(WEB_PORT)

# Passed to the demo stack only; prod-check and backup-test set their own ports.
COMPOSE = env WEB_PORT=$(WEB_PORT) docker compose -p $(PROJECT) --env-file .env -f infra/docker-compose.yml
COMPOSE_PROD = $(COMPOSE) -f infra/docker-compose.prod.yml
# Portable random hex (openssl is not guaranteed on every build host).
rand = $$(python3 -c "import secrets; print(secrets.token_hex($(1)))")
UV = $(shell command -v uv || echo $$HOME/Library/Python/3.10/bin/uv)

.PHONY: setup env dev schemas lint typecheck test e2e visual build up down demo smoke create-admin prod-check backup-test check-deploy build-amd64 terrain ci-api help

help:
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | sed 's/:.*##/\t/' || true

setup: ## install dependencies (uv from PyPI if missing)
	@command -v uv >/dev/null 2>&1 || python3 -m pip install --user uv
	cd services/api && $(UV) sync
	cd apps/web && npm ci

env: ## create .env with random secrets if it does not exist
	@if [ -f .env ]; then echo ".env exists; leaving it alone"; else \
	  umask 077; \
	  printf 'APP_ENV=demo\nSECRET_KEY=%s\nPOSTGRES_PASSWORD=%s\n' "$(call rand,32)" "$(call rand,16)" > .env; \
	  echo "created .env with random secrets"; fi

dev: ## run API and web dev servers (two terminals: see README)
	@echo "API: cd services/api && uv run uvicorn app.main:get_app --factory --reload"
	@echo "Web: cd apps/web && npm run dev"

schemas: ## export contract JSON Schemas to packs/schemas and regenerate the web TypeScript types
	cd services/api && $(UV) run python -m app.contracts.export
	cd apps/web && npm run contracts:gen

lint: ## ruff, eslint, prettier
	cd services/api && $(UV) run ruff check . && $(UV) run ruff format --check .
	cd apps/web && npm run lint

typecheck: ## mypy --strict, tsc
	cd services/api && $(UV) run mypy .
	cd apps/web && npm run typecheck

test: ## pytest (coverage gate) and vitest
	cd services/api && $(UV) run pytest -q
	cd apps/web && npm test

e2e: ## Playwright smoke, role and axe tests against URL (signed-in tests need the local demo stack)
	@COMPOSE_CMD="$(COMPOSE)" URL=$(URL) infra/e2e.sh chromium

visual: ## Playwright visual snapshots (per-platform baselines); add ARGS=--update-snapshots to refresh
	@COMPOSE_CMD="$(COMPOSE)" URL=$(URL) infra/e2e.sh visual $(ARGS)

build: ## build both production images
	$(COMPOSE) build

up: env ## start the stack (demo mode) on http://localhost:$WEB_PORT (default 8080)
	$(COMPOSE) up -d --build --wait

down: ## stop the stack; data volume is kept
	$(COMPOSE) down

demo: up ## start the stack and seed demo accounts (passwords printed once)
	$(COMPOSE) exec -T api python -m app.cli seed-demo
	@echo "Open $(URL)"

ci-api: ## API tests on x86-64 Linux like the CI job; ARGS="tests/x.py" CI_CPUS=2
	@cd services/api && docker compose -p $(PROJECT) -f ../../infra/docker-compose.ci.yml run --rm ci-api uv run pytest -q --no-cov $(ARGS)

smoke: ## health, readiness and version checks against URL
	@infra/smoke.sh $(URL)

terrain: ## bake the terrain packs from data/raw (TERRAIN_RAW=dir to override); needs the raw SRTM and OSM files
	cd tools/terrain && $(UV) run python -m terrain bake all --raw $(abspath $(or $(TERRAIN_RAW),data/raw)) --out $(abspath packs/terrain)

create-admin: ## create the first administrator in the running stack (prompts, or uses FIRST_ADMIN_*)
	$(COMPOSE) exec api python -m app.cli create-admin

prod-check: ## production images and stack on a throwaway project: smoke, page load, bootstrap, HTTPS, memory
	@infra/prod-check.sh

backup-test: ## backup and restore round trip on a throwaway project
	@infra/backup-test.sh

check-deploy: ## health, readiness, version and a page load against a deployed URL (URL=https://...)
	@infra/check-deploy.sh $(URL)

build-amd64: ## build linux/amd64 images (for an ARM Mac); see docs/DEPLOY.md
	docker buildx build --platform linux/amd64 -f infra/Dockerfile.api -t $(PROJECT)-api:amd64 --load .
	docker buildx build --platform linux/amd64 -f infra/Dockerfile.web -t $(PROJECT)-web:amd64 --load .
