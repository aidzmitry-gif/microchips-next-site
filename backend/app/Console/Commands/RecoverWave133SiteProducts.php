<?php

namespace App\Console\Commands;

use App\Models\Product;
use App\Models\Site;
use App\Models\SiteCategory;
use App\Models\SiteProduct;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\DB;
use RuntimeException;
use Throwable;

/**
 * Fail-closed recovery of the immutable Wave133 catalogue snapshot.
 *
 * This command restores catalogue structure only. New SiteProducts are always
 * unpublished and carry no price/SEO/URL. Existing records are never updated.
 */
class RecoverWave133SiteProducts extends Command
{
    private const SITE_KEY = 'microchips-by';

    private const SNAPSHOT_SHA256 = '19cadbd298f6326e8675e0b834730af7f198a203e05ec55027f554eabf408985';

    private const SNAPSHOT_ROWS = 558;

    protected $signature = 'catalog:recover-wave133-site-products
                            {site : Must be microchips-by}
                            {file : Immutable rb-applied-site-product-state-wave133.json snapshot}
                            {--apply : Persist missing drafts; otherwise validate in a rolled-back transaction}';

    protected $description = 'Recover only missing Wave133 products, unpublished site drafts and category links';

    public function handle(): int
    {
        try {
            $site = $this->guardedSite();
            $rows = $this->snapshot((string) $this->argument('file'));
            $apply = (bool) $this->option('apply');
            $summary = $this->recover($site, $rows, $apply);
            $this->line((string) json_encode([
                'mode' => $apply ? 'apply' : 'dry_run',
                'site' => $site->key,
                'snapshot_sha256' => self::SNAPSHOT_SHA256,
                'records' => self::SNAPSHOT_ROWS,
                ...$summary,
                'urls_created' => 0,
                'prices_created' => 0,
                'published_site_products_created' => 0,
            ], JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE));

            return self::SUCCESS;
        } catch (Throwable $error) {
            $this->error($error->getMessage());

            return self::FAILURE;
        }
    }

    private function guardedSite(): Site
    {
        if ((string) $this->argument('site') !== self::SITE_KEY) {
            throw new RuntimeException('Wave133 recovery is restricted to site microchips-by.');
        }
        $site = Site::query()->where('key', self::SITE_KEY)->first();
        if ($site === null) {
            throw new RuntimeException('Required site microchips-by does not exist.');
        }

        return $site;
    }

    /** @return list<array<string, mixed>> */
    private function snapshot(string $path): array
    {
        if (! is_file($path) || ! is_readable($path)) {
            throw new RuntimeException('Wave133 snapshot is missing or unreadable.');
        }
        if (hash_file('sha256', $path) !== self::SNAPSHOT_SHA256) {
            throw new RuntimeException('Wave133 snapshot SHA-256 mismatch.');
        }
        $rows = json_decode((string) file_get_contents($path), true, 512, JSON_THROW_ON_ERROR);
        if (! is_array($rows) || ! array_is_list($rows) || count($rows) !== self::SNAPSHOT_ROWS) {
            throw new RuntimeException('Wave133 snapshot must contain exactly 558 rows.');
        }

        $externalIds = [];
        $productSlugs = [];
        $siteSlugs = [];
        foreach ($rows as $index => $row) {
            if (! is_array($row) || ($row['site_id'] ?? null) !== 1 || ! is_array($row['product'] ?? null)
                || ! is_array($row['categories'] ?? null) || count($row['categories']) !== 1) {
                throw new RuntimeException("Wave133 row {$index} has invalid site/product/category topology.");
            }
            $product = $row['product'];
            foreach (['external_id', 'slug', 'name', 'status'] as $field) {
                if (! is_string($product[$field] ?? null) || trim($product[$field]) === '') {
                    throw new RuntimeException("Wave133 row {$index} product requires {$field}.");
                }
            }
            if (! is_string($row['slug'] ?? null) || trim($row['slug']) === '') {
                throw new RuntimeException("Wave133 row {$index} requires a site-product slug.");
            }
            $category = $row['categories'][0];
            foreach (['external_id', 'slug', 'name', 'source'] as $field) {
                if (! is_string($category[$field] ?? null) || trim($category[$field]) === '') {
                    throw new RuntimeException("Wave133 row {$index} category requires {$field}.");
                }
            }
            $this->uniqueSnapshotValue($externalIds, $product['external_id'], 'external_id');
            $this->uniqueSnapshotValue($productSlugs, $product['slug'], 'product slug');
            $this->uniqueSnapshotValue($siteSlugs, $row['slug'], 'site-product slug');
        }

        return $rows;
    }

    /** @param array<string, true> $seen */
    private function uniqueSnapshotValue(array &$seen, string $value, string $label): void
    {
        if (isset($seen[$value])) {
            throw new RuntimeException("Wave133 snapshot repeats {$label} {$value}.");
        }
        $seen[$value] = true;
    }

    /**
     * @param  list<array<string, mixed>>  $rows
     * @return array{products_created:int,site_products_created:int,category_links_created:int,unchanged:int}
     */
    private function recover(Site $site, array $rows, bool $apply): array
    {
        $summary = ['products_created' => 0, 'site_products_created' => 0, 'category_links_created' => 0, 'unchanged' => 0];
        DB::beginTransaction();
        try {
            foreach ($rows as $index => $row) {
                $this->recoverRow($site, $row, $index, $summary);
            }
            if ($apply) {
                DB::commit();
            } else {
                DB::rollBack();
            }
        } catch (Throwable $error) {
            DB::rollBack();
            throw $error;
        }

        return $summary;
    }

    /** @param array<string, mixed> $row
     * @param array{products_created:int,site_products_created:int,category_links_created:int,unchanged:int} $summary */
    private function recoverRow(Site $site, array $row, int $index, array &$summary): void
    {
        $source = $row['product'];
        $externalId = trim($source['external_id']);
        $expectedProduct = [
            'external_id' => $externalId,
            'sku' => $this->nullableString($source['sku'] ?? null),
            'mpn' => $this->nullableString($source['mpn'] ?? null),
            'manufacturer' => $this->nullableString($source['manufacturer'] ?? null),
            'slug' => trim($source['slug']),
            'name' => $source['name'],
            'short_description' => $this->nullableString($source['short_description'] ?? null),
            'technical_attributes' => is_array($source['technical_attributes'] ?? null) ? $source['technical_attributes'] : null,
            'status' => trim($source['status']),
        ];
        $product = Product::query()->where('external_id', $externalId)->first();
        if ($product === null) {
            $slugOwner = Product::query()->where('slug', $expectedProduct['slug'])->first();
            if ($slugOwner !== null) {
                throw new RuntimeException("Wave133 row {$index} product slug belongs to {$slugOwner->external_id}.");
            }
            $product = Product::query()->create($expectedProduct);
            $summary['products_created']++;
        } else {
            $this->assertProductExact($product, $expectedProduct, $index);
        }

        $siteSlug = trim($row['slug']);
        $siteProduct = SiteProduct::query()->where('site_id', $site->id)->where('product_id', $product->id)->first();
        if ($siteProduct === null) {
            $slugOwner = SiteProduct::query()->where('site_id', $site->id)->where('slug', $siteSlug)->first();
            if ($slugOwner !== null) {
                throw new RuntimeException("Wave133 row {$index} site slug belongs to another product.");
            }
            $siteProduct = SiteProduct::withoutEvents(fn (): SiteProduct => SiteProduct::query()->create([
                'site_id' => $site->id,
                'product_id' => $product->id,
                'slug' => $siteSlug,
                'is_published' => false,
                'availability' => 'on_request',
                'price' => null,
                'seo' => null,
                'sort_order' => 0,
            ]));
            $summary['site_products_created']++;
        } elseif ($siteProduct->slug !== $siteSlug) {
            throw new RuntimeException("Wave133 row {$index} existing site-product slug conflicts with the snapshot.");
        }

        $sourceCategory = $row['categories'][0];
        $category = SiteCategory::query()
            ->where('site_id', $site->id)
            ->where('external_id', $sourceCategory['external_id'])
            ->first();
        if ($category === null) {
            throw new RuntimeException("Wave133 row {$index} required site category {$sourceCategory['external_id']} is missing.");
        }
        foreach (['slug', 'name', 'source'] as $field) {
            if ($category->getAttribute($field) !== $sourceCategory[$field]) {
                throw new RuntimeException("Wave133 row {$index} site category {$field} conflicts with the snapshot.");
            }
        }
        $linked = $siteProduct->categories()->whereKey($category->id)->exists();
        if (! $linked) {
            if ($siteProduct->is_published) {
                throw new RuntimeException("Wave133 row {$index} refuses to change categories on an already-published site product.");
            }
            $siteProduct->categories()->attach($category->id, ['site_id' => $site->id]);
            $summary['category_links_created']++;
        } elseif ($product->wasRecentlyCreated === false && $siteProduct->wasRecentlyCreated === false) {
            $summary['unchanged']++;
        }
    }

    /** @param array<string, mixed> $expected */
    private function assertProductExact(Product $product, array $expected, int $index): void
    {
        foreach (['external_id', 'sku', 'mpn', 'manufacturer', 'slug', 'name', 'short_description', 'status'] as $field) {
            if ($product->getAttribute($field) !== $expected[$field]) {
                throw new RuntimeException("Wave133 row {$index} existing product {$field} conflicts with the snapshot.");
            }
        }
        if ($this->stable($product->technical_attributes) !== $this->stable($expected['technical_attributes'])) {
            throw new RuntimeException("Wave133 row {$index} existing product technical_attributes conflict with the snapshot.");
        }
    }

    private function nullableString(mixed $value): ?string
    {
        return is_string($value) && $value !== '' ? $value : null;
    }

    private function stable(mixed $value): string
    {
        if (is_array($value)) {
            if (! array_is_list($value)) {
                ksort($value);
            }
            foreach ($value as $key => $item) {
                $value[$key] = is_array($item) ? json_decode($this->stable($item), true, 512, JSON_THROW_ON_ERROR) : $item;
            }
        }

        return (string) json_encode($value, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE | JSON_THROW_ON_ERROR);
    }
}
