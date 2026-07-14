# Microchips Next Site - plan

## Purpose

Create a fast, reliable and SEO-safe replacement storefront for `microchips.by`.

The current Bitrix site remains the production system and the source of current SEO pages and content until the new site passes migration acceptance. 1C is a candidate source for product nomenclature and new products after its data is audited. The current SEO promotion work continues independently in `docs/seo/`.

## Product outcome

The new site must preserve existing organic traffic and improve conversion reliability:

- stable catalog, product pages, filters and lead-request flow;
- a normalized product nomenclature that can merge current Bitrix products and 1C goods without duplicates;
- full control over URLs, metadata, canonical URLs, sitemap, robots and structured data;
- fast server-side rendering and predictable cache invalidation;
- measurable link between SEO work, leads and revenue;
- independent infrastructure with tested backups and monitoring.

## Working boundaries

| Area | Current Bitrix site | New site project |
|---|---|---|
| Production traffic | Receives all traffic until final cutover | Closed from indexing until acceptance |
| Source of catalog structure and content | Source of truth during migration | Read-only import initially |
| Product nomenclature | Partial legacy source | Canonical product model, merged from Bitrix and approved 1C data |
| SEO changes | Continue quick-win and technical work | Reproduce and validate signals before launch |
| Leads/orders | Existing working process | Shadow-test and then switch deliberately |
| Infrastructure | Move to own stable server first | Separate staging and production environments |

Do not rewrite, delete, redirect or change production Bitrix data from the new project during the first stages.

## Proposed architecture

Start as a modular monolith, not microservices:

- storefront: Next.js with server-side rendering;
- backend API and administration: Laravel + Filament;
- database: PostgreSQL;
- cache and queues: Redis + Laravel Queue;
- search: start with PostgreSQL/Meilisearch only when catalog search needs it;
- files: S3-compatible object storage or managed local storage with backups;
- monitoring: uptime checks, error tracking, HTTP 500, database, RAM, disk and backup alerts.

The backend owns domain logic: nomenclature, catalog, attributes, availability presentation, SEO pages, redirects, lead requests, imports and audit events. Next.js must not contain business rules that cannot be executed or tested by the backend.

## Synchronization policy

Synchronization is required, but only for data that exists in Bitrix or is needed for the migration. Bitrix does not contain actual stock or reliable prices, so it is not a source for those fields.

| Object | Direction before launch | Frequency | Rule |
|---|---|---|---|
| Categories, products, attributes and content | Bitrix -> new site | Initial full import, then incremental | Bitrix is authoritative until cutover for these fields only |
| Nomenclature and new goods | 1C -> import staging -> new site | Initial audit, then approved imports | 1C records never publish directly without validation and duplicate checks |
| Actual prices and stock | No synchronization in phase 1 | Not applicable | Do not show invented availability or outdated prices |
| Availability and price presentation | New site administration -> storefront | On approval | Use controlled states: price on request, availability on request, or manually verified value with timestamp |
| Images and documents | Bitrix -> new site | Initial, then incremental | Preserve source mapping and checksums |
| SEO URL, title, H1, description, canonical | Bitrix -> URL registry/new site | Initial snapshot plus approved changes | Never overwrite a manually approved migration mapping silently |
| 301 redirects | URL registry -> new site | Manual approval, versioned | Every old important URL has one final destination |
| Lead requests before cutover | New site -> test destination only | Manual or isolated test flow | Do not duplicate real client requests without consent |
| Lead requests after cutover | New site -> CRM/ERP or email workflow | Real time | Idempotency key prevents duplicate submissions |

The project needs a synchronization journal with: run ID, source time, imported/updated/skipped/failed counts, error samples and rollback point. A sync without a report is not considered successful.

## Catalog and nomenclature redesign

The new catalog is not a technical copy of Bitrix folders. It must be designed around how customers search and choose goods, while preserving existing valuable SEO landing pages and URL equity.

### Canonical product model

Every sellable item needs a stable internal identity independent from a title or category:

| Field | Purpose |
|---|---|
| `product_id` | Immutable ID in the new system |
| `sku` | Internal commercial SKU; unique when available |
| `manufacturer` + `manufacturer_part_number` | Primary duplicate check for electronics and batteries |
| `barcode` | Additional duplicate check when reliable |
| `source_1c_id` / `source_bitrix_id` | Traceability back to each source |
| `product_type` | Battery, accumulator, charger, BMS, holder, component and so on |
| `attributes` | Structured properties used by filters and SEO: voltage, capacity, chemistry, form factor, dimensions, terminal type, application |
| `publication_status` | Draft, needs review, published, archived, duplicate |
| `seo_landing_relation` | Links product to indexable commercial categories without making every filter indexable |

The editor must be able to merge duplicates, split an incorrectly merged record and see the source history. No import should erase an editor-approved title, mapping or SEO decision without an explicit rule.

### Catalog design rules

1. Separate the product taxonomy from SEO landing pages. A customer can filter by voltage or brand, but only demand-backed filters become indexable landing pages.
2. Use structured attributes, not free-text names, for key selection factors such as voltage, capacity, chemistry and form factor.
3. Preserve high-value current URLs where possible. New taxonomy is not a reason to change URLs that already rank.
4. Create one canonical product page per physical item and prevent duplicate cards from Bitrix and 1C imports.
5. Keep unpublished, incomplete and duplicate 1C records out of the public sitemap and search results.
6. Treat category restructuring as an SEO migration: each removed or merged category must have a canonical destination or a single 301 redirect.

### 1C import pipeline

1. Obtain a sample export/API contract and profile actual fields, identifiers, duplicates, empty values and inactive goods.
2. Load 1C data into an import staging area, never directly into public catalog tables.
3. Match against existing records by 1C ID, SKU, manufacturer part number and barcode; send ambiguous cases to review.
4. Normalize units and attributes, for example `12 V` / `12В`, `7 Ah` / `7 Ач`, chemistry and form factor.
5. Validate required fields for a public product card: title, product type, at least one meaningful attribute, image or explicit image exception, and lead-request eligibility.
6. Publish only approved records and record the source/import run for every change.

**Gate:** a 1C sample import produces a review queue, not automatic public products; duplicate rate and required-field completeness are known before mass import.

## Stages and acceptance gates

### Stage 0 - stabilize the current production site

1. Move the current Bitrix production copy to an independent server.
2. Verify restore from backup on a non-production environment.
3. Configure external backups, retention, swap and monitoring.
4. Record production baseline: important URLs, traffic, positions, leads, conversion, server errors.

**Gate:** the Bitrix site is stable, recoverable and monitored. No migration cutover is allowed before this gate.

### Stage 1 - discovery and migration inventory

1. Export catalog structure, products, properties, filters, images and integration points from Bitrix.
2. Obtain and profile a representative 1C export/API: nomenclature, identifiers, groups, attributes, images and lifecycle status.
3. Crawl and classify current URLs: indexable, canonical, redirect, noindex, 404 and filter pages.
4. Create a URL registry: `old_url`, `new_url`, page type, canonical, redirect type, priority, status and owner.
5. Define conversion events: form, phone call, messenger and wholesale request.
6. Define honest storefront states for every product: `price_on_request`, `availability_on_request`, `manual_price`, `manual_availability`, including editor, timestamp and review interval.
7. Freeze a representative SEO baseline by cluster, not only an overall average position.

**Gate:** top commercial URLs and all indexable URL patterns are mapped; data-source ownership is explicit.

### Stage 2 - vertical slice on staging

Build one complete catalog slice, for example one priority battery category:

1. category and filter pages;
2. product cards and product details;
3. normalized product record with Bitrix and 1C source references;
4. SEO fields, canonical rules, schema.org Product/Offer/BreadcrumbList;
5. sitemap and robots generation;
6. lead-request form with CRM or email test delivery;
7. importer, duplicate-review queue and synchronization journal;
8. admin workflow for content, catalog and SEO approvals.

**Gate:** the slice works end to end on staging, including import, SEO validation and a test lead.

### Stage 3 - parallel build and SEO verification

1. Implement the remaining catalog and priority commercial landing pages.
2. Run repeated imports without data loss or duplicates.
3. Compare old and new HTML for the 100-500 most valuable URLs.
4. Validate response status, title, H1, canonical, robots, schema, breadcrumbs, content, images and internal links.
5. Generate and review the final 301 redirect map.
6. Keep the staging site closed from indexing until it is ready.

**Gate:** no P0/P1 SEO or conversion discrepancies remain for priority URLs.

### Stage 4 - controlled launch

1. Back up Bitrix, database, files and DNS settings.
2. Perform final data import and pause non-essential content changes.
3. Lower DNS TTL in advance and switch traffic in a planned window.
4. Enable 301 redirects, sitemap and monitoring.
5. Keep a documented rollback path to Bitrix.
6. Check HTTP status, forms, CRM/email delivery, canonical URLs and server logs immediately after launch.

**Gate:** the new site serves production traffic with no critical errors; rollback remains possible during the observation period.

### Stage 5 - post-launch protection

1. Monitor daily for 14 days: crawl errors, 404s, redirect chains, indexing, impressions, rankings, leads, conversion and server health.
2. Compare affected keyword clusters against the baseline at 2, 4 and 8 weeks.
3. Fix regression patterns before adding major new functionality.
4. Only then retire old production infrastructure according to a retained backup policy.

## SEO workstream coordination

Current SEO work is not paused because of the new project.

| Current-site action | What the new project must inherit |
|---|---|
| SmartSEO quick-win landing pages | Approved title/H1/text/FAQ, internal links and implementation date |
| Sitemap repair | Sitemap inclusion rules and meaningful `lastmod` policy |
| CR2032 and facet canonicalization | Canonical and noindex rules in the URL registry |
| Topvisor checks | Baseline clusters and before/after dates |
| Lead tracking | One event dictionary for Bitrix and the new site |

Every approved SEO change on Bitrix must be entered into the URL registry or migration changelog within one working day. Otherwise the new site can accidentally recreate an already fixed problem.

## First 10 working days

| Days | Outcome |
|---|---|
| 1-2 | Confirm infrastructure ownership, data sources, catalog scope, integrations, conversion events and access to a 1C sample |
| 3-4 | Profile Bitrix and 1C nomenclature; build the initial URL registry and duplicate-matching rules |
| 5-6 | Define the normalized product model, import contract, review queue and synchronization journal |
| 7-8 | Create one vertical slice on staging: category, merged product record, SEO, lead form and admin |
| 9 | Import real read-only Bitrix and 1C samples; run duplicate, SEO and conversion checks |
| 10 | Demo, gap list, estimate for the full migration and go/no-go decision |

This is a feasibility prototype, not a production replacement in 10 days.

## Definition of ready for cutover

- verified backup restore and rollback procedure;
- 100% mapping for priority URLs and URL patterns;
- no accidental `200` pages for removed content; redirects are single-hop where possible;
- catalog, images and leads are synchronized with an auditable report; 1C imports use duplicate review; price and availability states are honest and auditable;
- SEO output is validated automatically and manually for priority URLs;
- conversion tracking and CRM delivery are verified;
- production monitoring and on-call ownership are defined;
- a launch decision is approved using real staging evidence, not a visual demo.

## Decisions still required

1. Provide a representative 1C export or API description, including identifiers and item lifecycle fields.
2. Confirm the duplicate rule hierarchy: 1C ID, SKU, manufacturer part number, barcode and manual review.
3. Confirm who maintains manually verified price and availability states, and how often they are reviewed.
4. Confirm that the first release is lead generation only, without an online checkout or payment.
5. Confirm the target infrastructure provider and who has root-level operational ownership.
6. Select the first catalog vertical slice based on commercial value and current SEO quick-wins.
7. Decide the planned maximum acceptable temporary SEO/lead impact during launch; the recommended target is zero unplanned downtime and no intentional deindexing of production URLs.
