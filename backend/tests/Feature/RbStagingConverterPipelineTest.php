<?php

namespace Tests\Feature;

use App\Models\ImportRun;
use App\Models\StagedImportRecord;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

/**
 * End-to-end contract test for the RB manifest -> staging-CSV converter
 * (scripts/build-rb-staging-csv.ps1).
 *
 * The fixture tests/Fixtures/rb-staging-1c.golden.csv is REAL byte-for-byte
 * output of that converter (regenerate by running it on
 * tests/Fixtures/rb-import-manifest-sample.csv). Feeding real converter bytes —
 * not a hand-written CSV — is the point: it is the only way this test can catch
 * a serialization regression such as the UTF-8 BOM that made catalog:stage-1c
 * miss external_id on every row.
 */
class RbStagingConverterPipelineTest extends TestCase
{
    use RefreshDatabase;

    private function goldenPath(): string
    {
        return base_path('tests/Fixtures/rb-staging-1c.golden.csv');
    }

    public function test_converter_output_has_no_bom_and_a_quoted_external_id_header(): void
    {
        $bytes = file_get_contents($this->goldenPath());

        // A UTF-8 BOM here is the exact regression that breaks backend parsing:
        // PHP fgetcsv would read the first header as <BOM>"external_id" and never
        // match the 'external_id' key, failing required-external_id on every row.
        $this->assertStringStartsNotWith("\xEF\xBB\xBF", $bytes, 'Staging CSV must not start with a UTF-8 BOM.');
        $this->assertStringStartsWith('"external_id"', $bytes, 'First header cell must be the quoted external_id.');

        // Unconfirmed name-derived candidates must never reach the staging input.
        $this->assertStringNotContainsString('CAND-SHOULD-NOT-LEAK', $bytes, 'A name-derived candidate leaked into the staging CSV.');
    }

    public function test_converter_output_is_staged_by_catalog_stage_1c(): void
    {
        $this->artisan('catalog:stage-1c', ['file' => $this->goldenPath(), '--delimiter' => ';'])
            ->assertSuccessful();

        $run = ImportRun::query()->sole();
        $this->assertSame('ready_for_review', $run->status);
        $this->assertSame(2, $run->summary['ready_for_review']);
        $this->assertSame(0, $run->summary['invalid']);
        $this->assertSame(0, $run->summary['duplicate_conflicts']);

        // Both business-approved rows stage cleanly, keyed by the 1C external id.
        $this->assertDatabaseHas('staged_import_records', ['external_id' => '1c-A', 'status' => 'ready_for_review']);
        $this->assertDatabaseHas('staged_import_records', ['external_id' => '1c-B', 'status' => 'ready_for_review']);

        // Row A: SKU identifier plus technical attributes taken only from the
        // explicit name text (rule #2) survive normalization intact.
        $a = StagedImportRecord::query()->where('external_id', '1c-A')->sole();
        $this->assertSame('SKU-A', $a->normalized_payload['sku']);
        $this->assertSame('75Ah', $a->normalized_payload['technical_attributes']['capacity']);
        $this->assertSame('AGM', $a->normalized_payload['technical_attributes']['chemistry']);

        // Row B carries an MPN instead of a SKU and still stages.
        $b = StagedImportRecord::query()->where('external_id', '1c-B')->sole();
        $this->assertSame('MPN-B', $b->normalized_payload['mpn']);
        $this->assertArrayNotHasKey('sku', $b->normalized_payload);
    }
}
