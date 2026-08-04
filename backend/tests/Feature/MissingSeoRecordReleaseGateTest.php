<?php

namespace Tests\Feature;

use App\Domain\Seo\SiteIndexabilityPublisher;
use App\Domain\Seo\SiteSeoReleaseAuditor;
use App\Models\Site;
use App\Models\SiteCommercialFact;
use App\Models\SiteContact;
use App\Models\SitePage;
use App\Models\SiteUrl;
use App\Models\User;
use DomainException;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class MissingSeoRecordReleaseGateTest extends TestCase
{
    use RefreshDatabase;

    public function test_indexable_url_without_an_explicit_site_seo_record_is_blocked_and_omitted_from_sitemap(): void
    {
        [$site, $url] = $this->pageUrl(indexable: true);

        $report = app(SiteSeoReleaseAuditor::class)->audit($site);

        $this->assertFalse($report['passed']);
        $this->assertContains('SEO_INDEXABLE_URL_SEO_RECORD_MISSING', $this->issueCodes($report));
        $this->getJson('/api/v1/sites/microchips.by/seo/sitemap')
            ->assertOk()
            ->assertJsonCount(0, 'urls');
        $this->assertSame('/catalog/battery', $url->path);
    }

    public function test_promotion_rolls_back_when_the_required_seo_record_is_missing_even_with_verified_profile(): void
    {
        [$site, $url] = $this->pageUrl(indexable: false);
        $this->verifiedProfile($site);

        try {
            app(SiteIndexabilityPublisher::class)->promote($url);
            $this->fail('Promotion unexpectedly succeeded without an SEO record.');
        } catch (DomainException $exception) {
            $this->assertStringContainsString('SEO_INDEXABLE_URL_SEO_RECORD_MISSING', $exception->getMessage());
        }

        $this->assertFalse($url->fresh()->is_indexable);
    }

    /** @return array{Site, SiteUrl} */
    private function pageUrl(bool $indexable): array
    {
        $site = Site::create([
            'key' => 'microchips-by',
            'domain' => 'microchips.by',
            'country_code' => 'BY',
            'currency_code' => 'BYN',
            'default_locale' => 'ru-BY',
            'name' => 'Microchips Belarus',
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
            'locale' => 'ru-BY',
            'slug' => 'catalog-battery',
            'title' => 'Battery',
            'h1' => 'Battery',
            'is_published' => true,
        ]);
        $url = SiteUrl::create([
            'site_id' => $site->id,
            'path' => '/catalog/battery',
            'locale' => 'ru-BY',
            'target_type' => 'page',
            'target_id' => $page->id,
            'is_indexable' => $indexable,
        ]);

        return [$site, $url];
    }

    private function verifiedProfile(Site $site): void
    {
        $verifier = User::factory()->create(['is_admin' => true]);
        foreach (['legal_entity' => 'Microchips LLC', 'address' => 'Minsk', 'phone' => '+375 29 123 45 67', 'email' => 'sales@example.by'] as $type => $value) {
            $contact = SiteContact::create(['site_id' => $site->id, 'locale' => 'ru-BY', 'type' => $type, 'label' => $type, 'value' => $value]);
            $contact->publish($verifier, 'Verified against source document');
        }
        foreach (['legal_name' => 'Microchips LLC', 'legal_address' => 'Minsk', 'delivery_terms' => 'Delivery terms', 'payment_terms' => 'Payment terms'] as $key => $value) {
            $fact = SiteCommercialFact::create(['site_id' => $site->id, 'locale' => 'ru-BY', 'key' => $key, 'value' => $value]);
            $fact->publish($verifier, 'Verified against source document');
        }
    }

    /** @param array{issues: list<array{code: string}>} $report
     * @return list<string>
     */
    private function issueCodes(array $report): array
    {
        return array_map(fn (array $issue) => $issue['code'], $report['issues']);
    }
}
