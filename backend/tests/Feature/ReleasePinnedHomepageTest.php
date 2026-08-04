<?php

namespace Tests\Feature;

use App\Models\ImportRun;
use App\Models\Product;
use App\Models\Site;
use App\Models\SiteCommercialFact;
use App\Models\SiteContact;
use App\Models\SitePage;
use App\Models\SiteProduct;
use App\Models\SiteSeo;
use App\Models\SiteUrl;
use App\Models\StagedImportRecord;
use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class ReleasePinnedHomepageTest extends TestCase
{
    use RefreshDatabase;

    private array $temporaryFiles = [];

    protected function tearDown(): void
    {
        foreach ($this->temporaryFiles as $file) {
            if (is_file($file)) {
                unlink($file);
            }
        }
        parent::tearDown();
    }

    public function test_default_mode_runs_the_real_release_path_but_persists_nothing(): void
    {
        [$site, $url, $page, $seo] = $this->rootFixture();
        $this->verifiedProfile($site);
        $manifest = $this->releaseManifest($url, $page, $seo);
        $file = $this->writeManifest($manifest);
        $before = $this->rootState($url, $page, $seo);

        $this->artisan('seo:release-homepage', ['site' => $site->key, 'file' => $file])
            ->expectsOutputToContain('"mode": "dry_run"')
            ->assertSuccessful();

        $this->assertSame($before, $this->rootState($url->fresh(), $page->fresh(), $seo->fresh()));
        $this->assertDatabaseCount('import_runs', 0);
        $this->assertDatabaseCount('staged_import_records', 0);
        $this->assertFileDoesNotExist($this->defaultRollbackPath($file));
    }

    public function test_apply_updates_only_the_existing_root_and_records_an_atomic_audit_and_rollback_manifest(): void
    {
        [$site, $url, $page, $seo] = $this->rootFixture();
        $this->verifiedProfile($site);
        $product = Product::create(['external_id' => 'UNCHANGED-1', 'slug' => 'unchanged-1', 'name' => 'Unchanged product', 'status' => 'active']);
        $siteProduct = SiteProduct::create([
            'site_id' => $site->id, 'product_id' => $product->id, 'slug' => 'unchanged-1',
            'is_published' => true, 'availability' => 'on_request',
        ]);
        $productBefore = $product->fresh()->toArray();
        $siteProductBefore = $siteProduct->fresh()->toArray();
        $contactsBefore = SiteContact::query()->where('site_id', $site->id)->orderBy('id')->get()->toArray();
        $factsBefore = SiteCommercialFact::query()->where('site_id', $site->id)->orderBy('id')->get()->toArray();
        $file = $this->writeManifest($this->releaseManifest($url, $page, $seo));
        $rollback = $this->temporaryPath('homepage.rollback.json');

        $this->artisan('seo:release-homepage', [
            'site' => $site->key, 'file' => $file, '--apply' => true, '--rollback-output' => $rollback,
        ])->expectsOutputToContain('"mode": "apply"')->assertSuccessful();

        $expected = $this->baseReleaseManifest()['homepage'];
        $this->assertTrue($url->fresh()->is_indexable);
        $this->assertTrue($seo->fresh()->is_indexable);
        $this->assertSame('/', $seo->fresh()->canonical_path);
        $this->assertSame($expected['title'], $page->fresh()->title);
        $this->assertSame($expected['h1'], $page->fresh()->h1);
        $this->assertSame($expected['content'], $page->fresh()->content);
        $this->assertSame($expected['seo_title'], $seo->fresh()->title);
        $this->assertSame($expected['seo_description'], $seo->fresh()->description);
        $this->assertSame($expected['schema'], $seo->fresh()->schema);
        $this->assertFileExists($rollback);
        $rollbackData = json_decode((string) file_get_contents($rollback), true, 512, JSON_THROW_ON_ERROR);
        $this->assertSame('rb_homepage_rollback_v1', $rollbackData['schema']);
        $this->assertFalse($rollbackData['restore']['url']['is_indexable']);
        $this->assertFalse($rollbackData['restore']['seo']['is_indexable']);

        $run = ImportRun::query()->sole();
        $record = StagedImportRecord::query()->sole();
        $this->assertSame('seo_homepage_release:microchips-by', $run->source);
        $this->assertSame('homepage_indexability_release', $record->entity_type);
        $this->assertSame('released_indexable', $record->status);
        $this->assertTrue($record->normalized_payload['is_indexable']);
        $this->assertSame($productBefore, $product->fresh()->toArray());
        $this->assertSame($siteProductBefore, $siteProduct->fresh()->toArray());
        $this->assertSame($contactsBefore, SiteContact::query()->where('site_id', $site->id)->orderBy('id')->get()->toArray());
        $this->assertSame($factsBefore, SiteCommercialFact::query()->where('site_id', $site->id)->orderBy('id')->get()->toArray());
    }

    public function test_before_state_drift_fails_closed_without_partial_content_or_audit(): void
    {
        [$site, $url, $page, $seo] = $this->rootFixture();
        $this->verifiedProfile($site);
        $file = $this->writeManifest($this->releaseManifest($url, $page, $seo));
        $page->update(['h1' => 'Concurrent edit']);

        $this->artisan('seo:release-homepage', ['site' => $site->key, 'file' => $file, '--apply' => true])
            ->expectsOutputToContain('changed after the manifest was approved')
            ->assertFailed();

        $this->assertSame('Concurrent edit', $page->fresh()->h1);
        $this->assertFalse($url->fresh()->is_indexable);
        $this->assertFalse($seo->fresh()->is_indexable);
        $this->assertDatabaseCount('import_runs', 0);
    }

    public function test_demo_or_placeholder_release_content_is_rejected(): void
    {
        [$site, $url, $page, $seo] = $this->rootFixture();
        $this->verifiedProfile($site);
        $manifest = $this->releaseManifest($url, $page, $seo);
        $manifest['homepage']['content'] .= ' Placeholder for later.';
        $file = $this->writeManifest($manifest);

        $this->artisan('seo:release-homepage', ['site' => $site->key, 'file' => $file, '--apply' => true])
            ->expectsOutputToContain('contains a demo, placeholder, draft, or migration marker')
            ->assertFailed();

        $this->assertSame('Demo content to replace.', $page->fresh()->content);
        $this->assertFalse($url->fresh()->is_indexable);
        $this->assertDatabaseCount('import_runs', 0);
    }

    public function test_release_rejects_a_manifest_fact_not_backed_by_the_verified_owner_profile(): void
    {
        [$site, $url, $page, $seo] = $this->rootFixture();
        $this->verifiedProfile($site);
        SiteContact::query()->where('site_id', $site->id)->where('label', 'Самовывоз')->delete();
        $file = $this->writeManifest($this->releaseManifest($url, $page, $seo));

        $this->artisan('seo:release-homepage', ['site' => $site->key, 'file' => $file, '--apply' => true])
            ->expectsOutputToContain('Verified owner-approved contact is missing: Самовывоз')
            ->assertFailed();

        $this->assertFalse($url->fresh()->is_indexable);
        $this->assertDatabaseCount('import_runs', 0);
    }

    public function test_generated_manifest_restores_the_exact_noindex_root_and_records_rollback(): void
    {
        [$site, $url, $page, $seo] = $this->rootFixture();
        $this->verifiedProfile($site);
        $before = $this->rootState($url, $page, $seo);
        $file = $this->writeManifest($this->releaseManifest($url, $page, $seo));
        $rollback = $this->temporaryPath('homepage.rollback.json');
        $this->artisan('seo:release-homepage', [
            'site' => $site->key, 'file' => $file, '--apply' => true, '--rollback-output' => $rollback,
        ])->assertSuccessful();

        $this->artisan('seo:release-homepage', [
            'site' => $site->key, 'file' => $rollback, '--rollback' => true, '--apply' => true,
        ])->expectsOutputToContain('"operation": "rollback_homepage"')->assertSuccessful();

        $this->assertSame($before, $this->rootState($url->fresh(), $page->fresh(), $seo->fresh()));
        $this->assertDatabaseCount('import_runs', 2);
        $this->assertSame(['released_indexable', 'restored_noindex'], StagedImportRecord::query()->orderBy('id')->pluck('status')->all());
    }

    public function test_tampered_rollback_restore_state_is_rejected_without_touching_the_released_root(): void
    {
        [$site, $url, $page, $seo] = $this->rootFixture();
        $this->verifiedProfile($site);
        $file = $this->writeManifest($this->releaseManifest($url, $page, $seo));
        $rollback = $this->temporaryPath('homepage.rollback.json');
        $this->artisan('seo:release-homepage', [
            'site' => $site->key, 'file' => $file, '--apply' => true, '--rollback-output' => $rollback,
        ])->assertSuccessful();
        $releasedTitle = $page->fresh()->title;

        $tampered = json_decode((string) file_get_contents($rollback), true, 512, JSON_THROW_ON_ERROR);
        $tampered['restore']['page']['title'] = 'Injected rollback title';
        file_put_contents($rollback, json_encode($tampered, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR));

        $this->artisan('seo:release-homepage', [
            'site' => $site->key, 'file' => $rollback, '--rollback' => true, '--apply' => true,
        ])->expectsOutputToContain('Rollback restore-state changed after the manifest was approved')->assertFailed();

        $this->assertTrue($url->fresh()->is_indexable);
        $this->assertTrue($seo->fresh()->is_indexable);
        $this->assertSame($releasedTitle, $page->fresh()->title);
        $this->assertDatabaseCount('import_runs', 1);
    }

    /** @return array{Site, SiteUrl, SitePage, SiteSeo} */
    private function rootFixture(): array
    {
        $site = Site::create([
            'key' => 'microchips-by', 'domain' => 'microchips.by', 'country_code' => 'BY', 'currency_code' => 'BYN',
            'default_locale' => 'ru-BY', 'name' => 'Microchips Беларусь', 'is_active' => true,
        ]);
        $site->locales()->create(['locale' => 'ru-BY', 'language' => 'ru', 'is_default' => true, 'is_enabled' => true]);
        $page = SitePage::create([
            'site_id' => $site->id, 'locale' => 'ru-BY', 'slug' => 'home', 'title' => 'Old title',
            'h1' => 'Old H1', 'content' => 'Demo content to replace.', 'is_published' => true,
        ]);
        $url = SiteUrl::create([
            'site_id' => $site->id, 'path' => '/', 'locale' => 'ru-BY', 'target_type' => 'page',
            'target_id' => $page->id, 'is_indexable' => false,
        ]);
        $seo = SiteSeo::create([
            'site_id' => $site->id, 'locale' => 'ru-BY', 'resource_type' => 'page', 'resource_id' => $page->id,
            'canonical_path' => '/', 'title' => 'Old title', 'description' => null, 'is_indexable' => false, 'schema' => null,
        ]);

        return [$site, $url, $page, $seo];
    }

    private function verifiedProfile(Site $site): void
    {
        $operator = User::factory()->create(['is_admin' => true]);
        $approval = $this->baseReleaseManifest()['owner_approval'];
        $contacts = [
            ['legal_entity', 'Юридическое лицо', $approval['legal_name'].', УНП '.$approval['unp']],
            ['address', 'Юридический адрес', $approval['legal_address']],
            ['address', 'Самовывоз', $approval['pickup_address']],
            ['phone', 'Основной телефон', $approval['phones'][0]],
            ['phone', 'Городской телефон', $approval['phones'][1]],
            ['email', 'E-mail', $approval['email']],
            ['working_hours', 'Режим работы', $approval['working_hours']],
        ];
        foreach ($contacts as [$type, $label, $value]) {
            SiteContact::create([
                'site_id' => $site->id, 'locale' => 'ru-BY', 'type' => $type, 'label' => $label, 'value' => $value,
                'is_published' => true, 'verified_at' => now(), 'verified_by' => $operator->id,
                'verification_note' => 'Owner-approved test pin.',
            ]);
        }
        foreach ([
            'legal_name' => $approval['legal_name'].', УНП '.$approval['unp'],
            'legal_address' => $approval['legal_address'],
            'delivery_terms' => 'Verified delivery terms.',
            'payment_terms' => 'Verified payment terms.',
            'warranty_terms' => 'Verified warranty terms.',
        ] as $key => $value) {
            SiteCommercialFact::create([
                'site_id' => $site->id, 'locale' => 'ru-BY', 'key' => $key, 'value' => $value,
                'is_published' => true, 'verified_at' => now(), 'verified_by' => $operator->id,
                'verification_note' => 'Owner-approved test pin.',
            ]);
        }
    }

    /** @return array<string, mixed> */
    private function releaseManifest(SiteUrl $url, SitePage $page, SiteSeo $seo): array
    {
        $manifest = $this->baseReleaseManifest();
        $manifest['expected_before_sha256'] = $this->hashState($this->rootState($url, $page, $seo));

        return $manifest;
    }

    /** @return array<string, mixed> */
    private function baseReleaseManifest(): array
    {
        return json_decode(
            (string) file_get_contents(base_path('../docs/imports/rb-homepage-release-v1.json')),
            true,
            512,
            JSON_THROW_ON_ERROR,
        );
    }

    private function writeManifest(array $manifest): string
    {
        $file = $this->temporaryPath('homepage.release.json');
        file_put_contents($file, json_encode($manifest, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR));

        return $file;
    }

    private function temporaryPath(string $suffix): string
    {
        $file = storage_path('framework/testing/'.uniqid('rb-homepage-', true).'-'.$suffix);
        $this->temporaryFiles[] = $file;

        return $file;
    }

    private function defaultRollbackPath(string $file): string
    {
        return (preg_replace('/\.json$/i', '', $file) ?: $file).'.rollback.json';
    }

    /** @return array<string, mixed> */
    private function rootState(SiteUrl $url, SitePage $page, SiteSeo $seo): array
    {
        return [
            'url' => $url->only(['id', 'site_id', 'path', 'locale', 'target_type', 'target_id', 'is_indexable']),
            'page' => $page->only(['id', 'site_id', 'locale', 'slug', 'title', 'h1', 'content', 'is_published']),
            'seo' => $seo->only(['id', 'site_id', 'locale', 'resource_type', 'resource_id', 'canonical_path', 'title', 'description', 'is_indexable', 'schema']),
        ];
    }

    private function hashState(array $state): string
    {
        return hash('sha256', json_encode($this->canonicalize($state), JSON_THROW_ON_ERROR | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES));
    }

    private function canonicalize(mixed $value): mixed
    {
        if (! is_array($value)) {
            return $value;
        }
        if (! array_is_list($value)) {
            ksort($value);
        }
        foreach ($value as $key => $child) {
            $value[$key] = $this->canonicalize($child);
        }

        return $value;
    }
}
