<?php

namespace Tests\Feature;

use App\Domain\Seo\SiteSeoReleaseAuditor;
use App\Models\Site;
use App\Models\SitePage;
use App\Models\SiteSeo;
use App\Models\SiteUrl;
use App\Models\SiteUrlAlternate;
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

    public function test_hreflang_alternate_with_a_draft_target_is_blocked(): void
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
        $site->locales()->createMany([
            ['locale' => 'ru-BY', 'language' => 'ru', 'is_default' => true, 'is_enabled' => true],
            ['locale' => 'ru-RU', 'language' => 'ru', 'is_default' => false, 'is_enabled' => true],
        ]);
        $published = SitePage::create(['site_id' => $site->id, 'locale' => 'ru-BY', 'slug' => 'published', 'title' => 'Published', 'h1' => 'Published', 'is_published' => true]);
        $draft = SitePage::create(['site_id' => $site->id, 'locale' => 'ru-RU', 'slug' => 'draft', 'title' => 'Draft', 'h1' => 'Draft', 'is_published' => false]);
        $source = SiteUrl::create(['site_id' => $site->id, 'path' => '/published', 'locale' => 'ru-BY', 'target_type' => 'page', 'target_id' => $published->id, 'is_indexable' => true]);
        $target = SiteUrl::create(['site_id' => $site->id, 'path' => '/draft', 'locale' => 'ru-RU', 'target_type' => 'page', 'target_id' => $draft->id, 'is_indexable' => true]);
        SiteUrlAlternate::create(['source_url_id' => $source->id, 'alternate_url_id' => $target->id, 'locale' => 'ru-RU']);

        $report = app(SiteSeoReleaseAuditor::class)->audit($site);
        $codes = array_map(fn (array $issue) => $issue['code'], $report['issues']);

        $this->assertFalse($report['passed']);
        $this->assertContains('SEO_HREFLANG_ALTERNATE_TARGET_NOT_PUBLISHED_OR_CANONICAL', $codes);
    }

    public function test_hreflang_audit_uses_the_default_locale_for_a_null_locale_url(): void
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
        $site->locales()->createMany([
            ['locale' => 'ru-BY', 'language' => 'ru', 'is_default' => true, 'is_enabled' => true],
            ['locale' => 'ru-RU', 'language' => 'ru', 'is_default' => false, 'is_enabled' => true],
        ]);
        $sourcePage = SitePage::create(['site_id' => $site->id, 'locale' => 'ru-BY', 'slug' => 'source', 'title' => 'Source', 'h1' => 'Source', 'is_published' => true]);
        $targetPage = SitePage::create(['site_id' => $site->id, 'locale' => 'ru-RU', 'slug' => 'target', 'title' => 'Target', 'h1' => 'Target', 'is_published' => true]);
        $source = SiteUrl::create(['site_id' => $site->id, 'path' => '/source', 'locale' => null, 'target_type' => 'page', 'target_id' => $sourcePage->id, 'is_indexable' => true]);
        $target = SiteUrl::create(['site_id' => $site->id, 'path' => '/target', 'locale' => 'ru-RU', 'target_type' => 'page', 'target_id' => $targetPage->id, 'is_indexable' => true]);
        SiteSeo::create(['site_id' => $site->id, 'locale' => 'ru-BY', 'resource_type' => 'page', 'resource_id' => $sourcePage->id, 'canonical_path' => '/source', 'is_indexable' => false]);
        SiteUrlAlternate::create(['source_url_id' => $source->id, 'alternate_url_id' => $target->id, 'locale' => 'ru-RU']);
        SiteUrlAlternate::create(['source_url_id' => $target->id, 'alternate_url_id' => $source->id, 'locale' => 'ru-BY']);

        $report = app(SiteSeoReleaseAuditor::class)->audit($site);
        $codes = array_map(fn (array $issue) => $issue['code'], $report['issues']);

        $this->assertFalse($report['passed']);
        $this->assertContains('SEO_HREFLANG_SOURCE_TARGET_NOT_PUBLISHED_OR_CANONICAL', $codes);
    }
}
