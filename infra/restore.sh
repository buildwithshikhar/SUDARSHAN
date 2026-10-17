#!/bin/bash
# Restore a backup made by backup.sh: replaces the database contents and the uploads volume.
# Usage: infra/restore.sh <backup-dir> [--yes]
# Stops web and api during the restore, then starts them again (migrations run on start).
set -euo pipefail
# shellcheck source=infra/lib.sh
. "$(dirname "$0")/lib.sh"

src="${1:-}"
[ -n "$src" ] || die "usage: infra/restore.sh <backup-dir> [--yes]"
[ -d "$src" ] || src="$BACKUP_DIR/$src"
[ -f "$src/db.dump" ] && [ -f "$src/uploads.tgz" ] || die "$src does not contain db.dump and uploads.tgz"

if [ "${2:-}" != "--yes" ]; then
  echo "This replaces ALL current data in project '$PROJECT' with the backup in $src."
  read -r -p "Type 'restore' to continue: " answer
  [ "$answer" = "restore" ] || die "cancelled"
fi

say "stopping web and api"
compose stop web api
say "restoring the database"
compose exec -T db pg_restore -U app -d app --clean --if-exists --no-owner < "$src/db.dump"
say "restoring uploads"
compose run --rm --no-deps -T --entrypoint sh api -c \
  'mkdir -p /data/uploads && find /data/uploads -mindepth 1 -delete && tar -xzf - -C /data' < "$src/uploads.tgz"
say "starting the stack"
compose up -d --wait
say "restore complete from $src"
