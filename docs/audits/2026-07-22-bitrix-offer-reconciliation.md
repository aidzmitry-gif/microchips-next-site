# Bitrix offer reconciliation: snapshot evidence

Audit date: 2026-07-22. Source: the read-only 2026-06-23 SQL gzip snapshot
at `D:\6 Проекты\microchips.by\db\user_microchips_data.sql.gz`.

## Conclusion

The snapshot contains active SKU/offer elements in infoblocks 28 and 67, but
it contains no stored `CML2_LINK` values for those offers. The parent relation
therefore cannot be reconstructed from this backup. This is a source-data
limitation, not a reason to migrate or invent a parent relation.

The twelve active rows are all in iblock 67 (IDs `26838`–`26849`) and are
footwear names, not batteries or UPS equipment. They are reviewed as an exact,
snapshot-specific out-of-scope orphan set: the B2B battery slice may proceed
with a visible `needs_review` status, while the orphan rows remain migration
debt and are never exported as products or offers. This exception is not a
general relaxation of the guard: a new ID, a changed iblock, or any stored
`CML2_LINK` value blocks the extractor again.

No product, URL, price, availability, or SEO page was created or changed by
this audit.

## Verified evidence

| Check | Result |
| --- | --- |
| Active offer elements in 28/67 | 12 |
| Active offer elements in 28 | 0 |
| Active offer elements in 67 | 12 (reviewed footwear orphans) |
| `CML2_LINK` property definition in offer iblock 28 | property ID 541; parent iblock 26 |
| `CML2_LINK` property definition in offer iblock 67 | property ID 1371; parent iblock 65 |
| Rows in `b_iblock_element_property` for property ID 541 | 0 |
| Rows in `b_iblock_element_property` for property ID 1371 | 0 |
| Version-2 specialised property tables for 28/67 | not present in this snapshot |

The two zero counts were obtained by a read-only gzip scan for SQL tuples with
the respective property ID in the generic Bitrix property-value table. The
absence of specialised `b_iblock_element_prop_*` tables for offer iblocks 28
and 67 removes the main alternative storage location in this snapshot.

## Decision

Keep the hard stop for every unreviewed, linked, changed, or potentially
B2B-relevant offer. The extractor has an allow-list only for these twelve exact
unlinked iblock-67 IDs; it writes the reconciliation status into the generated
summary so a later snapshot cannot silently inherit the exception.

To reconcile the twelve offers, obtain one of the following authoritative
sources:

1. a 1C export containing offer ID/SKU/MPN and its parent product ID;
2. a newer complete Bitrix database export after the catalogue exchange; or
3. a supplier file with a reviewed parent-to-offer mapping.

Until identity evidence is reviewed, the RB focus remains `needs_review` and
is ineligible for staging or publication. The twelve footwear orphans also
remain ineligible for any migration until an owner explicitly resolves them.
