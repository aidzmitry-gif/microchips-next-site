<?php

namespace Tests\Feature;

use App\Models\Site;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class LeadBatteryPackDesignTest extends TestCase
{
    use RefreshDatabase;

    public function test_battery_pack_design_lead_is_created_with_correct_type_and_site(): void
    {
        $site = $this->site('microchips-by', 'microchips.by', 'BY', 'BYN', 'ru-BY');

        $this->postJson('/api/v1/leads/battery-pack-design', [
            'site_key' => 'microchips-by',
            'locale' => 'ru-BY',
            'company' => 'ООО Тест',
            'contact_name' => 'Иван Иванов',
            'email' => 'ivan@example.test',
            'page_url' => 'https://microchips.by/battery-pack-design',
            'message' => 'Нужен кастомный аккумуляторный пакет',
        ])
            ->assertCreated()
            ->assertJsonPath('status', 'accepted');

        $this->assertDatabaseHas('leads', [
            'site_id' => $site->id,
            'locale' => 'ru-BY',
            'type' => 'battery_pack_design',
            'company' => 'ООО Тест',
            'contact_name' => 'Иван Иванов',
            'page_url' => 'https://microchips.by/battery-pack-design',
        ]);
    }

    public function test_battery_pack_design_lead_rejects_missing_required_fields(): void
    {
        $this->site('microchips-by', 'microchips.by', 'BY', 'BYN', 'ru-BY');

        $this->postJson('/api/v1/leads/battery-pack-design', [
            'site_key' => 'microchips-by',
        ])
            ->assertUnprocessable()
            ->assertJsonValidationErrors([
                'company',
                'contact_name',
                'email',
                'phone',
                'page_url',
            ]);
    }

    private function site(string $key, string $domain, string $country, string $currency, string $locale): Site
    {
        return Site::create([
            'key' => $key,
            'domain' => $domain,
            'country_code' => $country,
            'currency_code' => $currency,
            'default_locale' => $locale,
            'name' => $key,
            'is_active' => true,
        ]);
    }
}
