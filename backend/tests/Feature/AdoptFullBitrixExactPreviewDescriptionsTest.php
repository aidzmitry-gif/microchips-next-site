<?php

namespace Tests\Feature;

use App\Models\CatalogDraftMaterialization;
use App\Models\ImportRun;
use App\Models\Product;
use App\Models\ProductDescriptionDraft;
use App\Models\Site;
use App\Models\SiteProduct;
use App\Models\SiteUrl;
use App\Models\StagedImportRecord;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Artisan;
use Illuminate\Support\Facades\Queue;
use Tests\TestCase;

class AdoptFullBitrixExactPreviewDescriptionsTest extends TestCase
{
    use RefreshDatabase;

    public function test_applies_only_sanitized_same_element_text_to_a_noindex_namespaced_draft(): void
    {
        Queue::fake();
        $site = Site::create([
            'key' => 'microchips-by', 'domain' => 'microchips.by', 'country_code' => 'BY',
            'currency_code' => 'BYN', 'default_locale' => 'ru-BY', 'name' => 'Microchips BY',
        ]);
        $sourceRun = ImportRun::create([
            'source' => 'bitrix_full_catalog_snapshot:microchips-by', 'status' => 'completed',
            'source_file' => 'full.json', 'total_records' => 1, 'processed_records' => 1,
            'failed_records' => 0, 'started_at' => now(), 'finished_at' => now(),
        ]);
        $materializationRun = ImportRun::create([
            'source' => 'bitrix_full_catalog_draft_materialization:microchips-by', 'status' => 'completed',
            'source_file' => 'full.json', 'total_records' => 1, 'processed_records' => 1,
            'failed_records' => 0, 'started_at' => now(), 'finished_at' => now(),
        ]);
        $staged = StagedImportRecord::create([
            'import_run_id' => $sourceRun->id, 'row_number' => 1, 'entity_type' => 'bitrix_full_catalog_product',
            'external_id' => 'bitrix:42',
            'payload' => ['legacy_url' => 'https://microchips.by/catalog/example/42/'],
            'normalized_payload' => ['transfer_status' => 'legacy_only_draft_candidate'],
            'validation_errors' => [], 'status' => 'staged_evidence',
        ]);
        $product = Product::create([
            'external_id' => 'bitrix:42', 'slug' => 'legacy-bitrix-42',
            'name' => 'Battery Example 42', 'status' => 'active',
        ]);
        $siteProduct = SiteProduct::create([
            'site_id' => $site->id, 'product_id' => $product->id, 'slug' => 'legacy-bitrix-42',
            'is_published' => true, 'availability' => 'on_request',
        ]);
        SiteUrl::create([
            'site_id' => $site->id, 'path' => '/catalog/example/legacy-bitrix-42',
            'locale' => 'ru-BY', 'target_type' => 'product', 'target_id' => $siteProduct->id,
            'is_indexable' => false,
        ]);
        CatalogDraftMaterialization::create([
            'materialization_run_id' => $materializationRun->id,
            'source_import_run_id' => $sourceRun->id,
            'staged_import_record_id' => $staged->id,
            'site_id' => $site->id, 'product_id' => $product->id, 'site_product_id' => $siteProduct->id,
            'source_namespace' => 'bitrix', 'source_external_id' => 'bitrix:42',
            'source_checksum' => str_repeat('a', 64), 'materialization_kind' => 'namespaced_draft',
            'target_category_external_id' => 'seo:test',
        ]);

        $file = storage_path('framework/testing/full-bitrix-content-'.uniqid().'.csv');
        $handle = fopen($file, 'wb');
        fwrite($handle, "\xEF\xBB\xBF");
        fputcsv($handle, ['legacy_element_id', 'name', 'preview_text', 'detail_text'], ',', '"', '');
        fputcsv($handle, ['42', 'Battery Example 42', 'Preview', '<p>Useful legacy copy</p><script>bad()</script>'], ',', '"', '');
        fclose($handle);
        $hash = hash_file('sha256', $file);

        $arguments = [
            'site' => $site->key, 'file' => $file, '--source-run' => $sourceRun->id,
            '--expected-records' => 1, '--expected-sha256' => $hash, '--batch-size' => 10,
        ];
        $exit = Artisan::call('catalog:adopt-full-bitrix-exact-preview-descriptions', $arguments);
        $output = Artisan::output();
        $this->assertSame(0, $exit, $output);
        $this->assertStringContainsString('"selected_batch": 1', $output);
        $this->assertNull($product->fresh()->short_description);

        $exit = Artisan::call('catalog:adopt-full-bitrix-exact-preview-descriptions', [...$arguments, '--apply' => true]);
        $output = Artisan::output();
        $this->assertSame(0, $exit, $output);
        $this->assertStringContainsString('"legacy_preview_descriptions_created": 1', $output);

        $this->assertSame('Useful legacy copy', $product->fresh()->short_description);
        $draft = ProductDescriptionDraft::query()->where('product_id', $product->id)->sole();
        $this->assertSame('legacy_preview_applied', $draft->status);
        $this->assertSame('legacy_bitrix_exact_element_preview', $draft->source_kind);
        $this->assertSame('exact_legacy_element', $draft->identity_scope);
        $this->assertFalse((bool) SiteUrl::query()->where('target_type', 'product')->where('target_id', $siteProduct->id)->value('is_indexable'));
        $this->assertNull($siteProduct->fresh()->price);

        $exit = Artisan::call('catalog:adopt-full-bitrix-exact-preview-descriptions', $arguments);
        $output = Artisan::output();
        $this->assertSame(0, $exit, $output);
        $this->assertStringContainsString('"eligible_missing_legacy_descriptions": 0', $output);
    }
}
