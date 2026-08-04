<?php

namespace App\Console\Commands;

use App\Events\SiteContentChanged;
use App\Models\Site;
use App\Models\SiteCategory;
use App\Models\SiteProduct;
use App\Models\SiteUrl;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\DB;
use RuntimeException;
use Throwable;

class AdoptFullBitrixExactPreviewDescriptions extends Command
{
    private const SOURCE_KIND = 'legacy_bitrix_exact_element_preview';

    protected $signature = 'catalog:adopt-full-bitrix-exact-preview-descriptions
                            {site : Site key}
                            {file : Complete full-catalog Bitrix content CSV}
                            {--source-run= : Pinned full Bitrix staging run ID}
                            {--expected-records=21132 : Exact CSV record count}
                            {--expected-sha256= : Required SHA-256 of the CSV}
                            {--batch-size=500 : Maximum descriptions to attach in one cycle}
                            {--apply : Persist sanitized legacy preview descriptions; default is dry-run}';

    protected $description = 'Attach sanitized text from the exact same Bitrix element to noindex legacy preview products';

    public function handle(): int
    {
        try {
            $site = Site::query()->where('key', trim((string) $this->argument('site')))->sole();
            $sourceRunId = (int) $this->option('source-run');
            $batchSize = (int) $this->option('batch-size');
            $expectedRecords = (int) $this->option('expected-records');
            $expectedHash = strtolower(trim((string) $this->option('expected-sha256')));
            if ($sourceRunId < 1 || $batchSize < 1 || $batchSize > 1000 || $expectedRecords < 1) {
                throw new RuntimeException('A source run, positive expected record count and batch size between 1 and 1000 are required.');
            }
            if (preg_match('/^[a-f0-9]{64}$/', $expectedHash) !== 1) {
                throw new RuntimeException('A lowercase or uppercase 64-character --expected-sha256 is required.');
            }
            $this->assertSourceRun($site->key, $sourceRunId);

            $file = (string) $this->argument('file');
            if (! is_file($file) || ! is_readable($file)) {
                throw new RuntimeException('Full-catalog content CSV is missing or unreadable.');
            }
            $actualHash = hash_file('sha256', $file);
            if (! is_string($actualHash) || ! hash_equals($expectedHash, strtolower($actualHash))) {
                throw new RuntimeException('Full-catalog content CSV SHA-256 does not match the pinned value.');
            }
            $contentByLegacyId = $this->readContent($file, $expectedRecords);

            $rows = DB::table('catalog_draft_materializations as m')
                ->join('staged_import_records as full', 'full.id', '=', 'm.staged_import_record_id')
                ->join('site_products as sp', 'sp.id', '=', 'm.site_product_id')
                ->join('products as p', 'p.id', '=', 'm.product_id')
                ->join('site_urls as u', function ($join) use ($site): void {
                    $join->on('u.target_id', '=', 'sp.id')
                        ->where('u.site_id', '=', $site->id)
                        ->where('u.target_type', '=', 'product')
                        ->where('u.is_indexable', '=', false);
                })
                ->where('m.site_id', $site->id)
                ->where('m.source_import_run_id', $sourceRunId)
                ->whereIn('full.normalized_payload->transfer_status', [
                    'legacy_only_draft_candidate',
                    'hold_duplicate_candidate',
                    'hold_linked_identity_candidate',
                    'hold_one_c_collision',
                    'existing_one_c_exact_link',
                ])
                ->where('sp.is_published', true)
                ->where(function ($query): void {
                    $query->whereNull('p.short_description')->orWhereRaw("trim(p.short_description) = ''");
                })
                ->whereNotExists(function ($query): void {
                    $query->selectRaw('1')->from('product_description_drafts as d')
                        ->whereColumn('d.product_id', 'p.id')
                        ->where('d.source_kind', self::SOURCE_KIND);
                })
                ->orderBy('m.id')
                ->get(['p.id as product_id', 'p.name', 'm.source_external_id', 'full.payload as full_payload'])
                ->map(function ($row) use ($contentByLegacyId): ?object {
                    $legacyId = $this->legacyId((string) $row->source_external_id);
                    $source = $contentByLegacyId[$legacyId] ?? null;
                    if ($source === null || $source['content'] === '') {
                        return null;
                    }
                    if ($this->normalizedName((string) $row->name) !== $this->normalizedName($source['name'])) {
                        throw new RuntimeException("Bitrix element {$legacyId} name does not match the materialized product.");
                    }
                    $payload = json_decode((string) $row->full_payload, true, 512, JSON_THROW_ON_ERROR);
                    $row->legacy_id = $legacyId;
                    $row->content = $source['content'];
                    $row->legacy_url = (string) ($payload['legacy_url'] ?? '');

                    return $row;
                })
                ->filter()
                ->values();

            $selected = $rows->take($batchSize);
            $summary = [
                'mode' => $this->option('apply') ? 'apply' : 'dry_run',
                'source_run_id' => $sourceRunId,
                'source_file_sha256' => $actualHash,
                'content_csv_records' => count($contentByLegacyId),
                'eligible_missing_legacy_descriptions' => $rows->count(),
                'selected_batch' => $selected->count(),
                'remaining_after' => $rows->count() - $selected->count(),
                'legacy_preview_descriptions_created' => 0,
                'revalidation_batches' => 0,
                'manufacturer_verified_descriptions_created' => 0,
                'indexable_pages_changed' => 0,
            ];

            if ($this->option('apply') && $selected->isNotEmpty()) {
                DB::transaction(function () use ($selected, $site): void {
                    $now = now();
                    $draftRows = [];
                    foreach ($selected as $row) {
                        DB::table('products')->where('id', $row->product_id)->update([
                            'short_description' => $row->content,
                            'updated_at' => $now,
                        ]);
                        $draftRows[] = [
                            'product_id' => $row->product_id,
                            'staged_import_record_id' => null,
                            'locale' => $site->default_locale,
                            'title' => $row->name,
                            'content' => $row->content,
                            'verified_fields' => json_encode([], JSON_THROW_ON_ERROR),
                            'source_urls' => json_encode(array_values(array_filter([
                                $row->legacy_url,
                                'bitrix-backup://element/'.$row->legacy_id,
                            ])), JSON_THROW_ON_ERROR),
                            'source_kind' => self::SOURCE_KIND,
                            'source_tier' => 'company_owned_legacy_preview',
                            'source_publisher' => 'microchips.by legacy Bitrix',
                            'manufacturer_primary' => null,
                            'identity_scope' => 'exact_legacy_element',
                            'source_checked_at' => now()->toDateString(),
                            'status' => 'legacy_preview_applied',
                            'rejection_reason' => null,
                            'submitted_by' => null,
                            'submitted_at' => null,
                            'created_at' => $now,
                            'updated_at' => $now,
                        ];
                    }
                    DB::table('product_description_drafts')->insert($draftRows);
                });
                $summary['legacy_preview_descriptions_created'] = $selected->count();
                $summary['revalidation_batches'] = $this->revalidateAffected(
                    $site,
                    $selected->pluck('product_id')->map(static fn (mixed $id): int => (int) $id)->all(),
                );
            }

            $this->line(json_encode($summary, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES));

            return self::SUCCESS;
        } catch (Throwable $error) {
            $this->error($error->getMessage());

            return self::FAILURE;
        }
    }

    private function assertSourceRun(string $siteKey, int $runId): void
    {
        $run = DB::table('import_runs')->where('id', $runId)->first();
        if ($run === null
            || $run->source !== 'bitrix_full_catalog_snapshot:'.$siteKey
            || $run->status !== 'completed'
            || (int) $run->failed_records !== 0) {
            throw new RuntimeException('Source run is not a completed zero-failure full Bitrix snapshot for this site.');
        }
    }

    /** @return array<int, array{name: string, content: string}> */
    private function readContent(string $file, int $expectedRecords): array
    {
        $handle = fopen($file, 'rb');
        if ($handle === false) {
            throw new RuntimeException('Unable to open full-catalog content CSV.');
        }

        try {
            $rawHeader = fgets($handle);
            if ($rawHeader === false) {
                throw new RuntimeException('Full-catalog content CSV is empty.');
            }
            $rawHeader = preg_replace('/^\xEF\xBB\xBF/', '', $rawHeader) ?? $rawHeader;
            $header = array_map(static fn (?string $value): string => trim((string) $value), str_getcsv($rawHeader, ',', '"', ''));
            $required = ['legacy_element_id', 'name', 'preview_text', 'detail_text'];
            foreach ($required as $column) {
                if (count(array_keys($header, $column, true)) !== 1) {
                    throw new RuntimeException("Full-catalog content CSV must contain exactly one {$column} column.");
                }
            }
            $positions = array_flip($header);
            $records = [];
            $rowNumber = 1;
            while (($row = fgetcsv($handle, 0, ',', '"', '')) !== false) {
                $rowNumber++;
                if (count($row) !== count($header)) {
                    throw new RuntimeException("Malformed full-catalog content CSV row {$rowNumber}.");
                }
                $legacyId = trim((string) $row[$positions['legacy_element_id']]);
                if ($legacyId === '' || ! ctype_digit($legacyId) || isset($records[(int) $legacyId])) {
                    throw new RuntimeException("Invalid or duplicate legacy_element_id at CSV row {$rowNumber}.");
                }
                $detail = (string) $row[$positions['detail_text']];
                $preview = (string) $row[$positions['preview_text']];
                $records[(int) $legacyId] = [
                    'name' => (string) $row[$positions['name']],
                    'content' => $this->plainText($detail !== '' ? $detail : $preview),
                ];
            }
        } finally {
            fclose($handle);
        }

        if (count($records) !== $expectedRecords) {
            throw new RuntimeException("Expected {$expectedRecords} full-catalog content rows; received ".count($records).'.');
        }

        return $records;
    }

    private function legacyId(string $externalId): int
    {
        if (preg_match('/^bitrix:(\d+)$/', $externalId, $match) !== 1) {
            throw new RuntimeException("Unexpected Bitrix external ID {$externalId}.");
        }

        return (int) $match[1];
    }

    private function normalizedName(string $value): string
    {
        $value = html_entity_decode($value, ENT_QUOTES | ENT_HTML5, 'UTF-8');
        $value = preg_replace('/\s+/u', ' ', $value) ?? '';

        return mb_strtolower(trim($value));
    }

    private function plainText(string $html): string
    {
        $html = preg_replace('#<(script|style)[^>]*>.*?</\1>#is', ' ', $html) ?? '';
        $html = preg_replace('#<(br|/p|/li|/h[1-6]|/tr|/td)\b[^>]*>#i', ' ', $html) ?? $html;
        $text = html_entity_decode(strip_tags($html), ENT_QUOTES | ENT_HTML5, 'UTF-8');
        $text = preg_replace('/[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]/u', ' ', $text) ?? '';
        $text = preg_replace('/\s+/u', ' ', $text) ?? '';

        return trim(mb_substr($text, 0, 4000));
    }

    /** @param list<int> $productIds */
    private function revalidateAffected(Site $site, array $productIds): int
    {
        $siteProductIds = SiteProduct::query()
            ->where('site_id', $site->id)
            ->whereIn('product_id', array_values(array_unique($productIds)))
            ->pluck('id');
        $paths = SiteUrl::query()
            ->where('site_id', $site->id)
            ->where('target_type', 'product')
            ->whereIn('target_id', $siteProductIds)
            ->pluck('path');
        $categoryIds = DB::table('site_category_product')
            ->where('site_id', $site->id)
            ->whereIn('site_product_id', $siteProductIds)
            ->pluck('site_category_id')
            ->map(static fn (mixed $id): int => (int) $id)
            ->unique()
            ->all();
        $paths = $paths
            ->merge(SiteCategory::revalidationPaths($site->id, $categoryIds))
            ->push('/catalog')
            ->filter(static fn (mixed $path): bool => is_string($path) && str_starts_with($path, '/'))
            ->unique()
            ->values();

        $batches = 0;
        foreach ($paths->chunk(100) as $batch) {
            SiteContentChanged::dispatch($site, $batch->values()->all());
            $batches++;
        }

        return $batches;
    }
}
