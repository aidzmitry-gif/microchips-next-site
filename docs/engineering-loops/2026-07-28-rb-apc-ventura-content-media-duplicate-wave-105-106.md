# RB APC and Ventura content/media/duplicate waves 105–106 — 2026-07-28

## Scope

This loop continued from the verified wave-104 state and processed only 1C
inventory products outside the electronic-component scope. It did not repeat
earlier media or duplicate decisions.

## Applied content

Two exact models passed the source and identity gates:

| 1C external ID | Manufacturer | MPN | Verified source-backed facts |
| --- | --- | --- | --- |
| `КА-00003200` | APC | `RBC31` | replacement cartridge, VRLA lead-acid, 48 V, 9 Ah, complete assembly, Smart-UPS On-Line SURT |
| `ФР-00001290` | Ventura | `GPL 12-40` | VRLA AGM, 12 V, official C20 capacity 47 Ah, F6 terminal, 197 × 166 × 176 mm, 13.5 kg |

The APC evidence is the official Schneider Electric RBC31 product page. The
Ventura evidence is the official GPL 12-40 product page. Local warranty claims
were not copied from either source.

The Ventura model name contains `12-40`, and the archived physical label says
`12V 40Ah`; the current official page separately states 47 Ah at the defined
C20 rate to 1.75 V/cell. The page preserves that measurement basis instead of
silently treating the two numbers as interchangeable.

Both products were published only as `noindex, nofollow` previews. They remain
`on_request`, show price on request and emit no `Offer` schema.

## Exact-label media

One company-owned legacy asset passed `visible_exact_mpn`:

- product: `ФР-00001290` Ventura GPL 12-40;
- Bitrix element: `1610`;
- visible label: `Ventura GPL 12-40`, `12V 40Ah`;
- Microchips watermark: present;
- SHA-256:
  `4dded1f12cf9e99233926e26a7b3027d5a2a3a2287efec2574e9ed299c21bc1f`.

An adversarial prefix check prevented a wrong attachment: `КА-00001290` is an
unrelated label-stock item, while the Ventura battery is `ФР-00001290`. Only
the verified `ФР` product received content, preview and media.

The archived APC RBC31 image remained rejected because the exact cartridge
number is not readable. The source-backed page is useful without presenting
that unverified image.

## Duplicate correction

Two unpublished RB links were removed as exact APCRBC141 cartridge duplicates:

- `КА-00004009`;
- `КА-00004503`.

The survivor is `КА-00003237`, already published as the source-backed APC
APCRBC141 canonical preview with verified media. The exclusion command deleted
only the two non-public `microchips-by` site links. Canonical Product records,
other markets and the published survivor were unchanged. A final database
query confirmed zero remaining RB links for both excluded IDs.

Other APC rows were held because the 1C voltage/capacity wording conflicts
with the official cartridge-level specification, or because the exact model
marking is unreadable. They were not forced into the catalogue.

## Applied counters

- RB site products: 7,143;
- published noindex previews: 87;
- applied source-backed descriptions: 210;
- verified published media products: 39;
- current prices with provenance evidence: 57;
- strict non-electronic content-complete cards: **39 / 7,286 = 0.54%**;
- remaining fixed first-10% enrichment queue: 690 records.

The accepted price policy remains legacy-site price first, otherwise usable
1C source price multiplied once by two. The current 1C snapshot contains no
usable price rows; no price was invented.

## Verification

- description dry-run and apply: 2 valid and applied;
- duplicate dry-run and apply: 2 non-public links removed, 0 canonical Product
  records deleted, 0 published records changed;
- preview dry-run and apply: 2 products, 0 indexable URLs, 0 offers;
- media dry-run and apply: 1 exact-label asset imported and published;
- repeat description staging: `0 created, 2 unchanged`;
- repeat media dry-run: `0 imported, 1 unchanged`;
- live SSR: one H1, self-canonical, `noindex, nofollow`, no horizontal
  overflow, price-on-request state and no `Offer` for both pages;
- the Ventura page exposes one verified image; RBC31 exposes no unverified
  image;
- SEO audit: 103 checked URLs, 0 blocking issues;
- enrichment queue rebuilt with the fixed 7,286 baseline and electronic
  components excluded: 39 complete, 690 remaining.

## Reproducible evidence

- `docs/imports/rb-source-backed-description-drafts-wave-105-2026-07-28.json`
- `docs/imports/rb-source-verified-preview-wave-105-2026-07-28.json`
- `docs/imports/rb-verified-legacy-images-wave-105-2026-07-28.json`
- `docs/imports/rb-strict-duplicate-exclusion-wave-106.csv`

