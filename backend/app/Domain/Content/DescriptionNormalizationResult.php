<?php

namespace App\Domain\Content;

/**
 * Outcome of running a single piece of draft-description text through
 * DescriptionHtmlNormalizer. Carries an audit trail (how many legacy links
 * were dereferenced, whether an unbalanced tag was auto-repaired, whether
 * the text needs a human look) so editors can see what changed instead of
 * trusting the normalizer silently.
 *
 * This is an audit record, not a safety guarantee: `html` is not XSS-safe
 * (see DescriptionHtmlNormalizer's docblock) — it is either the input
 * completely untouched, or the input with an unbalanced tag structure
 * accepted as the parser serialized it (`tagsRepaired`) and/or exactly one
 * legacy `<a>` wrapper removed.
 */
final class DescriptionNormalizationResult
{
    public function __construct(
        public readonly string $html,
        public readonly string $original,
        public readonly int $linksDereferenced,
        public readonly bool $needsManualReview,
        public readonly bool $tagsRepaired = false,
    ) {}

    /**
     * The real audit gate: did the stored value actually change, for any
     * reason at all — link dereferencing or a manual-review flag — rather
     * than a sum of counters that can miss a change no counter tracks.
     */
    public function isChanged(): bool
    {
        return $this->needsManualReview || $this->html !== $this->original;
    }

    public function isNoop(): bool
    {
        return ! $this->isChanged();
    }
}
