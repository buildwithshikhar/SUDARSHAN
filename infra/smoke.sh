#!/bin/sh
# Usage: infra/smoke.sh [URL]   (default http://localhost:8080)
# Checks liveness, readiness and the version endpoint; exits non-zero on any failure.
# EXPECT_ENV=production additionally asserts the reported environment.
# EXPECT_EVALUATION=true|false asserts the evaluation entry is on or off; unset, it accepts either.
# CURL_OPTS=-k passes extra curl options (for example to accept a local test certificate).
set -eu
URL="${1:-http://localhost:8080}"
URL="${URL%/}"
fail() { echo "smoke: FAIL $1" >&2; exit 1; }

check() {
  path="$1"
  # shellcheck disable=SC2086
  body="$(curl -fsS ${CURL_OPTS:-} --retry 10 --retry-delay 2 --retry-connrefused --max-time 5 "$URL$path")" \
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

# Evaluation entry: absent (404) unless EVALUATION_MODE is on; when on, each of the four seats
# signs in without a password and the session resolves to the expected role.
jar="$(mktemp)"; trap 'rm -f "$jar"' EXIT
code="$(curl -sS ${CURL_OPTS:-} -o /dev/null -w '%{http_code}' --max-time 5 -X POST \
  -H 'Content-Type: application/json' -d '{"seat":"trainee"}' "$URL/api/v1/auth/evaluation-login")" \
  || fail "evaluation-login request failed"
case "$code" in
  404)
    [ "${EXPECT_EVALUATION:-false}" = "true" ] && fail "evaluation entry expected but /auth/evaluation-login is 404"
    echo "smoke: ok   evaluation entry off (404)" ;;
  200)
    [ "${EXPECT_EVALUATION:-}" = "false" ] && fail "evaluation entry is on but was expected off"
    for pair in trainee:trainee commander:trainee instructor:instructor admin:admin; do
      seat="${pair%%:*}"; role="${pair##*:}"
      : > "$jar"
      # shellcheck disable=SC2086
      out="$(curl -fsS ${CURL_OPTS:-} --max-time 5 -c "$jar" -X POST -H 'Content-Type: application/json' \
        -d "{\"seat\":\"$seat\"}" "$URL/api/v1/auth/evaluation-login")" || fail "seat $seat did not sign in"
      echo "$out" | grep -q "\"role\":\"$role\"" || fail "seat $seat did not give role $role: $out"
      # shellcheck disable=SC2086
      curl -fsS ${CURL_OPTS:-} --max-time 5 -b "$jar" "$URL/api/v1/auth/me" | grep -q "\"role\":\"$role\"" \
        || fail "seat $seat session did not resolve to $role"
      echo "smoke: ok   evaluation seat $seat ($role)"
    done ;;
  *) fail "/auth/evaluation-login returned $code" ;;
esac
echo "smoke: PASS $URL"
