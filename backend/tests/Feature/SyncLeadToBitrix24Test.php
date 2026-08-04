<?php

namespace Tests\Feature;

use App\Jobs\SyncLeadToBitrix24;
use App\Models\Lead;
use App\Models\Site;
use App\Models\SiteIntegration;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Http\Client\RequestException;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Http;
use Tests\TestCase;

class SyncLeadToBitrix24Test extends TestCase
{
    use RefreshDatabase;

    private const WEBHOOK_URL = 'https://example.bitrix24.by/rest/1/testtoken/crm.lead.add.json';

    public function test_a_successful_response_stores_the_external_id_and_clears_the_error(): void
    {
        Http::fake([
            self::WEBHOOK_URL => Http::response(['result' => 4821], 200),
        ]);

        $site = $this->site();
        $this->integration($site);
        $lead = $this->lead($site, ['external_error' => 'previous failure']);

        (new SyncLeadToBitrix24($lead))->handle();

        Http::assertSent(function ($request) {
            return $request->url() === self::WEBHOOK_URL
                && $request['fields']['COMPANY_TITLE'] === 'ООО Тест'
                && $request['fields']['UF_CRM_SITE_KEY'] === 'microchips-by';
        });

        $this->assertDatabaseHas('leads', [
            'id' => $lead->id,
            'external_id' => '4821',
            'external_error' => null,
        ]);
    }

    public function test_a_failing_response_records_the_error_and_rethrows_for_retry(): void
    {
        Http::fake([
            self::WEBHOOK_URL => Http::response(['error' => 'Internal Server Error'], 500),
        ]);

        $site = $this->site();
        $this->integration($site);
        $lead = $this->lead($site);

        try {
            (new SyncLeadToBitrix24($lead))->handle();
            $this->fail('The job must rethrow the HTTP failure so the queue can retry it.');
        } catch (RequestException $exception) {
            $this->assertSame(500, $exception->response->status());
        }

        $lead->refresh();
        $this->assertNotNull($lead->external_error);
        $this->assertNull($lead->external_id);
    }

    public function test_an_http_success_without_a_valid_bitrix_lead_id_records_an_error_and_retries(): void
    {
        Http::fake([
            self::WEBHOOK_URL => Http::response(['error' => 'INVALID_CREDENTIALS'], 200),
        ]);

        $site = $this->site();
        $this->integration($site);
        $lead = $this->lead($site);

        try {
            (new SyncLeadToBitrix24($lead))->handle();
            $this->fail('A Bitrix24 response without a valid lead ID must not be treated as a successful sync.');
        } catch (\RuntimeException $exception) {
            $this->assertSame('Bitrix24 did not return a valid lead ID: INVALID_CREDENTIALS', $exception->getMessage());
        }

        $this->assertDatabaseHas('leads', [
            'id' => $lead->id,
            'external_id' => null,
            'external_error' => 'Bitrix24 did not return a valid lead ID: INVALID_CREDENTIALS',
        ]);
    }

    public function test_an_unconfigured_integration_is_visible_on_the_persisted_lead(): void
    {
        $site = $this->site();
        $lead = $this->lead($site);

        Http::fake();
        (new SyncLeadToBitrix24($lead))->handle();

        Http::assertNothingSent();
        $this->assertDatabaseHas('leads', [
            'id' => $lead->id,
            'external_id' => null,
            'external_error' => 'Bitrix24 integration is not enabled for this site.',
        ]);
    }

    public function test_it_never_posts_to_a_legacy_or_tampered_non_bitrix_webhook_url(): void
    {
        $site = $this->site();
        $lead = $this->lead($site);
        DB::table('site_integrations')->insert([
            'site_id' => $site->id,
            'driver' => 'bitrix24',
            'settings' => json_encode(['webhook_url' => 'https://127.0.0.1/rest/1/token/crm.lead.add.json']),
            'is_enabled' => true,
            'created_at' => now(),
            'updated_at' => now(),
        ]);

        Http::fake();
        (new SyncLeadToBitrix24($lead))->handle();

        Http::assertNothingSent();
        $this->assertSame('Bitrix24 integration has an invalid webhook URL.', $lead->fresh()->external_error);
    }

    private function site(): Site
    {
        return Site::create([
            'key' => 'microchips-by',
            'domain' => 'microchips.by',
            'country_code' => 'BY',
            'currency_code' => 'BYN',
            'default_locale' => 'ru-BY',
            'name' => 'Microchips Belarus',
            'is_active' => true,
        ]);
    }

    private function integration(Site $site): SiteIntegration
    {
        return SiteIntegration::create([
            'site_id' => $site->id,
            'driver' => 'bitrix24',
            'settings' => ['webhook_url' => self::WEBHOOK_URL],
            'is_enabled' => true,
        ]);
    }

    private function lead(Site $site, array $overrides = []): Lead
    {
        return Lead::create(array_merge([
            'site_id' => $site->id,
            'locale' => 'ru-BY',
            'type' => 'quote',
            'company' => 'ООО Тест',
            'contact_name' => 'Иван Иванов',
            'email' => 'ivan@example.test',
            'phone' => '+375291234567',
            'message' => 'Аккумуляторы для ИБП',
            'page_url' => 'https://microchips.by/catalog/alpha-battery',
            'cart' => [['sku' => 'ALPHA-01', 'quantity' => 2]],
            'utm' => ['utm_source' => 'google'],
            'status' => 'new',
        ], $overrides));
    }
}
