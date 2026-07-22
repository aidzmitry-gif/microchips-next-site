<?php

namespace App\Domain\Imports;

final class ProductIdentity
{
    /** @var list<string> */
    public const FIELDS = ['external_id', 'sku', 'mpn'];

    public static function normalize(mixed $value): ?string
    {
        if (! is_scalar($value)) {
            return null;
        }

        $value = mb_strtolower(trim((string) $value));
        $value = preg_replace('/[^\p{L}\p{N}]+/u', '', $value) ?? '';

        return $value === '' ? null : $value;
    }

    /**
     * @param  array<string, mixed>  $data
     * @return array<string, string>
     */
    public static function fingerprints(array $data): array
    {
        $fingerprints = [];

        foreach (self::FIELDS as $field) {
            $normalized = self::normalize($data[$field] ?? null);

            if ($normalized !== null) {
                $fingerprints[$field] = $normalized;
            }
        }

        return $fingerprints;
    }
}
