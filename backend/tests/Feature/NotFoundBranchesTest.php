<?php

namespace Tests\Feature;

use App\Models\Site;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class NotFoundBranchesTest extends TestCase
{
    use RefreshDatabase;

    public function test_resolve_site_path_returns_404_for_unknown_host(): void
    {
        $this->getJson('/api/v1/sites/unknown-host.example/resolve?path=/')
            ->assertNotFound()
            ->assertJsonPath('message', 'Site not found.');
    }

    public function test_catalog_index_returns_404_for_unknown_site_key(): void
    {
        $this->getJson('/api/v1/sites/unknown-site-key/catalog/products')
            ->assertNotFound();
    }

    public function test_catalog_index_returns_404_for_inactive_site_key(): void
    {
        $this->site('microchips-by', 'microchips.by', 'BY', 'BYN', 'ru-BY', false);

        $this->getJson('/api/v1/sites/microchips-by/catalog/products')
            ->assertNotFound();
    }

    public function test_lead_quote_returns_404_when_site_is_not_found(): void
    {
        $this->postJson('/api/v1/leads/quote', [
            'site_key' => 'unknown-site-key',
            'company' => 'ООО Тест',
            'contact_name' => 'Иван Иванов',
            'email' => 'ivan@example.test',
            'page_url' => 'https://microchips.by/catalog/alpha-battery',
        ])
            ->assertNotFound();
    }

    public function test_lead_quote_returns_422_when_required_fields_are_missing_before_site_lookup(): void
    {
        $this->postJson('/api/v1/leads/quote', [])
            ->assertUnprocessable()
            ->assertJsonValidationErrors([
                'site_key',
                'company',
                'contact_name',
                'page_url',
            ]);
    }

    private function site(string $key, string $domain, string $country, string $currency, string $locale, bool $isActive = true): Site
    {
        return Site::create([
            'key' => $key,
            'domain' => $domain,
            'country_code' => $country,
            'currency_code' => $currency,
            'default_locale' => $locale,
            'name' => $key,
            'is_active' => $isActive,
        ]);
    }
}
