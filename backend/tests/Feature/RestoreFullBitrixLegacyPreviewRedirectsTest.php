<?php

namespace Tests\Feature;

use App\Events\SiteContentChanged;
use App\Models\CatalogDraftMaterialization;
use App\Models\ImportRun;
use App\Models\Product;
use App\Models\Site;
use App\Models\SiteProduct;
use App\Models\SiteRedirect;
use App\Models\SiteSeo;
use App\Models\SiteUrl;
use App\Models\StagedImportRecord;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Event;
use Tests\TestCase;

class RestoreFullBitrixLegacyPreviewRedirectsTest extends TestCase
{
    use RefreshDatabase;

    private const MANIFEST_HASH = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa';

    public function test_it_dry_runs_restores_one_bulk_batch_event_and_is_idempotent(): void
    {
        [$site, $sourceRun] = $this->fixture(2);
        Event::fake([SiteContentChanged::class]);

        $this->artisan('catalog:restore-full-bitrix-legacy-preview-redirects', $this->arguments($site, $sourceRun, 1))
            ->assertSuccessful();
        $this->assertDatabaseCount('site_redirects', 0);
        Event::assertNotDispatched(SiteContentChanged::class);

        $this->artisan('catalog:restore-full-bitrix-legacy-preview-redirects', [
            ...$this->arguments($site, $sourceRun, 1),
            '--apply' => true,
        ])->assertSuccessful();
        $this->assertDatabaseCount('site_redirects', 1);
        Event::assertDispatchedTimes(SiteContentChanged::class, 1);

        $this->artisan('catalog:restore-full-bitrix-legacy-preview-redirects', [
            ...$this->arguments($site, $sourceRun, 1),
            '--apply' => true,
        ])->assertSuccessful();
        $this->assertDatabaseCount('site_redirects', 2);
        Event::assertDispatchedTimes(SiteContentChanged::class, 2);

        $this->artisan('catalog:restore-full-bitrix-legacy-preview-redirects', [
            ...$this->arguments($site, $sourceRun, 1),
            '--apply' => true,
        ])->assertSuccessful();
        $this->assertDatabaseCount('site_redirects', 2);
        Event::assertDispatchedTimes(SiteContentChanged::class, 2);

        $this->assertDatabaseHas('site_redirects', [
            'site_id' => $site->id,
            'source_path' => '/catalog/akkumulyatory/dlya_ibp/100',
            'target_path' => '/catalog/batteries-ups/legacy-bitrix-100',
            'status_code' => 301,
            'purpose' => SiteRedirect::PURPOSE_PREVIEW,
            'is_active' => true,
        ]);
    }

    public function test_it_fails_closed_for_a_bad_pin_or_drifted_source_checksum(): void
    {
        [$site, $sourceRun, $records] = $this->fixture();

        $this->artisan('catalog:restore-full-bitrix-legacy-preview-redirects', [
            ...$this->arguments($site, $sourceRun),
            '--source-manifest-sha256' => str_repeat('b', 64),
            '--apply' => true,
        ])->expectsOutputToContain('missing, incomplete or drifted')->assertFailed();
        $this->assertDatabaseCount('site_redirects', 0);

        $payload = $records[0]->payload;
        $payload['name'] = 'Drifted after staging';
        $records[0]->update(['payload' => $payload]);

        $this->artisan('catalog:restore-full-bitrix-legacy-preview-redirects', [
            ...$this->arguments($site, $sourceRun),
            '--apply' => true,
        ])->expectsOutputToContain('checksum drifted')->assertFailed();
        $this->assertDatabaseCount('site_redirects', 0);
    }

    public function test_it_fails_closed_for_a_non_local_legacy_url_or_an_active_source_route(): void
    {
        [$site, $sourceRun, $records, $lineages] = $this->fixture();
        $this->replaceLegacyUrl(
            $records[0],
            $lineages[0],
            'https://example.test/catalog/akkumulyatory/dlya_ibp/100/',
        );

        $this->artisan('catalog:restore-full-bitrix-legacy-preview-redirects', [
            ...$this->arguments($site, $sourceRun),
            '--apply' => true,
        ])->expectsOutputToContain('not an exact local HTTPS URL')->assertFailed();
        $this->assertDatabaseCount('site_redirects', 0);

        $this->replaceLegacyUrl(
            $records[0],
            $lineages[0],
            'https://microchips.by/catalog/akkumulyatory/dlya_ibp/100/',
        );
        SiteUrl::create([
            'site_id' => $site->id,
            'path' => '/catalog/akkumulyatory/dlya_ibp/100',
            'locale' => $site->default_locale,
            'target_type' => 'page',
            'target_id' => 999,
            'is_indexable' => false,
        ]);

        $this->artisan('catalog:restore-full-bitrix-legacy-preview-redirects', [
            ...$this->arguments($site, $sourceRun),
            '--apply' => true,
        ])->expectsOutputToContain('is still an active site URL')->assertFailed();
        $this->assertDatabaseCount('site_redirects', 0);
    }

    public function test_it_fails_closed_for_schema_or_a_redirect_chain_at_the_target(): void
    {
        [$site, $sourceRun, , , $siteProducts] = $this->fixture();
        $seo = SiteSeo::query()
            ->where('site_id', $site->id)
            ->where('resource_type', 'product')
            ->where('resource_id', $siteProducts[0]->id)
            ->sole();
        $seo->update(['schema' => ['@type' => 'Product']]);

        $this->artisan('catalog:restore-full-bitrix-legacy-preview-redirects', [
            ...$this->arguments($site, $sourceRun),
            '--apply' => true,
        ])->expectsOutputToContain('must be self-canonical and match its URL indexability')->assertFailed();
        $this->assertDatabaseCount('site_redirects', 0);

        $seo->update(['schema' => null]);
        SiteRedirect::create([
            'site_id' => $site->id,
            'source_path' => '/catalog/batteries-ups/legacy-bitrix-100',
            'target_path' => '/catalog/final-product',
            'status_code' => 301,
            'purpose' => SiteRedirect::PURPOSE_PREVIEW,
            'is_active' => true,
        ]);

        $this->artisan('catalog:restore-full-bitrix-legacy-preview-redirects', [
            ...$this->arguments($site, $sourceRun),
            '--apply' => true,
        ])->expectsOutputToContain('is itself an active redirect source')->assertFailed();
        $this->assertDatabaseMissing('site_redirects', [
            'site_id' => $site->id,
            'source_path' => '/catalog/akkumulyatory/dlya_ibp/100',
        ]);
    }

    public function test_it_uses_seo_purpose_for_an_already_indexable_released_product(): void
    {
        [$site, $sourceRun] = $this->fixture(1);
        SiteUrl::query()->where('site_id', $site->id)->where('target_type', 'product')->update(['is_indexable' => true]);
        SiteSeo::query()->where('site_id', $site->id)->where('resource_type', 'product')->update(['is_indexable' => true]);

        $this->artisan('catalog:restore-full-bitrix-legacy-preview-redirects', [
            ...$this->arguments($site, $sourceRun, 1),
            '--apply' => true,
        ])->assertSuccessful();

        $this->assertDatabaseHas('site_redirects', [
            'site_id' => $site->id,
            'source_path' => '/catalog/akkumulyatory/dlya_ibp/100',
            'purpose' => SiteRedirect::PURPOSE_SEO,
            'status_code' => 301,
            'is_active' => true,
        ]);
    }

    /**
     * @return array{Site,ImportRun,list<StagedImportRecord>,list<CatalogDraftMaterialization>,list<SiteProduct>}
     */
    private function fixture(int $count = 1): array
    {
        $site = Site::create([
            'key' => 'microchips-by',
            'domain' => 'microchips.by',
            'country_code' => 'BY',
            'currency_code' => 'BYN',
            'default_locale' => 'ru-BY',
            'name' => 'RB',
            'is_active' => true,
        ]);
        $sourceRun = ImportRun::create([
            'source' => 'bitrix_full_catalog_snapshot:'.$site->key,
            'status' => 'completed',
            'source_file' => 'full-bitrix.json',
            'total_records' => $count,
            'processed_records' => $count,
            'failed_records' => 0,
            'summary' => ['site_id' => $site->id, 'manifest_sha256' => self::MANIFEST_HASH],
            'started_at' => now(),
            'finished_at' => now(),
        ]);
        $materializationRun = ImportRun::create([
            'source' => 'bitrix_full_catalog_materialization:'.$site->key,
            'status' => 'completed',
            'source_file' => 'full-bitrix.json',
            'total_records' => $count,
            'processed_records' => $count,
            'failed_records' => 0,
            'summary' => [],
            'started_at' => now(),
            'finished_at' => now(),
        ]);

        $records = [];
        $lineages = [];
        $siteProducts = [];
        for ($offset = 0; $offset < $count; $offset++) {
            $bitrixId = (string) (100 + $offset);
            $payload = [
                'registry_id' => 'bitrix:'.$bitrixId,
                'bitrix_id' => $bitrixId,
                'name' => 'Legacy battery '.$bitrixId,
                'legacy_section_path' => 'akkumulyatory/dlya_ibp',
                'legacy_url' => 'https://microchips.by/catalog/akkumulyatory/dlya_ibp/'.$bitrixId.'/',
                'target_category_external_id' => 'seo:batteries-ups',
                'identity_status' => 'unresolved_identity',
                'transfer_status' => 'legacy_only_draft_candidate',
                'allow_product_create' => true,
                'allow_publication' => false,
                'allow_indexing' => false,
                'allow_merge' => false,
            ];
            ksort($payload);
            $payload['source_checksum'] = hash('sha256', json_encode(
                $payload,
                JSON_THROW_ON_ERROR | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES,
            ));
            $record = StagedImportRecord::create([
                'import_run_id' => $sourceRun->id,
                'row_number' => $offset + 1,
                'entity_type' => 'bitrix_full_catalog_product_evidence',
                'external_id' => 'bitrix:'.$bitrixId,
                'payload' => $payload,
                'normalized_payload' => [
                    'site_id' => $site->id,
                    'transfer_status' => 'legacy_only_draft_candidate',
                    'target_category_external_id' => 'seo:batteries-ups',
                    'source_checksum' => $payload['source_checksum'],
                ],
                'validation_errors' => [],
                'status' => 'staged_evidence',
            ]);
            $product = Product::create([
                'external_id' => 'bitrix:'.$bitrixId,
                'name' => 'Legacy battery '.$bitrixId,
                'slug' => 'legacy-bitrix-'.$bitrixId,
                'status' => 'needs_review',
            ]);
            $siteProduct = SiteProduct::create([
                'site_id' => $site->id,
                'product_id' => $product->id,
                'slug' => 'legacy-bitrix-'.$bitrixId,
                'is_published' => true,
                'availability' => 'on_request',
            ]);
            $targetPath = '/catalog/batteries-ups/legacy-bitrix-'.$bitrixId;
            SiteUrl::create([
                'site_id' => $site->id,
                'path' => $targetPath,
                'locale' => $site->default_locale,
                'target_type' => 'product',
                'target_id' => $siteProduct->id,
                'is_indexable' => false,
            ]);
            SiteSeo::create([
                'site_id' => $site->id,
                'locale' => $site->default_locale,
                'resource_type' => 'product',
                'resource_id' => $siteProduct->id,
                'canonical_path' => $targetPath,
                'title' => $product->name,
                'description' => null,
                'is_indexable' => false,
                'schema' => null,
            ]);
            $lineage = CatalogDraftMaterialization::create([
                'materialization_run_id' => $materializationRun->id,
                'source_import_run_id' => $sourceRun->id,
                'staged_import_record_id' => $record->id,
                'site_id' => $site->id,
                'product_id' => $product->id,
                'site_product_id' => $siteProduct->id,
                'source_namespace' => 'bitrix',
                'source_external_id' => 'bitrix:'.$bitrixId,
                'source_checksum' => $payload['source_checksum'],
                'materialization_kind' => CatalogDraftMaterialization::KIND_NAMESPACED_DRAFT,
                'target_category_external_id' => 'seo:batteries-ups',
            ]);

            $records[] = $record;
            $lineages[] = $lineage;
            $siteProducts[] = $siteProduct;
        }

        return [$site, $sourceRun, $records, $lineages, $siteProducts];
    }

    /** @return array<string,mixed> */
    private function arguments(Site $site, ImportRun $sourceRun, int $batchSize = 1000): array
    {
        return [
            'site' => $site->key,
            '--source-run' => (string) $sourceRun->id,
            '--source-manifest-sha256' => self::MANIFEST_HASH,
            '--expected-source-records' => $sourceRun->total_records,
            '--batch-size' => $batchSize,
        ];
    }

    private function replaceLegacyUrl(
        StagedImportRecord $record,
        CatalogDraftMaterialization $lineage,
        string $legacyUrl,
    ): void {
        $payload = $record->payload;
        $payload['legacy_url'] = $legacyUrl;
        unset($payload['source_checksum']);
        ksort($payload);
        $payload['source_checksum'] = hash('sha256', json_encode(
            $payload,
            JSON_THROW_ON_ERROR | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES,
        ));
        $normalized = $record->normalized_payload;
        $normalized['source_checksum'] = $payload['source_checksum'];
        $record->update(['payload' => $payload, 'normalized_payload' => $normalized]);
        $lineage->update(['source_checksum' => $payload['source_checksum']]);
    }
}
