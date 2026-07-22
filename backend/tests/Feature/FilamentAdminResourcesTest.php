<?php

namespace Tests\Feature;

use App\Filament\Resources\DuplicateConflicts\Pages\ListDuplicateConflicts;
use App\Filament\Resources\ImportRuns\Pages\ListImportRuns;
use App\Filament\Resources\Products\Pages\CreateProduct;
use App\Filament\Resources\Products\Pages\EditProduct;
use App\Filament\Resources\Products\Pages\ListProducts;
use App\Filament\Resources\Sites\Pages\CreateSite;
use App\Filament\Resources\Sites\Pages\EditSite;
use App\Filament\Resources\Sites\Pages\ListSites;
use App\Filament\Resources\StagedImportRecords\Pages\ListStagedImportRecords;
use App\Models\DuplicateConflict;
use App\Models\ImportRun;
use App\Models\Product;
use App\Models\Site;
use App\Models\StagedImportRecord;
use App\Models\User;
use DomainException;
use Filament\Facades\Filament;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Livewire\Livewire;
use Tests\TestCase;

class FilamentAdminResourcesTest extends TestCase
{
    use RefreshDatabase;

    protected function setUp(): void
    {
        parent::setUp();

        // Livewire component tests bypass the panel route middleware, so the
        // "current panel" must be set explicitly for Filament::getPanel()
        // calls inside resources/pages to resolve (e.g. Site::query() options,
        // resource URL generation) the same way a real /admin request would.
        Filament::setCurrentPanel(Filament::getPanel('admin'));
    }

    private function admin(): User
    {
        return User::factory()->create(['is_admin' => true]);
    }

    private function site(string $key = 'microchips-by'): Site
    {
        return Site::create([
            'key' => $key,
            'domain' => $key.'.test',
            'country_code' => 'BY',
            'currency_code' => 'BYN',
            'default_locale' => 'ru-BY',
            'name' => 'Microchips Belarus',
            'is_active' => true,
        ]);
    }

    private function importRun(): ImportRun
    {
        return ImportRun::create(['source' => '1c_csv', 'status' => 'needs_review', 'summary' => []]);
    }

    private function stagedRecord(ImportRun $run, string $status = 'ready_for_review'): StagedImportRecord
    {
        return StagedImportRecord::create([
            'import_run_id' => $run->id,
            'row_number' => 2,
            'entity_type' => 'product',
            'external_id' => '1c-alpha',
            'payload' => [
                'external_id' => '1c-alpha',
                'name' => 'Alpha Battery',
                'sku' => 'ALPHA-01',
                'voltage' => '12V',
            ],
            'normalized_payload' => [
                'external_id' => '1c-alpha',
                'name' => 'Alpha Battery',
                'sku' => 'ALPHA-01',
                'slug' => 'alpha-battery',
                'technical_attributes' => ['voltage' => '12V'],
            ],
            'validation_errors' => [],
            'status' => $status,
        ]);
    }

    // --- Panel-level authorization -------------------------------------------------

    public function test_admin_panel_dashboard_rejects_a_non_admin_user(): void
    {
        $user = User::factory()->create(['is_admin' => false]);

        $this->actingAs($user)->get('/admin')->assertForbidden();
    }

    public function test_admin_panel_dashboard_is_reachable_by_an_admin_user(): void
    {
        $this->actingAs($this->admin())->get('/admin')->assertOk();
    }

    // --- StagedImportRecordResource --------------------------------------------------

    public function test_staged_import_records_list_renders_and_shows_records(): void
    {
        $admin = $this->admin();
        $run = $this->importRun();
        $record = $this->stagedRecord($run);

        Livewire::actingAs($admin)
            ->test(ListStagedImportRecords::class)
            ->assertSuccessful()
            ->assertCanSeeTableRecords([$record]);
    }

    public function test_review_action_is_visible_only_for_ready_for_review_records(): void
    {
        $admin = $this->admin();
        $run = $this->importRun();
        $readyRecord = $this->stagedRecord($run, 'ready_for_review');
        $publishedRecord = $this->stagedRecord($run, 'published');

        Livewire::actingAs($admin)
            ->test(ListStagedImportRecords::class)
            ->assertTableActionVisible('review', $readyRecord)
            ->assertTableActionHidden('review', $publishedRecord);
    }

    public function test_review_action_marks_a_record_reviewed_and_records_the_reviewer(): void
    {
        $admin = $this->admin();
        $run = $this->importRun();
        $record = $this->stagedRecord($run);

        Livewire::actingAs($admin)
            ->test(ListStagedImportRecords::class)
            ->callTableAction('review', $record, data: ['review_note' => 'Проверено вручную.']);

        $this->assertDatabaseHas('staged_import_records', [
            'id' => $record->id,
            'status' => 'reviewed',
            'reviewed_by' => $admin->id,
            'review_note' => 'Проверено вручную.',
        ]);
    }

    public function test_review_action_is_blocked_by_an_open_duplicate_conflict(): void
    {
        $admin = $this->admin();
        $run = $this->importRun();
        $record = $this->stagedRecord($run);
        DuplicateConflict::create([
            'import_run_id' => $run->id,
            'entity_type' => 'product',
            'match_key' => 'sku:alpha-01',
            'candidate_ids' => ['staged_record_ids' => [$record->id], 'product_ids' => []],
            'status' => 'open',
        ]);

        // The action closure calls StagedProductPublisher::review() directly with no
        // try/catch, and Filament's action pipeline re-throws any non-Halt/Validation
        // exception (see vendor/filament/actions/src/Concerns/InteractsWithActions.php,
        // the `catch (Throwable $exception)` branch), so the DomainException propagates
        // out of the Livewire call rather than becoming a graceful notification.
        $this->expectException(DomainException::class);
        $this->expectExceptionMessage('Resolve the duplicate conflict');

        Livewire::actingAs($admin)
            ->test(ListStagedImportRecords::class)
            ->callTableAction('review', $record, data: ['review_note' => null]);
    }

    public function test_publish_to_site_action_is_visible_only_for_reviewed_records(): void
    {
        $admin = $this->admin();
        $run = $this->importRun();
        $readyRecord = $this->stagedRecord($run, 'ready_for_review');
        $reviewedRecord = $this->stagedRecord($run, 'reviewed');

        Livewire::actingAs($admin)
            ->test(ListStagedImportRecords::class)
            ->assertTableActionHidden('publishToSite', $readyRecord)
            ->assertTableActionVisible('publishToSite', $reviewedRecord);
    }

    public function test_publish_to_site_action_creates_the_product_and_a_draft_site_product(): void
    {
        $admin = $this->admin();
        $site = $this->site();
        $run = $this->importRun();
        $record = $this->stagedRecord($run, 'reviewed');
        $record->update(['reviewed_at' => now(), 'reviewed_by' => $admin->id]);

        Livewire::actingAs($admin)
            ->test(ListStagedImportRecords::class)
            ->callTableAction('publishToSite', $record, data: [
                'site_id' => $site->id,
                'confirmed' => true,
            ]);

        $this->assertDatabaseHas('staged_import_records', [
            'id' => $record->id,
            'status' => 'published',
            'published_by' => $admin->id,
            'published_site_id' => $site->id,
        ]);
        $this->assertDatabaseHas('products', [
            'external_id' => '1c-alpha',
            'sku' => 'ALPHA-01',
            'status' => 'active',
        ]);
        $this->assertDatabaseHas('site_products', [
            'site_id' => $site->id,
            'is_published' => false,
            'availability' => 'on_request',
        ]);
    }

    public function test_publish_to_site_action_requires_the_confirmation_checkbox(): void
    {
        $admin = $this->admin();
        $site = $this->site();
        $run = $this->importRun();
        $record = $this->stagedRecord($run, 'reviewed');
        $record->update(['reviewed_at' => now(), 'reviewed_by' => $admin->id]);

        Livewire::actingAs($admin)
            ->test(ListStagedImportRecords::class)
            ->callTableAction('publishToSite', $record, data: [
                'site_id' => $site->id,
                'confirmed' => false,
            ])
            ->assertHasTableActionErrors(['confirmed']);

        $this->assertDatabaseHas('staged_import_records', [
            'id' => $record->id,
            'status' => 'reviewed',
        ]);
    }

    // --- ImportRunResource -----------------------------------------------------------

    public function test_import_runs_list_renders_and_shows_the_run(): void
    {
        $run = ImportRun::create([
            'source' => '1c_csv',
            'status' => 'needs_review',
            'source_file' => 'export.csv',
            'total_records' => 3,
            'summary' => ['ready_for_review' => 1, 'invalid' => 1, 'duplicate_conflicts' => 1],
        ]);

        Livewire::actingAs($this->admin())
            ->test(ListImportRuns::class)
            ->assertSuccessful()
            ->assertCanSeeTableRecords([$run]);
    }

    // --- DuplicateConflictResource -----------------------------------------------------

    public function test_duplicate_conflicts_list_renders_when_there_are_no_conflicts(): void
    {
        Livewire::actingAs($this->admin())
            ->test(ListDuplicateConflicts::class)
            ->assertSuccessful()
            ->assertCountTableRecords(0);
    }

    public function test_duplicate_conflicts_list_renders_the_candidate_ids(): void
    {
        // Regression: the candidate_ids array columns used to crash the list — a dot
        // path to the array made Filament iterate the state per item and pass an int
        // to a ?array formatter (TypeError). The columns now compute the whole cell
        // via state(), so a conflict with candidate ids renders instead of crashing.
        $run = $this->importRun();
        $record = $this->stagedRecord($run);
        DuplicateConflict::create([
            'import_run_id' => $run->id,
            'entity_type' => 'product',
            'match_key' => 'sku:alpha-01',
            'candidate_ids' => ['staged_record_ids' => [$record->id], 'product_ids' => []],
            'status' => 'open',
        ]);

        Livewire::actingAs($this->admin())->test(ListDuplicateConflicts::class)
            ->assertOk()
            ->assertSee('sku:alpha-01')
            ->assertSee((string) $record->id);
    }

    // --- ProductResource ---------------------------------------------------------------

    public function test_products_list_renders_and_shows_the_product(): void
    {
        $product = Product::create([
            'external_id' => '1c-alpha',
            'slug' => 'alpha-battery',
            'name' => 'Alpha Battery',
            'sku' => 'ALPHA-01',
            'status' => 'active',
        ]);

        Livewire::actingAs($this->admin())
            ->test(ListProducts::class)
            ->assertSuccessful()
            ->assertCanSeeTableRecords([$product]);
    }

    public function test_product_can_be_created_through_the_admin_form(): void
    {
        Livewire::actingAs($this->admin())
            ->test(CreateProduct::class)
            ->fillForm([
                'name' => 'Beta Battery',
                'slug' => 'beta-battery',
                'external_id' => 'manual-beta',
                'sku' => 'BETA-02',
                'status' => 'draft',
            ])
            ->call('create')
            ->assertHasNoFormErrors();

        $this->assertDatabaseHas('products', [
            'slug' => 'beta-battery',
            'name' => 'Beta Battery',
            'status' => 'draft',
        ]);
    }

    public function test_product_edit_form_loads_and_saves_an_existing_record(): void
    {
        $product = Product::create([
            'external_id' => '1c-alpha',
            'slug' => 'alpha-battery',
            'name' => 'Alpha Battery',
            'sku' => 'ALPHA-01',
            'status' => 'draft',
        ]);

        Livewire::actingAs($this->admin())
            ->test(EditProduct::class, ['record' => $product->getRouteKey()])
            ->assertSchemaStateSet([
                'name' => 'Alpha Battery',
                'slug' => 'alpha-battery',
            ])
            ->fillForm(['status' => 'active'])
            ->call('save')
            ->assertHasNoFormErrors();

        $this->assertDatabaseHas('products', [
            'id' => $product->id,
            'status' => 'active',
        ]);
    }

    // --- SiteResource --------------------------------------------------------------------

    public function test_sites_list_renders_and_shows_the_site(): void
    {
        $site = $this->site();

        Livewire::actingAs($this->admin())
            ->test(ListSites::class)
            ->assertSuccessful()
            ->assertCanSeeTableRecords([$site]);
    }

    public function test_site_can_be_created_through_the_admin_form(): void
    {
        Livewire::actingAs($this->admin())
            ->test(CreateSite::class)
            ->fillForm([
                'key' => 'microchips-ru',
                'domain' => 'microchips.ru',
                'country_code' => 'RU',
                'currency_code' => 'RUB',
                'default_locale' => 'ru-RU',
                'name' => 'Microchips Russia',
            ])
            ->call('create')
            ->assertHasNoFormErrors();

        $this->assertDatabaseHas('sites', [
            'key' => 'microchips-ru',
            'domain' => 'microchips.ru',
        ]);
    }

    public function test_site_edit_form_loads_and_saves_an_existing_record(): void
    {
        $site = $this->site();

        Livewire::actingAs($this->admin())
            ->test(EditSite::class, ['record' => $site->getRouteKey()])
            ->assertSchemaStateSet([
                'key' => 'microchips-by',
                'domain' => 'microchips-by.test',
            ])
            ->fillForm(['is_active' => false])
            ->call('save')
            ->assertHasNoFormErrors();

        $this->assertDatabaseHas('sites', [
            'id' => $site->id,
            'is_active' => false,
        ]);
    }
}
