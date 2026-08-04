<?php

namespace Tests\Feature;

use App\Models\Product;
use App\Models\ProductMedia;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Storage;
use Tests\TestCase;

class ProductMediaVisibilityTest extends TestCase
{
    use RefreshDatabase;

    public function test_only_locally_stored_rights_verified_images_are_storefront_ready(): void
    {
        $product = Product::create([
            'external_id' => '1c-media-test',
            'name' => 'Verified media test product',
            'slug' => 'verified-media-test-product',
            'status' => 'active',
        ]);

        ProductMedia::create([
            'product_id' => $product->id,
            'source_page_url' => 'https://manufacturer.example.test/product',
            'source_asset_url' => 'https://manufacturer.example.test/image.jpg',
            'verification_status' => 'pending',
            'is_published' => false,
        ]);
        ProductMedia::create([
            'product_id' => $product->id,
            'source_page_url' => 'https://manufacturer.example.test/product',
            'source_asset_url' => 'https://manufacturer.example.test/verified.jpg',
            'rights_basis' => 'manufacturer product asset approved for catalogue use',
            'storage_path' => 'products/verified-media-test-product.jpg',
            'content_sha256' => str_repeat('a', 64),
            'verification_status' => 'verified',
            'is_published' => true,
        ]);

        $this->assertSame(1, ProductMedia::query()->storefrontReady()->count());
        $this->assertSame('products/verified-media-test-product.jpg', ProductMedia::query()->storefrontReady()->sole()->storage_path);
        $this->assertSame(1, ProductMedia::query()->previewReady()->count());
    }

    public function test_media_endpoint_denies_pending_assets_and_serves_only_verified_local_files(): void
    {
        Storage::fake('public');
        $product = Product::create(['external_id' => '1c-media-endpoint', 'name' => 'Media endpoint product', 'slug' => 'media-endpoint-product', 'status' => 'active']);
        $pending = ProductMedia::create(['product_id' => $product->id, 'source_page_url' => 'legacy://pending', 'verification_status' => 'pending', 'is_published' => false]);
        $path = 'product-media/media-endpoint.png';
        Storage::disk('public')->put($path, base64_decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAFgAI/ScL9pAAAAABJRU5ErkJggg=='));
        $verified = ProductMedia::create([
            'product_id' => $product->id, 'source_page_url' => 'legacy://verified', 'rights_basis' => 'company-owned archive',
            'storage_path' => $path, 'content_sha256' => str_repeat('b', 64), 'verification_status' => 'verified', 'is_published' => true,
        ]);

        $this->getJson("/api/v1/media/{$pending->id}")->assertNotFound();
        $this->get("/api/v1/media/{$verified->id}")->assertOk()->assertHeader('content-type', 'image/png');
    }

    public function test_exact_legacy_preview_media_is_visible_but_does_not_become_strictly_verified(): void
    {
        Storage::fake('public');
        $product = Product::create(['external_id' => 'bitrix:101', 'name' => 'Legacy preview', 'slug' => 'legacy-bitrix-101', 'status' => 'draft']);
        $path = 'legacy-staging/rb/bitrix-101-501.png';
        Storage::disk('public')->put($path, base64_decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAFgAI/ScL9pAAAAABJRU5ErkJggg=='));
        $preview = ProductMedia::create([
            'product_id' => $product->id, 'source_page_url' => 'bitrix-backup://element/101',
            'source_kind' => 'legacy_bitrix_exact_element_preview', 'rights_basis' => 'company-owned archive',
            'storage_path' => $path, 'content_sha256' => str_repeat('c', 64),
            'verification_status' => ProductMedia::STATUS_LEGACY_EXACT_PREVIEW, 'is_published' => true,
        ]);

        $this->assertSame(0, ProductMedia::query()->storefrontReady()->count());
        $this->assertSame(1, ProductMedia::query()->previewReady()->count());
        $this->get("/api/v1/media/{$preview->id}")->assertOk()
            ->assertHeader('X-Robots-Tag', 'noindex, noarchive');
    }
}
