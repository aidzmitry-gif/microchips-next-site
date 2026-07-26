<?php

namespace Tests\Feature;

use App\Domain\Imports\IdentityCandidateReviewer;
use App\Filament\Resources\CatalogIdentityCandidates\Pages\ListCatalogIdentityCandidates;
use App\Models\CatalogIdentityCandidate;
use App\Models\ImportRun;
use App\Models\OneCNomenclatureItem;
use App\Models\Product;
use App\Models\User;
use Filament\Facades\Filament;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Artisan;
use Illuminate\Validation\ValidationException;
use Livewire\Livewire;
use Tests\TestCase;

class CatalogIdentityCandidateWorkflowTest extends TestCase
{
    use RefreshDatabase;

    protected function setUp(): void
    {
        parent::setUp();

        Filament::setCurrentPanel(Filament::getPanel('admin'));
    }

    public function test_command_imports_strict_matches_into_review_batches_without_creating_products(): void
    {
        $this->inventoryItem('one-c-1', 'Первый товар');
        $this->inventoryItem('one-c-2', 'Второй товар');
        $this->inventoryItem('one-c-3', 'Третий товар');
        $file = $this->candidateCsv([
            $this->candidateRow('101', 'Товар Bitrix 1', 'one-c-1'),
            $this->candidateRow('102', 'Товар Bitrix 2', 'one-c-2'),
            $this->candidateRow('103', 'Товар Bitrix 3', 'one-c-3'),
        ]);

        $exitCode = Artisan::call('catalog:import-identity-candidates', [
            'file' => $file,
            '--initial-batch' => 2,
        ]);

        $this->assertSame(0, $exitCode);
        $this->assertDatabaseCount('catalog_identity_candidates', 3);
        $this->assertDatabaseCount('products', 0);
        $this->assertSame(2, CatalogIdentityCandidate::query()->where('review_batch', 'rb-initial-2')->count());
        $this->assertSame(1, CatalogIdentityCandidate::query()->where('review_batch', 'rb-backlog')->count());
        $this->assertDatabaseHas('import_runs', [
            'source' => 'bitrix_1c_identity_candidates',
            'status' => 'review_queue_ready',
            'total_records' => 3,
            'processed_records' => 3,
            'failed_records' => 0,
        ]);
    }

    public function test_command_marks_the_run_for_review_when_inventory_identity_is_missing(): void
    {
        $file = $this->candidateCsv([$this->candidateRow('101', 'Товар Bitrix', 'missing-one-c')]);

        $this->assertSame(0, Artisan::call('catalog:import-identity-candidates', ['file' => $file]));

        $this->assertDatabaseCount('catalog_identity_candidates', 0);
        $this->assertDatabaseHas('import_runs', [
            'source' => 'bitrix_1c_identity_candidates',
            'status' => 'needs_review',
            'failed_records' => 1,
        ]);
    }

    public function test_reviewer_requires_a_real_unique_identity_and_never_creates_a_product(): void
    {
        $reviewer = User::factory()->create(['is_admin' => true]);
        $first = $this->candidate('101', 'one-c-1');
        $second = $this->candidate('102', 'one-c-2');
        $service = app(IdentityCandidateReviewer::class);

        try {
            $service->approve($first, $reviewer, []);
            $this->fail('Approval without SKU or MPN must fail.');
        } catch (ValidationException $error) {
            $this->assertArrayHasKey('identifier', $error->errors());
        }

        $approved = $service->approve($first->fresh(), $reviewer, [
            'confirmed_mpn' => 'Fiamm 12-FGL-120',
            'confirmed_manufacturer' => 'Fiamm',
        ]);
        $this->assertSame('approved_for_staging', $approved->review_status);
        $this->assertSame('fiamm12fgl120', $approved->confirmed_mpn_normalized);
        $this->assertSame($reviewer->id, $approved->reviewed_by);

        try {
            $service->approve($second, $reviewer, ['confirmed_sku' => 'FIAMM-12 FGL 120']);
            $this->fail('Cross-field duplicate SKU/MPN must fail.');
        } catch (ValidationException $error) {
            $this->assertArrayHasKey('identifier', $error->errors());
        }

        Product::create([
            'external_id' => 'catalog-product-1',
            'sku' => 'EXISTING-001',
            'slug' => 'existing-product-1',
            'name' => 'Существующий товар',
            'status' => 'active',
        ]);
        try {
            $service->approve($second->fresh(), $reviewer, ['confirmed_mpn' => 'existing 001']);
            $this->fail('Identity already used by a catalog product must fail.');
        } catch (ValidationException $error) {
            $this->assertArrayHasKey('identifier', $error->errors());
        }

        $this->assertDatabaseCount('products', 1);
    }

    public function test_filament_actions_approve_and_reject_pending_candidates(): void
    {
        $admin = User::factory()->create(['is_admin' => true]);
        $approved = $this->candidate('101', 'one-c-1');
        $rejected = $this->candidate('102', 'one-c-2');

        Livewire::actingAs($admin)
            ->test(ListCatalogIdentityCandidates::class)
            ->assertSuccessful()
            ->assertCanSeeTableRecords([$approved, $rejected])
            ->callTableAction('approveIdentity', $approved, data: [
                'confirmed_sku' => 'SKU-101',
                'confirmed_mpn' => null,
                'confirmed_manufacturer' => 'Fiamm',
                'confirmed_category' => 'AGM',
                'review_note' => 'Проверено по первичному источнику.',
            ])
            ->callTableAction('rejectIdentity', $rejected, data: [
                'review_note' => 'Соответствие не подтверждено.',
            ]);

        $this->assertDatabaseHas('catalog_identity_candidates', [
            'id' => $approved->id,
            'review_status' => 'approved_for_staging',
            'confirmed_sku_normalized' => 'sku101',
            'reviewed_by' => $admin->id,
        ]);
        $this->assertDatabaseHas('catalog_identity_candidates', [
            'id' => $rejected->id,
            'review_status' => 'rejected',
            'reviewed_by' => $admin->id,
        ]);
    }

    public function test_export_contains_only_approved_candidates_and_does_not_stage_them(): void
    {
        $reviewer = User::factory()->create(['is_admin' => true]);
        $approved = $this->candidate('101', 'one-c-1');
        $this->candidate('102', 'one-c-2');
        app(IdentityCandidateReviewer::class)->approve($approved, $reviewer, [
            'confirmed_sku' => 'SKU-101',
            'confirmed_manufacturer' => 'Fiamm',
        ]);
        $output = storage_path('framework/testing/approved-identities.csv');
        if (is_file($output)) {
            unlink($output);
        }

        $this->assertSame(0, Artisan::call('catalog:export-approved-identities', ['output' => $output]));

        $contents = file_get_contents($output);
        $this->assertIsString($contents);
        $this->assertStringContainsString('external_id;name;sku;mpn;manufacturer', $contents);
        $this->assertStringContainsString('one-c-1;', $contents);
        $this->assertStringNotContainsString('one-c-2;', $contents);
        $this->assertDatabaseCount('staged_import_records', 0);
        $this->assertDatabaseCount('products', 0);
        unlink($output);
    }

    public function test_export_warns_when_approved_candidates_exist_in_other_batches(): void
    {
        $reviewer = User::factory()->create(['is_admin' => true]);
        $initial = $this->candidate('101', 'one-c-1', 'rb-initial-50');
        $backlogA = $this->candidate('201', 'one-c-2', 'rb-backlog');
        $backlogB = $this->candidate('202', 'one-c-3', 'rb-backlog');
        $service = app(IdentityCandidateReviewer::class);
        $service->approve($initial, $reviewer, ['confirmed_sku' => 'SKU-101']);
        $service->approve($backlogA, $reviewer, ['confirmed_sku' => 'SKU-201']);
        $service->approve($backlogB, $reviewer, ['confirmed_sku' => 'SKU-202']);

        $output = storage_path('framework/testing/approved-identities-'.uniqid().'.csv');

        $exitCode = Artisan::call('catalog:export-approved-identities', [
            'output' => $output,
            '--batch' => 'rb-initial-50',
        ]);
        $consoleOutput = Artisan::output();

        $this->assertSame(0, $exitCode);
        $this->assertStringContainsString('2 approved candidate(s) in other batch(es) were NOT exported', $consoleOutput);
        $this->assertStringContainsString('rb-backlog (2)', $consoleOutput);
        $this->assertStringContainsString('--batch=all', $consoleOutput);

        $contents = file_get_contents($output);
        $this->assertIsString($contents);
        $this->assertStringContainsString('external_id;name;sku;mpn;manufacturer;review_batch', $contents);
        $this->assertStringContainsString('one-c-1;', $contents);
        $this->assertStringNotContainsString('one-c-2;', $contents);
        $this->assertStringNotContainsString('one-c-3;', $contents);
        unlink($output);
    }

    public function test_export_batch_all_exports_every_approved_candidate(): void
    {
        $reviewer = User::factory()->create(['is_admin' => true]);
        $initial = $this->candidate('101', 'one-c-1', 'rb-initial-50');
        $backlogA = $this->candidate('201', 'one-c-2', 'rb-backlog');
        $backlogB = $this->candidate('202', 'one-c-3', 'rb-backlog');
        $pending = $this->candidate('301', 'one-c-4', 'rb-backlog');
        $service = app(IdentityCandidateReviewer::class);
        $service->approve($initial, $reviewer, ['confirmed_sku' => 'SKU-101']);
        $service->approve($backlogA, $reviewer, ['confirmed_sku' => 'SKU-201']);
        $service->approve($backlogB, $reviewer, ['confirmed_sku' => 'SKU-202']);
        // $pending stays 'pending' and must not be exported even with --batch=all.

        $output = storage_path('framework/testing/approved-identities-'.uniqid().'.csv');

        $exitCode = Artisan::call('catalog:export-approved-identities', [
            'output' => $output,
            '--batch' => 'all',
        ]);
        $consoleOutput = Artisan::output();

        $this->assertSame(0, $exitCode);
        $this->assertStringNotContainsString('were NOT exported', $consoleOutput);
        $this->assertStringContainsString('Exported 3 approved candidates from all batches', $consoleOutput);

        $contents = file_get_contents($output);
        $this->assertIsString($contents);
        $this->assertStringContainsString('one-c-1;', $contents);
        $this->assertStringContainsString('one-c-2;', $contents);
        $this->assertStringContainsString('one-c-3;', $contents);
        $this->assertStringNotContainsString('one-c-4;', $contents);
        unlink($output);

        $this->assertSame($pending->fresh()->review_status, 'pending');
    }

    public function test_export_with_no_approved_candidates_anywhere_keeps_existing_behavior(): void
    {
        $this->candidate('101', 'one-c-1', 'rb-initial-50');
        $this->candidate('201', 'one-c-2', 'rb-backlog');
        $output = storage_path('framework/testing/approved-identities-'.uniqid().'.csv');

        $exitCode = Artisan::call('catalog:export-approved-identities', ['output' => $output]);
        $consoleOutput = Artisan::output();

        $this->assertSame(0, $exitCode);
        $this->assertStringContainsString('No approved candidates found; no file was written.', $consoleOutput);
        $this->assertStringNotContainsString('were NOT exported', $consoleOutput);
        $this->assertFileDoesNotExist($output);
    }

    private function inventoryItem(string $externalId, string $name): OneCNomenclatureItem
    {
        $run = ImportRun::create(['source' => '1c_csv', 'status' => 'inventory_ready', 'summary' => []]);

        return OneCNomenclatureItem::create([
            'import_run_id' => $run->id,
            'source_key' => '1c_nomenclature',
            'external_id' => $externalId,
            'is_group' => false,
            'name' => $name,
            'classification_status' => 'needs_identity_review',
            'source_payload' => ['Код' => $externalId],
            'source_checksum' => hash('sha256', $externalId),
        ]);
    }

    private function candidate(string $legacyId, string $externalId, string $batch = 'rb-initial-50'): CatalogIdentityCandidate
    {
        $item = $this->inventoryItem($externalId, "Товар 1С {$externalId}");
        $run = ImportRun::create(['source' => 'bitrix_1c_identity_candidates', 'status' => 'review_queue_ready', 'summary' => []]);

        return CatalogIdentityCandidate::create([
            'import_run_id' => $run->id,
            'one_c_nomenclature_item_id' => $item->id,
            'legacy_source' => 'bitrix',
            'legacy_id' => $legacyId,
            'legacy_name' => "Товар Bitrix {$legacyId}",
            'review_priority' => (int) $legacyId,
            'review_batch' => $batch,
            'confidence' => '0.9500',
            'match_method' => 'sig+brand',
            'review_status' => 'pending',
            'source_payload' => ['Bitrix ID' => $legacyId],
            'source_checksum' => hash('sha256', $legacyId),
        ]);
    }

    /** @param list<list<string>> $rows */
    private function candidateCsv(array $rows): string
    {
        $file = storage_path('framework/testing/identity-candidates-'.uniqid().'.csv');
        $handle = fopen($file, 'wb');
        $this->assertNotFalse($handle);
        fputcsv($handle, [
            'Bitrix ID', 'Название сайта', 'Бренд', '1С-код', '1С-Артикул', '1С-Наименование',
            'signature', 'brand_ok', 'confidence', 'method', '1С-код(было Cursor)', 'сравнение',
            'queue_status', 'review_required', 'selection_rule_version',
        ], ',', '"', '');
        foreach ($rows as $row) {
            fputcsv($handle, $row, ',', '"', '');
        }
        fclose($handle);

        return $file;
    }

    /** @return list<string> */
    private function candidateRow(string $legacyId, string $legacyName, string $externalId): array
    {
        return [
            $legacyId, $legacyName, 'Fiamm', $externalId, '', "Товар 1С {$externalId}",
            'FIAMMTEST', 'yes', '0.95', 'sig+brand', '', 'differ',
            'review_candidate', 'yes', 'rb-1c-review-v1',
        ];
    }
}
