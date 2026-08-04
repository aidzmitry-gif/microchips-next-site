<?php

namespace Tests\Feature;

use App\Domain\Launch\SiteLaunchPreflight;
use App\Models\Site;
use App\Models\SiteCommercialFact;
use App\Models\SiteContact;
use App\Models\SitePage;
use App\Models\SiteSeo;
use App\Models\SiteUrl;
use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class SiteLaunchPreflightTest extends TestCase
{
    use RefreshDatabase;

    public function test_preflight_lists_missing_indexable_url_without_requiring_an_optional_crm(): void
    {
        $site = Site::create([
            'key' => 'microchips-by', 'domain' => 'microchips.by', 'country_code' => 'BY', 'currency_code' => 'BYN',
            'default_locale' => 'ru-BY', 'name' => 'Microchips Беларусь', 'is_active' => true,
        ]);

        $report = app(SiteLaunchPreflight::class)->inspect($site);

        $this->assertFalse($report['passed']);
        $this->assertContains('INDEXABLE_URL_MISSING', array_column($report['issues'], 'code'));
        $this->assertNotContains('BITRIX24_NOT_ENABLED', array_column($report['issues'], 'code'));
        // SEO audit correctly accepts an empty draft profile; country launch
        // preflight adds the stricter requirement that at least one URL has
        // actually been prepared for indexability.
        $this->assertTrue($report['summary']['seoAuditPassed']);
        $this->assertDatabaseCount('site_integrations', 0);
        $this->assertDatabaseCount('site_urls', 0);
    }

    public function test_preflight_command_returns_json_and_a_nonzero_exit_for_blocked_site(): void
    {
        Site::create([
            'key' => 'microchips-by', 'domain' => 'microchips.by', 'country_code' => 'BY', 'currency_code' => 'BYN',
            'default_locale' => 'ru-BY', 'name' => 'Microchips Беларусь', 'is_active' => true,
        ]);

        $this->artisan('site:launch-preflight', ['site' => 'microchips-by', '--json' => true])
            ->expectsOutputToContain('INDEXABLE_URL_MISSING')
            ->assertFailed();
    }

    public function test_preflight_requires_verified_local_commercial_profile_before_an_indexable_url_can_launch(): void
    {
        $site = Site::create([
            'key' => 'microchips-ru', 'domain' => 'microchips.ru', 'country_code' => 'RU', 'currency_code' => 'RUB',
            'default_locale' => 'ru-RU', 'name' => 'Microchips Россия', 'is_active' => true,
        ]);
        $page = SitePage::create(['site_id' => $site->id, 'locale' => 'ru-RU', 'slug' => 'contacts', 'title' => 'Контакты', 'h1' => 'Контакты', 'content' => 'Local content', 'is_published' => true]);
        SiteUrl::create(['site_id' => $site->id, 'path' => '/contacts', 'locale' => 'ru-RU', 'target_type' => 'page', 'target_id' => $page->id, 'is_indexable' => true]);
        SiteSeo::create(['site_id' => $site->id, 'locale' => 'ru-RU', 'resource_type' => 'page', 'resource_id' => $page->id, 'canonical_path' => '/contacts', 'title' => 'Контакты', 'description' => 'Local content', 'is_indexable' => true]);

        $report = app(SiteLaunchPreflight::class)->inspect($site);

        $this->assertFalse($report['passed']);
        $this->assertContains('COMMERCIAL_PROFILE_INCOMPLETE', array_column($report['issues'], 'code'));
    }

    public function test_preflight_accepts_complete_verified_local_commercial_profile(): void
    {
        $site = Site::create([
            'key' => 'microchips-ru', 'domain' => 'microchips.ru', 'country_code' => 'RU', 'currency_code' => 'RUB',
            'default_locale' => 'ru-RU', 'name' => 'Microchips Россия', 'is_active' => true,
        ]);
        $site->locales()->create(['locale' => 'ru-RU', 'language' => 'ru', 'is_default' => true, 'is_enabled' => true]);
        $operator = User::factory()->create(['is_admin' => true]);
        foreach (['legal_entity', 'address', 'phone', 'email', 'working_hours'] as $type) {
            $value = match ($type) {
                'phone' => '+7 495 123-45-67',
                'email' => 'operator@example.test',
                default => 'Verified '.$type,
            };
            SiteContact::create(['site_id' => $site->id, 'locale' => 'ru-RU', 'type' => $type, 'label' => $type, 'value' => $value, 'is_primary' => true, 'is_published' => true, 'verified_at' => now(), 'verified_by' => $operator->id, 'verification_note' => 'Test verification']);
        }
        foreach (SiteCommercialFact::KEYS as $key) {
            SiteCommercialFact::create(['site_id' => $site->id, 'locale' => 'ru-RU', 'key' => $key, 'value' => 'Verified '.$key, 'is_published' => true, 'verified_at' => now(), 'verified_by' => $operator->id, 'verification_note' => 'Test verification']);
        }
        $page = SitePage::create(['site_id' => $site->id, 'locale' => 'ru-RU', 'slug' => 'contacts', 'title' => 'Контакты', 'h1' => 'Контакты', 'content' => 'Local content', 'is_published' => true]);
        SiteUrl::create(['site_id' => $site->id, 'path' => '/contacts', 'locale' => 'ru-RU', 'target_type' => 'page', 'target_id' => $page->id, 'is_indexable' => true]);
        SiteSeo::create(['site_id' => $site->id, 'locale' => 'ru-RU', 'resource_type' => 'page', 'resource_id' => $page->id, 'canonical_path' => '/contacts', 'title' => 'Контакты', 'description' => 'Local content', 'is_indexable' => true]);

        $report = app(SiteLaunchPreflight::class)->inspect($site);

        $this->assertTrue($report['passed']);
    }
}
