<?php

namespace Tests\Feature;

use App\Models\Product;
use App\Models\ProductDescriptionDraft;
use App\Models\Site;
use App\Models\SiteProduct;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class StageSourceBackedDescriptionDraftsCommandTest extends TestCase
{
    use RefreshDatabase;

    public function test_it_validates_then_stages_source_backed_drafts_without_publishing(): void
    {
        $site = Site::create([
            'key' => 'microchips-by',
            'domain' => 'microchips-by.test',
            'country_code' => 'BY',
            'currency_code' => 'BYN',
            'default_locale' => 'ru-BY',
            'name' => 'Microchips Беларусь',
            'is_active' => true,
        ]);
        $product = Product::create([
            'external_id' => '1c-dtm6012',
            'name' => 'Delta DTM 6012',
            'slug' => 'delta-dtm-6012',
            'manufacturer' => 'Delta',
            'mpn' => 'DTM6012',
            'status' => 'active',
        ]);
        SiteProduct::create([
            'site_id' => $site->id,
            'product_id' => $product->id,
            'slug' => 'delta-dtm-6012',
            'is_published' => false,
        ]);
        $file = tempnam(sys_get_temp_dir(), 'description-drafts-');
        file_put_contents($file, json_encode([
            'locale' => 'ru-BY',
            'products' => [[
                'external_id' => '1c-dtm6012',
                'manufacturer' => 'Delta',
                'mpn' => 'DTM6012',
                'technology' => 'AGM',
                'source_url' => 'https://manufacturer.example.test/dtm6012',
                'technical_attributes' => ['Номинальное напряжение' => '6 V'],
            ]],
        ], JSON_THROW_ON_ERROR));

        try {
            $this->artisan('content:stage-source-backed-description-drafts', [
                'site' => 'microchips-by',
                'file' => $file,
            ])->assertSuccessful();
            $this->assertDatabaseCount('product_description_drafts', 0);

            $this->artisan('content:stage-source-backed-description-drafts', [
                'site' => 'microchips-by',
                'file' => $file,
                '--apply' => true,
            ])->assertSuccessful();

            $draft = ProductDescriptionDraft::query()->sole();
            $this->assertSame('draft', $draft->status);
            $this->assertSame(['https://manufacturer.example.test/dtm6012'], $draft->source_urls);
            $this->assertSame('AGM', $draft->verified_fields['technical_attributes']['Технология']);
            $this->assertStringContainsString('AGM', $draft->content);
            $this->assertStringContainsString('Номинальное напряжение', $draft->content);
            $this->assertFalse($product->refresh()->sites()->sole()->is_published);
        } finally {
            @unlink($file);
        }
    }

    public function test_it_refuses_evidence_that_does_not_match_the_catalogue_identity(): void
    {
        $site = Site::create([
            'key' => 'microchips-by', 'domain' => 'microchips-by.test', 'country_code' => 'BY',
            'currency_code' => 'BYN', 'default_locale' => 'ru-BY', 'name' => 'Microchips Беларусь', 'is_active' => true,
        ]);
        $product = Product::create([
            'external_id' => '1c-dtm6012', 'name' => 'Delta DTM 6012', 'slug' => 'delta-dtm-6012',
            'manufacturer' => 'Delta', 'mpn' => 'DTM6012', 'status' => 'active',
        ]);
        SiteProduct::create(['site_id' => $site->id, 'product_id' => $product->id, 'slug' => 'delta-dtm-6012']);
        $file = tempnam(sys_get_temp_dir(), 'description-drafts-');
        file_put_contents($file, json_encode(['locale' => 'ru-BY', 'products' => [[
            'external_id' => '1c-dtm6012', 'manufacturer' => 'Delta', 'mpn' => 'NOT-DTM6012',
            'technology' => 'AGM', 'source_url' => 'https://manufacturer.example.test/dtm6012',
        ]]], JSON_THROW_ON_ERROR));

        try {
            $this->artisan('content:stage-source-backed-description-drafts', ['site' => 'microchips-by', 'file' => $file, '--apply' => true])
                ->assertFailed();
            $this->assertDatabaseCount('product_description_drafts', 0);
        } finally {
            @unlink($file);
        }
    }

    public function test_it_accepts_verified_identity_when_legacy_structured_fields_are_blank(): void
    {
        $site = Site::create([
            'key' => 'microchips-by', 'domain' => 'microchips-by.test', 'country_code' => 'BY',
            'currency_code' => 'BYN', 'default_locale' => 'ru-BY', 'name' => 'Microchips Беларусь', 'is_active' => true,
        ]);
        $product = Product::create([
            'external_id' => '1c-br2330', 'name' => 'Эл. питания литиевый PANASONIC BR2330 3V',
            'slug' => 'panasonic-br2330', 'manufacturer' => null, 'mpn' => null, 'status' => 'active',
        ]);
        SiteProduct::create(['site_id' => $site->id, 'product_id' => $product->id, 'slug' => 'panasonic-br2330']);
        $file = tempnam(sys_get_temp_dir(), 'description-drafts-');
        file_put_contents($file, json_encode(['locale' => 'ru-BY', 'products' => [[
            'external_id' => '1c-br2330', 'manufacturer' => 'Panasonic', 'mpn' => 'BR2330',
            'technology' => 'литиевый элемент 3 V', 'source_url' => 'https://manufacturer.example.test/br2330',
        ]]], JSON_THROW_ON_ERROR));

        try {
            $this->artisan('content:stage-source-backed-description-drafts', [
                'site' => 'microchips-by', 'file' => $file, '--apply' => true,
            ])->assertSuccessful();
            $this->assertDatabaseCount('product_description_drafts', 1);
            $this->assertFalse($product->refresh()->sites()->sole()->is_published);
        } finally {
            @unlink($file);
        }
    }

    public function test_it_stages_model_core_evidence_without_requiring_an_mpn(): void
    {
        $site = Site::create([
            'key' => 'microchips-by', 'domain' => 'microchips-by.test', 'country_code' => 'BY',
            'currency_code' => 'BYN', 'default_locale' => 'ru-BY', 'name' => 'RB', 'is_active' => true,
        ]);
        $product = Product::create([
            'external_id' => '1c-saft-ls14250-cna', 'name' => 'LS 14250СNA (SAFT) литиевый элемент',
            'slug' => 'saft-ls14250-cna', 'manufacturer' => 'Saft', 'mpn' => null, 'status' => 'active',
        ]);
        SiteProduct::create(['site_id' => $site->id, 'product_id' => $product->id, 'slug' => 'saft-ls14250-cna']);
        $file = tempnam(sys_get_temp_dir(), 'description-drafts-');
        file_put_contents($file, json_encode(['locale' => 'ru-BY', 'products' => [[
            'external_id' => '1c-saft-ls14250-cna', 'identity_scope' => 'model_core',
            'manufacturer' => 'SAFT', 'model_core' => 'LS14250',
            'source_url' => 'https://manufacturer.example.test/saft-ls-series',
            'technical_attributes' => ['Номинальное напряжение' => '3,6 В'],
        ]]], JSON_THROW_ON_ERROR | JSON_UNESCAPED_UNICODE));

        try {
            $this->artisan('content:stage-source-backed-description-drafts', [
                'site' => 'microchips-by', 'file' => $file, '--apply' => true,
            ])->assertSuccessful();

            $draft = ProductDescriptionDraft::query()->sole();
            $this->assertSame('LS14250', $draft->verified_fields['model']);
            $this->assertArrayNotHasKey('mpn', $draft->verified_fields);
            $this->assertStringContainsString('3,6 В', $draft->content);
        } finally {
            @unlink($file);
        }
    }

    public function test_it_blocks_model_core_without_exact_name_boundaries(): void
    {
        $site = Site::create([
            'key' => 'microchips-by', 'domain' => 'microchips-by.test', 'country_code' => 'BY',
            'currency_code' => 'BYN', 'default_locale' => 'ru-BY', 'name' => 'RB', 'is_active' => true,
        ]);
        $product = Product::create([
            'external_id' => '1c-saft-lsh200', 'name' => 'SAFT LSH200 lithium cell',
            'slug' => 'saft-lsh200', 'manufacturer' => 'Saft', 'status' => 'active',
        ]);
        SiteProduct::create(['site_id' => $site->id, 'product_id' => $product->id, 'slug' => 'saft-lsh200']);
        $file = tempnam(sys_get_temp_dir(), 'description-drafts-');
        file_put_contents($file, json_encode(['locale' => 'ru-BY', 'products' => [[
            'external_id' => '1c-saft-lsh200', 'identity_scope' => 'model_core',
            'manufacturer' => 'Saft', 'model_core' => 'LSH20',
            'source_url' => 'https://manufacturer.example.test/saft-lsh-series',
            'technical_attributes' => ['Voltage' => '3.6 V'],
        ]]], JSON_THROW_ON_ERROR));

        try {
            $this->artisan('content:stage-source-backed-description-drafts', [
                'site' => 'microchips-by', 'file' => $file, '--apply' => true,
            ])->assertFailed();
            $this->assertDatabaseCount('product_description_drafts', 0);
        } finally {
            @unlink($file);
        }
    }

    public function test_it_blocks_model_core_when_the_catalogue_manufacturer_conflicts(): void
    {
        $site = Site::create([
            'key' => 'microchips-by', 'domain' => 'microchips-by.test', 'country_code' => 'BY',
            'currency_code' => 'BYN', 'default_locale' => 'ru-BY', 'name' => 'RB', 'is_active' => true,
        ]);
        $product = Product::create([
            'external_id' => '1c-other-lsh20', 'name' => 'LSH20 lithium cell',
            'slug' => 'other-lsh20', 'manufacturer' => 'Other', 'status' => 'active',
        ]);
        SiteProduct::create(['site_id' => $site->id, 'product_id' => $product->id, 'slug' => 'other-lsh20']);
        $file = tempnam(sys_get_temp_dir(), 'description-drafts-');
        file_put_contents($file, json_encode(['locale' => 'ru-BY', 'products' => [[
            'external_id' => '1c-other-lsh20', 'identity_scope' => 'model_core',
            'manufacturer' => 'Saft', 'model_core' => 'LSH20',
            'source_url' => 'https://manufacturer.example.test/saft-lsh-series',
            'technical_attributes' => ['Voltage' => '3.6 V'],
        ]]], JSON_THROW_ON_ERROR));

        try {
            $this->artisan('content:stage-source-backed-description-drafts', [
                'site' => 'microchips-by', 'file' => $file, '--apply' => true,
            ])->assertFailed();
            $this->assertDatabaseCount('product_description_drafts', 0);
        } finally {
            @unlink($file);
        }
    }

    public function test_it_refreshes_only_an_unapplied_draft_when_explicitly_requested(): void
    {
        $site = Site::create(['key' => 'microchips-by', 'domain' => 'microchips-by.test', 'country_code' => 'BY', 'currency_code' => 'BYN', 'default_locale' => 'ru-BY', 'name' => 'RB', 'is_active' => true]);
        $product = Product::create(['external_id' => '1c-dt401', 'name' => 'Delta DT 401', 'slug' => 'delta-dt-401', 'manufacturer' => 'Delta', 'mpn' => 'DT401', 'status' => 'active']);
        SiteProduct::create(['site_id' => $site->id, 'product_id' => $product->id, 'slug' => 'delta-dt-401']);
        ProductDescriptionDraft::create(['product_id' => $product->id, 'locale' => 'ru-BY', 'title' => 'Old', 'content' => 'Old evidence.', 'verified_fields' => ['technology' => 'AGM'], 'source_urls' => ['https://manufacturer.example.test/old'], 'status' => 'draft']);
        $file = tempnam(sys_get_temp_dir(), 'description-drafts-');
        file_put_contents($file, json_encode(['locale' => 'ru-BY', 'products' => [[
            'external_id' => '1c-dt401', 'manufacturer' => 'Delta', 'mpn' => 'DT401', 'technology' => 'AGM',
            'source_url' => 'https://manufacturer.example.test/dt401', 'technical_attributes' => ['Voltage' => '4 V'],
        ]]], JSON_THROW_ON_ERROR));

        try {
            $this->artisan('content:stage-source-backed-description-drafts', ['site' => 'microchips-by', 'file' => $file, '--apply' => true])->assertSuccessful();
            $this->assertSame('Old evidence.', ProductDescriptionDraft::query()->sole()->content);

            $this->artisan('content:stage-source-backed-description-drafts', ['site' => 'microchips-by', 'file' => $file, '--refresh-existing' => true, '--apply' => true])->assertSuccessful();
            $draft = ProductDescriptionDraft::query()->sole();
            $this->assertSame(['https://manufacturer.example.test/dt401'], $draft->source_urls);
            $this->assertSame(['Voltage' => '4 V', 'Технология' => 'AGM'], $draft->verified_fields['technical_attributes']);
        } finally {
            @unlink($file);
        }
    }

    public function test_it_refreshes_a_legacy_preview_only_with_both_explicit_refresh_flags(): void
    {
        $site = Site::create(['key' => 'microchips-by', 'domain' => 'microchips-by.test', 'country_code' => 'BY', 'currency_code' => 'BYN', 'default_locale' => 'ru-BY', 'name' => 'RB', 'is_active' => true]);
        $product = Product::create(['external_id' => 'bitrix:12162', 'name' => 'Zebra BTRY-MC55EAB02', 'slug' => 'zebra-btry-mc55eab02', 'manufacturer' => 'Zebra', 'mpn' => 'BTRY-MC55EAB02', 'status' => 'active']);
        SiteProduct::create(['site_id' => $site->id, 'product_id' => $product->id, 'slug' => 'zebra-btry-mc55eab02', 'is_published' => true]);
        ProductDescriptionDraft::create([
            'product_id' => $product->id,
            'locale' => 'ru-BY',
            'title' => 'Legacy title',
            'content' => 'Legacy preview.',
            'verified_fields' => ['name' => $product->name],
            'source_urls' => ['https://microchips.by/catalog/legacy'],
            'source_kind' => 'legacy_bitrix_exact_element_preview',
            'source_tier' => 'company_owned_legacy_preview',
            'status' => 'legacy_preview_applied',
        ]);
        $file = tempnam(sys_get_temp_dir(), 'description-drafts-');
        file_put_contents($file, json_encode(['locale' => 'ru-BY', 'products' => [[
            'external_id' => 'bitrix:12162',
            'manufacturer' => 'Zebra',
            'mpn' => 'BTRY-MC55EAB02',
            'technology' => 'Li-ion',
            'source_url' => 'https://www.zebra.com/example.pdf',
            'technical_attributes' => ['Capacity' => '3600 mAh'],
        ]]], JSON_THROW_ON_ERROR));

        try {
            $this->artisan('content:stage-source-backed-description-drafts', [
                'site' => 'microchips-by', 'file' => $file, '--refresh-existing' => true, '--apply' => true,
            ])->assertFailed();
            $this->assertSame('Legacy preview.', ProductDescriptionDraft::query()->sole()->content);

            $this->artisan('content:stage-source-backed-description-drafts', [
                'site' => 'microchips-by', 'file' => $file, '--refresh-existing' => true,
                '--refresh-applied' => true, '--apply' => true,
            ])->assertSuccessful();

            $draft = ProductDescriptionDraft::query()->sole();
            $this->assertSame('draft', $draft->status);
            $this->assertSame(['https://www.zebra.com/example.pdf'], $draft->source_urls);
            $this->assertSame(['Capacity' => '3600 mAh', 'Технология' => 'Li-ion'], $draft->verified_fields['technical_attributes']);
            $this->assertTrue($product->refresh()->sites()->sole()->is_published);
        } finally {
            @unlink($file);
        }
    }
}
