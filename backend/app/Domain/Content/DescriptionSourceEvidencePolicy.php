<?php

namespace App\Domain\Content;

use DateTimeImmutable;
use RuntimeException;

final class DescriptionSourceEvidencePolicy
{
    public const DEALER_KIND = 'official_dealer_product_page';

    public const DEALER_TIER = 'dealer_backed';

    public const MANUFACTURER_CATALOGUE_KIND = 'official_manufacturer_catalogue';

    public const MANUFACTURER_PRODUCT_PAGE_KIND = 'official_manufacturer_product_page';

    public const MANUFACTURER_PRIMARY_TIER = 'manufacturer_primary';

    /** @return array<string, mixed>|null */
    public static function fromManifestRow(array $row, int $index): ?array
    {
        $hasProvenance = array_key_exists('source_kind', $row) || array_key_exists('source_tier', $row);
        if (! $hasProvenance) {
            return null;
        }

        $sourceKind = self::requiredString($row, 'source_kind', $index);
        $sourceTier = self::requiredString($row, 'source_tier', $index);
        if ($sourceKind === self::DEALER_KIND && $sourceTier === self::DEALER_TIER) {
            return self::dealerEvidence($row, $index, $sourceKind, $sourceTier);
        }

        if (in_array($sourceKind, self::manufacturerPrimaryKinds(), true)
            && $sourceTier === self::MANUFACTURER_PRIMARY_TIER) {
            return self::manufacturerPrimaryEvidence($row, $index, $sourceKind, $sourceTier);
        }

        throw new RuntimeException("Product row {$index} uses an unsupported source kind/tier pair.");
    }

    /** @return array<string, mixed> */
    private static function dealerEvidence(array $row, int $index, string $sourceKind, string $sourceTier): array
    {

        $allowed = [
            'external_id', 'identity_scope', 'manufacturer', 'model_core', 'technology',
            'source_url', 'technical_attributes', 'source_kind', 'source_tier',
            'source_publisher', 'manufacturer_primary', 'evidence_scope', 'checked_at',
        ];
        $unknown = array_values(array_diff(array_keys($row), $allowed));
        if ($unknown !== []) {
            throw new RuntimeException("Product row {$index} dealer-backed evidence contains prohibited fields: ".implode(', ', $unknown).'.');
        }
        if (($row['identity_scope'] ?? null) !== 'model_core' || ($row['evidence_scope'] ?? null) !== 'model_core') {
            throw new RuntimeException("Product row {$index} dealer-backed evidence requires model_core scope.");
        }
        if (($row['manufacturer_primary'] ?? null) !== false) {
            throw new RuntimeException("Product row {$index} dealer-backed evidence must set manufacturer_primary=false.");
        }

        $sourceUrl = self::requiredString($row, 'source_url', $index);
        if (! filter_var($sourceUrl, FILTER_VALIDATE_URL) || parse_url($sourceUrl, PHP_URL_SCHEME) !== 'https') {
            throw new RuntimeException("Product row {$index} dealer-backed source_url must be HTTPS.");
        }
        $publisher = self::requiredString($row, 'source_publisher', $index);
        $checkedAt = self::requiredString($row, 'checked_at', $index);
        $date = DateTimeImmutable::createFromFormat('!Y-m-d', $checkedAt);
        if ($date === false || $date->format('Y-m-d') !== $checkedAt) {
            throw new RuntimeException("Product row {$index} dealer-backed checked_at must be YYYY-MM-DD.");
        }

        $attributes = $row['technical_attributes'] ?? [];
        if (! is_array($attributes) || $attributes === []) {
            throw new RuntimeException("Product row {$index} dealer-backed evidence requires technical_attributes.");
        }
        foreach (array_keys($attributes) as $key) {
            if (! is_string($key) || ! in_array(self::normaliseKey($key), self::dealerAttributeKeys(), true)) {
                throw new RuntimeException("Product row {$index} dealer-backed technical attribute {$key} is prohibited.");
            }
        }

        return [
            'source_kind' => $sourceKind,
            'source_tier' => $sourceTier,
            'source_publisher' => $publisher,
            'manufacturer_primary' => false,
            'identity_scope' => 'model_core',
            'checked_at' => $checkedAt,
        ];
    }

    /** @return array<string, mixed> */
    private static function manufacturerPrimaryEvidence(array $row, int $index, string $sourceKind, string $sourceTier): array
    {
        if (($row['identity_scope'] ?? null) === 'model_core' || ($row['evidence_scope'] ?? null) === 'model_core') {
            return self::manufacturerPrimaryModelCoreEvidence($row, $index, $sourceKind, $sourceTier);
        }
        $allowed = [
            'external_id', 'identity_scope', 'manufacturer', 'mpn', 'display_name', 'technology',
            'source_url', 'technical_attributes', 'remove_technical_attributes', 'source_kind', 'source_tier',
            'source_publisher', 'manufacturer_primary', 'evidence_scope', 'checked_at',
        ];
        $unknown = array_values(array_diff(array_keys($row), $allowed));
        if ($unknown !== []) {
            throw new RuntimeException("Product row {$index} manufacturer-primary evidence contains prohibited fields: ".implode(', ', $unknown).'.');
        }
        if (($row['identity_scope'] ?? null) !== 'exact' || ($row['evidence_scope'] ?? null) !== 'exact_model') {
            throw new RuntimeException("Product row {$index} manufacturer-primary evidence requires exact/exact_model scope.");
        }
        if (($row['manufacturer_primary'] ?? null) !== true) {
            throw new RuntimeException("Product row {$index} manufacturer-primary evidence must set manufacturer_primary=true.");
        }

        foreach (['manufacturer', 'mpn', 'technology'] as $field) {
            self::requiredString($row, $field, $index);
        }
        $sourceUrl = self::requiredString($row, 'source_url', $index);
        if (! filter_var($sourceUrl, FILTER_VALIDATE_URL) || parse_url($sourceUrl, PHP_URL_SCHEME) !== 'https') {
            throw new RuntimeException("Product row {$index} manufacturer-primary source_url must be HTTPS.");
        }
        $publisher = self::requiredString($row, 'source_publisher', $index);
        $checkedAt = self::requiredString($row, 'checked_at', $index);
        $date = DateTimeImmutable::createFromFormat('!Y-m-d', $checkedAt);
        if ($date === false || $date->format('Y-m-d') !== $checkedAt) {
            throw new RuntimeException("Product row {$index} manufacturer-primary checked_at must be YYYY-MM-DD.");
        }

        $attributes = $row['technical_attributes'] ?? null;
        if (! is_array($attributes) || $attributes === [] || array_is_list($attributes)) {
            throw new RuntimeException("Product row {$index} manufacturer-primary evidence requires a technical_attributes map.");
        }
        foreach ($attributes as $key => $value) {
            if (! is_string($key) || blank($key) || ! is_string($value) || blank($value)) {
                throw new RuntimeException("Product row {$index} manufacturer-primary technical_attributes must be a non-empty string map.");
            }
        }

        return [
            'source_kind' => $sourceKind,
            'source_tier' => $sourceTier,
            'source_publisher' => $publisher,
            'manufacturer_primary' => true,
            'identity_scope' => 'exact',
            'checked_at' => $checkedAt,
        ];
    }

    /** @return list<string> */
    private static function manufacturerPrimaryKinds(): array
    {
        return [
            self::MANUFACTURER_CATALOGUE_KIND,
            self::MANUFACTURER_PRODUCT_PAGE_KIND,
        ];
    }

    /** Manufacturer-primary facts may be attached to a bounded legacy model core, never to an inferred MPN. */
    private static function manufacturerPrimaryModelCoreEvidence(array $row, int $index, string $sourceKind, string $sourceTier): array
    {
        $allowed = [
            'external_id', 'identity_scope', 'manufacturer', 'model_core', 'technology',
            'source_url', 'technical_attributes', 'source_kind', 'source_tier',
            'source_publisher', 'manufacturer_primary', 'evidence_scope', 'checked_at',
        ];
        $unknown = array_values(array_diff(array_keys($row), $allowed));
        if ($unknown !== []) {
            throw new RuntimeException("Product row {$index} manufacturer-primary model_core evidence contains prohibited fields: ".implode(', ', $unknown).'.');
        }
        if (($row['identity_scope'] ?? null) !== 'model_core' || ($row['evidence_scope'] ?? null) !== 'model_core') {
            throw new RuntimeException("Product row {$index} manufacturer-primary model_core evidence requires model_core scope.");
        }
        if (($row['manufacturer_primary'] ?? null) !== true) {
            throw new RuntimeException("Product row {$index} manufacturer-primary model_core evidence must set manufacturer_primary=true.");
        }
        foreach (['manufacturer', 'model_core', 'technology'] as $field) {
            self::requiredString($row, $field, $index);
        }
        $sourceUrl = self::requiredString($row, 'source_url', $index);
        if (! filter_var($sourceUrl, FILTER_VALIDATE_URL) || parse_url($sourceUrl, PHP_URL_SCHEME) !== 'https') {
            throw new RuntimeException("Product row {$index} manufacturer-primary model_core source_url must be HTTPS.");
        }
        $publisher = self::requiredString($row, 'source_publisher', $index);
        $checkedAt = self::requiredString($row, 'checked_at', $index);
        $date = DateTimeImmutable::createFromFormat('!Y-m-d', $checkedAt);
        if ($date === false || $date->format('Y-m-d') !== $checkedAt) {
            throw new RuntimeException("Product row {$index} manufacturer-primary model_core checked_at must be YYYY-MM-DD.");
        }
        $attributes = $row['technical_attributes'] ?? null;
        if (! is_array($attributes) || $attributes === [] || array_is_list($attributes)) {
            throw new RuntimeException("Product row {$index} manufacturer-primary model_core evidence requires a technical_attributes map.");
        }
        foreach ($attributes as $key => $value) {
            if (! is_string($key) || blank($key) || ! is_string($value) || blank($value)) {
                throw new RuntimeException("Product row {$index} manufacturer-primary model_core technical_attributes must be a non-empty string map.");
            }
        }

        return [
            'source_kind' => $sourceKind,
            'source_tier' => $sourceTier,
            'source_publisher' => $publisher,
            'manufacturer_primary' => true,
            'identity_scope' => 'model_core',
            'checked_at' => $checkedAt,
        ];
    }

    /** @return list<string> */
    private static function dealerAttributeKeys(): array
    {
        return [
            'nominal voltage', 'voltage', 'номинальное напряжение',
            'nominal capacity', 'capacity', 'номинальная емкость', 'номинальная ёмкость',
        ];
    }

    private static function normaliseKey(string $key): string
    {
        return preg_replace('/\s+/u', ' ', mb_strtolower(trim($key))) ?? '';
    }

    private static function requiredString(array $row, string $key, int $index): string
    {
        if (! is_string($row[$key] ?? null) || blank($row[$key])) {
            throw new RuntimeException("Product row {$index} requires {$key}.");
        }

        return trim($row[$key]);
    }
}
