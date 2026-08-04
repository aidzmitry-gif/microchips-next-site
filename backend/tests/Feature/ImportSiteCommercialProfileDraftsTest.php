<?php

namespace Tests\Feature;

use App\Models\ImportRun;
use App\Models\Site;
use App\Models\SiteCommercialFact;
use App\Models\SiteContact;
use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class ImportSiteCommercialProfileDraftsTest extends TestCase
{
    use RefreshDatabase;

    public function test_dry_run_validates_without_writing_contacts_or_facts(): void
    {
        $site = $this->site();

        $this->artisan('site:import-commercial-profile-drafts', ['site' => $site->key, 'file' => $this->manifest()])->assertSuccessful();

        $this->assertDatabaseCount('site_contacts', 0);
        $this->assertDatabaseCount('site_commercial_facts', 0);
        $this->assertSame('dry_run_complete', ImportRun::query()->sole()->status);
    }

    public function test_apply_creates_unverified_drafts_and_is_idempotent(): void
    {
        $site = $this->site();
        $arguments = ['site' => $site->key, 'file' => $this->manifest(), '--apply' => true];

        $this->artisan('site:import-commercial-profile-drafts', $arguments)->assertSuccessful();
        $this->artisan('site:import-commercial-profile-drafts', $arguments)->assertSuccessful();

        $this->assertDatabaseCount('site_contacts', 1);
        $this->assertDatabaseCount('site_commercial_facts', 1);
        $this->assertFalse(SiteContact::query()->sole()->is_published);
        $this->assertNull(SiteContact::query()->sole()->verified_at);
        $this->assertFalse(SiteCommercialFact::query()->sole()->is_published);
        $this->assertSame(1, ImportRun::query()->latest('id')->firstOrFail()->summary['contacts_unchanged']);
        $this->assertSame(1, ImportRun::query()->latest('id')->firstOrFail()->summary['facts_unchanged']);
    }

    public function test_apply_refuses_to_overwrite_a_verified_fact_when_source_value_changes(): void
    {
        $site = $this->site();
        $fact = SiteCommercialFact::create(['site_id' => $site->id, 'locale' => 'ru-BY', 'key' => 'payment_terms', 'value' => 'Утверждённый текст.']);
        $fact->publish(User::factory()->create(['is_admin' => true]), 'Подтверждено владельцем.');

        $this->artisan('site:import-commercial-profile-drafts', ['site' => $site->key, 'file' => $this->manifest('Другой текст.'), '--apply' => true])->assertFailed();

        $this->assertSame('Утверждённый текст.', $fact->fresh()->value);
        $this->assertTrue($fact->fresh()->is_published);
        $this->assertSame('failed', ImportRun::query()->sole()->status);
    }

    private function site(): Site
    {
        $site = Site::create(['key' => 'microchips-by', 'domain' => 'microchips.by', 'country_code' => 'BY', 'currency_code' => 'BYN', 'default_locale' => 'ru-BY', 'name' => 'Microchips Беларусь', 'is_active' => true]);
        $site->locales()->create(['locale' => 'ru-BY', 'language' => 'ru', 'is_default' => true, 'is_enabled' => true]);

        return $site;
    }

    private function manifest(string $paymentTerms = 'Безналичный расчёт по счёту.'): string
    {
        $file = storage_path('framework/testing/commercial-profile-'.uniqid().'.json');
        file_put_contents($file, json_encode([
            'schema_version' => 1,
            'source' => 'Owner-approved source',
            'contacts' => [[
                'locale' => 'ru-BY', 'city' => 'Минск', 'type' => 'phone', 'label' => 'Основной телефон', 'value' => '+375 (33) 347-75-10', 'is_primary' => true,
            ]],
            'commercial_facts' => [[
                'locale' => 'ru-BY', 'key' => 'payment_terms', 'value' => $paymentTerms,
            ]],
        ], JSON_THROW_ON_ERROR | JSON_UNESCAPED_UNICODE));

        return $file;
    }
}
