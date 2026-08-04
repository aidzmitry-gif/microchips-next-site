<?php

namespace Tests\Feature;

use App\Models\Category;
use App\Models\Product;
use App\Models\Site;
use App\Models\SiteCategory;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Artisan;
use Illuminate\Support\Facades\DB;
use Tests\TestCase;

class RecoverWave131SiteProductsTest extends TestCase
{
    use RefreshDatabase;

    private string $snapshot;

    private string $waves;

    private string $assignments;

    private string $wave133;

    protected function setUp(): void
    {
        parent::setUp();
        $this->snapshot = base_path('../docs/audits/generated/rb-site-product-state-wave131.json');
        $this->waves = base_path('../docs/imports/one-c-draft-waves');
        $this->assignments = base_path('../docs/imports/one-c-seo-category-assignments-refresh-2.csv');
        $this->wave133 = base_path('../docs/audits/generated/rb-applied-site-product-state-wave133.json');
        $this->seedSiteAndAllCurrentSeoCategories();
        $this->applyWave133RecoveryBaseline();
    }

    public function test_real_7015_snapshot_recovers_only_6457_missing_safe_drafts_and_is_idempotent(): void
    {
        $beforeWave133 = $this->wave133State();
        $args = $this->args();

        $exit = Artisan::call('catalog:recover-wave131-site-products', $args);
        $this->assertSame(0, $exit, Artisan::output());
        $this->assertDatabaseCount('products', 558);
        $this->assertSame($beforeWave133, $this->wave133State());

        $exit = Artisan::call('catalog:recover-wave131-site-products', [...$args, '--apply' => true]);
        $this->assertSame(0, $exit, Artisan::output());
        $this->assertDatabaseCount('products', 7015);
        $this->assertDatabaseCount('site_products', 7015);
        $this->assertDatabaseCount('site_category_product', 5946);
        $this->assertDatabaseCount('site_urls', 0);
        $this->assertSame(7015, DB::table('products')->where('status', 'active')->count());
        $this->assertSame(7015, DB::table('site_products')->where('is_published', false)->count());
        $this->assertSame(7015, DB::table('site_products')->where('availability', 'on_request')->count());
        $this->assertSame(0, DB::table('site_products')->whereNotNull('price')->count());
        $this->assertSame(0, DB::table('site_products')->whereNotNull('seo')->count());
        $this->assertSame(0, DB::table('site_category_product')->join('site_categories', 'site_categories.id', '=', 'site_category_product.site_category_id')->where('site_categories.external_id', '410')->count());
        // 925 assignment-backed links among the 6,457 new rows plus three
        // immutable Wave133 electronics links that are deliberately preserved.
        $this->assertSame(928, DB::table('site_category_product')->join('site_categories', 'site_categories.id', '=', 'site_category_product.site_category_id')->where('site_categories.external_id', 'seo:electronic-components')->count());
        $this->assertSame($beforeWave133, $this->wave133State());
        $this->assertPinnedWaveFieldsOnEveryNewProduct();

        $exit = Artisan::call('catalog:recover-wave131-site-products', [...$args, '--apply' => true]);
        $this->assertSame(0, $exit, Artisan::output());
        $this->assertDatabaseCount('products', 7015);
        $this->assertDatabaseCount('site_products', 7015);
        $this->assertDatabaseCount('site_category_product', 5946);
        $this->assertSame($beforeWave133, $this->wave133State());

        $wave133Ids = array_keys($beforeWave133);
        $conflict = Product::query()->whereNotIn('external_id', $wave133Ids)->orderBy('id')->firstOrFail();
        $conflict->name = 'conflicting Wave131 recovery name';
        $conflict->saveQuietly();
        $exit = Artisan::call('catalog:recover-wave131-site-products', [...$args, '--apply' => true]);
        $this->assertSame(1, $exit);
        $this->assertDatabaseCount('products', 7015);
        $this->assertDatabaseCount('site_products', 7015);
        $this->assertDatabaseCount('site_category_product', 5946);
        $this->assertSame($beforeWave133, $this->wave133State());
    }

    /** @return array<string,mixed> */
    private function args(): array
    {
        return ['site' => 'microchips-by', 'snapshot' => $this->snapshot, 'waves-dir' => $this->waves,
            'assignments' => $this->assignments, 'wave133' => $this->wave133];
    }

    private function seedSiteAndAllCurrentSeoCategories(): void
    {
        $site = Site::create(['key' => 'microchips-by', 'domain' => 'microchips-by.test', 'country_code' => 'BY',
            'currency_code' => 'BYN', 'default_locale' => 'ru-BY', 'name' => 'RB', 'is_active' => true]);
        $categories = [];
        foreach (json_decode((string) file_get_contents($this->wave133), true, 512, JSON_THROW_ON_ERROR) as $row) {
            $source = $row['categories'][0];
            $categories[$source['external_id']] = ['slug' => $source['slug'], 'name' => $source['name'], 'source' => $source['source']];
        }
        $handle = fopen($this->assignments, 'rb');
        fgetcsv($handle);
        while (($row = fgetcsv($handle)) !== false) {
            $categories[$row[1]] ??= ['slug' => 'catalog/recovery/'.substr(hash('sha256', $row[1]), 0, 16),
                'name' => $row[1], 'source' => 'recovery-test-current-seo-tree'];
        }
        fclose($handle);
        foreach ($categories as $externalId => $source) {
            $canonical = Category::create(['slug' => 'canonical-'.substr(hash('sha256', $externalId), 0, 16),
                'name' => $source['name'], 'sort_order' => 0]);
            SiteCategory::create(['site_id' => $site->id, 'category_id' => $canonical->id,
                'source' => $source['source'], 'external_id' => $externalId, 'slug' => $source['slug'],
                'name' => $source['name'], 'seo' => null, 'is_published' => false, 'sort_order' => 0]);
        }
    }

    private function applyWave133RecoveryBaseline(): void
    {
        $exit = Artisan::call('catalog:recover-wave133-site-products', [
            'site' => 'microchips-by', 'file' => $this->wave133, '--apply' => true,
        ]);
        $this->assertSame(0, $exit, Artisan::output());
        $this->assertDatabaseCount('products', 558);
        $this->assertDatabaseCount('site_products', 558);
        $this->assertDatabaseCount('site_category_product', 558);
    }

    /** @return array<string,array<string,mixed>> */
    private function wave133State(): array
    {
        $ids = collect(json_decode((string) file_get_contents($this->wave133), true, 512, JSON_THROW_ON_ERROR))
            ->pluck('product.external_id')->all();

        return Product::query()->with(['sites.categories'])->whereIn('external_id', $ids)->get()
            ->mapWithKeys(fn (Product $product): array => [$product->external_id => [
                'product' => $product->only(['sku', 'mpn', 'manufacturer', 'slug', 'name', 'short_description', 'technical_attributes', 'status']),
                'site_product' => $product->sites->sole()->only(['slug', 'is_published', 'availability', 'price', 'seo', 'sort_order']),
                'categories' => $product->sites->sole()->categories->pluck('external_id')->sort()->values()->all(),
            ]])->sortKeys()->all();
    }

    private function assertPinnedWaveFieldsOnEveryNewProduct(): void
    {
        $expected = [];
        foreach (glob($this->waves.'/wave-*.csv') as $path) {
            $handle = fopen($path, 'rb');
            fgetcsv($handle, 0, ';');
            while (($row = fgetcsv($handle, 0, ';')) !== false) {
                $expected[$row[0]] = ['name' => $row[1], 'slug' => $row[2]];
            }
            fclose($handle);
        }
        $wave133Ids = collect(json_decode((string) file_get_contents($this->wave133), true, 512, JSON_THROW_ON_ERROR))
            ->pluck('product.external_id')->all();
        $seen = $categorized = $unclassified = $electronics = 0;
        Product::query()->with('sites.categories')->whereNotIn('external_id', $wave133Ids)->chunkById(200,
            function ($products) use ($expected, &$seen, &$categorized, &$unclassified, &$electronics): void {
                foreach ($products as $product) {
                    $seen++;
                    $this->assertSame($expected[$product->external_id]['name'], $product->name);
                    $this->assertSame($expected[$product->external_id]['slug'], $product->slug);
                    $this->assertNull($product->sku);
                    $this->assertNull($product->mpn);
                    $this->assertNull($product->manufacturer);
                    $this->assertSame('active', $product->status);
                    $siteProduct = $product->sites->sole();
                    $this->assertSame($expected[$product->external_id]['slug'], $siteProduct->slug);
                    $this->assertFalse($siteProduct->is_published);
                    $this->assertNull($siteProduct->price);
                    $this->assertNull($siteProduct->seo);
                    if ($siteProduct->categories->isEmpty()) {
                        $unclassified++;
                    } else {
                        $categorized++;
                        if ($siteProduct->categories->sole()->external_id === 'seo:electronic-components') {
                            $electronics++;
                        }
                    }
                }
            });
        $this->assertSame(6457, $seen);
        $this->assertSame(5388, $categorized);
        $this->assertSame(1069, $unclassified);
        $this->assertSame(925, $electronics);
    }
}
