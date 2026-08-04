<?php

namespace Tests\Feature;

use App\Domain\Imports\ProductIdentity;
use App\Models\CatalogDraftMaterialization;
use App\Models\Category;
use App\Models\ImportRun;
use App\Models\Product;
use App\Models\ProductDescriptionDraft;
use App\Models\Site;
use App\Models\SiteCategory;
use App\Models\SiteProduct;
use App\Models\SiteProductPriceEvidence;
use App\Models\SiteRedirect;
use App\Models\SiteUrl;
use App\Models\StagedImportRecord;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Tests\TestCase;

class PublishSourceVerifiedPreviewWaveTest extends TestCase
{
    use RefreshDatabase;

    public function test_it_retires_a_previous_noindex_product_path_when_a_verified_slug_changes(): void
    {
        $site = Site::create(['key' => 'microchips-by', 'domain' => 'microchips-by.test', 'country_code' => 'BY', 'currency_code' => 'BYN', 'default_locale' => 'ru-BY', 'name' => 'RB', 'is_active' => true]);
        $canonical = Category::create(['slug' => 'ups-batteries', 'name' => 'UPS batteries']);
        SiteCategory::create(['site_id' => $site->id, 'category_id' => $canonical->id, 'source' => 'seo_tree', 'external_id' => 'ups-batteries', 'slug' => 'catalog/ups-batteries', 'name' => 'UPS batteries', 'is_published' => true]);
        $product = Product::create(['external_id' => 'manufacturer:enersys:12HX650F-FR+', 'manufacturer' => 'EnerSys', 'mpn' => '12HX650F-FR+', 'name' => 'EnerSys 12HX650F-FR+', 'slug' => 'enersys-12hx650f-fr', 'short_description' => 'Verified.', 'status' => 'active']);
        $siteProduct = SiteProduct::create(['site_id' => $site->id, 'product_id' => $product->id, 'slug' => 'enersys-12hx650f-fr', 'is_published' => true, 'availability' => 'on_request']);
        ProductDescriptionDraft::create(['product_id' => $product->id, 'locale' => 'ru-BY', 'title' => $product->name, 'content' => 'Verified.', 'verified_fields' => [], 'source_urls' => ['https://manufacturer.example.test/12hx650'], 'status' => 'applied']);
        SiteUrl::create(['site_id' => $site->id, 'path' => '/catalog/ups-batteries/enersys-12hx650f-fr', 'locale' => 'ru-BY', 'target_type' => 'product', 'target_id' => $siteProduct->id, 'is_indexable' => false]);
        $file = tempnam(sys_get_temp_dir(), 'preview-wave-slug-change-');
        file_put_contents($file, json_encode(['locale' => 'ru-BY', 'products' => [[
            'external_id' => $product->external_id, 'manufacturer' => 'EnerSys', 'mpn' => '12HX650F-FR+',
            'source_url' => 'https://manufacturer.example.test/12hx650', 'category_slug' => 'catalog/ups-batteries', 'product_slug' => 'enersys-12hx650f-fr-plus',
        ]]], JSON_THROW_ON_ERROR));

        try {
            $this->artisan('catalog:publish-source-verified-preview-wave', ['site' => 'microchips-by', 'file' => $file, '--apply' => true])->assertSuccessful();
            $this->assertDatabaseMissing('site_urls', ['site_id' => $site->id, 'path' => '/catalog/ups-batteries/enersys-12hx650f-fr']);
            $this->assertDatabaseHas('site_urls', ['site_id' => $site->id, 'path' => '/catalog/ups-batteries/enersys-12hx650f-fr-plus', 'target_id' => $siteProduct->id, 'is_indexable' => false]);
            $this->assertDatabaseHas('site_redirects', ['site_id' => $site->id, 'source_path' => '/catalog/ups-batteries/enersys-12hx650f-fr', 'target_path' => '/catalog/ups-batteries/enersys-12hx650f-fr-plus', 'status_code' => 301, 'purpose' => SiteRedirect::PURPOSE_PREVIEW, 'is_active' => true]);
            $this->assertSame('enersys-12hx650f-fr-plus', $siteProduct->refresh()->slug);
        } finally {
            @unlink($file);
        }
    }

    public function test_it_can_publish_a_model_core_preview_without_inventing_an_mpn(): void
    {
        $site = Site::create(['key' => 'microchips-by', 'domain' => 'microchips-by.test', 'country_code' => 'BY', 'currency_code' => 'BYN', 'default_locale' => 'ru-BY', 'name' => 'RB', 'is_active' => true]);
        $canonical = Category::create(['slug' => 'ups-batteries', 'name' => 'UPS batteries']);
        SiteCategory::create(['site_id' => $site->id, 'category_id' => $canonical->id, 'source' => 'seo_tree', 'external_id' => 'ups-batteries', 'slug' => 'catalog/ups-batteries', 'name' => 'UPS batteries', 'is_published' => false]);
        $product = Product::create(['external_id' => '1c-gp1272', 'name' => 'CSB GP1272 F2', 'slug' => 'draft-gp1272', 'short_description' => 'Verified description.', 'status' => 'active']);
        $siteProduct = SiteProduct::create(['site_id' => $site->id, 'product_id' => $product->id, 'slug' => 'draft-gp1272', 'is_published' => false, 'availability' => 'on_request']);
        ProductDescriptionDraft::create(['product_id' => $product->id, 'locale' => 'ru-BY', 'title' => 'CSB GP1272', 'content' => 'Verified description.', 'verified_fields' => [], 'source_urls' => ['https://manufacturer.example.test/gp1272'], 'status' => 'applied']);
        $file = tempnam(sys_get_temp_dir(), 'preview-wave-core-');
        file_put_contents($file, json_encode(['locale' => 'ru-BY', 'products' => [[
            'external_id' => '1c-gp1272', 'manufacturer' => 'CSB', 'identity_scope' => 'model_core', 'model_core' => 'GP1272',
            'source_url' => 'https://manufacturer.example.test/gp1272', 'category_slug' => 'catalog/ups-batteries', 'product_slug' => 'csb-gp1272',
        ]]], JSON_THROW_ON_ERROR));

        try {
            $this->artisan('catalog:publish-source-verified-preview-wave', ['site' => 'microchips-by', 'file' => $file, '--apply' => true])->assertSuccessful();
            $this->assertTrue($siteProduct->refresh()->is_published);
            $this->assertSame('CSB', $product->refresh()->manufacturer);
            $this->assertNull($product->mpn);
        } finally {
            @unlink($file);
        }
    }

    public function test_dealer_backed_preview_never_promotes_manufacturer_into_canonical_identity(): void
    {
        $site = Site::create(['key' => 'microchips-by', 'domain' => 'microchips-by.test', 'country_code' => 'BY', 'currency_code' => 'BYN', 'default_locale' => 'ru-BY', 'name' => 'RB', 'is_active' => true]);
        $canonical = Category::create(['slug' => 'ups-batteries', 'name' => 'UPS batteries']);
        SiteCategory::create(['site_id' => $site->id, 'category_id' => $canonical->id, 'source' => 'seo_tree', 'external_id' => 'ups-batteries', 'slug' => 'catalog/ups-batteries', 'name' => 'UPS batteries', 'is_published' => false]);
        $product = Product::create(['external_id' => '1c-dt1207', 'name' => 'Аккумулятор Delta DT1207', 'slug' => 'draft-dt1207', 'short_description' => 'Verified dealer-backed description.', 'status' => 'active']);
        $siteProduct = SiteProduct::create(['site_id' => $site->id, 'product_id' => $product->id, 'slug' => 'draft-dt1207', 'is_published' => false, 'availability' => 'on_request']);
        ProductDescriptionDraft::create([
            'product_id' => $product->id,
            'locale' => 'ru-BY',
            'title' => 'Delta DT1207',
            'content' => 'Verified dealer-backed description.',
            'verified_fields' => ['manufacturer' => 'Delta', 'model' => 'DT1207', 'technical_attributes' => ['Nominal voltage' => '12 V']],
            'source_urls' => ['https://dealer.example.test/dt1207'],
            'source_kind' => 'official_dealer_product_page',
            'source_tier' => 'dealer_backed',
            'source_publisher' => 'Example dealer',
            'manufacturer_primary' => false,
            'identity_scope' => 'model_core',
            'source_checked_at' => '2026-07-28',
            'status' => 'applied',
        ]);
        $file = tempnam(sys_get_temp_dir(), 'preview-wave-dealer-');
        file_put_contents($file, json_encode(['locale' => 'ru-BY', 'products' => [[
            'external_id' => '1c-dt1207', 'manufacturer' => 'Delta', 'identity_scope' => 'model_core', 'model_core' => 'DT1207',
            'source_url' => 'https://dealer.example.test/dt1207', 'category_slug' => 'catalog/ups-batteries', 'product_slug' => 'delta-dt1207',
        ]]], JSON_THROW_ON_ERROR));

        try {
            $this->artisan('catalog:publish-source-verified-preview-wave', ['site' => 'microchips-by', 'file' => $file, '--apply' => true])->assertSuccessful();
            $this->assertTrue($siteProduct->refresh()->is_published);
            $this->assertNull($product->refresh()->manufacturer);
            $this->assertNull($product->mpn);
            $this->artisan('catalog:verify-manufacturer-preview-wave', ['site' => 'microchips-by', 'file' => $file])
                ->expectsOutputToContain('"passed": true')
                ->assertSuccessful();
        } finally {
            @unlink($file);
        }
    }

    public function test_manifest_preflight_rejects_duplicate_variant_slugs_without_partial_publication(): void
    {
        $site = Site::create(['key' => 'microchips-by', 'domain' => 'microchips-by.test', 'country_code' => 'BY', 'currency_code' => 'BYN', 'default_locale' => 'ru-BY', 'name' => 'RB', 'is_active' => true]);
        $canonical = Category::create(['slug' => 'ups-batteries', 'name' => 'UPS batteries']);
        SiteCategory::create(['site_id' => $site->id, 'category_id' => $canonical->id, 'source' => 'seo_tree', 'external_id' => 'ups-batteries', 'slug' => 'catalog/ups-batteries', 'name' => 'UPS batteries', 'is_published' => false]);
        $rows = [];
        $siteProducts = [];
        foreach ([['1c-gp1272-f1', 'CSB GP1272 F1'], ['1c-gp1272-f2', 'CSB GP1272 F2']] as [$externalId, $name]) {
            $product = Product::create(['external_id' => $externalId, 'name' => $name, 'slug' => 'draft-'.$externalId, 'short_description' => 'Verified description.', 'status' => 'active']);
            $siteProducts[] = SiteProduct::create(['site_id' => $site->id, 'product_id' => $product->id, 'slug' => 'draft-'.$externalId, 'is_published' => false, 'availability' => 'on_request']);
            $sourceUrl = 'https://manufacturer.example.test/'.$externalId;
            ProductDescriptionDraft::create(['product_id' => $product->id, 'locale' => 'ru-BY', 'title' => $name, 'content' => 'Verified description.', 'verified_fields' => [], 'source_urls' => [$sourceUrl], 'status' => 'applied']);
            $rows[] = [
                'external_id' => $externalId, 'manufacturer' => 'CSB', 'identity_scope' => 'model_core', 'model_core' => 'GP1272',
                'source_url' => $sourceUrl, 'category_slug' => 'catalog/ups-batteries', 'product_slug' => 'csb-gp1272',
            ];
        }
        $file = tempnam(sys_get_temp_dir(), 'preview-wave-duplicate-slug-');
        file_put_contents($file, json_encode(['locale' => 'ru-BY', 'products' => $rows], JSON_THROW_ON_ERROR));

        try {
            $this->artisan('catalog:publish-source-verified-preview-wave', ['site' => 'microchips-by', 'file' => $file, '--apply' => true])->assertFailed();
            foreach ($siteProducts as $siteProduct) {
                $this->assertFalse($siteProduct->refresh()->is_published);
            }
            $this->assertDatabaseCount('site_urls', 0);
        } finally {
            @unlink($file);
        }
    }

    public function test_it_publishes_only_a_noindex_source_verified_preview_without_commercial_data(): void
    {
        $site = Site::create(['key' => 'microchips-by', 'domain' => 'microchips-by.test', 'country_code' => 'BY', 'currency_code' => 'BYN', 'default_locale' => 'ru-BY', 'name' => 'RB', 'is_active' => true]);
        $canonical = Category::create(['slug' => 'primary-cells', 'name' => 'Primary cells']);
        $category = SiteCategory::create(['site_id' => $site->id, 'category_id' => $canonical->id, 'source' => 'seo_tree', 'external_id' => 'cells', 'slug' => 'catalog/primary-cells', 'name' => 'Primary cells', 'is_published' => false]);
        $product = Product::create(['external_id' => '1c-br2330', 'name' => 'Panasonic BR2330', 'slug' => 'draft-1', 'short_description' => 'Verified description.', 'status' => 'active']);
        $siteProduct = SiteProduct::create(['site_id' => $site->id, 'product_id' => $product->id, 'slug' => 'draft-1', 'is_published' => false, 'availability' => 'on_request', 'price' => null]);
        ProductDescriptionDraft::create(['product_id' => $product->id, 'locale' => 'ru-BY', 'title' => 'Panasonic BR2330', 'content' => 'Verified description.', 'verified_fields' => ['technical_attributes' => ['Voltage' => '3 V']], 'source_urls' => ['https://manufacturer.example.test/br2330'], 'status' => 'applied']);
        $file = tempnam(sys_get_temp_dir(), 'preview-wave-');
        file_put_contents($file, json_encode(['locale' => 'ru-BY', 'products' => [[
            'external_id' => '1c-br2330', 'manufacturer' => 'Panasonic', 'mpn' => 'BR2330',
            'source_url' => 'https://manufacturer.example.test/br2330', 'category_slug' => 'catalog/primary-cells', 'product_slug' => 'panasonic-br2330',
        ]]], JSON_THROW_ON_ERROR));

        try {
            $this->artisan('catalog:publish-source-verified-preview-wave', ['site' => 'microchips-by', 'file' => $file])->assertSuccessful();
            $this->assertFalse($siteProduct->refresh()->is_published);

            $this->artisan('catalog:publish-source-verified-preview-wave', ['site' => 'microchips-by', 'file' => $file, '--apply' => true])->assertSuccessful();

            $this->assertTrue($siteProduct->refresh()->is_published);
            $this->assertSame('Panasonic', $product->refresh()->manufacturer);
            $this->assertSame('BR2330', $product->mpn);
            $this->assertNull($siteProduct->price);
            $this->assertSame('on_request', $siteProduct->availability);
            $this->assertTrue($category->refresh()->is_published);
            $this->assertDatabaseHas('site_urls', ['site_id' => $site->id, 'path' => '/catalog/primary-cells/panasonic-br2330', 'target_type' => 'product', 'target_id' => $siteProduct->id, 'is_indexable' => false]);
            $this->assertDatabaseHas('site_seos', ['site_id' => $site->id, 'resource_type' => 'product', 'resource_id' => $siteProduct->id, 'is_indexable' => false]);
        } finally {
            @unlink($file);
        }
    }

    public function test_it_requires_an_explicit_flag_before_replacing_a_wrong_existing_category(): void
    {
        $site = Site::create(['key' => 'microchips-by', 'domain' => 'microchips-by.test', 'country_code' => 'BY', 'currency_code' => 'BYN', 'default_locale' => 'ru-BY', 'name' => 'RB', 'is_active' => true]);
        $wrongCanonical = Category::create(['slug' => 'wrong', 'name' => 'Wrong']);
        $targetCanonical = Category::create(['slug' => 'target', 'name' => 'Target']);
        $wrong = SiteCategory::create(['site_id' => $site->id, 'category_id' => $wrongCanonical->id, 'source' => 'seo_tree', 'external_id' => 'wrong', 'slug' => 'catalog/wrong', 'name' => 'Wrong', 'is_published' => false]);
        $target = SiteCategory::create(['site_id' => $site->id, 'category_id' => $targetCanonical->id, 'source' => 'seo_tree', 'external_id' => 'target', 'slug' => 'catalog/target', 'name' => 'Target', 'is_published' => false]);
        $product = Product::create(['external_id' => '1c-fix-category', 'name' => 'FIAMM 12FGH23', 'slug' => 'draft-fix', 'short_description' => 'Verified description.', 'status' => 'active']);
        $siteProduct = SiteProduct::create(['site_id' => $site->id, 'product_id' => $product->id, 'slug' => 'draft-fix', 'is_published' => false, 'availability' => 'on_request', 'price' => null]);
        $siteProduct->categories()->attach($wrong->id);
        ProductDescriptionDraft::create(['product_id' => $product->id, 'locale' => 'ru-BY', 'title' => 'FIAMM 12FGH23', 'content' => 'Verified description.', 'verified_fields' => [], 'source_urls' => ['https://manufacturer.example.test/12fgh23'], 'status' => 'applied']);
        $file = tempnam(sys_get_temp_dir(), 'preview-wave-');
        file_put_contents($file, json_encode(['locale' => 'ru-BY', 'products' => [[
            'external_id' => '1c-fix-category', 'manufacturer' => 'FIAMM', 'mpn' => '12FGH23',
            'source_url' => 'https://manufacturer.example.test/12fgh23', 'category_slug' => 'catalog/target', 'product_slug' => 'fiamm-12fgh23',
        ]]], JSON_THROW_ON_ERROR));

        try {
            $this->artisan('catalog:publish-source-verified-preview-wave', ['site' => 'microchips-by', 'file' => $file, '--apply' => true])->assertFailed();
            $this->assertSame([$wrong->id], $siteProduct->categories()->pluck('site_categories.id')->all());

            file_put_contents($file, json_encode(['locale' => 'ru-BY', 'products' => [[
                'external_id' => '1c-fix-category', 'manufacturer' => 'FIAMM', 'mpn' => '12FGH23',
                'source_url' => 'https://manufacturer.example.test/12fgh23', 'category_slug' => 'catalog/target', 'product_slug' => 'fiamm-12fgh23', 'replace_categories' => true,
            ]]], JSON_THROW_ON_ERROR));
            $this->artisan('catalog:publish-source-verified-preview-wave', ['site' => 'microchips-by', 'file' => $file, '--apply' => true])->assertSuccessful();
            $this->assertSame([$target->id], $siteProduct->categories()->pluck('site_categories.id')->all());
        } finally {
            @unlink($file);
        }
    }

    public function test_it_allows_a_price_only_with_an_explicit_flag_and_matching_current_evidence(): void
    {
        $site = Site::create(['key' => 'microchips-by', 'domain' => 'microchips-by.test', 'country_code' => 'BY', 'currency_code' => 'BYN', 'default_locale' => 'ru-BY', 'name' => 'RB', 'is_active' => true]);
        $canonical = Category::create(['slug' => 'ups-batteries', 'name' => 'UPS batteries']);
        SiteCategory::create(['site_id' => $site->id, 'category_id' => $canonical->id, 'source' => 'seo_tree', 'external_id' => 'ups-batteries', 'slug' => 'catalog/ups-batteries', 'name' => 'UPS batteries', 'is_published' => false]);
        $product = Product::create(['external_id' => '1c-delta-dtm1226', 'name' => 'Delta DTM1226', 'slug' => 'draft-dtm1226', 'short_description' => 'Verified description.', 'manufacturer' => 'Delta', 'mpn' => 'DTM1226', 'status' => 'active']);
        $siteProduct = SiteProduct::create(['site_id' => $site->id, 'product_id' => $product->id, 'slug' => 'draft-dtm1226', 'is_published' => false, 'availability' => 'on_request', 'price' => 181]);
        ProductDescriptionDraft::create(['product_id' => $product->id, 'locale' => 'ru-BY', 'title' => 'Delta DTM1226', 'content' => 'Verified description.', 'verified_fields' => ['technical_attributes' => ['Voltage' => '12 V']], 'source_urls' => ['https://manufacturer.example.test/dtm1226'], 'status' => 'applied']);
        SiteProductPriceEvidence::create([
            'site_id' => $site->id, 'site_product_id' => $siteProduct->id,
            'source' => SiteProductPriceEvidence::SOURCE_LEGACY_SITE,
            'source_price' => 181, 'multiplier' => 1, 'calculated_price' => 180,
            'currency' => 'BYN', 'price_type' => 'legacy_public_price',
            'source_external_id' => '2915', 'source_reference' => 'bitrix-backup://2026-06-23/element/2915',
            'observed_at' => '2026-06-23T00:00:00+03:00', 'evidence_key' => hash('sha256', 'wrong-price'),
            'is_current' => true,
        ]);
        $file = tempnam(sys_get_temp_dir(), 'preview-wave-');
        $row = [
            'external_id' => '1c-delta-dtm1226', 'manufacturer' => 'Delta', 'mpn' => 'DTM1226',
            'source_url' => 'https://manufacturer.example.test/dtm1226', 'category_slug' => 'catalog/ups-batteries', 'product_slug' => 'delta-dtm1226',
        ];

        try {
            file_put_contents($file, json_encode(['locale' => 'ru-BY', 'products' => [$row]], JSON_THROW_ON_ERROR));
            $this->artisan('catalog:publish-source-verified-preview-wave', ['site' => 'microchips-by', 'file' => $file, '--apply' => true])->assertFailed();

            $row['allow_verified_price'] = true;
            file_put_contents($file, json_encode(['locale' => 'ru-BY', 'products' => [$row]], JSON_THROW_ON_ERROR));
            $this->artisan('catalog:publish-source-verified-preview-wave', ['site' => 'microchips-by', 'file' => $file, '--apply' => true])->assertFailed();

            SiteProductPriceEvidence::query()->update(['is_current' => false]);
            SiteProductPriceEvidence::create([
                'site_id' => $site->id, 'site_product_id' => $siteProduct->id,
                'source' => SiteProductPriceEvidence::SOURCE_LEGACY_SITE,
                'source_price' => 181, 'multiplier' => 1, 'calculated_price' => 181,
                'currency' => 'BYN', 'price_type' => 'legacy_public_price',
                'source_external_id' => '2915', 'source_reference' => 'bitrix-backup://2026-06-23/element/2915',
                'observed_at' => '2026-06-23T00:00:00+03:00', 'evidence_key' => hash('sha256', 'matching-price'),
                'is_current' => true,
            ]);

            $this->artisan('catalog:publish-source-verified-preview-wave', ['site' => 'microchips-by', 'file' => $file, '--apply' => true])
                ->expectsOutputToContain('"verified_priced_products": 1')
                ->assertSuccessful();

            $this->assertTrue($siteProduct->refresh()->is_published);
            $this->assertSame('181.00', $siteProduct->price);
            $this->assertSame('on_request', $siteProduct->availability);
        } finally {
            @unlink($file);
        }
    }

    public function test_manufacturer_primary_publish_accepts_matching_exact_evidence_and_pinned_bitrix_lineage(): void
    {
        $fixture = $this->manufacturerPrimaryFixture();

        try {
            $this->artisan('catalog:publish-source-verified-preview-wave', [
                'site' => $fixture['site']->key,
                'file' => $fixture['file'],
                '--apply' => true,
            ])->assertSuccessful();

            $this->assertTrue($fixture['site_product']->refresh()->is_published);
            $this->assertSame('IPPON', $fixture['product']->refresh()->manufacturer);
            $this->assertSame('Back Basic 650', $fixture['product']->mpn);
        } finally {
            @unlink($fixture['file']);
        }
    }

    public function test_manufacturer_primary_publish_accepts_matching_exact_official_product_page(): void
    {
        $fixture = $this->manufacturerPrimaryFixture(sourceKind: 'official_manufacturer_product_page');

        try {
            $this->artisan('catalog:publish-source-verified-preview-wave', [
                'site' => $fixture['site']->key,
                'file' => $fixture['file'],
                '--apply' => true,
            ])->assertSuccessful();

            $this->assertTrue($fixture['site_product']->refresh()->is_published);
        } finally {
            @unlink($fixture['file']);
        }
    }

    public function test_manufacturer_primary_publish_accepts_bounded_model_core_without_creating_an_mpn(): void
    {
        $fixture = $this->manufacturerPrimaryFixture(sourceKind: 'official_manufacturer_product_page');
        $fixture['product']->mpn = null;
        $fixture['product']->saveQuietly();
        $draft = ProductDescriptionDraft::query()->where('product_id', $fixture['product']->id)->sole();
        $verified = $draft->verified_fields;
        unset($verified['mpn']);
        $draft->verified_fields = $verified;
        $draft->identity_scope = 'model_core';
        $draft->save();
        $manifest = json_decode((string) file_get_contents($fixture['file']), true, 512, JSON_THROW_ON_ERROR);
        $manifest['products'][0]['identity_scope'] = 'model_core';
        $manifest['products'][0]['model_core'] = $manifest['products'][0]['mpn'];
        unset($manifest['products'][0]['mpn']);
        file_put_contents($fixture['file'], json_encode($manifest, JSON_THROW_ON_ERROR));

        try {
            $this->artisan('catalog:publish-source-verified-preview-wave', [
                'site' => $fixture['site']->key,
                'file' => $fixture['file'],
                '--apply' => true,
            ])->assertSuccessful();

            $this->assertTrue($fixture['site_product']->refresh()->is_published);
            $this->assertNull($fixture['product']->refresh()->mpn);
        } finally {
            @unlink($fixture['file']);
        }
    }

    public function test_exact_preview_can_use_bounded_manufacturer_description_when_product_mpn_is_independently_present(): void
    {
        $fixture = $this->manufacturerPrimaryFixture(sourceKind: 'official_manufacturer_product_page');
        $draft = ProductDescriptionDraft::query()->where('product_id', $fixture['product']->id)->sole();
        $verified = $draft->verified_fields;
        unset($verified['mpn']);
        $draft->verified_fields = $verified;
        $draft->identity_scope = 'model_core';
        $draft->save();

        try {
            $this->artisan('catalog:publish-source-verified-preview-wave', [
                'site' => $fixture['site']->key,
                'file' => $fixture['file'],
                '--apply' => true,
            ])->assertSuccessful();

            $this->assertTrue($fixture['site_product']->refresh()->is_published);
            $this->assertSame('Back Basic 650', $fixture['product']->refresh()->mpn);
        } finally {
            @unlink($fixture['file']);
        }
    }

    public function test_manufacturer_primary_publish_does_not_use_a_newer_unrelated_lineage_to_bypass_a_hold(): void
    {
        $fixture = $this->manufacturerPrimaryFixture(transferStatus: 'hold_one_c_collision');
        $this->addUnrelatedMaterialization($fixture, 'legacy_only_draft_candidate');

        try {
            $this->artisan('catalog:publish-source-verified-preview-wave', [
                'site' => $fixture['site']->key,
                'file' => $fixture['file'],
                '--apply' => true,
            ])->assertFailed();

            $this->assertFalse($fixture['site_product']->refresh()->is_published);
        } finally {
            @unlink($fixture['file']);
        }
    }

    public function test_manufacturer_primary_publish_rejects_a_held_bitrix_lineage(): void
    {
        $fixture = $this->manufacturerPrimaryFixture(transferStatus: 'hold_one_c_collision');

        try {
            $this->artisan('catalog:publish-source-verified-preview-wave', [
                'site' => $fixture['site']->key,
                'file' => $fixture['file'],
                '--apply' => true,
            ])->assertFailed();

            $this->assertFalse($fixture['site_product']->refresh()->is_published);
        } finally {
            @unlink($fixture['file']);
        }
    }

    public function test_manufacturer_primary_publish_rejects_a_shorter_model_before_a_variant_suffix(): void
    {
        $fixture = $this->manufacturerPrimaryFixture(
            name: 'Источник бесперебойного питания IPPON Back Basic 650 S Euro',
        );

        try {
            $this->artisan('catalog:publish-source-verified-preview-wave', [
                'site' => $fixture['site']->key,
                'file' => $fixture['file'],
                '--apply' => true,
            ])->assertFailed();

            $this->assertFalse($fixture['site_product']->refresh()->is_published);
        } finally {
            @unlink($fixture['file']);
        }
    }

    public function test_manufacturer_primary_publish_rejects_an_mpn_matching_another_products_sku(): void
    {
        $fixture = $this->manufacturerPrimaryFixture();
        $normalizedMpn = ProductIdentity::normalize('Back Basic 650');
        DB::table('products')->insert([
            'external_id' => '1c:existing-ippon-sku',
            'external_id_normalized' => ProductIdentity::normalize('1c:existing-ippon-sku'),
            'sku' => 'Back Basic 650',
            'sku_normalized' => $normalizedMpn,
            'mpn' => null,
            'mpn_normalized' => null,
            'manufacturer' => 'IPPON',
            'slug' => 'existing-ippon-sku',
            'name' => 'Existing IPPON inventory row',
            'status' => 'active',
            'created_at' => now(),
            'updated_at' => now(),
        ]);

        try {
            $this->artisan('catalog:publish-source-verified-preview-wave', [
                'site' => $fixture['site']->key,
                'file' => $fixture['file'],
                '--apply' => true,
            ])->assertFailed();

            $this->assertFalse($fixture['site_product']->refresh()->is_published);
        } finally {
            @unlink($fixture['file']);
        }
    }

    public function test_manufacturer_primary_publish_rejects_an_applied_mpn_that_does_not_match_the_manifest(): void
    {
        $fixture = $this->manufacturerPrimaryFixture(evidenceMpn: 'Back Basic 850');

        try {
            $this->artisan('catalog:publish-source-verified-preview-wave', [
                'site' => $fixture['site']->key,
                'file' => $fixture['file'],
                '--apply' => true,
            ])->assertFailed();

            $this->assertFalse($fixture['site_product']->refresh()->is_published);
        } finally {
            @unlink($fixture['file']);
        }
    }

    /** @return array{site: Site, product: Product, site_product: SiteProduct, file: string} */
    private function manufacturerPrimaryFixture(
        string $transferStatus = 'legacy_only_draft_candidate',
        string $name = 'Источник бесперебойного питания IPPON Back Basic 650',
        string $mpn = 'Back Basic 650',
        ?string $evidenceMpn = null,
        string $sourceKind = 'official_manufacturer_catalogue',
    ): array {
        $evidenceMpn ??= $mpn;
        $externalId = 'bitrix:25109';
        $sourceUrl = 'https://static.ippon.ru/data/download/Ippon_UPS_Catalogue_II_2024.pdf';
        $site = Site::create([
            'key' => 'microchips-by',
            'domain' => 'microchips-by.test',
            'country_code' => 'BY',
            'currency_code' => 'BYN',
            'default_locale' => 'ru-BY',
            'name' => 'RB',
            'is_active' => true,
        ]);
        $canonical = Category::create(['slug' => 'ups-systems', 'name' => 'UPS systems']);
        SiteCategory::create([
            'site_id' => $site->id,
            'category_id' => $canonical->id,
            'source' => 'seo_tree',
            'external_id' => 'seo:ups-systems',
            'slug' => 'catalog/power-systems/ups-systems',
            'name' => 'UPS systems',
            'is_published' => false,
        ]);
        $product = Product::create([
            'external_id' => $externalId,
            'manufacturer' => 'IPPON',
            'mpn' => $mpn,
            'name' => $name,
            'slug' => 'draft-bitrix-25109',
            'short_description' => 'Verified IPPON description.',
            'technical_attributes' => ['Активная мощность' => '360 Вт'],
            'status' => 'active',
        ]);
        $siteProduct = SiteProduct::create([
            'site_id' => $site->id,
            'product_id' => $product->id,
            'slug' => 'draft-bitrix-25109',
            'is_published' => false,
            'availability' => 'on_request',
            'price' => null,
        ]);
        ProductDescriptionDraft::create([
            'product_id' => $product->id,
            'locale' => 'ru-BY',
            'title' => $name,
            'content' => 'Verified IPPON description.',
            'verified_fields' => [
                'name' => $name,
                'manufacturer' => 'IPPON',
                'model' => $evidenceMpn,
                'mpn' => $evidenceMpn,
                'technology' => 'Линейно-интерактивный ИБП',
                'technical_attributes' => ['Активная мощность' => '360 Вт'],
            ],
            'source_urls' => [$sourceUrl],
            'source_kind' => $sourceKind,
            'source_tier' => 'manufacturer_primary',
            'source_publisher' => 'IPPON',
            'manufacturer_primary' => true,
            'identity_scope' => 'exact',
            'source_checked_at' => '2026-07-29',
            'status' => 'applied',
        ]);

        $sourceRun = ImportRun::create(['source' => 'bitrix_full_catalog_snapshot:'.$site->key, 'status' => 'completed']);
        $materializationRun = ImportRun::create(['source' => 'materialize_bitrix_drafts', 'status' => 'completed']);
        $stagedRecord = StagedImportRecord::create([
            'import_run_id' => $sourceRun->id,
            'row_number' => 1,
            'entity_type' => 'bitrix_full_catalog_product_evidence',
            'external_id' => $externalId,
            'payload' => ['transfer_status' => $transferStatus],
            'normalized_payload' => ['transfer_status' => $transferStatus],
            'validation_errors' => [],
            'status' => 'staged_evidence',
        ]);
        CatalogDraftMaterialization::create([
            'materialization_run_id' => $materializationRun->id,
            'source_import_run_id' => $sourceRun->id,
            'staged_import_record_id' => $stagedRecord->id,
            'site_id' => $site->id,
            'product_id' => $product->id,
            'site_product_id' => $siteProduct->id,
            'source_namespace' => 'bitrix',
            'source_external_id' => $externalId,
            'source_checksum' => hash('sha256', $externalId),
            'materialization_kind' => CatalogDraftMaterialization::KIND_NAMESPACED_DRAFT,
            'target_category_external_id' => 'seo:ups-systems',
        ]);

        $file = tempnam(sys_get_temp_dir(), 'manufacturer-primary-preview-');
        file_put_contents($file, json_encode([
            'locale' => 'ru-BY',
            'products' => [[
                'external_id' => $externalId,
                'manufacturer' => 'IPPON',
                'identity_scope' => 'exact',
                'mpn' => $mpn,
                'source_url' => $sourceUrl,
                'category_slug' => 'catalog/power-systems/ups-systems',
                'product_slug' => 'ippon-back-basic-650',
                'replace_categories' => true,
            ]],
        ], JSON_THROW_ON_ERROR | JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT));

        return ['site' => $site, 'product' => $product, 'site_product' => $siteProduct, 'file' => $file];
    }

    /** @param array{site: Site, product: Product, site_product: SiteProduct, file: string} $fixture */
    private function addUnrelatedMaterialization(array $fixture, string $transferStatus): void
    {
        $sourceRun = ImportRun::create(['source' => 'one_c_catalog', 'status' => 'completed']);
        $materializationRun = ImportRun::create(['source' => 'materialize_one_c_drafts', 'status' => 'completed']);
        $stagedRecord = StagedImportRecord::create([
            'import_run_id' => $sourceRun->id,
            'row_number' => 1,
            'entity_type' => 'one_c_product_evidence',
            'external_id' => '1c:unrelated',
            'payload' => ['transfer_status' => $transferStatus],
            'normalized_payload' => ['transfer_status' => $transferStatus],
            'validation_errors' => [],
            'status' => 'staged_evidence',
        ]);
        CatalogDraftMaterialization::create([
            'materialization_run_id' => $materializationRun->id,
            'source_import_run_id' => $sourceRun->id,
            'staged_import_record_id' => $stagedRecord->id,
            'site_id' => $fixture['site']->id,
            'product_id' => $fixture['product']->id,
            'site_product_id' => $fixture['site_product']->id,
            'source_namespace' => 'one_c',
            'source_external_id' => '1c:unrelated',
            'source_checksum' => hash('sha256', '1c:unrelated'),
            'materialization_kind' => CatalogDraftMaterialization::KIND_EXISTING_EXACT_LINK,
            'target_category_external_id' => 'seo:ups-systems',
        ]);
    }
}
