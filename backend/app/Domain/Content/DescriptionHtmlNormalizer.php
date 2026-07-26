<?php

namespace App\Domain\Content;

use DOMDocument;
use DOMElement;
use DOMXPath;

/**
 * Normalizes raw legacy (Bitrix) description markup before it enters the
 * ProductDescriptionDraft workflow.
 *
 * CONTRACT: this is NOT an XSS-safe sanitizer and makes no such claim. It
 * does not strip `<script>`, `on*` handlers or dangerous URL schemes — any
 * caller that renders the returned value as HTML must escape it (or run it
 * through an actual sanitizer) at render time. What this class does is much
 * narrower and easier to trust: "round-trip, or repair only what is
 * provably safe, or leave it alone".
 *
 * Two rounds of regex-based "defense in depth" (2026-07-26) each tried to
 * repair/neutralize legacy markup with string heuristics and each shipped a
 * new way to silently destroy or scramble real text — a battery spec's bare
 * "<" comparison operator read as a tag start and swallowed everything up to
 * an unrelated later ">" elsewhere in the string; a malformed attribute
 * value glued raw JS into visible text; ordinary prose with a "<style 5>"
 * token vanished. The root cause was the same every time: a regex cannot
 * reliably tell markup from a battery spec that happens to contain "<"/">".
 *
 * A third round (2026-07-26) brought back auto-repair for the single most
 * common legacy Bitrix defect — an unbalanced `<p>` that reopens without
 * closing the previous one — but only after finding a check that cannot be
 * fooled by the same failure mode as the first two rounds. Algorithm:
 *
 * 1. No "<" anywhere in the string -> return it unchanged apart from the
 *    leading/trailing whitespace trim applied to every input. There is
 *    nothing to parse and no risk in skipping DOM entirely.
 * 2. Parse the fragment as HTML and immediately re-serialize it, with no
 *    transform applied yet. If that round trip reproduces the input
 *    (compared with insignificant whitespace normalized), skip straight to
 *    step 4.
 * 3. If the round trip does NOT reproduce the input, decide whether the
 *    parser can still be trusted with `isSafeStructuralRepair()`: is every
 *    character of the original string present, IN THE SAME ORDER, somewhere
 *    in the re-serialized output? If yes, the parser only ever INSERTED
 *    characters (closing-tag syntax to balance an element it auto-closed,
 *    e.g. the second `<p>` implicitly closing the first) and never removed
 *    or rewrote a single one of the original's own characters — accept the
 *    parser's serialization and record `tagsRepaired = true`. If no — some
 *    original character is missing or was rewritten (a bare "<"/">" got
 *    entity-escaped, text was swallowed into a bogus tag or malformed
 *    attribute, a mismatched closing tag was dropped) — the parser cannot be
 *    trusted. Return the ORIGINAL trimmed input unmodified, with
 *    `needsManualReview = true`, and stop.
 *
 *    This is a deliberately stronger test than comparing decoded
 *    `textContent` before/after: entity-escaping a literal "<" is *also*
 *    lossless once decoded back (that is the entire point of an entity), so
 *    a battery spec's bare "<max 10A" or "<3%/мес" would pass a plain
 *    textContent-equality check exactly as easily as a genuinely unbalanced
 *    `<p>` does — which is precisely how the first two auto-repair attempts
 *    fooled themselves. Comparing the raw, un-decoded strings as an ordered
 *    subsequence catches the difference that actually matters: an
 *    entity-escaped "<"/">" no longer appears as that literal character
 *    anywhere in the output, so the subsequence check correctly fails for
 *    it, while balancing an unclosed tag leaves every original character
 *    untouched and only adds new closing-tag syntax around it.
 * 4. Only once the string is either round-trip-clean or a confirmed safe
 *    structural repair is the one content-changing transform this class
 *    performs applied: an `<a>` whose `href` points at the legacy Bitrix
 *    catalog route (`/catalog/...`, see docs/audits/2026-07-25-rb-first-50-
 *    product-audit.md P1-2, which has no approved 301 mapping to a new-site
 *    URL) is unwrapped — the tag is removed, its text is kept. No new-site
 *    URL is ever invented.
 * 5. The visible text (`textContent`) before and after that transform is
 *    compared. Any difference at all discards the tag repair too and
 *    reverts to the ORIGINAL input, raising `needsManualReview` instead of
 *    shipping a guess. There is no partial fix: either every check along
 *    the way passes, or the caller gets the untouched original back.
 *
 *    The order check alone is NOT sufficient, so a second gate compares the
 *    text that actually RENDERS (CDATA subtrees excluded) — see
 *    `isVisibleTextPreserved()`. Both gates must hold to accept a repair.
 *
 * Consequence, stated plainly: an unbalanced `<p>` is auto-repaired again,
 * but only via the parser's own tag-balancing, never via string surgery —
 * and only when doing so is proven to move neither a single original
 * character nor a single character out of visible text. A malformed
 * attribute, a mismatched closing tag, a bare "<"/">" used as a comparison
 * operator in a battery spec, and prose swallowed into a `<style>`/`<script>`
 * element are all still left completely untouched and flagged for a human.
 *
 * The full audit trail is returned so the caller can leave a record of what
 * was changed (or flagged) — see DescriptionNormalizationResult.
 */
class DescriptionHtmlNormalizer
{
    /** The only href prefixes treated as the dead legacy Bitrix catalog route. */
    private const LEGACY_LINK_PREFIXES = ['/catalog/', 'catalog/'];

    public function normalize(?string $html): DescriptionNormalizationResult
    {
        $original = trim((string) $html);

        if ($original === '' || ! str_contains($original, '<')) {
            // Empty, or no "<" anywhere: nothing for a DOM parser to get
            // right or wrong. Returned exactly as received.
            return new DescriptionNormalizationResult($original, $original, 0, false);
        }

        $document = $this->parseFragment($original);
        $root = $document->getElementById('__root__');

        if (! $root instanceof DOMElement) {
            return new DescriptionNormalizationResult($original, $original, 0, true);
        }

        $roundTrip = $this->serializeChildren($document, $root);
        $tagsRepaired = false;

        if (! $this->areEquivalent($roundTrip, $original)) {
            if (! $this->isSafeStructuralRepair($original, $roundTrip, $root)) {
                // The parser does not understand this string losslessly —
                // and it is not merely a case of balancing an unclosed tag
                // either. Ship the untouched original, not the parser's
                // guess.
                return new DescriptionNormalizationResult($original, $original, 0, true);
            }

            // Every character of $original survives, in order, in
            // $roundTrip: the only difference is closing-tag syntax the
            // parser inserted to balance an element left open (e.g. a
            // reopened <p>). Nothing was removed or rewritten — safe to
            // accept the parser's own serialization.
            $tagsRepaired = true;
        }

        $textBefore = $root->textContent;
        $linksDereferenced = $this->dereferenceLegacyLinks($document, $root);

        if ($linksDereferenced === 0) {
            if (! $tagsRepaired) {
                // Round trip was clean but there is nothing this class
                // changes about this fragment — keep the original bytes
                // rather than a re-serialized copy nobody asked for.
                return new DescriptionNormalizationResult($original, $original, 0, false);
            }

            // The only change is the accepted tag repair from above.
            return new DescriptionNormalizationResult(
                trim($this->serializeChildren($document, $root)),
                $original,
                0,
                false,
                true,
            );
        }

        $textAfter = $root->textContent;

        if ($this->normalizeWhitespace($textBefore) !== $this->normalizeWhitespace($textAfter)) {
            // The link-unwrap transform must never move a single visible
            // character. If it did, refuse it — and discard any tag repair
            // too, since this class never ships a partial fix.
            return new DescriptionNormalizationResult($original, $original, 0, true);
        }

        return new DescriptionNormalizationResult(
            trim($this->serializeChildren($document, $root)),
            $original,
            $linksDereferenced,
            false,
            $tagsRepaired,
        );
    }

    /**
     * Elements whose content is CDATA/raw text: anything the parser moves
     * inside one of these stops being visible text at render time, even
     * though every character is still present in the serialized string.
     */
    private const INVISIBLE_CONTENT_TAGS = ['script', 'style', 'title', 'textarea'];

    /**
     * A repair is safe only when BOTH gates below hold. They catch different
     * failure modes and neither is sufficient alone.
     */
    private function isSafeStructuralRepair(string $original, string $roundTrip, DOMElement $root): bool
    {
        return $this->isCharacterOrderPreserved($original, $roundTrip)
            && $this->isVisibleTextPreserved($original, $root);
    }

    /**
     * Gate 1 — every character of $original appears, in the same relative
     * order, somewhere in $roundTrip: the parser could only have INSERTED
     * characters (closing-tag syntax) and never removed or substituted one
     * of the original's own. Strictly safer than comparing decoded
     * `textContent`, which entity-escaping passes trivially (see docblock).
     */
    private function isCharacterOrderPreserved(string $original, string $roundTrip): bool
    {
        $needle = mb_str_split($original);
        $haystack = mb_str_split($roundTrip);

        $needleLength = count($needle);
        $haystackLength = count($haystack);
        $matched = 0;

        for ($cursor = 0; $matched < $needleLength && $cursor < $haystackLength; $cursor++) {
            if ($needle[$matched] === $haystack[$cursor]) {
                $matched++;
            }
        }

        return $matched === $needleLength;
    }

    /**
     * Gate 2 — the text that will actually RENDER still carries every
     * non-whitespace character the original showed, in order.
     *
     * Gate 1 alone proves characters survive in the *string*, not that they
     * survive as *visible text*. A bare "<" followed by a CDATA tag name
     * defeats it: "Габариты <style h> 151х65х94 мм" re-serializes to
     * "Габариты <style h> 151х65х94 мм</style>" — every original character is
     * still there, in order, so gate 1 passes, yet the browser renders only
     * "Габариты " because the parser swallowed the rest into <style>.
     *
     * (The `<style 5>` spelling used to fail gate 1 by accident: libxml drops
     * "5" as an invalid attribute name, so a character went missing. Any
     * letter-led token such as `<style h>` has no such accident, which is
     * exactly why this second gate is required rather than optional.)
     *
     * The original's visible text is approximated by stripping well-formed
     * tags. That approximation can only be too pessimistic — a malformed tag
     * left in place merely adds characters the round trip may not show,
     * which rejects the repair. Erring toward "leave it alone and flag" is
     * the safe direction.
     */
    private function isVisibleTextPreserved(string $original, DOMElement $root): bool
    {
        $originalVisible = $this->significantCharacters(
            preg_replace('/<[^<>]*>/u', '', $original) ?? $original
        );

        return $this->isCharacterOrderPreserved(
            $originalVisible,
            $this->significantCharacters($this->renderableText($root))
        );
    }

    /**
     * textContent minus the subtrees whose content never renders as text.
     */
    private function renderableText(DOMElement $root): string
    {
        $clone = $root->cloneNode(true);

        if (! $clone instanceof DOMElement) {
            return $root->textContent;
        }

        $xpath = new DOMXPath($clone->ownerDocument);
        $selector = implode(' | ', array_map(
            static fn (string $tag): string => './/'.$tag,
            self::INVISIBLE_CONTENT_TAGS
        ));

        foreach (iterator_to_array($xpath->query($selector, $clone) ?: []) as $node) {
            $node->parentNode?->removeChild($node);
        }

        return $clone->textContent;
    }

    /** Whitespace carries no meaning for this comparison; everything else does. */
    private function significantCharacters(string $text): string
    {
        return preg_replace('/\s+/u', '', $text) ?? $text;
    }

    private function parseFragment(string $html): DOMDocument
    {
        $document = new DOMDocument;
        $previous = libxml_use_internal_errors(true);

        // The XML declaration forces UTF-8 decoding; DOMDocument otherwise
        // assumes ISO-8859-1 and mangles Cyrillic text. It is stripped from
        // the parsed tree automatically and is never a child of #__root__.
        $document->loadHTML(
            '<?xml encoding="utf-8"?><div id="__root__">'.$html.'</div>',
            LIBXML_HTML_NOIMPLIED | LIBXML_HTML_NODEFDTD,
        );

        libxml_clear_errors();
        libxml_use_internal_errors($previous);

        return $document;
    }

    private function serializeChildren(DOMDocument $document, DOMElement $root): string
    {
        $html = '';

        foreach (iterator_to_array($root->childNodes) as $child) {
            $html .= $document->saveHTML($child);
        }

        return $html;
    }

    private function areEquivalent(string $roundTrip, string $original): bool
    {
        return $this->normalizeWhitespace($roundTrip) === $this->normalizeWhitespace($original);
    }

    private function normalizeWhitespace(string $text): string
    {
        return trim(preg_replace('/\s+/u', ' ', $text) ?? $text);
    }

    private function dereferenceLegacyLinks(DOMDocument $document, DOMElement $root): int
    {
        $xpath = new DOMXPath($document);
        $anchors = iterator_to_array($xpath->query('.//a', $root) ?: []);

        $count = 0;

        foreach ($anchors as $anchor) {
            if (! $anchor instanceof DOMElement) {
                continue;
            }

            if (! $this->isLegacyCatalogLink(trim($anchor->getAttribute('href')))) {
                continue;
            }

            $count++;
            $this->unwrap($anchor);
        }

        return $count;
    }

    private function isLegacyCatalogLink(string $href): bool
    {
        foreach (self::LEGACY_LINK_PREFIXES as $prefix) {
            if (str_starts_with($href, $prefix)) {
                return true;
            }
        }

        return false;
    }

    /** Removes an element but keeps its children/text in its place. */
    private function unwrap(DOMElement $element): void
    {
        $parent = $element->parentNode;

        if ($parent === null) {
            return;
        }

        while ($element->firstChild) {
            $parent->insertBefore($element->firstChild, $element);
        }

        $parent->removeChild($element);
    }
}
