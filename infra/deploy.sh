#!/bin/bash
# Deployment helper for a single Linux VM running Docker. Run it from the repository checkout.
#
#   infra/deploy.sh init --domain NAME --email ADDRESS   create .env with random secrets
#   infra/deploy.sh up                                    build and start the production stack
#   infra/deploy.sh update                                back up, pull, rebuild, restart, check
#   infra/deploy.sh rollback                              return to the commit deployed before the last update
#   infra/deploy.sh check                                 run the deployed-URL checks
#   infra/deploy.sh status | logs [service]               inspect the stack
#   infra/deploy.sh create-admin                          create the first administrator (prompts)
#   infra/deploy.sh backup | restore <backup-dir>         data backup and restore
#
# NO_BUILD=1 starts from images that are already loaded on the machine (see docs/DEPLOY.md).
# HTTPS=0 leaves out Caddy (for testing behind another proxy). No credential is read from, or
# written to, anywhere but the git-ignored .env file.
set -euo pipefail
# shellcheck source=infra/lib.sh
. "$(dirname "$0")/lib.sh"
mkdir -p .deploy

public_url() {
  local domain; domain="$(env_value DOMAIN)"
  if [ "${HTTPS:-1}" = "0" ] || [ -z "$domain" ]; then
    local port; port="$(env_value WEB_PORT)"
    echo "http://127.0.0.1:${port:-8080}"
  else
    echo "https://$domain"
  fi
}

cmd_init() {
  local domain="" email=""
  while [ $# -gt 0 ]; do
    case "$1" in
      --domain) domain="${2:?--domain needs a value}"; shift 2 ;;
      --email) email="${2:?--email needs a value}"; shift 2 ;;
      *) die "unknown option $1" ;;
    esac
  done
  [ -n "$domain" ] && [ -n "$email" ] || die "usage: infra/deploy.sh init --domain NAME --email ADDRESS"
  [ ! -f "$ENV_FILE" ] || die "$ENV_FILE already exists; edit it by hand or remove it first"
  umask 077
  {
    echo "APP_ENV=production"
    echo "SECRET_KEY=$(rand_hex 32)"
    echo "POSTGRES_PASSWORD=$(rand_hex 16)"
    echo "DOMAIN=$domain"
    echo "ACME_EMAIL=$email"
    echo "WEB_PORT=8080"
    echo "WEB_BIND=127.0.0.1"
  } > "$ENV_FILE"
  say "wrote $ENV_FILE (mode 600) with new random secrets. Keep it out of git and out of chat."
  say "next: infra/deploy.sh up, then infra/deploy.sh create-admin"
}

cmd_up() {
  [ -f "$ENV_FILE" ] || die "$ENV_FILE is missing; run infra/deploy.sh init first"
  [ "$(env_value APP_ENV)" = "production" ] || die "APP_ENV in $ENV_FILE must be production"
  say "building and starting ($PROJECT, commit $GIT_SHA)"
  if [ "${NO_BUILD:-0}" = "1" ]; then
    compose up -d --no-build --wait --remove-orphans
  else
    compose up -d --build --wait --remove-orphans
  fi
}

cmd_check() {
  local url; url="$(public_url)"
  say "checking $url"
  CURL_OPTS="${CURL_OPTS:-}" EXPECT_ENV=production "$(dirname "$0")/check-deploy.sh" "$url"
}

cmd_update() {
  [ -f "$ENV_FILE" ] || die "$ENV_FILE is missing"
  git diff --quiet && git diff --cached --quiet || die "uncommitted changes in the checkout; stash or discard them first"
  git rev-parse HEAD > .deploy/previous-commit
  say "backing up before the update"
  "$(dirname "$0")/backup.sh" | tail -n 1 > .deploy/last-backup
  say "pulling the latest main"
  git pull --ff-only
  # re-read the version stamps after the pull
  GIT_SHA="$(git rev-parse --short HEAD)"; export GIT_SHA
  cmd_up
  if cmd_check; then
    say "updated to $(git rev-parse --short HEAD); previous commit recorded for rollback"
  else
    echo "The update did not pass its checks. To go back: infra/deploy.sh rollback" >&2
    echo "If the new version changed the database schema, also restore: infra/deploy.sh restore $(cat .deploy/last-backup)" >&2
    exit 1
  fi
}

cmd_rollback() {
  [ -f .deploy/previous-commit ] || die "no previous commit recorded; nothing to roll back to"
  local previous; previous="$(cat .deploy/previous-commit)"
  say "checking out $previous"
  git checkout --detach "$previous"
  GIT_SHA="$(git rev-parse --short HEAD)"; export GIT_SHA
  cmd_up
  cmd_check
  say "rolled back to $GIT_SHA. Database migrations only move forward: if the failed release changed"
  say "the schema, restore the backup taken before it ($(cat .deploy/last-backup 2>/dev/null || echo none)):"
  say "  infra/deploy.sh restore <that backup>"
  say "To resume normal updates later: git checkout main"
}

case "${1:-}" in
  init) shift; cmd_init "$@" ;;
  up) cmd_up ;;
  update) cmd_update ;;
  rollback) cmd_rollback ;;
  check) cmd_check ;;
  status) compose ps ;;
  logs) shift; compose logs --tail=200 "$@" ;;
  create-admin) compose exec api python -m app.cli create-admin ;;
  backup) "$(dirname "$0")/backup.sh" ;;
  restore) shift; "$(dirname "$0")/restore.sh" "$@" ;;
  *) sed -n '2,15p' "$0"; exit 1 ;;
esac
