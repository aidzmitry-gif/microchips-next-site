<?php

namespace Tests\Feature;

use App\Models\CatalogDraftMaterialization;
use App\Models\Category;
use App\Models\ImportRun;
use App\Models\Product;
use App\Models\Site;
use App\Models\SiteCategory;
use App\Models\SiteProduct;
use App\Models\StagedImportRecord;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class PublishHeldBitrixNoindexCatalogTest extends TestCase
{
    use RefreshDatabase;

    public function test_explicit_held_status_is_published_only_as_a_noindex_preview(): void
    {
        $site = Site::create([
            'key' => 'microchips-by', 'domain' => 'microchips.by', 'country_code' => 'BY',
            'currency_code' => 'BYN', 'default_locale' => 'ru-BY', 'name' => 'Microchips BY',
        ]);
        $category = Category::create(['slug' => 'primary-cells', 'name' => 'Батарейки']);
        $siteCategory = SiteCategory::create([
            'site_id' => $site->id, 'category_id' => $category->id,
            'source' => 'full_catalog_seo_tree', 'external_id' => 'seo:primary-cells',
            'slug' => 'catalog/primary-cells', 'name' => 'Батарейки', 'is_published' => false,
        ]);
        $run = ImportRun::create([
            'source' => 'bitrix_full_catalog_snapshot:microchips-by', 'status' => 'completed',
            'source_file' => 'manifest.json', 'total_records' => 1, 'processed_records' => 1,
            'failed_records' => 0, 'summary' => ['manifest_sha256' => str_repeat('a', 64)],
            'started_at' => now(), 'finished_at' => now(),
        ]);
        $record = StagedImportRecord::create([
            'import_run_id' => $run->id, 'row_number' => 1,
            'entity_type' => 'bitrix_full_catalog_product_evidence', 'external_id' => 'bitrix:42',
            'payload' => ['transfer_status' => 'hold_duplicate_candidate'],
            'normalized_payload' => [
                'transfer_status' => 'hold_duplicate_candidate',
                'target_category_external_id' => 'seo:primary-cells',
            ],
            'validation_errors' => [], 'status' => 'staged_evidence',
        ]);
        $product = Product::create([
            'external_id' => 'bitrix:42', 'slug' => 'legacy-bitrix-42',
            'name' => 'Непроверенная батарея', 'status' => 'draft',
        ]);
        $siteProduct = SiteProduct::create([
            'site_id' => $site->id, 'product_id' => $product->id,
            'slug' => 'legacy-bitrix-42', 'is_published' => false,
            'availability' => 'on_request', 'price' => null,
        ]);
        $siteProduct->categories()->attach($siteCategory->id, ['site_id' => $site->id]);
        CatalogDraftMaterialization::create([
            'materialization_run_id' => $run->id, 'source_import_run_id' => $run->id,
            'staged_import_record_id' => $record->id, 'site_id' => $site->id,
            'product_id' => $product->id, 'site_product_id' => $siteProduct->id,
            'source_namespace' => 'bitrix', 'source_external_id' => 'bitrix:42',
            'source_checksum' => str_repeat('b', 64), 'materialization_kind' => 'namespaced_draft',
            'target_category_external_id' => 'seo:primary-cells',
        ]);

        $arguments = [
            'site' => $site->key, '--source-run' => $run->id,
            '--source-manifest-sha256' => str_repeat('a', 64),
            '--expected-source-records' => 1, '--expected-candidates' => 1,
            '--transfer-status' => ['hold_duplicate_candidate'], '--batch-size' => 10,
        ];

        $this->artisan('catalog:publish-full-bitrix-noindex', $arguments)->assertSuccessful();
        $this->assertFalse($siteProduct->fresh()->is_published);

        $this->artisan('catalog:publish-full-bitrix-noindex', [...$arguments, '--apply' => true])->assertSuccessful();
        $this->assertTrue($siteProduct->fresh()->is_published);
        $this->assertDatabaseHas('site_urls', [
            'site_id' => $site->id, 'path' => '/catalog/primary-cells/legacy-bitrix-42',
            'target_type' => 'product', 'target_id' => $siteProduct->id, 'is_indexable' => false,
        ]);
        $this->assertDatabaseHas('site_seos', [
            'site_id' => $site->id, 'resource_type' => 'product',
            'resource_id' => $siteProduct->id, 'is_indexable' => false, 'schema' => null,
        ]);
        $this->assertNull($siteProduct->fresh()->price);
    }
}
