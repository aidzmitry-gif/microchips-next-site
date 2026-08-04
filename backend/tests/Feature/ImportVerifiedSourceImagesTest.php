<?php

namespace Tests\Feature;

use App\Models\Product;
use App\Models\ProductMedia;
use App\Models\Site;
use App\Models\SiteProduct;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Storage;
use Tests\TestCase;

class ImportVerifiedSourceImagesTest extends TestCase
{
    use RefreshDatabase;

    public function test_it_promotes_an_exact_pending_candidate_only_with_hash_identity_and_rights_evidence(): void
    {
        Storage::fake('public');
        $site = Site::create([
            'key' => 'microchips-by', 'domain' => 'microchips-by.test',
            'country_code' => 'BY', 'currency_code' => 'BYN',
            'default_locale' => 'ru-BY', 'name' => 'RB', 'is_active' => true,
        ]);
        $product = Product::create([
            'external_id' => '1c-gpl1272', 'name' => 'CSB GPL1272',
            'slug' => 'csb-gpl1272', 'manufacturer' => 'CSB',
            'mpn' => 'GPL1272', 'status' => 'active',
        ]);
        SiteProduct::create([
            'site_id' => $site->id, 'product_id' => $product->id,
            'slug' => 'csb-gpl1272', 'is_published' => true,
            'availability' => 'on_request',
        ]);
        $candidate = ProductMedia::create([
            'product_id' => $product->id, 'kind' => 'image', 'role' => 'primary',
            'source_page_url' => 'https://manufacturer.example.test/gpl1272',
            'source_asset_url' => 'https://manufacturer.example.test/gpl1272.png',
            'source_kind' => 'official manufacturer product page',
            'verification_status' => 'pending', 'is_published' => false,
        ]);

        $root = sys_get_temp_dir().DIRECTORY_SEPARATOR.'source-media-'.uniqid();
        mkdir($root);
        $image = $root.DIRECTORY_SEPARATOR.'gpl1272.png';
        file_put_contents($image, base64_decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAFgAI/ScL9pAAAAABJRU5ErkJggg=='));
        $manifest = $root.DIRECTORY_SEPARATOR.'manifest.json';
        $row = [
            'external_id' => '1c-gpl1272', 'mpn' => 'GPL1272',
            'asset_file' => 'gpl1272.png', 'sha256' => hash_file('sha256', $image),
            'source_page_url' => 'https://manufacturer.example.test/gpl1272',
            'source_asset_url' => 'https://manufacturer.example.test/gpl1272.png',
            'source_kind' => 'official manufacturer product page',
            'rights_basis' => 'manufacturer media explicitly licensed for dealer product presentation',
            'visual_verification_note' => 'Visible product label exactly reads GPL1272.',
        ];
        file_put_contents($manifest, json_encode(['locale' => 'ru-BY', 'images' => [$row]], JSON_THROW_ON_ERROR));

        try {
            $this->artisan('media:import-verified-source-images', [
                'site' => 'microchips-by', 'file' => $manifest, '--assets-root' => $root,
            ])->expectsOutputToContain('"promoted": 1')->assertSuccessful();
            $this->assertFalse($candidate->fresh()->is_published);

            $this->artisan('media:import-verified-source-images', [
                'site' => 'microchips-by', 'file' => $manifest,
                '--assets-root' => $root, '--apply' => true,
            ])->expectsOutputToContain('"published": 1')->assertSuccessful();

            $candidate->refresh();
            $this->assertSame('verified', $candidate->verification_status);
            $this->assertTrue($candidate->is_published);
            $this->assertSame($row['rights_basis'], $candidate->rights_basis);
            $this->assertSame($row['sha256'], $candidate->content_sha256);
            Storage::disk('public')->assertExists($candidate->storage_path);

            $this->artisan('media:import-verified-source-images', [
                'site' => 'microchips-by', 'file' => $manifest,
                '--assets-root' => $root, '--apply' => true,
            ])->expectsOutputToContain('"unchanged": 1')->assertSuccessful();
            $this->assertSame(1, ProductMedia::query()->count());
        } finally {
            @unlink($manifest);
            @unlink($image);
            @rmdir($root);
        }
    }

    public function test_it_rejects_a_source_image_without_rights_evidence(): void
    {
        $site = Site::create([
            'key' => 'microchips-by', 'domain' => 'microchips-by.test',
            'country_code' => 'BY', 'currency_code' => 'BYN',
            'default_locale' => 'ru-BY', 'name' => 'RB', 'is_active' => true,
        ]);
        $product = Product::create([
            'external_id' => '1c-gpl1272', 'name' => 'CSB GPL1272',
            'slug' => 'csb-gpl1272', 'mpn' => 'GPL1272', 'status' => 'active',
        ]);
        SiteProduct::create([
            'site_id' => $site->id, 'product_id' => $product->id,
            'slug' => 'csb-gpl1272', 'is_published' => true,
            'availability' => 'on_request',
        ]);

        $root = sys_get_temp_dir().DIRECTORY_SEPARATOR.'source-media-'.uniqid();
        mkdir($root);
        $image = $root.DIRECTORY_SEPARATOR.'gpl1272.png';
        file_put_contents($image, base64_decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAFgAI/ScL9pAAAAABJRU5ErkJggg=='));
        $manifest = $root.DIRECTORY_SEPARATOR.'manifest.json';
        file_put_contents($manifest, json_encode(['locale' => 'ru-BY', 'images' => [[
            'external_id' => '1c-gpl1272', 'mpn' => 'GPL1272',
            'asset_file' => 'gpl1272.png', 'sha256' => hash_file('sha256', $image),
            'source_page_url' => 'https://manufacturer.example.test/gpl1272',
            'source_asset_url' => 'https://manufacturer.example.test/gpl1272.png',
            'source_kind' => 'official manufacturer product page',
            'rights_basis' => '',
            'visual_verification_note' => 'Visible product label exactly reads GPL1272.',
        ]]], JSON_THROW_ON_ERROR));

        try {
            $this->artisan('media:import-verified-source-images', [
                'site' => 'microchips-by', 'file' => $manifest, '--assets-root' => $root,
            ])->expectsOutputToContain('requires rights_basis')->assertFailed();
            $this->assertDatabaseCount('product_media', 0);
        } finally {
            @unlink($manifest);
            @unlink($image);
            @rmdir($root);
        }
    }
}
