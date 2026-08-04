#!/bin/sh
set -eu

# Local evidence runner for the existing backup/restore scripts. It deliberately
# creates a disposable archive outside the repository and verifies an isolated
# temporary database; the working database is never restored over or modified.
: "${POSTGRES_DB:?POSTGRES_DB is required}"
: "${POSTGRES_USER:?POSTGRES_USER is required}"

# The production backup creator intentionally rejects /tmp; use /var/tmp by
# default so this runner exercises precisely the same safety checks.
backup_root="${MICROCHIPS_BACKUP_VERIFY_TMPDIR:-/var/tmp}"
backup_dir="$(mktemp -d "$backup_root/microchips-backup-verify.XXXXXX")"
cleanup() {
  rm -rf "$backup_dir"
}
trap cleanup EXIT HUP INT TERM

POSTGRES_BACKUP_DIR="$backup_dir" \
  ./scripts/create-postgres-backup.sh

backup_file="$(find "$backup_dir" -type f -name '*.dump' -print -quit)"
test -n "$backup_file"

POSTGRES_BACKUP_FILE="$backup_file" \
POSTGRES_BACKUP_EXPECT_TABLE=users \
POSTGRES_BACKUP_EXPECT_MIN_ROWS=1 \
  ./scripts/verify-postgres-backup-file.sh

echo "Local PostgreSQL backup/restore verification passed."
