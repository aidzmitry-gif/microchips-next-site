# Production deployment contour

The base `docker-compose.yml` is a local development and CI topology. For a
server, combine it with `docker-compose.production.yml`. That override binds
Laravel/Nginx and Next only to `127.0.0.1`, restarts long-running services, and
runs database migrations successfully before PHP-FPM and Horizon start.

An external TLS reverse proxy or load balancer is required in front of the two
localhost ports. It owns certificates, redirects HTTP to HTTPS and forwards:

- public storefront domains to `127.0.0.1:${FRONTEND_PORT}`;
- the protected Laravel/Filament endpoint only when an operator explicitly
  needs it, to `127.0.0.1:${BACKEND_PORT}`.

The proxy must overwrite (never pass through) client-supplied
`X-Forwarded-Host` and `X-Forwarded-Proto`. The application deliberately does
not trust every proxy address: the production topology varies by host, while
the session cookie is explicitly marked `Secure` in the production Compose
override.

No certificate, domain, password, or production URL is committed to this
repository.

## Server sequence

1. Copy `deploy/.env.production.example` to a server-local protected file and
   replace every placeholder.
2. Export the file and run `scripts/release-preflight.sh`.
3. Validate the composed configuration:

   ```sh
   docker compose --env-file .env.production -f docker-compose.yml -f docker-compose.production.yml config --quiet
   ```

4. Build and start with the same two compose files. The `migrate` service must
   finish successfully before `backend` and `worker` are eligible to start.
5. Create the first administrator without demo data. Run the command in an
   interactive server shell so the password is not placed in shell history:

   ```sh
   docker compose --env-file .env.production -f docker-compose.yml -f docker-compose.production.yml exec backend \
     php artisan admin:bootstrap owner@example.com
   ```

   The command refuses to run when an administrator already exists and never
   seeds test sites. Sign in at `/admin`, then create each site profile with
   its real domain and country data; do not use `db:seed` on a server.
6. Verify host-based storefront responses, sitemap, redirects, a real lead
   handled in the local inbox, and the SEO release audit before exposing a
   country domain. Bitrix24 is an optional later integration.

## Database backup and restore evidence

The CI restore check proves that PostgreSQL tools work; it is not a production
backup. On the server, choose a host-local directory outside Docker volumes,
for example `/var/backups/microchips/postgres`, owned by the service account
with mode `0700`. Set `POSTGRES_BACKUP_DIR` only in the systemd unit, never in
git or the web application environment.

Install [microchips-postgres-backup.service](../deploy/systemd/microchips-postgres-backup.service)
and [microchips-postgres-backup.timer](../deploy/systemd/microchips-postgres-backup.timer), then enable the timer:

```sh
sudo systemctl daemon-reload
sudo systemctl enable --now microchips-postgres-backup.timer
sudo systemctl list-timers microchips-postgres-backup.timer
```

Each run creates an atomic custom-format dump and SHA-256 manifest. Verify a
stored file—not a newly created temporary dump—before launch and at regular
intervals:

```sh
set -a
. /etc/microchips/microchips.env
set +a
COMPOSE_ENV_FILE=/etc/microchips/microchips.env \
POSTGRES_BACKUP_FILE=/var/backups/microchips/postgres/microchips-microchips-YYYYMMDDTHHMMSSZ.dump \
  ./scripts/verify-postgres-backup-file.sh
```

The environment file supplies the required `POSTGRES_DB` and `POSTGRES_USER`;
`COMPOSE_ENV_FILE` makes the isolated restore use the same protected Compose
configuration as the backup timer. Run this as the `microchips` service user
from the repository working directory, never by copying secrets into shell
history.

Retention, encryption-key management, and a tested off-host replica are
mandatory operational decisions. The repository intentionally does not claim
that a local disk backup survives host loss; record the chosen retention and
off-host destination in server operations evidence before launch.

This is a deployment contour, not authorization to publish a country: regional
legal/commercial data and the launch gates still apply.
