<?php

namespace App\Domain\Content;

use App\Models\Product;
use App\Models\ProductDescriptionDraft;
use App\Models\StagedImportRecord;
use App\Models\User;
use DomainException;
use Illuminate\Support\Arr;
use Illuminate\Support\Facades\DB;

class ProductDescriptionDrafter
{
    private const ALLOWED_FIELDS = [
        'name',
        'manufacturer',
        'model',
        'sku',
        'mpn',
        'technology',
        'applications',
        'technical_attributes',
        'removed_technical_attributes',
        'source_evidence',
    ];

    private const IDENTITY_FIELDS = ['name', 'sku', 'mpn'];

    /**
     * Identity/attribution fields are never routed through the HTML
     * normalizer: they are opaque catalogue identifiers, not markup, and a
     * DOM round trip must not be allowed to turn e.g. a real SKU
     * "RBC<124>" into "RBC&lt;124&gt;" — an entity-escaped string is no
     * longer the same identifier.
     */
    private const UNNORMALIZED_FIELDS = ['name', 'sku', 'mpn', 'manufacturer', 'source_evidence'];

    /** Metadata keys `normalizeFields()` may append; never treated as a verified descriptive fact. */
    private const META_FIELDS = ['_rejected_fields', '_sanitization', 'source_evidence', 'removed_technical_attributes'];

    public function __construct(
        private readonly DescriptionHtmlNormalizer $normalizer = new DescriptionHtmlNormalizer,
    ) {}

    /**
     * Creates editorial material only. It never writes to products or site_products.
     *
     * @param  array<string, mixed>  $verifiedFields  Fields explicitly verified against the supplied sources.
     * @param  array<int, string>  $sourceUrls  Absolute source URLs inspected by the operator.
     */
    public function createDraft(
        array $verifiedFields,
        array $sourceUrls,
        ?Product $product = null,
        ?StagedImportRecord $stagedRecord = null,
        string $locale = 'ru-BY',
        ?array $sourceEvidence = null,
    ): ProductDescriptionDraft {
        if ($sourceEvidence !== null) {
            $verifiedFields['source_evidence'] = $sourceEvidence;
        }
        $fields = $this->normalizeFields($verifiedFields);
        $sources = $this->normalizeSources($sourceUrls);
        $title = $fields['name'] ?? $product?->name ?? 'Без названия';
        $rejectionReason = $this->rejectionReason($fields, $sources, $stagedRecord);

        return ProductDescriptionDraft::query()->create([
            'product_id' => $product?->id,
            'staged_import_record_id' => $stagedRecord?->id,
            'locale' => $locale,
            'title' => $title,
            'content' => $rejectionReason === null ? $this->compose($fields) : null,
            'verified_fields' => $fields,
            'source_urls' => $sources,
            'source_kind' => $sourceEvidence['source_kind'] ?? null,
            'source_tier' => $sourceEvidence['source_tier'] ?? null,
            'source_publisher' => $sourceEvidence['source_publisher'] ?? null,
            'manufacturer_primary' => $sourceEvidence['manufacturer_primary'] ?? null,
            'identity_scope' => $sourceEvidence['identity_scope'] ?? null,
            'source_checked_at' => $sourceEvidence['checked_at'] ?? null,
            'status' => $rejectionReason === null ? 'draft' : 'rejected',
            'rejection_reason' => $rejectionReason,
        ]);
    }

    public function submitForReview(ProductDescriptionDraft $draft, ?User $submitter): ProductDescriptionDraft
    {
        return DB::transaction(function () use ($draft, $submitter): ProductDescriptionDraft {
            $draft = ProductDescriptionDraft::query()->lockForUpdate()->findOrFail($draft->id);

            if ($draft->status !== 'draft' || blank($draft->content)) {
                throw new DomainException('Only a non-empty description draft can be submitted for editorial review.');
            }

            $draft->update([
                'status' => 'review',
                'submitted_by' => $submitter?->id,
                'submitted_at' => now(),
            ]);

            return $draft->refresh();
        });
    }

    /** @param array<string, mixed> $fields */
    private function normalizeFields(array $fields): array
    {
        $unknown = array_diff(array_keys($fields), self::ALLOWED_FIELDS);
        $allowed = Arr::only($fields, self::ALLOWED_FIELDS);

        [$normalized, $auditTrail] = $this->normalizeAllowedFields($allowed);

        if ($auditTrail !== null) {
            $normalized['_sanitization'] = $auditTrail;
        }

        // An unsupported top-level field makes the whole submission
        // rejected (see rejectionReason()), but the fields that ARE
        // supported still go through the same normalization pipeline as a
        // valid submission — a rejected draft's verified_fields must not
        // be a second, unnormalized code path.
        if ($unknown !== []) {
            $normalized['_rejected_fields'] = array_values($unknown);
        }

        return $normalized;
    }

    /**
     * Splits the allowed fields into identity fields (passed through
     * untouched — see UNNORMALIZED_FIELDS) and descriptive fields (recursed
     * into and run through DescriptionHtmlNormalizer), then builds the audit
     * trail from a real before/after comparison rather than from summed
     * counters (see DescriptionNormalizationResult::isChanged()).
     *
     * @param  array<string, mixed>  $allowed
     * @return array{0: array<string, mixed>, 1: ?array<string, int|bool>}
     */
    private function normalizeAllowedFields(array $allowed): array
    {
        $identity = Arr::only($allowed, self::UNNORMALIZED_FIELDS);
        $descriptive = Arr::except($allowed, self::UNNORMALIZED_FIELDS);

        [$normalizedDescriptive, $linksDereferenced, $needsManualReview, $changed, $tagsRepaired]
            = $this->normalizeValue($descriptive);

        $merged = [...$identity, ...$normalizedDescriptive];

        if ($changed === 0) {
            return [$merged, null];
        }

        return [$merged, [
            'links_dereferenced' => $linksDereferenced,
            'needs_manual_review' => $needsManualReview,
            'tags_repaired' => $tagsRepaired,
        ]];
    }

    /**
     * Recursively runs every string leaf through DescriptionHtmlNormalizer
     * so a raw legacy Bitrix `<a>` link (e.g. copied into an "applications"
     * or "technical_attributes" fact) never reaches storage still pointing
     * at the dead legacy catalog route, an unbalanced `<p>` is repaired only
     * when provably safe, and no leaf is ever silently rewritten in a way
     * that could have lost text.
     *
     * @return array{0: mixed, 1: int, 2: int, 3: int, 4: int} normalized value,
     *                                                         links dereferenced, how many leaves need manual review, how many
     *                                                         leaves actually changed value (the real audit gate), and how many
     *                                                         leaves had an unbalanced tag structure auto-repaired.
     */
    private function normalizeValue(mixed $value): array
    {
        if (is_string($value)) {
            $result = $this->normalizer->normalize($value);

            return [
                $result->html,
                $result->linksDereferenced,
                $result->needsManualReview ? 1 : 0,
                $result->isChanged() ? 1 : 0,
                $result->tagsRepaired ? 1 : 0,
            ];
        }

        if (is_array($value)) {
            $normalizedArray = [];
            $linksDereferenced = 0;
            $needsManualReview = 0;
            $changed = 0;
            $tagsRepaired = 0;

            foreach ($value as $key => $item) {
                [$normalizedItem, $itemLinks, $itemNeedsReview, $itemChanged, $itemTagsRepaired]
                    = $this->normalizeValue($item);
                $normalizedArray[$key] = $normalizedItem;
                $linksDereferenced += $itemLinks;
                $needsManualReview += $itemNeedsReview;
                $changed += $itemChanged;
                $tagsRepaired += $itemTagsRepaired;
            }

            return [$normalizedArray, $linksDereferenced, $needsManualReview, $changed, $tagsRepaired];
        }

        return [$value, 0, 0, 0, 0];
    }

    /** @param array<int, string> $sourceUrls */
    private function normalizeSources(array $sourceUrls): array
    {
        return array_values(array_unique(array_filter(array_map(
            static fn (mixed $url): ?string => is_string($url) && filter_var(trim($url), FILTER_VALIDATE_URL)
                && in_array(parse_url(trim($url), PHP_URL_SCHEME), ['http', 'https'], true)
                    ? trim($url)
                    : null,
            $sourceUrls,
        ))));
    }

    /** @param array<string, mixed> $fields */
    private function rejectionReason(array $fields, array $sources, ?StagedImportRecord $stagedRecord): ?string
    {
        if ($stagedRecord?->status === 'duplicate') {
            return 'A duplicate catalogue record cannot receive migrated content until its identity conflict is resolved.';
        }

        if (isset($fields['_rejected_fields'])) {
            return 'Unsupported fields were supplied as verified: '.implode(', ', $fields['_rejected_fields']).'.';
        }

        if (blank($fields['name'] ?? null)) {
            return 'A verified product name is required before drafting a description.';
        }

        if ($sources === []) {
            return 'At least one valid absolute source URL is required before drafting a description.';
        }

        $descriptiveFields = Arr::except($fields, [...self::IDENTITY_FIELDS, ...self::META_FIELDS]);
        $hasFact = collect($descriptiveFields)->contains(function (mixed $value): bool {
            if (is_array($value)) {
                return collect($value)->contains(static fn (mixed $item): bool => filled($item));
            }

            return is_scalar($value) && filled(trim((string) $value));
        });

        if (! $hasFact) {
            return 'Title-only source data is insufficient: verify at least one descriptive fact before drafting.';
        }

        return null;
    }

    /** @param array<string, mixed> $fields */
    private function compose(array $fields): string
    {
        $name = trim((string) $fields['name']);
        $introFacts = [];

        foreach (['manufacturer' => 'производитель', 'model' => 'модель', 'technology' => 'технология'] as $key => $label) {
            if (filled($fields[$key] ?? null)) {
                $introFacts[] = $label.': '.trim((string) $fields[$key]);
            }
        }

        $paragraphs = [$name.($introFacts === [] ? '.' : ' — '.implode(', ', $introFacts).'.')];
        $attributes = $fields['technical_attributes'] ?? [];

        if (is_array($attributes) && $attributes !== []) {
            // A `<key>_provenance` sibling (see SiteProductCategoryAssigner)
            // marks <key> as DERIVED, not independently confirmed -- if such
            // a value ever reaches this editorial tool bundled inside a
            // Product's raw technical_attributes, it must not be printed
            // under the "Подтверждённые характеристики" (confirmed
            // characteristics) heading alongside facts the operator actually
            // verified. The provenance object itself is already excluded by
            // is_scalar(); this also excludes the fact it annotates.
            $derivedKeys = collect(array_keys($attributes))
                ->filter(static fn (mixed $key): bool => is_string($key) && str_ends_with($key, '_provenance'))
                ->map(static fn (string $key): string => substr($key, 0, -strlen('_provenance')))
                ->all();

            $facts = collect($attributes)
                ->filter(static fn (mixed $value, mixed $key): bool => is_scalar($value) && filled(trim((string) $value)) && ! in_array($key, $derivedKeys, true))
                ->map(static fn (mixed $value, mixed $key): string => trim((string) $key).': '.trim((string) $value))
                ->values()
                ->all();

            if ($facts !== []) {
                $paragraphs[] = 'Подтверждённые характеристики: '.implode('; ', $facts).'.';
            }
        }

        $applications = $fields['applications'] ?? [];
        if (is_array($applications)) {
            $applications = array_values(array_filter($applications, static fn (mixed $value): bool => is_scalar($value) && filled(trim((string) $value))));
        } elseif (is_scalar($applications) && filled(trim((string) $applications))) {
            $applications = [trim((string) $applications)];
        } else {
            $applications = [];
        }

        if ($applications !== []) {
            $paragraphs[] = 'Подтверждённое применение: '.implode(', ', $applications).'.';
        }

        return implode("\n\n", $paragraphs);
    }
}
