<?php

namespace Tests\Feature;

use App\Models\Category;
use App\Models\Product;
use App\Models\Site;
use App\Models\SiteCategory;
use App\Models\SiteCategoryProduct;
use App\Models\SiteProduct;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class RemoveRedundantSiteCategoryLinksTest extends TestCase
{
    use RefreshDatabase;

    public function test_it_removes_only_the_named_redundant_link_after_dry_run(): void
    {
        $site = Site::create(['key' => 'microchips-by', 'domain' => 'test.by', 'country_code' => 'BY', 'currency_code' => 'BYN', 'default_locale' => 'ru-BY', 'name' => 'RB', 'is_active' => true]);
        $root = Category::create(['external_id' => 'root', 'name' => 'Root', 'slug' => 'root']);
        $good = Category::create(['external_id' => 'good', 'name' => 'Good', 'slug' => 'good', 'parent_id' => $root->id]);
        $bad = Category::create(['external_id' => 'bad', 'name' => 'Bad', 'slug' => 'bad', 'parent_id' => $root->id]);
        $goodSite = SiteCategory::create(['site_id' => $site->id, 'source' => 'bitrix_sections', 'external_id' => '410', 'category_id' => $good->id, 'slug' => 'catalog/good', 'name' => 'Good']);
        $badSite = SiteCategory::create(['site_id' => $site->id, 'source' => 'full_catalog_seo_tree', 'external_id' => 'seo:wrong', 'category_id' => $bad->id, 'slug' => 'catalog/bad', 'name' => 'Bad']);
        $product = Product::create(['external_id' => 'P1', 'name' => 'Battery', 'slug' => 'battery', 'status' => 'active']);
        $siteProduct = SiteProduct::create(['site_id' => $site->id, 'product_id' => $product->id, 'slug' => 'battery']);
        foreach ([$goodSite, $badSite] as $category) {
            SiteCategoryProduct::create(['site_id' => $site->id, 'site_category_id' => $category->id, 'site_product_id' => $siteProduct->id]);
        }
        $file = tempnam(sys_get_temp_dir(), 'redundant-category-');
        file_put_contents($file, "product_external_id,category_external_id\nP1,seo:wrong\n");
        try {
            $this->artisan('catalog:remove-redundant-category-links', ['site' => 'microchips-by', 'file' => $file])->assertSuccessful();
            $this->assertDatabaseCount('site_category_product', 2);
            $this->artisan('catalog:remove-redundant-category-links', ['site' => 'microchips-by', 'file' => $file, '--apply' => true])->assertSuccessful();
            $this->assertDatabaseCount('site_category_product', 1);
            $this->assertDatabaseHas('site_category_product', ['site_category_id' => $goodSite->id, 'site_product_id' => $siteProduct->id]);
        } finally {
            @unlink($file);
        }
    }
}
