<?php

namespace Tests\Feature;

use App\Models\Site;
use App\Models\SitePage;
use App\Models\SiteSeo;
use App\Models\SiteUrl;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class PublishCommercialPagesPackageTest extends TestCase
{
    use RefreshDatabase;

    public function test_dry_run_does_not_publish_pages_and_apply_keeps_routes_noindex(): void
    {
        $site = $this->site();
        foreach (['contacts', 'delivery', 'payment', 'warranty'] as $slug) {
            $page = SitePage::create([
                'site_id' => $site->id,
                'locale' => 'ru-BY',
                'slug' => $slug,
                'title' => ucfirst($slug),
                'h1' => ucfirst($slug),
                'content' => 'Reviewed local commercial content.',
                'is_published' => false,
            ]);
            SiteUrl::create(['site_id' => $site->id, 'path' => '/'.$slug, 'locale' => 'ru-BY', 'target_type' => 'page', 'target_id' => $page->id, 'is_indexable' => false]);
            SiteSeo::create(['site_id' => $site->id, 'locale' => 'ru-BY', 'resource_type' => 'page', 'resource_id' => $page->id, 'canonical_path' => '/'.$slug, 'title' => ucfirst($slug), 'description' => 'Reviewed local commercial content.', 'is_indexable' => false]);
        }

        $this->artisan('site:publish-commercial-pages-package', ['site' => $site->key])
            ->expectsOutputToContain('"mode": "dry_run"')
            ->assertSuccessful();
        $this->assertSame(0, SitePage::query()->published()->count());

        $this->artisan('site:publish-commercial-pages-package', ['site' => $site->key, '--apply' => true])
            ->expectsOutputToContain('"mode": "apply"')
            ->assertSuccessful();
        $this->assertSame(4, SitePage::query()->published()->count());
        $this->assertSame(0, SiteUrl::query()->where('is_indexable', true)->count());
        $this->assertSame(0, SiteSeo::query()->where('is_indexable', true)->count());
    }

    public function test_it_refuses_a_missing_or_indexable_page_route(): void
    {
        $site = $this->site();

        $this->artisan('site:publish-commercial-pages-package', ['site' => $site->key])
            ->expectsOutputToContain('Commercial page package is incomplete')
            ->assertFailed();
    }

    private function site(): Site
    {
        return Site::create([
            'key' => 'microchips-by',
            'domain' => 'microchips.by',
            'country_code' => 'BY',
            'currency_code' => 'BYN',
            'default_locale' => 'ru-BY',
            'name' => 'Microchips BY',
            'is_active' => true,
        ]);
    }
}
