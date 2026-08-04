<?php

namespace Tests\Feature;

use App\Models\Product;
use App\Models\Site;
use App\Models\SiteProduct;
use App\Models\SiteRedirect;
use App\Models\SiteSeo;
use App\Models\SiteUrl;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class ControllerBranchesTest extends TestCase
{
    use RefreshDatabase;

    public function test_catalog_search_query_matches_product_name_via_where_has(): void
    {
        $site = $this->site();
        $this->publishProduct($site, 'alpha-battery', 'Alpha Battery', 'ALPHA-01');
        $this->publishProduct($site, 'beta-inverter', 'Beta Inverter', 'BETA-02');

        $this->getJson('/api/v1/sites/microchips-by/catalog/products?q=Alpha')
            ->assertOk()
            ->assertJsonCount(1, 'data')
            ->assertJsonPath('data.0.name', 'Alpha Battery');
    }

    public function test_redirect_lookup_returns_only_an_active_site_scoped_redirect(): void
    {
        $site = Site::create([
            'key' => 'microchips-by',
            'domain' => 'microchips.by',
            'country_code' => 'BY',
            'currency_code' => 'BYN',
            'default_locale' => 'ru-BY',
            'name' => 'Microchips BY',
            'is_active' => true,
        ]);
        SiteRedirect::create([
            'site_id' => $site->id,
            'source_path' => '/catalog/old-battery',
            'target_path' => '/catalog/new-battery',
            'status_code' => 301,
            'is_active' => true,
        ]);

        $this->getJson('/api/v1/sites/microchips.by/redirect?path=/catalog/old-battery')
            ->assertOk()
            ->assertExactJson(['kind' => 'redirect', 'to' => '/catalog/new-battery', 'status' => 301, 'locale' => 'ru-BY']);
        $this->getJson('/api/v1/sites/microchips.by/redirect?path=/catalog/missing')
            ->assertOk()
            ->assertExactJson(['kind' => 'not_found', 'locale' => 'ru-BY']);
    }

    public function test_unsafe_redirect_targets_are_not_exposed_by_runtime_endpoints(): void
    {
        $site = $this->site();
        foreach (['https://attacker.example/collect', '/%2f%2fattacker.example/collect'] as $index => $target) {
            $sourcePath = "/catalog/legacy-{$index}";
            SiteRedirect::create([
                'site_id' => $site->id,
                'source_path' => $sourcePath,
                'target_path' => $target,
                'status_code' => 301,
                'is_active' => true,
            ]);

            $this->getJson("/api/v1/sites/microchips.by/redirect?path={$sourcePath}")
                ->assertOk()
                ->assertExactJson(['kind' => 'not_found', 'locale' => 'ru-BY']);
            $this->getJson("/api/v1/sites/microchips.by/resolve?path={$sourcePath}")
                ->assertOk()
                ->assertJsonPath('kind', 'not_found')
                ->assertJsonMissingPath('redirect');
        }
    }

    public function test_catalog_search_query_with_no_matches_returns_empty_data(): void
    {
        $site = $this->site();
        $this->publishProduct($site, 'alpha-battery', 'Alpha Battery', 'ALPHA-01');

        $this->getJson('/api/v1/sites/microchips-by/catalog/products?q=Nonexistent')
            ->assertOk()
            ->assertJsonCount(0, 'data');
    }

    public function test_catalog_pagination_respects_per_page_and_reports_meta(): void
    {
        $site = $this->site();
        $this->publishProduct($site, 'alpha-battery', 'Alpha Battery', 'ALPHA-01');
        $this->publishProduct($site, 'beta-inverter', 'Beta Inverter', 'BETA-02');
        $this->publishProduct($site, 'gamma-charger', 'Gamma Charger', 'GAMMA-03');

        $this->getJson('/api/v1/sites/microchips-by/catalog/products?per_page=2')
            ->assertOk()
            ->assertJsonCount(2, 'data')
            ->assertJsonPath('meta.current_page', 1)
            ->assertJsonPath('meta.last_page', 2)
            ->assertJsonPath('meta.total', 3);

        $this->getJson('/api/v1/sites/microchips-by/catalog/products?per_page=2&page=2')
            ->assertOk()
            ->assertJsonCount(1, 'data')
            ->assertJsonPath('meta.current_page', 2)
            ->assertJsonPath('meta.last_page', 2)
            ->assertJsonPath('meta.total', 3);
    }

    public function test_catalog_allows_only_explicit_name_sorts_until_prices_are_confirmed(): void
    {
        $site = $this->site();
        $zeta = $this->publishProduct($site, 'zeta-battery', 'Zeta Battery', 'ZETA-01');
        $alpha = $this->publishProduct($site, 'alpha-battery', 'Alpha Battery', 'ALPHA-01');
        $this->getJson('/api/v1/sites/microchips-by/catalog/products?sort=name_asc')
            ->assertOk()
            ->assertJsonPath('data.0.name', 'Alpha Battery')
            ->assertJsonPath('meta.sort', 'name_asc');

        $this->getJson('/api/v1/sites/microchips-by/catalog/products?sort=price_desc')
            ->assertUnprocessable()
            ->assertJsonValidationErrors('sort');

        $this->getJson('/api/v1/sites/microchips-by/catalog/products?sort=untrusted_column')
            ->assertUnprocessable()
            ->assertJsonValidationErrors('sort');
    }

    public function test_catalog_excludes_unpublished_site_products(): void
    {
        $site = $this->site();
        $this->publishProduct($site, 'alpha-battery', 'Alpha Battery', 'ALPHA-01');

        $hidden = Product::create(['slug' => 'hidden-battery', 'name' => 'Hidden Battery', 'status' => 'active']);
        SiteProduct::create([
            'site_id' => $site->id,
            'product_id' => $hidden->id,
            'slug' => 'hidden-battery',
            'is_published' => false,
            'availability' => 'on_request',
        ]);

        $this->getJson('/api/v1/sites/microchips-by/catalog/products')
            ->assertOk()
            ->assertJsonCount(1, 'data')
            ->assertJsonPath('data.0.name', 'Alpha Battery');
    }

    public function test_seo_audit_command_reports_invalid_for_a_site_that_does_not_exist(): void
    {
        $this->artisan('seo:audit', ['site' => 'no-such-site'])
            ->expectsOutputToContain('Site [no-such-site] was not found. The audit did not change any data.')
            ->assertFailed();
    }

    public function test_seo_audit_command_prints_a_blocked_table_without_the_json_flag(): void
    {
        $site = $this->site();
        SiteUrl::create([
            'site_id' => $site->id,
            'path' => '/orphan-page',
            'locale' => 'ru-BY',
            'target_type' => 'page',
            'target_id' => 999999,
            'is_indexable' => true,
        ]);
        SiteSeo::create([
            'site_id' => $site->id,
            'locale' => 'ru-BY',
            'resource_type' => 'page',
            'resource_id' => 999999,
            'canonical_path' => '/orphan-page',
            'is_indexable' => true,
        ]);

        $this->artisan('seo:audit', ['site' => 'microchips-by'])
            ->expectsOutputToContain('BLOCKED: 1 release blocker(s) found for microchips-by.')
            ->expectsOutputToContain('SEO_INDEXABLE_TARGET_NOT_PUBLISHED')
            ->assertFailed();
    }

    public function test_resolve_site_path_returns_not_found_kind_for_an_unregistered_path(): void
    {
        $this->site();

        $this->getJson('/api/v1/sites/microchips.by/resolve?path=/does-not-exist')
            ->assertOk()
            ->assertJsonPath('kind', 'not_found')
            ->assertJsonPath('site.key', 'microchips-by')
            ->assertJsonMissingPath('page')
            ->assertJsonMissingPath('redirect');
    }

    public function test_sitemap_endpoint_returns_404_for_an_unknown_host(): void
    {
        $this->site();

        $this->getJson('/api/v1/sites/unknown-domain.example/seo/sitemap')
            ->assertNotFound();
    }

    private function publishProduct(Site $site, string $slug, string $name, string $sku): SiteProduct
    {
        $product = Product::create(['slug' => $slug, 'name' => $name, 'sku' => $sku, 'status' => 'active']);

        return SiteProduct::create([
            'site_id' => $site->id,
            'product_id' => $product->id,
            'slug' => $slug,
            'is_published' => true,
            'availability' => 'in_stock',
        ]);
    }

    private function site(): Site
    {
        $site = Site::create([
            'key' => 'microchips-by',
            'domain' => 'microchips.by',
            'country_code' => 'BY',
            'currency_code' => 'BYN',
            'default_locale' => 'ru-BY',
            'name' => 'Microchips Belarus',
            'is_active' => true,
        ]);
        $site->locales()->create([
            'locale' => 'ru-BY',
            'language' => 'ru',
            'is_default' => true,
            'is_enabled' => true,
        ]);

        return $site;
    }
}
