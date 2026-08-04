<?php

namespace Tests\Feature;

use App\Models\Product;
use App\Models\ProductMedia;
use App\Models\Site;
use App\Models\SiteProduct;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Storage;
use PHPUnit\Framework\Attributes\DataProvider;
use Tests\TestCase;

class PromoteLegacyExactPreviewMediaTest extends TestCase
{
    use RefreshDatabase;

    public function test_it_dry_runs_then_promotes_only_the_pinned_legacy_preview_fields(): void
    {
        [$site, $product, $siteProduct, $media, $manifest] = $this->exactFixture();

        try {
            $beforeSiteProduct = $siteProduct->updated_at;
            $this->artisan('media:promote-legacy-exact-preview-media', [
                'site' => $site->key, 'file' => $manifest,
            ])->expectsOutputToContain('"mode": "dry_run"')->assertSuccessful();
            $this->assertSame(ProductMedia::STATUS_LEGACY_EXACT_PREVIEW, $media->fresh()->verification_status);
            $this->assertNull($media->fresh()->verified_at);
            $this->assertSame($beforeSiteProduct?->toDateTimeString(), $siteProduct->fresh()->updated_at?->toDateTimeString());

            $this->artisan('media:promote-legacy-exact-preview-media', [
                'site' => $site->key, 'file' => $manifest, '--apply' => true,
            ])->expectsOutputToContain('"promoted": 1')->assertSuccessful();
            $media->refresh();
            $this->assertSame(ProductMedia::STATUS_VERIFIED, $media->verification_status);
            $this->assertTrue($media->is_published);
            $this->assertNotNull($media->verified_at);
            $this->assertStringContainsString('visible_exact_mpn', $media->verification_note);
            $this->assertSame($this->hash, $media->content_sha256);
            $this->assertSame($this->path, $media->storage_path);
            $this->assertSame('Company-owned Microchips legacy Bitrix upload backup.', $media->rights_basis);
            $this->assertSame('CSB', $product->refresh()->manufacturer);
            $this->assertSame('GP1272', $product->mpn);
            $this->assertSame('on_request', $siteProduct->refresh()->availability);
            $this->assertSame('42.00', $siteProduct->price);
            $this->assertTrue($siteProduct->is_published);
        } finally {
            @unlink($manifest);
        }
    }

    public function test_it_promotes_visible_exact_model_core_without_inventing_an_mpn(): void
    {
        [$site, $product, $siteProduct, $media, $manifest] = $this->exactFixture('model_core');
        $product->update(['manufacturer' => null, 'mpn' => null]);

        try {
            $this->artisan('media:promote-legacy-exact-preview-media', [
                'site' => $site->key, 'file' => $manifest, '--apply' => true,
            ])->assertSuccessful();
            $this->assertSame(ProductMedia::STATUS_VERIFIED, $media->fresh()->verification_status);
            $this->assertNull($product->refresh()->manufacturer);
            $this->assertNull($product->mpn);
            $this->assertSame('on_request', $siteProduct->refresh()->availability);
        } finally {
            @unlink($manifest);
        }
    }

    public function test_it_rejects_duplicate_manifest_ids_and_a_non_preview_current_status(): void
    {
        [$site, $product, $siteProduct, $media, $manifest] = $this->exactFixture();
        $payload = json_decode((string) file_get_contents($manifest), true, 512, JSON_THROW_ON_ERROR);
        $payload['images'][] = $payload['images'][0];
        file_put_contents($manifest, json_encode($payload, JSON_THROW_ON_ERROR));

        try {
            $this->artisan('media:promote-legacy-exact-preview-media', [
                'site' => $site->key, 'file' => $manifest,
            ])->assertFailed();
            $this->assertSame(ProductMedia::STATUS_LEGACY_EXACT_PREVIEW, $media->fresh()->verification_status);

            file_put_contents($manifest, json_encode(['locale' => 'ru-BY', 'images' => [$payload['images'][0]]], JSON_THROW_ON_ERROR));
            $media->update(['verification_status' => 'pending']);
            $this->artisan('media:promote-legacy-exact-preview-media', [
                'site' => $site->key, 'file' => $manifest,
            ])->assertFailed();
            $this->assertSame('pending', $media->fresh()->verification_status);
        } finally {
            @unlink($manifest);
        }
    }

    #[DataProvider('mismatchedManifest')]
    public function test_it_fails_closed_on_manifest_or_current_media_mismatches(string $field, mixed $value): void
    {
        [$site, $product, $siteProduct, $media, $manifest] = $this->exactFixture();
        $payload = json_decode((string) file_get_contents($manifest), true, 512, JSON_THROW_ON_ERROR);
        $payload['images'][0][$field] = $value;
        file_put_contents($manifest, json_encode($payload, JSON_THROW_ON_ERROR));

        try {
            $this->artisan('media:promote-legacy-exact-preview-media', [
                'site' => $site->key, 'file' => $manifest, '--apply' => true,
            ])->assertFailed();
            $this->assertSame(ProductMedia::STATUS_LEGACY_EXACT_PREVIEW, $media->fresh()->verification_status);
            $this->assertNull($media->fresh()->verified_at);
        } finally {
            @unlink($manifest);
        }
    }

    /** @return iterable<string, array{string, mixed}> */
    public static function mismatchedManifest(): iterable
    {
        yield 'wrong media id' => ['media_id', 99999];
        yield 'wrong hash' => ['content_sha256', str_repeat('a', 64)];
        yield 'wrong storage path' => ['storage_path', 'legacy-staging/rb/other.png'];
        yield 'wrong rights' => ['rights_basis', 'third-party rights'];
        yield 'wrong exact MPN' => ['mpn', 'GP1272X'];
        yield 'wrong evidence level' => ['identity_evidence_level', 'visible_exact_model_core'];
    }

    private string $path;

    private string $hash;

    /** @return array{Site, Product, SiteProduct, ProductMedia, string} */
    private function exactFixture(string $scope = 'exact'): array
    {
        Storage::fake('public');
        $site = Site::create(['key' => 'microchips-by', 'domain' => 'microchips-by.test', 'country_code' => 'BY', 'currency_code' => 'BYN', 'default_locale' => 'ru-BY', 'name' => 'RB', 'is_active' => true]);
        $product = Product::create(['external_id' => '1c:csb-gp1272', 'name' => 'CSB GP1272 F2', 'slug' => 'csb-gp1272', 'manufacturer' => 'CSB', 'mpn' => 'GP1272', 'status' => 'active']);
        $siteProduct = SiteProduct::create(['site_id' => $site->id, 'product_id' => $product->id, 'slug' => 'csb-gp1272', 'is_published' => true, 'availability' => 'on_request', 'price' => '42.00']);
        $this->path = 'legacy-staging/rb/bitrix-900-1.png';
        $bytes = base64_decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAFgAI/ScL9pAAAAABJRU5ErkJggg==');
        Storage::disk('public')->put($this->path, $bytes);
        $this->hash = hash('sha256', $bytes);
        $media = ProductMedia::create([
            'product_id' => $product->id, 'kind' => 'image', 'role' => 'primary',
            'source_page_url' => 'bitrix-backup://element/900', 'source_asset_url' => 'bitrix-backup://file/1',
            'source_kind' => 'legacy_bitrix_exact_element_preview', 'rights_basis' => 'Company-owned Microchips legacy Bitrix upload backup.',
            'storage_path' => $this->path, 'content_sha256' => $this->hash,
            'verification_status' => ProductMedia::STATUS_LEGACY_EXACT_PREVIEW,
            'verification_note' => 'Exact legacy preview; visual review pending.', 'is_published' => true,
        ]);
        $row = [
            'external_id' => $product->external_id, 'media_id' => $media->id, 'content_sha256' => $this->hash,
            'storage_path' => $this->path, 'rights_basis' => $media->rights_basis, 'identity_scope' => $scope,
            'identity_evidence_level' => $scope === 'exact' ? 'visible_exact_mpn' : 'visible_exact_model_core',
            'visual_verification_note' => 'Visible label and form factor match the reviewed identity.', 'reviewed_at' => '2026-07-29',
        ];
        if ($scope === 'exact') {
            $row['mpn'] = 'GP1272';
        } else {
            $row['model_core'] = 'GP1272';
            $row['manufacturer'] = 'CSB';
        }
        $manifest = tempnam(sys_get_temp_dir(), 'legacy-preview-promotion-');
        file_put_contents($manifest, json_encode(['locale' => 'ru-BY', 'images' => [$row]], JSON_THROW_ON_ERROR));

        return [$site, $product, $siteProduct, $media, $manifest];
    }
}
