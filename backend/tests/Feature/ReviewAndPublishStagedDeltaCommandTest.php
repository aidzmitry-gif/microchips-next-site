<?php

namespace Tests\Feature;

use App\Models\ImportRun;
use App\Models\Site;
use App\Models\StagedImportRecord;
use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class ReviewAndPublishStagedDeltaCommandTest extends TestCase
{
    use RefreshDatabase;

    public function test_it_requires_an_exact_expected_count_before_it_changes_a_delta(): void
    {
        $this->site();
        User::factory()->create(['is_admin' => true]);
        $run = $this->runWithRecords(2);

        $this->artisan('catalog:review-publish-staged-delta', [
            'site' => 'microchips-by',
            'run' => $run->id,
            '--expected-count' => 1,
        ])->assertFailed();

        $this->assertDatabaseCount('products', 0);
        $this->assertDatabaseHas('staged_import_records', ['import_run_id' => $run->id, 'status' => 'ready_for_review']);
    }

    public function test_it_creates_non_public_site_drafts_only_after_a_bounded_apply(): void
    {
        $site = $this->site();
        User::factory()->create(['is_admin' => true]);
        $run = $this->runWithRecords(2);

        $arguments = [
            'site' => $site->key,
            'run' => $run->id,
            '--expected-count' => 2,
        ];

        $this->artisan('catalog:review-publish-staged-delta', $arguments)->assertSuccessful();
        $this->assertDatabaseCount('products', 0);

        $this->artisan('catalog:review-publish-staged-delta', [...$arguments, '--apply' => true])->assertSuccessful();

        $this->assertDatabaseCount('products', 2);
        $this->assertDatabaseCount('site_products', 2);
        $this->assertDatabaseMissing('site_products', ['is_published' => true]);
        $this->assertDatabaseCount('staged_import_records', 2);
        $this->assertSame(2, StagedImportRecord::query()->where('import_run_id', $run->id)->where('status', 'published')->count());
    }

    private function runWithRecords(int $count): ImportRun
    {
        $run = ImportRun::create(['source' => '1c_csv', 'status' => 'ready_for_review']);

        foreach (range(1, $count) as $index) {
            StagedImportRecord::create([
                'import_run_id' => $run->id,
                'row_number' => $index + 1,
                'entity_type' => 'product',
                'external_id' => "1c-delta-{$index}",
                'payload' => [
                    'external_id' => "1c-delta-{$index}",
                    'name' => "Delta battery {$index}",
                    'mpn' => "DT-{$index}",
                ],
                'normalized_payload' => [
                    'external_id' => "1c-delta-{$index}",
                    'name' => "Delta battery {$index}",
                    'mpn' => "DT-{$index}",
                    'slug' => "delta-battery-{$index}",
                ],
                'validation_errors' => [],
                'status' => 'ready_for_review',
            ]);
        }

        return $run;
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
}
