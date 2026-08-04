<?php

namespace Tests\Feature;

use App\Models\Product;
use App\Models\Site;
use App\Models\SiteProduct;
use App\Models\SiteProductPriceEvidence;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class ImportVerifiedSitePricesTest extends TestCase
{
    use RefreshDatabase;

    public function test_one_c_price_is_multiplied_by_two_without_publishing_or_inventing_stock(): void
    {
        [$site, $siteProduct] = $this->catalogProduct();
        $file = $this->csv([
            ['ITEM-1', 'one_c_x2', '10.125', 'BYN', '2026-07-27T10:00:00+03:00', '1c://price-register/ITEM-1', '', 'retail'],
        ]);

        $this->artisan('catalog:import-verified-prices', ['site' => $site->key, 'file' => $file, '--apply' => true])
            ->assertSuccessful();

        $siteProduct->refresh();
        $this->assertSame('20.25', $siteProduct->price);
        $this->assertFalse($siteProduct->is_published);
        $this->assertSame('on_request', $siteProduct->availability);

        $evidence = SiteProductPriceEvidence::query()->sole();
        $this->assertSame('one_c_x2', $evidence->source);
        $this->assertSame('10.1250', $evidence->source_price);
        $this->assertSame('2.0000', $evidence->multiplier);
        $this->assertSame('20.25', $evidence->calculated_price);
        $this->assertTrue($evidence->is_current);
    }

    public function test_legacy_site_price_has_priority_over_newer_one_c_fallback(): void
    {
        [$site, $siteProduct] = $this->catalogProduct();
        $file = $this->csv([
            ['ITEM-1', 'legacy_site', '30.50', 'BYN', '2026-07-26T10:00:00+03:00', 'https://microchips.by/catalog/example/', '1', ''],
            ['ITEM-1', 'one_c_x2', '100', 'BYN', '2026-07-27T10:00:00+03:00', '1c://price-register/ITEM-1', '2', 'retail'],
        ]);

        $this->artisan('catalog:import-verified-prices', ['site' => $site->key, 'file' => $file, '--apply' => true])
            ->assertSuccessful();

        $this->assertSame('30.50', $siteProduct->refresh()->price);
        $this->assertSame(2, SiteProductPriceEvidence::query()->count());
        $this->assertSame(
            'legacy_site',
            SiteProductPriceEvidence::query()->where('is_current', true)->sole()->source
        );
    }

    public function test_invalid_currency_aborts_the_whole_file_without_writes(): void
    {
        [$site, $siteProduct] = $this->catalogProduct();
        $file = $this->csv([
            ['ITEM-1', 'one_c_x2', '10', 'USD', '2026-07-27T10:00:00+03:00', '1c://price-register/ITEM-1', '2', 'retail'],
        ]);

        $this->artisan('catalog:import-verified-prices', ['site' => $site->key, 'file' => $file, '--apply' => true])
            ->assertFailed();

        $this->assertNull($siteProduct->refresh()->price);
        $this->assertDatabaseCount('site_product_price_evidences', 0);
    }

    public function test_dry_run_validates_but_does_not_write(): void
    {
        [$site, $siteProduct] = $this->catalogProduct();
        $file = $this->csv([
            ['ITEM-1', 'legacy_site', '30.50', 'BYN', '2026-07-27T10:00:00+03:00', 'https://microchips.by/catalog/example/', '', ''],
        ]);

        $this->artisan('catalog:import-verified-prices', ['site' => $site->key, 'file' => $file])
            ->expectsOutputToContain('Dry run only')
            ->assertSuccessful();

        $this->assertNull($siteProduct->refresh()->price);
        $this->assertDatabaseCount('site_product_price_evidences', 0);
    }

    /** @return array{Site, SiteProduct} */
    private function catalogProduct(): array
    {
        $site = Site::create([
            'key' => 'microchips-by', 'domain' => 'microchips.by', 'country_code' => 'BY',
            'currency_code' => 'BYN', 'default_locale' => 'ru-BY', 'name' => 'Microchips Беларусь',
        ]);
        $product = Product::create([
            'external_id' => 'ITEM-1', 'slug' => 'item-1', 'name' => 'Тестовый товар', 'status' => 'draft',
        ]);
        $siteProduct = SiteProduct::create([
            'site_id' => $site->id, 'product_id' => $product->id, 'slug' => 'item-1',
            'is_published' => false, 'availability' => 'on_request', 'price' => null,
        ]);

        return [$site, $siteProduct];
    }

    /** @param list<array<int, string>> $rows */
    private function csv(array $rows): string
    {
        $path = tempnam(sys_get_temp_dir(), 'price-evidence-');
        $handle = fopen($path, 'wb');
        fputcsv($handle, ['product_external_id', 'source', 'source_price', 'currency', 'observed_at', 'source_reference', 'multiplier', 'price_type'], ';', '"', '');
        foreach ($rows as $row) {
            fputcsv($handle, $row, ';', '"', '');
        }
        fclose($handle);

        return $path;
    }
}
