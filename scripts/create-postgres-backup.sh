#!/bin/sh
set -eu
umask 077

: "${POSTGRES_DB:?POSTGRES_DB is required}"
: "${POSTGRES_USER:?POSTGRES_USER is required}"
: "${POSTGRES_BACKUP_DIR:?POSTGRES_BACKUP_DIR must be an absolute host directory}"

case "$POSTGRES_BACKUP_DIR" in
  /|/tmp|/tmp/*|*postgres-data*|*'..'*)
    echo "Refusing unsafe POSTGRES_BACKUP_DIR." >&2
    exit 2
    ;;
  /*) ;;
  *)
    echo "POSTGRES_BACKUP_DIR must be an absolute host directory." >&2
    exit 2
    ;;
esac

mkdir -p "$POSTGRES_BACKUP_DIR"
chmod 700 "$POSTGRES_BACKUP_DIR"

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
base="microchips-${POSTGRES_DB}-${timestamp}"
destination="$POSTGRES_BACKUP_DIR/$base.dump"
manifest="$POSTGRES_BACKUP_DIR/$base.sha256"
temporary="$(mktemp "$POSTGRES_BACKUP_DIR/.${base}.XXXXXX")"
manifest_temporary=""

cleanup() {
  rm -f "$temporary"
  [ -z "$manifest_temporary" ] || rm -f "$manifest_temporary"
}
trap cleanup EXIT HUP INT TERM

docker compose exec -T postgres pg_dump \
  -U "$POSTGRES_USER" \
  -d "$POSTGRES_DB" \
  --format=custom > "$temporary"

[ -s "$temporary" ] || { echo "PostgreSQL dump is empty." >&2; exit 1; }
cat "$temporary" | docker compose exec -T postgres sh -ceu '
  archive="$(mktemp)"
  cat > "$archive"
  if pg_restore --list "$archive" >/dev/null; then
    rm -f "$archive"
  else
    rm -f "$archive"
    exit 1
  fi
'

mv "$temporary" "$destination"
manifest_temporary="$(mktemp "$POSTGRES_BACKUP_DIR/.${base}.sha256.XXXXXX")"
if command -v sha256sum >/dev/null 2>&1; then
  (cd "$POSTGRES_BACKUP_DIR" && sha256sum "$base.dump") > "$manifest_temporary"
else
  (cd "$POSTGRES_BACKUP_DIR" && shasum -a 256 "$base.dump") > "$manifest_temporary"
fi
mv "$manifest_temporary" "$manifest"
manifest_temporary=""

echo "Backup created: $destination"
