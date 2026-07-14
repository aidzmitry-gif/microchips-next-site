# Read-only audit: Bitrix source snapshot

Audit date: 2026-07-14. Source: `D:\6 Проекты\microchips.by`. This is a point-in-time snapshot made on 2026-06-23, not proof of current production state.

## Source integrity

The backup is a complete component set, not one monolithic archive:

| Component | Evidence | Use in migration |
| --- | --- | --- |
| Database | `db/user_microchips_data.sql.gz` | Catalog, URLs, properties, SEO, orders and source IDs. |
| Custom code | `microchips_code_20260623.tar.gz` | Aspro templates, components and custom business logic. |
| Bitrix kernel | `microchips_bitrix-kernel_20260623.tar.gz` | Read-only reference only; it is not a migration target. |
| Media | `microchips_upload_20260623.tar` | Product images and documents. |
| Public front | `microchips_fronts_20260623.tar.gz` | Public routes, crawl controls, sitemaps and `.htaccess`. |

The existing Docker guide describes a local Apache/PHP 8.2/MariaDB 10.11 sandbox. The audit did not start it and did not alter a database, archive or production service.

## Catalog evidence

The source is Bitrix + Aspro Max. It contains two active catalog infoblocks that must be reconciled rather than blindly merged.

| Infoblock | Active products | Inactive products | Active sections | Role |
| ---: | ---: | ---: | ---: | --- |
| 26 | 17,189 | 18 | 501 | Main public catalogue; referenced by the main sitemap. |
| 65 | 3,920 | 5 | 44 | Secondary catalogue; source ownership needs confirmation. |

The primary catalogue is organized as follows (product count uses a product's primary section):

| Root category | Active products |
| --- | ---: |
| Аккумуляторы | 13,165 |
| Батарейки | 1,630 |
| Аккумуляторные батарейки | 1,080 |
| Источники питания | 687 |
| Микроэлектроника | 295 |
| Зарядные устройства | 284 |

The first B2B vertical should be `Аккумуляторы → Промышленные аккумуляторы / Для ИБП`. It is part of the largest commercial cluster and matches the planned industrial positioning.

Available filterable properties in the main catalogue: capacity in Ah/mAh, brand relation, use case, marketing offer, popularity, technology and form factor. The new model must normalize these fields before any indexable landing page is published.

## URL and SEO evidence

- Product URLs follow `/catalog/#SECTION_CODE_PATH#/#ELEMENT_ID#/`. Preserve the numeric Bitrix element ID in the migration registry; it is a reliable legacy identity even if the new public slug changes.
- `sitemap-iblock-26.xml` contains **17,707** URLs. This is consistent with products and catalogue sections.
- `aspro-sitemap/sitemap-1.xml` contains **5,089** additional URLs, including parameter-free filter/SEO landing candidates such as voltage pages. They must be individually classified, not mass-indexed on the new site.
- The root sitemap references timestamps from 2024 and 2025 even though the snapshot is from 2026. Generate `lastmod` from approved content changes on the new platform; do not copy those values.
- The existing `robots.txt` blocks query URLs, filters, sortings, search, baskets and personal area. These are useful intent signals, but the final rules must be tested against the new URL design.
- `.htaccess` is about 1 MB and contains **5,471** explicit `Redirect`/`RedirectMatch` 301 directives, of which **5,469** begin with `/catalog/`. It also has structural canonical redirects for trailing slash, non-www and `index.php`.
- `.htaccess` also contains 430 User-Agent blocking directives. Do not transfer this legacy crawler blocklist to the new site without a security review; it can block useful SEO tooling and AI crawlers.

## Migration decisions already fixed

| Legacy source | New-platform handling |
| --- | --- |
| Main catalogue (iblock 26) | Import to shared `products` staging; publish only after site-specific review. |
| Second catalogue (iblock 65) | Keep segregated until its business role and duplicate rate are confirmed. |
| `b_iblock_*_iprop` metadata tables | Import as source SEO evidence; never silently overwrite an approved new SEO record. |
| Main sitemap URLs | Start the `keep/fix/redirect/remove` registry from these URLs. |
| Aspro sitemap landing pages | Mark as `seo_landing_candidate`; require demand, unique content and commercial value. |
| 5,471 old 301 directives | Extract as `needs_review`; preserve only valid single-hop mappings. |
| Robots and `.htaccess` rules | Reimplement intentionally in Laravel/Next.js; never copy the files verbatim. |

## Generated raw inventories

Run the following from the new project root:

```powershell
.\scripts\export-bitrix-audit-inventory.ps1 -SourceRoot "D:\6 Проекты\microchips.by"
```

It generates ignored local files in `docs/audits/generated/`:

- `legacy-url-inventory.csv` — 22,796 sitemap URL candidates with an empty decision column;
- `legacy-redirect-source.csv` — 5,471 source redirects for review;
- `summary.json` — reproducible counts.

The files are intentionally not committed: they are large raw source material and have not yet passed SEO classification.

## Release blockers

1. Build a current production crawl and compare it with the 2026-06-23 snapshot.
2. Classify all priority URLs and all URL patterns as `keep`, `fix`, `redirect` or `remove`.
3. Reconcile infoblock 26 and 65 by external IDs, SKU/MPN, manufacturer and manual duplicate review.
4. Extract and test each old redirect against its final destination; reject redirect chains and homepage fallbacks.
5. Verify actual legal/commercial data for Belarus before any page can become indexable.
