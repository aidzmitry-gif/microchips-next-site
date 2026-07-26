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

## HTML normalization (import-level)

Before facts are composed or stored, every string leaf in the **descriptive**
allowed fields (`model`, `technology`, `applications`, `technical_attributes`)
is passed through `DescriptionHtmlNormalizer`.

**Contract: the output is NOT XSS-safe.** This class removes no script,
event handler or dangerous URL scheme, and makes no such promise. Any caller
that renders a stored description as HTML must escape it (or run it through
an actual sanitizer) at render time. Two earlier rounds (2026-07-26) tried to
build that safety guarantee out of string regexes and a DOM allowlist; each
round shipped a new way to silently destroy or scramble real text instead
(a battery spec's bare `<` swallowed everything up to an unrelated later
`>`; a malformed attribute value glued raw JS into visible text; ordinary
prose with a `<style 5>` token vanished). A regex cannot reliably tell
markup apart from a battery spec that happens to contain `<`/`>`, so a third
round stopped using regexes for repair, narrowed the promise, and later (a
fourth round) brought back auto-repair for exactly one, provably safe case.

What it actually does — "round trip, or a provably safe repair, or leave it
alone":

1. A string with no `<` at all is returned unchanged, apart from the
   leading/trailing whitespace trim applied to every input.
2. Otherwise the fragment is parsed as HTML and immediately re-serialized,
   with no transform applied yet. If that round trip reproduces the input
   (compared with only insignificant whitespace normalized), it proceeds
   to step 3 unchanged.
3. If the round trip does **not** reproduce the input, the normalizer asks
   whether the parser can still be trusted, via **two independent gates that
   must both hold**:

   - **Character order** — is every character of the original present, in
     the same order, somewhere in the re-serialized output? If yes, the
     parser only ever *inserted* closing-tag syntax to balance an element it
     auto-closed (the classic unbalanced `<p>`) and never removed or rewrote
     an original character.
   - **Visible text** — does the text that will actually render still carry
     every non-whitespace character the original showed? Content the parser
     moved inside a CDATA element (`script`, `style`, `title`, `textarea`)
     does not count as visible, because it does not render.

   If both hold, the parser's serialization is accepted and `tagsRepaired`
   is raised on the audit trail. **This is the only auto-repair this class
   performs.** If either fails — a bare `<`/`>` got entity-escaped, text was
   swallowed into a bogus tag or a malformed attribute, a mismatched closing
   tag was dropped, text became invisible CDATA content, or anything else
   the parser did not understand losslessly — **the original trimmed input
   is returned unmodified**, and `needsManualReview` is raised instead.

   This character-order check is deliberately stronger than comparing
   decoded `textContent` before/after: entity-escaping a literal `<` is
   *also* lossless once decoded back (that is the entire point of an
   entity), so a battery spec's bare `<max 10A` or `<3%/мес` would pass a
   plain textContent-equality check exactly as easily as a genuinely
   unbalanced `<p>` does — comparing decoded text alone is exactly how the
   first two auto-repair rounds fooled themselves. Comparing the raw,
   un-decoded strings for character order catches the difference that
   matters: an entity-escaped `<`/`>` no longer appears as that literal
   character anywhere in the output, so the check correctly refuses it,
   while balancing an unclosed tag leaves every original character
   untouched and only adds new closing-tag syntax around it.
4. Only once the string is round-trip-clean or a confirmed safe structural
   repair is the one content-changing transform this class performs
   applied: an `<a>` whose `href` points at the legacy Bitrix catalog route
   (`/catalog/...`, e.g. `/catalog/akkumulyatory/...`, see the 2026-07-25 RB
   first-50 audit, P1-2) is unwrapped — the tag is removed, its text is
   kept, since there is no approved 301 mapping to a new-site URL yet and
   the normalizer never invents one. Any other relative path, a link with
   its own scheme (`https://...`, `mailto:`, `tel:`), or a same-page
   `#anchor` is left untouched.
5. The visible text (`textContent`) before and after that transform is
   compared; any difference at all discards the tag repair too and reverts
   to the original input, raising `needsManualReview` instead of shipping a
   guess. There is no partial fix: either every check along the way passes,
   or the caller gets the untouched original back.

**Consequence, stated plainly: an unbalanced `<p>` — the single most common
legacy Bitrix defect (P2-2) — is auto-repaired again**, but only through the
parser's own tag-balancing and only once proven not to move or remove a
single original character — never through string surgery. A malformed
attribute, a mismatched closing tag, or a bare `<`/`>` used as a comparison
operator in a battery spec is still left completely untouched and flagged
for a human, exactly as before this round.

**The auto-repair does NOT apply** unless *both* gates in step 3 hold. A
bare `<` used as a comparison operator in a battery spec (`<max 10A`,
`<C20 = 0.35 A`, `<5A`, `<3%/мес`), a malformed attribute value, and a
mismatched closing tag all fail the character-order gate, so they come back
untouched and flagged.

The visible-text gate exists because the order gate alone is not enough. A
bare `<` followed by a CDATA element name (`style`, `script`, `title`,
`textarea`) makes the parser swallow the rest of the string as that
element's raw content: `Габариты <style h> 151х65х94 мм` re-serializes to
`Габариты <style h> 151х65х94 мм</style>`. Every original character is
still present, in order — the order gate accepts it — yet the browser
renders only `Габариты `. Comparing the text that actually renders (with
CDATA subtrees excluded) catches this and returns the original untouched.

Note that the `<style 5>` spelling used to fail the order gate *by
accident*: libxml drops `5` as an invalid attribute name, so a character
went missing. Any letter-led token (`<style h>`) has no such accident,
which is why the second gate is required rather than a belt-and-braces
extra.

**No silent text loss, ever** — the invariant every case above serves: the
output is either the trimmed input untouched, or the trimmed input with a
safe tag repair applied and/or its legacy `<a>` wrappers removed; there is
no path where text is quietly dropped, escaped, or rearranged without
`needsManualReview` (or a recorded tag repair / link dereference) marking
that something changed.

**Identity fields are never normalized** — `name`, `sku`, `mpn` and
`manufacturer` are opaque catalogue identifiers, not markup, and are stored
exactly as verified. Routing a real SKU/MPN like `RBC<124>` through an HTML
parser would entity-escape it into `RBC&lt;124&gt;` — a string that no
longer matches the real-world identifier. Only the descriptive fields above
go through `DescriptionHtmlNormalizer`.

When normalization actually changes a value — a tag structure repaired, a
link dereferenced, or a manual-review flag raised — `verified_fields._sanitization`
records:

- `links_dereferenced` — legacy `<a>` wrappers removed.
- `needs_manual_review` — how many leaf strings could not be trusted to
  round-trip losslessly (and were not a provably safe tag repair either),
  and were therefore left untouched; an editor must look at these by hand.
- `tags_repaired` — how many leaf strings had an unbalanced tag structure
  (e.g. a reopened `<p>`) auto-repaired by accepting the parser's own
  serialization, after confirming every original character survived the
  round trip in order.

The gate for adding `_sanitization` is a direct comparison of the normalized
value against the original (`DescriptionNormalizationResult::isChanged()`),
not a sum of the counters above. The key is absent only when nothing changed
at all.

See `App\Domain\Content\DescriptionHtmlNormalizer` and
`tests/Unit/Domain/Content/DescriptionHtmlNormalizerTest.php`.

## Filament

The **Черновики описаний** resource is read-only: administrators can list
records, inspect the draft, verified fields and source URLs, and move a valid
`draft` to `review`. It exposes no create, edit, approve, apply, delete or
publish action.

## Verification

```powershell
cd backend
php artisan test --filter=ProductDescriptionDraftWorkflowTest
php artisan test --filter=DescriptionHtmlNormalizerTest
```
