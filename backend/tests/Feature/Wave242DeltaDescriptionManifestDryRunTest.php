<?php

namespace Tests\Feature;

use App\Models\CatalogDraftMaterialization;
use App\Models\ImportRun;
use App\Models\Product;
use App\Models\Site;
use App\Models\SiteProduct;
use App\Models\StagedImportRecord;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class Wave242DeltaDescriptionManifestDryRunTest extends TestCase
{
    use RefreshDatabase;

    public function test_wave242_manifest_passes_the_real_laravel_dry_run_without_apply(): void
    {
        $manifestPath = base_path('../docs/imports/rb-source-backed-descriptions-wave242-delta-2026-07-29.json');
        $manifest = json_decode((string) file_get_contents($manifestPath), true, 512, JSON_THROW_ON_ERROR);
        $this->assertSame('ru-BY', $manifest['locale']);
        $this->assertCount(56, $manifest['products']);

        $site = Site::create([
            'key' => 'microchips-by', 'domain' => 'microchips-by.test', 'country_code' => 'BY',
            'currency_code' => 'BYN', 'default_locale' => 'ru-BY', 'name' => 'RB', 'is_active' => true,
        ]);
        $sourceRun = ImportRun::create([
            'source' => 'bitrix_full_catalog_snapshot:microchips-by', 'status' => 'completed',
        ]);
        $materializationRun = ImportRun::create([
            'source' => 'materialize_bitrix_drafts', 'status' => 'completed',
        ]);

        foreach ($manifest['products'] as $offset => $row) {
            $slug = 'wave242-'.str_replace(':', '-', $row['external_id']);
            $product = Product::create([
                'external_id' => $row['external_id'],
                'name' => $this->ledgerTitle($row['external_id']),
                'slug' => $slug,
                'manufacturer' => null,
                'mpn' => null,
                'status' => 'active',
            ]);
            $siteProduct = SiteProduct::create([
                'site_id' => $site->id,
                'product_id' => $product->id,
                'slug' => $slug,
                'is_published' => false,
            ]);
            $staged = StagedImportRecord::create([
                'import_run_id' => $sourceRun->id,
                'row_number' => $offset + 1,
                'entity_type' => 'bitrix_full_catalog_product_evidence',
                'external_id' => $row['external_id'],
                'payload' => ['transfer_status' => 'legacy_only_draft_candidate', 'allow_publication' => true],
                'normalized_payload' => ['transfer_status' => 'legacy_only_draft_candidate'],
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
                'source_external_id' => $row['external_id'],
                'source_checksum' => hash('sha256', $row['external_id']),
                'materialization_kind' => CatalogDraftMaterialization::KIND_NAMESPACED_DRAFT,
                'target_category_external_id' => 'seo:batteries-ups',
            ]);
        }

        $this->artisan('content:stage-source-backed-description-drafts', [
            'site' => 'microchips-by',
            'file' => $manifestPath,
        ])->assertSuccessful();

        $this->assertDatabaseCount('product_description_drafts', 0);
        $dryRun = ImportRun::query()->where('source', 'source_backed_description_drafts')->sole();
        $this->assertSame('dry_run_complete', $dryRun->status);
        $this->assertSame(56, $dryRun->total_records);
        $this->assertSame(56, $dryRun->summary['created']);
    }

    private function ledgerTitle(string $externalId): string
    {
        $handle = fopen(base_path('../docs/audits/generated/rb-wave242-delta-hold-research-ledger.csv'), 'rb');
        $this->assertIsResource($handle);
        $header = fgetcsv($handle);
        $header[0] = preg_replace('/^\xEF\xBB\xBF/', '', $header[0]);
        while (($values = fgetcsv($handle)) !== false) {
            $row = array_combine($header, $values);
            if (($row['external_id'] ?? null) === $externalId) {
                fclose($handle);

                return $row['current_name'];
            }
        }
        fclose($handle);
        $this->fail("Wave242 ledger row {$externalId} is missing.");
    }
}
