<?php

namespace Tests\Feature;

use App\Models\Product;
use App\Models\ProductDescriptionDraft;
use App\Models\Site;
use App\Models\SiteProduct;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class DealerBackedDescriptionWorkflowTest extends TestCase
{
    use RefreshDatabase;

    public function test_dealer_backed_content_persists_provenance_without_changing_identity_or_commercial_fields(): void
    {
        $site = Site::create(['key' => 'microchips-by', 'domain' => 'microchips-by.test', 'country_code' => 'BY', 'currency_code' => 'BYN', 'default_locale' => 'ru-BY', 'name' => 'RB', 'is_active' => true]);
        $product = Product::create(['external_id' => '1c-delta-dt612', 'name' => 'Аккумулятор Delta DT 612', 'slug' => 'delta-dt-612', 'manufacturer' => null, 'mpn' => null, 'status' => 'active']);
        $siteProduct = SiteProduct::create(['site_id' => $site->id, 'product_id' => $product->id, 'slug' => 'delta-dt-612', 'is_published' => false, 'availability' => 'on_request', 'price' => '42.00']);
        $file = $this->manifestFile($product->external_id, ['Nominal voltage' => '6 V', 'Nominal capacity' => '12 Ah']);

        try {
            $this->artisan('content:stage-source-backed-description-drafts', ['site' => $site->key, 'file' => $file, '--apply' => true])->assertSuccessful();
            $draft = ProductDescriptionDraft::query()->sole();
            $this->assertSame('dealer_backed', $draft->source_tier);
            $this->assertSame('ООО «Спектр РС»', $draft->source_publisher);
            $this->assertFalse($draft->manufacturer_primary);

            $this->artisan('content:apply-verified-description-drafts', ['site' => $site->key, 'file' => $file, '--apply' => true])->assertSuccessful();
            $product->refresh();
            $this->assertSame('Аккумулятор Delta DT 612', $product->name);
            $this->assertNull($product->manufacturer);
            $this->assertNull($product->mpn);
            $this->assertSame('6 V', $product->technical_attributes['Nominal voltage']);
            $this->assertSame('VRLA AGM', $product->technical_attributes['Технология']);
            $this->assertFalse($siteProduct->refresh()->is_published);
            $this->assertSame('42.00', $siteProduct->price);
            $this->assertSame('on_request', $siteProduct->availability);
        } finally {
            @unlink($file);
        }
    }

    public function test_dealer_backed_content_rejects_prohibited_attributes_and_conflicts(): void
    {
        $site = Site::create(['key' => 'microchips-by', 'domain' => 'microchips-by.test', 'country_code' => 'BY', 'currency_code' => 'BYN', 'default_locale' => 'ru-BY', 'name' => 'RB', 'is_active' => true]);
        $product = Product::create(['external_id' => '1c-delta-dt612', 'name' => 'Аккумулятор Delta DT 612', 'slug' => 'delta-dt-612', 'manufacturer' => 'Delta', 'status' => 'active', 'technical_attributes' => ['Nominal voltage' => '12 V']]);
        SiteProduct::create(['site_id' => $site->id, 'product_id' => $product->id, 'slug' => 'delta-dt-612']);
        $prohibited = $this->manifestFile($product->external_id, ['Terminal' => 'F2']);
        $conflict = $this->manifestFile($product->external_id, ['Nominal voltage' => '6 V']);

        try {
            $this->artisan('content:stage-source-backed-description-drafts', ['site' => $site->key, 'file' => $prohibited, '--apply' => true])->assertFailed();
            $this->assertDatabaseCount('product_description_drafts', 0);

            $this->artisan('content:stage-source-backed-description-drafts', ['site' => $site->key, 'file' => $conflict, '--apply' => true])->assertSuccessful();
            $this->artisan('content:apply-verified-description-drafts', ['site' => $site->key, 'file' => $conflict, '--apply' => true])->assertFailed();
            $this->assertSame('12 V', $product->refresh()->technical_attributes['Nominal voltage']);
            $this->assertNull($product->short_description);
        } finally {
            @unlink($prohibited);
            @unlink($conflict);
        }
    }

    /** @param array<string, string> $attributes */
    private function manifestFile(string $externalId, array $attributes): string
    {
        $file = tempnam(sys_get_temp_dir(), 'dealer-description-');
        file_put_contents($file, json_encode(['locale' => 'ru-BY', 'products' => [[
            'external_id' => $externalId,
            'identity_scope' => 'model_core',
            'manufacturer' => 'Delta',
            'model_core' => 'DT 612',
            'technology' => 'VRLA AGM',
            'source_url' => 'https://dealer.example.test/delta-dt-612',
            'technical_attributes' => $attributes,
            'source_kind' => 'official_dealer_product_page',
            'source_tier' => 'dealer_backed',
            'source_publisher' => 'ООО «Спектр РС»',
            'manufacturer_primary' => false,
            'evidence_scope' => 'model_core',
            'checked_at' => '2026-07-28',
        ]]], JSON_THROW_ON_ERROR | JSON_UNESCAPED_UNICODE));

        return $file;
    }
}
