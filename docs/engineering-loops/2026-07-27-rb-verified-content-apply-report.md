# RB verified content apply — 2026-07-27

## Purpose

Source-backed editorial drafts are useful only if their verified facts can
reach canonical product fields without bypassing commercial or publication
gates. A new explicit command applies only `short_description` and the
source-verified `technical_attributes` from a draft named in the evidence
manifest.

It cannot change product URL, SKU, MPN, manufacturer, price, availability or
`site_products.is_published`.

## Applied evidence

The manifest named three source-backed records:

- Panasonic BR2330 (`КА-00004377`);
- OMRON CJ1W-BAT01 (`КА-00003325`);
- FIAMM 12FGH36 (`ФР-00002108`).

Run 91 dry run validated three changes and zero publications. Run 92 applied
all three. Database verification shows non-empty descriptions (406, 424 and
285 characters respectively), `status = applied`, `is_published = false`, no
price, and `availability = on_request` for every record.

## Guardrail

The operation is not a release. These products still need their own public URL
decision, local commercial data, media evidence and SEO release checks before
they can become customer-visible or indexable.
