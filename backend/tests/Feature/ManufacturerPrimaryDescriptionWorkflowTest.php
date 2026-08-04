<?php

namespace Tests\Feature;

use App\Models\CatalogDraftMaterialization;
use App\Models\ImportRun;
use App\Models\Product;
use App\Models\ProductDescriptionDraft;
use App\Models\Site;
use App\Models\SiteProduct;
use App\Models\StagedImportRecord;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class ManufacturerPrimaryDescriptionWorkflowTest extends TestCase
{
    use RefreshDatabase;

    public function test_it_accepts_exact_model_evidence_from_an_official_manufacturer_catalogue(): void
    {
        [$site, $product] = $this->catalogueProduct('bitrix:25109', 'Источник бесперебойного питания IPPON Back Basic 650');
        $file = $this->manifestFile($product->external_id, 'Back Basic 650');

        try {
            $this->artisan('content:stage-source-backed-description-drafts', [
                'site' => $site->key, 'file' => $file, '--apply' => true,
            ])->assertSuccessful();

            $draft = ProductDescriptionDraft::query()->sole();
            $this->assertSame('manufacturer_primary', $draft->source_tier);
            $this->assertSame('official_manufacturer_catalogue', $draft->source_kind);
            $this->assertTrue($draft->manufacturer_primary);
            $this->assertSame('exact', $draft->identity_scope);
            $this->assertSame('Back Basic 650', $draft->verified_fields['mpn']);
            $this->assertNull($product->refresh()->mpn);
        } finally {
            @unlink($file);
        }
    }

    public function test_it_rejects_an_exact_mpn_that_is_not_present_in_the_catalogue_name(): void
    {
        [$site, $product] = $this->catalogueProduct('bitrix:25109', 'Источник бесперебойного питания IPPON Back Basic 650');
        $file = $this->manifestFile($product->external_id, 'Back Basic 850');

        try {
            $this->artisan('content:stage-source-backed-description-drafts', [
                'site' => $site->key, 'file' => $file, '--apply' => true,
            ])->assertFailed();
            $this->assertDatabaseCount('product_description_drafts', 0);
        } finally {
            @unlink($file);
        }
    }

    public function test_it_rejects_a_shorter_model_when_the_catalogue_name_has_a_variant_suffix(): void
    {
        [$site, $product] = $this->catalogueProduct('bitrix:25126', 'Источник бесперебойного питания IPPON Back Basic 1050 S Euro');
        $file = $this->manifestFile($product->external_id, 'Back Basic 1050');

        try {
            $this->artisan('content:stage-source-backed-description-drafts', [
                'site' => $site->key, 'file' => $file, '--apply' => true,
            ])->assertFailed();
            $this->assertDatabaseCount('product_description_drafts', 0);
        } finally {
            @unlink($file);
        }
    }

    public function test_it_rejects_an_exact_mpn_that_already_belongs_to_another_product(): void
    {
        [$site, $product] = $this->catalogueProduct('bitrix:25109', 'Источник бесперебойного питания IPPON Back Basic 650');
        Product::create([
            'external_id' => '1c:existing-ippon', 'name' => 'IPPON Back Basic 650',
            'slug' => 'existing-ippon-back-basic-650', 'manufacturer' => 'IPPON',
            'mpn' => 'Back Basic 650', 'status' => 'active',
        ]);
        $file = $this->manifestFile($product->external_id, 'Back Basic 650');

        try {
            $this->artisan('content:stage-source-backed-description-drafts', [
                'site' => $site->key, 'file' => $file, '--apply' => true,
            ])->assertFailed();
            $this->assertDatabaseCount('product_description_drafts', 0);
        } finally {
            @unlink($file);
        }
    }

    public function test_it_rejects_an_exact_mpn_that_matches_another_products_sku(): void
    {
        [$site, $product] = $this->catalogueProduct('bitrix:25109', 'Источник бесперебойного питания IPPON Back Basic 650');
        Product::create([
            'external_id' => '1c:existing-ippon-sku', 'name' => 'Existing inventory row',
            'slug' => 'existing-ippon-sku', 'manufacturer' => 'IPPON',
            'sku' => 'Back Basic 650', 'status' => 'active',
        ]);
        $file = $this->manifestFile($product->external_id, 'Back Basic 650');

        try {
            $this->artisan('content:stage-source-backed-description-drafts', [
                'site' => $site->key, 'file' => $file, '--apply' => true,
            ])->assertFailed();
            $this->assertDatabaseCount('product_description_drafts', 0);
        } finally {
            @unlink($file);
        }
    }

    public function test_it_rejects_a_bitrix_record_with_a_held_transfer_status(): void
    {
        [$site, $product] = $this->catalogueProduct(
            'bitrix:25121',
            'Источник бесперебойного питания IPPON Back Basic 1050',
            'hold_one_c_collision',
        );
        $file = $this->manifestFile($product->external_id, 'Back Basic 1050');

        try {
            $this->artisan('content:stage-source-backed-description-drafts', [
                'site' => $site->key, 'file' => $file, '--apply' => true,
            ])->assertFailed();
            $this->assertDatabaseCount('product_description_drafts', 0);
        } finally {
            @unlink($file);
        }
    }

    public function test_it_rejects_inconsistent_manufacturer_primary_provenance(): void
    {
        [$site, $product] = $this->catalogueProduct('bitrix:25109', 'Источник бесперебойного питания IPPON Back Basic 650');
        $file = $this->manifestFile($product->external_id, 'Back Basic 650', [
            'manufacturer_primary' => false,
        ]);

        try {
            $this->artisan('content:stage-source-backed-description-drafts', [
                'site' => $site->key, 'file' => $file, '--apply' => true,
            ])->assertFailed();
            $this->assertDatabaseCount('product_description_drafts', 0);
        } finally {
            @unlink($file);
        }
    }

    public function test_it_stages_and_applies_manufacturer_primary_model_core_without_changing_legacy_identity(): void
    {
        [$site, $product] = $this->catalogueProduct('bitrix:panasonic-cr123a', 'Panasonic CR123A 1BP');
        $product->update(['mpn' => 'legacy-pack-1BP', 'sku' => 'legacy-sku', 'short_description' => 'Legacy text.']);
        $siteProduct = SiteProduct::query()->where('site_id', $site->id)->where('product_id', $product->id)->sole();
        $siteProduct->update(['availability' => 'on_request', 'price' => null, 'currency' => null, 'is_published' => false]);
        $file = $this->modelCoreManifestFile($product->external_id, 'CR123A');

        try {
            $this->artisan('content:stage-source-backed-description-drafts', [
                'site' => $site->key, 'file' => $file, '--apply' => true,
            ])->assertSuccessful();
            $draft = ProductDescriptionDraft::query()->sole();
            $this->assertSame('model_core', $draft->identity_scope);
            $this->assertArrayNotHasKey('mpn', $draft->verified_fields);
            $this->assertSame('Panasonic CR123A 1BP', $draft->verified_fields['name']);

            $this->artisan('content:apply-verified-description-drafts', [
                'site' => $site->key, 'file' => $file, '--apply' => true,
            ])->assertSuccessful();
            $product->refresh();
            $this->assertSame('Panasonic CR123A 1BP', $product->name);
            $this->assertSame('legacy-pack-1BP', $product->mpn);
            $this->assertSame('legacy-sku', $product->sku);
            $this->assertSame('active', $product->status);
            $this->assertSame('Panasonic', $product->manufacturer);
            $this->assertNotSame('Legacy text.', $product->short_description);
            $this->assertSame('3 V', $product->technical_attributes['Voltage']);
            $siteProduct->refresh();
            $this->assertSame('on_request', $siteProduct->availability);
            $this->assertNull($siteProduct->price);
            $this->assertNull($siteProduct->currency);
            $this->assertFalse($siteProduct->is_published);
        } finally {
            @unlink($file);
        }
    }

    public function test_it_rejects_missing_or_ambiguous_manufacturer_primary_model_core(): void
    {
        [$site, $product] = $this->catalogueProduct('bitrix:panasonic-cr123ab', 'Panasonic CR123AB 1BP');
        $ambiguous = $this->modelCoreManifestFile($product->external_id, 'CR123A');
        $missing = $this->modelCoreManifestFile($product->external_id, '');
        try {
            $this->artisan('content:stage-source-backed-description-drafts', [
                'site' => $site->key, 'file' => $ambiguous, '--apply' => true,
            ])->assertFailed();
            $this->artisan('content:stage-source-backed-description-drafts', [
                'site' => $site->key, 'file' => $missing, '--apply' => true,
            ])->assertFailed();
            $this->assertDatabaseCount('product_description_drafts', 0);
        } finally {
            @unlink($ambiguous);
            @unlink($missing);
        }
    }

    public function test_it_rejects_manufacturer_primary_model_core_when_brand_is_absent_from_name_and_identity(): void
    {
        [$site, $product] = $this->catalogueProduct('bitrix:generic-cr2032', 'Батарейка CR2032 1BP');
        $file = $this->modelCoreManifestFile($product->external_id, 'CR2032');

        try {
            $this->artisan('content:stage-source-backed-description-drafts', [
                'site' => $site->key, 'file' => $file, '--apply' => true,
            ])->assertFailed();
            $this->assertDatabaseCount('product_description_drafts', 0);
        } finally {
            @unlink($file);
        }
    }

    /** @return array{Site, Product} */
    private function catalogueProduct(string $externalId, string $name, string $transferStatus = 'legacy_only_draft_candidate'): array
    {
        $site = Site::create([
            'key' => 'microchips-by', 'domain' => 'microchips-by.test', 'country_code' => 'BY',
            'currency_code' => 'BYN', 'default_locale' => 'ru-BY', 'name' => 'RB', 'is_active' => true,
        ]);
        $product = Product::create([
            'external_id' => $externalId, 'name' => $name, 'slug' => 'draft-'.$externalId,
            'manufacturer' => null, 'mpn' => null, 'status' => 'active',
        ]);
        $siteProduct = SiteProduct::create([
            'site_id' => $site->id, 'product_id' => $product->id,
            'slug' => 'draft-'.$externalId, 'is_published' => false,
        ]);
        if (str_starts_with($externalId, 'bitrix:')) {
            $sourceRun = ImportRun::create(['source' => 'bitrix_full_catalog_snapshot:'.$site->key, 'status' => 'completed']);
            $materializationRun = ImportRun::create(['source' => 'materialize_bitrix_drafts', 'status' => 'completed']);
            $staged = StagedImportRecord::create([
                'import_run_id' => $sourceRun->id,
                'row_number' => 1,
                'entity_type' => 'bitrix_full_catalog_product_evidence',
                'external_id' => $externalId,
                'payload' => ['transfer_status' => $transferStatus, 'allow_publication' => $transferStatus === 'legacy_only_draft_candidate'],
                'normalized_payload' => ['transfer_status' => $transferStatus],
                'status' => 'staged_evidence',
            ]);
            CatalogDraftMaterialization::create([
                'materialization_run_id' => $materializationRun->id,
                'source_import_run_id' => $sourceRun->id,
                'staged_import_record_id' => $staged->id,
                'site_id' => $site->id,
                'product_id' => $product->id,
                'site_product_id' => $siteProduct->id,
                'source_namespace' => 'bitrix',
                'source_external_id' => $externalId,
                'source_checksum' => hash('sha256', $externalId),
                'materialization_kind' => CatalogDraftMaterialization::KIND_NAMESPACED_DRAFT,
                'target_category_external_id' => 'seo:power-systems',
            ]);
        }

        return [$site, $product];
    }

    /** @param array<string, mixed> $overrides */
    private function manifestFile(string $externalId, string $mpn, array $overrides = []): string
    {
        $row = array_replace([
            'external_id' => $externalId,
            'identity_scope' => 'exact',
            'manufacturer' => 'IPPON',
            'mpn' => $mpn,
            'technology' => 'Линейно-интерактивный ИБП',
            'source_url' => 'https://static.ippon.ru/data/download/Ippon_UPS_Catalogue_II_2024.pdf',
            'technical_attributes' => [
                'Топология' => 'Линейно-интерактивная',
                'Полная мощность' => '650 В·А',
                'Активная мощность' => '360 Вт',
            ],
            'source_kind' => 'official_manufacturer_catalogue',
            'source_tier' => 'manufacturer_primary',
            'source_publisher' => 'IPPON',
            'manufacturer_primary' => true,
            'evidence_scope' => 'exact_model',
            'checked_at' => '2026-07-29',
        ], $overrides);
        $file = tempnam(sys_get_temp_dir(), 'manufacturer-primary-');
        file_put_contents($file, json_encode([
            'locale' => 'ru-BY', 'products' => [$row],
        ], JSON_THROW_ON_ERROR | JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT));

        return $file;
    }

    private function modelCoreManifestFile(string $externalId, string $modelCore): string
    {
        $file = tempnam(sys_get_temp_dir(), 'manufacturer-primary-model-core-');
        file_put_contents($file, json_encode(['locale' => 'ru-BY', 'products' => [[
            'external_id' => $externalId,
            'identity_scope' => 'model_core',
            'manufacturer' => 'Panasonic',
            'model_core' => $modelCore,
            'technology' => 'Lithium primary cell',
            'source_url' => 'https://www.panasonic.com/global/energy/products/batteries.html',
            'technical_attributes' => ['Voltage' => '3 V'],
            'source_kind' => 'official_manufacturer_catalogue',
            'source_tier' => 'manufacturer_primary',
            'source_publisher' => 'Panasonic',
            'manufacturer_primary' => true,
            'evidence_scope' => 'model_core',
            'checked_at' => '2026-07-29',
        ]]], JSON_THROW_ON_ERROR | JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT));

        return $file;
    }
}
