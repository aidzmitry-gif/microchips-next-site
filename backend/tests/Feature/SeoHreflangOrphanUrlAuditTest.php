<?php

namespace Tests\Feature;

use App\Domain\Seo\SiteSeoReleaseAuditor;
use App\Models\Site;
use App\Models\SitePage;
use App\Models\SiteUrl;
use Illuminate\Foundation\Testing\DatabaseMigrations;
use Illuminate\Support\Facades\DB;
use Tests\TestCase;

/**
 * Covers SEO_HREFLANG_MISSING_URL, the defensive branch that fires when a
 * site_url_alternates row references a site_urls id that no longer exists.
 *
 * That state cannot be produced through normal Eloquent/FK-respecting writes
 * (site_url_alternates.alternate_url_id is FK-constrained with cascade
 * delete), so the row is inserted with SQLite foreign-key enforcement
 * temporarily off. SQLite only allows toggling that pragma outside of an
 * open transaction, so this uses DatabaseMigrations (real migrate/rollback
 * per test) instead of RefreshDatabase (which wraps every test in a
 * transaction and would make the pragma a silent no-op).
 */
class SeoHreflangOrphanUrlAuditTest extends TestCase
{
    use DatabaseMigrations;

    public function test_hreflang_alternate_row_referencing_a_missing_url_is_blocked(): void
    {
        $site = Site::create([
            'key' => 'microchips-by',
            'domain' => 'microchips.by',
            'country_code' => 'BY',
            'currency_code' => 'BYN',
            'default_locale' => 'ru-BY',
            'name' => 'microchips-by',
            'is_active' => true,
        ]);
        $site->locales()->create([
            'locale' => 'ru-BY',
            'language' => 'ru',
            'is_default' => true,
            'is_enabled' => true,
        ]);
        $page = SitePage::create([
            'site_id' => $site->id,
            'locale' => $site->default_locale,
            'slug' => 'industrial-batteries',
            'title' => 'Title',
            'h1' => 'H1',
            'is_published' => true,
        ]);
        $source = SiteUrl::create([
            'site_id' => $site->id,
            'path' => '/industrial-batteries',
            'locale' => $site->default_locale,
            'target_type' => 'page',
            'target_id' => $page->id,
            'is_indexable' => true,
        ]);

        $this->assertSame(0, DB::table('site_url_alternates')->count());

        DB::statement('PRAGMA foreign_keys = OFF');
        try {
            DB::table('site_url_alternates')->insert([
                'source_url_id' => $source->id,
                'alternate_url_id' => 999999,
                'locale' => 'ru-RU',
                'created_at' => now(),
                'updated_at' => now(),
            ]);
        } finally {
            DB::statement('PRAGMA foreign_keys = ON');
        }

        $report = app(SiteSeoReleaseAuditor::class)->audit($site);
        $codes = array_map(fn (array $issue) => $issue['code'], $report['issues']);

        $this->assertFalse($report['passed']);
        $this->assertContains('SEO_HREFLANG_MISSING_URL', $codes);
    }
}
