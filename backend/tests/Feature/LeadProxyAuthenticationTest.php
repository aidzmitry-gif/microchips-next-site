<?php

namespace Tests\Feature;

use App\Models\Site;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class LeadProxyAuthenticationTest extends TestCase
{
    use RefreshDatabase;

    public function test_direct_lead_requests_cannot_bypass_the_application_proxy_with_rotating_rate_keys(): void
    {
        Site::create([
            'key' => 'microchips-by',
            'domain' => 'microchips.by',
            'country_code' => 'BY',
            'currency_code' => 'BYN',
            'default_locale' => 'ru-BY',
            'name' => 'Microchips',
            'is_active' => true,
        ]);

        for ($attempt = 0; $attempt < 12; $attempt++) {
            $this->withoutHeader('X-Lead-Proxy-Secret')
                ->withHeader('X-Lead-Rate-Key', sprintf('00000000-0000-4000-8000-%012d', $attempt))
                ->postJson('/api/v1/leads/quote', $this->validPayload())
                ->assertForbidden();
        }

        $this->assertDatabaseCount('leads', 0);
    }

    public function test_proxy_authenticated_lead_request_is_accepted(): void
    {
        Site::create([
            'key' => 'microchips-by',
            'domain' => 'microchips.by',
            'country_code' => 'BY',
            'currency_code' => 'BYN',
            'default_locale' => 'ru-BY',
            'name' => 'Microchips',
            'is_active' => true,
        ]);

        $this->postJson('/api/v1/leads/quote', $this->validPayload())->assertCreated();
    }

    /** @return array<string, string> */
    private function validPayload(): array
    {
        return [
            'site_key' => 'microchips-by',
            'company' => 'Test company',
            'contact_name' => 'Test contact',
            'email' => 'contact@example.test',
            'page_url' => 'https://microchips.by/catalog/battery',
        ];
    }
}
