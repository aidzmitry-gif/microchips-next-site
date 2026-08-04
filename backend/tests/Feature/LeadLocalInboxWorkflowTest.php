<?php

namespace Tests\Feature;

use App\Models\Lead;
use App\Models\Site;
use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class LeadLocalInboxWorkflowTest extends TestCase
{
    use RefreshDatabase;

    public function test_closing_a_local_lead_requires_a_nonblank_outcome_note(): void
    {
        $lead = $this->lead();

        $this->expectException(\InvalidArgumentException::class);
        $lead->close(User::factory()->create(['is_admin' => true]), ' ');
    }

    public function test_processing_assigns_an_operator_without_changing_customer_facts(): void
    {
        $lead = $this->lead();
        $operator = User::factory()->create(['is_admin' => true]);

        $lead->startProcessing($operator, 'Проверяю совместимость.');

        $this->assertSame('in_progress', $lead->fresh()->status);
        $this->assertSame($operator->id, $lead->fresh()->handled_by);
        $this->assertSame('ООО Тест', $lead->fresh()->company);
        $this->assertSame('ivan@example.test', $lead->fresh()->email);
    }

    private function lead(): Lead
    {
        $site = Site::create(['key' => 'microchips-by', 'domain' => 'microchips.by', 'country_code' => 'BY', 'currency_code' => 'BYN', 'default_locale' => 'ru-BY', 'name' => 'Microchips Беларусь', 'is_active' => true]);

        return Lead::create([
            'site_id' => $site->id, 'locale' => 'ru-BY', 'type' => 'quote', 'status' => 'new',
            'company' => 'ООО Тест', 'contact_name' => 'Иван Иванов', 'email' => 'ivan@example.test',
            'page_url' => 'https://microchips.by/catalog/test',
        ]);
    }
}
