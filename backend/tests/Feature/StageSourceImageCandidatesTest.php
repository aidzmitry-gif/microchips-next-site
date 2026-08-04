<?php

namespace Tests\Feature;

use App\Models\Product;
use App\Models\ProductMedia;
use App\Models\Site;
use App\Models\SiteProduct;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class StageSourceImageCandidatesTest extends TestCase
{
    use RefreshDatabase;

    public function test_it_stages_a_non_public_pending_candidate_without_storage_or_rights_claim(): void
    {
        $site = Site::create(['key' => 'microchips-by', 'domain' => 'microchips-by.test', 'country_code' => 'BY', 'currency_code' => 'BYN', 'default_locale' => 'ru-BY', 'name' => 'RB', 'is_active' => true]);
        $product = Product::create(['external_id' => '1c-br2330', 'name' => 'Panasonic BR2330', 'slug' => 'panasonic-br2330', 'status' => 'active']);
        SiteProduct::create(['site_id' => $site->id, 'product_id' => $product->id, 'slug' => 'panasonic-br2330', 'availability' => 'on_request']);
        $file = tempnam(sys_get_temp_dir(), 'media-candidate-');
        file_put_contents($file, json_encode(['locale' => 'ru-BY', 'products' => [[
            'external_id' => '1c-br2330',
            'source_page_url' => 'https://manufacturer.example.test/br2330',
            'source_asset_url' => 'https://manufacturer.example.test/images/br2330.png',
            'source_kind' => 'official manufacturer product page',
            'verification_note' => 'Visual match pending rights verification.',
        ]]], JSON_THROW_ON_ERROR));

        try {
            $this->artisan('media:stage-source-image-candidates', ['site' => 'microchips-by', 'file' => $file])->assertSuccessful();
            $this->assertSame(0, ProductMedia::query()->count());
            $this->artisan('media:stage-source-image-candidates', ['site' => 'microchips-by', 'file' => $file, '--apply' => true])->assertSuccessful();
            $candidate = ProductMedia::query()->sole();
            $this->assertSame('pending', $candidate->verification_status);
            $this->assertFalse($candidate->is_published);
            $this->assertNull($candidate->storage_path);
            $this->assertNull($candidate->rights_basis);
        } finally {
            @unlink($file);
        }
    }
}
