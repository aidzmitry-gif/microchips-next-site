<?php

namespace Tests\Feature;

use App\Models\CatalogIdentityCandidate;
use App\Models\ImportRun;
use App\Models\OneCNomenclatureItem;
use App\Models\Product;
use App\Models\Site;
use App\Models\SiteProduct;
use App\Models\StagedImportRecord;
use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class ApplyBitrixIdentityReviewDecisionsTest extends TestCase
{
    use RefreshDatabase;

    public function test_applies_only_confirmed_relation_evidence_and_replays_idempotently(): void
    {
        $admin = User::factory()->create(['is_admin' => true]);
        $site = Site::query()->create([
            'key' => 'microchips-by',
            'domain' => 'microchips.by',
            'country_code' => 'BY',
            'currency_code' => 'BYN',
            'default_locale' => 'ru-BY',
            'name' => 'Microchips',
            'is_active' => true,
        ]);
        [$snapshotRun, $duplicateRun, $snapshotHash, $duplicateHash] = $this->sourceEvidence();
        $product = Product::query()->create([
            'external_id' => 'P1',
            'slug' => 'product-p1',
            'name' => 'Product P1',
            'status' => 'draft',
        ]);
        SiteProduct::query()->create([
            'site_id' => $site->id,
            'product_id' => $product->id,
            'slug' => 'product-p1',
            'is_published' => false,
            'availability' => 'on_request',
        ]);
        $file = $this->manifest($snapshotRun->id, $duplicateRun->id, $snapshotHash, $duplicateHash);

        $this->artisan('catalog:apply-bitrix-identity-review-decisions', ['file' => $file])
            ->assertSuccessful();
        $this->assertDatabaseCount('import_runs', 2);
        $this->assertDatabaseCount('catalog_identity_candidates', 0);

        $this->artisan('catalog:apply-bitrix-identity-review-decisions', ['file' => $file, '--apply' => true])
            ->assertSuccessful();
        $this->assertDatabaseCount('import_runs', 3);
        $this->assertDatabaseCount('products', 1);
        $this->assertDatabaseCount('site_products', 1);
        $this->assertSame(3, StagedImportRecord::query()->where('entity_type', 'bitrix_identity_review_decision')->count());
        $this->assertDatabaseCount('catalog_identity_candidates', 1);
        $candidate = CatalogIdentityCandidate::query()->sole();
        $this->assertSame('same_identity_confirmed', $candidate->review_status);
        $this->assertSame('M1', $candidate->confirmed_mpn);
        $this->assertSame('1', $candidate->legacy_id);
        $this->assertSame($admin->id, $candidate->reviewed_by);

        $this->artisan('catalog:apply-bitrix-identity-review-decisions', ['file' => $file, '--apply' => true])
            ->assertSuccessful();
        $this->assertDatabaseCount('import_runs', 3);
        $this->assertDatabaseCount('catalog_identity_candidates', 1);
    }

    public function test_rejects_model_core_same_identity_and_rolls_back_the_package(): void
    {
        User::factory()->create(['is_admin' => true]);
        Site::query()->create([
            'key' => 'microchips-by',
            'domain' => 'microchips.by',
            'country_code' => 'BY',
            'currency_code' => 'BYN',
            'default_locale' => 'ru-BY',
            'name' => 'Microchips',
            'is_active' => true,
        ]);
        [$snapshotRun, $duplicateRun, $snapshotHash, $duplicateHash] = $this->sourceEvidence();
        $file = $this->manifest($snapshotRun->id, $duplicateRun->id, $snapshotHash, $duplicateHash, 'model_core');

        $this->artisan('catalog:apply-bitrix-identity-review-decisions', ['file' => $file, '--apply' => true])
            ->assertFailed();
        $this->assertDatabaseCount('import_runs', 2);
        $this->assertDatabaseCount('catalog_identity_candidates', 0);
        $this->assertSame(0, StagedImportRecord::query()->where('entity_type', 'bitrix_identity_review_decision')->count());
    }

    /** @return array{ImportRun,ImportRun,string,string} */
    private function sourceEvidence(): array
    {
        $snapshotHash = str_repeat('a', 64);
        $duplicateHash = str_repeat('b', 64);
        $snapshot = ImportRun::query()->create([
            'source' => 'bitrix_legacy_snapshot:microchips-by',
            'status' => 'completed',
            'total_records' => 3,
            'processed_records' => 3,
            'failed_records' => 0,
            'summary' => ['manifest_sha256' => $snapshotHash],
        ]);
        $duplicate = ImportRun::query()->create([
            'source' => 'bitrix_duplicate_review_evidence:microchips-by',
            'status' => 'completed',
            'total_records' => 3,
            'processed_records' => 3,
            'failed_records' => 0,
            'summary' => ['manifest_sha256' => $duplicateHash],
        ]);
        foreach ([1, 2, 3] as $legacyId) {
            $externalId = 'P'.$legacyId;
            OneCNomenclatureItem::query()->create([
                'import_run_id' => $snapshot->id,
                'source_key' => '1c_nomenclature',
                'external_id' => $externalId,
                'is_group' => false,
                'name' => 'Product '.$externalId,
                'classification_status' => 'catalog_product',
                'source_payload' => [],
                'source_checksum' => str_repeat((string) $legacyId, 64),
            ]);
            StagedImportRecord::query()->create([
                'import_run_id' => $snapshot->id,
                'row_number' => $legacyId,
                'entity_type' => 'bitrix_legacy_product_evidence',
                'external_id' => 'bitrix:'.$legacyId,
                'payload' => [
                    'legacy_element_id' => (string) $legacyId,
                    'legacy_name' => 'Legacy '.$legacyId,
                    'legacy_url_candidate' => '/catalog/'.$legacyId.'/',
                    'one_c_external_id' => $externalId,
                    'legacy_text_sha256' => str_repeat((string) $legacyId, 64),
                    'transfer_status' => 'candidate_duplicate_group',
                ],
                'status' => 'staged_evidence',
            ]);
            StagedImportRecord::query()->create([
                'import_run_id' => $duplicate->id,
                'row_number' => $legacyId,
                'entity_type' => 'bitrix_duplicate_review_decision',
                'external_id' => 'bitrix:'.$legacyId,
                'payload' => [
                    'legacy_element_id' => (string) $legacyId,
                    'one_c_external_id' => $externalId,
                    'group_decision' => 'single_high_signal_review_queue',
                    'member_decision' => 'review_exact_identity_candidate',
                ],
                'status' => 'staged_evidence',
            ]);
        }

        return [$snapshot, $duplicate, $snapshotHash, $duplicateHash];
    }

    private function manifest(int $snapshotRunId, int $duplicateRunId, string $snapshotHash, string $duplicateHash, string $sameScope = 'exact'): string
    {
        $decisions = [
            [
                'review_priority' => 1,
                'legacy_element_id' => '1',
                'one_c_external_id' => 'P1',
                'legacy_text_sha256' => str_repeat('1', 64),
                'decision' => 'same_identity',
                'identity_scope' => $sameScope,
                'confirmed_mpn' => 'M1',
                'manufacturer' => 'Maker',
                'source_url' => 'https://manufacturer.example/products/m1',
                'source_kind' => 'official_manufacturer_product_page',
                'reason' => 'Exact product evidence.',
                'checked_at' => '2026-07-28',
            ],
            [
                'review_priority' => 2,
                'legacy_element_id' => '2',
                'one_c_external_id' => 'P2',
                'legacy_text_sha256' => str_repeat('2', 64),
                'decision' => 'hold',
                'identity_scope' => 'variant_unresolved',
                'reason' => 'Variant is not proven.',
                'checked_at' => '2026-07-28',
            ],
            [
                'review_priority' => 3,
                'legacy_element_id' => '3',
                'one_c_external_id' => 'P3',
                'legacy_text_sha256' => str_repeat('3', 64),
                'decision' => 'different_product_false_mapping',
                'identity_scope' => 'exact_suffix_conflict',
                'reason' => 'Suffix conflict.',
                'checked_at' => '2026-07-28',
            ],
        ];
        $manifest = [
            'schema_version' => 1,
            'site_key' => 'microchips-by',
            'review_batch' => 'test-wave145',
            'source_snapshot_run_id' => $snapshotRunId,
            'source_snapshot_manifest_sha256' => $snapshotHash,
            'source_duplicate_evidence_run_id' => $duplicateRunId,
            'source_duplicate_manifest_sha256' => $duplicateHash,
            'expected_count' => 3,
            'decision_counts' => [
                'different_product_false_mapping' => 1,
                'hold' => 1,
                'same_identity' => 1,
            ],
            'mutation_policy' => array_fill_keys([
                'change_products', 'change_site_links', 'merge_products', 'delete_products',
                'change_publication', 'change_urls', 'change_seo', 'change_media',
            ], false),
            'decisions' => $decisions,
        ];
        $file = storage_path('framework/testing/bitrix-identity-decisions-'.uniqid().'.json');
        file_put_contents($file, json_encode($manifest, JSON_THROW_ON_ERROR));

        return $file;
    }
}
