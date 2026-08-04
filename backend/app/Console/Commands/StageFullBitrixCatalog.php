<?php

namespace App\Console\Commands;

use App\Models\ImportRun;
use App\Models\Site;
use App\Models\SiteCategory;
use App\Models\StagedImportRecord;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\DB;
use JsonException;
use RuntimeException;
use Throwable;

class StageFullBitrixCatalog extends Command
{
    protected $signature = 'catalog:stage-full-bitrix-catalog
                            {site : Site key}
                            {file : Complete full-catalog staging manifest}
                            {--expected-records=17207 : Exact expected source row count}
                            {--apply : Persist staging evidence; default is dry-run}';

    protected $description = 'Stage the complete namespaced Bitrix catalogue without merging, publishing or indexing';

    private const STATUSES = [
        'excluded_inactive_legacy',
        'scope_excluded_electronics',
        'hold_duplicate_candidate',
        'hold_one_c_collision',
        'existing_one_c_exact_link',
        'hold_linked_identity_candidate',
        'legacy_only_draft_candidate',
    ];

    public function handle(): int
    {
        try {
            $site = Site::query()->where('key', trim((string) $this->argument('site')))->sole();
            [$records, $raw, $statusCounts, $categoryCounts] = $this->validatedManifest(
                $site,
                (string) $this->argument('file'),
                (int) $this->option('expected-records'),
            );
            $hash = hash('sha256', $raw);
            $source = 'bitrix_full_catalog_snapshot:'.$site->key;
            $existing = ImportRun::query()->where('source', $source)->latest('id')->first();
            $unchanged = $existing !== null
                && ($existing->summary['manifest_sha256'] ?? null) === $hash
                && $existing->total_records === count($records)
                && StagedImportRecord::query()->where('import_run_id', $existing->id)->count() === count($records);
            $summary = [
                'mode' => $this->option('apply') ? 'apply' : 'dry_run',
                'site' => $site->key,
                'records' => count($records),
                'status_counts' => $statusCounts,
                'active_category_counts' => $categoryCounts,
                'manifest_sha256' => $hash,
                'product_changes' => 0,
                'publication_changes' => 0,
                'indexable_urls' => 0,
                'merges' => 0,
                'unchanged' => $unchanged,
            ];

            if (! $this->option('apply') || $unchanged) {
                $this->line(json_encode($summary, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE));

                return self::SUCCESS;
            }

            DB::transaction(function () use ($categoryCounts, $hash, $records, $site, $source, $statusCounts): void {
                $run = ImportRun::query()->create([
                    'source' => $source,
                    'status' => 'completed',
                    'source_file' => basename((string) $this->argument('file')),
                    'total_records' => count($records),
                    'processed_records' => count($records),
                    'failed_records' => 0,
                    'summary' => [
                        'site_id' => $site->id,
                        'manifest_sha256' => $hash,
                        'status_counts' => $statusCounts,
                        'active_category_counts' => $categoryCounts,
                        'product_changes' => 0,
                        'publication_changes' => 0,
                        'indexable_urls' => 0,
                        'merges' => 0,
                    ],
                    'started_at' => now(),
                    'finished_at' => now(),
                ]);

                foreach (array_chunk($records, 250) as $chunkOffset => $chunk) {
                    $now = now();
                    $rows = [];
                    foreach ($chunk as $offset => $record) {
                        $rows[] = [
                            'import_run_id' => $run->id,
                            'row_number' => ($chunkOffset * 250) + $offset + 1,
                            'entity_type' => 'bitrix_full_catalog_product_evidence',
                            'external_id' => $record['registry_id'],
                            'payload' => json_encode($record, JSON_THROW_ON_ERROR | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES),
                            'normalized_payload' => json_encode([
                                'site_id' => $site->id,
                                'bitrix_id' => $record['bitrix_id'],
                                'one_c_external_id' => $record['one_c_external_id'],
                                'target_category_external_id' => $record['target_category_external_id'],
                                'transfer_status' => $record['transfer_status'],
                                'source_checksum' => $record['source_checksum'],
                            ], JSON_THROW_ON_ERROR | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES),
                            'validation_errors' => json_encode([], JSON_THROW_ON_ERROR),
                            'status' => 'staged_evidence',
                            'error' => null,
                            'review_note' => 'Complete Bitrix staging only; no merge, Product creation, publication or indexing.',
                            'created_at' => $now,
                            'updated_at' => $now,
                        ];
                    }
                    StagedImportRecord::query()->insert($rows);
                }
            });

            $this->line(json_encode($summary, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE));

            return self::SUCCESS;
        } catch (Throwable $error) {
            $this->error($error->getMessage());

            return self::FAILURE;
        }
    }

    /**
     * @return array{list<array<string,mixed>>,string,array<string,int>,array<string,int>}
     */
    private function validatedManifest(Site $site, string $file, int $expected): array
    {
        if (! is_file($file) || ! is_readable($file)) {
            throw new RuntimeException('Full Bitrix catalogue manifest is missing or unreadable.');
        }
        try {
            $raw = file_get_contents($file);
            if ($raw === false) {
                throw new RuntimeException('Unable to read full Bitrix catalogue manifest.');
            }
            $manifest = json_decode($raw, true, 512, JSON_THROW_ON_ERROR);
        } catch (JsonException $error) {
            throw new RuntimeException('Full Bitrix catalogue manifest is invalid JSON.', previous: $error);
        }
        if (! is_array($manifest)
            || ($manifest['schema_version'] ?? null) !== 1
            || ($manifest['site_key'] ?? null) !== $site->key
            || ! is_array($manifest['summary'] ?? null)
            || ! is_array($manifest['records'] ?? null)) {
            throw new RuntimeException('Full Bitrix catalogue manifest schema or site key is invalid.');
        }
        $records = array_values($manifest['records']);
        if ($expected < 1 || count($records) !== $expected) {
            throw new RuntimeException("Expected {$expected} records; received ".count($records).'.');
        }

        $availableCategories = SiteCategory::query()
            ->where('site_id', $site->id)
            ->pluck('external_id')
            ->filter()
            ->flip();
        $seen = [];
        $statuses = [];
        $categories = [];
        foreach ($records as $index => $record) {
            if (! is_array($record)) {
                throw new RuntimeException('Manifest record '.($index + 1).' is not an object.');
            }
            foreach (['registry_id', 'bitrix_id', 'name', 'legacy_section_path', 'target_category_external_id', 'identity_status', 'transfer_status', 'source_checksum'] as $field) {
                if (! is_string($record[$field] ?? null) || trim($record[$field]) === '') {
                    throw new RuntimeException('Manifest record '.($index + 1)." misses {$field}.");
                }
            }
            $bitrixId = trim($record['bitrix_id']);
            $registryId = trim($record['registry_id']);
            $status = trim($record['transfer_status']);
            $category = trim($record['target_category_external_id']);
            if (! ctype_digit($bitrixId) || $registryId !== 'bitrix:'.$bitrixId || isset($seen[$bitrixId])) {
                throw new RuntimeException('Manifest record '.($index + 1).' has an invalid or duplicate Bitrix identity.');
            }
            if (! in_array($status, self::STATUSES, true) || ! $availableCategories->has($category)) {
                throw new RuntimeException("Manifest record {$registryId} has an unsupported status or category.");
            }
            foreach (['allow_publication', 'allow_indexing', 'allow_merge'] as $flag) {
                if (($record[$flag] ?? null) !== false) {
                    throw new RuntimeException("Manifest record {$registryId} must keep {$flag}=false.");
                }
            }
            $canCreate = $status === 'legacy_only_draft_candidate';
            if (($record['allow_product_create'] ?? null) !== $canCreate) {
                throw new RuntimeException("Manifest record {$registryId} has an inconsistent product-create gate.");
            }
            if (! preg_match('/^[a-f0-9]{64}$/', $record['source_checksum'])) {
                throw new RuntimeException("Manifest record {$registryId} has an invalid source checksum.");
            }
            $checksumPayload = $record;
            unset($checksumPayload['source_checksum']);
            ksort($checksumPayload);
            $expectedChecksum = hash('sha256', json_encode(
                $checksumPayload,
                JSON_THROW_ON_ERROR | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES,
            ));
            if (! hash_equals($expectedChecksum, $record['source_checksum'])) {
                throw new RuntimeException("Manifest record {$registryId} drifted from its source checksum.");
            }
            $electronic = $category === 'seo:electronic-components';
            if (($status === 'scope_excluded_electronics') !== $electronic) {
                throw new RuntimeException("Manifest record {$registryId} has an inconsistent electronics scope gate.");
            }
            if ($status === 'existing_one_c_exact_link' && blank($record['one_c_external_id'] ?? null)) {
                throw new RuntimeException("Exact link {$registryId} misses its 1C identity.");
            }
            $seen[$bitrixId] = true;
            $statuses[$status] = ($statuses[$status] ?? 0) + 1;
            if ($status !== 'excluded_inactive_legacy') {
                $categories[$category] = ($categories[$category] ?? 0) + 1;
            }
        }
        ksort($statuses);
        ksort($categories);
        if (($manifest['summary']['records'] ?? null) !== count($records)
            || ($manifest['summary']['status_counts'] ?? null) !== $statuses
            || ($manifest['summary']['active_category_counts'] ?? null) !== $categories
            || ($manifest['summary']['publication_changes'] ?? null) !== 0
            || ($manifest['summary']['indexable_urls'] ?? null) !== 0
            || ($manifest['summary']['merges'] ?? null) !== 0) {
            throw new RuntimeException('Manifest summary does not match the recomputed full-catalogue evidence.');
        }

        return [$records, $raw, $statuses, $categories];
    }
}
