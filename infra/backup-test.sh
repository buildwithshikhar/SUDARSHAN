#!/bin/bash
# Local round-trip test of backup.sh and restore.sh on a throwaway project:
# create data, back up, change and delete data, restore, and verify the original state is back.
# Only the throwaway project (<product>-backuptest) is touched; it is removed at the end.
set -euo pipefail
# shellcheck source=infra/lib.sh
. "$(dirname "$0")/lib.sh"

PROJECT="$PROJECT-backuptest"
ENV_FILE=".env.backuptest"
COMPOSE_FILES="-f infra/docker-compose.yml -f infra/docker-compose.prod.yml"
BACKUP_DIR="$(mktemp -d)"
export PROJECT ENV_FILE COMPOSE_FILES BACKUP_DIR

umask 077
{
  echo "SECRET_KEY=$(rand_hex 32)"
  echo "POSTGRES_PASSWORD=$(rand_hex 16)"
  echo "WEB_PORT=18081"
} > "$ENV_FILE"

cleanup() {
  compose down -v --remove-orphans >/dev/null 2>&1 || true
  rm -f "$ENV_FILE"
  rm -rf "$BACKUP_DIR"
}
trap cleanup EXIT

users() { compose exec -T db psql -U app -d app -tAc "select email from users order by email"; }
password="$(rand_hex 12)"

say "starting a throwaway production stack"
compose up -d --build --wait
EXPECT_ENV=production "$(dirname "$0")/smoke.sh" http://localhost:18081 >/dev/null

say "creating data: one administrator and one upload"
compose exec -T -e NEW_USER_PASSWORD="$password" api \
  python -m app.cli create-user --email keep@backuptest.invalid --role admin >/dev/null
compose exec -T api sh -c 'echo original-upload > /data/uploads/marker.txt'
[ "$(users)" = "keep@backuptest.invalid" ] || die "setup failed: unexpected users"

say "backing up"
backup="$("$(dirname "$0")/backup.sh" | tail -n 1)"
[ -s "$backup/db.dump" ] && [ -s "$backup/uploads.tgz" ] && [ -s "$backup/MANIFEST" ] || die "backup incomplete"

say "damaging the data: add a user, delete the upload, change the marker"
compose exec -T -e NEW_USER_PASSWORD="$password" api \
  python -m app.cli create-user --email extra@backuptest.invalid --role trainee >/dev/null
compose exec -T api sh -c 'rm /data/uploads/marker.txt && echo damaged > /data/uploads/other.txt'
[ "$(users | wc -l | tr -d ' ')" = "2" ] || die "damage step failed"

say "restoring"
"$(dirname "$0")/restore.sh" "$backup" --yes

say "verifying"
[ "$(users)" = "keep@backuptest.invalid" ] || die "users after restore: $(users | tr '\n' ' ')"
[ "$(compose exec -T api cat /data/uploads/marker.txt)" = "original-upload" ] || die "marker not restored"
compose exec -T api test ! -e /data/uploads/other.txt || die "file created after the backup survived the restore"
EXPECT_ENV=production "$(dirname "$0")/smoke.sh" http://localhost:18081 >/dev/null

say "retention: the newest BACKUP_KEEP=2 are kept"
BACKUP_KEEP=2 "$(dirname "$0")/backup.sh" >/dev/null; sleep 1
BACKUP_KEEP=2 "$(dirname "$0")/backup.sh" >/dev/null; sleep 1
BACKUP_KEEP=2 "$(dirname "$0")/backup.sh" >/dev/null
[ "$(ls -1d "$BACKUP_DIR"/*/ | wc -l | tr -d ' ')" = "2" ] || die "retention did not prune to 2"

say "backup-test: PASS"
