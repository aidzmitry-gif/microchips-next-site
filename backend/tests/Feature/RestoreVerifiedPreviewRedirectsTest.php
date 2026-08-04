<?php

namespace Tests\Feature;

use App\Models\Product;
use App\Models\Site;
use App\Models\SiteProduct;
use App\Models\SiteRedirect;
use App\Models\SiteSeo;
use App\Models\SiteUrl;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class RestoreVerifiedPreviewRedirectsTest extends TestCase
{
    use RefreshDatabase;

    public function test_it_dry_runs_applies_and_is_idempotent(): void
    {
        [$site, $target, $file] = $this->fixture();

        try {
            $this->artisan('catalog:restore-verified-preview-redirects', ['site' => $site->key, 'file' => $file])
                ->assertSuccessful();
            $this->assertDatabaseCount('site_redirects', 0);

            $this->artisan('catalog:restore-verified-preview-redirects', ['site' => $site->key, 'file' => $file, '--apply' => true])
                ->assertSuccessful();
            $this->assertDatabaseHas('site_redirects', [
                'site_id' => $site->id,
                'source_path' => '/catalog/legacy-battery',
                'target_path' => '/catalog/verified-battery',
                'status_code' => 301,
                'purpose' => SiteRedirect::PURPOSE_PREVIEW,
                'is_active' => true,
            ]);
            $this->assertDatabaseHas('site_urls', ['id' => $target->id, 'is_indexable' => false]);

            $this->artisan('catalog:restore-verified-preview-redirects', ['site' => $site->key, 'file' => $file, '--apply' => true])
                ->assertSuccessful();
            $this->assertSame(1, SiteRedirect::query()->where('site_id', $site->id)->count());
        } finally {
            @unlink($file);
        }
    }

    public function test_it_fails_closed_when_the_target_route_is_missing(): void
    {
        [$site, $target, $file] = $this->fixture();
        $target->delete();

        try {
            $this->artisan('catalog:restore-verified-preview-redirects', ['site' => $site->key, 'file' => $file, '--apply' => true])
                ->assertFailed();
            $this->assertDatabaseCount('site_redirects', 0);
        } finally {
            @unlink($file);
        }
    }

    public function test_it_fails_closed_when_the_target_route_is_indexable(): void
    {
        [$site, $target, $file] = $this->fixture();
        $target->update(['is_indexable' => true]);

        try {
            $this->artisan('catalog:restore-verified-preview-redirects', ['site' => $site->key, 'file' => $file, '--apply' => true])
                ->assertFailed();
            $this->assertDatabaseCount('site_redirects', 0);
        } finally {
            @unlink($file);
        }
    }

    public function test_it_fails_closed_for_a_conflicting_existing_redirect(): void
    {
        [$site, , $file] = $this->fixture();
        SiteRedirect::create([
            'site_id' => $site->id,
            'source_path' => '/catalog/legacy-battery',
            'target_path' => '/catalog/other-battery',
            'status_code' => 301,
            'purpose' => SiteRedirect::PURPOSE_PREVIEW,
            'is_active' => true,
        ]);

        try {
            $this->artisan('catalog:restore-verified-preview-redirects', ['site' => $site->key, 'file' => $file, '--apply' => true])
                ->assertFailed();
            $this->assertDatabaseHas('site_redirects', ['site_id' => $site->id, 'source_path' => '/catalog/legacy-battery', 'target_path' => '/catalog/other-battery']);
            $this->assertDatabaseMissing('site_redirects', ['site_id' => $site->id, 'source_path' => '/catalog/legacy-battery', 'target_path' => '/catalog/verified-battery']);
        } finally {
            @unlink($file);
        }
    }

    public function test_it_fails_closed_when_restoring_the_redirect_would_create_a_chain(): void
    {
        [$site, , $file] = $this->fixture();
        SiteRedirect::create([
            'site_id' => $site->id,
            'source_path' => '/catalog/verified-battery',
            'target_path' => '/catalog/final-battery',
            'status_code' => 301,
            'purpose' => SiteRedirect::PURPOSE_PREVIEW,
            'is_active' => true,
        ]);

        try {
            $this->artisan('catalog:restore-verified-preview-redirects', ['site' => $site->key, 'file' => $file, '--apply' => true])
                ->assertFailed();
            $this->assertDatabaseMissing('site_redirects', ['site_id' => $site->id, 'source_path' => '/catalog/legacy-battery']);
        } finally {
            @unlink($file);
        }
    }

    public function test_it_fails_closed_when_expected_redirects_does_not_match_the_manifest_rows(): void
    {
        [$site, , $file] = $this->fixture(expectedRedirects: 2);

        try {
            $this->artisan('catalog:restore-verified-preview-redirects', ['site' => $site->key, 'file' => $file, '--apply' => true])
                ->assertFailed();
            $this->assertDatabaseCount('site_redirects', 0);
        } finally {
            @unlink($file);
        }
    }

    /** @return array{Site, SiteUrl, string} */
    private function fixture(int $expectedRedirects = 1): array
    {
        $site = Site::create([
            'key' => 'microchips-by',
            'domain' => 'microchips-by.test',
            'country_code' => 'BY',
            'currency_code' => 'BYN',
            'default_locale' => 'ru-BY',
            'name' => 'RB',
            'is_active' => true,
        ]);
        $product = Product::create([
            'external_id' => 'bitrix:verified-battery',
            'name' => 'Verified battery',
            'slug' => 'verified-battery',
            'status' => 'active',
        ]);
        $siteProduct = SiteProduct::create([
            'site_id' => $site->id,
            'product_id' => $product->id,
            'slug' => 'verified-battery',
            'is_published' => true,
            'availability' => 'on_request',
        ]);
        $target = SiteUrl::create([
            'site_id' => $site->id,
            'path' => '/catalog/verified-battery',
            'locale' => 'ru-BY',
            'target_type' => 'product',
            'target_id' => $siteProduct->id,
            'is_indexable' => false,
        ]);
        SiteSeo::create([
            'site_id' => $site->id,
            'locale' => 'ru-BY',
            'resource_type' => 'product',
            'resource_id' => $siteProduct->id,
            'canonical_path' => '/catalog/verified-battery',
            'is_indexable' => false,
            'schema' => null,
        ]);
        $file = tempnam(sys_get_temp_dir(), 'preview-redirect-recovery-');
        file_put_contents($file, json_encode([
            'schema_version' => 1,
            'site_key' => $site->key,
            'expected_redirects' => $expectedRedirects,
            'redirects' => [[
                'source_path' => '/catalog/legacy-battery',
                'target_path' => '/catalog/verified-battery',
                'target_external_id' => $product->external_id,
                'evidence' => 'reviewed_historical_slug_correction',
            ]],
        ], JSON_THROW_ON_ERROR));

        return [$site, $target, $file];
    }
}
