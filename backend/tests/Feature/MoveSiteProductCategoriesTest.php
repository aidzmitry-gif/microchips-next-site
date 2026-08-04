<?php

namespace Tests\Feature;

use App\Models\Category;
use App\Models\ImportRun;
use App\Models\Product;
use App\Models\Site;
use App\Models\SiteCategory;
use App\Models\SiteCategoryProduct;
use App\Models\SiteProduct;
use App\Models\SiteSeo;
use App\Models\SiteUrl;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class MoveSiteProductCategoriesTest extends TestCase
{
    use RefreshDatabase;

    public function test_dry_run_reports_move_without_changing_assignment(): void
    {
        [$site, $siteProduct, $from, $to] = $this->catalog();
        $file = $this->csv('p-1', $from->external_id, $to->external_id);

        $this->artisan('catalog:move-site-product-categories', ['site' => $site->key, 'file' => $file])
            ->assertSuccessful();

        $this->assertDatabaseHas('site_category_product', ['site_category_id' => $from->id, 'site_product_id' => $siteProduct->id]);
        $this->assertDatabaseMissing('site_category_product', ['site_category_id' => $to->id, 'site_product_id' => $siteProduct->id]);
        $run = ImportRun::query()->sole();
        $this->assertSame('dry_run_complete', $run->status);
        $this->assertSame(0, $run->processed_records);
        $this->assertSame(1, $run->summary['moves_completed']);
    }

    public function test_apply_moves_exact_link_and_is_idempotent(): void
    {
        [$site, $siteProduct, $from, $to] = $this->catalog();
        $file = $this->csv('p-1', $from->external_id, $to->external_id);
        $arguments = ['site' => $site->key, 'file' => $file, '--apply' => true];

        $this->artisan('catalog:move-site-product-categories', $arguments)->assertSuccessful();
        $this->artisan('catalog:move-site-product-categories', $arguments)->assertSuccessful();

        $this->assertDatabaseMissing('site_category_product', ['site_category_id' => $from->id, 'site_product_id' => $siteProduct->id]);
        $this->assertDatabaseHas('site_category_product', ['site_category_id' => $to->id, 'site_product_id' => $siteProduct->id]);
        $this->assertDatabaseCount('site_category_product', 1);
        $run = ImportRun::query()->latest('id')->firstOrFail();
        $this->assertSame(1, $run->summary['already_moved']);
        $this->assertSame(0, $run->summary['moves_completed']);
    }

    public function test_invalid_row_blocks_every_move(): void
    {
        [$site, $siteProduct, $from, $to] = $this->catalog();
        $file = storage_path('framework/testing/move-categories-'.uniqid().'.csv');
        file_put_contents($file, "product_external_id,from_category_external_id,to_category_external_id\np-1,{$from->external_id},{$to->external_id}\nmissing,{$from->external_id},{$to->external_id}\n");

        $this->artisan('catalog:move-site-product-categories', ['site' => $site->key, 'file' => $file, '--apply' => true])
            ->assertFailed();

        $this->assertDatabaseHas('site_category_product', ['site_category_id' => $from->id, 'site_product_id' => $siteProduct->id]);
        $this->assertDatabaseMissing('site_category_product', ['site_category_id' => $to->id, 'site_product_id' => $siteProduct->id]);
        $this->assertContains('unknown_product', collect(ImportRun::query()->sole()->summary['validation_errors'])->pluck('reason')->all());
    }

    public function test_apply_updates_existing_noindex_route_and_canonical_without_creating_new_routes(): void
    {
        [$site, $siteProduct, $from, $to] = $this->catalog();
        SiteUrl::create([
            'site_id' => $site->id, 'path' => '/catalog/from/p-1', 'locale' => 'ru-BY',
            'target_type' => 'product', 'target_id' => $siteProduct->id, 'is_indexable' => false,
        ]);
        SiteSeo::create([
            'site_id' => $site->id, 'locale' => 'ru-BY', 'resource_type' => 'product',
            'resource_id' => $siteProduct->id, 'canonical_path' => '/catalog/from/p-1',
            'title' => 'Product', 'is_indexable' => false,
        ]);
        $file = $this->csv('p-1', $from->external_id, $to->external_id);

        $this->artisan('catalog:move-site-product-categories', [
            'site' => $site->key, 'file' => $file, '--apply' => true,
        ])->assertSuccessful();

        $this->assertDatabaseHas('site_urls', ['target_id' => $siteProduct->id, 'path' => '/catalog/to/p-1']);
        $this->assertDatabaseHas('site_seos', ['resource_id' => $siteProduct->id, 'canonical_path' => '/catalog/to/p-1']);
        $this->assertSame(1, ImportRun::query()->sole()->summary['routes_updated']);
    }

    /** @return array{Site, SiteProduct, SiteCategory, SiteCategory} */
    private function catalog(): array
    {
        $site = Site::create([
            'key' => 'microchips-by', 'domain' => 'microchips.by', 'country_code' => 'BY',
            'currency_code' => 'BYN', 'default_locale' => 'ru-BY', 'name' => 'Microchips BY',
        ]);
        $product = Product::create(['external_id' => 'p-1', 'slug' => 'p-1', 'name' => 'Product', 'status' => 'active']);
        $siteProduct = SiteProduct::create([
            'site_id' => $site->id, 'product_id' => $product->id, 'slug' => 'p-1',
            'is_published' => false, 'availability' => 'on_request',
        ]);
        $from = $this->category($site, 'seo:from', 'catalog/from');
        $to = $this->category($site, 'seo:to', 'catalog/to');
        SiteCategoryProduct::create(['site_id' => $site->id, 'site_category_id' => $from->id, 'site_product_id' => $siteProduct->id]);

        return [$site, $siteProduct, $from, $to];
    }

    private function category(Site $site, string $externalId, string $slug): SiteCategory
    {
        $category = Category::create(['slug' => str_replace(':', '-', $externalId), 'name' => $externalId]);

        return SiteCategory::create([
            'site_id' => $site->id, 'source' => 'bitrix_sections', 'external_id' => $externalId,
            'category_id' => $category->id, 'slug' => $slug, 'name' => $externalId, 'is_published' => false,
        ]);
    }

    private function csv(string $product, string $from, string $to): string
    {
        $file = storage_path('framework/testing/move-categories-'.uniqid().'.csv');
        file_put_contents($file, "product_external_id,from_category_external_id,to_category_external_id\n{$product},{$from},{$to}\n");

        return $file;
    }
}
