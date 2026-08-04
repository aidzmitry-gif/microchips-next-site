<?php

namespace Tests\Feature;

use App\Models\CatalogIdentityCandidate;
use App\Models\Category;
use App\Models\ImportRun;
use App\Models\OneCNomenclatureItem;
use App\Models\Site;
use App\Models\SiteCategory;
use App\Models\StagedImportRecord;
use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Storage;
use Tests\TestCase;

class LegacyCatalogPreviewApiTest extends TestCase
{
    use RefreshDatabase;

    public function test_preview_is_test_domain_only_sanitized_noindex_and_excludes_out_of_scope_rows(): void
    {
        $this->fakePublicDisk();
        [$site, $run] = $this->snapshotFixture();
        $this->record($run, 101, 'strict_mapped_evidence', '<p>Useful text</p><script>alert(1)</script>');
        $this->record($run, 102, 'hold_missing_1c_identity', '<b>Needs identity</b>');
        $this->record($run, 103, 'scope_excluded_electronics', 'Electronics');
        $this->record($run, 104, 'excluded_inactive_legacy', 'Inactive');
        Storage::disk('public')->put('legacy-staging/rb/bitrix-101-10.png', $this->png());
        $this->categoryFixture($site);

        $response = $this->getJson('/api/v1/sites/rb/legacy-preview/products?per_page=100');
        $response->assertOk()
            ->assertHeader('x-robots-tag', 'noindex, nofollow, noarchive')
            ->assertJsonPath('meta.snapshot_total', 4)
            ->assertJsonPath('meta.visible_scope_total', 2)
            ->assertJsonPath('meta.excluded_total', 2)
            ->assertJsonCount(2, 'data')
            ->assertJsonPath('data.0.has_staging_image', true)
            ->assertJsonMissing(['name' => 'Legacy 103']);
        $this->assertStringNotContainsString('script', $response->json('data.0.description'));
        $this->assertStringNotContainsString('alert', $response->json('data.0.description'));

        $this->getJson('/api/v1/sites/rb/legacy-preview/categories')
            ->assertOk()
            ->assertJsonPath('meta.categories_total', 1)
            ->assertJsonPath('data.0.count', 2)
            ->assertJsonPath('data.0.path', '/legacy-preview/catalog/akkumulyatory/promyshlennye');

        $this->get('/api/v1/sites/rb/legacy-preview/media/101')
            ->assertOk()
            ->assertHeader('x-robots-tag', 'noindex, nofollow, noarchive')
            ->assertHeader('content-type', 'image/png');
        $this->get('/api/v1/sites/rb/legacy-preview/media/103')->assertNotFound();

        $site->update(['domain' => 'microchips.by']);
        $this->getJson('/api/v1/sites/rb/legacy-preview/products')->assertNotFound();
    }

    public function test_preview_search_category_status_and_product_detail_are_read_only(): void
    {
        [$site, $run] = $this->snapshotFixture();
        $this->record($run, 201, 'strict_mapped_evidence', '<p>First detail</p>', 'akkumulyatory/promyshlennye');
        $this->record($run, 202, 'candidate_duplicate_group', '<p>Second detail</p>', 'akkumulyatory/dlya_ibp');
        $before = [
            'runs' => ImportRun::query()->count(),
            'records' => StagedImportRecord::query()->count(),
        ];

        $this->getJson('/api/v1/sites/rb/legacy-preview/products?q=Legacy%20202')
            ->assertOk()->assertJsonPath('meta.total', 1)->assertJsonPath('data.0.legacy_id', 202);
        $this->getJson('/api/v1/sites/rb/legacy-preview/products?category=akkumulyatory/promyshlennye')
            ->assertOk()->assertJsonPath('meta.total', 1)->assertJsonPath('data.0.legacy_id', 201);
        $this->getJson('/api/v1/sites/rb/legacy-preview/products?status=strict_mapped_evidence')
            ->assertOk()->assertJsonPath('meta.total', 1);
        $this->getJson('/api/v1/sites/rb/legacy-preview/products/201')
            ->assertOk()->assertJsonPath('data.description', 'First detail');
        $this->getJson('/api/v1/sites/rb/legacy-preview/products?status=scope_excluded_electronics')->assertUnprocessable();

        $this->assertSame($before['runs'], ImportRun::query()->count());
        $this->assertSame($before['records'], StagedImportRecord::query()->count());
        $this->assertSame(0, StagedImportRecord::query()->whereNotNull('published_at')->count());
        $this->assertSame(0, StagedImportRecord::query()->whereNotNull('published_product_id')->count());
    }

    public function test_preview_exposes_reviewed_identity_without_treating_holds_as_canonical_links(): void
    {
        [$site, $snapshot] = $this->snapshotFixture();
        $this->record($snapshot, 301, 'candidate_duplicate_group', 'Confirmed legacy product');
        $this->record($snapshot, 302, 'candidate_duplicate_group', 'Held legacy product');
        $this->record($snapshot, 303, 'candidate_duplicate_group', 'Rejected mapping');
        $identityRun = ImportRun::query()->create([
            'source' => 'bitrix_identity_review_decisions:rb',
            'status' => 'completed',
            'total_records' => 3,
            'processed_records' => 3,
            'failed_records' => 0,
        ]);
        $oneC = OneCNomenclatureItem::query()->create([
            'import_run_id' => $identityRun->id,
            'source_key' => '1c_nomenclature',
            'external_id' => 'P301',
            'is_group' => false,
            'name' => 'Canonical P301',
            'classification_status' => 'catalog_product',
            'source_payload' => [],
            'source_checksum' => str_repeat('a', 64),
        ]);
        $reviewer = User::factory()->create(['is_admin' => true]);
        CatalogIdentityCandidate::query()->create([
            'import_run_id' => $identityRun->id,
            'one_c_nomenclature_item_id' => $oneC->id,
            'legacy_source' => 'bitrix',
            'legacy_id' => '301',
            'legacy_name' => 'Legacy 301',
            'review_priority' => 1,
            'review_batch' => 'test-reviewed-identities',
            'confidence' => 1,
            'match_method' => 'official_source_exact_identity',
            'comparison_status' => 'same_identity',
            'review_status' => 'same_identity_confirmed',
            'confirmed_mpn' => 'M301',
            'confirmed_mpn_normalized' => 'm301',
            'confirmed_manufacturer' => 'Maker',
            'reviewed_by' => $reviewer->id,
            'reviewed_at' => now(),
            'source_payload' => [],
            'source_checksum' => str_repeat('b', 64),
        ]);
        foreach ([301 => 'same_identity', 302 => 'hold', 303 => 'different_product_false_mapping'] as $legacyId => $decision) {
            StagedImportRecord::query()->create([
                'import_run_id' => $identityRun->id,
                'row_number' => $legacyId,
                'entity_type' => 'bitrix_identity_review_decision',
                'external_id' => 'bitrix:'.$legacyId,
                'payload' => [
                    'legacy_element_id' => (string) $legacyId,
                    'one_c_external_id' => $legacyId === 301 ? 'P301' : 'P'.$legacyId,
                    'decision' => $decision,
                    'reason' => 'Reviewed '.$decision,
                ],
                'status' => 'reviewed_evidence',
            ]);
        }

        $this->getJson('/api/v1/sites/'.$site->key.'/legacy-preview/products/301')
            ->assertOk()
            ->assertJsonPath('data.identity_review.state', 'confirmed')
            ->assertJsonPath('data.identity_review.canonical_external_id', 'P301');
        $this->getJson('/api/v1/sites/'.$site->key.'/legacy-preview/products/302')
            ->assertOk()
            ->assertJsonPath('data.identity_review.state', 'hold')
            ->assertJsonPath('data.identity_review.canonical_external_id', null);
        $this->getJson('/api/v1/sites/'.$site->key.'/legacy-preview/products/303')
            ->assertOk()
            ->assertJsonPath('data.identity_review.state', 'rejected_mapping')
            ->assertJsonPath('data.identity_review.canonical_external_id', null);
    }

    /** @return array{Site, ImportRun} */
    private function snapshotFixture(): array
    {
        $site = Site::create([
            'key' => 'rb', 'domain' => 'rb.test', 'country_code' => 'BY', 'currency_code' => 'BYN',
            'default_locale' => 'ru-BY', 'name' => 'RB preview', 'is_active' => true,
        ]);
        $run = ImportRun::create([
            'source' => 'bitrix_legacy_snapshot:rb', 'status' => 'completed', 'source_file' => 'snapshot.json',
            'total_records' => 4, 'processed_records' => 4, 'failed_records' => 0,
        ]);

        return [$site, $run];
    }

    private function record(ImportRun $run, int $legacyId, string $status, string $detail, string $section = 'akkumulyatory/promyshlennye'): void
    {
        StagedImportRecord::create([
            'import_run_id' => $run->id,
            'row_number' => $legacyId,
            'entity_type' => 'bitrix_legacy_product_evidence',
            'external_id' => 'bitrix:'.$legacyId,
            'payload' => [
                'legacy_element_id' => (string) $legacyId,
                'legacy_name' => 'Legacy '.$legacyId,
                'legacy_url_candidate' => '/catalog/'.$section.'/'.$legacyId.'/',
                'legacy_primary_section_path' => $section,
                'legacy_matched_section_paths' => $section,
                'detail_text' => $detail,
                'preview_text' => '',
                'one_c_external_id' => $status === 'strict_mapped_evidence' ? '1C-'.$legacyId : '',
                'one_c_name' => '',
                'one_c_article' => '',
                'transfer_status' => $status,
            ],
            'normalized_payload' => [],
            'validation_errors' => [],
            'status' => 'staged_evidence',
        ]);
    }

    private function categoryFixture(Site $site): void
    {
        $category = Category::create(['slug' => 'legacy-industrial', 'name' => 'Промышленные аккумуляторы']);
        SiteCategory::create([
            'site_id' => $site->id,
            'source' => 'bitrix_sections',
            'external_id' => '427',
            'category_id' => $category->id,
            'slug' => 'catalog/akkumulyatory/promyshlennye',
            'name' => 'Промышленные аккумуляторы',
            'is_published' => false,
        ]);
    }

    private function png(): string
    {
        return base64_decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAFgAI/ScL9pAAAAABJRU5ErkJggg==');
    }

    private function fakePublicDisk(): void
    {
        config(['filesystems.disks.public' => [
            'driver' => 'local',
            'root' => sys_get_temp_dir().'/legacy-preview-public-'.uniqid(),
            'throw' => false,
        ]]);
        Storage::forgetDisk('public');
    }
}
