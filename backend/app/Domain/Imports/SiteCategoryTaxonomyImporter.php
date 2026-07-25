<?php

namespace App\Domain\Imports;

use App\Models\Category;
use App\Models\Site;
use App\Models\SiteCategory;
use Illuminate\Support\Facades\DB;
use RuntimeException;
use Throwable;

class SiteCategoryTaxonomyImporter
{
    /** @var array<string, string> */
    private const HEADERS = [
        'bitrixidраздела' => 'external_id',
        'родительid' => 'parent_external_id',
        'название' => 'name',
        'путьнасайте' => 'path',
        'ссылканасайт' => 'source_url',
        '1сгруппазаполнить' => 'one_c_group',
    ];

    /**
     * @param  list<string>  $allowedMissingParents
     * @return array<string, mixed>
     */
    public function import(
        Site $site,
        string $file,
        string $delimiter,
        string $source,
        array $allowedMissingParents,
        bool $apply,
    ): array {
        [$rows, $errors] = $this->read($file, $delimiter);
        $allowedMissingParents = array_values(array_unique(array_filter(array_map('trim', $allowedMissingParents))));

        $summary = [
            'mode' => $apply ? 'apply' : 'dry_run',
            'site_id' => $site->id,
            'site_key' => $site->key,
            'source_key' => $source,
            'csv_records' => count($rows),
            'accepted_records' => 0,
            'created' => 0,
            'updated' => 0,
            'unchanged' => 0,
            'existing_parent_resolutions' => 0,
            'external_boundary_parent_ids' => [],
            'new_records_published' => 0,
            'existing_publication_preserved' => 0,
            'publication_status' => 'new_records_unpublished_existing_status_preserved',
            'validation_error_count' => 0,
            'validation_errors' => [],
        ];

        $validation = $this->validate($site, $source, $rows, $allowedMissingParents, $errors);
        $summary['validation_error_count'] = count($validation['errors']);
        $summary['validation_errors'] = array_slice($validation['errors'], 0, 50);
        $summary['external_boundary_parent_ids'] = $validation['boundary_parent_ids'];
        $summary['existing_parent_resolutions'] = count($validation['existing_parents']);

        if ($validation['errors'] !== []) {
            return $summary;
        }

        $summary['accepted_records'] = count($rows);
        DB::beginTransaction();

        try {
            /** @var array<string, SiteCategory> $resolved */
            $resolved = $validation['existing_parents'];

            foreach ($validation['ordered_rows'] as $row) {
                $existing = SiteCategory::query()
                    ->where('site_id', $site->id)
                    ->where('source', $source)
                    ->where('external_id', $row['external_id'])
                    ->first();
                $parent = $resolved[$row['parent_external_id']] ?? null;
                $parentId = $parent?->category_id;

                if ($existing === null) {
                    $category = Category::create([
                        'parent_id' => $parentId,
                        'slug' => $this->categoryIdentitySlug($site, $source, $row['external_id']),
                        'name' => $row['name'],
                        'sort_order' => $row['sort_order'],
                    ]);
                    $existing = SiteCategory::create([
                        'site_id' => $site->id,
                        'source' => $source,
                        'external_id' => $row['external_id'],
                        'category_id' => $category->id,
                        'slug' => $row['path'],
                        'name' => $row['name'],
                        'is_published' => false,
                        'sort_order' => $row['sort_order'],
                    ]);
                    $summary['created']++;
                } else {
                    $category = $existing->category()->firstOrFail();
                    $category->fill([
                        'parent_id' => $parentId,
                        'name' => $row['name'],
                        'sort_order' => $row['sort_order'],
                    ]);
                    $existing->fill([
                        'slug' => $row['path'],
                        'name' => $row['name'],
                        'sort_order' => $row['sort_order'],
                    ]);

                    if ($category->isDirty() || $existing->isDirty()) {
                        $category->save();
                        $existing->category_id = $category->id;
                        $existing->save();
                        $summary['updated']++;
                    } else {
                        $summary['unchanged']++;
                    }

                    if ($existing->is_published) {
                        $summary['existing_publication_preserved']++;
                    }
                }

                $resolved[$row['external_id']] = $existing;
            }

            if ($apply) {
                DB::commit();
            } else {
                DB::rollBack();
            }
        } catch (Throwable $error) {
            if (DB::transactionLevel() > 0) {
                DB::rollBack();
            }

            throw $error;
        }

        return $summary;
    }

    /**
     * @param  list<array<string, mixed>>  $rows
     * @param  list<string>  $allowedMissingParents
     * @param  list<array<string, mixed>>  $readErrors
     * @return array{errors: list<array<string, mixed>>, ordered_rows: list<array<string, mixed>>, existing_parents: array<string, SiteCategory>, boundary_parent_ids: list<string>}
     */
    private function validate(Site $site, string $source, array $rows, array $allowedMissingParents, array $readErrors): array
    {
        $errors = $readErrors;
        $byId = [];
        $paths = [];

        foreach ($rows as $row) {
            $id = $row['external_id'];
            $pathKey = mb_strtolower($row['path']);

            if (isset($byId[$id])) {
                $errors[] = $this->error($row['row_number'], 'duplicate_external_id', ['external_id' => $id]);
            } else {
                $byId[$id] = $row;
            }

            if (isset($paths[$pathKey])) {
                $errors[] = $this->error($row['row_number'], 'duplicate_path', ['path' => $row['path']]);
            } else {
                $paths[$pathKey] = $id;
            }

            if ($id === $row['parent_external_id']) {
                $errors[] = $this->error($row['row_number'], 'self_parent', ['external_id' => $id]);
            }
        }

        $parentIds = array_values(array_unique(array_column($rows, 'parent_external_id')));
        $existingParents = SiteCategory::query()
            ->where('site_id', $site->id)
            ->where('source', $source)
            ->whereIn('external_id', $parentIds)
            ->get()
            ->keyBy('external_id')
            ->all();
        $allowed = array_fill_keys($allowedMissingParents, true);
        $boundaryParents = [];

        foreach ($rows as $row) {
            $parentId = $row['parent_external_id'];
            if (isset($byId[$parentId]) || isset($existingParents[$parentId])) {
                continue;
            }
            if (isset($allowed[$parentId])) {
                $boundaryParents[$parentId] = true;

                continue;
            }

            $errors[] = $this->error($row['row_number'], 'unknown_parent', [
                'external_id' => $row['external_id'],
                'parent_external_id' => $parentId,
            ]);
        }

        $existingIdentities = SiteCategory::query()
            ->where('site_id', $site->id)
            ->where('source', $source)
            ->whereIn('external_id', array_keys($byId))
            ->get()
            ->keyBy('external_id');
        $existingPaths = SiteCategory::query()
            ->where('site_id', $site->id)
            ->get()
            ->filter(fn (SiteCategory $siteCategory): bool => isset($paths[mb_strtolower($siteCategory->slug)]));

        foreach ($existingPaths as $siteCategory) {
            $expected = $existingIdentities->get((string) $siteCategory->external_id);
            if ($expected?->id !== $siteCategory->id) {
                $errors[] = $this->error(null, 'site_path_conflict', [
                    'path' => $siteCategory->slug,
                    'site_category_id' => $siteCategory->id,
                ]);
            }
        }

        foreach ($existingIdentities as $siteCategory) {
            if (SiteCategory::query()
                ->where('category_id', $siteCategory->category_id)
                ->where('site_id', '!=', $site->id)
                ->exists()) {
                $errors[] = $this->error(null, 'shared_canonical_category', [
                    'external_id' => $siteCategory->external_id,
                    'category_id' => $siteCategory->category_id,
                ]);
            }
        }

        $ordered = [];
        $remaining = $byId;
        while ($remaining !== []) {
            $progress = false;
            foreach ($remaining as $id => $row) {
                if (isset($remaining[$row['parent_external_id']])) {
                    continue;
                }
                $ordered[] = $row;
                unset($remaining[$id]);
                $progress = true;
            }

            if (! $progress) {
                $errors[] = $this->error(null, 'cyclic_hierarchy', ['external_ids' => array_keys($remaining)]);

                break;
            }
        }

        return [
            'errors' => $errors,
            'ordered_rows' => $ordered,
            'existing_parents' => $existingParents,
            'boundary_parent_ids' => array_keys($boundaryParents),
        ];
    }

    /**
     * @return array{list<array<string, mixed>>, list<array<string, mixed>>}
     */
    private function read(string $file, string $delimiter): array
    {
        $handle = fopen($file, 'rb');
        if ($handle === false) {
            throw new RuntimeException("Unable to open {$file}.");
        }

        try {
            $rawHeaders = fgetcsv($handle, 0, $delimiter, '"', '');
            if ($rawHeaders === false) {
                throw new RuntimeException('CSV file does not contain a header row.');
            }

            $headers = array_map(fn (mixed $header): string => $this->normalizeHeader((string) $header), $rawHeaders);
            foreach (['external_id', 'parent_external_id', 'name', 'path'] as $required) {
                if (! in_array($required, $headers, true)) {
                    throw new RuntimeException("Required category column is missing: {$required}.");
                }
            }
            if (count($headers) !== count(array_unique($headers))) {
                throw new RuntimeException('CSV contains duplicate normalized headers.');
            }

            $rows = [];
            $errors = [];
            $rowNumber = 1;
            while (($raw = fgetcsv($handle, 0, $delimiter, '"', '')) !== false) {
                $rowNumber++;
                if ($raw === [null] || $raw === []) {
                    continue;
                }
                if (count($raw) !== count($headers)) {
                    $errors[] = $this->error($rowNumber, 'column_count_mismatch', [
                        'expected' => count($headers),
                        'actual' => count($raw),
                    ]);

                    continue;
                }

                $payload = array_combine($headers, $raw);
                $externalId = $this->clean($payload['external_id'] ?? null);
                $parentId = $this->clean($payload['parent_external_id'] ?? null);
                $name = $this->clean($payload['name'] ?? null);
                $path = $this->normalizePath($payload['path'] ?? null);
                $invalid = array_keys(array_filter([
                    'external_id' => $externalId === null,
                    'parent_external_id' => $parentId === null,
                    'name' => $name === null,
                    'path' => $path === null,
                ]));

                if ($invalid !== []) {
                    $errors[] = $this->error($rowNumber, 'invalid_required_fields', ['fields' => $invalid]);

                    continue;
                }

                $rows[] = [
                    'row_number' => $rowNumber,
                    'sort_order' => $rowNumber - 2,
                    'external_id' => $externalId,
                    'parent_external_id' => $parentId,
                    'name' => $name,
                    'path' => $path,
                ];
            }

            return [$rows, $errors];
        } finally {
            fclose($handle);
        }
    }

    private function normalizeHeader(string $header): string
    {
        $normalized = mb_strtolower(ltrim(trim($header), "\xEF\xBB\xBF"));
        $normalized = preg_replace('/[^\p{L}\p{N}]+/u', '', $normalized) ?? '';

        return self::HEADERS[$normalized] ?? $normalized;
    }

    private function normalizePath(mixed $value): ?string
    {
        $path = $this->clean($value);
        if ($path === null) {
            return null;
        }

        $path = trim(str_replace('\\', '/', $path), '/');
        if ($path === '' || mb_strlen($path) > 255 || str_contains($path, '//') || preg_match('/(^|\/)\.\.?($|\/)|[?#]/u', $path)) {
            return null;
        }

        return mb_strtolower($path);
    }

    private function clean(mixed $value): ?string
    {
        if (! is_scalar($value)) {
            return null;
        }
        $clean = trim((string) $value);

        return $clean !== '' && mb_strlen($clean) <= 255 ? $clean : null;
    }

    /** @param  array<string, mixed>  $context */
    private function error(?int $rowNumber, string $reason, array $context = []): array
    {
        return ['row_number' => $rowNumber, 'reason' => $reason, ...$context];
    }

    private function categoryIdentitySlug(Site $site, string $source, string $externalId): string
    {
        return 'taxonomy-'.substr(hash('sha256', $site->id.'|'.$source.'|'.$externalId), 0, 40);
    }
}
