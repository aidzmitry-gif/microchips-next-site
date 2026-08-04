<?php

namespace Tests\Feature;

use App\Models\Product;
use App\Models\Site;
use App\Models\SiteProduct;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Storage;
use Tests\TestCase;

class ImportVerifiedLegacyImagesTest extends TestCase
{
    use RefreshDatabase;

    public function test_it_imports_visible_model_core_media_without_inventing_an_mpn(): void
    {
        Storage::fake('public');
        $site = Site::create(['key' => 'microchips-by', 'domain' => 'microchips-by.test', 'country_code' => 'BY', 'currency_code' => 'BYN', 'default_locale' => 'ru-BY', 'name' => 'RB', 'is_active' => true]);
        $product = Product::create(['external_id' => '1c-gp1272', 'name' => 'CSB GP1272 F2', 'slug' => 'csb-gp1272', 'manufacturer' => null, 'mpn' => null, 'status' => 'active']);
        SiteProduct::create(['site_id' => $site->id, 'product_id' => $product->id, 'slug' => 'csb-gp1272', 'is_published' => true, 'availability' => 'on_request']);
        $root = sys_get_temp_dir().DIRECTORY_SEPARATOR.'legacy-media-core-'.uniqid();
        mkdir($root);
        $file = $root.DIRECTORY_SEPARATOR.'gp1272.png';
        file_put_contents($file, base64_decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAFgAI/ScL9pAAAAABJRU5ErkJggg=='));
        $hash = hash_file('sha256', $file);
        $manifest = $root.DIRECTORY_SEPARATOR.'manifest.json';
        file_put_contents($manifest, json_encode(['images' => [[
            'external_id' => '1c-gp1272', 'identity_scope' => 'model_core', 'model_core' => 'GP1272', 'manufacturer' => 'CSB',
            'asset_file' => 'gp1272.png', 'sha256' => $hash, 'archive_member' => '_shared/upload/gp1272.png',
            'rights_basis' => 'company-owned legacy backup', 'identity_evidence_level' => 'visible_exact_model_core',
            'visual_verification_note' => 'Visible label reads GP1272 and 12V 7.2Ah.',
        ]]], JSON_THROW_ON_ERROR));

        try {
            $this->artisan('media:import-verified-legacy-images', [
                'site' => 'microchips-by', 'file' => $manifest, '--assets-root' => $root, '--apply' => true,
            ])->assertSuccessful();
            $this->assertDatabaseHas('product_media', ['product_id' => $product->id, 'content_sha256' => $hash, 'is_published' => true]);
            $this->assertNull($product->refresh()->manufacturer);
            $this->assertNull($product->refresh()->mpn);
        } finally {
            @unlink($manifest);
            @unlink($file);
            @rmdir($root);
        }
    }

    public function test_it_requires_hash_model_rights_and_a_published_site_product_before_importing_legacy_media(): void
    {
        Storage::fake('public');
        $site = Site::create(['key' => 'microchips-by', 'domain' => 'microchips-by.test', 'country_code' => 'BY', 'currency_code' => 'BYN', 'default_locale' => 'ru-BY', 'name' => 'RB', 'is_active' => true]);
        $product = Product::create(['external_id' => '1c-dtm6012', 'name' => 'Delta DTM 6012', 'slug' => 'delta-dtm6012', 'manufacturer' => 'Delta', 'mpn' => 'DTM6012', 'status' => 'active']);
        SiteProduct::create(['site_id' => $site->id, 'product_id' => $product->id, 'slug' => 'delta-dtm6012', 'is_published' => true, 'availability' => 'on_request']);
        $root = sys_get_temp_dir().DIRECTORY_SEPARATOR.'legacy-media-'.uniqid();
        mkdir($root);
        $file = $root.DIRECTORY_SEPARATOR.'dtm6012.png';
        // Valid 1×1 PNG; source bytes are deliberately independent of public storage.
        file_put_contents($file, base64_decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAFgAI/ScL9pAAAAABJRU5ErkJggg=='));
        $hash = hash_file('sha256', $file);
        $manifest = $root.DIRECTORY_SEPARATOR.'manifest.json';
        file_put_contents($manifest, json_encode(['images' => [[
            'external_id' => '1c-dtm6012', 'mpn' => 'DTM6012', 'asset_file' => 'dtm6012.png', 'sha256' => $hash,
            'archive_member' => '_shared/upload/iblock/test/dtm6012.png', 'rights_basis' => 'company-owned legacy backup',
            'visual_verification_note' => 'Visible label matched DTM6012.',
        ]]], JSON_THROW_ON_ERROR));

        try {
            $this->artisan('media:import-verified-legacy-images', ['site' => 'microchips-by', 'file' => $manifest, '--assets-root' => $root])->assertSuccessful();
            $this->assertDatabaseCount('product_media', 0);

            $this->artisan('media:import-verified-legacy-images', ['site' => 'microchips-by', 'file' => $manifest, '--assets-root' => $root, '--apply' => true])->assertSuccessful();
            $this->assertDatabaseHas('product_media', ['product_id' => $product->id, 'content_sha256' => $hash, 'verification_status' => 'verified', 'is_published' => true]);
            $media = $product->media()->sole();
            Storage::disk('public')->assertExists($media->storage_path);

            $this->artisan('media:import-verified-legacy-images', ['site' => 'microchips-by', 'file' => $manifest, '--assets-root' => $root, '--apply' => true])->assertSuccessful();
            $this->assertDatabaseCount('product_media', 1);
        } finally {
            @unlink($manifest);
            @unlink($file);
            @rmdir($root);
        }
    }

    public function test_unique_catalogue_identity_evidence_requires_an_explicit_reference(): void
    {
        Storage::fake('public');
        $site = Site::create(['key' => 'microchips-by', 'domain' => 'microchips-by.test', 'country_code' => 'BY', 'currency_code' => 'BYN', 'default_locale' => 'ru-BY', 'name' => 'RB', 'is_active' => true]);
        $product = Product::create(['external_id' => '1c-rbc7', 'name' => 'APC RBC7', 'slug' => 'apc-rbc7', 'manufacturer' => 'APC', 'mpn' => 'RBC7', 'status' => 'active']);
        SiteProduct::create(['site_id' => $site->id, 'product_id' => $product->id, 'slug' => 'apc-rbc7', 'is_published' => true, 'availability' => 'on_request']);
        $root = sys_get_temp_dir().DIRECTORY_SEPARATOR.'legacy-media-catalogue-'.uniqid();
        mkdir($root);
        $file = $root.DIRECTORY_SEPARATOR.'rbc7.png';
        file_put_contents($file, base64_decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAFgAI/ScL9pAAAAABJRU5ErkJggg=='));
        $hash = hash_file('sha256', $file);
        $manifest = $root.DIRECTORY_SEPARATOR.'manifest.json';
        $row = [
            'external_id' => '1c-rbc7', 'mpn' => 'RBC7', 'asset_file' => 'rbc7.png', 'sha256' => $hash,
            'archive_member' => '_shared/upload/iblock/test/rbc7.png', 'rights_basis' => 'company-owned legacy backup',
            'visual_verification_note' => 'APC replacement-cartridge form factor is consistent and no contradictory model is visible.',
            'identity_evidence_level' => 'unique_catalog_identity_plus_visual_consistency',
        ];
        file_put_contents($manifest, json_encode(['images' => [$row]], JSON_THROW_ON_ERROR));

        try {
            $this->artisan('media:import-verified-legacy-images', [
                'site' => 'microchips-by', 'file' => $manifest, '--assets-root' => $root, '--apply' => true,
            ])->assertFailed();
            $this->assertDatabaseCount('product_media', 0);

            $row['catalog_identity_reference'] = 'bitrix-backup://2026-06-23/element/123';
            file_put_contents($manifest, json_encode(['images' => [$row]], JSON_THROW_ON_ERROR));
            $this->artisan('media:import-verified-legacy-images', [
                'site' => 'microchips-by', 'file' => $manifest, '--assets-root' => $root, '--apply' => true,
            ])->assertSuccessful();

            $media = $product->media()->sole();
            $this->assertStringContainsString('unique_catalog_identity_plus_visual_consistency', $media->verification_note);
            $this->assertStringContainsString('bitrix-backup://2026-06-23/element/123', $media->verification_note);
        } finally {
            @unlink($manifest);
            @unlink($file);
            @rmdir($root);
        }
    }
}
