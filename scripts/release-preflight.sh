#!/bin/sh
set -eu

fail() {
  printf '%s\n' "release preflight failed: $1" >&2
  exit 1
}

require_value() {
  name="$1"
  value=$(printenv "$name" || true)
  [ -n "$value" ] || fail "$name is required"
  case "$value" in
    *replace-with-*|*example*|*changeme*) fail "$name still has a placeholder value" ;;
  esac
}

require_value POSTGRES_PASSWORD
require_value LARAVEL_APP_KEY
require_value NEXT_REVALIDATE_SECRET
require_value LEAD_PROXY_SECRET
require_value DEFAULT_SITE_HOST
require_value PUBLIC_APP_URL

case "$PUBLIC_APP_URL" in
  https://*) ;;
  *) fail "PUBLIC_APP_URL must use https" ;;
esac

PUBLIC_APP_HOST=${PUBLIC_APP_URL#https://}
case "$PUBLIC_APP_HOST" in
  ""|*/*|*\?*|*\#*|*:*|*.test|localhost|*' '*) fail "PUBLIC_APP_URL must be an HTTPS origin with a public hostname and no port" ;;
esac

case "$DEFAULT_SITE_HOST" in
  *.test|localhost|*/*|*:*|*' '*|"") fail "DEFAULT_SITE_HOST must be a public hostname without a port" ;;
esac

[ "$PUBLIC_APP_HOST" = "$DEFAULT_SITE_HOST" ] || fail "PUBLIC_APP_URL host must exactly match DEFAULT_SITE_HOST"

[ "${#NEXT_REVALIDATE_SECRET}" -ge 32 ] || fail "NEXT_REVALIDATE_SECRET must be at least 32 characters"
[ "${#LEAD_PROXY_SECRET}" -ge 32 ] || fail "LEAD_PROXY_SECRET must be at least 32 characters"

printf '%s\n' 'release preflight passed: secrets are present and public URL host matches the deployable site host.'
