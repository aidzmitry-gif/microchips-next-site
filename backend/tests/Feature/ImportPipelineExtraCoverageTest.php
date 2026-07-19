<?php

namespace Tests\Feature;

use App\Domain\Imports\StagedProductPublisher;
use App\Models\DuplicateConflict;
use App\Models\ImportRun;
use App\Models\Product;
use App\Models\Site;
use App\Models\SiteProduct;
use App\Models\StagedImportRecord;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class ImportPipelineExtraCoverageTest extends TestCase
{
    use RefreshDatabase;

    public function test_two_staged_rows_sharing_an_mpn_are_flagged_as_a_duplicate_conflict(): void
    {
        $file = $this->csvFile(<<<'CSV'
external_id;name;mpn
1c-m1;Widget A;MPN-100
1c-m2;Widget B;MPN-100
CSV, 'mpn-collision.csv');

        $this->artisan('catalog:stage-1c', ['file' => $file, '--delimiter' => ';'])->assertSuccessful();

        $run = ImportRun::query()->sole();
        $this->assertSame('needs_review', $run->status);
        $this->assertSame(1, $run->summary['duplicate_conflicts']);

        $conflict = DuplicateConflict::query()->sole();
        $this->assertSame('mpn:mpn-100', $conflict->match_key);
        $this->assertCount(2, $conflict->candidate_ids['staged_record_ids']);
        $this->assertSame([], $conflict->candidate_ids['product_ids']);

        $this->assertDatabaseHas('staged_import_records', [
            'import_run_id' => $run->id,
            'external_id' => '1c-m1',
            'status' => 'duplicate',
        ]);
        $this->assertDatabaseHas('staged_import_records', [
            'import_run_id' => $run->id,
            'external_id' => '1c-m2',
            'status' => 'duplicate',
        ]);
    }

    public function test_an_mpn_collision_against_a_product_with_a_different_external_id_is_reported_as_a_product_conflict(): void
    {
        $existing = Product::create([
            'external_id' => '1c-other',
            'mpn' => 'MPN-200',
            'slug' => 'delta-battery-existing',
            'name' => 'Delta Battery (existing)',
            'status' => 'active',
        ]);

        $file = $this->csvFile(<<<'CSV'
external_id;name;mpn
1c-real;Delta Battery;MPN-200
CSV, 'mpn-external-id-mismatch.csv');

        $this->artisan('catalog:stage-1c', ['file' => $file, '--delimiter' => ';'])->assertSuccessful();

        $run = ImportRun::query()->sole();
        $this->assertSame('needs_review', $run->status);

        $conflict = DuplicateConflict::query()->sole();
        $this->assertSame('mpn:mpn-200', $conflict->match_key);
        $this->assertSame([$existing->id], $conflict->candidate_ids['product_ids']);

        $this->assertDatabaseHas('staged_import_records', [
            'import_run_id' => $run->id,
            'external_id' => '1c-real',
            'status' => 'duplicate',
        ]);
    }

    public function test_publishing_a_known_external_id_updates_the_existing_product_and_reuses_the_existing_site_product(): void
    {
        $site = $this->site();

        $product = Product::create([
            'external_id' => '1c-alpha',
            'sku' => 'ALPHA-OLD',
            'slug' => 'alpha-battery',
            'name' => 'Alpha Battery (old name)',
            'status' => 'active',
        ]);

        $siteProduct = SiteProduct::create([
            'site_id' => $site->id,
            'product_id' => $product->id,
            'slug' => 'alpha-battery',
            'is_published' => true,
            'availability' => 'in_stock',
        ]);

        $record = $this->stagedRecordFor('1c-alpha', 'Alpha Battery (updated)', 'ALPHA-NEW');

        $publisher = app(StagedProductPublisher::class);
        $publisher->review($record, null);
        $published = $publisher->publishToSite($record, $site, null);

        $this->assertSame('published', $published->status);
        $this->assertDatabaseCount('products', 1);
        $this->assertDatabaseHas('products', [
            'id' => $product->id,
            'external_id' => '1c-alpha',
            'sku' => 'ALPHA-NEW',
            'name' => 'Alpha Battery (updated)',
        ]);

        // The pre-existing site_product row must be reused, not duplicated, and its
        // publication state must be left untouched by firstOrCreate's non-create path.
        $this->assertDatabaseCount('site_products', 1);
        $this->assertDatabaseHas('site_products', [
            'id' => $siteProduct->id,
            'is_published' => true,
            'availability' => 'in_stock',
        ]);

        $snapshot = $published->publication_snapshot;
        $this->assertNotNull($snapshot['product_before']);
        $this->assertSame('ALPHA-OLD', $snapshot['product_before']['sku']);
        $this->assertSame('Alpha Battery (old name)', $snapshot['product_before']['name']);
        $this->assertSame('ALPHA-NEW', $snapshot['product_after']['sku']);
    }

    private function stagedRecordFor(string $externalId, string $name, string $sku): StagedImportRecord
    {
        $run = ImportRun::create(['source' => '1c_csv', 'status' => 'ready_for_review']);

        return StagedImportRecord::create([
            'import_run_id' => $run->id,
            'row_number' => 2,
            'entity_type' => 'product',
            'external_id' => $externalId,
            'payload' => [
                'external_id' => $externalId,
                'name' => $name,
                'sku' => $sku,
            ],
            'normalized_payload' => [
                'external_id' => $externalId,
                'name' => $name,
                'sku' => $sku,
                'slug' => 'alpha-battery',
            ],
            'validation_errors' => [],
            'status' => 'ready_for_review',
        ]);
    }

    private function site(): Site
    {
        return Site::create([
            'key' => 'microchips-by',
            'domain' => 'microchips.by',
            'country_code' => 'BY',
            'currency_code' => 'BYN',
            'default_locale' => 'ru-BY',
            'name' => 'Microchips Belarus',
            'is_active' => true,
        ]);
    }

    private function csvFile(string $contents, string $name): string
    {
        $directory = storage_path('framework/testing');
        if (! is_dir($directory)) {
            mkdir($directory, 0777, true);
        }

        $file = $directory.'/'.$name;
        file_put_contents($file, $contents);

        return $file;
    }
}
