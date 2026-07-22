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
    ];

    private const IDENTITY_FIELDS = ['name', 'sku', 'mpn'];

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
    ): ProductDescriptionDraft {
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

        if ($unknown !== []) {
            return [
                ...Arr::only($fields, self::ALLOWED_FIELDS),
                '_rejected_fields' => array_values($unknown),
            ];
        }

        return Arr::only($fields, self::ALLOWED_FIELDS);
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

        $descriptiveFields = Arr::except($fields, self::IDENTITY_FIELDS);
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
            $facts = collect($attributes)
                ->filter(static fn (mixed $value): bool => is_scalar($value) && filled(trim((string) $value)))
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
