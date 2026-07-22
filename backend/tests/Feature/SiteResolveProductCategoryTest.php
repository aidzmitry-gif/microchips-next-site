<?php

namespace Tests\Feature;

use App\Models\Category;
use App\Models\Product;
use App\Models\Site;
use App\Models\SiteCategory;
use App\Models\SiteProduct;
use App\Models\SiteUrl;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class SiteResolveProductCategoryTest extends TestCase
{
    use RefreshDatabase;

    public function test_it_resolves_a_site_scoped_product_by_hostname_and_path(): void
    {
        $site = $this->site('microchips-by', 'microchips.by', 'BY', 'BYN', 'ru-BY');
        $product = Product::create([
            'sku' => 'ALPHA-01',
            'mpn' => 'MPN-ALPHA-01',
            'manufacturer' => 'Alpha Corp',
            'slug' => 'alpha-battery',
            'name' => 'Alpha Battery',
            'short_description' => 'Промышленный аккумулятор Alpha.',
            'technical_attributes' => ['voltage' => '12V', 'capacity' => '100Ah'],
            'status' => 'active',
        ]);
        $siteProduct = SiteProduct::create([
            'site_id' => $site->id,
            'product_id' => $product->id,
            'slug' => 'alpha-battery',
            'is_published' => true,
            'availability' => 'in_stock',
            'price' => '199.99',
        ]);
        SiteUrl::create([
            'site_id' => $site->id,
            'path' => '/catalog/alpha-battery',
            'locale' => 'ru-BY',
            'target_type' => 'product',
            'target_id' => $siteProduct->id,
        ]);

        $this->getJson('/api/v1/sites/microchips.by/resolve?path=/catalog/alpha-battery')
            ->assertOk()
            ->assertJsonPath('kind', 'product')
            ->assertJsonPath('site.key', 'microchips-by')
            ->assertJsonPath('path', '/catalog/alpha-battery')
            ->assertJsonPath('product.name', 'Alpha Battery')
            ->assertJsonPath('product.sku', 'ALPHA-01')
            ->assertJsonPath('product.mpn', 'MPN-ALPHA-01')
            ->assertJsonPath('product.manufacturer', 'Alpha Corp')
            ->assertJsonPath('product.description', 'Промышленный аккумулятор Alpha.')
            ->assertJsonPath('product.attributes.voltage', '12V')
            ->assertJsonPath('product.availability', 'in_stock')
            ->assertJsonPath('product.price', '199.99')
            ->assertJsonPath('product.currency', 'BYN')
            ->assertJsonPath('seo.canonicalPath', '/catalog/alpha-battery');
    }

    public function test_it_resolves_a_site_scoped_category_by_hostname_and_path(): void
    {
        $site = $this->site('microchips-by', 'microchips.by', 'BY', 'BYN', 'ru-BY');
        $category = Category::create([
            'slug' => 'batteries',
            'name' => 'Аккумуляторы',
            'sort_order' => 1,
        ]);
        $siteCategory = SiteCategory::create([
            'site_id' => $site->id,
            'category_id' => $category->id,
            'slug' => 'akkumulyatory',
            'name' => 'Промышленные аккумуляторы',
            'is_published' => true,
            'sort_order' => 1,
        ]);
        SiteUrl::create([
            'site_id' => $site->id,
            'path' => '/catalog/akkumulyatory',
            'locale' => 'ru-BY',
            'target_type' => 'category',
            'target_id' => $siteCategory->id,
        ]);

        $this->getJson('/api/v1/sites/microchips.by/resolve?path=/catalog/akkumulyatory')
            ->assertOk()
            ->assertJsonPath('kind', 'category')
            ->assertJsonPath('site.key', 'microchips-by')
            ->assertJsonPath('path', '/catalog/akkumulyatory')
            ->assertJsonPath('category.name', 'Промышленные аккумуляторы')
            ->assertJsonPath('category.slug', 'akkumulyatory')
            ->assertJsonPath('seo.canonicalPath', '/catalog/akkumulyatory');
    }

    private function site(string $key, string $domain, string $country, string $currency, string $locale): Site
    {
        return Site::create([
            'key' => $key,
            'domain' => $domain,
            'country_code' => $country,
            'currency_code' => $currency,
            'default_locale' => $locale,
            'name' => $key,
            'is_active' => true,
        ]);
    }
}
