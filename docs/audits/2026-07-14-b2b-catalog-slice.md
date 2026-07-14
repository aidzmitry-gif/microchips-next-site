# Read-only B2B catalog slice: industrial batteries and UPS

Audit date: 2026-07-14. Source snapshot: `D:\6 Проекты\microchips.by`, made on 2026-06-23. This is migration evidence only; it is neither a live stock feed nor authority to publish a product in Belarus, Russia, Uzbekistan or another market.

## Purpose and safety boundary

The first commercial slice is `Аккумуляторы → Промышленные аккумуляторы / Для ИБП`. It matches the initial HTML prototype and gives the project a focused B2B catalogue to validate before importing the whole source.

The extractor does all of the following locally and read-only:

- reads `db/user_microchips_data.sql.gz` through .NET `GzipStream`;
- never starts MariaDB, Docker, Bitrix, a network client, Laravel, or a publisher;
- writes only ignored review artifacts under `docs/audits/generated/`;
- retains legacy infoblock, section and element IDs for the URL/SEO registry;
- leaves every extracted row with `needs_review` status.
- verifies the exact `CREATE TABLE` column order and every tuple width before
  reading positional values;
- recognises an INSERT terminator only outside quoted SQL text, so a semicolon
  inside a product value cannot truncate a table silently;
- counts offer infoblocks 28/67 and blocks a catalogue-only result if an offer
  is present.

It explicitly fails before writing if the SQL gzip file cannot be found or no UPS/industrial source section is detected. `-WhatIf` parses the snapshot but writes nothing.

## Verified run: 2026-07-14

The earlier baseline parser self-test, full `-WhatIf` and a local ignored
export completed successfully. The hardened parser self-test also passes,
including the multiline statement state, semicolon-in-a-string and schema-drift
cases. A hardened full `-WhatIf` completed all five passes and intentionally
blocked export: infoblocks 28/67 contain 12 active offer elements, define two
`CML2_LINK` properties, and the current parser found zero links from those
offers to the 26/65 parent set. No artifact was written. This is a reconciliation
blocker, not evidence that the offers can be ignored.

| Measure | Verified result |
| --- | ---: |
| Direct source sections selected by keyword | 6 (three in each infoblock) |
| Selected sections including descendants | 219 |
| Product candidates | 2,856 |
| Active snapshot records | 2,849 |
| Inactive snapshot records | 7 |
| Candidates from infoblock 26 | 2,856 |
| Candidates from infoblock 65 | 0 |
| Raw property values retained | 43,967 |
| Records without media file reference | 4 |
| Records without an article/SKU/MPN property value | 2,856 |
| Records without detected capacity property | 1,500 |
| Records without detected voltage property | 18 |
| Records without detected technology property | 28 |
| Offer elements in infoblocks 28/67 | 12 active; export blocked |
| `CML2_LINK` properties in 28/67 | 2; 0 links to a 26/65 parent resolved |

The direct matches are `Для ИБП`, `Промышленные аккумуляторы` and `Источники бесперебойного питания` in each source infoblock. Although the secondary taxonomy is found, this snapshot produced no selected product rows from infoblock 65; that is a reconciliation finding, not a reason to omit infoblock 65 from review.

The zero article/SKU/MPN values in the parent-catalog rows are a release blocker
for automatic identity matching. The snapshot does define an `Артикул` property
(`CML2_ARTICLE`) in both parent catalog infoblocks, but the selected B2B rows
have no extracted value for it. This is not proof that the SKU/offer layer has
no identity data: the 28/67 guard above blocks that conclusion until its
`CML2_LINK` relation is reconciled. The legacy numeric element ID remains only
a migration identity, not a supplier SKU or MPN.

## Scope correction for the first RB prototype

The source taxonomy confirms that a broad `Промышленные аккумуляторы` root
is not a safe first public assortment: it also contains radio, barcode-terminal,
medical-equipment and cash-register battery lines. This must not be silently
presented as a UPS catalogue merely because it sits beneath an industrial root.

For the first RB route and the HTML prototype, the pre-review focus is based on
**any matched source-section membership**, not only the primary source path.
The current generated evidence contains **1,569** candidates:

- 1,445 have their primary source path in the focus;
- 81 have a primary section elsewhere inside the broad industrial/UPS audit
  slice but an additional membership in the focus;
- 43 have a primary section outside the broad audit slice but an additional
  membership in the focus (including the Atlas Battery and Kanavno LiFePO4
  examples).

The three focus roots are:

- `akkumulyatory/dlya_ibp` and its AGM/GEL/OPzS children — 1,018;
- `istochniki-pitaniya/ibp` — 337;
- `akkumulyatory/promyshlennye/dlya_rezervnogo_pitaniya` — 90.

The remaining 1,287 broad candidates stay in the audit output for future
taxonomy work, but are out of scope for the first UPS/reserve-power commercial
route until an editor approves their category, product identity and local
commercial rules. The number 1,569 is an audit filter, not publication
approval: every row remains `needs_review` and has the identity blocker above.

## Reproducible command

From the new project root:

```powershell
.\scripts\extract-bitrix-b2b-catalog-slice.ps1 -RunSelfTest
.\scripts\extract-bitrix-b2b-catalog-slice.ps1 -SourceRoot "D:\6 Проекты\microchips.by"
```

Safe dry run:

```powershell
.\scripts\extract-bitrix-b2b-catalog-slice.ps1 -SourceRoot "D:\6 Проекты\microchips.by" -WhatIf
```

## Scope selection

The source has two parent-catalog infoblocks and two related SKU/offer
infoblocks. They cannot be silently merged or ignored:

| Infoblock | Snapshot evidence | Handling in this slice |
| ---: | --- | --- |
| 26 | Main public catalogue | Candidate B2B records are extracted for review. |
| 65 | Secondary catalogue | Candidate records remain marked `secondary_catalog_role_unconfirmed`. |
| 28 | SKU/offer infoblock | Counted on every run; a non-zero element count blocks this extractor until offers and `CML2_LINK` parents are reconciled. |
| 67 | SKU/offer infoblock | Counted on every run; a non-zero element count blocks this extractor until offers and `CML2_LINK` parents are reconciled. |

The extractor looks for a source section code or name containing `ИБП`, `бесперебойн`, `промышлен`, `industrial` or `ups`, then includes every descendant section. It also uses `b_iblock_section_element` so a product assigned to the selected category as a non-primary section is not silently missed.

This is an explicit working taxonomy rule, not a production navigation decision. A missing or unexpectedly broad match stops the run or is visible in the generated section CSV. A non-zero 28/67 offer count also stops the run: the parent catalogue cannot be called complete until the linked offer identities are reconciled.

## Generated artifacts

All files below are intentionally Git-ignored raw source material. The current
files are a historical baseline export; the hardened extractor will not refresh
them while a non-zero 28/67 offer count remains unresolved.

| Artifact | Contents | How to use it |
| --- | --- | --- |
| `bitrix-b2b-catalog-sections.csv` | Selected source sections, hierarchy path and selection reason | Approve the B2B taxonomy before URL design. |
| `bitrix-b2b-catalog-products.csv` | Legacy product identity, section membership, media file IDs and name-only technical signals | Create review records; do not publish directly. |
| `bitrix-b2b-catalog-properties.csv` | Definitions for properties from infoblocks 26 and 65 | Map property codes/names to the shared catalogue model. |
| `bitrix-b2b-catalog-property-values.csv` | Raw values only for selected product IDs, including resolved list labels where available | Validate capacity, voltage, technology, brand and SKU/MPN mappings. |
| `bitrix-b2b-catalog-quality.csv` | Per-product gaps and duplicate-name signal | Resolve before a row becomes `ready_for_review`. |
| `bitrix-b2b-catalog-summary.json` | Exact counts and source provenance for this run | Attach to the import-review report. |

`legacy_url_candidate` is deliberately only a candidate based on the source section path and numeric element ID. It must be matched to the separate URL decision registry; it never creates a redirect or canonical URL by itself.

## Fields and mapping boundary

The product CSV keeps the immutable source identities required for safe migration:

- `legacy_element_id`, `legacy_iblock_id`, `legacy_xml_id`, `legacy_code`;
- primary and additional source section membership;
- source image/document references as Bitrix file IDs only;
- `active` strictly as a snapshot signal, not current availability;
- name-derived capacity, voltage and technology signals explicitly marked `name_signals_only_needs_property_review`.

Technical, commercial and SEO values must be confirmed from `bitrix-b2b-catalog-property-values.csv` and then normalized into the import contract: stable supplier/1C ID, SKU or MPN, manufacturer, name, category, capacity, voltage, chemistry/technology, dimensions, media and status. No price, stock, delivery promise, certificate, legal entity, market currency or regional SEO text is inferred.

## Known quality risks to resolve

1. Both infoblocks can contain overlapping products; equality of product name alone is only a duplicate signal, never an automatic merge key.
2. A Bitrix `ACTIVE=Y` snapshot does not confirm current availability, price, condition, warranty or permission to sell in a country.
3. Some products can have missing media IDs, XML IDs, capacity, voltage, technology or article/SKU/MPN properties. The generated quality CSV reports these gaps per row.
4. List-property labels are resolved only when a matching `b_iblock_property_enum` value exists. Element-linked and file-linked properties remain source evidence until a reviewer maps them.
5. The legacy product detail text may contain stale prices, phones, claims or internal links. The extractor intentionally does not export it to the initial B2B slice.
6. `legacy_url_candidate` can disagree with the live route because a product may have additional sections or later redirects. Resolve it through the URL registry and live crawl before a 301 is approved.
7. A future 1C exchange can populate offer infoblocks 28/67 even when parent product records remain unchanged. The extractor blocks instead of silently dropping those offers; reconcile `CML2_LINK`, offer identity and publication rules before rerunning.

## Exit criteria for this slice

The slice advances from raw audit material only after a reviewer has: approved the target sections, reconciled parent and offer infoblocks 26/65/28/67 with `CML2_LINK`, selected stable identifiers, mapped required technical fields, checked duplicate candidates and media rights, and provided local commercial/legal data for the target site. Only then may records enter Laravel staging; publication remains a separate per-site action.
