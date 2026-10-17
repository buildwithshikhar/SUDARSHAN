# Common tasks. The product name comes from brand.json; nothing here hard-codes it.
SHELL := /bin/bash
PRODUCT_NAME := $(shell node -p "require('./brand.json').productName")
PROJECT ?= $(shell echo '$(PRODUCT_NAME)' | tr '[:upper:]' '[:lower:]')
GIT_SHA := $(shell git rev-parse --short HEAD 2>/dev/null || echo dev)
BUILD_TIME := $(shell date -u +%Y-%m-%dT%H:%M:%SZ)
export PRODUCT_NAME GIT_SHA BUILD_TIME
WEB_PORT := $(or $(shell grep -s '^WEB_PORT=' .env | cut -d= -f2),8080)
URL ?= http://localhost:$(WEB_PORT)

COMPOSE = docker compose -p $(PROJECT) --env-file .env -f infra/docker-compose.yml
COMPOSE_PROD = $(COMPOSE) -f infra/docker-compose.prod.yml
# Portable random hex (openssl is not guaranteed on every build host).
rand = $$(python3 -c "import secrets; print(secrets.token_hex($(1)))")
UV = $(shell command -v uv || echo $$HOME/Library/Python/3.10/bin/uv)

.PHONY: setup env dev lint typecheck test e2e build up down demo smoke create-admin prod-check help

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

lint: ## ruff, eslint, prettier
	cd services/api && $(UV) run ruff check . && $(UV) run ruff format --check .
	cd apps/web && npm run lint

typecheck: ## mypy --strict, tsc
	cd services/api && $(UV) run mypy .
	cd apps/web && npm run typecheck

test: ## pytest (coverage gate) and vitest
	cd services/api && $(UV) run pytest -q
	cd apps/web && npm test

e2e: ## Playwright smoke and axe against URL (default http://localhost:8080)
	cd apps/web && PLAYWRIGHT_BASE_URL=$(URL) npx playwright test

build: ## build both production images
	$(COMPOSE) build

up: env ## start the stack (demo mode) on http://localhost:8080
	$(COMPOSE) up -d --build --wait

down: ## stop the stack; data volume is kept
	$(COMPOSE) down

demo: up ## start the stack and seed demo accounts (passwords printed once)
	$(COMPOSE) exec -T api python -m app.cli seed-demo
	@echo "Open $(URL)"

smoke: ## health, readiness and version checks against URL
	@infra/smoke.sh $(URL)

create-admin: ## create the first administrator in the running stack (prompts, or uses FIRST_ADMIN_*)
	$(COMPOSE) exec api python -m app.cli create-admin

prod-check: ## build production images, run the production stack on a throwaway project, smoke it, remove it
	@set -e; \
	P=$(PROJECT)-prodcheck; F=.env.prodcheck; \
	umask 077; \
	printf 'SECRET_KEY=%s\nPOSTGRES_PASSWORD=%s\nWEB_PORT=18080\nFIRST_ADMIN_EMAIL=ops@prodcheck.invalid\nFIRST_ADMIN_PASSWORD=%s\n' \
	  "$(call rand,32)" "$(call rand,16)" "$(call rand,16)" > $$F; \
	C="docker compose -p $$P --env-file $$F -f infra/docker-compose.yml -f infra/docker-compose.prod.yml"; \
	cleanup() { $$C down -v --remove-orphans >/dev/null 2>&1 || true; rm -f $$F; }; \
	trap cleanup EXIT; \
	$$C up -d --build --wait; \
	EXPECT_ENV=production infra/smoke.sh http://localhost:18080; \
	$$C exec -T api python -m app.cli create-admin | grep -q "exists: ops@prodcheck.invalid"; \
	echo "prod-check: admin bootstrap is idempotent"; \
	if $$C exec -T api python -m app.cli seed-demo; then echo "prod-check: FAIL seed-demo ran in production" >&2; exit 1; fi; \
	echo "prod-check: PASS"
