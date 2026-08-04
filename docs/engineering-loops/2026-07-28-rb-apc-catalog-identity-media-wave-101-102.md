# RB APC catalogue-identity media waves 101–102 — 2026-07-28

## Scope

This loop continued from the verified wave-100 state without reapplying old
duplicate decisions. Only products present in the 1C inventory were eligible;
electronic components remained excluded.

The loop formalized a second, still strict, image-evidence level for cases in
which the physical model label is too small to read but all of the following
are true:

1. the 1C item maps one-to-one to a Bitrix item by manufacturer and exact MPN;
2. the archived asset is company-owned and carries the Microchips watermark;
3. the visible form factor is consistent with that catalogue identity;
4. no contradictory model or specification is visible;
5. the Bitrix identity reference is stored with the media record.

This level is named `unique_catalog_identity_plus_visual_consistency`. It does
not admit capacity-only, family-only or one-to-many matches.

## Applied products

| 1C external ID | Exact MPN | Safe verified content | Bitrix evidence | Media SHA-256 |
| --- | --- | --- | --- | --- |
| `КА-00003292` | `RBC7` | APC replacement cartridge; VRLA; 12 V; 17 Ah | element `20088` | `44900e77bedb6a25cf95874143f6b07270e6679ccd5ef592c44de622aefdc4f5` |
| `КА-00005164` | `RBC23` | APC sealed lead-acid replacement cartridge | element `23799` | `ad525ac5cf05b6dd90fcf6011c897ca68653e641b77e713f85f50e126e7c9af3` |
| `КА-00003237` | `APCRBC141` | APC 72 V replacement cartridge for the documented SRT2200 family | element `23818` | `561ec2b260a2763cfd20b95ff39133c6693dc89076e346e98f83cc7730a7d146` |

The content sources are official APC catalogue, safety-data and compatibility
documents recorded in the source-backed description manifest. The unsafe old
`12 V / 5 Ah` wording for APCRBC141 was not copied as a cartridge-pack
specification because APC documents the cartridge as 72 V.

All three pages are published only as `noindex, nofollow` previews under
`/catalog/industrial-batteries/batteries-ups/`. They remain `on_request`, have
no price, do not claim stock or local warranty, and emit no `Offer` schema.

## Adversarial holds and duplicate result

- `APCRBC152` remained rejected because the available source facts conflict
  with the candidate specification.
- Image candidates whose identity was only a capacity, family or ambiguous
  model match remained rejected.
- The `LS14500 SAFT 2PF` pair remained held because the source records contain
  a France-versus-China origin conflict.
- The duplicate scan for the next priority block found eight groups already
  present in the established exclusion registry. A live dry-run proved that
  every safe excluded ID was already absent from the RB site scope, so wave
  102 intentionally made no duplicate database change and created no second
  exclusion registry.

## Verified counters

- RB site products: 7,145;
- published noindex previews: 79;
- applied source-backed descriptions: 202;
- verified published media products: 36;
- current prices with provenance evidence: 57;
- strict non-electronic content-complete cards: **36 / 7,286 = 0.49%**;
- remaining fixed first-10% queue: 693 records.

The current 1C snapshot contains 9,209 inventory records but zero usable price
rows. The accepted fallback remains `1C source_price × 2`; no price was
invented for these products. The price suite independently passes 4 tests and
20 assertions.

## Verification

- database identity, category, publication, availability, price and media
  evidence were checked for all three products;
- repeat description staging: `0 created, 3 unchanged`;
- repeat preview dry-run: 3 products, 0 indexable URLs, 0 offers;
- repeat media dry-run: `0 imported, 3 unchanged`;
- targeted media importer suite: 2 tests, 12 assertions — pass;
- Laravel Pint for the modified media importer and its test — pass;
- live Next.js pages: one H1, one verified image, correct self-canonical,
  `noindex, nofollow`, no horizontal overflow and no `Offer` schema;
- SEO release audit: 95 checked URLs, 0 blocking issues;
- enrichment queue rebuilt with fixed baseline 7,286 and electronic-component
  exclusion: 36 complete, 693 remaining to the first 10% target.

The separate description-application dry-run correctly reports that already
applied drafts are no longer applicable; this is expected state protection,
not an idempotency failure. Staging, preview and media gates prove the repeated
wave cannot create duplicate drafts, URLs or assets.

## Reproducible evidence

- `docs/imports/rb-source-backed-description-drafts-wave-101-2026-07-28.json`
- `docs/imports/rb-source-verified-preview-wave-101-2026-07-28.json`
- `docs/imports/rb-verified-legacy-images-wave-101-2026-07-28.json`
- `backend/app/Console/Commands/ImportVerifiedLegacyImages.php`
- `backend/tests/Feature/ImportVerifiedLegacyImagesTest.php`

