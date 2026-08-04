<?php

namespace Tests\Feature;

use App\Domain\Imports\StagedProductPublisher;
use App\Models\DuplicateConflict;
use App\Models\ImportRun;
use App\Models\Site;
use App\Models\StagedImportRecord;
use App\Models\User;
use DomainException;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class CatalogImportReviewWorkflowTest extends TestCase
{
    use RefreshDatabase;

    public function test_csv_records_are_normalized_validated_and_duplicate_rows_are_blocked(): void
    {
        $file = $this->csvFile(<<<'CSV'
external_id;name;sku;mpn;voltage
1c-alpha;Alpha Battery;ALPHA-01;;12V
1c-beta;Beta Battery;ALPHA-01;;12V
1c-invalid;;;MPN-3;
CSV);

        $this->artisan('catalog:stage-1c', ['file' => $file, '--delimiter' => ';'])->assertSuccessful();

        $run = ImportRun::query()->sole();
        $this->assertSame('needs_review', $run->status);
        $this->assertSame(1, $run->summary['duplicate_conflicts']);
        $this->assertSame(1, $run->summary['invalid']);

        $this->assertDatabaseHas('staged_import_records', [
            'import_run_id' => $run->id,
            'external_id' => '1c-alpha',
            'status' => 'duplicate',
        ]);
        $this->assertDatabaseHas('staged_import_records', [
            'import_run_id' => $run->id,
            'external_id' => '1c-invalid',
            'status' => 'invalid',
        ]);

        $conflict = DuplicateConflict::query()->sole();
        $this->assertSame('identifier:alpha01', $conflict->match_key);
        $this->assertCount(2, $conflict->candidate_ids['staged_record_ids']);
        $this->assertSame([], $conflict->candidate_ids['product_ids']);
    }

    public function test_a_record_must_be_reviewed_before_it_can_be_added_to_a_chosen_site(): void
    {
        $record = $this->validRecord();
        $site = $this->site();
        $reviewer = User::factory()->create(['is_admin' => true]);
        $publisher = app(StagedProductPublisher::class);

        try {
            $publisher->publishToSite($record, $site, $reviewer);
            $this->fail('A record must not publish before explicit review.');
        } catch (DomainException $exception) {
            $this->assertStringContainsString('explicitly reviewed', $exception->getMessage());
        }

        $publisher->review($record, $reviewer, 'Identifiers checked against source export.');
        $published = $publisher->publishToSite($record, $site, $reviewer);

        $this->assertSame('published', $published->status);
        $this->assertSame($site->id, $published->published_site_id);
        $this->assertSame($reviewer->id, $published->reviewed_by);
        $this->assertSame($reviewer->id, $published->published_by);
        $this->assertFalse($published->publication_snapshot['publicly_visible']);
        $this->assertDatabaseHas('products', [
            'external_id' => '1c-alpha',
            'sku' => 'ALPHA-01',
            'name' => 'Alpha Battery',
            'status' => 'active',
        ]);
        $this->assertDatabaseHas('site_products', [
            'site_id' => $site->id,
            'is_published' => false,
            'availability' => 'on_request',
        ]);
    }

    public function test_an_open_duplicate_conflict_blocks_review_and_publication(): void
    {
        $record = $this->validRecord();
        DuplicateConflict::create([
            'import_run_id' => $record->import_run_id,
            'entity_type' => 'product',
            'match_key' => 'sku:alpha-01',
            'candidate_ids' => ['staged_record_ids' => [$record->id], 'product_ids' => []],
        ]);

        $this->expectException(DomainException::class);
        $this->expectExceptionMessage('Resolve the duplicate conflict');

        app(StagedProductPublisher::class)->review($record, null);
    }

    public function test_publication_revalidates_immutable_source_payload_before_writing_catalog_data(): void
    {
        $record = $this->validRecord();
        $publisher = app(StagedProductPublisher::class);
        $publisher->review($record, null);
        $record->update(['payload' => ['external_id' => '1c-alpha', 'name' => '', 'sku' => 'ALPHA-01']]);

        try {
            $publisher->publishToSite($record, $this->site(), null);
            $this->fail('The modified invalid payload must not be published.');
        } catch (DomainException $exception) {
            $this->assertStringContainsString('no longer passes validation', $exception->getMessage());
        }

        $this->assertDatabaseHas('staged_import_records', [
            'id' => $record->id,
            'status' => 'invalid',
        ]);
        $this->assertDatabaseCount('products', 0);
        $this->assertDatabaseCount('site_products', 0);
    }

    private function validRecord(): StagedImportRecord
    {
        $run = ImportRun::create(['source' => '1c_csv', 'status' => 'ready_for_review']);

        return StagedImportRecord::create([
            'import_run_id' => $run->id,
            'row_number' => 2,
            'entity_type' => 'product',
            'external_id' => '1c-alpha',
            'payload' => [
                'external_id' => '1c-alpha',
                'name' => 'Alpha Battery',
                'sku' => 'ALPHA-01',
                'voltage' => '12V',
            ],
            'normalized_payload' => [
                'external_id' => '1c-alpha',
                'name' => 'Alpha Battery',
                'sku' => 'ALPHA-01',
                'slug' => 'alpha-battery',
                'technical_attributes' => ['voltage' => '12V'],
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

    private function csvFile(string $contents): string
    {
        $directory = storage_path('framework/testing');
        if (! is_dir($directory)) {
            mkdir($directory, 0777, true);
        }

        $file = $directory.'/catalog-import.csv';
        file_put_contents($file, $contents);

        return $file;
    }
}
