<?php

namespace Tests\Feature;

use App\Domain\Content\ProductDescriptionDrafter;
use App\Models\Product;
use App\Models\ProductDescriptionDraft;
use App\Models\Site;
use App\Models\SiteProduct;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class ApplyVerifiedDescriptionDraftsCommandTest extends TestCase
{
    use RefreshDatabase;

    public function test_it_applies_only_source_backed_content_without_publishing_or_changing_commercial_fields(): void
    {
        $site = Site::create(['key' => 'microchips-by', 'domain' => 'microchips-by.test', 'country_code' => 'BY', 'currency_code' => 'BYN', 'default_locale' => 'ru-BY', 'name' => 'Microchips Беларусь', 'is_active' => true]);
        $product = Product::create(['external_id' => '1c-br2330', 'name' => 'Panasonic BR2330', 'slug' => 'panasonic-br2330', 'status' => 'active']);
        $link = SiteProduct::create(['site_id' => $site->id, 'product_id' => $product->id, 'slug' => 'panasonic-br2330', 'is_published' => false, 'availability' => 'on_request', 'price' => null]);
        app(ProductDescriptionDrafter::class)->createDraft([
            'name' => $product->name, 'manufacturer' => 'Panasonic', 'mpn' => 'BR2330', 'technology' => 'Lithium',
            'technical_attributes' => ['Номинальное напряжение' => '3 V'],
        ], ['https://manufacturer.example.test/br2330'], $product, null, 'ru-BY');
        $file = tempnam(sys_get_temp_dir(), 'apply-description-');
        file_put_contents($file, json_encode(['locale' => 'ru-BY', 'products' => [['external_id' => '1c-br2330', 'source_url' => 'https://manufacturer.example.test/br2330']]], JSON_THROW_ON_ERROR));

        try {
            $this->artisan('content:apply-verified-description-drafts', ['site' => 'microchips-by', 'file' => $file])->assertSuccessful();
            $this->assertNull($product->refresh()->short_description);
            $this->artisan('content:apply-verified-description-drafts', ['site' => 'microchips-by', 'file' => $file, '--apply' => true])->assertSuccessful();
            $this->assertNotNull($product->refresh()->short_description);
            $this->assertSame('3 V', $product->technical_attributes['Номинальное напряжение']);
            $this->assertSame('Panasonic', $product->manufacturer);
            $this->assertSame('BR2330', $product->mpn);
            $this->assertFalse($link->refresh()->is_published);
            $this->assertNull($link->price);
        } finally {
            @unlink($file);
        }
    }

    public function test_it_applies_model_core_content_without_writing_an_mpn(): void
    {
        $site = Site::create(['key' => 'microchips-by', 'domain' => 'microchips-by.test', 'country_code' => 'BY', 'currency_code' => 'BYN', 'default_locale' => 'ru-BY', 'name' => 'RB', 'is_active' => true]);
        $product = Product::create([
            'external_id' => '1c-saft-ls14500', 'name' => 'LS 14500 CNR (SAFT) литиевый элемент',
            'slug' => 'saft-ls-14500-cnr', 'status' => 'active',
            'technical_attributes' => ['Устаревшая ёмкость' => 'неподтверждено', 'Сохранить' => 'да'],
        ]);
        $link = SiteProduct::create(['site_id' => $site->id, 'product_id' => $product->id, 'slug' => 'saft-ls-14500-cnr', 'is_published' => false, 'availability' => 'on_request', 'price' => null]);
        $file = tempnam(sys_get_temp_dir(), 'apply-description-');
        file_put_contents($file, json_encode(['locale' => 'ru-BY', 'products' => [[
            'external_id' => '1c-saft-ls14500', 'identity_scope' => 'model_core',
            'manufacturer' => 'Saft', 'model_core' => 'LS14500',
            'source_url' => 'https://manufacturer.example.test/saft-ls-series',
            'remove_technical_attributes' => ['Устаревшая ёмкость'],
            'technical_attributes' => ['Номинальное напряжение' => '3,6 В', 'Типоразмер' => 'AA'],
        ]]], JSON_THROW_ON_ERROR | JSON_UNESCAPED_UNICODE));

        try {
            $this->artisan('content:stage-source-backed-description-drafts', [
                'site' => 'microchips-by', 'file' => $file, '--apply' => true,
            ])->assertSuccessful();
            $this->artisan('content:apply-verified-description-drafts', [
                'site' => 'microchips-by', 'file' => $file, '--apply' => true,
            ])->assertSuccessful();

            $product->refresh();
            $this->assertSame('Saft', $product->manufacturer);
            $this->assertNull($product->mpn);
            $this->assertSame('3,6 В', $product->technical_attributes['Номинальное напряжение']);
            $this->assertArrayNotHasKey('Устаревшая ёмкость', $product->technical_attributes);
            $this->assertSame('да', $product->technical_attributes['Сохранить']);
            $this->assertStringContainsString('LS14500', $product->short_description);
            $this->assertFalse($link->refresh()->is_published);
            $this->assertNull($link->price);

            $product->update(['technical_attributes' => [
                ...$product->technical_attributes,
                'Устаревшая ёмкость' => 'вернулась из старого импорта',
            ]]);
            $this->artisan('content:stage-source-backed-description-drafts', [
                'site' => 'microchips-by', 'file' => $file, '--refresh-existing' => true,
                '--refresh-applied' => true, '--apply' => true,
            ])->assertSuccessful();
            $this->artisan('content:apply-verified-description-drafts', [
                'site' => 'microchips-by', 'file' => $file, '--apply' => true,
            ])->assertSuccessful();
            $this->assertArrayNotHasKey('Устаревшая ёмкость', $product->refresh()->technical_attributes);
        } finally {
            @unlink($file);
        }
    }

    public function test_it_revalidates_model_core_boundaries_before_apply(): void
    {
        $site = Site::create(['key' => 'microchips-by', 'domain' => 'microchips-by.test', 'country_code' => 'BY', 'currency_code' => 'BYN', 'default_locale' => 'ru-BY', 'name' => 'RB', 'is_active' => true]);
        $product = Product::create(['external_id' => '1c-saft-lsh20', 'name' => 'SAFT LSH20 lithium cell', 'slug' => 'saft-lsh20', 'manufacturer' => 'Saft', 'status' => 'active']);
        SiteProduct::create(['site_id' => $site->id, 'product_id' => $product->id, 'slug' => 'saft-lsh20']);
        app(ProductDescriptionDrafter::class)->createDraft([
            'name' => $product->name, 'manufacturer' => 'Saft', 'model' => 'LSH20',
            'technical_attributes' => ['Voltage' => '3.6 V'],
        ], ['https://manufacturer.example.test/saft-lsh-series'], $product, null, 'ru-BY');
        $product->update(['name' => 'SAFT LSH200 lithium cell']);
        $file = tempnam(sys_get_temp_dir(), 'apply-description-');
        file_put_contents($file, json_encode(['locale' => 'ru-BY', 'products' => [[
            'external_id' => '1c-saft-lsh20', 'identity_scope' => 'model_core',
            'manufacturer' => 'Saft', 'model_core' => 'LSH20',
            'source_url' => 'https://manufacturer.example.test/saft-lsh-series',
        ]]], JSON_THROW_ON_ERROR));

        try {
            $this->artisan('content:apply-verified-description-drafts', [
                'site' => 'microchips-by', 'file' => $file, '--apply' => true,
            ])->assertFailed();
            $this->assertNull($product->refresh()->short_description);
            $this->assertSame('draft', ProductDescriptionDraft::query()->sole()->status);
        } finally {
            @unlink($file);
        }
    }
}
