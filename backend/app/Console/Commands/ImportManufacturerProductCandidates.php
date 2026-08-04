<?php

namespace App\Console\Commands;

use App\Domain\Content\ModelCoreIdentityMatcher;
use App\Domain\Imports\ProductIdentity;
use App\Models\Product;
use App\Models\Site;
use App\Models\SiteCategory;
use App\Models\SiteProduct;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\DB;
use RuntimeException;
use Throwable;

/** Creates source-identified manufacturer products as unpublished market drafts. */
class ImportManufacturerProductCandidates extends Command
{
    protected $signature = 'catalog:import-manufacturer-product-candidates
                            {site : Site key}
                            {file : Reviewed JSON manufacturer manifest}
                            {--apply : Persist candidates; default is dry-run}';

    protected $description = 'Create deduplicated manufacturer-backed product candidates without URLs, prices, stock claims or publication';

    public function handle(): int
    {
        $site = Site::query()->where('key', (string) $this->argument('site'))->first();
        if ($site === null) {
            $this->error('Site was not found.');

            return self::FAILURE;
        }

        try {
            $summary = $this->import($site, (string) $this->argument('file'), (bool) $this->option('apply'));
        } catch (Throwable $error) {
            $this->error($error->getMessage());

            return self::FAILURE;
        }

        $this->line(json_encode($summary, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE));

        return self::SUCCESS;
    }

    /** @return array{mode:string,records:int,created:int,unchanged:int,published:int,indexable_urls:int,prices_created:int} */
    private function import(Site $site, string $file, bool $apply): array
    {
        if (! is_file($file) || ! is_readable($file)) {
            throw new RuntimeException('Manufacturer product manifest is not readable.');
        }
        $manifest = json_decode((string) file_get_contents($file), true, 512, JSON_THROW_ON_ERROR);
        if (($manifest['schema_version'] ?? null) !== 1
            || ($manifest['site_key'] ?? null) !== $site->key
            || ! is_array($manifest['products'] ?? null)
            || $manifest['products'] === []) {
            throw new RuntimeException('Manifest schema_version/site_key/products are invalid.');
        }

        $created = 0;
        $unchanged = 0;
        $seenExternalIds = [];
        $seenMpns = [];
        $existingNamedProducts = Product::query()->get(['id', 'external_id', 'manufacturer', 'name']);
        $work = function () use ($site, $manifest, $existingNamedProducts, &$created, &$unchanged, &$seenExternalIds, &$seenMpns): void {
            foreach ($manifest['products'] as $index => $row) {
                if (! is_array($row)) {
                    throw new RuntimeException("Product row {$index} must be an object.");
                }
                foreach (['external_id', 'manufacturer', 'mpn', 'name', 'slug', 'category_external_id', 'source_url'] as $field) {
                    if (! is_string($row[$field] ?? null) || blank(trim($row[$field]))) {
                        throw new RuntimeException("Product row {$index} requires {$field}.");
                    }
                }
                $externalId = trim($row['external_id']);
                $mpn = trim($row['mpn']);
                $slug = trim($row['slug']);
                $sourceUrl = trim($row['source_url']);
                if (isset($seenExternalIds[mb_strtolower($externalId)]) || isset($seenMpns[mb_strtolower($mpn)])) {
                    throw new RuntimeException("Product row {$index} repeats an external_id or MPN in the manifest.");
                }
                $seenExternalIds[mb_strtolower($externalId)] = true;
                $seenMpns[mb_strtolower($mpn)] = true;
                if (! preg_match('/^[a-z0-9]+(?:-[a-z0-9]+)*$/', $slug)) {
                    throw new RuntimeException("Product {$externalId} has an unsafe slug.");
                }
                if (! filter_var($sourceUrl, FILTER_VALIDATE_URL) || parse_url($sourceUrl, PHP_URL_SCHEME) !== 'https') {
                    throw new RuntimeException("Product {$externalId} source_url must be HTTPS.");
                }
                if (! is_array($row['technical_attributes'] ?? null)
                    || $row['technical_attributes'] === []
                    || collect($row['technical_attributes'])->contains(fn (mixed $value): bool => ! is_string($value) || blank($value))) {
                    throw new RuntimeException("Product {$externalId} requires a non-empty string technical_attributes map.");
                }

                $category = SiteCategory::query()
                    ->where('site_id', $site->id)
                    ->where('external_id', trim($row['category_external_id']))
                    ->where('is_published', true)
                    ->sole();
                $externalIdNormalized = ProductIdentity::normalize($externalId);
                $mpnNormalized = ProductIdentity::normalize($mpn);
                $existing = Product::query()->where('external_id_normalized', $externalIdNormalized)->first();
                if ($existing !== null) {
                    if (ProductIdentity::normalize($existing->mpn) !== $mpnNormalized
                        || ProductIdentity::normalize($existing->manufacturer) !== ProductIdentity::normalize(trim($row['manufacturer']))) {
                        throw new RuntimeException("Product {$externalId} conflicts with an existing identity.");
                    }
                    $unchanged++;

                    continue;
                }
                $identityConflict = Product::query()
                    ->where('mpn_normalized', $mpnNormalized)
                    ->orWhere('sku_normalized', $mpnNormalized)
                    ->exists();
                if ($identityConflict) {
                    throw new RuntimeException("Product {$externalId} duplicates an existing SKU/MPN.");
                }
                $manufacturer = trim($row['manufacturer']);
                $hiddenNameConflict = $existingNamedProducts->first(
                    fn (Product $product): bool => (ProductIdentity::normalize($product->manufacturer) === ProductIdentity::normalize($manufacturer)
                            || ModelCoreIdentityMatcher::nameContains($product->name, $manufacturer))
                        && ModelCoreIdentityMatcher::nameContains($product->name, $mpn)
                );
                if ($hiddenNameConflict !== null) {
                    throw new RuntimeException(
                        "Product {$externalId} duplicates manufacturer/model tokens in existing product {$hiddenNameConflict->external_id}."
                    );
                }

                $product = Product::query()->create([
                    'external_id' => $externalId,
                    'manufacturer' => $manufacturer,
                    'mpn' => $mpn,
                    'slug' => $slug,
                    'name' => trim($row['name']),
                    'short_description' => null,
                    'technical_attributes' => [],
                    'status' => 'draft',
                ]);
                $siteProduct = SiteProduct::query()->create([
                    'site_id' => $site->id,
                    'product_id' => $product->id,
                    'slug' => $slug,
                    'is_published' => false,
                    'availability' => 'on_request',
                    'price' => null,
                    'seo' => [
                        'source' => 'manufacturer_official',
                        'source_url' => $sourceUrl,
                        'migration_status' => 'source_backed_candidate',
                    ],
                ]);
                $siteProduct->categories()->attach($category->id);
                $created++;
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
            'records' => count($manifest['products']),
            'created' => $created,
            'unchanged' => $unchanged,
            'published' => 0,
            'indexable_urls' => 0,
            'prices_created' => 0,
        ];
    }
}
