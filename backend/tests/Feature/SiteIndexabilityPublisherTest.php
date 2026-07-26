<?php

namespace Tests\Feature;

use App\Domain\Seo\SiteIndexabilityPublisher;
use App\Models\Site;
use App\Models\SiteCommercialFact;
use App\Models\SiteContact;
use App\Models\SitePage;
use App\Models\SiteSeo;
use App\Models\SiteUrl;
use App\Models\User;
use DomainException;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class SiteIndexabilityPublisherTest extends TestCase
{
    use RefreshDatabase;

    public function test_promotion_rolls_back_when_verified_regional_profile_is_missing(): void
    {
        [$site, $url] = $this->noindexPage();

        try {
            app(SiteIndexabilityPublisher::class)->promote($url);
            $this->fail('Promotion unexpectedly succeeded without a verified profile.');
        } catch (DomainException) {
            // Expected: the transaction must leave both records noindex.
        }

        $this->assertFalse($url->fresh()->is_indexable);
        $this->assertFalse((bool) SiteSeo::query()->where('site_id', $site->id)->value('is_indexable'));
    }

    public function test_promotion_succeeds_only_after_the_complete_verified_profile_exists(): void
    {
        [$site, $url] = $this->noindexPage();
        $this->verifiedProfile($site);

        app(SiteIndexabilityPublisher::class)->promote($url);

        $this->assertTrue($url->fresh()->is_indexable);
        $this->assertTrue((bool) SiteSeo::query()->where('site_id', $site->id)->value('is_indexable'));
        $this->artisan('seo:promote-url', ['site' => $site->key, 'path' => $url->path])
            ->expectsOutputToContain('PASS: /catalog/battery is now indexable.')
            ->assertExitCode(0);
    }

    /** @return array{Site, SiteUrl} */
    private function noindexPage(): array
    {
        $site = Site::create([
            'key' => 'microchips-by', 'domain' => 'microchips.by', 'country_code' => 'BY', 'currency_code' => 'BYN',
            'default_locale' => 'ru-BY', 'name' => 'Microchips', 'is_active' => true,
        ]);
        $site->locales()->create(['locale' => 'ru-BY', 'language' => 'ru', 'is_default' => true, 'is_enabled' => true]);
        $page = SitePage::create([
            'site_id' => $site->id, 'locale' => 'ru-BY', 'slug' => 'catalog-battery', 'title' => 'Battery', 'h1' => 'Battery', 'is_published' => true,
        ]);
        $url = SiteUrl::create([
            'site_id' => $site->id, 'path' => '/catalog/battery', 'locale' => 'ru-BY', 'target_type' => 'page', 'target_id' => $page->id, 'is_indexable' => false,
        ]);
        SiteSeo::create([
            'site_id' => $site->id, 'locale' => 'ru-BY', 'resource_type' => 'page', 'resource_id' => $page->id,
            'canonical_path' => '/catalog/battery', 'title' => 'Battery', 'is_indexable' => false,
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
}
