# RB scope exclusion wave 110 — evidence

## Decision

Six unpublished RB market drafts are excluded from the storefront. The
canonical 1C products remain untouched, so the decision is market-scoped and
reversible.

| Excluded 1C ID | Decision | Canonical survivor / reason |
| --- | --- | --- |
| `КА-00004699` | exact duplicate | keep `КА-00004649`: both identify a 24×4PzS420 traction battery in an 827×519×625 case with NAKI `321162.554` |
| `КА-00003593` | exact duplicate | keep `КА-00003672`: both identify a 24×4PzS460, 48 V / 460 Ah traction battery in a 968×527×645 case |
| `КА-00005102` | service | loading and unloading by forklift is an activity, not a separately identifiable catalogue good |
| `КА-00005192` | outside scope | complete CPD20 electric forklift, not an accumulator or reserve-power product |
| `КА-00005999` | outside scope | complete HILIFT OP15 electric forklift, not an accumulator or reserve-power product |
| `КА-00004721` | unsafe/outside scope | complete forklift row with implausible “1600 tons” wording; publishing it would create a misleading thin page |

## Safety checks

- all six records exist in the canonical `products` table and are linked to
  the RB site;
- all six RB `site_products` rows are unpublished, `on_request` and have no
  price;
- the exclusion command deletes only the six RB market links;
- neither canonical products nor other country sites are changed;
- duplicate survivors are retained as unpublished RB drafts for later
  identity and content enrichment.

The exclusion is intentionally narrower than a general fuzzy duplicate pass.
Only pairs with the same model configuration and case identity are treated as
duplicates. Similar-looking battery names without matching technical identity
remain on hold.
