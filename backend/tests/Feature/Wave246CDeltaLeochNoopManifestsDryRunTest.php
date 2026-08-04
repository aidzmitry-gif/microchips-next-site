<?php

namespace Tests\Feature;

use App\Models\ImportRun;
use App\Models\Site;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class Wave246CDeltaLeochNoopManifestsDryRunTest extends TestCase
{
    use RefreshDatabase;

    public function test_final_no_repeat_manifests_pass_both_real_laravel_dry_runs_without_apply(): void
    {
        $identityPath = base_path('../docs/imports/rb-verified-oem-identities-wave246c-delta-leoch-2026-07-30.json');
        $descriptionPath = base_path('../docs/imports/rb-source-backed-descriptions-wave246c-delta-leoch-2026-07-30.json');
        $identity = json_decode((string) file_get_contents($identityPath), true, 512, JSON_THROW_ON_ERROR);
        $description = json_decode((string) file_get_contents($descriptionPath), true, 512, JSON_THROW_ON_ERROR);

        $this->assertSame([], $identity['products']);
        $this->assertSame([], $description['products']);
        $this->assertSame('active_1c', $identity['target_kind']);
        $this->assertSame('ru-BY', $description['locale']);

        Site::create([
            'key' => 'microchips-by', 'domain' => 'microchips-by.test', 'country_code' => 'BY',
            'currency_code' => 'BYN', 'default_locale' => 'ru-BY', 'name' => 'RB', 'is_active' => true,
        ]);

        $this->artisan('catalog:apply-verified-oem-identities', [
            'site' => 'microchips-by', 'file' => $identityPath,
        ])->expectsOutputToContain('non-empty products list')->assertFailed();
        $this->artisan('content:stage-source-backed-description-drafts', [
            'site' => 'microchips-by', 'file' => $descriptionPath,
        ])->assertSuccessful();

        $this->assertDatabaseCount('products', 0);
        $this->assertDatabaseCount('site_products', 0);
        $this->assertDatabaseCount('product_description_drafts', 0);
        $run = ImportRun::query()->where('source', 'source_backed_description_drafts')->sole();
        $this->assertSame('dry_run_complete', $run->status);
        $this->assertSame(0, $run->total_records);
        $this->assertSame(0, $run->summary['created']);
        $this->assertSame(0, $run->summary['refreshed']);
        $this->assertSame(0, $run->summary['unchanged']);
    }
}
