#!/bin/sh
set -eu
umask 077

compose() {
  if [ -n "${COMPOSE_ENV_FILE:-}" ]; then
    docker compose --env-file "$COMPOSE_ENV_FILE" "$@"
  else
    docker compose "$@"
  fi
}

: "${POSTGRES_DB:?POSTGRES_DB is required}"
: "${POSTGRES_USER:?POSTGRES_USER is required}"
: "${POSTGRES_BACKUP_FILE:?POSTGRES_BACKUP_FILE is required}"

case "$POSTGRES_BACKUP_FILE" in
  /*) ;;
  *) echo "POSTGRES_BACKUP_FILE must be an absolute host path." >&2; exit 2 ;;
esac
[ -f "$POSTGRES_BACKUP_FILE" ] || { echo "Backup file does not exist." >&2; exit 2; }
[ -s "$POSTGRES_BACKUP_FILE" ] || { echo "Backup file is empty." >&2; exit 2; }

name_bytes="$(LC_ALL=C printf '%s' "$POSTGRES_DB" | wc -c | tr -d ' ')"
[ "$name_bytes" -le 36 ] || { echo "POSTGRES_DB must be at most 36 bytes for this restore check." >&2; exit 2; }

restore_db="${POSTGRES_DB}_restore_verify_$$"
archive_file="/tmp/microchips-restore-verify-$$.dump"

cleanup() {
  compose exec -T -e RESTORE_DB="$restore_db" -e ARCHIVE_FILE="$archive_file" postgres sh -ceu '
    dropdb -U "$POSTGRES_USER" --if-exists "$RESTORE_DB" >/dev/null 2>&1 || true
    rm -f "$ARCHIVE_FILE"
  ' || true
}
trap cleanup EXIT HUP INT TERM

cat "$POSTGRES_BACKUP_FILE" | compose exec -T -e ARCHIVE_FILE="$archive_file" postgres sh -ceu '
  umask 077
  cat > "$ARCHIVE_FILE"
'

compose exec -T -e RESTORE_DB="$restore_db" -e ARCHIVE_FILE="$archive_file" postgres sh -ceu '
  dropdb -U "$POSTGRES_USER" --if-exists "$RESTORE_DB"
  createdb -U "$POSTGRES_USER" "$RESTORE_DB"
  pg_restore -U "$POSTGRES_USER" -d "$RESTORE_DB" --exit-on-error "$ARCHIVE_FILE"
  test "$(psql -U "$POSTGRES_USER" -d "$RESTORE_DB" -tAc "select to_regclass('"'"'public.migrations'"'"')")" = migrations
'

echo "Stored PostgreSQL backup isolated restore verification passed."
