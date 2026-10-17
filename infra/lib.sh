# Shared helpers for the deployment scripts. Source it; do not run it.
# shellcheck shell=bash
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PRODUCT_NAME="${PRODUCT_NAME:-$(python3 -c "import json; print(json.load(open('brand.json'))['productName'])")}"
PROJECT="${PROJECT:-$(printf '%s' "$PRODUCT_NAME" | tr '[:upper:]' '[:lower:]')}"
ENV_FILE="${ENV_FILE:-.env}"
COMPOSE_FILES="${COMPOSE_FILES:--f infra/docker-compose.yml -f infra/docker-compose.prod.yml -f infra/docker-compose.https.yml}"
BACKUP_DIR="${BACKUP_DIR:-./backups}"
BACKUP_KEEP="${BACKUP_KEEP:-14}"
export PRODUCT_NAME
GIT_SHA="$(git rev-parse --short HEAD 2>/dev/null || echo dev)"
BUILD_TIME="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
export GIT_SHA BUILD_TIME

# shellcheck disable=SC2086
compose() { docker compose -p "$PROJECT" --env-file "$ENV_FILE" $COMPOSE_FILES "$@"; }

die() { echo "error: $*" >&2; exit 1; }
say() { echo "==> $*"; }

env_value() { # env_value NAME  -> value from the env file, empty if unset
  [ -f "$ENV_FILE" ] || return 0
  grep -E "^$1=" "$ENV_FILE" | tail -n 1 | cut -d= -f2-
}

rand_hex() { python3 -c "import secrets; print(secrets.token_hex($1))"; }
