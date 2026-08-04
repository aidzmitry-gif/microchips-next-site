<?php

namespace App\Console\Commands;

use App\Domain\Content\DescriptionSourceEvidencePolicy;
use App\Domain\Content\ModelCoreIdentityMatcher;
use App\Domain\Imports\ProductIdentity;
use App\Models\CatalogDraftMaterialization;
use App\Models\Product;
use App\Models\ProductDescriptionDraft;
use App\Models\Site;
use App\Models\SiteCategory;
use App\Models\SiteProduct;
use App\Models\SiteProductPriceEvidence;
use App\Models\SiteRedirect;
use App\Models\SiteSeo;
use App\Models\SiteUrl;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\DB;
use RuntimeException;
use Throwable;

/**
 * Publishes a deliberately small, source-verified catalogue preview.
 *
 * The command is intentionally stricter than ordinary catalogue staging:
 * every item must have an already applied source-classified description,
 * an unambiguous category and a noindex canonical URL. It never creates an
 * offer, price, stock assertion or indexable URL.
 */
class PublishSourceVerifiedPreviewWave extends Command
{
    protected $signature = 'catalog:publish-source-verified-preview-wave
                            {site : Site key}
                            {file : JSON manifest describing the bounded preview wave}
                            {--apply : Persist the noindex preview wave; default is dry-run}';

    protected $description = 'Publish only source-verified products as noindex catalogue preview pages without stock claims';

    public function handle(): int
    {
        $site = Site::query()->where('key', (string) $this->argument('site'))->first();
        if ($site === null) {
            $this->error('Site was not found.');

            return self::FAILURE;
        }

        try {
            $summary = $this->publish($site, (string) $this->argument('file'), (bool) $this->option('apply'));
        } catch (Throwable $error) {
            $this->error($error->getMessage());

            return self::FAILURE;
        }

        $this->line(json_encode($summary, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE));

        return self::SUCCESS;
    }

    /** @return array{mode: string, products: int, categories: int, verified_priced_products: int, indexable_urls: int, offers_created: int} */
    private function publish(Site $site, string $file, bool $apply): array
    {
        $manifest = $this->manifest($file);
        if (($manifest['locale'] ?? null) !== $site->default_locale || ! is_array($manifest['products'] ?? null) || $manifest['products'] === []) {
            throw new RuntimeException('Manifest locale must match the site default locale and contain at least one product.');
        }
        $this->preflightManifest($site, $manifest['products']);

        $publishedCategoryIds = [];
        $verifiedPricedProducts = 0;
        $work = function () use ($site, $manifest, &$publishedCategoryIds, &$verifiedPricedProducts): void {
            foreach ($manifest['products'] as $index => $row) {
                if (! is_array($row)) {
                    throw new RuntimeException("Manifest row {$index} must be an object.");
                }
                $this->publishProduct($site, $row, $publishedCategoryIds, $verifiedPricedProducts);
            }
        };

        if ($apply) {
            DB::transaction($work);
        } else {
            DB::beginTransaction();
            try {
                $work();
            } finally {
                DB::rollBack();
            }
        }

        return [
            'mode' => $apply ? 'apply' : 'dry_run',
            'products' => count($manifest['products']),
            'categories' => count(array_unique($publishedCategoryIds)),
            'verified_priced_products' => $verifiedPricedProducts,
            'indexable_urls' => 0,
            'offers_created' => 0,
        ];
    }

    /** @param array<string, mixed> $row @param array<int, int> $publishedCategoryIds */
    private function publishProduct(Site $site, array $row, array &$publishedCategoryIds, int &$verifiedPricedProducts): void
    {
        foreach (['external_id', 'manufacturer', 'source_url', 'category_slug', 'product_slug'] as $field) {
            if (! is_string($row[$field] ?? null) || blank(trim($row[$field]))) {
                throw new RuntimeException("Preview manifest requires a non-empty {$field}.");
            }
        }
        $externalId = trim($row['external_id']);
        $manufacturer = trim($row['manufacturer']);
        $identityScope = $row['identity_scope'] ?? 'exact';
        if (! is_string($identityScope) || ! in_array($identityScope, ['exact', 'model_core'], true)) {
            throw new RuntimeException("Product {$externalId} identity_scope must be exact or model_core.");
        }
        $identityField = $identityScope === 'exact' ? 'mpn' : 'model_core';
        if (! is_string($row[$identityField] ?? null) || blank(trim($row[$identityField]))) {
            throw new RuntimeException("Product {$externalId} requires {$identityField} for {$identityScope} identity.");
        }
        $identity = trim($row[$identityField]);
        $sourceUrl = trim($row['source_url']);
        $productSlug = trim($row['product_slug']);
        if (! preg_match('/^[a-z0-9]+(?:-[a-z0-9]+)*$/', $productSlug)) {
            throw new RuntimeException("Product {$externalId} has an unsafe product_slug.");
        }

        $siteProduct = SiteProduct::query()
            ->with('product')
            ->where('site_id', $site->id)
            ->whereHas('product', fn ($query) => $query->where('external_id', $externalId))
            ->sole();
        $product = $siteProduct->product;
        if ($product === null || blank($product->short_description)) {
            throw new RuntimeException("Product {$externalId} has no applied source-backed description.");
        }
        $appliedEvidence = ProductDescriptionDraft::query()
            ->where('product_id', $product->id)
            ->where('locale', $site->default_locale)
            ->where('status', 'applied')
            ->whereJsonContains('source_urls', $sourceUrl)
            ->latest('id')
            ->first();
        if ($appliedEvidence === null) {
            throw new RuntimeException("Product {$externalId} has no applied description for the manifest source URL.");
        }
        $dealerBacked = $appliedEvidence->source_tier === DescriptionSourceEvidencePolicy::DEALER_TIER;
        $manufacturerPrimary = $appliedEvidence->source_tier === DescriptionSourceEvidencePolicy::MANUFACTURER_PRIMARY_TIER;
        if ($dealerBacked) {
            if ($appliedEvidence->source_kind !== DescriptionSourceEvidencePolicy::DEALER_KIND
                || $appliedEvidence->manufacturer_primary !== false
                || $appliedEvidence->identity_scope !== 'model_core') {
                throw new RuntimeException("Product {$externalId} has inconsistent dealer-backed provenance; preview publication was blocked.");
            }
            if ($identityScope !== 'model_core') {
                throw new RuntimeException("Product {$externalId} dealer-backed evidence cannot establish an exact MPN.");
            }
            if (filled($product->manufacturer)) {
                $this->assertIdentity($product->manufacturer, $manufacturer, 'manufacturer', $externalId);
            } elseif (! ModelCoreIdentityMatcher::nameContains($product->name, $manufacturer)) {
                throw new RuntimeException("Product {$externalId} name does not contain the dealer-backed manufacturer with exact boundaries.");
            }
        } elseif ($manufacturerPrimary) {
            $this->assertBitrixTransferEligibility($product, $siteProduct, $site, $externalId);
            if (! in_array($appliedEvidence->source_kind, [
                DescriptionSourceEvidencePolicy::MANUFACTURER_CATALOGUE_KIND,
                DescriptionSourceEvidencePolicy::MANUFACTURER_PRODUCT_PAGE_KIND,
            ], true)
                || $appliedEvidence->manufacturer_primary !== true) {
                throw new RuntimeException("Product {$externalId} has inconsistent manufacturer-primary provenance; preview publication was blocked.");
            }
            if ($appliedEvidence->identity_scope === 'model_core') {
                $verified = is_array($appliedEvidence->verified_fields) ? $appliedEvidence->verified_fields : [];
                foreach (['manufacturer' => $manufacturer, 'model' => $identity] as $field => $manifestValue) {
                    $evidenceValue = $verified[$field] ?? null;
                    if (! is_string($evidenceValue)
                        || ProductIdentity::normalize($evidenceValue) !== ProductIdentity::normalize($manifestValue)) {
                        throw new RuntimeException("Product {$externalId} applied manufacturer-primary {$field} does not match the preview manifest.");
                    }
                }
                if (! ModelCoreIdentityMatcher::nameContains($product->name, $manufacturer)
                    || ! ModelCoreIdentityMatcher::nameContains($product->name, $identity)) {
                    throw new RuntimeException("Product {$externalId} name does not preserve the manufacturer-primary model core.");
                }
                if (filled($product->manufacturer)) {
                    $this->assertIdentity($product->manufacturer, $manufacturer, 'manufacturer', $externalId);
                }
            } elseif ($appliedEvidence->identity_scope === 'exact' && $identityScope === 'exact') {
                $this->assertManufacturerPrimaryEvidenceIdentity(
                    $appliedEvidence,
                    $product,
                    $manufacturer,
                    $identity,
                    $externalId,
                );
                if (! ModelCoreIdentityMatcher::nameContains($product->name, $manufacturer)
                    || ! ModelCoreIdentityMatcher::nameEndsWith($product->name, $identity)) {
                    throw new RuntimeException("Product {$externalId} name does not preserve the manufacturer-primary exact identity.");
                }
                $this->assertIdentity($product->manufacturer, $manufacturer, 'manufacturer', $externalId);
            } else {
                throw new RuntimeException("Product {$externalId} has inconsistent manufacturer-primary identity scope; preview publication was blocked.");
            }
        } else {
            $this->assertIdentity($product->manufacturer, $manufacturer, 'manufacturer', $externalId);
        }
        if ($identityScope === 'exact') {
            $this->assertIdentity($product->mpn, $identity, 'mpn', $externalId);
            $mpnNormalized = ProductIdentity::normalize($identity);
            if ($mpnNormalized === null) {
                throw new RuntimeException("Product {$externalId} exact MPN cannot be normalized.");
            }
            $duplicate = Product::query()
                ->where(function ($query) use ($mpnNormalized): void {
                    $query->where('mpn_normalized', $mpnNormalized)
                        ->orWhere('sku_normalized', $mpnNormalized);
                })
                ->where('id', '<>', $product->id)
                ->first();
            if ($duplicate !== null) {
                throw new RuntimeException("Product {$externalId} exact MPN already belongs to {$duplicate->external_id}; preview publication was blocked.");
            }
            // A 1C record may carry the very same manufacturer part number in
            // both `sku` and `mpn`. This preview command never writes `sku`, so
            // that duplication is safe. A different SKU would be a competing
            // identity and remains a hard blocker rather than being silently
            // treated as the MPN from the manifest.
            if (filled($product->sku)
                && ProductIdentity::normalize($product->sku) !== ProductIdentity::normalize($identity)) {
                throw new RuntimeException("Product {$externalId} SKU conflicts with the verified MPN; preview publication was blocked.");
            }
        } elseif (! ModelCoreIdentityMatcher::nameContains($product->name, $identity)) {
            throw new RuntimeException("Product {$externalId} name does not contain the verified model_core with exact boundaries.");
        }
        if ($siteProduct->availability !== 'on_request') {
            throw new RuntimeException("Product {$externalId} has an availability claim; it cannot enter a noindex preview wave.");
        }
        $allowVerifiedPrice = $row['allow_verified_price'] ?? false;
        if (! is_bool($allowVerifiedPrice)) {
            throw new RuntimeException("Product {$externalId} allow_verified_price must be a boolean when present.");
        }
        if ($siteProduct->price !== null) {
            if (! $allowVerifiedPrice) {
                throw new RuntimeException("Product {$externalId} has a price; explicit allow_verified_price evidence is required.");
            }
            $hasCurrentEvidence = SiteProductPriceEvidence::query()
                ->where('site_id', $site->id)
                ->where('site_product_id', $siteProduct->id)
                ->where('is_current', true)
                ->whereIn('source', [SiteProductPriceEvidence::SOURCE_LEGACY_SITE, SiteProductPriceEvidence::SOURCE_ONE_C_X2])
                ->where('calculated_price', $siteProduct->price)
                ->where('currency', $site->currency_code)
                ->whereNotNull('observed_at')
                ->whereNotNull('price_type')
                ->whereNotNull('source_reference')
                ->exists();
            if (! $hasCurrentEvidence) {
                throw new RuntimeException("Product {$externalId} price has no matching current provenance evidence.");
            }
            $verifiedPricedProducts++;
        }

        $category = SiteCategory::query()
            ->with('category')
            ->where('site_id', $site->id)
            ->where('slug', trim($row['category_slug']))
            ->sole();
        $existingCategoryIds = $siteProduct->categories()->pluck('site_categories.id')->all();
        $replaceCategories = $row['replace_categories'] ?? false;
        if (! is_bool($replaceCategories)) {
            throw new RuntimeException("Product {$externalId} replace_categories must be a boolean when present.");
        }
        if ($existingCategoryIds !== [] && $existingCategoryIds !== [$category->id] && ! $replaceCategories) {
            throw new RuntimeException("Product {$externalId} already belongs to a different category; set explicit replace_categories only after review.");
        }
        if ($replaceCategories) {
            // A category replacement is deliberately opt-in per manifest row. This
            // prevents a source-verified content wave from silently creating
            // duplicate category memberships and duplicate commercial URLs.
            $siteProduct->categories()->sync([$category->id]);
        } else {
            $siteProduct->categories()->syncWithoutDetaching([$category->id]);
        }
        foreach ($this->categoryAncestors($site, $category) as $ancestor) {
            $categoryPath = $this->categoryPath($ancestor);
            $this->upsertNoindexUrl($site, $categoryPath, 'category', $ancestor->id);
            SiteSeo::query()->updateOrCreate(
                ['site_id' => $site->id, 'locale' => $site->default_locale, 'resource_type' => 'category', 'resource_id' => $ancestor->id],
                ['canonical_path' => $categoryPath, 'title' => $ancestor->name ?? $ancestor->category?->name, 'description' => null, 'is_indexable' => false, 'schema' => null],
            );
            $ancestor->update(['is_published' => true]);
            $publishedCategoryIds[] = $ancestor->id;
        }

        $productPath = $this->categoryPath($category).'/'.$productSlug;
        $this->retirePreviousNoindexProductPaths($site, $siteProduct, $productPath);
        $this->upsertNoindexUrl($site, $productPath, 'product', $siteProduct->id);
        SiteSeo::query()->updateOrCreate(
            ['site_id' => $site->id, 'locale' => $site->default_locale, 'resource_type' => 'product', 'resource_id' => $siteProduct->id],
            ['canonical_path' => $productPath, 'title' => $product->name, 'description' => $product->short_description, 'is_indexable' => false, 'schema' => null],
        );

        $productUpdate = [];
        if (! $dealerBacked) {
            $productUpdate['manufacturer'] = $manufacturer;
        }
        if ($identityScope === 'exact') {
            $productUpdate['mpn'] = $identity;
        }
        if ($productUpdate !== []) {
            $product->update($productUpdate);
        }
        $siteProduct->update(['slug' => $productSlug, 'is_published' => true]);
    }

    private function retirePreviousNoindexProductPaths(Site $site, SiteProduct $siteProduct, string $newPath): void
    {
        $previousUrls = SiteUrl::query()
            ->where('site_id', $site->id)
            ->where('target_type', 'product')
            ->where('target_id', $siteProduct->id)
            ->where('path', '<>', $newPath)
            ->get();

        foreach ($previousUrls as $previousUrl) {
            if ($previousUrl->is_indexable) {
                throw new RuntimeException("Indexable product path {$previousUrl->path} cannot be replaced by the preview workflow.");
            }

            SiteRedirect::query()->updateOrCreate(
                ['site_id' => $site->id, 'source_path' => $previousUrl->path],
                [
                    'target_path' => $newPath,
                    'status_code' => 301,
                    'purpose' => SiteRedirect::PURPOSE_PREVIEW,
                    'is_active' => true,
                ],
            );
            $previousUrl->delete();
        }
    }

    private function assertIdentity(?string $current, string $incoming, string $field, string $externalId): void
    {
        if (filled($current) && mb_strtolower(trim($current)) !== mb_strtolower($incoming)) {
            throw new RuntimeException("Product {$externalId} {$field} conflicts with the verified manifest.");
        }
    }

    private function assertManufacturerPrimaryEvidenceIdentity(
        ProductDescriptionDraft $appliedEvidence,
        Product $product,
        string $manifestManufacturer,
        string $manifestMpn,
        string $externalId,
    ): void {
        $identities = [
            'manufacturer' => [
                data_get($appliedEvidence->verified_fields, 'manufacturer'),
                $product->manufacturer,
                $manifestManufacturer,
            ],
            'mpn' => [
                data_get($appliedEvidence->verified_fields, 'mpn'),
                $product->mpn,
                $manifestMpn,
            ],
        ];

        foreach ($identities as $field => [$evidenceValue, $productValue, $manifestValue]) {
            $evidenceNormalized = ProductIdentity::normalize($evidenceValue);
            $productNormalized = ProductIdentity::normalize($productValue);
            $manifestNormalized = ProductIdentity::normalize($manifestValue);
            if ($evidenceNormalized === null
                || $productNormalized === null
                || $manifestNormalized === null
                || $evidenceNormalized !== $manifestNormalized
                || $productNormalized !== $manifestNormalized) {
                throw new RuntimeException("Product {$externalId} applied manufacturer-primary {$field} does not match the product and preview manifest.");
            }
        }
    }

    private function assertBitrixTransferEligibility(Product $product, SiteProduct $siteProduct, Site $site, string $externalId): void
    {
        if (! str_starts_with($externalId, 'bitrix:')) {
            return;
        }

        $materialization = CatalogDraftMaterialization::query()
            ->with(['sourceImportRun', 'stagedImportRecord.importRun'])
            ->where('site_id', $site->id)
            ->where('product_id', $product->id)
            ->where('site_product_id', $siteProduct->id)
            ->where('source_namespace', 'bitrix')
            ->where('source_external_id', $externalId)
            ->where('materialization_kind', CatalogDraftMaterialization::KIND_NAMESPACED_DRAFT)
            ->whereHas('stagedImportRecord', static function ($query) use ($externalId): void {
                $query->where('entity_type', 'bitrix_full_catalog_product_evidence')
                    ->where('external_id', $externalId)
                    ->where('status', 'staged_evidence');
            })
            ->first();
        if ($materialization === null || $materialization->stagedImportRecord === null) {
            throw new RuntimeException("Product {$externalId} has no eligible pinned Bitrix staging lineage; preview publication was blocked.");
        }

        $stagedRecord = $materialization->stagedImportRecord;
        $expectedSource = 'bitrix_full_catalog_snapshot:'.$site->key;
        if ((int) $materialization->source_import_run_id !== (int) $stagedRecord->import_run_id
            || $materialization->sourceImportRun?->source !== $expectedSource
            || $stagedRecord->importRun?->source !== $expectedSource) {
            throw new RuntimeException("Product {$externalId} has inconsistent Bitrix source-run lineage; preview publication was blocked.");
        }

        $normalizedStatus = data_get($stagedRecord->normalized_payload, 'transfer_status');
        $payloadStatus = data_get($stagedRecord->payload, 'transfer_status');
        if ($normalizedStatus !== 'legacy_only_draft_candidate' || $payloadStatus !== 'legacy_only_draft_candidate') {
            throw new RuntimeException("Product {$externalId} has no eligible pinned Bitrix staging lineage; preview publication was blocked.");
        }
    }

    /** @param list<mixed> $rows */
    private function preflightManifest(Site $site, array $rows): void
    {
        $seenExternalIds = [];
        $seenSlugs = [];
        $seenPaths = [];
        $planned = [];
        foreach ($rows as $index => $row) {
            if (! is_array($row)) {
                throw new RuntimeException("Manifest row {$index} must be an object.");
            }
            foreach (['external_id', 'category_slug', 'product_slug'] as $field) {
                if (! is_string($row[$field] ?? null) || blank(trim($row[$field]))) {
                    throw new RuntimeException("Preview manifest requires a non-empty {$field}.");
                }
            }
            $externalId = trim($row['external_id']);
            $productSlug = trim($row['product_slug']);
            if (! preg_match('/^[a-z0-9]+(?:-[a-z0-9]+)*$/', $productSlug)) {
                throw new RuntimeException("Product {$externalId} has an unsafe product_slug.");
            }
            if (isset($seenExternalIds[$externalId])) {
                throw new RuntimeException("Preview manifest repeats external_id {$externalId}.");
            }
            if (isset($seenSlugs[$productSlug])) {
                throw new RuntimeException("Preview manifest repeats product_slug {$productSlug}.");
            }
            $categorySlug = trim($row['category_slug'], '/');
            $categorySlug = preg_replace('#^catalog/#', '', $categorySlug) ?? $categorySlug;
            if ($categorySlug === '' || str_contains($categorySlug, '..')) {
                throw new RuntimeException("Product {$externalId} has an unsafe category_slug.");
            }
            $path = '/catalog/'.$categorySlug.'/'.$productSlug;
            if (isset($seenPaths[$path])) {
                throw new RuntimeException("Preview manifest repeats canonical path {$path}.");
            }
            $seenExternalIds[$externalId] = true;
            $seenSlugs[$productSlug] = true;
            $seenPaths[$path] = true;
            $planned[$externalId] = ['slug' => $productSlug, 'path' => $path];
        }

        $siteProducts = SiteProduct::query()
            ->with('product')
            ->where('site_id', $site->id)
            ->whereHas('product', fn ($query) => $query->whereIn('external_id', array_keys($planned)))
            ->get();
        $byExternalId = $siteProducts->keyBy('product.external_id');
        if ($byExternalId->count() !== count($planned)) {
            $missing = array_values(array_diff(array_keys($planned), $byExternalId->keys()->all()));
            throw new RuntimeException('Some preview products are not linked to the site: '.implode(', ', array_slice($missing, 0, 10)));
        }
        $existingBySlug = SiteProduct::query()
            ->where('site_id', $site->id)
            ->whereIn('slug', array_column($planned, 'slug'))
            ->get()
            ->keyBy('slug');
        $existingByPath = SiteUrl::query()
            ->where('site_id', $site->id)
            ->whereIn('path', array_column($planned, 'path'))
            ->get()
            ->keyBy('path');

        foreach ($planned as $externalId => $item) {
            /** @var SiteProduct $siteProduct */
            $siteProduct = $byExternalId->get($externalId);
            $slugOwner = $existingBySlug->get($item['slug']);
            if ($slugOwner !== null && $slugOwner->id !== $siteProduct->id) {
                throw new RuntimeException("Product slug {$item['slug']} already belongs to another site product.");
            }
            $url = $existingByPath->get($item['path']);
            if ($url !== null && ($url->target_type !== 'product' || $url->target_id !== $siteProduct->id || $url->is_indexable)) {
                throw new RuntimeException("Canonical path {$item['path']} belongs to another or indexable resource.");
            }
        }
        if (SiteSeo::query()
            ->where('site_id', $site->id)
            ->where('locale', $site->default_locale)
            ->where('resource_type', 'product')
            ->whereIn('resource_id', $siteProducts->pluck('id'))
            ->where('is_indexable', true)
            ->exists()) {
            throw new RuntimeException('An indexable product SEO record cannot enter a noindex preview manifest.');
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
                throw new RuntimeException('Category tree is incomplete for the preview wave.');
            }
        }

        return $result;
    }

    private function categoryPath(SiteCategory $category): string
    {
        $slug = trim((string) $category->slug, '/');
        $slug = preg_replace('#^catalog/#', '', $slug) ?? $slug;
        if ($slug === '' || str_contains($slug, '..')) {
            throw new RuntimeException('Category has no safe canonical slug.');
        }

        return '/catalog/'.$slug;
    }

    private function upsertNoindexUrl(Site $site, string $path, string $targetType, int $targetId): void
    {
        $existing = SiteUrl::query()->where('site_id', $site->id)->where('path', $path)->first();
        if ($existing !== null && ($existing->target_type !== $targetType || $existing->target_id !== $targetId || $existing->is_indexable)) {
            throw new RuntimeException("Path {$path} is already reserved by a different or indexable resource.");
        }
        SiteUrl::query()->updateOrCreate(
            ['site_id' => $site->id, 'path' => $path],
            ['locale' => $site->default_locale, 'target_type' => $targetType, 'target_id' => $targetId, 'is_indexable' => false],
        );
    }

    /** @return array<string, mixed> */
    private function manifest(string $file): array
    {
        if (! is_readable($file)) {
            throw new RuntimeException('Preview manifest is not readable.');
        }
        try {
            $manifest = json_decode((string) file_get_contents($file), true, 512, JSON_THROW_ON_ERROR);
        } catch (\JsonException $error) {
            throw new RuntimeException('Preview manifest is not valid JSON.', previous: $error);
        }

        if (! is_array($manifest)) {
            throw new RuntimeException('Preview manifest must be an object.');
        }

        return $manifest;
    }
}
