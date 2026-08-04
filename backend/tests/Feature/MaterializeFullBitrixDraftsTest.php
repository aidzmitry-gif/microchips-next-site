<?php

namespace Tests\Feature;

use App\Models\Category;
use App\Models\ImportRun;
use App\Models\Site;
use App\Models\SiteCategory;
use App\Models\StagedImportRecord;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Tests\TestCase;

class MaterializeFullBitrixDraftsTest extends TestCase
{
    use RefreshDatabase;

    public function test_it_materializes_bounded_namespaced_drafts_without_public_urls_and_continues_next_batch(): void
    {
        [$site, $sourceRun] = $this->sourceFixture();
        $arguments = [
            'site' => $site->key,
            '--source-run' => $sourceRun->id,
            '--source-manifest-sha256' => str_repeat('a', 64),
            '--expected-source-records' => 4,
            '--expected-candidates' => 3,
            '--batch-size' => 2,
            '--include-held-as-namespaced-drafts' => true,
        ];

        $this->artisan('catalog:materialize-full-bitrix-drafts', $arguments)->assertSuccessful();
        $this->assertDatabaseCount('products', 0);

        $this->artisan('catalog:materialize-full-bitrix-drafts', [...$arguments, '--apply' => true])->assertSuccessful();
        $this->assertDatabaseCount('products', 2);
        $this->assertDatabaseCount('site_products', 2);
        $this->assertDatabaseCount('site_category_product', 2);
        $this->assertDatabaseCount('catalog_draft_materializations', 2);
        $this->assertDatabaseCount('site_urls', 0);
        $this->assertDatabaseCount('site_seos', 0);
        $this->assertDatabaseHas('products', ['external_id' => 'bitrix:1', 'status' => 'draft']);
        $this->assertDatabaseHas('products', ['external_id' => 'bitrix:2', 'status' => 'draft']);
        $this->assertDatabaseMissing('products', ['external_id' => 'bitrix:3']);
        $this->assertDatabaseMissing('products', ['external_id' => 'bitrix:4']);
        $this->assertSame(0, DB::table('site_products')->where('is_published', true)->count());

        $this->artisan('catalog:materialize-full-bitrix-drafts', [...$arguments, '--apply' => true])->assertSuccessful();
        $this->assertDatabaseCount('products', 3);
        $this->assertDatabaseCount('site_products', 3);
        $this->assertDatabaseCount('site_category_product', 3);
        $this->assertDatabaseCount('catalog_draft_materializations', 3);
        $this->assertDatabaseCount('site_urls', 0);
        $this->assertDatabaseCount('site_seos', 0);
    }

    /** @return array{Site,ImportRun} */
    private function sourceFixture(): array
    {
        $site = Site::create([
            'key' => 'microchips-by', 'domain' => 'microchips.by', 'country_code' => 'BY',
            'currency_code' => 'BYN', 'default_locale' => 'ru-BY', 'name' => 'Microchips BY',
        ]);
        $category = Category::create(['slug' => 'primary-cells', 'name' => 'Primary cells']);
        SiteCategory::create([
            'site_id' => $site->id, 'category_id' => $category->id,
            'source' => 'full_catalog_seo_tree', 'external_id' => 'seo:primary-cells',
            'slug' => 'catalog/primary-cells', 'name' => 'Primary cells', 'is_published' => false,
        ]);
        $run = ImportRun::create([
            'source' => 'bitrix_full_catalog_snapshot:microchips-by',
            'status' => 'completed', 'source_file' => 'manifest.json',
            'total_records' => 4, 'processed_records' => 4, 'failed_records' => 0,
            'summary' => ['manifest_sha256' => str_repeat('a', 64)],
            'started_at' => now(), 'finished_at' => now(),
        ]);
        foreach ([
            ['1', 'legacy_only_draft_candidate'],
            ['2', 'hold_duplicate_candidate'],
            ['3', 'hold_one_c_collision'],
            ['4', 'scope_excluded_electronics'],
        ] as $offset => [$id, $status]) {
            $payload = [
                'registry_id' => 'bitrix:'.$id, 'bitrix_id' => $id,
                'name' => 'Product '.$id, 'legacy_section_path' => 'batareyki',
                'legacy_url' => 'https://microchips.by/catalog/batareyki/'.$id.'/',
                'target_category_external_id' => 'seo:primary-cells',
                'one_c_external_id' => '', 'identity_status' => 'unresolved_identity',
                'duplicate_candidate_key' => '', 'transfer_status' => $status,
                'allow_product_create' => $status === 'legacy_only_draft_candidate',
                'allow_publication' => false, 'allow_indexing' => false, 'allow_merge' => false,
            ];
            $checksumPayload = $payload;
            ksort($checksumPayload);
            $payload['source_checksum'] = hash('sha256', json_encode(
                $checksumPayload,
                JSON_THROW_ON_ERROR | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES,
            ));
            StagedImportRecord::create([
                'import_run_id' => $run->id, 'row_number' => $offset + 1,
                'entity_type' => 'bitrix_full_catalog_product_evidence',
                'external_id' => 'bitrix:'.$id, 'payload' => $payload,
                'normalized_payload' => [
                    'site_id' => $site->id, 'bitrix_id' => $id,
                    'one_c_external_id' => '',
                    'target_category_external_id' => 'seo:primary-cells',
                    'transfer_status' => $status,
                    'source_checksum' => $payload['source_checksum'],
                ],
                'validation_errors' => [], 'status' => 'staged_evidence',
            ]);
        }

        return [$site, $run];
    }
}
