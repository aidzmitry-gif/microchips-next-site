<?php

namespace Tests\Feature;

use App\Models\Category;
use App\Models\Product;
use App\Models\Site;
use App\Models\SiteCategory;
use App\Models\SiteProduct;
use App\Models\SiteProductPriceEvidence;
use App\Models\SiteSeo;
use App\Models\SiteUrl;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Artisan;
use Tests\TestCase;

class Wave244AFiammDuplicateCollapseDryRunTest extends TestCase
{
    use RefreshDatabase;

    public function test_checked_in_manifest_passes_real_command_without_apply(): void
    {
        $path = base_path('../docs/imports/rb-reviewed-fiamm-duplicates-wave244a-2026-07-30.json');
        $manifest = json_decode((string) file_get_contents($path), true, 512, JSON_THROW_ON_ERROR);
        $this->assertCount(2, $manifest['duplicates']);
        $site = Site::create([
            'key' => 'microchips-by', 'domain' => 'microchips-by.test', 'country_code' => 'BY',
            'currency_code' => 'BYN', 'default_locale' => 'ru-BY', 'name' => 'RB', 'is_active' => true,
        ]);
        $siteCategories = [];
        foreach (['410', 'seo:batteries-ups'] as $offset => $externalId) {
            $category = Category::create(['slug' => 'wave244a-'.$offset, 'name' => $externalId]);
            $siteCategories[$externalId] = SiteCategory::create([
                'site_id' => $site->id, 'category_id' => $category->id, 'source' => 'test',
                'external_id' => $externalId, 'slug' => 'wave244a-'.$offset,
                'name' => $externalId, 'is_published' => true,
            ]);
        }

        foreach ($manifest['duplicates'] as $offset => $row) {
            $canonical = Product::create([
                'external_id' => $row['survivor_external_id'], 'name' => $row['survivor_name'],
                'manufacturer' => $row['manufacturer'], 'mpn' => $row['survivor_mpn'],
                'slug' => 'wave244a-survivor-'.$offset, 'status' => 'active',
            ]);
            $legacy = Product::create([
                'external_id' => $row['duplicate_external_id'], 'name' => $row['duplicate_name'],
                'slug' => 'wave244a-duplicate-'.$offset, 'status' => 'active',
            ]);
            $price = $row['model_core'] === '12FGH36' ? '126.00' : '19.00';
            $survivor = SiteProduct::create([
                'site_id' => $site->id, 'product_id' => $canonical->id,
                'slug' => 'wave244a-survivor-'.$offset, 'is_published' => true,
                'availability' => 'on_request', 'price' => $price,
            ]);
            $duplicate = SiteProduct::create([
                'site_id' => $site->id, 'product_id' => $legacy->id,
                'slug' => 'wave244a-duplicate-'.$offset, 'is_published' => true,
                'availability' => 'on_request',
            ]);
            foreach ($row['category_external_ids'] as $externalId) {
                $survivor->categories()->attach($siteCategories[$externalId]->id, ['site_id' => $site->id]);
            }
            foreach ($row['duplicate_category_external_ids'] as $externalId) {
                $duplicate->categories()->attach($siteCategories[$externalId]->id, ['site_id' => $site->id]);
            }
            foreach ([[$survivor, $row['survivor_path']], [$duplicate, $row['duplicate_path']]] as [$sp, $url]) {
                SiteUrl::create(['site_id' => $site->id, 'path' => $url, 'locale' => 'ru-BY', 'target_type' => 'product', 'target_id' => $sp->id, 'is_indexable' => false]);
                SiteSeo::create(['site_id' => $site->id, 'locale' => 'ru-BY', 'resource_type' => 'product', 'resource_id' => $sp->id, 'canonical_path' => $url, 'is_indexable' => false, 'schema' => null]);
            }
            SiteProductPriceEvidence::create([
                'site_id' => $site->id, 'site_product_id' => $survivor->id,
                'source' => SiteProductPriceEvidence::SOURCE_LEGACY_SITE,
                'source_price' => $price, 'multiplier' => '1.0000', 'calculated_price' => $price,
                'currency' => 'BYN', 'source_reference' => 'bitrix-backup://wave244a/'.$offset,
                'observed_at' => '2026-06-23T00:00:00+03:00',
                'evidence_key' => hash('sha256', 'wave244a-'.$offset), 'is_current' => true,
            ]);
        }

        $exitCode = Artisan::call('catalog:collapse-verified-noindex-duplicates', [
            'site' => 'microchips-by', 'file' => $path,
        ]);
        $this->assertSame(0, $exitCode, Artisan::output());
        $this->assertDatabaseCount('site_products', 4);
        $this->assertDatabaseCount('site_redirects', 0);
    }
}
