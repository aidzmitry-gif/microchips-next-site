<?php

namespace Tests\Feature;

use App\Models\Category;
use App\Models\Product;
use App\Models\ProductDescriptionDraft;
use App\Models\ProductMedia;
use App\Models\Site;
use App\Models\SiteCategory;
use App\Models\SiteCategoryProduct;
use App\Models\SiteProduct;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class BuildCatalogEnrichmentQueueTest extends TestCase
{
    use RefreshDatabase;

    public function test_builds_fixed_target_queue_and_excludes_postponed_category(): void
    {
        $site = Site::create([
            'key' => 'microchips-by', 'domain' => 'microchips.by', 'country_code' => 'BY',
            'currency_code' => 'BYN', 'default_locale' => 'ru-BY', 'name' => 'Microchips BY',
        ]);
        $ups = $this->category($site, 'seo:batteries-ups', 'UPS batteries');
        $electronics = $this->category($site, 'seo:electronic-components', 'Electronics');
        $complete = $this->product($site, $ups, 'p-complete', 'Complete');
        $missingImage = $this->product($site, $ups, 'КА-00000001', 'Аккумулятор без изображения');
        $this->product($site, $electronics, 'p-electronics', 'Postponed');
        $complete->product->update([
            'manufacturer' => 'Verified Manufacturer',
            'sku' => 'COMPLETE-1',
            'technical_attributes' => ['voltage' => '12 V', 'capacity' => '7 Ah', '_internal' => 'ignored'],
        ]);
        $this->description($site, $complete);
        $this->description($site, $missingImage);
        ProductMedia::create([
            'product_id' => $complete->product_id, 'kind' => 'image', 'role' => 'primary',
            'source_page_url' => 'https://manufacturer.test/p-complete',
            'source_asset_url' => 'https://manufacturer.test/p-complete.jpg',
            'source_kind' => 'manufacturer', 'rights_basis' => 'manufacturer_media',
            'storage_path' => 'products/p-complete.jpg', 'content_sha256' => str_repeat('a', 64),
            'verification_status' => 'verified', 'verified_at' => now(), 'is_published' => true,
        ]);
        $output = storage_path('framework/testing/enrichment-'.uniqid().'.csv');
        $auditOutput = storage_path('framework/testing/enrichment-audit-'.uniqid().'.csv');

        $this->artisan('catalog:build-enrichment-queue', [
            'site' => $site->key,
            'output' => $output,
            '--baseline' => 20,
            '--target-percent' => 10,
            '--exclude-category' => ['seo:electronic-components'],
            '--audit-output' => $auditOutput,
        ])->assertSuccessful();

        $raw = (string) file_get_contents($output);
        $this->assertStringStartsWith("\xEF\xBB\xBF", $raw);
        $this->assertStringNotContainsString("\u{FFFD}", $raw);
        $this->assertStringContainsString('КА-00000001', $raw);
        $rows = array_map('str_getcsv', file($output, FILE_IGNORE_NEW_LINES));
        $this->assertCount(2, $rows);
        $this->assertSame('КА-00000001', $rows[1][1]);
        $summary = json_decode((string) file_get_contents(preg_replace('/\.csv$/', '', $output).'.summary.json'), true, flags: JSON_THROW_ON_ERROR);
        $this->assertSame(1, $summary['current_content_complete_cards']);
        $this->assertSame(1, $summary['queue_records']);
        $this->assertSame(0, $summary['remaining_gap_after_queue']);
        $this->assertSame($auditOutput, $summary['audit_output_path']);
        $this->assertSame(1, $summary['readiness_distribution']['strict_content_ready']);
        $this->assertSame(1, $summary['readiness_distribution']['source_backed_partial']);

        $auditRows = array_map('str_getcsv', file($auditOutput, FILE_IGNORE_NEW_LINES));
        $this->assertCount(3, $auditRows);
        $header = $auditRows[0];
        $header[0] = ltrim($header[0], "\xEF\xBB\xBF");
        $readinessIndex = array_search('readiness_class', $header, true);
        $externalIdIndex = array_search('product_external_id', $header, true);
        $this->assertNotFalse($readinessIndex);
        $this->assertNotFalse($externalIdIndex);
        $completeAudit = collect(array_slice($auditRows, 1))->first(
            static fn (array $row): bool => $row[$externalIdIndex] === 'p-complete'
        );
        $this->assertSame('strict_content_ready', $completeAudit[$readinessIndex]);
    }

    public function test_skip_file_omits_confirmed_holds_and_backfills_without_changing_completeness_metrics(): void
    {
        $site = Site::create([
            'key' => 'microchips-by', 'domain' => 'microchips.by', 'country_code' => 'BY',
            'currency_code' => 'BYN', 'default_locale' => 'ru-BY', 'name' => 'Microchips BY',
        ]);
        $ups = $this->category($site, 'seo:batteries-ups', 'UPS batteries');
        $complete = $this->product($site, $ups, 'p-complete', 'Complete');
        $held = $this->product($site, $ups, 'p-held', 'Confirmed hold');
        $backfill = $this->product($site, $ups, 'p-backfill', 'Backfill');
        $this->description($site, $complete);
        ProductMedia::create([
            'product_id' => $complete->product_id, 'kind' => 'image', 'role' => 'primary',
            'source_page_url' => 'https://manufacturer.test/p-complete',
            'source_asset_url' => 'https://manufacturer.test/p-complete.jpg',
            'source_kind' => 'manufacturer', 'rights_basis' => 'manufacturer_media',
            'storage_path' => 'products/p-complete.jpg', 'content_sha256' => str_repeat('b', 64),
            'verification_status' => 'verified', 'verified_at' => now(), 'is_published' => true,
        ]);
        $output = storage_path('framework/testing/enrichment-skip-'.uniqid().'.csv');
        $skipFile = storage_path('framework/testing/enrichment-skip-source-'.uniqid().'.csv');
        file_put_contents($skipFile, "\xEF\xBB\xBF\"product_external_id\"\r\n\"{$held->product->external_id}\"\r\n");

        $this->artisan('catalog:build-enrichment-queue', [
            'site' => $site->key,
            'output' => $output,
            '--baseline' => 20,
            '--target-percent' => 10,
            '--skip-file' => $skipFile,
        ])->assertSuccessful();

        $rows = array_map('str_getcsv', file($output, FILE_IGNORE_NEW_LINES));
        $this->assertCount(2, $rows);
        $this->assertSame($backfill->product->external_id, $rows[1][1]);
        $this->assertStringNotContainsString($held->product->external_id, (string) file_get_contents($output));
        $summary = json_decode((string) file_get_contents(preg_replace('/\.csv$/', '', $output).'.summary.json'), true, flags: JSON_THROW_ON_ERROR);
        $this->assertSame(3, $summary['eligible_site_products']);
        $this->assertSame(1, $summary['current_content_complete_cards']);
        $this->assertSame(1, $summary['skipped_hold_products']);
        $this->assertSame($skipFile, $summary['skip_file_path']);
        $this->assertSame(1, $summary['queue_records']);
    }

    public function test_skip_file_fails_closed_for_missing_header_empty_ids_and_duplicate_ids(): void
    {
        $site = Site::create([
            'key' => 'microchips-by', 'domain' => 'microchips.by', 'country_code' => 'BY',
            'currency_code' => 'BYN', 'default_locale' => 'ru-BY', 'name' => 'Microchips BY',
        ]);
        $output = storage_path('framework/testing/enrichment-invalid-skip-'.uniqid().'.csv');
        foreach ([
            "external_id\np-held\n",
            "product_external_id\n\n",
            "product_external_id\np-held\np-held\n",
        ] as $contents) {
            $skipFile = storage_path('framework/testing/enrichment-invalid-skip-source-'.uniqid().'.csv');
            file_put_contents($skipFile, $contents);

            $this->artisan('catalog:build-enrichment-queue', [
                'site' => $site->key,
                'output' => $output,
                '--baseline' => 20,
                '--target-percent' => 10,
                '--skip-file' => $skipFile,
            ])->assertFailed();
        }
    }

    private function category(Site $site, string $externalId, string $name): SiteCategory
    {
        $category = Category::create(['slug' => str_replace(':', '-', $externalId), 'name' => $name]);

        return SiteCategory::create([
            'site_id' => $site->id, 'source' => 'full_catalog_seo_tree', 'external_id' => $externalId,
            'category_id' => $category->id, 'slug' => 'catalog/'.str_replace('seo:', '', $externalId),
            'name' => $name, 'is_published' => false,
        ]);
    }

    private function product(Site $site, SiteCategory $category, string $externalId, string $name): SiteProduct
    {
        $product = Product::create(['external_id' => $externalId, 'slug' => $externalId, 'name' => $name, 'status' => 'active']);
        $siteProduct = SiteProduct::create([
            'site_id' => $site->id, 'product_id' => $product->id, 'slug' => $externalId,
            'is_published' => false, 'availability' => 'on_request',
        ]);
        SiteCategoryProduct::create([
            'site_id' => $site->id, 'site_category_id' => $category->id, 'site_product_id' => $siteProduct->id,
        ]);

        return $siteProduct;
    }

    private function description(Site $site, SiteProduct $siteProduct): void
    {
        $siteProduct->product->update(['short_description' => 'Verified description']);
        ProductDescriptionDraft::create([
            'product_id' => $siteProduct->product_id, 'locale' => $site->default_locale,
            'title' => $siteProduct->product->name, 'content' => 'Verified description',
            'verified_fields' => ['description'], 'source_urls' => ['https://manufacturer.test/product'],
            'status' => 'applied',
        ]);
    }
}
