<?php

namespace Tests\Feature;

use App\Models\Category;
use App\Models\Product;
use App\Models\Site;
use App\Models\SiteCategory;
use App\Models\SiteProduct;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class ImportManufacturerProductCandidatesTest extends TestCase
{
    use RefreshDatabase;

    public function test_it_creates_only_an_unpublished_unpriced_deduplicated_candidate(): void
    {
        $site = Site::create([
            'key' => 'microchips-by', 'domain' => 'microchips.by', 'country_code' => 'BY',
            'currency_code' => 'BYN', 'default_locale' => 'ru-BY', 'name' => 'Microchips', 'is_active' => true,
        ]);
        $category = Category::create(['slug' => 'batteries-ups', 'name' => 'UPS batteries']);
        SiteCategory::create([
            'site_id' => $site->id, 'category_id' => $category->id, 'source' => 'full_catalog_seo_tree',
            'external_id' => 'seo:batteries-ups', 'slug' => 'catalog/industrial-batteries/batteries-ups',
            'name' => 'UPS batteries', 'is_published' => true,
        ]);
        $file = $this->manifest();

        try {
            $this->artisan('catalog:import-manufacturer-product-candidates', [
                'site' => 'microchips-by', 'file' => $file,
            ])->assertSuccessful();
            $this->assertDatabaseCount('products', 0);

            $this->artisan('catalog:import-manufacturer-product-candidates', [
                'site' => 'microchips-by', 'file' => $file, '--apply' => true,
            ])->assertSuccessful();

            $product = Product::query()->sole();
            $siteProduct = SiteProduct::query()->sole();
            $this->assertSame('manufacturer:csb:XTV1272', $product->external_id);
            $this->assertSame('XTV1272', $product->mpn);
            $this->assertSame('draft', $product->status);
            $this->assertFalse($siteProduct->is_published);
            $this->assertSame('on_request', $siteProduct->availability);
            $this->assertNull($siteProduct->price);
            $this->assertDatabaseCount('site_urls', 0);
            $this->assertDatabaseCount('site_seos', 0);

            $this->artisan('catalog:import-manufacturer-product-candidates', [
                'site' => 'microchips-by', 'file' => $file, '--apply' => true,
            ])->assertSuccessful();
            $this->assertDatabaseCount('products', 1);
        } finally {
            @unlink($file);
        }
    }

    public function test_it_rejects_a_hidden_duplicate_whose_exact_brand_and_model_exist_only_in_the_name(): void
    {
        $site = Site::create([
            'key' => 'microchips-by', 'domain' => 'microchips.by', 'country_code' => 'BY',
            'currency_code' => 'BYN', 'default_locale' => 'ru-BY', 'name' => 'Microchips', 'is_active' => true,
        ]);
        $category = Category::create(['slug' => 'batteries-ups', 'name' => 'UPS batteries']);
        SiteCategory::create([
            'site_id' => $site->id, 'category_id' => $category->id, 'source' => 'full_catalog_seo_tree',
            'external_id' => 'seo:batteries-ups', 'slug' => 'catalog/industrial-batteries/batteries-ups',
            'name' => 'UPS batteries', 'is_published' => true,
        ]);
        Product::create([
            'external_id' => 'bitrix:gp672', 'name' => 'Аккумулятор CSB GP 672 (AGM)',
            'slug' => 'legacy-csb-gp672', 'status' => 'active',
        ]);
        $file = tempnam(sys_get_temp_dir(), 'manufacturer-products-hidden-duplicate-');
        file_put_contents($file, json_encode([
            'schema_version' => 1,
            'site_key' => 'microchips-by',
            'products' => [[
                'external_id' => 'manufacturer:csb:GP672', 'manufacturer' => 'CSB', 'mpn' => 'GP672',
                'name' => 'Аккумулятор CSB GP672', 'slug' => 'csb-gp672',
                'category_external_id' => 'seo:batteries-ups',
                'source_url' => 'https://csb-battery.com/product/gp-series/',
                'technical_attributes' => ['Series' => 'GP'],
            ]],
        ], JSON_THROW_ON_ERROR));

        try {
            $this->artisan('catalog:import-manufacturer-product-candidates', [
                'site' => 'microchips-by', 'file' => $file, '--apply' => true,
            ])->assertFailed();
            $this->assertDatabaseCount('products', 1);
            $this->assertDatabaseMissing('products', ['external_id' => 'manufacturer:csb:GP672']);
        } finally {
            @unlink($file);
        }
    }

    private function manifest(): string
    {
        $file = tempnam(sys_get_temp_dir(), 'manufacturer-products-');
        file_put_contents($file, json_encode([
            'schema_version' => 1,
            'site_key' => 'microchips-by',
            'products' => [[
                'external_id' => 'manufacturer:csb:XTV1272',
                'manufacturer' => 'CSB',
                'mpn' => 'XTV1272',
                'name' => 'CSB XTV1272',
                'slug' => 'csb-xtv1272',
                'category_external_id' => 'seo:batteries-ups',
                'source_url' => 'https://csb-battery.com/product/xtv-series/',
                'technical_attributes' => ['Series' => 'XTV'],
            ]],
        ], JSON_THROW_ON_ERROR));

        return $file;
    }
}
