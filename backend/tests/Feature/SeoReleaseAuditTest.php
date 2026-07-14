<?php

namespace Tests\Feature;

use App\Domain\Seo\SiteSeoReleaseAuditor;
use App\Models\Site;
use App\Models\SitePage;
use App\Models\SiteRedirect;
use App\Models\SiteSeo;
use App\Models\SiteUrl;
use App\Models\SiteUrlAlternate;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class SeoReleaseAuditTest extends TestCase
{
    use RefreshDatabase;

    public function test_a_valid_site_profile_passes_the_read_only_release_audit_and_command(): void
    {
        $belarus = $this->site('microchips-by', 'microchips.by', 'BY', 'ru-BY');
        $russia = $this->site('microchips-ru', 'microchips.ru', 'RU', 'ru-RU');
        $byUrl = $this->publishedPage($belarus, '/industrial-batteries');
        $ruUrl = $this->publishedPage($russia, '/promyshlennye-akkumulyatory');

        SiteUrlAlternate::create([
            'source_url_id' => $byUrl->id,
            'alternate_url_id' => $ruUrl->id,
            'locale' => 'ru-RU',
        ]);
        SiteUrlAlternate::create([
            'source_url_id' => $ruUrl->id,
            'alternate_url_id' => $byUrl->id,
            'locale' => 'ru-BY',
        ]);

        $report = app(SiteSeoReleaseAuditor::class)->audit($belarus);

        $this->assertTrue($report['passed']);
        $this->assertSame(0, $report['summary']['blockingIssues']);
        $this->artisan('seo:audit', ['site' => 'microchips-by'])
            ->expectsOutputToContain('PASS: SEO release audit passed')
            ->assertExitCode(0);
    }

    public function test_cross_country_canonical_and_non_self_canonical_are_release_blockers(): void
    {
        $site = $this->site('microchips-by', 'microchips.by', 'BY', 'ru-BY');
        $url = $this->publishedPage($site, '/industrial-batteries');
        SiteSeo::query()->where([
            'site_id' => $site->id,
            'locale' => 'ru-BY',
            'resource_type' => 'page',
            'resource_id' => $url->target_id,
        ])->update(['canonical_path' => '/battery-catalog']);

        $notSelfReport = app(SiteSeoReleaseAuditor::class)->audit($site);

        $this->assertFalse($notSelfReport['passed']);
        $this->assertContains('SEO_CANONICAL_NOT_SELF', $this->issueCodes($notSelfReport));

        SiteSeo::query()->where([
            'site_id' => $site->id,
            'locale' => 'ru-BY',
            'resource_type' => 'page',
            'resource_id' => $url->target_id,
        ])->update(['canonical_path' => 'https://microchips.ru/prom-battery']);

        $report = app(SiteSeoReleaseAuditor::class)->audit($site);

        $this->assertFalse($report['passed']);
        $this->assertContains('SEO_CANONICAL_CROSS_COUNTRY', $this->issueCodes($report));
        $this->getJson('/api/v1/sites/microchips.by/seo/sitemap')
            ->assertOk()
            ->assertJsonCount(0, 'urls');
    }

    public function test_hreflang_requires_an_enabled_target_locale_and_reciprocal_mapping(): void
    {
        $belarus = $this->site('microchips-by', 'microchips.by', 'BY', 'ru-BY');
        $russia = $this->site('microchips-ru', 'microchips.ru', 'RU', 'ru-RU', false);
        $byUrl = $this->publishedPage($belarus, '/industrial-batteries');
        $ruUrl = $this->publishedPage($russia, '/promyshlennye-akkumulyatory');

        SiteUrlAlternate::create([
            'source_url_id' => $byUrl->id,
            'alternate_url_id' => $ruUrl->id,
            'locale' => 'ru-RU',
        ]);

        $report = app(SiteSeoReleaseAuditor::class)->audit($belarus);

        $this->assertFalse($report['passed']);
        $this->assertContains('SEO_HREFLANG_ALTERNATE_LOCALE_DISABLED', $this->issueCodes($report));
        $this->assertContains('SEO_HREFLANG_NOT_RECIPROCAL', $this->issueCodes($report));
    }

    public function test_sitemap_excludes_filter_query_and_noindex_urls_and_audit_blocks_them(): void
    {
        $site = $this->site('microchips-by', 'microchips.by', 'BY', 'ru-BY');
        $safe = $this->publishedPage($site, '/industrial-batteries');
        $query = $this->publishedPage($site, '/catalog?sort=price');
        $filter = $this->publishedPage($site, '/catalog/filter/brand-is-alpha/apply');
        $noindex = $this->publishedPage($site, '/contract-pricing');
        SiteSeo::query()->where('resource_id', $noindex->target_id)->update(['is_indexable' => false]);

        $report = app(SiteSeoReleaseAuditor::class)->audit($site);

        $this->assertFalse($report['passed']);
        $this->assertContains('SEO_SITEMAP_UNSAFE_PATH', $this->issueCodes($report));
        $this->assertContains('SEO_INDEXABILITY_CONFLICT', $this->issueCodes($report));
        $this->getJson('/api/v1/sites/microchips.by/seo/sitemap')
            ->assertOk()
            ->assertJsonPath('urls.0.path', $safe->path)
            ->assertJsonCount(1, 'urls');
        $this->assertNotSame($safe->id, $query->id);
        $this->assertNotSame($safe->id, $filter->id);
    }

    public function test_redirect_chains_homepage_fallbacks_and_external_targets_block_release(): void
    {
        $site = $this->site('microchips-by', 'microchips.by', 'BY', 'ru-BY');
        $this->publishedPage($site, '/new-battery');
        SiteRedirect::create(['site_id' => $site->id, 'source_path' => '/old-battery', 'target_path' => '/middle-battery', 'status_code' => 301, 'is_active' => true]);
        SiteRedirect::create(['site_id' => $site->id, 'source_path' => '/middle-battery', 'target_path' => '/new-battery', 'status_code' => 302, 'is_active' => true]);
        SiteRedirect::create(['site_id' => $site->id, 'source_path' => '/removed-battery', 'target_path' => '/', 'status_code' => 301, 'is_active' => true]);
        SiteRedirect::create(['site_id' => $site->id, 'source_path' => '/external-battery', 'target_path' => 'https://microchips.ru/battery', 'status_code' => 301, 'is_active' => true]);

        $report = app(SiteSeoReleaseAuditor::class)->audit($site);
        $codes = $this->issueCodes($report);

        $this->assertFalse($report['passed']);
        $this->assertContains('SEO_REDIRECT_CHAIN', $codes);
        $this->assertContains('SEO_REDIRECT_TO_HOME', $codes);
        $this->assertContains('SEO_REDIRECT_UNSAFE_TARGET', $codes);
        $this->assertContains('SEO_REDIRECT_NOT_PERMANENT', $codes);
        $this->artisan('seo:audit', ['site' => 'microchips-by', '--json' => true])
            ->assertExitCode(1);
    }

    private function site(string $key, string $domain, string $country, string $locale, bool $localeEnabled = true): Site
    {
        $site = Site::create([
            'key' => $key,
            'domain' => $domain,
            'country_code' => $country,
            'currency_code' => $country === 'RU' ? 'RUB' : 'BYN',
            'default_locale' => $locale,
            'name' => $key,
            'is_active' => true,
        ]);
        $site->locales()->create([
            'locale' => $locale,
            'language' => 'ru',
            'is_default' => true,
            'is_enabled' => $localeEnabled,
        ]);

        return $site;
    }

    private function publishedPage(Site $site, string $path): SiteUrl
    {
        $slug = trim(str_replace(['/', '?', '=', '&'], '-', $path), '-');
        $page = SitePage::create([
            'site_id' => $site->id,
            'locale' => $site->default_locale,
            'slug' => $slug === '' ? 'home' : $slug,
            'title' => "Title {$path}",
            'h1' => "H1 {$path}",
            'is_published' => true,
        ]);
        $url = SiteUrl::create([
            'site_id' => $site->id,
            'path' => $path,
            'locale' => $site->default_locale,
            'target_type' => 'page',
            'target_id' => $page->id,
            'is_indexable' => true,
        ]);
        SiteSeo::create([
            'site_id' => $site->id,
            'locale' => $site->default_locale,
            'resource_type' => 'page',
            'resource_id' => $page->id,
            'canonical_path' => $path,
            'title' => "Title {$path}",
            'is_indexable' => true,
        ]);

        return $url;
    }

    /** @param array{issues: list<array{code: string}>} $report
     * @return list<string>
     */
    private function issueCodes(array $report): array
    {
        return array_map(fn (array $issue) => $issue['code'], $report['issues']);
    }
}
