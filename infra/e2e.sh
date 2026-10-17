#!/bin/bash
# Usage: infra/e2e.sh <chromium|visual> [extra playwright args]
# Seeds the three demo accounts with a one-off random password when the target is the local demo
# stack, then runs Playwright against $URL. Against any other URL only the signed-out tests run.
set -euo pipefail
PROJECT="${1:?project name}"; shift || true
URL="${URL:-http://localhost:8080}"
PASSWORD_ENV=""
case "$URL" in
  http://localhost:*|http://127.0.0.1:*)
    if [ -n "${COMPOSE_CMD:-}" ] && $COMPOSE_CMD ps --status running --services 2>/dev/null | grep -q '^api$'; then
      PW="$(python3 -c 'import secrets; print(secrets.token_urlsafe(18))')"
      $COMPOSE_CMD exec -T -e DEMO_PASSWORD="$PW" api python -m app.cli seed-demo >/dev/null
      PASSWORD_ENV="$PW"
    fi
    ;;
esac
if [ -z "$PASSWORD_ENV" ]; then
  echo "e2e: no local demo stack seeded; signed-in tests will be skipped" >&2
fi
cd apps/web
PLAYWRIGHT_BASE_URL="$URL" E2E_PASSWORD="$PASSWORD_ENV" npx playwright test --project="$PROJECT" "$@"
