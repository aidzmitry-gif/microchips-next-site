<?php

namespace Tests\Feature;

use App\Events\SiteContentChanged;
use App\Models\CatalogDraftMaterialization;
use App\Models\Category;
use App\Models\ImportRun;
use App\Models\Product;
use App\Models\Site;
use App\Models\SiteCategory;
use App\Models\SiteProduct;
use App\Models\SiteRedirect;
use App\Models\SiteSeo;
use App\Models\SiteUrl;
use App\Models\StagedImportRecord;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Event;
use Tests\TestCase;

class PublishExistingExactLinkPreviewsTest extends TestCase
{
    use RefreshDatabase;

    public function test_it_dry_runs_then_atomically_publishes_four_existing_products_as_idempotent_noindex_previews(): void
    {
        $fixture = $this->fixture();
        $arguments = ['site' => $fixture['site']->key, 'file' => $fixture['file']];

        try {
            $this->artisan('catalog:publish-existing-exact-link-previews', $arguments)
                ->assertSuccessful();

            $this->assertDatabaseCount('products', 4);
            $this->assertDatabaseCount('site_urls', 0);
            $this->assertDatabaseCount('site_seos', 0);
            $this->assertDatabaseCount('site_redirects', 0);
            $this->assertDatabaseCount('catalog_draft_materializations', 0);
            $this->assertSame(0, SiteProduct::query()->where('is_published', true)->count());

            Event::fake([SiteContentChanged::class]);
            $this->artisan('catalog:publish-existing-exact-link-previews', [...$arguments, '--apply' => true])
                ->assertSuccessful();

            $this->assertDatabaseCount('products', 4);
            $this->assertSame(4, SiteProduct::query()->where('is_published', true)->count());
            $this->assertSame(4, CatalogDraftMaterialization::query()
                ->where('materialization_kind', CatalogDraftMaterialization::KIND_EXISTING_EXACT_LINK)
                ->count());
            $this->assertDatabaseCount('site_redirects', 4);
            $this->assertSame(4, SiteRedirect::query()
                ->where('status_code', 301)
                ->where('purpose', SiteRedirect::PURPOSE_PREVIEW)
                ->where('is_active', true)
                ->count());
            $this->assertSame(6, SiteUrl::query()->where('is_indexable', false)->count());
            $this->assertSame(0, SiteUrl::query()->where('is_indexable', true)->count());
            $this->assertSame(6, SiteSeo::query()->where('is_indexable', false)->whereNull('schema')->count());
            $this->assertSame(0, SiteSeo::query()->whereNotNull('schema')->count());
            $this->assertTrue($fixture['root']->refresh()->is_published);
            $this->assertTrue($fixture['category']->refresh()->is_published);
            foreach ($fixture['site_products'] as $offset => $siteProduct) {
                $siteProduct->refresh();
                $this->assertTrue($siteProduct->is_published);
                $this->assertSame('exact-product-'.($offset + 1), $siteProduct->slug);
                $this->assertNull($siteProduct->price);
                $this->assertSame('on_request', $siteProduct->availability);
                $this->assertTrue($siteProduct->categories()->whereKey($fixture['category']->id)->exists());
            }
            Event::assertDispatched(SiteContentChanged::class, static fn (SiteContentChanged $event): bool => in_array('/catalog/legacy/1', $event->paths, true)
                && in_array('/catalog/power/exact-product-1', $event->paths, true)
                && in_array('/sitemap.xml', $event->paths, true));

            $runsAfterApply = ImportRun::query()->count();
            $this->artisan('catalog:publish-existing-exact-link-previews', [...$arguments, '--apply' => true])
                ->assertSuccessful();
            $this->assertSame($runsAfterApply, ImportRun::query()->count());
            $this->assertDatabaseCount('products', 4);
            $this->assertDatabaseCount('site_redirects', 4);
            $this->assertDatabaseCount('catalog_draft_materializations', 4);
        } finally {
            @unlink($fixture['file']);
        }
    }

    public function test_it_fails_closed_when_one_existing_product_has_a_commercial_claim(): void
    {
        $fixture = $this->fixture();
        $fixture['site_products'][2]->update(['price' => '10.00']);

        try {
            $this->artisan('catalog:publish-existing-exact-link-previews', [
                'site' => $fixture['site']->key,
                'file' => $fixture['file'],
                '--apply' => true,
            ])->assertFailed();

            $this->assertDatabaseCount('products', 4);
            $this->assertSame(0, SiteProduct::query()->where('is_published', true)->count());
            $this->assertDatabaseCount('site_urls', 0);
            $this->assertDatabaseCount('site_seos', 0);
            $this->assertDatabaseCount('site_redirects', 0);
            $this->assertDatabaseCount('catalog_draft_materializations', 0);
            $this->assertSame(1, ImportRun::query()->count());
        } finally {
            @unlink($fixture['file']);
        }
    }

    public function test_it_rejects_source_hash_path_and_exact_link_drift_before_writing(): void
    {
        $fixture = $this->fixture();
        $manifest = json_decode((string) file_get_contents($fixture['file']), true, 512, JSON_THROW_ON_ERROR);
        $manifest['links'][0]['target_path'] = '/catalog/power/not-the-pinned-slug';
        file_put_contents($fixture['file'], json_encode($manifest, JSON_THROW_ON_ERROR));

        try {
            $this->artisan('catalog:publish-existing-exact-link-previews', [
                'site' => $fixture['site']->key,
                'file' => $fixture['file'],
                '--apply' => true,
            ])->assertFailed();

            $this->assertDatabaseCount('products', 4);
            $this->assertSame(0, SiteProduct::query()->where('is_published', true)->count());
            $this->assertDatabaseCount('site_urls', 0);
            $this->assertDatabaseCount('site_redirects', 0);
            $this->assertDatabaseCount('catalog_draft_materializations', 0);

            $manifest['links'][0]['target_path'] = '/catalog/power/exact-product-1';
            $manifest['source_manifest_sha256'] = str_repeat('b', 64);
            file_put_contents($fixture['file'], json_encode($manifest, JSON_THROW_ON_ERROR));
            $this->artisan('catalog:publish-existing-exact-link-previews', [
                'site' => $fixture['site']->key,
                'file' => $fixture['file'],
                '--apply' => true,
            ])->assertFailed();
            $this->assertDatabaseCount('site_urls', 0);
        } finally {
            @unlink($fixture['file']);
        }
    }

    /**
     * @return array{site:Site,root:SiteCategory,category:SiteCategory,site_products:list<SiteProduct>,file:string}
     */
    private function fixture(): array
    {
        $site = Site::create([
            'key' => 'microchips-by',
            'domain' => 'microchips.by',
            'country_code' => 'BY',
            'currency_code' => 'BYN',
            'default_locale' => 'ru-BY',
            'name' => 'Microchips BY',
            'is_active' => true,
        ]);
        $rootCanonical = Category::create(['slug' => 'catalog-root', 'name' => 'Catalogue']);
        $childCanonical = Category::create(['parent_id' => $rootCanonical->id, 'slug' => 'power', 'name' => 'Power']);
        $root = SiteCategory::create([
            'site_id' => $site->id,
            'category_id' => $rootCanonical->id,
            'source' => 'seo_tree',
            'external_id' => 'seo:catalog-root',
            'slug' => 'catalog',
            'name' => 'Catalogue',
            'is_published' => false,
        ]);
        $category = SiteCategory::create([
            'site_id' => $site->id,
            'category_id' => $childCanonical->id,
            'source' => 'seo_tree',
            'external_id' => 'seo:power',
            'slug' => 'catalog/power',
            'name' => 'Power',
            'is_published' => false,
        ]);
        $manifestHash = str_repeat('a', 64);
        $sourceRun = ImportRun::create([
            'source' => 'bitrix_full_catalog_snapshot:'.$site->key,
            'status' => 'completed',
            'source_file' => 'full-bitrix.json',
            'total_records' => 4,
            'processed_records' => 4,
            'failed_records' => 0,
            'summary' => ['manifest_sha256' => $manifestHash],
            'started_at' => now(),
            'finished_at' => now(),
        ]);

        $links = [];
        $siteProducts = [];
        foreach (range(1, 4) as $number) {
            $oneCExternalId = '1c:exact-'.$number;
            $product = Product::create([
                'external_id' => $oneCExternalId,
                'slug' => 'draft-exact-'.$number,
                'name' => 'Exact product '.$number,
                'short_description' => 'Legacy preview description '.$number.'.',
                'status' => 'active',
            ]);
            $siteProduct = SiteProduct::create([
                'site_id' => $site->id,
                'product_id' => $product->id,
                'slug' => 'draft-exact-'.$number,
                'is_published' => false,
                'availability' => 'on_request',
                'price' => null,
            ]);
            $siteProducts[] = $siteProduct;

            $payload = [
                'registry_id' => 'bitrix:'.$number,
                'bitrix_id' => (string) $number,
                'name' => 'Legacy product '.$number,
                'legacy_section_path' => 'power',
                'legacy_url' => 'https://microchips.by/catalog/legacy/'.$number.'/',
                'target_category_external_id' => $category->external_id,
                'one_c_external_id' => $oneCExternalId,
                'identity_status' => 'linked_exact_name',
                'duplicate_candidate_key' => '',
                'transfer_status' => 'existing_one_c_exact_link',
                'allow_product_create' => false,
                'allow_publication' => false,
                'allow_indexing' => false,
                'allow_merge' => false,
            ];
            $checksumPayload = $payload;
            ksort($checksumPayload);
            $payload['source_checksum'] = hash('sha256', json_encode(
                $checksumPayload,
                JSON_THROW_ON_ERROR | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES,
            ));
            StagedImportRecord::create([
                'import_run_id' => $sourceRun->id,
                'row_number' => $number,
                'entity_type' => 'bitrix_full_catalog_product_evidence',
                'external_id' => 'bitrix:'.$number,
                'payload' => $payload,
                'normalized_payload' => [
                    'site_id' => $site->id,
                    'bitrix_id' => (string) $number,
                    'one_c_external_id' => $oneCExternalId,
                    'target_category_external_id' => $category->external_id,
                    'transfer_status' => 'existing_one_c_exact_link',
                    'source_checksum' => $payload['source_checksum'],
                ],
                'validation_errors' => [],
                'status' => 'staged_evidence',
            ]);
            $links[] = [
                'bitrix_external_id' => 'bitrix:'.$number,
                'one_c_external_id' => $oneCExternalId,
                'source_checksum' => $payload['source_checksum'],
                'target_category_external_id' => $category->external_id,
                'product_slug' => 'exact-product-'.$number,
                'target_path' => '/catalog/power/exact-product-'.$number,
                'legacy_source_path' => '/catalog/legacy/'.$number,
            ];
        }

        $file = tempnam(sys_get_temp_dir(), 'exact-link-previews-');
        file_put_contents($file, json_encode([
            'schema_version' => 1,
            'site_key' => $site->key,
            'source_run_id' => $sourceRun->id,
            'source_manifest_sha256' => $manifestHash,
            'source_records' => 4,
            'links' => $links,
        ], JSON_THROW_ON_ERROR | JSON_UNESCAPED_SLASHES | JSON_PRETTY_PRINT));

        return compact('site', 'root', 'category', 'siteProducts', 'file') + ['site_products' => $siteProducts];
    }
}
