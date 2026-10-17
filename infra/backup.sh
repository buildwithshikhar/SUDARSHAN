#!/bin/bash
# Back up the database and the uploads volume of the running stack.
# Usage: infra/backup.sh            -> writes $BACKUP_DIR/<UTC timestamp>/ and prints its path
# Keeps the newest $BACKUP_KEEP backups (default 14). Files are readable only by the current user.
set -euo pipefail
# shellcheck source=infra/lib.sh
. "$(dirname "$0")/lib.sh"

stamp="$(date -u +%Y%m%dT%H%M%SZ)"
dest="$BACKUP_DIR/$stamp"
umask 077
mkdir -p "$dest"

say "dumping the database"
compose exec -T db pg_dump -U app -d app --format=custom > "$dest/db.dump"
say "archiving uploads"
compose exec -T api tar -C /data -czf - uploads > "$dest/uploads.tgz"

[ -s "$dest/db.dump" ] || die "database dump is empty; backup discarded"
[ -s "$dest/uploads.tgz" ] || die "uploads archive is empty; backup discarded"

{
  echo "created_utc=$stamp"
  echo "commit=$(git rev-parse HEAD 2>/dev/null || echo unknown)"
  echo "project=$PROJECT"
  ( cd "$dest" && shasum -a 256 db.dump uploads.tgz 2>/dev/null || sha256sum db.dump uploads.tgz )
} > "$dest/MANIFEST"

# prune: keep the newest $BACKUP_KEEP directories (portable: no GNU-only head/ls options)
# shellcheck disable=SC2012
ls -1d "$BACKUP_DIR"/*/ 2>/dev/null | sort \
  | awk -v keep="$BACKUP_KEEP" '{ a[NR] = $0 } END { for (i = 1; i <= NR - keep; i++) print a[i] }' \
  | while read -r old; do rm -rf "$old"; done

say "backup written to $dest"
echo "$dest"
