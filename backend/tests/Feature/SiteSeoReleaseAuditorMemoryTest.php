<?php

namespace Tests\Feature;

use App\Domain\Seo\SiteSeoReleaseAuditor;
use App\Models\Site;
use App\Models\SitePage;
use App\Models\SiteSeo;
use App\Models\SiteUrl;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class SiteSeoReleaseAuditorMemoryTest extends TestCase
{
    use RefreshDatabase;

    public function test_noindex_inventory_is_counted_without_hydrating_its_seo_payload(): void
    {
        $site = Site::create([
            'key' => 'microchips-by',
            'domain' => 'microchips.by',
            'country_code' => 'BY',
            'currency_code' => 'BYN',
            'default_locale' => 'ru-BY',
            'name' => 'Microchips',
            'is_active' => true,
        ]);
        $site->locales()->create([
            'locale' => 'ru-BY',
            'language' => 'ru',
            'is_default' => true,
            'is_enabled' => true,
        ]);

        $indexablePage = $this->page($site, 'published', true);
        $noindexPage = $this->page($site, 'migration-inventory', false);

        SiteSeo::create([
            'site_id' => $site->id,
            'locale' => 'ru-BY',
            'resource_type' => 'page',
            'resource_id' => $indexablePage->id,
            'canonical_path' => '/published',
            'is_indexable' => true,
        ]);
        SiteSeo::create([
            'site_id' => $site->id,
            'locale' => 'ru-BY',
            'resource_type' => 'page',
            'resource_id' => $noindexPage->id,
            'canonical_path' => '/migration-inventory',
            'description' => str_repeat('large migration-only payload ', 4000),
            'is_indexable' => false,
            'schema' => ['migration' => str_repeat('payload', 4000)],
        ]);

        $retrievedSeoRecords = 0;
        SiteSeo::retrieved(function () use (&$retrievedSeoRecords): void {
            $retrievedSeoRecords++;
        });

        $report = app(SiteSeoReleaseAuditor::class)->audit($site);

        $this->assertSame(2, $report['summary']['checkedUrls']);
        $this->assertSame(1, $report['summary']['sitemapUrls']);
        $this->assertSame(1, $retrievedSeoRecords);
    }

    private function page(Site $site, string $slug, bool $indexable): SitePage
    {
        $page = SitePage::create([
            'site_id' => $site->id,
            'locale' => 'ru-BY',
            'slug' => $slug,
            'title' => $slug,
            'h1' => $slug,
            'is_published' => true,
        ]);

        SiteUrl::create([
            'site_id' => $site->id,
            'path' => '/'.$slug,
            'locale' => 'ru-BY',
            'target_type' => 'page',
            'target_id' => $page->id,
            'is_indexable' => $indexable,
        ]);

        return $page;
    }
}
