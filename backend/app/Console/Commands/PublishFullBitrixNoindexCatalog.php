<?php

namespace App\Console\Commands;

use App\Models\ImportRun;
use App\Models\Site;
use App\Models\SiteCategory;
use Illuminate\Console\Command;
use Illuminate\Support\Collection;
use Illuminate\Support\Facades\DB;
use RuntimeException;
use Throwable;

class PublishFullBitrixNoindexCatalog extends Command
{
    private const ALLOWED_PREVIEW_STATUSES = [
        'legacy_only_draft_candidate',
        'hold_duplicate_candidate',
        'hold_linked_identity_candidate',
        'hold_one_c_collision',
    ];

    protected $signature = 'catalog:publish-full-bitrix-noindex
                            {site : Site key}
                            {--source-run= : Pinned full Bitrix staging run ID}
                            {--source-manifest-sha256= : Required SHA-256 of the pinned source manifest}
                            {--expected-source-records=17207 : Exact source row count}
                            {--expected-candidates=16173 : Exact safe candidate count}
                            {--transfer-status=* : Explicit transfer statuses to publish; defaults to legacy_only_draft_candidate}
                            {--batch-size=1000 : Maximum products to publish in this cycle}
                            {--apply : Persist the noindex preview batch; default is dry-run}';

    protected $description = 'Publish materialized safe Bitrix drafts as noindex catalogue previews without price, stock or schema claims';

    public function handle(): int
    {
        try {
            $site = Site::query()->where('key', trim((string) $this->argument('site')))->sole();
            $run = ImportRun::query()->findOrFail((int) $this->option('source-run'));
            $batchSize = (int) $this->option('batch-size');
            if ($batchSize < 1 || $batchSize > 2000) {
                throw new RuntimeException('Batch size must be between 1 and 2000.');
            }
            $this->assertPinnedSource($site, $run);

            $statuses = array_values(array_unique(array_filter(array_map(
                static fn (mixed $status): string => is_string($status) ? trim($status) : '',
                (array) $this->option('transfer-status'),
            ))));
            if ($statuses === []) {
                $statuses = ['legacy_only_draft_candidate'];
            }
            if (array_diff($statuses, self::ALLOWED_PREVIEW_STATUSES) !== []) {
                throw new RuntimeException('Only reviewed non-electronics Bitrix preview statuses may be published.');
            }

            $eligible = $this->eligibleQuery($site->id, $run->id, $statuses);
            $eligibleCount = (clone $eligible)->count();
            $expected = (int) $this->option('expected-candidates');
            if ($eligibleCount !== $expected) {
                throw new RuntimeException("Expected {$expected} safe materialized candidates; received {$eligibleCount}.");
            }

            $this->assertPreviouslyPublishedRowsAreSafe($site, $run->id, $statuses);
            $publishedBefore = (clone $eligible)->where('sp.is_published', true)->count();
            $selected = (clone $eligible)
                ->where('sp.is_published', false)
                ->orderBy('r.row_number')
                ->limit($batchSize)
                ->get([
                    'm.site_product_id', 'm.product_id', 'm.target_category_external_id',
                    'sp.slug', 'p.name',
                ]);
            $remainingBefore = $eligibleCount - $publishedBefore;
            $summary = [
                'mode' => $this->option('apply') ? 'apply' : 'dry_run',
                'site' => $site->key,
                'source_run_id' => $run->id,
                'transfer_statuses' => $statuses,
                'eligible_safe_rows' => $eligibleCount,
                'already_published' => $publishedBefore,
                'selected_batch' => $selected->count(),
                'remaining_before' => $remainingBefore,
                'remaining_after' => $remainingBefore - $selected->count(),
                'indexable_urls_created' => 0,
                'prices_changed' => 0,
                'availability_changed' => 0,
                'schema_created' => 0,
            ];

            if (! $this->option('apply') || $selected->isEmpty()) {
                $this->line(json_encode($summary, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES));

                return self::SUCCESS;
            }

            DB::transaction(function () use ($site, $run, $selected): void {
                if (DB::getDriverName() === 'pgsql') {
                    DB::select('select pg_advisory_xact_lock(hashtext(?))', [
                        'bitrix-noindex-publication:'.$site->key.':'.$run->id,
                    ]);
                }
                $this->publishBatch($site, $selected);
            });

            $this->line(json_encode($summary, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES));

            return self::SUCCESS;
        } catch (Throwable $error) {
            $this->error($error->getMessage());

            return self::FAILURE;
        }
    }

    private function assertPinnedSource(Site $site, ImportRun $run): void
    {
        if ($run->source !== 'bitrix_full_catalog_snapshot:'.$site->key || $run->status !== 'completed') {
            throw new RuntimeException('Pinned run is not the completed full Bitrix snapshot for this site.');
        }
        $expectedRows = (int) $this->option('expected-source-records');
        if ($run->total_records !== $expectedRows || $run->processed_records !== $expectedRows || $run->failed_records !== 0) {
            throw new RuntimeException('Pinned source run counters do not match the expected complete snapshot.');
        }
        $expectedHash = strtolower(trim((string) $this->option('source-manifest-sha256')));
        if (! preg_match('/^[a-f0-9]{64}$/', $expectedHash) || strtolower((string) ($run->summary['manifest_sha256'] ?? '')) !== $expectedHash) {
            throw new RuntimeException('Pinned source manifest SHA-256 does not match.');
        }
    }

    /** @param list<string> $statuses */
    private function eligibleQuery(int $siteId, int $runId, array $statuses)
    {
        return DB::table('catalog_draft_materializations as m')
            ->join('staged_import_records as r', 'r.id', '=', 'm.staged_import_record_id')
            ->join('site_products as sp', 'sp.id', '=', 'm.site_product_id')
            ->join('products as p', 'p.id', '=', 'm.product_id')
            ->where('m.site_id', $siteId)
            ->where('m.source_import_run_id', $runId)
            ->where('m.materialization_kind', 'namespaced_draft')
            ->whereIn('r.normalized_payload->transfer_status', $statuses);
    }

    /** @param list<string> $statuses */
    private function assertPreviouslyPublishedRowsAreSafe(Site $site, int $runId, array $statuses): void
    {
        $bad = $this->eligibleQuery($site->id, $runId, $statuses)
            ->where('sp.is_published', true)
            ->where(function ($query) use ($site): void {
                $query->whereNotExists(function ($url) use ($site): void {
                    $url->selectRaw('1')->from('site_urls as u')
                        ->whereColumn('u.target_id', 'sp.id')
                        ->where('u.site_id', $site->id)
                        ->where('u.target_type', 'product')
                        ->where('u.locale', $site->default_locale)
                        ->where('u.is_indexable', false);
                })->orWhereNotExists(function ($seo) use ($site): void {
                    $seo->selectRaw('1')->from('site_seos as s')
                        ->whereColumn('s.resource_id', 'sp.id')
                        ->where('s.site_id', $site->id)
                        ->where('s.locale', $site->default_locale)
                        ->where('s.resource_type', 'product')
                        ->where('s.is_indexable', false)
                        ->whereNull('s.schema');
                });
            })
            ->exists();
        if ($bad) {
            throw new RuntimeException('A previously published Bitrix preview is missing its noindex URL/SEO invariant.');
        }
    }

    /** @param Collection<int, object> $selected */
    private function publishBatch(Site $site, Collection $selected): void
    {
        $categories = SiteCategory::query()
            ->with('category')
            ->where('site_id', $site->id)
            ->get()
            ->keyBy('external_id');
        $byCanonicalId = $categories->keyBy('category_id');
        $direct = $selected->pluck('target_category_external_id')->unique()
            ->map(fn (string $externalId) => $categories->get($externalId));
        if ($direct->contains(null)) {
            throw new RuntimeException('A publication candidate references a missing site category.');
        }

        $publishCategories = collect();
        foreach ($direct as $category) {
            $current = $category;
            while ($current !== null) {
                $publishCategories->put($current->id, $current);
                $parentId = $current->category?->parent_id;
                $current = $parentId === null ? null : $byCanonicalId->get($parentId);
                if ($parentId !== null && $current === null) {
                    throw new RuntimeException('Category tree is incomplete for the noindex publication wave.');
                }
            }
        }

        $now = now();
        $categoryUrlRows = [];
        $categorySeoRows = [];
        foreach ($publishCategories as $category) {
            $path = $this->categoryPath($category->slug);
            $this->assertPathAvailable($site->id, $path, 'category', $category->id);
            $categoryUrlRows[] = $this->urlRow($site, $path, 'category', $category->id, $now);
            $categorySeoRows[] = $this->seoRow($site, $path, 'category', $category->id, $category->name, $now);
        }

        $productUrlRows = [];
        $productSeoRows = [];
        foreach ($selected as $row) {
            $category = $categories->get($row->target_category_external_id);
            $path = $this->categoryPath($category->slug).'/'.$row->slug;
            $this->assertPathAvailable($site->id, $path, 'product', $row->site_product_id);
            $productUrlRows[] = $this->urlRow($site, $path, 'product', $row->site_product_id, $now);
            $productSeoRows[] = $this->seoRow($site, $path, 'product', $row->site_product_id, $row->name, $now);
        }

        DB::table('site_urls')->upsert(
            [...$categoryUrlRows, ...$productUrlRows],
            ['site_id', 'path'],
            ['locale', 'target_type', 'target_id', 'is_indexable', 'updated_at'],
        );
        DB::table('site_seos')->upsert(
            [...$categorySeoRows, ...$productSeoRows],
            ['site_id', 'locale', 'resource_type', 'resource_id'],
            ['canonical_path', 'title', 'description', 'is_indexable', 'schema', 'updated_at'],
        );
        DB::table('site_categories')->whereIn('id', $publishCategories->keys())->update([
            'is_published' => true,
            'updated_at' => $now,
        ]);
        DB::table('site_products')->whereIn('id', $selected->pluck('site_product_id'))->update([
            'is_published' => true,
            'updated_at' => $now,
        ]);
    }

    private function assertPathAvailable(int $siteId, string $path, string $targetType, int $targetId): void
    {
        $conflict = DB::table('site_urls')
            ->where('site_id', $siteId)
            ->where('path', $path)
            ->where(function ($query) use ($targetType, $targetId): void {
                $query->where('target_type', '<>', $targetType)
                    ->orWhere('target_id', '<>', $targetId)
                    ->orWhere('is_indexable', true);
            })
            ->exists();
        if ($conflict) {
            throw new RuntimeException("Canonical path {$path} belongs to another or indexable resource.");
        }
    }

    private function categoryPath(string $slug): string
    {
        $slug = trim($slug, '/');
        $slug = preg_replace('#^catalog/#', '', $slug) ?? $slug;
        if ($slug === '' || str_contains($slug, '..')) {
            throw new RuntimeException('Category has no safe canonical slug.');
        }

        return '/catalog/'.$slug;
    }

    private function urlRow(Site $site, string $path, string $type, int $id, $now): array
    {
        return ['site_id' => $site->id, 'path' => $path, 'locale' => $site->default_locale,
            'target_type' => $type, 'target_id' => $id, 'is_indexable' => false,
            'created_at' => $now, 'updated_at' => $now];
    }

    private function seoRow(Site $site, string $path, string $type, int $id, ?string $title, $now): array
    {
        return ['site_id' => $site->id, 'locale' => $site->default_locale, 'resource_type' => $type,
            'resource_id' => $id, 'canonical_path' => $path, 'title' => $title, 'description' => null,
            'is_indexable' => false, 'schema' => null, 'created_at' => $now, 'updated_at' => $now];
    }
}
