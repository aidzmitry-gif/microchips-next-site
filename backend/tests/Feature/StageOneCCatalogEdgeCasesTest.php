<?php

namespace Tests\Feature;

use App\Domain\Imports\StageProductValidator;
use App\Models\DuplicateConflict;
use App\Models\ImportRun;
use App\Models\Product;
use App\Models\StagedImportRecord;
use Illuminate\Foundation\Testing\RefreshDatabase;
use RuntimeException;
use Tests\TestCase;

class StageOneCCatalogEdgeCasesTest extends TestCase
{
    use RefreshDatabase;

    public function test_a_missing_file_fails_without_creating_an_import_run(): void
    {
        $missing = storage_path('framework/testing/does-not-exist-'.uniqid('', true).'.csv');

        $this->artisan('catalog:stage-1c', ['file' => $missing])
            ->assertFailed();

        $this->assertDatabaseCount('import_runs', 0);
    }

    public function test_a_multi_character_delimiter_fails_without_creating_an_import_run(): void
    {
        $file = $this->csvFile(<<<'CSV'
external_id;name;sku
1c-alpha;Alpha Battery;ALPHA-01
CSV, 'multi-delimiter.csv');

        $this->artisan('catalog:stage-1c', ['file' => $file, '--delimiter' => ';;'])
            ->assertFailed();

        $this->assertDatabaseCount('import_runs', 0);
    }

    public function test_a_csv_file_without_a_header_row_marks_the_import_run_as_failed(): void
    {
        $file = $this->csvFile('', 'empty.csv');

        try {
            $this->artisan('catalog:stage-1c', ['file' => $file, '--delimiter' => ';'])->run();
            $this->fail('Expected a RuntimeException for a headerless CSV file.');
        } catch (RuntimeException $exception) {
            $this->assertStringContainsString('does not contain a header row', $exception->getMessage());
        }

        $run = ImportRun::query()->sole();
        $this->assertSame('failed', $run->status);
        $this->assertStringContainsString('does not contain a header row', $run->summary['error']);
        $this->assertNotNull($run->finished_at);
    }

    public function test_a_row_with_more_columns_than_the_header_is_recorded_as_an_invalid_row(): void
    {
        $file = $this->csvFile(<<<'CSV'
external_id;name;sku
1c-delta;Delta Battery;DELTA-01;unexpected-extra-column
CSV, 'ragged-row.csv');

        $this->artisan('catalog:stage-1c', ['file' => $file, '--delimiter' => ';'])->assertSuccessful();

        $run = ImportRun::query()->sole();
        $this->assertSame('ready_for_review', $run->status);
        $this->assertSame(1, $run->failed_records);

        $this->assertDatabaseHas('staged_import_records', [
            'import_run_id' => $run->id,
            'row_number' => 2,
            'status' => 'invalid',
        ]);
    }

    public function test_a_sku_collision_with_an_existing_product_is_recorded_as_a_duplicate_conflict(): void
    {
        $existing = Product::create([
            'external_id' => null,
            'sku' => 'GAMMA-01',
            'slug' => 'gamma-battery-existing',
            'name' => 'Gamma Battery (existing)',
            'status' => 'active',
        ]);

        $file = $this->csvFile(<<<'CSV'
external_id;name;sku;voltage
1c-gamma;Gamma Battery;GAMMA-01;12V
CSV, 'sku-collision.csv');

        $this->artisan('catalog:stage-1c', ['file' => $file, '--delimiter' => ';'])->assertSuccessful();

        $run = ImportRun::query()->sole();
        $this->assertSame('needs_review', $run->status);
        $this->assertSame(1, $run->summary['duplicate_conflicts']);

        $conflict = DuplicateConflict::query()->sole();
        $this->assertSame('sku:gamma-01', $conflict->match_key);
        $this->assertSame([$existing->id], $conflict->candidate_ids['product_ids']);

        $this->assertDatabaseHas('staged_import_records', [
            'import_run_id' => $run->id,
            'external_id' => '1c-gamma',
            'status' => 'duplicate',
        ]);
    }

    public function test_an_exception_while_staging_rows_marks_the_import_run_as_failed(): void
    {
        $this->app->bind(StageProductValidator::class, function () {
            return new class extends StageProductValidator
            {
                public function normalizeAndValidate(array $payload): array
                {
                    throw new RuntimeException('Simulated staging failure.');
                }
            };
        });

        $file = $this->csvFile(<<<'CSV'
external_id;name;sku
1c-epsilon;Epsilon Battery;EPSILON-01
CSV, 'exploding-validator.csv');

        try {
            $this->artisan('catalog:stage-1c', ['file' => $file, '--delimiter' => ';'])->run();
            $this->fail('Expected the simulated validator exception to propagate.');
        } catch (RuntimeException $exception) {
            $this->assertSame('Simulated staging failure.', $exception->getMessage());
        }

        $run = ImportRun::query()->sole();
        $this->assertSame('failed', $run->status);
        $this->assertSame('Simulated staging failure.', $run->summary['error']);
        $this->assertNotNull($run->finished_at);
        $this->assertDatabaseCount('staged_import_records', 0);
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
