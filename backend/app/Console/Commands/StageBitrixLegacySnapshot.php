<?php

namespace App\Console\Commands;

use App\Models\ImportRun;
use App\Models\Product;
use App\Models\Site;
use App\Models\SiteProduct;
use App\Models\StagedImportRecord;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\DB;
use JsonException;
use RuntimeException;

class StageBitrixLegacySnapshot extends Command
{
    protected $signature = 'catalog:stage-bitrix-legacy-snapshot
                            {site : Site key}
                            {file : Complete JSON staging manifest}
                            {--expected-records=1569 : Exact expected record count}
                            {--apply : Persist evidence; default is dry-run}';

    protected $description = 'Preserve a complete Bitrix catalogue snapshot as non-renderable staging evidence';

    /** @var list<string> */
    private const STATUSES = [
        'strict_mapped_evidence',
        'candidate_mapped_evidence',
        'candidate_duplicate_group',
        'hold_missing_1c_identity',
        'hold_missing_rb_site_product',
        'scope_excluded_electronics',
        'excluded_inactive_legacy',
    ];

    public function handle(): int
    {
        $site = Site::query()->where('key', trim((string) $this->argument('site')))->first();
        if ($site === null) {
            $this->error('Unknown site key.');

            return self::FAILURE;
        }

        $file = (string) $this->argument('file');
        if (! is_file($file) || ! is_readable($file)) {
            $this->error('Manifest is missing or unreadable.');

            return self::FAILURE;
        }

        try {
            $raw = file_get_contents($file);
            if ($raw === false) {
                throw new RuntimeException('Unable to read manifest.');
            }
            $payload = json_decode($raw, true, 512, JSON_THROW_ON_ERROR);
            $records = $this->validateManifest($payload, $site, (int) $this->option('expected-records'));
        } catch (JsonException|RuntimeException $exception) {
            $this->error($exception->getMessage());

            return self::FAILURE;
        }

        $hash = hash('sha256', $raw);
        $statusCounts = array_count_values(array_column($records, 'transfer_status'));
        ksort($statusCounts);
        $source = 'bitrix_legacy_snapshot:'.$site->key;
        $existing = ImportRun::query()
            ->where('source', $source)
            ->latest('id')
            ->first();
        $unchanged = $existing !== null
            && ($existing->summary['manifest_sha256'] ?? null) === $hash
            && $existing->total_records === count($records);

        $summary = [
            'mode' => $this->option('apply') ? 'apply' : 'dry_run',
            'site' => $site->key,
            'records' => count($records),
            'status_counts' => $statusCounts,
            'manifest_sha256' => $hash,
            'renderable_rows' => 0,
            'publication_changes' => 0,
            'unchanged' => $unchanged,
        ];

        if (! $this->option('apply') || $unchanged) {
            $this->line(json_encode($summary, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE));

            return self::SUCCESS;
        }

        DB::transaction(function () use ($file, $hash, $records, $site, $source, $statusCounts): void {
            $run = ImportRun::query()->create([
                'source' => $source,
                'status' => 'completed',
                'source_file' => basename($file),
                'total_records' => count($records),
                'processed_records' => count($records),
                'failed_records' => 0,
                'summary' => [
                    'site_id' => $site->id,
                    'manifest_sha256' => $hash,
                    'status_counts' => $statusCounts,
                    'renderable_rows' => 0,
                    'publication_changes' => 0,
                ],
                'started_at' => now(),
                'finished_at' => now(),
            ]);

            foreach (array_chunk($records, 100) as $chunkOffset => $chunk) {
                $rows = [];
                foreach ($chunk as $offset => $record) {
                    $rows[] = [
                        'import_run_id' => $run->id,
                        'row_number' => ($chunkOffset * 100) + $offset + 1,
                        'entity_type' => 'bitrix_legacy_product_evidence',
                        'external_id' => 'bitrix:'.$record['legacy_element_id'],
                        'payload' => json_encode($record, JSON_THROW_ON_ERROR | JSON_UNESCAPED_UNICODE),
                        'normalized_payload' => json_encode([
                            'site_id' => $site->id,
                            'one_c_external_id' => $record['one_c_external_id'],
                            'transfer_status' => $record['transfer_status'],
                            'legacy_text_sha256' => $record['legacy_text_sha256'],
                        ], JSON_THROW_ON_ERROR | JSON_UNESCAPED_UNICODE),
                        'validation_errors' => json_encode([], JSON_THROW_ON_ERROR),
                        'status' => 'staged_evidence',
                        'error' => null,
                        'review_note' => 'Legacy snapshot only: never render or publish without a later reviewed decision.',
                        'created_at' => now(),
                        'updated_at' => now(),
                    ];
                }
                StagedImportRecord::query()->insert($rows);
            }
        });

        $this->line(json_encode($summary, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE));

        return self::SUCCESS;
    }

    /** @return list<array<string, mixed>> */
    private function validateManifest(mixed $payload, Site $site, int $expected): array
    {
        if (! is_array($payload) || ($payload['schema_version'] ?? null) !== 1 || ! is_array($payload['records'] ?? null)) {
            throw new RuntimeException('Manifest must use schema_version 1 and contain records.');
        }
        $records = array_values($payload['records']);
        if ($expected < 1 || count($records) !== $expected) {
            throw new RuntimeException("Expected {$expected} records; received ".count($records).'.');
        }

        $legacyIds = [];
        $mappedExternalIds = [];
        foreach ($records as $index => $record) {
            if (! is_array($record)) {
                throw new RuntimeException('Record '.($index + 1).' is not an object.');
            }
            $legacyId = trim((string) ($record['legacy_element_id'] ?? ''));
            $status = trim((string) ($record['transfer_status'] ?? ''));
            $oneC = trim((string) ($record['one_c_external_id'] ?? ''));
            if ($legacyId === '' || ! ctype_digit($legacyId) || isset($legacyIds[$legacyId])) {
                throw new RuntimeException('Invalid or duplicate legacy_element_id at record '.($index + 1).'.');
            }
            if (! in_array($status, self::STATUSES, true)) {
                throw new RuntimeException('Unknown transfer_status at record '.($index + 1).'.');
            }
            if (($record['render_legacy_html'] ?? null) !== false || ($record['change_publication'] ?? null) !== false) {
                throw new RuntimeException('Legacy HTML rendering and publication changes must be false.');
            }
            if ($status === 'hold_missing_1c_identity' && $oneC !== '') {
                throw new RuntimeException('Missing-identity row unexpectedly contains a 1C identity.');
            }
            if ($status !== 'hold_missing_1c_identity' && $status !== 'excluded_inactive_legacy' && $oneC !== '') {
                $mappedExternalIds[$oneC] = true;
            }
            $legacyIds[$legacyId] = true;
        }

        if ($mappedExternalIds !== []) {
            $productIds = Product::query()
                ->whereIn('external_id', array_keys($mappedExternalIds))
                ->pluck('id', 'external_id');
            $linkedProductIds = SiteProduct::query()
                ->where('site_id', $site->id)
                ->whereIn('product_id', $productIds->values()->all())
                ->pluck('product_id')
                ->flip();
            foreach (array_keys($mappedExternalIds) as $externalId) {
                $productId = $productIds->get($externalId);
                if ($productId === null || ! $linkedProductIds->has($productId)) {
                    // The manifest may explicitly preserve this as a hold, but
                    // no mapped/applicable row may pretend the site link exists.
                    $statuses = array_unique(array_column(array_filter(
                        $records,
                        fn (array $record): bool => ($record['one_c_external_id'] ?? null) === $externalId
                    ), 'transfer_status'));
                    if ($statuses !== ['hold_missing_rb_site_product']) {
                        throw new RuntimeException("1C product {$externalId} is not linked to site {$site->key}.");
                    }
                }
            }
        }

        return $records;
    }
}
