<?php

namespace App\Console\Commands;

use App\Events\SiteContentChanged;
use App\Models\CatalogDraftMaterialization;
use App\Models\ImportRun;
use App\Models\Site;
use App\Models\SiteRedirect;
use App\Models\SiteSeo;
use App\Models\SiteUrl;
use App\Models\StagedImportRecord;
use Illuminate\Console\Command;
use Illuminate\Support\Collection;
use Illuminate\Support\Facades\DB;
use RuntimeException;
use Throwable;

class RestoreFullBitrixLegacyPreviewRedirects extends Command
{
    private const ALLOWED_PREVIEW_STATUSES = [
        'legacy_only_draft_candidate',
        'hold_duplicate_candidate',
        'hold_linked_identity_candidate',
        'hold_one_c_collision',
    ];

    protected $signature = 'catalog:restore-full-bitrix-legacy-preview-redirects
                            {site : Site key}
                            {--source-run= : Required pinned full Bitrix staging run ID}
                            {--source-manifest-sha256= : Required SHA-256 of the pinned source manifest}
                            {--expected-source-records=17207 : Exact source row count}
                            {--batch-size=1000 : Maximum missing redirects to restore in this cycle}
                            {--apply : Persist the preview redirects; default is a dry-run}';

    protected $description = 'Restore original Bitrix product URLs to their materialized published noindex preview URLs';

    public function handle(): int
    {
        try {
            $site = Site::query()->where('key', trim((string) $this->argument('site')))->sole();
            $this->assertExactLegacyHost($site);
            $sourceRun = $this->pinnedSourceRun($site);
            $batchSize = (int) $this->option('batch-size');
            if ($batchSize < 1 || $batchSize > 2000) {
                throw new RuntimeException('Batch size must be between 1 and 2000.');
            }

            $plan = $this->buildPlan($site, $sourceRun, $batchSize);
            $restored = 0;
            if ((bool) $this->option('apply') && $plan['selected']->isNotEmpty()) {
                DB::transaction(function () use ($site, $sourceRun, $plan, &$restored): void {
                    if (DB::getDriverName() === 'pgsql') {
                        DB::select('select pg_advisory_xact_lock(hashtext(?))', [
                            'full-bitrix-legacy-preview-redirects:'.$site->key.':'.$sourceRun->id,
                        ]);
                    }

                    $this->assertSelectedBatchStillSafe($site, $plan['selected']);
                    $now = now();
                    DB::table('site_redirects')->insert($plan['selected']->map(
                        static fn (array $row): array => [
                            'site_id' => $site->id,
                            'source_path' => $row['source_path'],
                            'target_path' => $row['target_path'],
                            'status_code' => 301,
                            'purpose' => $row['purpose'],
                            'is_active' => true,
                            'created_at' => $now,
                            'updated_at' => $now,
                        ],
                    )->all());
                    $restored = $plan['selected']->count();

                    SiteContentChanged::dispatch($site, array_values(array_unique([
                        '/catalog',
                        '/sitemap.xml',
                        ...$plan['selected']->pluck('source_path')->all(),
                        ...$plan['selected']->pluck('target_path')->all(),
                    ])));
                });
            }

            $this->line(json_encode([
                'mode' => $this->option('apply') ? 'apply' : 'dry_run',
                'site' => $site->key,
                'source_run_id' => $sourceRun->id,
                'source_manifest_sha256' => $sourceRun->summary['manifest_sha256'],
                'published_lineage_rows' => $plan['candidate_count'],
                'already_restored' => $plan['already_restored'],
                'pending_before' => $plan['pending_count'],
                'selected_batch' => $plan['selected']->count(),
                'restored_redirects' => $restored,
                'remaining_after' => $plan['pending_count'] - $restored,
                'preview_redirects_selected' => $plan['selected']->where('purpose', SiteRedirect::PURPOSE_PREVIEW)->count(),
                'seo_redirects_selected' => $plan['selected']->where('purpose', SiteRedirect::PURPOSE_SEO)->count(),
                'product_mutations' => 0,
                'indexable_urls_created' => 0,
                'schema_created' => 0,
            ], JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES));

            return self::SUCCESS;
        } catch (Throwable $error) {
            $this->error($error->getMessage());

            return self::FAILURE;
        }
    }

    private function assertExactLegacyHost(Site $site): void
    {
        if ($site->key !== 'microchips-by' || $site->domain !== 'microchips.by') {
            throw new RuntimeException('This migration requires the exact microchips-by site on microchips.by.');
        }
    }

    private function pinnedSourceRun(Site $site): ImportRun
    {
        $runId = trim((string) $this->option('source-run'));
        $expectedHash = strtolower(trim((string) $this->option('source-manifest-sha256')));
        $expectedRows = (int) $this->option('expected-source-records');
        if (! ctype_digit($runId) || (int) $runId < 1) {
            throw new RuntimeException('A pinned full Bitrix source run ID is required.');
        }
        if (! preg_match('/^[a-f0-9]{64}$/', $expectedHash) || $expectedRows < 1) {
            throw new RuntimeException('Pinned source manifest SHA-256 and expected source count are required.');
        }

        $run = ImportRun::query()->find((int) $runId);
        $stagedCount = $run === null ? 0 : StagedImportRecord::query()->where('import_run_id', $run->id)->count();
        if ($run === null
            || $run->source !== 'bitrix_full_catalog_snapshot:'.$site->key
            || $run->status !== 'completed'
            || (int) ($run->summary['site_id'] ?? 0) !== $site->id
            || strtolower((string) ($run->summary['manifest_sha256'] ?? '')) !== $expectedHash
            || $run->total_records !== $expectedRows
            || $run->processed_records !== $expectedRows
            || $run->failed_records !== 0
            || $stagedCount !== $expectedRows) {
            throw new RuntimeException('Pinned full Bitrix source run is missing, incomplete or drifted.');
        }

        return $run;
    }

    /**
     * @return array{candidate_count:int,already_restored:int,pending_count:int,selected:Collection<int,array{source_path:string,target_path:string,site_product_id:int,purpose:string,is_indexable:bool}>}
     */
    private function buildPlan(Site $site, ImportRun $sourceRun, int $batchSize): array
    {
        $lineageRows = DB::table('catalog_draft_materializations as m')
            ->join('staged_import_records as r', 'r.id', '=', 'm.staged_import_record_id')
            ->join('site_products as sp', 'sp.id', '=', 'm.site_product_id')
            ->join('products as p', 'p.id', '=', 'm.product_id')
            ->where('m.site_id', $site->id)
            ->where('m.source_import_run_id', $sourceRun->id)
            ->where('m.source_namespace', 'bitrix')
            ->where('m.materialization_kind', CatalogDraftMaterialization::KIND_NAMESPACED_DRAFT)
            ->where('sp.is_published', true)
            ->orderBy('r.row_number')
            ->get([
                'm.id as materialization_id',
                'm.staged_import_record_id',
                'm.product_id',
                'm.site_product_id',
                'm.source_external_id',
                'm.source_checksum',
                'm.target_category_external_id',
                'r.import_run_id as staged_import_run_id',
                'r.external_id as staged_external_id',
                'r.entity_type as staged_entity_type',
                'r.status as staged_status',
                'r.payload as staged_payload',
                'r.normalized_payload as staged_normalized_payload',
                'sp.product_id as site_product_product_id',
                'p.external_id as product_external_id',
            ]);

        $prepared = collect();
        $sourcePaths = [];
        foreach ($lineageRows as $row) {
            $payload = $this->decodedJson($row->staged_payload, "source row {$row->staged_import_record_id} payload");
            $normalized = $this->decodedJson($row->staged_normalized_payload, "source row {$row->staged_import_record_id} normalized payload");
            $sourcePath = $this->validateLineageAndSourcePath($site, $sourceRun, $row, $payload, $normalized);
            if (isset($sourcePaths[$sourcePath])) {
                throw new RuntimeException("Pinned source repeats legacy path {$sourcePath}.");
            }
            $sourcePaths[$sourcePath] = true;
            $prepared->push([
                'source_path' => $sourcePath,
                'site_product_id' => (int) $row->site_product_id,
            ]);
        }

        $siteUrls = SiteUrl::query()->where('site_id', $site->id)->get();
        $productUrls = $siteUrls->where('target_type', 'product')->groupBy('target_id');
        $urlsByPath = $siteUrls->keyBy('path');
        $productSeo = SiteSeo::query()
            ->where('site_id', $site->id)
            ->where('resource_type', 'product')
            ->get()
            ->groupBy('resource_id');
        $redirects = SiteRedirect::query()->where('site_id', $site->id)->get()->groupBy('source_path');
        $activeRedirectSources = SiteRedirect::query()
            ->where('site_id', $site->id)
            ->where('is_active', true)
            ->pluck('source_path')
            ->flip();

        $selected = collect();
        $alreadyRestored = 0;
        $pending = 0;
        foreach ($prepared as $row) {
            $urls = $productUrls->get($row['site_product_id'], collect());
            if ($urls->count() !== 1) {
                throw new RuntimeException("Published preview {$row['site_product_id']} must have exactly one product URL.");
            }
            /** @var SiteUrl $targetUrl */
            $targetUrl = $urls->first();
            if ($targetUrl->locale !== $site->default_locale) {
                throw new RuntimeException("Published product {$row['site_product_id']} must have one default-locale URL.");
            }
            $targetIsIndexable = (bool) $targetUrl->is_indexable;
            $purpose = $targetIsIndexable ? SiteRedirect::PURPOSE_SEO : SiteRedirect::PURPOSE_PREVIEW;
            $targetPath = $this->safeLocalPath($targetUrl->path, 'target path');
            if ($row['source_path'] === $targetPath || isset($sourcePaths[$targetPath])) {
                throw new RuntimeException("Legacy redirect {$row['source_path']} would create a self redirect or chain.");
            }
            if ($urlsByPath->has($row['source_path'])) {
                throw new RuntimeException("Legacy source {$row['source_path']} is still an active site URL.");
            }
            if ($activeRedirectSources->has($targetPath)) {
                throw new RuntimeException("Product target {$targetPath} is itself an active redirect source.");
            }

            $seoRows = $productSeo->get($row['site_product_id'], collect());
            if ($seoRows->count() !== 1) {
                throw new RuntimeException("Published preview {$row['site_product_id']} must have exactly one SEO row.");
            }
            /** @var SiteSeo $seo */
            $seo = $seoRows->first();
            if ($seo->locale !== $site->default_locale
                || $seo->canonical_path !== $targetPath
                || (bool) $seo->is_indexable !== $targetIsIndexable
                || (! $targetIsIndexable && $seo->schema !== null)) {
                throw new RuntimeException("Product target {$targetPath} must be self-canonical and match its URL indexability; noindex targets cannot have schema.");
            }

            $existingRows = $redirects->get($row['source_path'], collect());
            if ($existingRows->count() > 1) {
                throw new RuntimeException("Legacy source {$row['source_path']} has multiple redirect rows.");
            }
            $existing = $existingRows->first();
            if ($existing !== null) {
                if ($existing->target_path !== $targetPath
                    || (int) $existing->status_code !== 301
                    || $existing->purpose !== $purpose
                    || ! $existing->is_active) {
                    throw new RuntimeException("Legacy source {$row['source_path']} conflicts with the materialized preview lineage.");
                }
                $alreadyRestored++;

                continue;
            }

            $pending++;
            if ($selected->count() < $batchSize) {
                $selected->push([
                    'source_path' => $row['source_path'],
                    'target_path' => $targetPath,
                    'site_product_id' => $row['site_product_id'],
                    'purpose' => $purpose,
                    'is_indexable' => $targetIsIndexable,
                ]);
            }
        }

        return [
            'candidate_count' => $prepared->count(),
            'already_restored' => $alreadyRestored,
            'pending_count' => $pending,
            'selected' => $selected,
        ];
    }

    /** @param array<string,mixed> $payload
     * @param  array<string,mixed>  $normalized
     */
    private function validateLineageAndSourcePath(
        Site $site,
        ImportRun $sourceRun,
        object $row,
        array $payload,
        array $normalized,
    ): string {
        $transferStatus = $normalized['transfer_status'] ?? null;
        $bitrixId = is_string($payload['bitrix_id'] ?? null) ? trim($payload['bitrix_id']) : '';
        $sourceChecksum = is_string($payload['source_checksum'] ?? null) ? strtolower($payload['source_checksum']) : '';
        if ((int) $row->staged_import_run_id !== $sourceRun->id
            || $row->staged_entity_type !== 'bitrix_full_catalog_product_evidence'
            || $row->staged_status !== 'staged_evidence'
            || ! in_array($transferStatus, self::ALLOWED_PREVIEW_STATUSES, true)
            || $bitrixId === ''
            || $row->staged_external_id !== 'bitrix:'.$bitrixId
            || $row->source_external_id !== $row->staged_external_id
            || $row->product_external_id !== $row->source_external_id
            || (int) $row->product_id !== (int) $row->site_product_product_id
            || ($payload['allow_publication'] ?? null) !== false
            || ($payload['allow_indexing'] ?? null) !== false
            || ($payload['allow_merge'] ?? null) !== false
            || ! preg_match('/^[a-f0-9]{64}$/', $sourceChecksum)
            || strtolower((string) $row->source_checksum) !== $sourceChecksum
            || strtolower((string) ($normalized['source_checksum'] ?? '')) !== $sourceChecksum
            || ($normalized['target_category_external_id'] ?? null) !== $row->target_category_external_id) {
            throw new RuntimeException("Materialized source row {$row->staged_import_record_id} drifted from its guarded lineage.");
        }

        $checksumPayload = $payload;
        unset($checksumPayload['source_checksum']);
        ksort($checksumPayload);
        $actualChecksum = hash('sha256', json_encode(
            $checksumPayload,
            JSON_THROW_ON_ERROR | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES,
        ));
        if (! hash_equals($sourceChecksum, $actualChecksum)) {
            throw new RuntimeException("Materialized source row {$row->staged_import_record_id} checksum drifted.");
        }

        return $this->legacySourcePath($site, $payload['legacy_url'] ?? null, $bitrixId);
    }

    private function legacySourcePath(Site $site, mixed $value, string $bitrixId): string
    {
        if (! is_string($value) || $value === '') {
            throw new RuntimeException("Bitrix {$bitrixId} has no legacy URL.");
        }
        $parts = parse_url($value);
        if (! is_array($parts)
            || ($parts['scheme'] ?? null) !== 'https'
            || ($parts['host'] ?? null) !== $site->domain
            || isset($parts['user'])
            || isset($parts['pass'])
            || isset($parts['port'])
            || isset($parts['query'])
            || isset($parts['fragment'])
            || ! isset($parts['path'])
            || $value !== 'https://'.$site->domain.$parts['path']) {
            throw new RuntimeException("Bitrix {$bitrixId} legacy URL is not an exact local HTTPS URL.");
        }

        $path = $this->safeLocalPath($parts['path'], "Bitrix {$bitrixId} legacy path");
        $segments = explode('/', trim($path, '/'));
        if (($segments[0] ?? null) !== 'catalog'
            || count($segments) < 3
            || end($segments) !== $bitrixId) {
            throw new RuntimeException("Bitrix {$bitrixId} legacy path does not identify its source product.");
        }

        return rtrim($path, '/');
    }

    private function safeLocalPath(mixed $value, string $field): string
    {
        if (! is_string($value)
            || $value === ''
            || $value === '/'
            || ! str_starts_with($value, '/')
            || str_starts_with($value, '//')
            || str_contains($value, '?')
            || str_contains($value, '#')
            || str_contains($value, '\\')
            || str_contains($value, '//')
            || rawurldecode($value) !== $value
            || preg_match('/[\x00-\x1F\x7F]/', $value) === 1) {
            throw new RuntimeException("Unsafe {$field}.");
        }
        foreach (explode('/', $value) as $segment) {
            if ($segment === '.' || $segment === '..') {
                throw new RuntimeException("Unsafe {$field}.");
            }
        }

        return $value;
    }

    /** @return array<string,mixed> */
    private function decodedJson(mixed $value, string $field): array
    {
        if (is_array($value)) {
            return $value;
        }
        if (! is_string($value)) {
            throw new RuntimeException("Invalid {$field}.");
        }
        $decoded = json_decode($value, true, 512, JSON_THROW_ON_ERROR);
        if (! is_array($decoded)) {
            throw new RuntimeException("Invalid {$field}.");
        }

        return $decoded;
    }

    /** @param Collection<int,array{source_path:string,target_path:string,site_product_id:int,purpose:string,is_indexable:bool}> $selected */
    private function assertSelectedBatchStillSafe(Site $site, Collection $selected): void
    {
        $sourcePaths = $selected->pluck('source_path')->all();
        $targetPaths = $selected->pluck('target_path')->all();
        $siteProductIds = $selected->pluck('site_product_id')->all();

        if ($this->existsInChunks('site_urls', $site->id, 'path', $sourcePaths)
            || $this->existsInChunks('site_redirects', $site->id, 'source_path', $sourcePaths)
            || $this->existsInChunks('site_redirects', $site->id, 'source_path', $targetPaths, true)) {
            throw new RuntimeException('Redirect batch changed after validation; no redirects were written.');
        }

        $urls = $this->rowsForIdsInChunks('site_urls', $site->id, 'target_id', $siteProductIds)
            ->where('target_type', 'product')
            ->groupBy('target_id');
        $seo = $this->rowsForIdsInChunks('site_seos', $site->id, 'resource_id', $siteProductIds)
            ->where('resource_type', 'product')
            ->groupBy('resource_id');
        $published = $this->rowsForIdsInChunks('site_products', $site->id, 'id', $siteProductIds)
            ->where('is_published', true)
            ->keyBy('id');
        foreach ($selected as $row) {
            $targetUrls = $urls->get($row['site_product_id'], collect());
            $seoRows = $seo->get($row['site_product_id'], collect());
            $targetUrl = $targetUrls->first();
            $seoRow = $seoRows->first();
            if (! $published->has($row['site_product_id'])
                || $targetUrls->count() !== 1
                || $targetUrl?->path !== $row['target_path']
                || (bool) $targetUrl?->is_indexable !== $row['is_indexable']
                || $seoRows->count() !== 1
                || $seoRow?->canonical_path !== $row['target_path']
                || (bool) $seoRow?->is_indexable !== $row['is_indexable']
                || (! $row['is_indexable'] && $seoRow?->schema !== null)) {
                throw new RuntimeException('Product target changed after validation; no redirects were written.');
            }
        }
    }

    /** @param list<mixed> $values */
    private function existsInChunks(
        string $table,
        int $siteId,
        string $column,
        array $values,
        bool $activeOnly = false,
    ): bool {
        foreach (array_chunk($values, 400) as $chunk) {
            $query = DB::table($table)->where('site_id', $siteId)->whereIn($column, $chunk);
            if ($activeOnly) {
                $query->where('is_active', true);
            }
            if ($query->exists()) {
                return true;
            }
        }

        return false;
    }

    /** @param list<int> $ids
     * @return Collection<int,object>
     */
    private function rowsForIdsInChunks(string $table, int $siteId, string $column, array $ids): Collection
    {
        $rows = collect();
        foreach (array_chunk($ids, 400) as $chunk) {
            $rows->push(...DB::table($table)->where('site_id', $siteId)->whereIn($column, $chunk)->get());
        }

        return $rows;
    }
}
