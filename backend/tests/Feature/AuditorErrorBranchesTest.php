<?php

namespace Tests\Feature;

use App\Domain\Seo\LegacyUrlMigrationDecisionAuditor;
use App\Domain\Seo\SiteSeoReleaseAuditor;
use App\Models\Category;
use App\Models\Product;
use App\Models\Site;
use App\Models\SiteCategory;
use App\Models\SitePage;
use App\Models\SiteProduct;
use App\Models\SiteRedirect;
use App\Models\SiteSeo;
use App\Models\SiteUrl;
use App\Models\SiteUrlAlternate;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

/**
 * Targets error-code branches in SiteSeoReleaseAuditor and
 * LegacyUrlMigrationDecisionAuditor that are not already exercised by
 * SeoReleaseAuditTest / LegacyUrlMigrationDecisionAuditorTest.
 */
class AuditorErrorBranchesTest extends TestCase
{
    use RefreshDatabase;

    // -----------------------------------------------------------------
    // SiteSeoReleaseAuditor
    // -----------------------------------------------------------------

    public function test_canonical_with_query_and_no_host_is_not_a_local_path(): void
    {
        $site = $this->site('microchips-by', 'microchips.by', 'BY', 'ru-BY');
        $page = $this->page($site, 'battery', true);
        $this->siteUrl($site, '/catalog/battery', 'page', $page->id, $site->default_locale);
        SiteSeo::create([
            'site_id' => $site->id,
            'locale' => $site->default_locale,
            'resource_type' => 'page',
            'resource_id' => $page->id,
            'canonical_path' => '/catalog?sort=price',
            'is_indexable' => true,
        ]);

        $report = app(SiteSeoReleaseAuditor::class)->audit($site);

        $this->assertFalse($report['passed']);
        $this->assertContains('SEO_CANONICAL_NOT_LOCAL_PATH', $this->issueCodes($report));
    }

    public function test_hreflang_duplicate_locale_from_the_same_source_is_blocked(): void
    {
        $belarus = $this->site('microchips-by', 'microchips.by', 'BY', 'ru-BY');
        $russia = $this->site('microchips-ru', 'microchips.ru', 'RU', 'ru-RU');
        $source = $this->publishedPage($belarus, '/industrial-batteries');
        $targetOne = $this->publishedPage($russia, '/ru-alternate-one');
        $targetTwo = $this->publishedPage($russia, '/ru-alternate-two');

        SiteUrlAlternate::create(['source_url_id' => $source->id, 'alternate_url_id' => $targetOne->id, 'locale' => 'ru-RU']);
        SiteUrlAlternate::create(['source_url_id' => $source->id, 'alternate_url_id' => $targetTwo->id, 'locale' => 'ru-RU']);

        $report = app(SiteSeoReleaseAuditor::class)->audit($belarus);

        $this->assertFalse($report['passed']);
        $this->assertContains('SEO_HREFLANG_DUPLICATE_LOCALE', $this->issueCodes($report));
    }

    public function test_hreflang_non_indexable_source_and_alternate_are_blocked(): void
    {
        $belarus = $this->site('microchips-by', 'microchips.by', 'BY', 'ru-BY');
        $russia = $this->site('microchips-ru', 'microchips.ru', 'RU', 'ru-RU');

        $noindexSource = $this->publishedPage($belarus, '/noindex-source', indexable: false);
        $okTarget = $this->publishedPage($russia, '/ok-target');
        SiteUrlAlternate::create(['source_url_id' => $noindexSource->id, 'alternate_url_id' => $okTarget->id, 'locale' => 'ru-RU']);

        $okSource = $this->publishedPage($belarus, '/ok-source');
        $noindexTarget = $this->publishedPage($russia, '/noindex-target', indexable: false);
        SiteUrlAlternate::create(['source_url_id' => $okSource->id, 'alternate_url_id' => $noindexTarget->id, 'locale' => 'ru-RU']);

        $report = app(SiteSeoReleaseAuditor::class)->audit($belarus);
        $codes = $this->issueCodes($report);

        $this->assertFalse($report['passed']);
        $this->assertContains('SEO_HREFLANG_SOURCE_NOT_INDEXABLE', $codes);
        $this->assertContains('SEO_HREFLANG_ALTERNATE_NOT_INDEXABLE', $codes);
    }

    public function test_hreflang_declared_locale_must_equal_the_target_urls_locale(): void
    {
        $belarus = $this->site('microchips-by', 'microchips.by', 'BY', 'ru-BY');
        $russia = $this->site('microchips-ru', 'microchips.ru', 'RU', 'ru-RU');
        $source = $this->publishedPage($belarus, '/industrial-batteries');
        $target = $this->publishedPage($russia, '/promyshlennye-akkumulyatory');

        SiteUrlAlternate::create(['source_url_id' => $source->id, 'alternate_url_id' => $target->id, 'locale' => 'en-US']);

        $report = app(SiteSeoReleaseAuditor::class)->audit($belarus);

        $this->assertFalse($report['passed']);
        $this->assertContains('SEO_HREFLANG_LOCALE_MISMATCH', $this->issueCodes($report));
    }

    public function test_unpublished_page_product_and_category_targets_block_release(): void
    {
        $site = $this->site('microchips-by', 'microchips.by', 'BY', 'ru-BY');

        $unpublishedPage = $this->page($site, 'draft-page', false);
        $this->siteUrl($site, '/unpub-page', 'page', $unpublishedPage->id, $site->default_locale);

        $publishedProduct = $this->product($site, 'published-product', true);
        $this->siteUrl($site, '/pub-product', 'product', $publishedProduct->id, $site->default_locale);
        $unpublishedProduct = $this->product($site, 'draft-product', false);
        $this->siteUrl($site, '/unpub-product', 'product', $unpublishedProduct->id, $site->default_locale);

        $publishedCategory = $this->category($site, 'published-category', true);
        $this->siteUrl($site, '/pub-category', 'category', $publishedCategory->id, $site->default_locale);
        $unpublishedCategory = $this->category($site, 'draft-category', false);
        $this->siteUrl($site, '/unpub-category', 'category', $unpublishedCategory->id, $site->default_locale);

        $report = app(SiteSeoReleaseAuditor::class)->audit($site);

        $this->assertFalse($report['passed']);
        $this->assertSame(3, $report['summary']['blockingIssues']);

        $issuesByPath = collect($report['issues'])->keyBy('path');
        $this->assertSame('SEO_INDEXABLE_TARGET_NOT_PUBLISHED', $issuesByPath['/unpub-page']['code']);
        $this->assertSame('page', $issuesByPath['/unpub-page']['context']['targetType']);
        $this->assertSame('SEO_INDEXABLE_TARGET_NOT_PUBLISHED', $issuesByPath['/unpub-product']['code']);
        $this->assertSame('product', $issuesByPath['/unpub-product']['context']['targetType']);
        $this->assertSame('SEO_INDEXABLE_TARGET_NOT_PUBLISHED', $issuesByPath['/unpub-category']['code']);
        $this->assertSame('category', $issuesByPath['/unpub-category']['context']['targetType']);
        $this->assertArrayNotHasKey('/pub-product', $issuesByPath);
        $this->assertArrayNotHasKey('/pub-category', $issuesByPath);
    }

    public function test_redirect_with_an_unsafe_source_path_is_blocked(): void
    {
        $site = $this->site('microchips-by', 'microchips.by', 'BY', 'ru-BY');
        $this->publishedPage($site, '/new-battery');
        SiteRedirect::create([
            'site_id' => $site->id,
            'source_path' => '/legacy?ref=1',
            'target_path' => '/new-battery',
            'status_code' => 301,
            'is_active' => true,
        ]);

        $report = app(SiteSeoReleaseAuditor::class)->audit($site);

        $this->assertFalse($report['passed']);
        $this->assertContains('SEO_REDIRECT_UNSAFE_SOURCE', $this->issueCodes($report));
    }

    public function test_redirect_pointing_to_itself_is_blocked(): void
    {
        $site = $this->site('microchips-by', 'microchips.by', 'BY', 'ru-BY');
        SiteRedirect::create([
            'site_id' => $site->id,
            'source_path' => '/loop',
            'target_path' => '/loop',
            'status_code' => 301,
            'is_active' => true,
        ]);

        $report = app(SiteSeoReleaseAuditor::class)->audit($site);

        $this->assertFalse($report['passed']);
        $this->assertContains('SEO_REDIRECT_SELF_REFERENCE', $this->issueCodes($report));
    }

    // -----------------------------------------------------------------
    // LegacyUrlMigrationDecisionAuditor
    // -----------------------------------------------------------------

    public function test_legacy_decision_invalid_is_blocked(): void
    {
        $report = app(LegacyUrlMigrationDecisionAuditor::class)->audit('microchips.by', [
            $this->row('/catalog/valid', 'archive', 'approved', null, null, null, true),
        ]);

        $this->assertFalse($report['passed']);
        $this->assertContains('LEGACY_DECISION_INVALID', $this->legacyIssueCodes($report));
    }

    public function test_legacy_url_invalid_when_legacy_url_is_missing(): void
    {
        $report = app(LegacyUrlMigrationDecisionAuditor::class)->audit('microchips.by', [
            $this->row(null, 'keep', 'approved', null, 200, null, true),
        ]);

        $this->assertFalse($report['passed']);
        $this->assertContains('LEGACY_URL_INVALID', $this->legacyIssueCodes($report));
    }

    public function test_legacy_redirect_expected_status_must_be_permanent(): void
    {
        $report = app(LegacyUrlMigrationDecisionAuditor::class)->audit('microchips.by', [
            $this->row('/catalog/temp-redirect', 'redirect', 'approved', '/catalog/target', 302, null, true),
        ]);

        $this->assertFalse($report['passed']);
        $this->assertContains('LEGACY_REDIRECT_NOT_PERMANENT', $this->legacyIssueCodes($report));
    }

    public function test_legacy_redirect_cannot_declare_a_canonical(): void
    {
        $report = app(LegacyUrlMigrationDecisionAuditor::class)->audit('microchips.by', [
            $this->row('/catalog/redirect-with-canonical', 'redirect', 'approved', '/catalog/target', 301, '/catalog/some-canonical', true),
        ]);

        $this->assertFalse($report['passed']);
        $this->assertContains('LEGACY_REDIRECT_HAS_CANONICAL', $this->legacyIssueCodes($report));
    }

    public function test_legacy_redirect_source_must_be_unique(): void
    {
        $report = app(LegacyUrlMigrationDecisionAuditor::class)->audit('microchips.by', [
            $this->row('/catalog/dup', 'redirect', 'approved', '/catalog/a', 301, null, true),
            $this->row('/catalog/dup', 'redirect', 'approved', '/catalog/b', 301, null, true),
        ]);

        $this->assertFalse($report['passed']);
        $this->assertContains('LEGACY_REDIRECT_DUPLICATE_SOURCE', $this->legacyIssueCodes($report));
    }

    public function test_legacy_keep_canonical_must_equal_the_final_path(): void
    {
        $report = app(LegacyUrlMigrationDecisionAuditor::class)->audit('microchips.by', [
            $this->row('/catalog/keep-me', 'keep', 'approved', null, 200, '/catalog/other', true),
        ]);

        $this->assertFalse($report['passed']);
        $this->assertContains('LEGACY_CANONICAL_NOT_SELF', $this->legacyIssueCodes($report));
    }

    public function test_legacy_remove_cannot_declare_a_destination(): void
    {
        $report = app(LegacyUrlMigrationDecisionAuditor::class)->audit('microchips.by', [
            $this->row('/catalog/remove-me', 'remove', 'approved', '/catalog/somewhere', 410, null, true),
        ]);

        $this->assertFalse($report['passed']);
        $this->assertContains('LEGACY_REMOVE_HAS_DESTINATION', $this->legacyIssueCodes($report));
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

    private function page(Site $site, string $slug, bool $published): SitePage
    {
        return SitePage::create([
            'site_id' => $site->id,
            'locale' => $site->default_locale,
            'slug' => $slug,
            'title' => "Title {$slug}",
            'h1' => "H1 {$slug}",
            'is_published' => $published,
        ]);
    }

    private function product(Site $site, string $slug, bool $published): SiteProduct
    {
        $product = Product::create([
            'slug' => "{$site->key}-{$slug}",
            'name' => "Product {$slug}",
            'status' => 'active',
        ]);

        return SiteProduct::create([
            'site_id' => $site->id,
            'product_id' => $product->id,
            'slug' => $slug,
            'is_published' => $published,
            'availability' => 'on_request',
        ]);
    }

    private function category(Site $site, string $slug, bool $published): SiteCategory
    {
        $category = Category::create([
            'slug' => "{$site->key}-{$slug}",
            'name' => "Category {$slug}",
        ]);

        return SiteCategory::create([
            'site_id' => $site->id,
            'category_id' => $category->id,
            'slug' => $slug,
            'name' => "Category {$slug}",
            'is_published' => $published,
        ]);
    }

    private function siteUrl(Site $site, string $path, string $targetType, int $targetId, string $locale, bool $indexable = true): SiteUrl
    {
        return SiteUrl::create([
            'site_id' => $site->id,
            'path' => $path,
            'locale' => $locale,
            'target_type' => $targetType,
            'target_id' => $targetId,
            'is_indexable' => $indexable,
        ]);
    }

    private function publishedPage(Site $site, string $path, bool $indexable = true): SiteUrl
    {
        $slug = trim(str_replace(['/', '?', '=', '&'], '-', $path), '-');
        $page = $this->page($site, $slug === '' ? 'home' : $slug, true);

        return $this->siteUrl($site, $path, 'page', $page->id, $site->default_locale, $indexable);
    }

    /** @return array<string, mixed> */
    private function row(
        ?string $legacyUrl,
        string $decision,
        string $reviewStatus,
        ?string $destinationUrl,
        ?int $expectedStatus,
        ?string $canonicalUrl,
        bool $priority,
    ): array {
        return [
            'legacy_url' => $legacyUrl,
            'decision' => $decision,
            'review_status' => $reviewStatus,
            'destination_url' => $destinationUrl,
            'expected_status' => $expectedStatus,
            'canonical_url' => $canonicalUrl,
            'priority' => $priority,
        ];
    }

    /** @param array{issues: list<array{code: string}>} $report
     * @return list<string>
     */
    private function issueCodes(array $report): array
    {
        return array_map(fn (array $issue) => $issue['code'], $report['issues']);
    }

    /** @param array{issues: list<array{code: string}>} $report
     * @return list<string>
     */
    private function legacyIssueCodes(array $report): array
    {
        return array_map(fn (array $issue) => $issue['code'], $report['issues']);
    }
}
