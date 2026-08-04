<?php

namespace Tests\Feature;

use App\Events\SiteContentChanged;
use App\Models\Site;
use App\Models\SiteRedirect;
use App\Models\SiteUrl;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Artisan;
use Illuminate\Support\Facades\Event;
use Tests\TestCase;

class NormalizeBitrixLegacyRedirectPathsTest extends TestCase
{
    use RefreshDatabase;

    public function test_it_dry_runs_then_atomically_normalizes_the_guarded_redirects(): void
    {
        $site = $this->site();
        $first = $this->redirect($site, '/catalog/akkumulyatory/dlya_ibp/100/', '/catalog/batteries-ups/legacy-bitrix-100');
        $second = $this->redirect($site, '/catalog/akkumulyatory/dlya_ibp/101/', '/catalog/batteries-ups/product-101', SiteRedirect::PURPOSE_SEO);
        Event::fake([SiteContentChanged::class]);

        $exitCode = Artisan::call('catalog:normalize-bitrix-legacy-redirect-paths', [
            'site' => $site->key,
            '--expected-redirects' => 2,
        ]);
        $output = Artisan::output();
        $this->assertSame(0, $exitCode, $output);

        $this->assertSame('/catalog/akkumulyatory/dlya_ibp/100/', $first->fresh()->source_path);
        $this->assertSame('/catalog/akkumulyatory/dlya_ibp/101/', $second->fresh()->source_path);
        Event::assertNotDispatched(SiteContentChanged::class);

        $this->artisan('catalog:normalize-bitrix-legacy-redirect-paths', [
            'site' => $site->key,
            '--expected-redirects' => 2,
            '--apply' => true,
        ])->assertSuccessful();

        $this->assertSame('/catalog/akkumulyatory/dlya_ibp/100', $first->fresh()->source_path);
        $this->assertSame('/catalog/akkumulyatory/dlya_ibp/101', $second->fresh()->source_path);
        Event::assertDispatchedTimes(SiteContentChanged::class, 1);
        Event::assertDispatched(SiteContentChanged::class, fn (SiteContentChanged $event): bool => $event->site->is($site)
            && $event->paths === ['/catalog', '/sitemap.xml']
        );
    }

    public function test_an_apply_rerun_is_idempotent_and_reports_every_redirect_unchanged(): void
    {
        $site = $this->site();
        $this->redirect($site, '/catalog/akkumulyatory/dlya_ibp/100', '/catalog/batteries-ups/legacy-bitrix-100');
        $this->redirect($site, '/catalog/akkumulyatory/dlya_ibp/101', '/catalog/batteries-ups/legacy-bitrix-101');
        Event::fake([SiteContentChanged::class]);

        $this->artisan('catalog:normalize-bitrix-legacy-redirect-paths', [
            'site' => $site->key,
            '--expected-redirects' => 2,
            '--apply' => true,
        ])->assertSuccessful();

        Event::assertNotDispatched(SiteContentChanged::class);
    }

    public function test_it_fails_closed_on_count_site_url_and_other_redirect_source_drift(): void
    {
        $site = $this->site();
        $redirect = $this->redirect($site, '/catalog/akkumulyatory/dlya_ibp/100/', '/catalog/batteries-ups/legacy-bitrix-100');

        $this->artisan('catalog:normalize-bitrix-legacy-redirect-paths', [
            'site' => $site->key,
            '--expected-redirects' => 2,
            '--apply' => true,
        ])->expectsOutputToContain('Expected exactly 2')->assertFailed();
        $this->assertSame('/catalog/akkumulyatory/dlya_ibp/100/', $redirect->fresh()->source_path);

        SiteUrl::create([
            'site_id' => $site->id,
            'path' => '/catalog/akkumulyatory/dlya_ibp/100',
            'locale' => $site->default_locale,
            'target_type' => 'page',
            'target_id' => 1,
            'is_indexable' => false,
        ]);
        $this->artisan('catalog:normalize-bitrix-legacy-redirect-paths', [
            'site' => $site->key,
            '--expected-redirects' => 1,
            '--apply' => true,
        ])->expectsOutputToContain('conflicts with an active site URL')->assertFailed();
        $this->assertSame('/catalog/akkumulyatory/dlya_ibp/100/', $redirect->fresh()->source_path);

        SiteUrl::query()->delete();
        $this->redirect($site, '/catalog/akkumulyatory/dlya_ibp/100', '/catalog/batteries-ups/other-target');
        $this->artisan('catalog:normalize-bitrix-legacy-redirect-paths', [
            'site' => $site->key,
            '--expected-redirects' => 2,
            '--apply' => true,
        ])->expectsOutputToContain('conflicts with another redirect source')->assertFailed();
        $this->assertSame('/catalog/akkumulyatory/dlya_ibp/100/', $redirect->fresh()->source_path);
    }

    public function test_it_fails_closed_on_redirect_contract_or_target_path_drift(): void
    {
        $site = $this->site();
        $redirect = $this->redirect($site, '/catalog/akkumulyatory/dlya_ibp/100/', '/catalog/batteries-ups/legacy-bitrix-100');

        $redirect->update(['status_code' => 302]);
        $this->artisan('catalog:normalize-bitrix-legacy-redirect-paths', [
            'site' => $site->key,
            '--expected-redirects' => 1,
            '--apply' => true,
        ])->expectsOutputToContain('must be active 301')->assertFailed();

        $redirect->update(['status_code' => 301, 'target_path' => '/catalog/batteries-ups/legacy-bitrix-100/']);
        $this->artisan('catalog:normalize-bitrix-legacy-redirect-paths', [
            'site' => $site->key,
            '--expected-redirects' => 1,
            '--apply' => true,
        ])->expectsOutputToContain('is not normalized')->assertFailed();

        $redirect->update(['target_path' => 'https://example.test/catalog/product']);
        $this->artisan('catalog:normalize-bitrix-legacy-redirect-paths', [
            'site' => $site->key,
            '--expected-redirects' => 1,
            '--apply' => true,
        ])->expectsOutputToContain('Unsafe local target path')->assertFailed();

        $this->assertSame('/catalog/akkumulyatory/dlya_ibp/100/', $redirect->fresh()->source_path);
    }

    public function test_it_rejects_any_site_other_than_the_exact_production_identity(): void
    {
        $site = $this->site('preview.microchips.by');

        $this->artisan('catalog:normalize-bitrix-legacy-redirect-paths', [
            'site' => $site->key,
            '--expected-redirects' => 1,
        ])->expectsOutputToContain('requires the exact microchips-by site on microchips.by')->assertFailed();
    }

    private function site(string $domain = 'microchips.by'): Site
    {
        return Site::create([
            'key' => 'microchips-by',
            'domain' => $domain,
            'country_code' => 'BY',
            'currency_code' => 'BYN',
            'default_locale' => 'ru-BY',
            'name' => 'RB',
            'is_active' => true,
        ]);
    }

    private function redirect(
        Site $site,
        string $sourcePath,
        string $targetPath,
        string $purpose = SiteRedirect::PURPOSE_PREVIEW,
    ): SiteRedirect {
        return SiteRedirect::create([
            'site_id' => $site->id,
            'source_path' => $sourcePath,
            'target_path' => $targetPath,
            'status_code' => 301,
            'purpose' => $purpose,
            'is_active' => true,
        ]);
    }
}
