#!/bin/bash
# Builds the production images, starts the production-mode stack on a throwaway project, and
# checks it: smoke, page load, admin bootstrap, demo-account refusal, cookie flags, CSRF, HTTPS
# through Caddy on a local domain, and memory use. Only the throwaway project
# (<product>-prodcheck) is touched; it is removed at the end. Results of the memory measurement
# are written to build/prod-check-memory.txt.
set -euo pipefail
# shellcheck source=infra/lib.sh
. "$(dirname "$0")/lib.sh"

PROJECT="$PROJECT-prodcheck"
ENV_FILE=".env.prodcheck"
COMPOSE_FILES="-f infra/docker-compose.yml -f infra/docker-compose.prod.yml"
export PROJECT ENV_FILE COMPOSE_FILES
here="$(dirname "$0")"
admin_email="ops@prodcheck.invalid"
admin_password="$(rand_hex 16)"
mkdir -p build

umask 077
{
  echo "SECRET_KEY=$(rand_hex 32)"
  echo "POSTGRES_PASSWORD=$(rand_hex 16)"
  echo "WEB_PORT=18080"
  echo "FIRST_ADMIN_EMAIL=$admin_email"
  echo "FIRST_ADMIN_PASSWORD=$admin_password"
} > "$ENV_FILE"

cleanup() {
  COMPOSE_FILES="-f infra/docker-compose.yml -f infra/docker-compose.prod.yml -f infra/docker-compose.https.yml" \
    DOMAIN=localhost ACME_EMAIL=x@prodcheck.invalid compose down -v --remove-orphans >/dev/null 2>&1 || true
  rm -f "$ENV_FILE" .deploy/cookiejar
}
trap cleanup EXIT

base=http://localhost:18080

say "building and starting the production stack"
compose up -d --build --wait

say "smoke and page load (production mode)"
EXPECT_ENV=production "$here/smoke.sh" "$base"
EXPECT_ENV=production "$here/check-deploy.sh" "$base" >/dev/null && echo "prod-check: page load ok"

say "admin bootstrap is idempotent; demo seeding is refused"
compose exec -T api python -m app.cli create-admin | grep -q "exists: $admin_email"
if compose exec -T api python -m app.cli seed-demo >/dev/null 2>&1; then die "seed-demo ran in production"; fi

say "the API image carries the sim core and the packs (Q-19)"
compose exec -T api python -m app.cli sim-check | grep -q '^sim ok: ' || die "sim-check failed in the API image"

say "sign-in, cookie flags and CSRF"
mkdir -p .deploy
jar=.deploy/cookiejar
login() { curl -sS -o /dev/null -w '%{http_code}' -c "$jar" -D .deploy/headers -H 'Content-Type: application/json' \
  -d "{\"email\":\"$admin_email\",\"password\":\"$1\"}" "$base/api/v1/auth/login"; }
[ "$(login "wrong-password-here")" = "401" ] || die "wrong password was not refused"
[ "$(login "$admin_password")" = "200" ] || die "the bootstrapped administrator cannot sign in"
grep -qi 'set-cookie: session=.*HttpOnly' .deploy/headers || die "session cookie is not HttpOnly"
grep -qi 'set-cookie: session=.*Secure' .deploy/headers || die "session cookie is not Secure in production"
[ "$(curl -sS -o /dev/null -w '%{http_code}' -b "$jar" -X POST "$base/api/v1/auth/logout")" = "403" ] || die "logout without CSRF token was accepted"
rm -f .deploy/headers

say "terrain packs are served, and the CSP lets the 3D scene read its textures"
for pack in heron-ridge osprey-town; do
  [ "$(curl -sS -o /dev/null -w '%{http_code}' -b "$jar" "$base/api/v1/terrain/$pack/manifest.json")" = "200" ] || die "terrain pack $pack is not served"
done
[ "$(curl -sS -o /dev/null -w '%{http_code}' "$base/api/v1/terrain/heron-ridge/manifest.json")" = "401" ] || die "terrain files are served without signing in"
csp="$(curl -sSI "$base/" | grep -i '^content-security-policy:')"
echo "$csp" | grep -q "connect-src 'self' blob:" || die "CSP connect-src does not allow blob: (glTF textures)"
echo "$csp" | grep -q "img-src 'self' data: blob:" || die "CSP img-src does not allow blob:"

measure() {
  local label="$1" ids
  ids="$(compose ps -q)"
  echo "--- $label"
  # shellcheck disable=SC2086
  docker stats --no-stream --format 'table {{.Name}}\t{{.MemUsage}}\t{{.MemPerc}}\t{{.CPUPerc}}' $ids
  # shellcheck disable=SC2086
  docker stats --no-stream --format '{{.MemUsage}}' $ids | python3 -c '
import re, sys
total = 0.0
for line in sys.stdin:
    used = line.split("/")[0].strip()
    m = re.match(r"([0-9.]+)\s*([KMG]i?B)", used)
    if m:
        scale = {"KiB": 1 / 1024, "MiB": 1, "GiB": 1024, "KB": 1 / 1000, "MB": 1, "GB": 1000}[m.group(2)]
        total += float(m.group(1)) * scale
print(f"total of listed containers: {total:.0f} MiB")'
}

{
  echo "Local measurement, not a benchmark of any cloud VM."
  echo "date_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ) commit=$GIT_SHA"
  docker info --format 'docker_server={{.ServerVersion}} cpus={{.NCPU}} vm_memory_bytes={{.MemTotal}} arch={{.Architecture}} os={{.OperatingSystem}}'
  measure "production stack: idle, just after start and checks"
} | tee build/prod-check-memory.txt

say "light load: 150 page loads, 150 version calls, 10 sign-ins"
for _ in $(seq 1 150); do
  curl -sS -o /dev/null "$base/"
  curl -sS -o /dev/null "$base/api/v1/version"
done
for _ in $(seq 1 10); do login "$admin_password" >/dev/null; done
measure "production stack: after light load" | tee -a build/prod-check-memory.txt

say "HTTPS through Caddy on a local domain"
https_env="DOMAIN=localhost ACME_EMAIL=$admin_email HTTP_PORT=18079 HTTPS_PORT=18443"
{
  echo "DOMAIN=localhost"
  echo "ACME_EMAIL=$admin_email"
  echo "HTTP_PORT=18079"
  echo "HTTPS_PORT=18443"
} >> "$ENV_FILE"
COMPOSE_FILES="-f infra/docker-compose.yml -f infra/docker-compose.prod.yml -f infra/docker-compose.https.yml" \
  compose up -d --wait
# the first request may race Caddy's internal certificate issuance
for _ in $(seq 1 30); do
  curl -sSk --max-time 3 -o /dev/null "https://localhost:18443/healthz" 2>/dev/null && break
  sleep 1
done
CURL_OPTS=-k EXPECT_ENV=production "$here/check-deploy.sh" https://localhost:18443 >/dev/null && echo "prod-check: HTTPS page load ok"
curl -sSk -D - -o /dev/null "https://localhost:18443/" | grep -qi '^strict-transport-security:' || die "no HSTS header over HTTPS"
code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 5 "http://localhost:18079/healthz" || true)"
case "$code" in 301|302|307|308) echo "prod-check: HTTP redirects to HTTPS ($code)" ;; *) die "HTTP did not redirect to HTTPS (got $code)" ;; esac
{
  COMPOSE_FILES="-f infra/docker-compose.yml -f infra/docker-compose.prod.yml -f infra/docker-compose.https.yml" \
    measure "production stack plus Caddy (HTTPS)"
} | tee -a build/prod-check-memory.txt

say "prod-check: PASS (memory table in build/prod-check-memory.txt)"
