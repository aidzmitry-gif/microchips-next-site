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

## Legacy migration decision gate

`App\Domain\Seo\LegacyUrlMigrationDecisionAuditor` is a separate read-only
regression gate for rows of the legacy URL registry. It does not read a
database, crawl a domain, or invoke PowerShell. The registry import or CI job
passes the CSV rows to `audit('microchips.by', $rows)` and must block release
when `passed` is `false`.

The mandatory CSV fields are:

| Field | Allowed values / meaning |
| --- | --- |
| `legacy_url` | Normalized local path or absolute URL on the site being migrated. |
| `decision` | `keep`, `fix`, `redirect`, or `remove`. |
| `review_status` | `approved`, `needs_review`, or `blocked`. Priority rows require `approved`. |
| `destination_url` | Nullable. Required for `fix` and `redirect`; absent for `remove`; `keep` retains `legacy_url` when omitted. |
| `expected_status` | Nullable planned response status. `keep`/`fix` may only use `200`; redirects may only use `301`/`308`; removes may only use `404`/`410`. |
| `canonical_url` | Nullable. For `keep`/`fix`, it must be a self-canonical local URL; redirects and removes must not emit one. |

`priority` is an optional boolean CSV field. A priority row with
`needs_review`, `blocked`, or an invalid review status is a release blocker;
non-priority unresolved rows are returned as warnings and cannot be silently
promoted to priority.

The preliminary output of `build-legacy-url-decision-registry.ps1` is not this
approved manifest. It intentionally uses source-evidence fields such as
`old_url`, `legacy_target_raw` and an empty `final_url`; an explicit owner
review must map it to the fields above and set `review_status=approved` before
this auditor is invoked. This separation prevents a legacy `.htaccess` target
from becoming a new redirect destination by accident.

The gate rejects redirect chains, home-page fallbacks, duplicate redirect
sources, non-permanent redirects, cross-site or external destinations,
cross-country canonicals, and a `remove` decision that plans an HTTP `200`.
It validates the proposed migration manifest; the deploy-time
`seo:audit {site}` gate remains responsible for validating the actual new-site
URLs, canonicals, sitemap, and active redirects.
