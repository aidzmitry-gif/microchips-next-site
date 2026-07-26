<?php

namespace Tests\Feature;

use App\Models\Category;
use App\Models\Product;
use App\Models\Site;
use App\Models\SiteCategory;
use App\Models\SiteLocale;
use App\Models\SitePage;
use App\Models\SiteProduct;
use App\Models\SiteSeo;
use App\Models\SiteUrl;
use App\Models\SiteUrlAlternate;
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

    public function test_internal_provenance_metadata_never_reaches_the_public_product_payload(): void
    {
        // Round-2 regression: a nested `chemistry_provenance` object (see
        // SiteProductCategoryAssigner) used to be dumped verbatim into
        // `product.attributes`, breaking the frontend's declared
        // `Record<string, string> | null` contract and leaking internal
        // audit metadata to any API caller.
        $site = $this->site('microchips-by', 'microchips.by', 'BY', 'BYN', 'ru-BY');
        $product = Product::create([
            'slug' => 'beta-battery',
            'name' => 'Beta Battery',
            'status' => 'active',
            'technical_attributes' => [
                'voltage' => '12V',
                'chemistry' => 'AGM',
                'chemistry_provenance' => [
                    'source' => 'operator_supplied_csv_column',
                ],
            ],
        ]);
        $siteProduct = SiteProduct::create([
            'site_id' => $site->id,
            'product_id' => $product->id,
            'slug' => 'beta-battery',
            'is_published' => true,
            'availability' => 'on_request',
        ]);
        SiteUrl::create([
            'site_id' => $site->id,
            'path' => '/catalog/beta-battery',
            'locale' => 'ru-BY',
            'target_type' => 'product',
            'target_id' => $siteProduct->id,
        ]);

        $response = $this->getJson('/api/v1/sites/microchips.by/resolve?path=/catalog/beta-battery')
            ->assertOk()
            ->assertJsonPath('product.attributes.voltage', '12V')
            ->assertJsonPath('product.attributes.chemistry', 'AGM')
            ->assertJsonMissingPath('product.attributes.chemistry_provenance');

        foreach ($response->json('product.attributes') as $value) {
            $this->assertIsString($value);
        }
    }

    public function test_a_nested_technical_attribute_and_a_false_value_are_not_silently_dropped(): void
    {
        // Round-2 regression: publicAttributes() filtered on is_scalar($value),
        // which quietly dropped ANY non-scalar attribute (not just
        // *_provenance keys) with no trace in the payload, and turned a
        // boolean `false` value into an indistinguishable empty string.
        $site = $this->site('microchips-by', 'microchips.by', 'BY', 'BYN', 'ru-BY');
        $product = Product::create([
            'slug' => 'gamma-battery',
            'name' => 'Gamma Battery',
            'status' => 'active',
            'technical_attributes' => [
                'voltage' => '12V',
                'chemistry' => 'AGM',
                'chemistry_provenance' => ['source' => 'operator_supplied_csv_column'],
                'nested_spec' => ['a' => 'b'],
                'is_maintenance_free' => false,
            ],
        ]);
        $siteProduct = SiteProduct::create([
            'site_id' => $site->id,
            'product_id' => $product->id,
            'slug' => 'gamma-battery',
            'is_published' => true,
            'availability' => 'on_request',
        ]);
        SiteUrl::create([
            'site_id' => $site->id,
            'path' => '/catalog/gamma-battery',
            'locale' => 'ru-BY',
            'target_type' => 'product',
            'target_id' => $siteProduct->id,
        ]);

        $response = $this->getJson('/api/v1/sites/microchips.by/resolve?path=/catalog/gamma-battery')
            ->assertOk()
            ->assertJsonPath('product.attributes.voltage', '12V')
            ->assertJsonMissingPath('product.attributes.chemistry_provenance');

        $attributes = $response->json('product.attributes');
        $this->assertArrayHasKey('nested_spec', $attributes);
        $this->assertIsString($attributes['nested_spec']);
        $this->assertSame(['a' => 'b'], json_decode($attributes['nested_spec'], true));
        $this->assertSame('false', $attributes['is_maintenance_free']);
    }

    public function test_a_null_technical_attribute_is_omitted_not_stringified_to_an_empty_string(): void
    {
        // A null value means "this attribute was never set". Turning it into
        // '' would make it indistinguishable from a genuinely confirmed
        // blank value -- the exact defect this class's own docblock warns
        // about for `false`. The key must be absent from the payload.
        $site = $this->site('microchips-by', 'microchips.by', 'BY', 'BYN', 'ru-BY');
        $product = Product::create([
            'slug' => 'delta-battery',
            'name' => 'Delta Battery',
            'status' => 'active',
            'technical_attributes' => [
                'voltage' => '12V',
                'chemistry' => null,
            ],
        ]);
        $siteProduct = SiteProduct::create([
            'site_id' => $site->id,
            'product_id' => $product->id,
            'slug' => 'delta-battery',
            'is_published' => true,
            'availability' => 'on_request',
        ]);
        SiteUrl::create([
            'site_id' => $site->id,
            'path' => '/catalog/delta-battery',
            'locale' => 'ru-BY',
            'target_type' => 'product',
            'target_id' => $siteProduct->id,
        ]);

        $response = $this->getJson('/api/v1/sites/microchips.by/resolve?path=/catalog/delta-battery')
            ->assertOk()
            ->assertJsonPath('product.attributes.voltage', '12V')
            ->assertJsonMissingPath('product.attributes.chemistry');

        $attributes = $response->json('product.attributes');
        $this->assertArrayNotHasKey('chemistry', $attributes);
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

    public function test_it_strips_offer_schema_when_local_price_is_not_confirmed(): void
    {
        $site = $this->site('microchips-by', 'microchips.by', 'BY', 'BYN', 'ru-BY');
        $product = Product::create(['slug' => 'draft-battery', 'name' => 'Draft Battery', 'status' => 'active']);
        $siteProduct = SiteProduct::create([
            'site_id' => $site->id,
            'product_id' => $product->id,
            'slug' => 'draft-battery',
            'is_published' => true,
            'availability' => 'on_request',
            'price' => null,
        ]);
        SiteUrl::create([
            'site_id' => $site->id,
            'path' => '/catalog/draft-battery',
            'locale' => 'ru-BY',
            'target_type' => 'product',
            'target_id' => $siteProduct->id,
        ]);
        SiteSeo::create([
            'site_id' => $site->id,
            'locale' => 'ru-BY',
            'resource_type' => 'product',
            'resource_id' => $siteProduct->id,
            'canonical_path' => '/catalog/draft-battery',
            'is_indexable' => true,
            'schema' => ['@type' => 'Product', 'name' => 'Draft Battery', 'offers' => ['@type' => 'Offer', 'price' => '10']],
        ]);

        $this->getJson('/api/v1/sites/microchips.by/resolve?path=/catalog/draft-battery')
            ->assertOk()
            ->assertJsonPath('seo.schema.@type', 'Product')
            ->assertJsonMissingPath('seo.schema.offers');
    }

    public function test_it_omits_noindex_hreflang_alternates_from_the_resolve_payload(): void
    {
        $belarus = $this->site('microchips-by', 'microchips.by', 'BY', 'BYN', 'ru-BY');
        $russia = $this->site('microchips-ru', 'microchips.ru', 'RU', 'RUB', 'ru-RU');
        SiteLocale::create(['site_id' => $belarus->id, 'locale' => 'ru-BY', 'language' => 'ru', 'is_default' => true, 'is_enabled' => true]);
        SiteLocale::create(['site_id' => $russia->id, 'locale' => 'ru-RU', 'language' => 'ru', 'is_default' => true, 'is_enabled' => true]);
        $byPage = SitePage::create(['site_id' => $belarus->id, 'locale' => 'ru-BY', 'slug' => 'battery', 'title' => 'Battery', 'h1' => 'Battery', 'is_published' => true]);
        $ruPage = SitePage::create(['site_id' => $russia->id, 'locale' => 'ru-RU', 'slug' => 'battery', 'title' => 'Battery', 'h1' => 'Battery', 'is_published' => true]);
        $byUrl = SiteUrl::create(['site_id' => $belarus->id, 'path' => '/battery', 'locale' => 'ru-BY', 'target_type' => 'page', 'target_id' => $byPage->id]);
        $ruUrl = SiteUrl::create(['site_id' => $russia->id, 'path' => '/battery', 'locale' => 'ru-RU', 'target_type' => 'page', 'target_id' => $ruPage->id]);
        SiteSeo::create(['site_id' => $russia->id, 'locale' => 'ru-RU', 'resource_type' => 'page', 'resource_id' => $ruPage->id, 'canonical_path' => '/battery', 'is_indexable' => false]);
        SiteUrlAlternate::create(['source_url_id' => $byUrl->id, 'alternate_url_id' => $ruUrl->id, 'locale' => 'ru-RU']);

        $this->getJson('/api/v1/sites/microchips.by/resolve?path=/battery')
            ->assertOk()
            ->assertJsonPath('seo.hreflang.ru-BY', 'https://microchips.by/battery')
            ->assertJsonMissingPath('seo.hreflang.ru-RU');
    }

    public function test_a_non_indexable_url_cannot_become_indexable_without_a_seo_record(): void
    {
        $site = $this->site('microchips-by', 'microchips.by', 'BY', 'BYN', 'ru-BY');
        $page = SitePage::create(['site_id' => $site->id, 'locale' => 'ru-BY', 'slug' => 'private', 'title' => 'Private', 'h1' => 'Private', 'is_published' => true]);
        SiteUrl::create([
            'site_id' => $site->id,
            'path' => '/private',
            'locale' => 'ru-BY',
            'target_type' => 'page',
            'target_id' => $page->id,
            'is_indexable' => false,
        ]);

        $this->getJson('/api/v1/sites/microchips.by/resolve?path=/private')
            ->assertOk()
            ->assertJsonPath('seo.isIndexable', false);
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
