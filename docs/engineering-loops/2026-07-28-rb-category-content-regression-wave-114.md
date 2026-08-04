# RB category content regression wave 114 — 2026-07-28

## Outcome

Restored market-specific introductions for five published RB category previews
whose `site_seos.description` values were missing in the current database, and
added reviewed introductions for two additional published categories. The
operation did not enable indexation or alter any canonical URL.

## Applied categories

- `seo:industrial-batteries`
- `seo:batteries-ups`
- `seo:batteries-industrial`
- `seo:batteries-traction`
- `seo:power-systems`
- `seo:ups-systems`
- `seo:replacement-batteries`

Source manifest:
`docs/imports/rb-site-category-content-wave-114-2026-07-28.json`.

The copy is written as buyer guidance: application, voltage, capacity or
power, discharge mode, dimensions, terminals, topology, compatibility and
other selection constraints. It does not add unsupported availability,
warranty or commercial claims.

## Verification

- JSON parsed successfully: 7 unique records; descriptions contain 361–408
  characters.
- Import dry run: 7 updates, 0 indexability changes.
- Apply: 7 updates, 0 indexability changes.
- Idempotency dry run: 0 updates, 7 unchanged.
- Database check: all 7 descriptions are non-empty; SEO and URL records remain
  `is_indexable=false`; every canonical path exactly equals its URL path.
- Browser SSR check on four representative pages: HTTP content rendered, one
  H1, exact canonical, `noindex, nofollow`, reviewed description visible, no
  404 marker and no horizontal overflow.
- `php artisan seo:audit microchips-by --json`: PASS, 118 URLs checked, 0
  blocking issues.

## Readiness effect

This closes a current-state content regression and improves category-page
quality, but it does not increase strict product completion. Product readiness
remains 44 of 7,286 (`0.60%`) because that metric still requires verified
identity, description, price policy, media and storefront QA per product.
