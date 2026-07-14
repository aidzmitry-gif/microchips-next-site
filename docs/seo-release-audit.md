# SEO release audit

`php artisan seo:audit {site}` is a read-only release gate for a site profile. It
does not crawl a public domain and does not create, update or publish any data.

Run it before a deploy that changes public URLs, SEO records, redirects, locales
or sitemap data:

```powershell
php artisan seo:audit microchips-by
php artisan seo:audit microchips.by --json
```

The command exits with `0` only if there are no blockers. Exit `1` blocks a
release; `2` means that the requested site key or domain was not found. The JSON
mode is intended for CI artifacts and never writes a report file by itself.

## Blockers

- Every indexable URL must resolve to a published resource, be locally
  canonicalized to its own normalized path, and not also be a redirect source.
- A canonical containing a host, query, fragment or a different path is blocked.
  This prevents cross-country canonicals such as a Belarus page canonicalized to
  a Russian domain.
- Sitemap output excludes and the audit blocks query URLs and route segments for
  filters, search, sort, baskets, cart, compare and personal area. This follows
  the source audit finding that 5,089 Aspro filter/SEO URLs require individual
  classification, not automatic indexation.
- Every `hreflang` alternate must reference enabled locales, indexable local URLs
  and have a reciprocal edge back to the source URL.
- Active redirects must use normalized same-site paths and status `301` or `308`.
  Chains, missing targets and redirects to the home page are blockers. This is
  specifically required before importing any of the 5,471 legacy 301 entries.

The audit is a guardrail for data already approved in the new platform. It does
not replace the source URL registry or a production crawl required for the
Belarus migration.
