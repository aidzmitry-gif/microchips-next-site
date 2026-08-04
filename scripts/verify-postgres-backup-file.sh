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

# Optional, allowlisted evidence that a persisted archive carries application
# rows rather than just an empty schema. These are intentionally constrained
# to an identifier plus a decimal lower bound, never arbitrary SQL.
expected_table="${POSTGRES_BACKUP_EXPECT_TABLE:-}"
expected_min_rows="${POSTGRES_BACKUP_EXPECT_MIN_ROWS:-}"
if [ -n "$expected_table$expected_min_rows" ]; then
  [ -n "$expected_table" ] && [ -n "$expected_min_rows" ] || {
    echo "Set both POSTGRES_BACKUP_EXPECT_TABLE and POSTGRES_BACKUP_EXPECT_MIN_ROWS, or neither." >&2
    exit 2
  }
  case "$expected_table" in
    *[!A-Za-z0-9_]*|"") echo "POSTGRES_BACKUP_EXPECT_TABLE must be a simple relation name." >&2; exit 2 ;;
  esac
  case "$expected_min_rows" in
    *[!0-9]*|"") echo "POSTGRES_BACKUP_EXPECT_MIN_ROWS must be a non-negative integer." >&2; exit 2 ;;
  esac
fi

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

if [ -n "$expected_table" ]; then
  restored_rows="$(compose exec -T -e RESTORE_DB="$restore_db" -e EXPECTED_TABLE="$expected_table" postgres sh -ceu '
    printf '\''select count(*) from :"expected_table";\n'\'' | psql -U "$POSTGRES_USER" -d "$RESTORE_DB" -v expected_table="$EXPECTED_TABLE" -tA
  ')"
  case "$restored_rows" in
    *[!0-9]*|"") echo "Restore verification returned an invalid row count." >&2; exit 1 ;;
  esac
  [ "$restored_rows" -ge "$expected_min_rows" ] || {
    echo "Restore verification failed: expected at least $expected_min_rows row(s) in $expected_table, got $restored_rows." >&2
    exit 1
  }
fi

echo "Stored PostgreSQL backup isolated restore verification passed."
