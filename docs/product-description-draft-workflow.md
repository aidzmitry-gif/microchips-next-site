# Product description draft workflow

This workflow fills editorial gaps without turning unverified catalogue data
into public claims.

## Gate

`ProductDescriptionDrafter::createDraft()` accepts only explicitly verified
fields and the absolute HTTP(S) URLs used to verify them. Allowed fields are
`name`, `manufacturer`, `model`, `sku`, `mpn`, `technology`, `applications`
and `technical_attributes`.

- A verified name, at least one valid source URL and at least one descriptive
  fact beyond the title/SKU/MPN are required.
- Title-only rows, missing sources and unsupported fields are stored with
  `status=rejected`, an empty `content` and a machine-readable audit trail in
  `verified_fields` plus a human-readable `rejection_reason`.
- Valid material starts at `status=draft`. An editor may move it only to
  `status=review` with `submitForReview()`.
- A staged record with `status=duplicate` is always stored as `rejected`, even
  when its manufacturer source and text are otherwise valid. It cannot add a
  second product or transfer content until the identity conflict is resolved.
- An already known, identical `external_id` is a controlled update of the
  existing shared product, not a new product. A matching SKU/MPN with another
  `external_id` is a duplicate conflict and cannot be imported.
- There is deliberately no publish/apply method. The service never changes
  `products.short_description`, `site_products.is_published`, SEO metadata or
  availability. A reviewed draft must be copied/approved through a separate
  editorial action that is outside this gate.

The generated text is deterministic and contains only supplied facts; it does
not infer warranty, price, availability, compatibility or performance.

## Filament

The **Черновики описаний** resource is read-only: administrators can list
records, inspect the draft, verified fields and source URLs, and move a valid
`draft` to `review`. It exposes no create, edit, approve, apply, delete or
publish action.

## Verification

```powershell
cd backend
php artisan test --filter=ProductDescriptionDraftWorkflowTest
```
