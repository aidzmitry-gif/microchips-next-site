<?php

namespace Tests\Feature;

use App\Models\Category;
use App\Models\ImportRun;
use App\Models\Site;
use App\Models\SiteCategory;
use App\Models\StagedImportRecord;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class StageFullBitrixCatalogTest extends TestCase
{
    use RefreshDatabase;

    public function test_it_stages_the_complete_manifest_without_catalogue_mutations_and_is_idempotent(): void
    {
        $site = Site::create([
            'key' => 'microchips-by', 'domain' => 'microchips.by', 'country_code' => 'BY',
            'currency_code' => 'BYN', 'default_locale' => 'ru-BY', 'name' => 'Microchips BY',
        ]);
        foreach (['seo:primary-cells', 'seo:electronic-components'] as $offset => $externalId) {
            $category = Category::create(['slug' => 'category-'.$offset, 'name' => 'Category '.$offset]);
            SiteCategory::create([
                'site_id' => $site->id, 'category_id' => $category->id,
                'source' => 'full_catalog_seo_tree', 'external_id' => $externalId,
                'slug' => 'catalog/category-'.$offset, 'name' => 'Category '.$offset,
                'is_published' => false,
            ]);
        }
        $file = $this->manifest();
        $arguments = ['site' => $site->key, 'file' => $file, '--expected-records' => 3];

        $this->artisan('catalog:stage-full-bitrix-catalog', $arguments)->assertSuccessful();
        $this->assertDatabaseCount('import_runs', 0);
        $this->assertDatabaseCount('products', 0);

        $this->artisan('catalog:stage-full-bitrix-catalog', [...$arguments, '--apply' => true])->assertSuccessful();
        $this->assertDatabaseCount('import_runs', 1);
        $this->assertDatabaseCount('staged_import_records', 3);
        $this->assertDatabaseCount('products', 0);
        $this->assertDatabaseCount('site_products', 0);
        $this->assertDatabaseCount('site_urls', 0);
        $this->assertDatabaseCount('site_seos', 0);
        $this->assertSame(0, StagedImportRecord::query()->whereNotNull('published_at')->count());
        $this->assertSame('completed', ImportRun::query()->sole()->status);

        $this->artisan('catalog:stage-full-bitrix-catalog', [...$arguments, '--apply' => true])->assertSuccessful();
        $this->assertDatabaseCount('import_runs', 1);
        $this->assertDatabaseCount('staged_import_records', 3);
    }

    public function test_it_rejects_a_publication_flag_or_missing_category(): void
    {
        $site = Site::create([
            'key' => 'microchips-by', 'domain' => 'microchips.by', 'country_code' => 'BY',
            'currency_code' => 'BYN', 'default_locale' => 'ru-BY', 'name' => 'Microchips BY',
        ]);
        $file = $this->manifest(true);

        $this->artisan('catalog:stage-full-bitrix-catalog', [
            'site' => $site->key, 'file' => $file, '--expected-records' => 3,
        ])->assertFailed();
        $this->assertDatabaseCount('import_runs', 0);
    }

    private function manifest(bool $unsafe = false): string
    {
        $records = [
            $this->row('1', 'seo:primary-cells', 'legacy_only_draft_candidate', '', true),
            $this->row('2', 'seo:electronic-components', 'scope_excluded_electronics'),
            $this->row('3', 'seo:primary-cells', 'existing_one_c_exact_link', 'C-3'),
        ];
        if ($unsafe) {
            $records[0]['allow_publication'] = true;
        }
        $statuses = [
            'existing_one_c_exact_link' => 1,
            'legacy_only_draft_candidate' => 1,
            'scope_excluded_electronics' => 1,
        ];
        $categories = ['seo:electronic-components' => 1, 'seo:primary-cells' => 2];
        $file = storage_path('framework/testing/full-bitrix-'.uniqid().'.json');
        file_put_contents($file, json_encode([
            'schema_version' => 1,
            'site_key' => 'microchips-by',
            'summary' => [
                'records' => 3, 'status_counts' => $statuses,
                'active_category_counts' => $categories,
                'publication_changes' => 0, 'indexable_urls' => 0, 'merges' => 0,
            ],
            'records' => $records,
        ], JSON_THROW_ON_ERROR));

        return $file;
    }

    /** @return array<string,mixed> */
    private function row(string $id, string $category, string $status, string $oneC = '', bool $create = false): array
    {
        $row = [
            'registry_id' => 'bitrix:'.$id,
            'bitrix_id' => $id,
            'name' => 'Product '.$id,
            'legacy_section_path' => 'batareyki',
            'legacy_url' => 'https://microchips.by/catalog/batareyki/'.$id.'/',
            'target_category_external_id' => $category,
            'one_c_external_id' => $oneC,
            'identity_status' => $status === 'legacy_only_draft_candidate' ? 'unresolved_identity' : 'linked_exact_name',
            'duplicate_candidate_key' => '',
            'transfer_status' => $status,
            'allow_product_create' => $create,
            'allow_publication' => false,
            'allow_indexing' => false,
            'allow_merge' => false,
        ];
        $checksumPayload = $row;
        ksort($checksumPayload);
        $row['source_checksum'] = hash('sha256', json_encode(
            $checksumPayload,
            JSON_THROW_ON_ERROR | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES,
        ));

        return $row;
    }
}
