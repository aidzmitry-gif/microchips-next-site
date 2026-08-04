<?php

namespace Tests\Feature;

use App\Models\Product;
use App\Models\ProductDescriptionDraft;
use App\Models\Site;
use App\Models\SiteProduct;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class ManufacturerProductPageDescriptionWorkflowTest extends TestCase
{
    use RefreshDatabase;

    public function test_it_stages_exact_product_page_evidence_without_publication_or_commercial_changes(): void
    {
        [$site, $product, $siteProduct] = $this->product('1c:ippon-back-basic-650', 'IPPON Back Basic 650');
        $file = $this->manifest($product->external_id, 'exact');

        try {
            $this->artisan('content:stage-source-backed-description-drafts', [
                'site' => $site->key, 'file' => $file, '--apply' => true,
            ])->assertSuccessful();

            $draft = ProductDescriptionDraft::query()->sole();
            $this->assertSame('official_manufacturer_product_page', $draft->source_kind);
            $this->assertSame('manufacturer_primary', $draft->source_tier);
            $this->assertSame('exact', $draft->identity_scope);
            $this->assertTrue($draft->manufacturer_primary);
            $this->assertSame('Back Basic 650', $draft->verified_fields['mpn']);
            $this->assertNull($product->refresh()->manufacturer);
            $this->assertNull($product->mpn);
            $this->assertSame('on_request', $siteProduct->refresh()->availability);
            $this->assertSame('42.00', $siteProduct->price);
            $this->assertFalse($siteProduct->is_published);
        } finally {
            @unlink($file);
        }
    }

    public function test_it_stages_model_core_product_page_evidence_without_changing_legacy_identity(): void
    {
        [$site, $product, $siteProduct] = $this->product('1c:panasonic-cr123a', 'Panasonic CR123A 1BP');
        $product->update(['manufacturer' => 'Panasonic', 'mpn' => 'legacy-pack-1bp', 'sku' => 'legacy-sku']);
        $file = $this->manifest($product->external_id, 'model_core');

        try {
            $this->artisan('content:stage-source-backed-description-drafts', [
                'site' => $site->key, 'file' => $file, '--apply' => true,
            ])->assertSuccessful();

            $draft = ProductDescriptionDraft::query()->sole();
            $this->assertSame('official_manufacturer_product_page', $draft->source_kind);
            $this->assertSame('model_core', $draft->identity_scope);
            $this->assertArrayNotHasKey('mpn', $draft->verified_fields);
            $this->assertSame('legacy-pack-1bp', $product->refresh()->mpn);
            $this->assertSame('legacy-sku', $product->sku);
            $this->assertSame('on_request', $siteProduct->refresh()->availability);
            $this->assertSame('42.00', $siteProduct->price);
            $this->assertFalse($siteProduct->is_published);
        } finally {
            @unlink($file);
        }
    }

    /** @return array{Site, Product, SiteProduct} */
    private function product(string $externalId, string $name): array
    {
        $site = Site::create(['key' => 'microchips-by', 'domain' => 'microchips-by.test', 'country_code' => 'BY', 'currency_code' => 'BYN', 'default_locale' => 'ru-BY', 'name' => 'RB', 'is_active' => true]);
        $product = Product::create(['external_id' => $externalId, 'name' => $name, 'slug' => 'draft-'.str_replace(':', '-', $externalId), 'status' => 'active']);
        $siteProduct = SiteProduct::create(['site_id' => $site->id, 'product_id' => $product->id, 'slug' => 'draft-'.str_replace(':', '-', $externalId), 'is_published' => false, 'availability' => 'on_request', 'price' => '42.00']);

        return [$site, $product, $siteProduct];
    }

    private function manifest(string $externalId, string $scope): string
    {
        $exact = $scope === 'exact';
        $row = [
            'external_id' => $externalId,
            'identity_scope' => $exact ? 'exact' : 'model_core',
            'manufacturer' => $exact ? 'IPPON' : 'Panasonic',
            'technology' => $exact ? 'Line-interactive UPS' : 'Lithium primary cell',
            'source_url' => $exact ? 'https://ippon.example.test/products/back-basic-650' : 'https://panasonic.example.test/batteries/cr123a',
            'technical_attributes' => $exact ? ['Topology' => 'Line-interactive'] : ['Voltage' => '3 V'],
            'source_kind' => 'official_manufacturer_product_page',
            'source_tier' => 'manufacturer_primary',
            'source_publisher' => $exact ? 'IPPON' : 'Panasonic',
            'manufacturer_primary' => true,
            'evidence_scope' => $exact ? 'exact_model' : 'model_core',
            'checked_at' => '2026-07-29',
        ];
        $row[$exact ? 'mpn' : 'model_core'] = $exact ? 'Back Basic 650' : 'CR123A';
        $file = tempnam(sys_get_temp_dir(), 'manufacturer-product-page-');
        file_put_contents($file, json_encode(['locale' => 'ru-BY', 'products' => [$row]], JSON_THROW_ON_ERROR | JSON_UNESCAPED_UNICODE));

        return $file;
    }
}
