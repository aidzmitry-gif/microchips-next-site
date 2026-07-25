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
5. Verify host-based storefront responses, sitemap, redirects, a real lead in
   Bitrix24, and the SEO release audit before exposing a country domain.

This is a deployment contour, not authorization to publish a country: regional
legal/commercial data and the launch gates still apply.
