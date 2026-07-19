<?php

namespace Tests\Feature;

use App\Models\Category;
use App\Models\Product;
use App\Models\Site;
use App\Models\SiteCategory;
use App\Models\SiteIntegration;
use App\Models\SiteProduct;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class SiteCatalogModelsTest extends TestCase
{
    use RefreshDatabase;

    public function test_site_category_published_scope_only_returns_published_rows(): void
    {
        $site = $this->site();
        $visibleCategory = Category::create(['slug' => 'batteries', 'name' => 'Batteries', 'sort_order' => 1]);
        $hiddenCategory = Category::create(['slug' => 'ups', 'name' => 'UPS', 'sort_order' => 2]);

        $visible = SiteCategory::create([
            'site_id' => $site->id,
            'category_id' => $visibleCategory->id,
            'slug' => 'batteries',
            'name' => 'Batteries',
            'is_published' => true,
        ]);
        SiteCategory::create([
            'site_id' => $site->id,
            'category_id' => $hiddenCategory->id,
            'slug' => 'ups',
            'name' => 'UPS',
            'is_published' => false,
        ]);

        $published = SiteCategory::query()->where('site_id', $site->id)->published()->get();

        $this->assertCount(1, $published);
        $this->assertSame($visible->id, $published->first()->id);
        $this->assertTrue($published->first()->is_published);
    }

    public function test_site_category_belongs_to_its_site_and_category(): void
    {
        $site = $this->site();
        $category = Category::create(['slug' => 'batteries', 'name' => 'Batteries']);

        $siteCategory = SiteCategory::create([
            'site_id' => $site->id,
            'category_id' => $category->id,
            'slug' => 'batteries',
            'name' => 'Batteries',
            'is_published' => true,
        ]);

        $this->assertTrue($siteCategory->site->is($site));
        $this->assertTrue($siteCategory->category->is($category));
        $this->assertInstanceOf(Site::class, $siteCategory->site);
        $this->assertInstanceOf(Category::class, $siteCategory->category);
    }

    public function test_site_product_belongs_to_its_site_and_product(): void
    {
        $site = $this->site();
        $product = Product::create(['slug' => 'alpha-battery', 'name' => 'Alpha Battery', 'status' => 'active']);

        $siteProduct = SiteProduct::create([
            'site_id' => $site->id,
            'product_id' => $product->id,
            'slug' => 'alpha-battery',
            'is_published' => true,
            'availability' => 'in_stock',
        ]);

        $this->assertTrue($siteProduct->site->is($site));
        $this->assertTrue($siteProduct->product->is($product));
        $this->assertInstanceOf(Site::class, $siteProduct->site);
        $this->assertInstanceOf(Product::class, $siteProduct->product);
    }

    public function test_site_product_published_scope_only_returns_published_rows(): void
    {
        $site = $this->site();
        $visibleProduct = Product::create(['slug' => 'alpha-battery', 'name' => 'Alpha Battery', 'status' => 'active']);
        $hiddenProduct = Product::create(['slug' => 'beta-battery', 'name' => 'Beta Battery', 'status' => 'active']);

        $visible = SiteProduct::create([
            'site_id' => $site->id,
            'product_id' => $visibleProduct->id,
            'slug' => 'alpha-battery',
            'is_published' => true,
            'availability' => 'in_stock',
        ]);
        SiteProduct::create([
            'site_id' => $site->id,
            'product_id' => $hiddenProduct->id,
            'slug' => 'beta-battery',
            'is_published' => false,
            'availability' => 'on_request',
        ]);

        $published = SiteProduct::query()->published()->get();

        $this->assertCount(1, $published);
        $this->assertSame($visible->id, $published->first()->id);
    }

    public function test_site_integration_can_be_created_for_the_bitrix24_driver_and_belongs_to_its_site(): void
    {
        $site = $this->site();

        $integration = SiteIntegration::create([
            'site_id' => $site->id,
            'driver' => 'bitrix24',
            'settings' => ['webhook_url' => 'https://example.bitrix24.by/rest/1/token/'],
            'is_enabled' => true,
        ]);

        $this->assertDatabaseHas('site_integrations', [
            'site_id' => $site->id,
            'driver' => 'bitrix24',
            'is_enabled' => true,
        ]);
        $this->assertTrue($integration->site->is($site));
        $this->assertInstanceOf(Site::class, $integration->site);
        $this->assertIsArray($integration->settings);
        $this->assertSame('https://example.bitrix24.by/rest/1/token/', $integration->settings['webhook_url']);
        $this->assertTrue($integration->is_enabled);
    }

    private function site(): Site
    {
        return Site::create([
            'key' => 'microchips-by',
            'domain' => 'microchips.by',
            'country_code' => 'BY',
            'currency_code' => 'BYN',
            'default_locale' => 'ru-BY',
            'name' => 'Microchips Belarus',
            'is_active' => true,
        ]);
    }
}
