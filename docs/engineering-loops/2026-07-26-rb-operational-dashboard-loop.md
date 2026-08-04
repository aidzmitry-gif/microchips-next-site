# RB operational dashboard and release boundary

Date: 2026-07-26.

## Delivered local monitoring surface

The Filament dashboard now discovers `RbOperationalReadinessWidget`. It displays live local metrics for the RB site profile:

- non-public catalog drafts, category links and public-card count;
- unresolved duplicate conflicts;
- local-inbox leads awaiting handling;
- unpublished regional content drafts and indexable URL count.

The widget is intentionally a measurement surface, not a readiness score or a release toggle.

## Current local release evidence

`seo:audit microchips-by --json` passes the configured local checks. `site:launch-preflight microchips-by --json` correctly blocks the release with `INDEXABLE_URL_MISSING`; it does not claim that local data equals a public launch.

The launch-page draft import is idempotent: the four RB commercial pages already existed as noindex drafts and remained unchanged on both dry-run and apply. The database now contains five RB pages in total, one pre-existing published page, and zero indexable page URLs.

A dedicated QA lead (no customer data, clearly marked as a local-inbox test) was created for RB and handled by the existing administrator through `new → in_progress → closed`. Its closing note records that no customer contact is required. This is evidence of the local inbox lifecycle only; it does not represent a production customer conversion.

## Still external, therefore not credited

- public staging DNS/TLS plus external crawl;
- separate analytics, Google Search Console and Yandex Webmaster properties;
- approved redirect cutover and 14-day observation.

These are not simulated locally. They are the remaining evidence needed to credit RB monitoring/release readiness and to raise the overall verified score beyond 54.0%.
