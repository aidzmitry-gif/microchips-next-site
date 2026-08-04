<?php

namespace Tests\Feature;

use App\Filament\Resources\Leads\Pages\ListLeads;
use App\Filament\Resources\Leads\Pages\ViewLead;
use App\Models\Lead;
use App\Models\Site;
use App\Models\User;
use Filament\Facades\Filament;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Livewire\Livewire;
use Tests\TestCase;

class LeadResourceTest extends TestCase
{
    use RefreshDatabase;

    protected function setUp(): void
    {
        parent::setUp();

        Filament::setCurrentPanel(Filament::getPanel('admin'));
    }

    public function test_an_admin_can_review_a_lead_and_its_crm_error_without_editing_it(): void
    {
        $admin = User::factory()->create(['is_admin' => true]);
        $lead = $this->lead();

        Livewire::actingAs($admin)
            ->test(ListLeads::class)
            ->assertSuccessful()
            ->assertCanSeeTableRecords([$lead])
            ->assertTableActionVisible('view', $lead);

        Livewire::actingAs($admin)
            ->test(ViewLead::class, ['record' => $lead->getRouteKey()])
            ->assertSuccessful()
            ->assertSee('ООО Тест')
            ->assertSee('Bitrix24 integration is not enabled for this site.');
    }

    public function test_an_admin_can_process_and_close_a_local_inbox_lead_with_an_audit_note(): void
    {
        $admin = User::factory()->create(['is_admin' => true]);
        $lead = $this->lead();

        Livewire::actingAs($admin)
            ->test(ListLeads::class)
            ->callTableAction('startProcessing', $lead, ['internal_note' => 'Перезвонить после проверки ТЗ.']);

        $this->assertDatabaseHas('leads', [
            'id' => $lead->id,
            'status' => 'in_progress',
            'handled_by' => $admin->id,
            'internal_note' => 'Перезвонить после проверки ТЗ.',
        ]);
        $this->assertNotNull($lead->fresh()->handled_at);

        Livewire::actingAs($admin)
            ->test(ListLeads::class)
            ->callTableAction('closeLead', $lead->fresh(), ['internal_note' => 'КП отправлено на e-mail.']);

        $this->assertDatabaseHas('leads', [
            'id' => $lead->id,
            'status' => 'closed',
            'handled_by' => $admin->id,
            'internal_note' => 'КП отправлено на e-mail.',
        ]);
    }

    private function lead(): Lead
    {
        $site = Site::create(['key' => 'microchips-by', 'domain' => 'microchips.by', 'country_code' => 'BY', 'currency_code' => 'BYN', 'default_locale' => 'ru-BY', 'name' => 'Microchips Беларусь', 'is_active' => true]);

        return Lead::create([
            'site_id' => $site->id,
            'locale' => 'ru-BY',
            'type' => 'quote',
            'status' => 'new',
            'company' => 'ООО Тест',
            'contact_name' => 'Иван Иванов',
            'email' => 'ivan@example.test',
            'page_url' => 'https://microchips.by/catalog/test',
            'cart' => [['sku' => 'TEST-1', 'quantity' => 1]],
            'utm' => ['utm_source' => 'test'],
            'external_error' => 'Bitrix24 integration is not enabled for this site.',
        ]);
    }
}
