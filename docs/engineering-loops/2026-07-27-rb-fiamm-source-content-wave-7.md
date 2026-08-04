# RB FIAMM source-content wave 7

## Scope

Three RB catalogue records with stable manufacturer + MPN identity were refreshed
from model-specific FIAMM technical documents:

| 1C external ID | MPN | Source | Result |
| --- | --- | --- | --- |
| `КА-00004114` | `6SLA100` | FIAMM-branded 6SLA100 datasheet | name, description and 6 V / 100 Ah / VRLA AGM facts applied |
| `КА-00003889` | `6SLA125` | FIAMM-branded 6SLA125 datasheet | name, description, electrical facts, dimensions and mass applied |
| `ФР-00001439` | `FG21202` | FIAMM FG21202 technical datasheet | name, description, electrical facts, dimensions, mass and terminal applied |

The source manifest is
`docs/imports/rb-source-backed-description-drafts-wave-7-2026-07-27.json`.

## Safety boundary

This wave deliberately did **not**:

- change a product price, availability, delivery claim or offer markup;
- create an image from a third-party source;
- publish any of the three products;
- make a URL indexable.

All three were subsequently allowed into a separate `noindex` preview wave
only after the company-owned archive image passed an exact-model visual check.
They are not eligible for search indexation, pricing, stock claims or
`Offer` structured data.

## Evidence

1. `content:stage-source-backed-description-drafts … --refresh-existing --apply`
   created/renewed the three editorial drafts.
2. `content:apply-verified-description-drafts … --apply` applied 3 and
   reported no publication or commercial-data changes.
3. The exact legacy `b_file` references were read from the gzipped Bitrix
   dump with `scripts/inspect-bitrix-file-references.py`; images were extracted
   from the company backup and visually verified.
4. `catalog:publish-source-verified-preview-wave … --apply` published exactly
   three noindex product pages; `media:import-verified-legacy-images … --apply`
   added exactly three verified images.
5. PostgreSQL verification confirmed all three canonical product URLs have
   `is_indexable = false`. The RB preview now has 13 published noindex products
   and 10 verified visible product images.
