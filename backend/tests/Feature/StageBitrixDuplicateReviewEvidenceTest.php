<?php

namespace Tests\Feature;

use App\Models\ImportRun;
use App\Models\StagedImportRecord;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class StageBitrixDuplicateReviewEvidenceTest extends TestCase
{
    use RefreshDatabase;

    public function test_stages_complete_collision_evidence_without_catalog_mutation_and_is_idempotent(): void
    {
        [$sourceRun, $sourceHash] = $this->sourceSnapshot();
        $file = $this->manifest($sourceRun->id, $sourceHash);
        $arguments = ['file' => $file];

        $this->artisan('catalog:stage-bitrix-duplicate-review-evidence', $arguments)->assertSuccessful();
        $this->assertDatabaseCount('import_runs', 1);
        $this->assertDatabaseCount('staged_import_records', 2);

        $this->artisan('catalog:stage-bitrix-duplicate-review-evidence', [...$arguments, '--apply' => true])->assertSuccessful();
        $this->assertDatabaseCount('import_runs', 2);
        $this->assertDatabaseCount('staged_import_records', 4);
        $this->assertDatabaseCount('products', 0);
        $this->assertDatabaseCount('site_products', 0);
        $this->assertDatabaseCount('product_families', 0);
        $this->assertDatabaseCount('site_urls', 0);
        $this->assertDatabaseCount('site_seos', 0);
        $this->assertSame(2, StagedImportRecord::query()->where('entity_type', 'bitrix_duplicate_review_decision')->count());
        $this->assertSame(0, StagedImportRecord::query()->whereNotNull('published_product_id')->count());

        $this->artisan('catalog:stage-bitrix-duplicate-review-evidence', [...$arguments, '--apply' => true])->assertSuccessful();
        $this->assertDatabaseCount('import_runs', 2);
        $this->assertDatabaseCount('staged_import_records', 4);
    }

    public function test_fails_when_a_member_drifted_from_source_snapshot(): void
    {
        [$sourceRun, $sourceHash] = $this->sourceSnapshot();
        $file = $this->manifest($sourceRun->id, $sourceHash, 'wrong-hash');

        $this->artisan('catalog:stage-bitrix-duplicate-review-evidence', ['file' => $file])
            ->assertFailed();
        $this->assertDatabaseCount('import_runs', 1);
    }

    /** @return array{ImportRun,string} */
    private function sourceSnapshot(): array
    {
        $hash = str_repeat('a', 64);
        $run = ImportRun::create([
            'source' => 'bitrix_legacy_snapshot:microchips-by',
            'status' => 'completed',
            'total_records' => 2,
            'processed_records' => 2,
            'summary' => ['manifest_sha256' => $hash],
        ]);
        foreach ([1, 2] as $legacyId) {
            StagedImportRecord::create([
                'import_run_id' => $run->id,
                'row_number' => $legacyId,
                'entity_type' => 'bitrix_legacy_product_evidence',
                'external_id' => 'bitrix:'.$legacyId,
                'payload' => [
                    'legacy_element_id' => (string) $legacyId,
                    'one_c_external_id' => 'P1',
                    'legacy_text_sha256' => str_repeat((string) $legacyId, 64),
                    'transfer_status' => 'candidate_duplicate_group',
                ],
                'status' => 'staged_evidence',
            ]);
        }

        return [$run, $hash];
    }

    private function manifest(int $sourceRunId, string $sourceHash, ?string $firstTextHash = null): string
    {
        $members = [];
        foreach ([1, 2] as $legacyId) {
            $members[] = [
                'legacy_element_id' => (string) $legacyId,
                'legacy_name' => 'Legacy '.$legacyId,
                'legacy_url_candidate' => '/catalog/'.$legacyId.'/',
                'legacy_text_sha256' => $legacyId === 1 && $firstTextHash !== null ? $firstTextHash : str_repeat((string) $legacyId, 64),
                'preview_picture_file_id' => '',
                'detail_picture_file_id' => '',
                'match_method' => $legacyId === 1 ? 'sig+brand' : 'generic',
                'match_score' => $legacyId === 1 ? '0.95' : '0.6',
                'brand_ok' => $legacyId === 1 ? 'yes' : 'no',
                'comparison_status' => 'agree',
                'signature' => 'SIG'.$legacyId,
                'member_decision' => $legacyId === 1 ? 'review_exact_identity_candidate' : 'hold_insufficient_identity_evidence',
                'retry_condition' => 'Primary evidence required.',
                'create_product' => false,
                'merge_product' => false,
                'change_publication' => false,
            ];
        }
        $manifest = [
            'schema_version' => 1,
            'site_key' => 'microchips-by',
            'source_import_run_id' => $sourceRunId,
            'source_manifest_sha256' => $sourceHash,
            'matcher_evidence_sha256' => str_repeat('b', 64),
            'expected_groups' => 1,
            'expected_members' => 2,
            'group_decision_counts' => ['single_high_signal_review_queue' => 1],
            'member_decision_counts' => [
                'hold_insufficient_identity_evidence' => 1,
                'review_exact_identity_candidate' => 1,
            ],
            'mutation_policy' => array_fill_keys([
                'create_products', 'merge_products', 'delete_products', 'change_site_links',
                'create_families', 'change_publication', 'change_urls', 'change_seo',
                'render_legacy_html',
            ], false),
            'groups' => [[
                'group_key' => 'one_c:P1',
                'one_c_external_id' => 'P1',
                'one_c_name' => 'Product P1',
                'expected_member_count' => 2,
                'high_signal_member_count' => 1,
                'group_decision' => 'single_high_signal_review_queue',
                'members' => $members,
            ]],
        ];
        $file = storage_path('framework/testing/duplicate-evidence-'.uniqid().'.json');
        file_put_contents($file, json_encode($manifest, JSON_THROW_ON_ERROR));

        return $file;
    }
}
