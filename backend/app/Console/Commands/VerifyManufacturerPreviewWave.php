<?php

namespace App\Console\Commands;

use App\Domain\Content\DescriptionSourceEvidencePolicy;
use App\Domain\Content\ModelCoreIdentityMatcher;
use App\Models\Product;
use App\Models\ProductDescriptionDraft;
use App\Models\Site;
use App\Models\SiteProduct;
use App\Models\SiteProductPriceEvidence;
use App\Models\SiteSeo;
use App\Models\SiteUrl;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\DB;
use JsonException;
use RuntimeException;
use Throwable;

/** Read-only proof that a manufacturer preview manifest matches the persisted catalogue. */
class VerifyManufacturerPreviewWave extends Command
{
    protected $signature = 'catalog:verify-manufacturer-preview-wave
                            {site : Site key}
                            {file : The applied preview JSON manifest}';

    protected $description = 'Verify an applied manufacturer preview wave without changing catalogue data';

    public function handle(): int
    {
        try {
            $site = Site::query()->where('key', (string) $this->argument('site'))->firstOrFail();
            $manifest = $this->manifest((string) $this->argument('file'));
            if (($manifest['locale'] ?? null) !== $site->default_locale || ! is_array($manifest['products'] ?? null)) {
                throw new RuntimeException('Manifest locale must match the site default locale and contain products.');
            }

            $errors = [];
            $siteProductIds = [];
            $paths = [];
            $mpns = [];
            foreach ($manifest['products'] as $index => $row) {
                if (! is_array($row)) {
                    $errors[] = "Row {$index} must be an object.";

                    continue;
                }
                foreach (['external_id', 'manufacturer', 'category_slug', 'product_slug'] as $field) {
                    if (! is_string($row[$field] ?? null) || blank(trim($row[$field]))) {
                        $errors[] = "Row {$index} requires {$field}.";

                        continue 2;
                    }
                }
                $product = Product::query()->where('external_id', trim($row['external_id']))->first();
                if ($product === null) {
                    $errors[] = "Missing product {$row['external_id']}.";

                    continue;
                }
                $identityScope = $row['identity_scope'] ?? 'exact';
                if (! is_string($identityScope) || ! in_array($identityScope, ['exact', 'model_core'], true)) {
                    $errors[] = "Product {$row['external_id']} has an invalid identity scope.";

                    continue;
                }
                if ($identityScope === 'exact') {
                    if (trim((string) $product->manufacturer) !== trim($row['manufacturer'])) {
                        $errors[] = "Product {$row['external_id']} has a different manufacturer.";
                    }
                    if (! is_string($row['mpn'] ?? null) || blank(trim($row['mpn'])) || trim((string) $product->mpn) !== trim($row['mpn'])) {
                        $errors[] = "Product {$row['external_id']} has a different MPN.";
                    }
                } else {
                    $modelCore = is_string($row['model_core'] ?? null) ? trim($row['model_core']) : '';
                    if ($modelCore === '' || ! ModelCoreIdentityMatcher::nameContains($product->name, $modelCore)) {
                        $errors[] = "Product {$row['external_id']} does not contain the verified model core.";
                    }
                    if (filled($product->manufacturer)
                        && trim((string) $product->manufacturer) !== trim($row['manufacturer'])) {
                        $errors[] = "Product {$row['external_id']} has a different manufacturer.";
                    }
                    $sourceUrl = is_string($row['source_url'] ?? null) ? trim($row['source_url']) : '';
                    $evidence = $sourceUrl === '' ? null : ProductDescriptionDraft::query()
                        ->where('product_id', $product->id)
                        ->where('locale', $site->default_locale)
                        ->where('status', 'applied')
                        ->whereJsonContains('source_urls', $sourceUrl)
                        ->latest('id')
                        ->first();
                    if ($evidence === null
                        || $evidence->source_tier !== DescriptionSourceEvidencePolicy::DEALER_TIER
                        || $evidence->source_kind !== DescriptionSourceEvidencePolicy::DEALER_KIND
                        || $evidence->manufacturer_primary !== false
                        || $evidence->identity_scope !== 'model_core') {
                        $errors[] = "Product {$row['external_id']} has no matching applied dealer-backed evidence.";
                    }
                }
                if (filled($product->mpn)) {
                    $mpns[] = $product->mpn_normalized;
                }

                $siteProduct = SiteProduct::query()
                    ->where('site_id', $site->id)
                    ->where('product_id', $product->id)
                    ->first();
                if ($siteProduct === null) {
                    $errors[] = "Product {$row['external_id']} has no site product.";

                    continue;
                }
                $siteProductIds[] = $siteProduct->id;
                if (! $siteProduct->is_published || $siteProduct->availability !== 'on_request' || $siteProduct->price !== null) {
                    $errors[] = "Product {$row['external_id']} violates the published no-price/on-request boundary.";
                }

                $path = '/'.trim($row['category_slug'], '/').'/'.trim($row['product_slug'], '/');
                $paths[] = $path;
                $url = SiteUrl::query()
                    ->where('site_id', $site->id)
                    ->where('path', $path)
                    ->where('target_type', 'product')
                    ->where('target_id', $siteProduct->id)
                    ->first();
                if ($url === null || $url->is_indexable) {
                    $errors[] = "Product {$row['external_id']} has no exact noindex URL {$path}.";
                }
                $seo = SiteSeo::query()
                    ->where('site_id', $site->id)
                    ->where('locale', $site->default_locale)
                    ->where('resource_type', 'product')
                    ->where('resource_id', $siteProduct->id)
                    ->first();
                if ($seo === null || $seo->canonical_path !== $path || $seo->is_indexable || $seo->schema !== null) {
                    $errors[] = "Product {$row['external_id']} has an invalid preview SEO record.";
                }
                if (! $siteProduct->categories()->where('site_categories.slug', trim($row['category_slug'], '/'))->exists()) {
                    $errors[] = "Product {$row['external_id']} is not linked to {$row['category_slug']}.";
                }
            }

            $priceEvidenceCount = SiteProductPriceEvidence::query()
                ->whereIn('site_product_id', $siteProductIds)
                ->count();
            if ($priceEvidenceCount !== 0) {
                $errors[] = "Wave has {$priceEvidenceCount} unexpected price evidence row(s).";
            }
            if (count(array_unique($paths)) !== count($paths)) {
                $errors[] = 'Wave contains duplicate paths.';
            }
            if (count(array_unique($mpns)) !== count($mpns)) {
                $errors[] = 'Wave contains duplicate normalized MPNs.';
            }

            $duplicateMpnGroups = DB::table('products')
                ->whereNotNull('mpn_normalized')
                ->select('mpn_normalized')
                ->groupBy('mpn_normalized')
                ->havingRaw('count(*) > 1')
                ->get()
                ->count();
            if ($duplicateMpnGroups !== 0) {
                $errors[] = "Catalogue contains {$duplicateMpnGroups} duplicate normalized MPN group(s).";
            }

            $summary = [
                'site' => $site->key,
                'records' => count($manifest['products']),
                'products_found' => count($siteProductIds),
                'distinct_paths' => count(array_unique($paths)),
                'price_evidence_rows' => $priceEvidenceCount,
                'duplicate_mpn_groups' => $duplicateMpnGroups,
                'errors' => $errors,
                'passed' => $errors === [],
            ];
            $this->line(json_encode($summary, JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT | JSON_THROW_ON_ERROR));

            return $errors === [] ? self::SUCCESS : self::FAILURE;
        } catch (Throwable $error) {
            $this->error($error->getMessage());

            return self::FAILURE;
        }
    }

    /** @return array<string, mixed> */
    private function manifest(string $file): array
    {
        if (! is_readable($file)) {
            throw new RuntimeException('Preview manifest is not readable.');
        }
        try {
            $manifest = json_decode((string) file_get_contents($file), true, 512, JSON_THROW_ON_ERROR);
        } catch (JsonException $error) {
            throw new RuntimeException('Preview manifest is not valid JSON.', previous: $error);
        }
        if (! is_array($manifest)) {
            throw new RuntimeException('Preview manifest must be an object.');
        }

        return $manifest;
    }
}
