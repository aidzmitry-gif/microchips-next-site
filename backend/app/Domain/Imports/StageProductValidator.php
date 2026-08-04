<?php

namespace App\Domain\Imports;

use Illuminate\Support\Str;

class StageProductValidator
{
    /**
     * Normalizes only known product fields. Source payload remains immutable on the staged record.
     *
     * @param  array<string, mixed>  $payload
     * @return array{data: array<string, mixed>, errors: array<string, string>}
     */
    public function normalizeAndValidate(array $payload): array
    {
        $externalId = $this->value($payload, ['external_id', 'id', '1c_id', 'uuid']);
        $name = $this->value($payload, ['name', 'product_name', 'наименование']);
        $sku = $this->value($payload, ['sku', 'article', 'артикул']);
        $mpn = $this->value($payload, ['mpn', 'part_number', 'номер_производителя']);
        $manufacturer = $this->value($payload, ['manufacturer', 'brand', 'производитель']);
        $sourceSlug = $this->value($payload, ['slug', 'url_slug']);

        $errors = [];

        if ($externalId === null) {
            $errors['external_id'] = 'A stable 1C external ID is required.';
        }

        if ($name === null) {
            $errors['name'] = 'Product name is required.';
        }

        if ($externalId === null && $sku === null && $mpn === null) {
            $errors['identifier'] = 'At least one stable identifier (1C external ID, SKU or MPN) is required.';
        }

        $slug = $sourceSlug ?: ($name === null ? null : Str::slug($name));
        if (blank($slug)) {
            $errors['slug'] = 'A URL slug is required when the product name cannot be safely transliterated.';
        }

        return [
            'data' => array_filter([
                'external_id' => $externalId,
                'sku' => $sku,
                'mpn' => $mpn,
                'manufacturer' => $manufacturer,
                'name' => $name,
                'slug' => $slug,
                'technical_attributes' => $this->technicalAttributes($payload),
            ], static fn (mixed $value): bool => $value !== null),
            'errors' => $errors,
        ];
    }

    /** @param array<string, mixed> $payload */
    private function value(array $payload, array $keys): ?string
    {
        foreach ($keys as $key) {
            $value = $payload[$key] ?? null;

            if (is_scalar($value) && filled(trim((string) $value))) {
                return trim((string) $value);
            }
        }

        return null;
    }

    /**
     * @param  array<string, mixed>  $payload
     * @return array<string, string>
     */
    private function technicalAttributes(array $payload): array
    {
        $attributes = [];

        foreach (['voltage', 'capacity', 'chemistry', 'dimensions', 'weight'] as $key) {
            $value = $this->value($payload, [$key]);

            if ($value !== null) {
                $attributes[$key] = $value;
            }
        }

        return $attributes;
    }
}
