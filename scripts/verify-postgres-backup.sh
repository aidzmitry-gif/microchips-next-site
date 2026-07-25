#!/bin/sh
set -eu
umask 077

db_name_bytes="$(LC_ALL=C printf '%s' "$POSTGRES_DB" | wc -c | tr -d ' ')"
if [ "$db_name_bytes" -gt 40 ]; then
    echo "POSTGRES_DB must be at most 40 bytes for an isolated restore check." >&2
    exit 2
fi

restore_db="${POSTGRES_DB}_restore_check_$$"
backup_file="/tmp/microchips-restore-check-$$.dump"

if [ "$restore_db" = "$POSTGRES_DB" ]; then
    echo "Refusing an unsafe restore database name." >&2
    exit 2
fi

cleanup() {
    dropdb -U "$POSTGRES_USER" --if-exists "$restore_db" >/dev/null 2>&1 || true
    rm -f "$backup_file"
}
trap cleanup EXIT

pg_dump \
    -U "$POSTGRES_USER" \
    -d "$POSTGRES_DB" \
    --format=custom \
    --file="$backup_file"

dropdb -U "$POSTGRES_USER" --if-exists "$restore_db"
createdb -U "$POSTGRES_USER" "$restore_db"
pg_restore \
    -U "$POSTGRES_USER" \
    -d "$restore_db" \
    --exit-on-error \
    "$backup_file"

restored_relation="$(
    psql \
        -U "$POSTGRES_USER" \
        -d "$restore_db" \
        -tAc "select to_regclass('public.migrations')"
)"

if [ "$restored_relation" != "migrations" ]; then
    echo "Restore verification failed: migrations table was not restored." >&2
    exit 1
fi

echo "PostgreSQL backup and isolated restore verification passed."
