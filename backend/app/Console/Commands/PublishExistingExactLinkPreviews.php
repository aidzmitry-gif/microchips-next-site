<?php

namespace App\Console\Commands;

use App\Events\SiteContentChanged;
use App\Models\CatalogDraftMaterialization;
use App\Models\ImportRun;
use App\Models\Product;
use App\Models\Site;
use App\Models\SiteCategory;
use App\Models\SiteProduct;
use App\Models\SiteRedirect;
use App\Models\SiteSeo;
use App\Models\SiteUrl;
use App\Models\StagedImportRecord;
use Illuminate\Console\Command;
use Illuminate\Support\Collection;
use Illuminate\Support\Facades\DB;
use JsonException;
use RuntimeException;
use Throwable;

/**
 * Publishes the four already-existing 1C products that have an exact Bitrix link.
 *
 * No Product is created or merged here. The Bitrix row remains immutable source
 * evidence while its existing 1C Product receives only a site-scoped noindex
 * preview, lineage and a redirect from the exact legacy path.
 */
class PublishExistingExactLinkPreviews extends Command
{
    protected $signature = 'catalog:publish-existing-exact-link-previews
                            {site : Site key}
                            {file : Pinned JSON manifest containing exactly four exact links}
                            {--apply : Persist the noindex previews; default is dry-run}';

    protected $description = 'Publish four pinned exact Bitrix-to-1C links as noindex previews without creating Product duplicates';

    private const EXPECTED_LINKS = 4;

    public function handle(): int
    {
        try {
            $site = Site::query()->where('key', trim((string) $this->argument('site')))->sole();
            $manifest = $this->manifest($site, (string) $this->argument('file'));
            $apply = (bool) $this->option('apply');

            $summary = $apply
                ? DB::transaction(fn (): array => $this->processManifest($site, $manifest, true))
                : $this->processManifest($site, $manifest, false);

            $this->line(json_encode($summary, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE));

            return self::SUCCESS;
        } catch (Throwable $error) {
            $this->error($error->getMessage());

            return self::FAILURE;
        }
    }

    /**
     * @param  array{source_run_id:int,source_manifest_sha256:string,source_records:int,links:list<array<string,mixed>>,manifest_file:string}  $manifest
     * @return array<string, int|string>
     */
    private function processManifest(Site $site, array $manifest, bool $apply): array
    {
        if ($apply && DB::getDriverName() === 'pgsql') {
            DB::select('select pg_advisory_xact_lock(hashtext(?))', [
                'existing-exact-link-previews:'.$site->key.':'.$manifest['source_run_id'],
            ]);
        }

        $sourceRunQuery = ImportRun::query()->whereKey($manifest['source_run_id']);
        if ($apply) {
            $sourceRunQuery->lockForUpdate();
        }
        $sourceRun = $sourceRunQuery->first();
        $this->assertSourceRun($site, $sourceRun, $manifest);

        $plans = collect($manifest['links'])->map(
            fn (array $row, int $index): array => $this->plan($site, $sourceRun, $row, $index, $apply),
        );
        $this->assertUniquePlan($plans);

        $pending = $plans->where('state', 'pending');
        $unchanged = $plans->where('state', 'unchanged');
        if ($pending->isNotEmpty() && $unchanged->isNotEmpty()) {
            throw new RuntimeException('Exact-link package is partially applied; the atomic four-row invariant was violated.');
        }

        $summary = [
            'mode' => $apply ? 'apply' : 'dry_run',
            'site' => $site->key,
            'source_run_id' => $sourceRun->id,
            'source_manifest_sha256' => $manifest['source_manifest_sha256'],
            'links' => self::EXPECTED_LINKS,
            'pending_links' => $pending->count(),
            'unchanged_links' => $unchanged->count(),
            'products_created' => 0,
            'site_products_published' => $apply ? $pending->count() : 0,
            'noindex_urls' => self::EXPECTED_LINKS,
            'indexable_urls' => 0,
            'offer_schemas' => 0,
            'legacy_redirects' => self::EXPECTED_LINKS,
        ];

        if (! $apply || $pending->isEmpty()) {
            return $summary;
        }

        $run = ImportRun::query()->create([
            'source' => 'bitrix_existing_exact_link_preview_publication:'.$site->key,
            'status' => 'completed',
            'source_file' => basename($manifest['manifest_file']),
            'total_records' => self::EXPECTED_LINKS,
            'processed_records' => self::EXPECTED_LINKS,
            'failed_records' => 0,
            'summary' => $summary,
            'started_at' => now(),
            'finished_at' => now(),
        ]);

        $revalidationPaths = ['/catalog', '/sitemap.xml'];
        foreach ($pending as $plan) {
            /** @var SiteProduct $siteProduct */
            $siteProduct = $plan['siteProduct'];
            /** @var SiteCategory $category */
            $category = $plan['category'];
            /** @var StagedImportRecord $sourceRow */
            $sourceRow = $plan['sourceRow'];

            foreach ($plan['ancestors'] as $ancestor) {
                $categoryPath = $this->categoryPath($ancestor);
                $this->writeNoindexUrl($site, $categoryPath, 'category', $ancestor->id);
                SiteSeo::query()->updateOrCreate(
                    [
                        'site_id' => $site->id,
                        'locale' => $site->default_locale,
                        'resource_type' => 'category',
                        'resource_id' => $ancestor->id,
                    ],
                    [
                        'canonical_path' => $categoryPath,
                        'title' => $ancestor->name ?? $ancestor->category?->name,
                        'description' => null,
                        'is_indexable' => false,
                        'schema' => null,
                    ],
                );
                $ancestor->update(['is_published' => true]);
                $revalidationPaths[] = $categoryPath;
            }

            $siteProduct->categories()->syncWithoutDetaching([
                $category->id => ['site_id' => $site->id],
            ]);
            $siteProduct->update([
                'slug' => $plan['productSlug'],
                'is_published' => true,
            ]);
            $this->writeNoindexUrl($site, $plan['targetPath'], 'product', $siteProduct->id);
            SiteSeo::query()->updateOrCreate(
                [
                    'site_id' => $site->id,
                    'locale' => $site->default_locale,
                    'resource_type' => 'product',
                    'resource_id' => $siteProduct->id,
                ],
                [
                    'canonical_path' => $plan['targetPath'],
                    'title' => $siteProduct->product?->name,
                    'description' => $siteProduct->product?->short_description,
                    'is_indexable' => false,
                    'schema' => null,
                ],
            );
            SiteRedirect::query()->create([
                'site_id' => $site->id,
                'source_path' => $plan['legacySourcePath'],
                'target_path' => $plan['targetPath'],
                'status_code' => 301,
                'purpose' => SiteRedirect::PURPOSE_PREVIEW,
                'is_active' => true,
            ]);
            CatalogDraftMaterialization::query()->create([
                'materialization_run_id' => $run->id,
                'source_import_run_id' => $sourceRun->id,
                'staged_import_record_id' => $sourceRow->id,
                'site_id' => $site->id,
                'product_id' => $siteProduct->product_id,
                'site_product_id' => $siteProduct->id,
                'source_namespace' => 'bitrix',
                'source_external_id' => $sourceRow->external_id,
                'source_checksum' => $plan['sourceChecksum'],
                'materialization_kind' => CatalogDraftMaterialization::KIND_EXISTING_EXACT_LINK,
                'target_category_external_id' => $category->external_id,
            ]);

            $revalidationPaths[] = $plan['legacySourcePath'];
            $revalidationPaths[] = $plan['targetPath'];
        }

        SiteContentChanged::dispatch($site, array_values(array_unique($revalidationPaths)));

        return $summary;
    }

    /**
     * @param  array{source_run_id:int,source_manifest_sha256:string,source_records:int}  $manifest
     */
    private function assertSourceRun(Site $site, ?ImportRun $run, array $manifest): void
    {
        $expectedSource = 'bitrix_full_catalog_snapshot:'.$site->key;
        if ($run === null
            || $run->source !== $expectedSource
            || $run->status !== 'completed'
            || $run->failed_records !== 0
            || $run->total_records !== $manifest['source_records']
            || ($run->summary['manifest_sha256'] ?? null) !== $manifest['source_manifest_sha256']
            || StagedImportRecord::query()->where('import_run_id', $run->id)->count() !== $manifest['source_records']) {
            throw new RuntimeException('Pinned full Bitrix source run is missing, incomplete or drifted.');
        }
    }

    /** @param array<string,mixed> $row
     * @return array<string,mixed>
     */
    private function plan(Site $site, ImportRun $sourceRun, array $row, int $index, bool $lock): array
    {
        foreach (['bitrix_external_id', 'one_c_external_id', 'source_checksum', 'target_category_external_id', 'product_slug', 'target_path', 'legacy_source_path'] as $field) {
            if (! is_string($row[$field] ?? null) || trim($row[$field]) === '') {
                throw new RuntimeException("Exact-link row {$index} requires {$field}.");
            }
        }

        $bitrixExternalId = trim($row['bitrix_external_id']);
        $oneCExternalId = trim($row['one_c_external_id']);
        $sourceChecksum = trim($row['source_checksum']);
        $categoryExternalId = trim($row['target_category_external_id']);
        $productSlug = trim($row['product_slug']);
        $targetPath = trim($row['target_path']);
        $legacySourcePath = trim($row['legacy_source_path']);
        if (! preg_match('/^bitrix:\d+$/', $bitrixExternalId)
            || ! preg_match('/^[a-f0-9]{64}$/', $sourceChecksum)
            || ! preg_match('/^[a-z0-9]+(?:-[a-z0-9]+)*$/', $productSlug)
            || ! $this->safePath($targetPath, false)
            || ! $this->safePath($legacySourcePath, false)
            || $targetPath === $legacySourcePath) {
            throw new RuntimeException("Exact-link row {$bitrixExternalId} has an unsafe identity, checksum, slug or path.");
        }

        $sourceRowQuery = StagedImportRecord::query()
            ->where('import_run_id', $sourceRun->id)
            ->where('entity_type', 'bitrix_full_catalog_product_evidence')
            ->where('external_id', $bitrixExternalId);
        if ($lock) {
            $sourceRowQuery->lockForUpdate();
        }
        $sourceRow = $sourceRowQuery->sole();
        $payload = $sourceRow->payload;
        $normalized = $sourceRow->normalized_payload;
        $legacyUrlPath = rtrim((string) parse_url((string) ($payload['legacy_url'] ?? ''), PHP_URL_PATH), '/');
        if ($sourceRow->status !== 'staged_evidence'
            || ($payload['transfer_status'] ?? null) !== 'existing_one_c_exact_link'
            || ($normalized['transfer_status'] ?? null) !== 'existing_one_c_exact_link'
            || ($payload['one_c_external_id'] ?? null) !== $oneCExternalId
            || ($normalized['one_c_external_id'] ?? null) !== $oneCExternalId
            || ($payload['source_checksum'] ?? null) !== $sourceChecksum
            || ($normalized['source_checksum'] ?? null) !== $sourceChecksum
            || ($payload['target_category_external_id'] ?? null) !== $categoryExternalId
            || ($normalized['target_category_external_id'] ?? null) !== $categoryExternalId
            || $legacyUrlPath !== $legacySourcePath
            || ($payload['allow_product_create'] ?? null) !== false
            || ($payload['allow_publication'] ?? null) !== false
            || ($payload['allow_indexing'] ?? null) !== false
            || ($payload['allow_merge'] ?? null) !== false) {
            throw new RuntimeException("Exact-link row {$bitrixExternalId} drifted from its guarded staging contract.");
        }
        $checksumPayload = $payload;
        unset($checksumPayload['source_checksum']);
        ksort($checksumPayload);
        $calculatedChecksum = hash('sha256', json_encode(
            $checksumPayload,
            JSON_THROW_ON_ERROR | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES,
        ));
        if (! hash_equals($calculatedChecksum, $sourceChecksum)) {
            throw new RuntimeException("Exact-link row {$bitrixExternalId} checksum drifted.");
        }

        $product = Product::query()->where('external_id', $oneCExternalId)->sole();
        $siteProductQuery = SiteProduct::query()
            ->with('product')
            ->where('site_id', $site->id)
            ->where('product_id', $product->id);
        if ($lock) {
            $siteProductQuery->lockForUpdate();
        }
        $siteProduct = $siteProductQuery->sole();
        if ($siteProduct->price !== null || $siteProduct->availability !== 'on_request') {
            throw new RuntimeException("Exact-linked 1C product {$oneCExternalId} has a commercial price or availability claim.");
        }

        $category = SiteCategory::query()
            ->with('category')
            ->where('site_id', $site->id)
            ->where('external_id', $categoryExternalId)
            ->sole();
        $expectedTargetPath = $this->categoryPath($category).'/'.$productSlug;
        if ($targetPath !== $expectedTargetPath) {
            throw new RuntimeException("Exact-link row {$bitrixExternalId} target path does not match its pinned category and slug.");
        }
        $ancestors = $this->categoryAncestors($site, $category);
        foreach ($ancestors as $ancestor) {
            $this->assertNoindexResourceState($site, $this->categoryPath($ancestor), 'category', $ancestor->id, true);
        }

        $materialization = CatalogDraftMaterialization::query()
            ->where('site_id', $site->id)
            ->where('source_namespace', 'bitrix')
            ->where('source_external_id', $bitrixExternalId)
            ->first();
        if ($materialization !== null) {
            $this->assertAppliedState(
                $site,
                $sourceRun,
                $sourceRow,
                $product,
                $siteProduct,
                $category,
                $materialization,
                $sourceChecksum,
                $productSlug,
                $targetPath,
                $legacySourcePath,
            );

            return compact('sourceRow', 'product', 'siteProduct', 'category', 'ancestors', 'sourceChecksum', 'productSlug', 'targetPath', 'legacySourcePath') + ['state' => 'unchanged'];
        }

        if ($siteProduct->is_published
            || SiteUrl::query()->where('site_id', $site->id)->where('target_type', 'product')->where('target_id', $siteProduct->id)->exists()
            || SiteSeo::query()->where('site_id', $site->id)->where('resource_type', 'product')->where('resource_id', $siteProduct->id)->exists()
            || SiteRedirect::query()->where('site_id', $site->id)->where('source_path', $legacySourcePath)->exists()
            || CatalogDraftMaterialization::query()->where('site_id', $site->id)->where('staged_import_record_id', $sourceRow->id)->exists()
            || CatalogDraftMaterialization::query()->where('site_id', $site->id)->where('product_id', $product->id)->where('materialization_kind', CatalogDraftMaterialization::KIND_EXISTING_EXACT_LINK)->exists()) {
            throw new RuntimeException("Exact-linked 1C product {$oneCExternalId} is not an untouched unpublished preview candidate.");
        }
        $this->assertTargetOwnership($site, $siteProduct, $productSlug, $targetPath);

        return compact('sourceRow', 'product', 'siteProduct', 'category', 'ancestors', 'sourceChecksum', 'productSlug', 'targetPath', 'legacySourcePath') + ['state' => 'pending'];
    }

    private function assertAppliedState(
        Site $site,
        ImportRun $sourceRun,
        StagedImportRecord $sourceRow,
        Product $product,
        SiteProduct $siteProduct,
        SiteCategory $category,
        CatalogDraftMaterialization $materialization,
        string $sourceChecksum,
        string $productSlug,
        string $targetPath,
        string $legacySourcePath,
    ): void {
        $lineageMatches = $materialization->source_import_run_id === $sourceRun->id
            && $materialization->staged_import_record_id === $sourceRow->id
            && $materialization->product_id === $product->id
            && $materialization->site_product_id === $siteProduct->id
            && $materialization->source_checksum === $sourceChecksum
            && $materialization->materialization_kind === CatalogDraftMaterialization::KIND_EXISTING_EXACT_LINK
            && $materialization->target_category_external_id === $category->external_id;
        $linkedCategory = DB::table('site_category_product')
            ->where('site_id', $site->id)
            ->where('site_product_id', $siteProduct->id)
            ->where('site_category_id', $category->id)
            ->exists();
        $redirectMatches = SiteRedirect::query()
            ->where('site_id', $site->id)
            ->where('source_path', $legacySourcePath)
            ->where('target_path', $targetPath)
            ->where('status_code', 301)
            ->where('purpose', SiteRedirect::PURPOSE_PREVIEW)
            ->where('is_active', true)
            ->exists();
        if (! $lineageMatches
            || ! $siteProduct->is_published
            || $siteProduct->slug !== $productSlug
            || ! $linkedCategory
            || ! $redirectMatches) {
            throw new RuntimeException("Applied exact-link {$sourceRow->external_id} drifted from its pinned state.");
        }
        $this->assertNoindexResourceState($site, $targetPath, 'product', $siteProduct->id, false, true);
    }

    private function assertTargetOwnership(Site $site, SiteProduct $siteProduct, string $slug, string $path): void
    {
        if (SiteProduct::query()->where('site_id', $site->id)->where('slug', $slug)->where('id', '<>', $siteProduct->id)->exists()
            || SiteUrl::query()->where('site_id', $site->id)->where('path', $path)->exists()
            || SiteRedirect::query()->where('site_id', $site->id)->where(function ($query) use ($path): void {
                $query->where('source_path', $path)->orWhere('target_path', $path);
            })->exists()) {
            throw new RuntimeException("Target slug or path {$path} is already reserved.");
        }
    }

    private function assertNoindexResourceState(
        Site $site,
        string $path,
        string $type,
        int $id,
        bool $allowAbsent,
        bool $allowPreviewRedirectTarget = false,
    ): void {
        $urls = SiteUrl::query()->where('site_id', $site->id)->where('target_type', $type)->where('target_id', $id)->get();
        $pathOwner = SiteUrl::query()->where('site_id', $site->id)->where('path', $path)->first();
        $seo = SiteSeo::query()
            ->where('site_id', $site->id)
            ->where('locale', $site->default_locale)
            ->where('resource_type', $type)
            ->where('resource_id', $id)
            ->get();
        $redirectConflict = SiteRedirect::query()
            ->where('site_id', $site->id)
            ->where(function ($query) use ($allowPreviewRedirectTarget, $path): void {
                $query->where('source_path', $path);
                if (! $allowPreviewRedirectTarget) {
                    $query->orWhere('target_path', $path);
                }
            })
            ->exists();
        if (($pathOwner !== null && ($pathOwner->target_type !== $type || $pathOwner->target_id !== $id))
            || $redirectConflict) {
            throw new RuntimeException("Resource path {$path} is reserved by another URL or redirect.");
        }
        if ($allowAbsent && $urls->isEmpty() && $seo->isEmpty()) {
            return;
        }
        if ($urls->count() !== 1
            || $urls->sole()->path !== $path
            || $urls->sole()->is_indexable
            || $seo->count() !== 1
            || $seo->sole()->canonical_path !== $path
            || $seo->sole()->is_indexable
            || $seo->sole()->schema !== null) {
            throw new RuntimeException("Resource {$type}:{$id} is not the exact schema-null noindex state at {$path}.");
        }
    }

    /** @param Collection<int,array<string,mixed>> $plans */
    private function assertUniquePlan(Collection $plans): void
    {
        foreach (['sourceRow.id', 'product.id', 'siteProduct.id', 'targetPath', 'legacySourcePath'] as $key) {
            $values = $plans->pluck($key);
            if ($values->unique()->count() !== self::EXPECTED_LINKS) {
                throw new RuntimeException("Exact-link manifest repeats {$key}.");
            }
        }
    }

    /** @return list<SiteCategory> */
    private function categoryAncestors(Site $site, SiteCategory $category): array
    {
        $all = SiteCategory::query()->with('category')->where('site_id', $site->id)->get()->keyBy('category_id');
        $result = [];
        $current = $category;
        while ($current !== null) {
            array_unshift($result, $current);
            $parentId = $current->category?->parent_id;
            $current = $parentId === null ? null : $all->get($parentId);
            if ($parentId !== null && $current === null) {
                throw new RuntimeException('Category tree is incomplete for an exact-link preview.');
            }
        }

        return $result;
    }

    private function categoryPath(SiteCategory $category): string
    {
        $slug = trim((string) $category->slug, '/');
        $slug = preg_replace('#^catalog/#', '', $slug) ?? $slug;
        if ($slug === '' || str_contains($slug, '..')) {
            throw new RuntimeException('Exact-link target category has no safe canonical slug.');
        }

        return '/catalog/'.$slug;
    }

    private function writeNoindexUrl(Site $site, string $path, string $type, int $id): void
    {
        SiteUrl::query()->updateOrCreate(
            ['site_id' => $site->id, 'path' => $path],
            [
                'locale' => $site->default_locale,
                'target_type' => $type,
                'target_id' => $id,
                'is_indexable' => false,
            ],
        );
    }

    private function safePath(string $path, bool $allowTrailingSlash): bool
    {
        if (! preg_match('#^/catalog/[a-zA-Z0-9_~.%+-]+(?:/[a-zA-Z0-9_~.%+-]+)*/?$#', $path)
            || str_contains($path, '..')
            || str_contains($path, '//')) {
            return false;
        }

        return $allowTrailingSlash || ! str_ends_with($path, '/');
    }

    /**
     * @return array{source_run_id:int,source_manifest_sha256:string,source_records:int,links:list<array<string,mixed>>,manifest_file:string}
     */
    private function manifest(Site $site, string $file): array
    {
        if (! is_file($file) || ! is_readable($file)) {
            throw new RuntimeException('Exact-link preview manifest is missing or unreadable.');
        }
        try {
            $manifest = json_decode((string) file_get_contents($file), true, 512, JSON_THROW_ON_ERROR);
        } catch (JsonException $error) {
            throw new RuntimeException('Exact-link preview manifest is invalid JSON.', previous: $error);
        }
        if (! is_array($manifest)
            || ($manifest['schema_version'] ?? null) !== 1
            || ($manifest['site_key'] ?? null) !== $site->key
            || ! is_int($manifest['source_run_id'] ?? null)
            || ! is_int($manifest['source_records'] ?? null)
            || ! is_string($manifest['source_manifest_sha256'] ?? null)
            || ! preg_match('/^[a-f0-9]{64}$/', $manifest['source_manifest_sha256'])
            || ! is_array($manifest['links'] ?? null)
            || count($manifest['links']) !== self::EXPECTED_LINKS) {
            throw new RuntimeException('Exact-link preview manifest must pin one source run/hash and exactly four links.');
        }

        return [
            'source_run_id' => $manifest['source_run_id'],
            'source_manifest_sha256' => $manifest['source_manifest_sha256'],
            'source_records' => $manifest['source_records'],
            'links' => array_values($manifest['links']),
            'manifest_file' => $file,
        ];
    }
}
