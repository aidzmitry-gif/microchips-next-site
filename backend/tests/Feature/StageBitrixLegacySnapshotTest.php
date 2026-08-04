<?php

namespace Tests\Feature;

use App\Models\ImportRun;
use App\Models\Product;
use App\Models\Site;
use App\Models\SiteProduct;
use App\Models\StagedImportRecord;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class StageBitrixLegacySnapshotTest extends TestCase
{
    use RefreshDatabase;

    public function test_stages_complete_snapshot_without_rendering_or_publication_and_is_idempotent(): void
    {
        $site = Site::create([
            'key' => 'microchips-by', 'domain' => 'microchips.by', 'country_code' => 'BY',
            'currency_code' => 'BYN', 'default_locale' => 'ru-BY', 'name' => 'Microchips BY',
        ]);
        $product = Product::create(['external_id' => 'P1', 'slug' => 'p1', 'name' => 'Product', 'status' => 'active']);
        SiteProduct::create([
            'site_id' => $site->id, 'product_id' => $product->id, 'slug' => 'p1',
            'is_published' => false, 'availability' => 'on_request',
        ]);
        $file = $this->manifest();
        $arguments = [
            'site' => $site->key,
            'file' => $file,
            '--expected-records' => 2,
        ];

        $this->artisan('catalog:stage-bitrix-legacy-snapshot', $arguments)->assertSuccessful();
        $this->assertDatabaseCount('import_runs', 0);

        $this->artisan('catalog:stage-bitrix-legacy-snapshot', [...$arguments, '--apply' => true])->assertSuccessful();
        $this->assertDatabaseCount('import_runs', 1);
        $this->assertDatabaseCount('staged_import_records', 2);
        $this->assertSame(0, StagedImportRecord::query()->whereNotNull('published_at')->count());
        $this->assertSame(0, StagedImportRecord::query()->whereNotNull('published_product_id')->count());
        $this->assertSame('completed', ImportRun::query()->sole()->status);

        $this->artisan('catalog:stage-bitrix-legacy-snapshot', [...$arguments, '--apply' => true])->assertSuccessful();
        $this->assertDatabaseCount('import_runs', 1);
        $this->assertDatabaseCount('staged_import_records', 2);
    }

    private function manifest(): string
    {
        $file = storage_path('framework/testing/bitrix-snapshot-'.uniqid().'.json');
        file_put_contents($file, json_encode([
            'schema_version' => 1,
            'records' => [
                [
                    'legacy_element_id' => '1',
                    'one_c_external_id' => 'P1',
                    'transfer_status' => 'strict_mapped_evidence',
                    'legacy_text_sha256' => hash('sha256', 'legacy'),
                    'render_legacy_html' => false,
                    'change_publication' => false,
                ],
                [
                    'legacy_element_id' => '2',
                    'one_c_external_id' => '',
                    'transfer_status' => 'hold_missing_1c_identity',
                    'legacy_text_sha256' => '',
                    'render_legacy_html' => false,
                    'change_publication' => false,
                ],
            ],
        ], JSON_THROW_ON_ERROR));

        return $file;
    }
}
