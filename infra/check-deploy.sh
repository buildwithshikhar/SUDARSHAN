#!/bin/sh
# Usage: infra/check-deploy.sh [URL]    (default http://localhost:8080)
# Checks a deployed instance: /healthz, /readyz, /api/v1/version and one real page load
# (the HTML shell and the main script it references). Exits non-zero on any failure.
#   EXPECT_ENV=production   also assert the reported environment (set to empty to skip)
#   CURL_OPTS=-k            pass extra curl options, for example to accept a local test certificate
set -eu
URL="${1:-http://localhost:8080}"
URL="${URL%/}"
here="$(cd "$(dirname "$0")" && pwd)"
PRODUCT="${PRODUCT_NAME:-$(python3 -c "import json; print(json.load(open('$here/../brand.json'))['productName'])")}"
fail() { echo "check-deploy: FAIL $1" >&2; exit 1; }

EXPECT_ENV="${EXPECT_ENV-production}" "$here/smoke.sh" "$URL"

# shellcheck disable=SC2086
page="$(curl -fsS ${CURL_OPTS:-} --max-time 10 "$URL/")" || fail "/ did not return 200"
echo "$page" | grep -q 'id="root"' || fail "/ is not the application shell"
echo "$page" | grep -q "<title>$PRODUCT</title>" || fail "page title is not $PRODUCT"
script="$(echo "$page" | grep -o 'src="/assets/[^"]*\.js"' | head -n 1 | sed 's/^src="//; s/"$//')"
[ -n "$script" ] || fail "no application script referenced by /"
# shellcheck disable=SC2086
curl -fsS ${CURL_OPTS:-} --max-time 10 -o /dev/null "$URL$script" || fail "$script did not load"
echo "check-deploy: ok   page load ($script)"
echo "check-deploy: PASS $URL"
