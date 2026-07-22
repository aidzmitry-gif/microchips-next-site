<?php

namespace Tests\Feature;

use App\Domain\Seo\SiteSeoReleaseAuditor;
use App\Domain\Sites\SiteResolver;
use App\Models\Site;
use App\Models\SitePage;
use App\Models\SiteRedirect;
use App\Models\SiteSeo;
use App\Models\SiteUrl;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

/**
 * Targets the remaining uncovered branches in SiteSeoReleaseAuditor
 * (not already exercised by SeoReleaseAuditTest / AuditorErrorBranchesTest)
 * and the host/path normalization + resolution branches in SiteResolver
 * (not already exercised by MultiSiteApiTest / SiteResolveProductCategoryTest /
 * ControllerBranchesTest / NotFoundBranchesTest).
 */
class SeoAuditorResolverCoverageTest extends TestCase
{
    use RefreshDatabase;

    // -----------------------------------------------------------------
    // SiteSeoReleaseAuditor
    // -----------------------------------------------------------------

    public function test_canonical_with_a_full_url_on_the_sites_own_domain_is_rejected_as_external_format(): void
    {
        $site = $this->site('microchips-by', 'microchips.by', 'BY', 'ru-BY');
        $url = $this->publishedPage($site, '/industrial-batteries');
        SiteSeo::query()->where([
            'site_id' => $site->id,
            'locale' => 'ru-BY',
            'resource_type' => 'page',
            'resource_id' => $url->target_id,
        ])->update(['canonical_path' => 'https://MICROCHIPS.BY/industrial-batteries']);

        $report = app(SiteSeoReleaseAuditor::class)->audit($site);
        $codes = $this->issueCodes($report);

        $this->assertFalse($report['passed']);
        $this->assertContains('SEO_CANONICAL_EXTERNAL_FORMAT', $codes);
        // Same-domain case must take the "external format" branch, not the
        // cross-country branch — they are mutually exclusive in validateCanonical().
        $this->assertNotContains('SEO_CANONICAL_CROSS_COUNTRY', $codes);
    }

    public function test_an_indexable_url_that_is_also_an_active_redirect_source_is_blocked(): void
    {
        $site = $this->site('microchips-by', 'microchips.by', 'BY', 'ru-BY');
        $this->publishedPage($site, '/battery-catalog');
        $this->publishedPage($site, '/other-target');
        SiteRedirect::create([
            'site_id' => $site->id,
            'source_path' => '/battery-catalog',
            'target_path' => '/other-target',
            'status_code' => 301,
            'is_active' => true,
        ]);

        $report = app(SiteSeoReleaseAuditor::class)->audit($site);

        $this->assertFalse($report['passed']);
        $this->assertContains('SEO_INDEXABLE_REDIRECT_SOURCE', $this->issueCodes($report));
    }

    public function test_redirect_target_that_does_not_resolve_to_any_url_is_blocked(): void
    {
        $site = $this->site('microchips-by', 'microchips.by', 'BY', 'ru-BY');
        SiteRedirect::create([
            'site_id' => $site->id,
            'source_path' => '/gone-battery',
            'target_path' => '/never-existed',
            'status_code' => 301,
            'is_active' => true,
        ]);

        $report = app(SiteSeoReleaseAuditor::class)->audit($site);

        $this->assertFalse($report['passed']);
        $this->assertContains('SEO_REDIRECT_TARGET_NOT_RESOLVABLE', $this->issueCodes($report));
    }

    // -----------------------------------------------------------------
    // SiteResolver::normalizeHost
    // -----------------------------------------------------------------

    public function test_normalize_host_strips_scheme_www_prefix_port_and_trailing_path(): void
    {
        $resolver = new SiteResolver;

        $this->assertSame('microchips.by', $resolver->normalizeHost('https://WWW.Microchips.BY:8443/catalog/battery'));
        $this->assertSame('microchips.by', $resolver->normalizeHost('http://microchips.by'));
        $this->assertSame('microchips.by', $resolver->normalizeHost('  MICROCHIPS.BY  '));
        $this->assertSame('microchips.by', $resolver->normalizeHost('microchips.by:443'));
        $this->assertSame('microchips.by', $resolver->normalizeHost('www.microchips.by'));
    }

    public function test_normalize_host_only_strips_a_single_leading_www_label(): void
    {
        $resolver = new SiteResolver;

        $this->assertSame('www.example.by', $resolver->normalizeHost('www.www.example.by'));
    }

    public function test_resolve_applies_host_normalization_against_the_stored_plain_domain(): void
    {
        $this->site('microchips-by', 'microchips.by', 'BY', 'ru-BY');

        $resolved = (new SiteResolver)->resolve('HTTPS://WWW.Microchips.BY:443/ignored/path');

        $this->assertNotNull($resolved);
        $this->assertSame('microchips-by', $resolved->key);
    }

    // -----------------------------------------------------------------
    // SiteResolver::normalizePath
    // -----------------------------------------------------------------

    public function test_normalize_path_defaults_an_empty_path_to_root(): void
    {
        $resolver = new SiteResolver;

        $this->assertSame('/', $resolver->normalizePath(''));
    }

    public function test_normalize_path_adds_a_leading_slash_when_missing(): void
    {
        $resolver = new SiteResolver;

        $this->assertSame('/catalog/battery', $resolver->normalizePath('catalog/battery/'));
    }

    public function test_normalize_path_collapses_double_slashes(): void
    {
        $resolver = new SiteResolver;

        $this->assertSame('/catalog/battery', $resolver->normalizePath('/catalog//battery'));
    }

    public function test_normalize_path_trims_a_trailing_slash_but_keeps_the_bare_root_slash(): void
    {
        $resolver = new SiteResolver;

        $this->assertSame('/catalog/battery', $resolver->normalizePath('/catalog/battery/'));
        $this->assertSame('/', $resolver->normalizePath('/'));
    }

    public function test_resolve_path_applies_path_normalization_before_looking_up_the_url(): void
    {
        $site = $this->site('microchips-by', 'microchips.by', 'BY', 'ru-BY');
        $this->publishedPage($site, '/catalog/battery');

        $result = (new SiteResolver)->resolvePath($site, 'catalog//battery///');

        $this->assertSame('page', $result['kind']);
        $this->assertSame('/catalog/battery', $result['path']);
    }

    // -----------------------------------------------------------------
    // SiteResolver::resolvePath — 'not_found' for a URL whose target_type
    // does not match any of the known resource kinds.
    // -----------------------------------------------------------------

    public function test_resolve_path_returns_not_found_for_a_url_with_an_unrecognized_target_type(): void
    {
        $site = $this->site('microchips-by', 'microchips.by', 'BY', 'ru-BY');
        SiteUrl::create([
            'site_id' => $site->id,
            'path' => '/mystery-resource',
            'locale' => 'ru-BY',
            'target_type' => 'article',
            'target_id' => 1,
            'is_indexable' => true,
        ]);

        $result = (new SiteResolver)->resolvePath($site, '/mystery-resource');

        $this->assertSame('not_found', $result['kind']);
        $this->assertSame('microchips-by', $result['site']['key']);
    }

    // -----------------------------------------------------------------
    // Fixture helpers
    // -----------------------------------------------------------------

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

    private function publishedPage(Site $site, string $path, bool $indexable = true): SiteUrl
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
            'is_indexable' => $indexable,
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
