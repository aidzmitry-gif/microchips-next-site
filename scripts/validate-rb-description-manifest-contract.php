<?php

declare(strict_types=1);

use App\Domain\Content\DescriptionSourceEvidencePolicy;
$root = dirname(__DIR__);
require $root.'/backend/vendor/autoload.php';

$file = $argv[1] ?? '';
if ($file === '' || ! is_readable($file)) {
    fwrite(STDERR, "Description manifest is not readable.\n");
    exit(2);
}

try {
    $manifest = json_decode((string) file_get_contents($file), true, 512, JSON_THROW_ON_ERROR);
    if (! is_array($manifest) || ($manifest['locale'] ?? null) !== 'ru-BY'
        || ! is_array($manifest['products'] ?? null) || $manifest['products'] === []) {
        throw new RuntimeException('Manifest requires locale=ru-BY and a non-empty products list.');
    }
    $seen = [];
    foreach ($manifest['products'] as $index => $row) {
        if (! is_array($row)) {
            throw new RuntimeException("Product row {$index} must be an object.");
        }
        DescriptionSourceEvidencePolicy::fromManifestRow($row, $index);
        $scope = $row['identity_scope'] ?? 'exact';
        if (! is_string($scope) || ! in_array($scope, ['exact', 'model_core'], true)) {
            throw new RuntimeException("Product row {$index} identity_scope must be exact or model_core.");
        }
        $required = $scope === 'model_core'
            ? ['external_id', 'manufacturer', 'model_core', 'source_url']
            : ['external_id', 'manufacturer', 'mpn', 'technology', 'source_url'];
        foreach ($required as $field) {
            if (! is_string($row[$field] ?? null) || trim($row[$field]) === '') {
                throw new RuntimeException("Product row {$index} requires {$field}.");
            }
        }
        $externalId = trim($row['external_id']);
        if (isset($seen[$externalId])) {
            throw new RuntimeException("Manifest repeats external_id {$externalId}.");
        }
        $seen[$externalId] = true;
        if (array_key_exists('technical_attributes', $row)) {
            if (! is_array($row['technical_attributes'])) {
                throw new RuntimeException("Product row {$index} technical_attributes must be a map.");
            }
            foreach ($row['technical_attributes'] as $key => $value) {
                if (! is_string($key) || ! is_string($value) || trim($value) === '') {
                    throw new RuntimeException("Product row {$index} technical_attributes must be a non-empty string map.");
                }
            }
        }
        if (is_string($row['technology'] ?? null) && trim($row['technology']) !== '') {
            $technology = trim($row['technology']);
            $attributes = $row['technical_attributes'] ?? [];
            if (isset($attributes['Технология']) && trim((string) $attributes['Технология']) !== $technology) {
                throw new RuntimeException("Product row {$index} technology contradicts technical_attributes.Технология.");
            }
        }
        $removed = $row['remove_technical_attributes'] ?? [];
        if (! is_array($removed) || ! array_is_list($removed)) {
            throw new RuntimeException("Product row {$index} remove_technical_attributes must be a list.");
        }
        $trimmed = [];
        foreach ($removed as $value) {
            if (! is_string($value) || trim($value) === '') {
                throw new RuntimeException("Product row {$index} remove_technical_attributes contains a blank value.");
            }
            $trimmed[] = trim($value);
        }
        if (count(array_unique($trimmed)) !== count($trimmed)) {
            throw new RuntimeException("Product row {$index} remove_technical_attributes contains duplicates.");
        }
        if (array_intersect($trimmed, array_keys($row['technical_attributes'] ?? [])) !== []) {
            throw new RuntimeException("Product row {$index} verifies and removes the same technical attribute.");
        }
    }
    echo json_encode([
        'status' => 'pass',
        'products' => count($manifest['products']),
        'policy' => DescriptionSourceEvidencePolicy::class,
    ], JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE).PHP_EOL;
} catch (Throwable $error) {
    fwrite(STDERR, $error->getMessage().PHP_EOL);
    exit(2);
}
