#!/bin/sh
# Usage: infra/smoke.sh [URL]   (default http://localhost:8080)
# Checks liveness, readiness and the version endpoint; exits non-zero on any failure.
# EXPECT_ENV=production additionally asserts the reported environment.
set -eu
URL="${1:-http://localhost:8080}"
URL="${URL%/}"
fail() { echo "smoke: FAIL $1" >&2; exit 1; }

check() {
  path="$1"
  body="$(curl -fsS --retry 10 --retry-delay 2 --retry-connrefused --max-time 5 "$URL$path")" \
    || fail "$path did not return 200"
  echo "smoke: ok   $path"
  printf '%s' "$body"
}

check /healthz >/dev/null
check /readyz >/dev/null
version="$(check /api/v1/version)"
echo "$version" | grep -q '"productName"' || fail "/api/v1/version has no productName"
if [ -n "${EXPECT_ENV:-}" ]; then
  echo "$version" | grep -q "\"env\":\"$EXPECT_ENV\"" || fail "expected env $EXPECT_ENV, got: $version"
fi
echo "smoke: PASS $URL"
