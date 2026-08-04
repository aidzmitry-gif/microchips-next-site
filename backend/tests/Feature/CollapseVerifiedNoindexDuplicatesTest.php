<?php

namespace Tests\Feature;

use App\Models\Category;
use App\Models\Product;
use App\Models\Site;
use App\Models\SiteCategory;
use App\Models\SiteProduct;
use App\Models\SiteProductPriceEvidence;
use App\Models\SiteRedirect;
use App\Models\SiteSeo;
use App\Models\SiteUrl;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Queue;
use Tests\TestCase;

class CollapseVerifiedNoindexDuplicatesTest extends TestCase
{
    use RefreshDatabase;

    protected function setUp(): void
    {
        parent::setUp();
        Queue::fake();
    }

    public function test_it_dry_runs_then_redirects_and_removes_only_the_duplicate_site_row(): void
    {
        [$site, $survivor, $duplicate, $file] = $this->fixture();
        try {
            $this->artisan('catalog:collapse-verified-noindex-duplicates', ['site' => $site->key, 'file' => $file])->assertSuccessful();
            $this->assertDatabaseCount('site_products', 2);
            $this->assertDatabaseCount('site_redirects', 0);
            $this->artisan('catalog:collapse-verified-noindex-duplicates', ['site' => $site->key, 'file' => $file, '--apply' => true])->assertSuccessful();
            $this->assertDatabaseMissing('site_products', ['id' => $duplicate->id]);
            $this->assertDatabaseHas('site_products', ['id' => $survivor->id]);
            $this->assertDatabaseHas('products', ['id' => $duplicate->product_id]);
            $this->assertDatabaseHas('site_redirects', ['site_id' => $site->id, 'source_path' => '/d', 'target_path' => '/s', 'status_code' => 301, 'purpose' => SiteRedirect::PURPOSE_PREVIEW]);
            $this->assertDatabaseMissing('site_urls', ['target_id' => $duplicate->id]);
            $this->assertDatabaseMissing('site_seos', ['resource_id' => $duplicate->id]);
            $this->artisan('catalog:collapse-verified-noindex-duplicates', ['site' => $site->key, 'file' => $file, '--apply' => true])->assertSuccessful();
            $this->assertDatabaseCount('site_redirects', 1);
            SiteRedirect::query()->where('site_id', $site->id)->where('source_path', '/d')->update(['purpose' => SiteRedirect::PURPOSE_SEO]);
            $this->artisan('catalog:collapse-verified-noindex-duplicates', ['site' => $site->key, 'file' => $file, '--apply' => true])
                ->expectsOutputToContain('"redirect_purposes_repaired": 1')
                ->assertSuccessful();
            $this->assertDatabaseHas('site_redirects', ['site_id' => $site->id, 'source_path' => '/d', 'purpose' => SiteRedirect::PURPOSE_PREVIEW]);
        } finally {
            @unlink($file);
        }
    }

    public function test_it_fails_closed_for_unbounded_model_core_or_indexable_url(): void
    {
        [$site, $survivor, $duplicate, $file] = $this->fixture('CS-MC90BXY');
        try {
            $this->artisan('catalog:collapse-verified-noindex-duplicates', ['site' => $site->key, 'file' => $file, '--apply' => true])->assertFailed();
            $this->assertDatabaseCount('site_products', 2);
            SiteUrl::query()->where('target_id', $duplicate->id)->update(['is_indexable' => true]);
            $file = $this->manifest($survivor->product->external_id, $duplicate->product->external_id, $survivor->product->name, $duplicate->product->name);
            $this->artisan('catalog:collapse-verified-noindex-duplicates', ['site' => $site->key, 'file' => $file, '--apply' => true])->assertFailed();
            $this->assertDatabaseCount('site_redirects', 0);
        } finally {
            @unlink($file);
        }
    }

    public function test_it_collapses_an_officially_evidenced_legacy_duplicate_into_a_priced_survivor(): void
    {
        [$site, $survivor, $duplicate, $file, $evidence, $snapshot] = $this->pricedFixture();
        try {
            $this->artisan('catalog:collapse-verified-noindex-duplicates', ['site' => $site->key, 'file' => $file])
                ->expectsOutputToContain('"collapsed": 1')
                ->assertSuccessful();
            $this->assertDatabaseHas('site_products', ['id' => $survivor->id, 'price' => '20.00']);
            $this->assertDatabaseHas('site_products', ['id' => $duplicate->id]);

            $this->artisan('catalog:collapse-verified-noindex-duplicates', ['site' => $site->key, 'file' => $file, '--apply' => true])
                ->assertSuccessful();

            $this->assertDatabaseMissing('site_products', ['id' => $duplicate->id]);
            $this->assertDatabaseHas('site_products', ['id' => $survivor->id, 'price' => '20.00']);
            $this->assertDatabaseHas('site_product_price_evidences', ['site_product_id' => $survivor->id, 'calculated_price' => '20.00', 'currency' => 'BYN', 'is_current' => true]);
            $this->assertDatabaseHas('site_redirects', ['source_path' => '/legacy-delta-dt12012', 'target_path' => '/delta-dt12012', 'status_code' => 301]);
        } finally {
            @unlink($file);
            @unlink($evidence);
            @unlink($snapshot);
        }
    }

    public function test_it_fails_closed_when_official_evidence_or_current_price_drifts(): void
    {
        [$site, $survivor, $duplicate, $file, $evidence, $snapshot] = $this->pricedFixture();
        try {
            file_put_contents($snapshot, 'changed bytes');
            $this->artisan('catalog:collapse-verified-noindex-duplicates', ['site' => $site->key, 'file' => $file, '--apply' => true])
                ->assertFailed();
            $this->assertDatabaseHas('site_products', ['id' => $duplicate->id]);

            file_put_contents($snapshot, 'official delta source');
            SiteProductPriceEvidence::query()->where('site_product_id', $survivor->id)->update(['calculated_price' => '21.00']);
            $this->artisan('catalog:collapse-verified-noindex-duplicates', ['site' => $site->key, 'file' => $file, '--apply' => true])
                ->assertFailed();
            $this->assertDatabaseHas('site_products', ['id' => $duplicate->id]);
            $this->assertDatabaseCount('site_redirects', 0);
        } finally {
            @unlink($file);
            @unlink($evidence);
            @unlink($snapshot);
        }
    }

    private function fixture(string $duplicateCore = 'CS-MC90BX'): array
    {
        $site = Site::create(['key' => 'test', 'domain' => 'test.local', 'country_code' => 'BY', 'currency_code' => 'BYN', 'default_locale' => 'ru-BY', 'name' => 'Test', 'is_active' => true]);
        $category = Category::create(['slug' => 'industrial', 'name' => 'Industrial']);
        $siteCategory = SiteCategory::create(['site_id' => $site->id, 'category_id' => $category->id, 'source' => 'test', 'external_id' => 'seo:batteries-industrial', 'slug' => 'industrial', 'name' => 'Industrial', 'is_published' => true]);
        $a = Product::create(['external_id' => 'bitrix:survivor', 'name' => 'Battery CS-MC90BX 7.4V 3400mAh', 'slug' => 's', 'status' => 'active']);
        $b = Product::create(['external_id' => 'bitrix:duplicate', 'name' => "Battery {$duplicateCore} 7.4V 3400mAh", 'slug' => 'd', 'status' => 'active']);
        $sa = SiteProduct::create(['site_id' => $site->id, 'product_id' => $a->id, 'slug' => 's', 'is_published' => true]);
        $sb = SiteProduct::create(['site_id' => $site->id, 'product_id' => $b->id, 'slug' => 'd', 'is_published' => true]);
        $sa->categories()->attach($siteCategory->id, ['site_id' => $site->id]);
        $sb->categories()->attach($siteCategory->id, ['site_id' => $site->id]);
        foreach ([[$sa, '/s'], [$sb, '/d']] as [$sp,$path]) {
            SiteUrl::create(['site_id' => $site->id, 'path' => $path, 'locale' => 'ru-BY', 'target_type' => 'product', 'target_id' => $sp->id, 'is_indexable' => false]);
            SiteSeo::create(['site_id' => $site->id, 'locale' => 'ru-BY', 'resource_type' => 'product', 'resource_id' => $sp->id, 'canonical_path' => $path, 'is_indexable' => false, 'schema' => null]);
        }

        return [$site, $sa, $sb, $this->manifest($a->external_id, $b->external_id, $a->name, $b->name)];
    }

    private function pricedFixture(): array
    {
        $site = Site::create(['key' => 'test-priced', 'domain' => 'priced.test', 'country_code' => 'BY', 'currency_code' => 'BYN', 'default_locale' => 'ru-BY', 'name' => 'Test priced', 'is_active' => true]);
        $category = Category::create(['slug' => 'ups-batteries', 'name' => 'UPS batteries']);
        $siteCategory = SiteCategory::create(['site_id' => $site->id, 'category_id' => $category->id, 'source' => 'test', 'external_id' => 'seo:batteries-ups', 'slug' => 'ups-batteries', 'name' => 'UPS batteries', 'is_published' => true]);
        $canonical = Product::create(['external_id' => 'one-c:delta-dt12012', 'name' => 'Аккумуляторная батарея Delta DT 12012', 'manufacturer' => 'Delta', 'mpn' => 'DT12012', 'slug' => 'delta-dt12012', 'status' => 'active']);
        $legacy = Product::create(['external_id' => 'bitrix:1401', 'name' => 'Аккумулятор Delta DT 12012 (AGM, 1.2Ah, 12V)', 'slug' => 'legacy-delta-dt12012', 'status' => 'active']);
        $survivor = SiteProduct::create(['site_id' => $site->id, 'product_id' => $canonical->id, 'slug' => 'delta-dt12012', 'is_published' => true, 'availability' => 'on_request', 'price' => '20.00']);
        $duplicate = SiteProduct::create(['site_id' => $site->id, 'product_id' => $legacy->id, 'slug' => 'legacy-delta-dt12012', 'is_published' => true, 'availability' => 'on_request']);
        $survivor->categories()->attach($siteCategory->id, ['site_id' => $site->id]);
        $duplicate->categories()->attach($siteCategory->id, ['site_id' => $site->id]);
        foreach ([[$survivor, '/delta-dt12012'], [$duplicate, '/legacy-delta-dt12012']] as [$siteProduct, $path]) {
            SiteUrl::create(['site_id' => $site->id, 'path' => $path, 'locale' => 'ru-BY', 'target_type' => 'product', 'target_id' => $siteProduct->id, 'is_indexable' => false]);
            SiteSeo::create(['site_id' => $site->id, 'locale' => 'ru-BY', 'resource_type' => 'product', 'resource_id' => $siteProduct->id, 'canonical_path' => $path, 'is_indexable' => false, 'schema' => null]);
        }
        SiteProductPriceEvidence::create([
            'site_id' => $site->id,
            'site_product_id' => $survivor->id,
            'source' => SiteProductPriceEvidence::SOURCE_LEGACY_SITE,
            'source_price' => '20.0000',
            'multiplier' => '1.0000',
            'calculated_price' => '20.00',
            'currency' => 'BYN',
            'source_reference' => 'https://microchips.by/catalog/delta-dt12012/',
            'observed_at' => '2026-06-23T00:00:00+03:00',
            'evidence_key' => hash('sha256', 'priced-survivor'),
            'is_current' => true,
        ]);
        $evidence = tempnam(sys_get_temp_dir(), 'delta-evidence-');
        $snapshot = tempnam(sys_get_temp_dir(), 'delta-source-');
        file_put_contents($evidence, 'reviewed delta evidence');
        file_put_contents($snapshot, 'official delta source');
        $manifest = tempnam(sys_get_temp_dir(), 'priced-duplicate-');
        file_put_contents($manifest, json_encode(['schema_version' => 1, 'duplicates' => [[
            'survivor_external_id' => $canonical->external_id,
            'duplicate_external_id' => $legacy->external_id,
            'survivor_name' => $canonical->name,
            'duplicate_name' => $legacy->name,
            'survivor_path' => '/delta-dt12012',
            'duplicate_path' => '/legacy-delta-dt12012',
            'model_core' => 'DT12012',
            'voltage' => '12V',
            'capacity' => '1.2Ah',
            'availability' => 'on_request',
            'category_external_ids' => ['seo:batteries-ups'],
            'manufacturer' => 'Delta',
            'survivor_mpn' => 'DT12012',
            'source_url' => 'https://delta-batt.com/series/dt/',
            'source_evidence_path' => $evidence,
            'source_evidence_sha256' => hash_file('sha256', $evidence),
            'source_snapshot_path' => $snapshot,
            'source_snapshot_sha256' => hash_file('sha256', $snapshot),
        ]]], JSON_THROW_ON_ERROR));

        return [$site, $survivor, $duplicate, $manifest, $evidence, $snapshot];
    }

    private function manifest(string $survivor, string $duplicate, string $survivorName, string $duplicateName): string
    {
        $file = tempnam(sys_get_temp_dir(), 'noindex-duplicate-');
        file_put_contents($file, json_encode(['schema_version' => 1, 'duplicates' => [['survivor_external_id' => $survivor, 'duplicate_external_id' => $duplicate, 'survivor_name' => $survivorName, 'duplicate_name' => $duplicateName, 'survivor_path' => '/s', 'duplicate_path' => '/d', 'model_core' => 'CS-MC90BX', 'voltage' => '7.4V', 'capacity' => '3400mAh', 'availability' => 'on_request', 'category_external_ids' => ['seo:batteries-industrial']]]], JSON_THROW_ON_ERROR));

        return $file;
    }
}
