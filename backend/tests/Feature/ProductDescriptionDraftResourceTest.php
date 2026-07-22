<?php

namespace Tests\Feature;

use App\Domain\Content\ProductDescriptionDrafter;
use App\Filament\Resources\ProductDescriptionDrafts\Pages\ListProductDescriptionDrafts;
use App\Filament\Resources\ProductDescriptionDrafts\Pages\ViewProductDescriptionDraft;
use App\Models\ProductDescriptionDraft;
use App\Models\User;
use Filament\Facades\Filament;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Livewire\Livewire;
use Tests\TestCase;

class ProductDescriptionDraftResourceTest extends TestCase
{
    use RefreshDatabase;

    protected function setUp(): void
    {
        parent::setUp();

        Filament::setCurrentPanel(Filament::getPanel('admin'));
    }

    public function test_list_and_read_only_view_render_the_draft_and_provenance(): void
    {
        $admin = User::factory()->create(['is_admin' => true]);
        $draft = $this->draft();

        Livewire::actingAs($admin)
            ->test(ListProductDescriptionDrafts::class)
            ->assertSuccessful()
            ->assertCanSeeTableRecords([$draft])
            ->assertTableActionVisible('view', $draft)
            ->assertTableActionVisible('submitForReview', $draft);

        Livewire::actingAs($admin)
            ->test(ViewProductDescriptionDraft::class, ['record' => $draft->getRouteKey()])
            ->assertSuccessful()
            ->assertSee($draft->title)
            ->assertSee('https://example.test/catalog/a');
    }

    public function test_submit_action_moves_only_a_draft_to_review_and_records_the_admin(): void
    {
        $admin = User::factory()->create(['is_admin' => true]);
        $draft = $this->draft();

        Livewire::actingAs($admin)
            ->test(ListProductDescriptionDrafts::class)
            ->callTableAction('submitForReview', $draft);

        $this->assertDatabaseHas('product_description_drafts', [
            'id' => $draft->id,
            'status' => 'review',
            'submitted_by' => $admin->id,
        ]);
        $this->assertDatabaseCount('products', 0);

        Livewire::actingAs($admin)
            ->test(ListProductDescriptionDrafts::class)
            ->assertTableActionHidden('submitForReview', $draft->refresh());
    }

    private function draft(): ProductDescriptionDraft
    {
        return app(ProductDescriptionDrafter::class)->createDraft([
            'name' => 'Battery A',
            'technology' => 'AGM',
            'technical_attributes' => ['voltage' => '12 V'],
        ], ['https://example.test/catalog/a']);
    }
}
