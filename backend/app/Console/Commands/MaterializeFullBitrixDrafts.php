<?php

namespace App\Console\Commands;

use App\Domain\Imports\ProductIdentity;
use App\Models\CatalogDraftMaterialization;
use App\Models\ImportRun;
use App\Models\Product;
use App\Models\Site;
use App\Models\SiteCategory;
use App\Models\SiteProduct;
use App\Models\StagedImportRecord;
use Illuminate\Console\Command;
use Illuminate\Database\Eloquent\Builder;
use Illuminate\Support\Collection;
use Illuminate\Support\Facades\DB;
use RuntimeException;
use Throwable;

class MaterializeFullBitrixDrafts extends Command
{
    protected $signature = 'catalog:materialize-full-bitrix-drafts
                            {site : Site key}
                            {--source-run= : Full Bitrix staging run ID; defaults to the latest matching run}
                            {--source-manifest-sha256= : Required SHA-256 of the pinned source manifest}
                            {--expected-source-records=17207 : Exact number of rows in the pinned source run}
                            {--expected-candidates=16173 : Exact number of rows eligible under the selected policy}
                            {--batch-size=1000 : Number of missing namespaced drafts to create in this cycle}
                            {--include-held-as-namespaced-drafts : Preserve held legacy rows as separate review drafts without merging}
                            {--apply : Persist the bounded draft batch; default is dry-run}';

    protected $description = 'Create unpublished namespaced Product/SiteProduct drafts from the full Bitrix staging evidence';

    private const BASE_STATUS = 'legacy_only_draft_candidate';

    private const HELD_STATUSES = [
        'hold_duplicate_candidate',
        'hold_linked_identity_candidate',
        'hold_one_c_collision',
    ];

    public function handle(): int
    {
        try {
            $site = Site::query()->where('key', trim((string) $this->argument('site')))->sole();
            $sourceRun = $this->sourceRun($site);
            $batchSize = (int) $this->option('batch-size');
            if ($batchSize < 1 || $batchSize > 2000) {
                throw new RuntimeException('Batch size must be between 1 and 2000.');
            }
            $statuses = [self::BASE_STATUS];
            if ((bool) $this->option('include-held-as-namespaced-drafts')) {
                $statuses = [...$statuses, ...self::HELD_STATUSES];
            }
            $eligibleQuery = StagedImportRecord::query()
                ->where('import_run_id', $sourceRun->id)
                ->where('entity_type', 'bitrix_full_catalog_product_evidence')
                ->whereIn('normalized_payload->transfer_status', $statuses);
            $expectedCandidates = (int) $this->option('expected-candidates');
            $eligibleCount = (clone $eligibleQuery)->count();
            if ($expectedCandidates < 1 || $eligibleCount !== $expectedCandidates) {
                throw new RuntimeException("Expected {$expectedCandidates} eligible rows; received {$eligibleCount}.");
            }
            $this->assertSourceSet($site, $sourceRun, $eligibleQuery, $statuses, $eligibleCount);
            $alreadyMaterialized = CatalogDraftMaterialization::query()
                ->where('site_id', $site->id)
                ->where('source_import_run_id', $sourceRun->id)
                ->where('materialization_kind', CatalogDraftMaterialization::KIND_NAMESPACED_DRAFT)
                ->count();
            $selected = (clone $eligibleQuery)
                ->whereNotExists(function ($query) use ($site, $sourceRun): void {
                    $query->selectRaw('1')
                        ->from('catalog_draft_materializations as materialized')
                        ->whereColumn('materialized.staged_import_record_id', 'staged_import_records.id')
                        ->where('materialized.site_id', $site->id)
                        ->where('materialized.source_import_run_id', $sourceRun->id);
                })
                ->orderBy('row_number')
                ->limit($batchSize)
                ->get();
            $this->assertSelectedRows($site, $selected, $statuses);
            $remainingBefore = $eligibleCount - $alreadyMaterialized;
            $summary = [
                'mode' => $this->option('apply') ? 'apply' : 'dry_run',
                'site' => $site->key,
                'source_run_id' => $sourceRun->id,
                'source_manifest_sha256' => $sourceRun->summary['manifest_sha256'],
                'eligible_rows' => $eligibleCount,
                'already_materialized' => $alreadyMaterialized,
                'selected_batch' => $selected->count(),
                'remaining_before' => $remainingBefore,
                'remaining_after' => $remainingBefore - $selected->count(),
                'held_rows_included' => (bool) $this->option('include-held-as-namespaced-drafts'),
                'products_created' => $selected->count(),
                'site_products_created' => $selected->count(),
                'category_links_created' => $selected->count(),
                'publication_changes' => 0,
                'urls_created' => 0,
                'indexable_urls' => 0,
                'merges' => 0,
            ];

            if (! $this->option('apply') || $selected->isEmpty()) {
                $this->line(json_encode($summary, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE));

                return self::SUCCESS;
            }

            DB::transaction(function () use ($selected, $site, $sourceRun, $summary): void {
                if (DB::getDriverName() === 'pgsql') {
                    DB::select('select pg_advisory_xact_lock(hashtext(?))', [
                        'bitrix-draft-materialization:'.$site->key.':'.$sourceRun->id,
                    ]);
                }
                $categoryIds = SiteCategory::query()
                    ->where('site_id', $site->id)
                    ->whereIn('external_id', $selected->pluck('normalized_payload.target_category_external_id')->unique()->all())
                    ->pluck('id', 'external_id');
                $now = now();
                $run = ImportRun::query()->create([
                    'source' => 'bitrix_full_catalog_draft_materialization:'.$site->key,
                    'status' => 'completed',
                    'source_file' => $sourceRun->source_file,
                    'total_records' => $selected->count(),
                    'processed_records' => $selected->count(),
                    'failed_records' => 0,
                    'summary' => $summary,
                    'started_at' => $now,
                    'finished_at' => $now,
                ]);
                $productRows = [];
                foreach ($selected as $sourceRow) {
                    $payload = $sourceRow->payload;
                    $externalId = $sourceRow->external_id;
                    $bitrixId = $payload['bitrix_id'];
                    $slug = 'legacy-bitrix-'.$bitrixId;
                    $productRows[] = [
                        'external_id' => $externalId,
                        'external_id_normalized' => ProductIdentity::normalize($externalId),
                        'sku' => null,
                        'sku_normalized' => null,
                        'mpn' => null,
                        'mpn_normalized' => null,
                        'manufacturer' => null,
                        'slug' => $slug,
                        'name' => $payload['name'],
                        'short_description' => null,
                        'technical_attributes' => json_encode([
                            'legacy_migration_provenance' => [
                                'source' => 'bitrix',
                                'source_run_id' => $sourceRun->id,
                                'bitrix_id' => $bitrixId,
                                'legacy_url' => $payload['legacy_url'],
                                'legacy_section_path' => $payload['legacy_section_path'],
                                'source_checksum' => $payload['source_checksum'],
                                'identity_status' => $payload['identity_status'],
                                'transfer_status' => $payload['transfer_status'],
                                'verification_status' => 'needs_review',
                            ],
                        ], JSON_THROW_ON_ERROR | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES),
                        'status' => 'draft',
                        'created_at' => $now,
                        'updated_at' => $now,
                    ];
                }
                DB::table('products')->insert($productRows);

                $products = Product::query()
                    ->whereIn('external_id', $selected->pluck('external_id')->all())
                    ->get(['id', 'external_id'])
                    ->keyBy('external_id');
                $siteProductRows = [];
                foreach ($selected as $sourceRow) {
                    $product = $products->get($sourceRow->external_id);
                    if ($product === null) {
                        throw new RuntimeException("Draft product {$sourceRow->external_id} was not inserted.");
                    }
                    $siteProductRows[] = [
                        'site_id' => $site->id,
                        'product_id' => $product->id,
                        'slug' => 'legacy-bitrix-'.$sourceRow->payload['bitrix_id'],
                        'is_published' => false,
                        'availability' => 'on_request',
                        'price' => null,
                        'seo' => json_encode([
                            'migration_status' => 'needs_review',
                            'source' => 'bitrix',
                        ], JSON_THROW_ON_ERROR),
                        'sort_order' => 0,
                        'created_at' => $now,
                        'updated_at' => $now,
                    ];
                }
                DB::table('site_products')->insert($siteProductRows);
                $siteProducts = SiteProduct::query()
                    ->where('site_id', $site->id)
                    ->whereIn('product_id', $products->pluck('id')->all())
                    ->get(['id', 'product_id'])
                    ->keyBy('product_id');

                $pivotRows = [];
                foreach ($selected as $sourceRow) {
                    $product = $products->get($sourceRow->external_id);
                    $siteProduct = $product === null ? null : $siteProducts->get($product->id);
                    $category = $categoryIds->get($sourceRow->normalized_payload['target_category_external_id']);
                    if ($siteProduct === null || $category === null) {
                        throw new RuntimeException("Draft {$sourceRow->external_id} misses its site product or category.");
                    }
                    $pivotRows[] = [
                        'site_id' => $site->id,
                        'site_category_id' => $category,
                        'site_product_id' => $siteProduct->id,
                        'created_at' => $now,
                        'updated_at' => $now,
                    ];
                }
                DB::table('site_category_product')->insert($pivotRows);
                $evidenceRows = [];
                $lineageRows = [];
                foreach ($selected as $offset => $sourceRow) {
                    $product = $products->get($sourceRow->external_id);
                    $siteProduct = $product === null ? null : $siteProducts->get($product->id);
                    $evidenceRows[] = [
                        'import_run_id' => $run->id,
                        'row_number' => $offset + 1,
                        'entity_type' => 'bitrix_full_catalog_draft_materialization',
                        'external_id' => $sourceRow->external_id,
                        'payload' => json_encode([
                            'source_run_id' => $sourceRun->id,
                            'source_row_id' => $sourceRow->id,
                            'source_checksum' => $sourceRow->payload['source_checksum'],
                            'product_id' => $product?->id,
                            'site_product_id' => $siteProduct?->id,
                            'target_category_external_id' => $sourceRow->normalized_payload['target_category_external_id'],
                        ], JSON_THROW_ON_ERROR | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES),
                        'normalized_payload' => json_encode([
                            'site_id' => $site->id,
                            'source_run_id' => $sourceRun->id,
                            'product_id' => $product?->id,
                            'site_product_id' => $siteProduct?->id,
                            'materialization_status' => 'draft_created',
                        ], JSON_THROW_ON_ERROR),
                        'validation_errors' => json_encode([], JSON_THROW_ON_ERROR),
                        'status' => 'draft_materialized',
                        'error' => null,
                        'review_note' => 'Namespaced Bitrix preservation draft; not merged, published or indexed.',
                        'created_at' => $now,
                        'updated_at' => $now,
                    ];
                    $lineageRows[] = [
                        'materialization_run_id' => $run->id,
                        'source_import_run_id' => $sourceRun->id,
                        'staged_import_record_id' => $sourceRow->id,
                        'site_id' => $site->id,
                        'product_id' => $product?->id,
                        'site_product_id' => $siteProduct?->id,
                        'source_namespace' => 'bitrix',
                        'source_external_id' => $sourceRow->external_id,
                        'source_checksum' => $sourceRow->payload['source_checksum'],
                        'materialization_kind' => CatalogDraftMaterialization::KIND_NAMESPACED_DRAFT,
                        'target_category_external_id' => $sourceRow->normalized_payload['target_category_external_id'],
                        'created_at' => $now,
                        'updated_at' => $now,
                    ];
                }
                StagedImportRecord::query()->insert($evidenceRows);
                DB::table('catalog_draft_materializations')->insert($lineageRows);
            });

            $this->line(json_encode($summary, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE));

            return self::SUCCESS;
        } catch (Throwable $error) {
            $this->error($error->getMessage());

            return self::FAILURE;
        }
    }

    private function sourceRun(Site $site): ImportRun
    {
        $query = ImportRun::query()->where('source', 'bitrix_full_catalog_snapshot:'.$site->key);
        $runId = trim((string) $this->option('source-run'));
        $run = $runId === '' ? $query->latest('id')->first() : $query->whereKey($runId)->first();
        $expectedHash = trim((string) $this->option('source-manifest-sha256'));
        $expectedRecords = (int) $this->option('expected-source-records');
        if (! preg_match('/^[a-f0-9]{64}$/', $expectedHash) || $expectedRecords < 1) {
            throw new RuntimeException('Pinned source manifest SHA-256 and expected source count are required.');
        }
        if ($run === null
            || $run->status !== 'completed'
            || $run->failed_records !== 0
            || ($run->summary['manifest_sha256'] ?? null) !== $expectedHash
            || $run->total_records !== $expectedRecords
            || StagedImportRecord::query()->where('import_run_id', $run->id)->count() !== $run->total_records) {
            throw new RuntimeException('Full Bitrix source run is missing, incomplete or drifted.');
        }

        return $run;
    }

    /** @param list<string> $statuses */
    private function assertSourceSet(
        Site $site,
        ImportRun $sourceRun,
        Builder $eligibleQuery,
        array $statuses,
        int $eligibleCount,
    ): void {
        $isPostgres = DB::getDriverName() === 'pgsql';
        $jsonText = static fn (string $column, string $key): string => $isPostgres
            ? "{$column}->>'{$key}'"
            : "json_extract({$column}, '$.{$key}')";
        $expectedFalse = $isPostgres ? 'false' : 0;
        $allowPublication = $jsonText('payload', 'allow_publication');
        $allowIndexing = $jsonText('payload', 'allow_indexing');
        $allowMerge = $jsonText('payload', 'allow_merge');
        $payloadChecksum = $jsonText('payload', 'source_checksum');
        $normalizedChecksum = $jsonText('normalized_payload', 'source_checksum');

        $invalidContractRows = (clone $eligibleQuery)
            ->where(function ($query) use (
                $allowPublication,
                $allowIndexing,
                $allowMerge,
                $payloadChecksum,
                $normalizedChecksum,
                $expectedFalse,
            ): void {
                $query->where('status', '!=', 'staged_evidence')
                    ->orWhereRaw("{$allowPublication} IS NULL OR {$allowPublication} <> ?", [$expectedFalse])
                    ->orWhereRaw("{$allowIndexing} IS NULL OR {$allowIndexing} <> ?", [$expectedFalse])
                    ->orWhereRaw("{$allowMerge} IS NULL OR {$allowMerge} <> ?", [$expectedFalse])
                    ->orWhereRaw("{$payloadChecksum} IS NULL OR {$normalizedChecksum} IS NULL OR {$payloadChecksum} <> {$normalizedChecksum}");
            })
            ->count();
        if ($invalidContractRows !== 0) {
            throw new RuntimeException("Source run contains {$invalidContractRows} rows outside the guarded staging contract.");
        }

        $categoryIds = (clone $eligibleQuery)
            ->selectRaw("DISTINCT normalized_payload->>'target_category_external_id' AS category_external_id")
            ->pluck('category_external_id')
            ->sort()
            ->values()
            ->all();
        $available = SiteCategory::query()
            ->where('site_id', $site->id)
            ->whereIn('external_id', $categoryIds)
            ->pluck('external_id')
            ->sort()
            ->values()
            ->all();
        if ($available !== $categoryIds) {
            throw new RuntimeException('One or more full-catalogue target categories are missing from the site.');
        }

        $rogueProducts = DB::table('products as products')
            ->join('staged_import_records as source_rows', 'source_rows.external_id', '=', 'products.external_id')
            ->leftJoin('catalog_draft_materializations as materialized', function ($join) use ($site, $sourceRun): void {
                $join->on('materialized.product_id', '=', 'products.id')
                    ->where('materialized.site_id', '=', $site->id)
                    ->where('materialized.source_import_run_id', '=', $sourceRun->id);
            })
            ->where('source_rows.import_run_id', $sourceRun->id)
            ->whereIn(DB::raw("source_rows.normalized_payload->>'transfer_status'"), $statuses)
            ->whereNull('materialized.id')
            ->count();
        if ($rogueProducts !== 0) {
            throw new RuntimeException("Found {$rogueProducts} untracked namespaced Products; materialization was blocked.");
        }

        $lineageCount = CatalogDraftMaterialization::query()
            ->where('site_id', $site->id)
            ->where('source_import_run_id', $sourceRun->id)
            ->where('materialization_kind', CatalogDraftMaterialization::KIND_NAMESPACED_DRAFT)
            ->count();
        if ($lineageCount > $eligibleCount) {
            throw new RuntimeException('Draft lineage exceeds the pinned eligible source set.');
        }
        $stableLineageCount = DB::table('catalog_draft_materializations as materialized')
            ->join('products as products', 'products.id', '=', 'materialized.product_id')
            ->join('site_products as site_products', function ($join) use ($site): void {
                $join->on('site_products.id', '=', 'materialized.site_product_id')
                    ->on('site_products.product_id', '=', 'products.id')
                    ->where('site_products.site_id', '=', $site->id);
            })
            ->join('site_category_product as links', function ($join) use ($site): void {
                $join->on('links.site_product_id', '=', 'site_products.id')
                    ->where('links.site_id', '=', $site->id);
            })
            ->join('site_categories as categories', function ($join): void {
                $join->on('categories.id', '=', 'links.site_category_id')
                    ->whereColumn('categories.external_id', 'materialized.target_category_external_id');
            })
            ->where('materialized.site_id', $site->id)
            ->where('materialized.source_import_run_id', $sourceRun->id)
            ->where('materialized.materialization_kind', CatalogDraftMaterialization::KIND_NAMESPACED_DRAFT)
            ->distinct('materialized.id')
            ->count('materialized.id');
        if ($stableLineageCount !== $lineageCount) {
            throw new RuntimeException('Existing draft lineage, Product, SiteProduct or category links drifted.');
        }
    }

    /** @param Collection<int,StagedImportRecord> $rows
     * @param  list<string>  $statuses
     */
    private function assertSelectedRows(Site $site, Collection $rows, array $statuses): void
    {
        if ($rows->isEmpty()) {
            return;
        }
        $categoryIds = $rows->pluck('normalized_payload.target_category_external_id')->unique()->values()->all();
        $available = SiteCategory::query()
            ->where('site_id', $site->id)
            ->whereIn('external_id', $categoryIds)
            ->pluck('external_id')
            ->sort()
            ->values()
            ->all();
        sort($categoryIds);
        if ($available !== $categoryIds) {
            throw new RuntimeException('One or more full-catalogue target categories are missing from the site.');
        }
        foreach ($rows as $row) {
            $status = $row->normalized_payload['transfer_status'] ?? null;
            if (! in_array($status, $statuses, true)
                || $row->external_id !== 'bitrix:'.($row->payload['bitrix_id'] ?? '')
                || ($row->payload['allow_publication'] ?? null) !== false
                || ($row->payload['allow_indexing'] ?? null) !== false
                || ($row->payload['allow_merge'] ?? null) !== false
                || $row->status !== 'staged_evidence'
                || ($row->normalized_payload['source_checksum'] ?? null) !== ($row->payload['source_checksum'] ?? null)) {
                throw new RuntimeException("Source row {$row->id} drifted from the guarded staging contract.");
            }
            $checksumPayload = $row->payload;
            unset($checksumPayload['source_checksum']);
            ksort($checksumPayload);
            $checksum = hash('sha256', json_encode(
                $checksumPayload,
                JSON_THROW_ON_ERROR | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES,
            ));
            if (! hash_equals($checksum, $row->payload['source_checksum'])) {
                throw new RuntimeException("Source row {$row->id} checksum drifted.");
            }
        }
    }
}
