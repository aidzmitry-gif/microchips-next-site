<?php

namespace Tests\Feature;

use App\Events\SiteContentChanged;
use App\Models\ImportRun;
use App\Models\Product;
use App\Models\ProductMedia;
use App\Models\Site;
use App\Models\SiteProduct;
use App\Models\StagedImportRecord;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Event;
use Illuminate\Support\Facades\Storage;
use Tests\TestCase;

class QuarantineIdentityMismatchMediaTest extends TestCase
{
    use RefreshDatabase;

    public function test_it_dry_runs_with_an_auditable_record_without_mutating_media_or_catalogue(): void
    {
        [$site, $product, $siteProduct, $media, $file] = $this->fixture();
        try {
            $before = $siteProduct->updated_at?->toDateTimeString();
            $this->artisan('media:quarantine-identity-mismatches', ['site' => $site->key, 'file' => $file])
                ->expectsOutputToContain('"mode": "dry_run"')->assertSuccessful();
            $this->assertSame(ProductMedia::STATUS_VERIFIED, $media->fresh()->verification_status);
            $this->assertTrue($media->fresh()->is_published);
            $this->assertNotNull($media->fresh()->verified_at);
            $this->assertSame($before, $siteProduct->fresh()->updated_at?->toDateTimeString());
            $this->assertSame('completed', $product->fresh()->status);
            $this->assertSame('dry_run_complete', ImportRun::query()->sole()->status);
            $this->assertSame('dry_run_validated', StagedImportRecord::query()->sole()->status);
        } finally {
            $this->cleanupEvidence($file);
        }
    }

    public function test_it_quarantines_wrong_product_media_and_retains_truncated_identity_as_preview_only(): void
    {
        Event::fake([SiteContentChanged::class]);
        [$site, $product, $siteProduct, $media, $file] = $this->fixture();
        [$otherProduct, $holdMedia] = $this->secondFixture($site);
        $payload = json_decode((string) file_get_contents($file), true, 512, JSON_THROW_ON_ERROR);
        $payload['images'][] = $this->row($otherProduct, $holdMedia, 'hold_truncated_identity_preview');
        file_put_contents($file, json_encode($payload, JSON_THROW_ON_ERROR));
        try {
            $beforeAvailability = $siteProduct->availability;
            $beforePrice = $siteProduct->price;
            $beforeUpdated = $siteProduct->updated_at?->toDateTimeString();
            $this->artisan('media:quarantine-identity-mismatches', ['site' => $site->key, 'file' => $file, '--apply' => true])
                ->expectsOutputToContain('"quarantined": 1')->assertSuccessful();
            $media->refresh();
            $holdMedia->refresh();
            $this->assertSame(ProductMedia::STATUS_NEEDS_REVIEW, $media->verification_status);
            $this->assertFalse($media->is_published);
            $this->assertNull($media->verified_at);
            $this->assertSame(ProductMedia::STATUS_LEGACY_EXACT_PREVIEW, $holdMedia->verification_status);
            $this->assertTrue($holdMedia->is_published);
            $this->assertNull($holdMedia->verified_at);
            $this->assertStringContainsString('observed visible MPN GP1272X', $media->verification_note);
            $this->assertSame($beforeAvailability, $siteProduct->fresh()->availability);
            $this->assertSame($beforePrice, $siteProduct->fresh()->price);
            $this->assertSame($beforeUpdated, $siteProduct->fresh()->updated_at?->toDateTimeString());
            $this->assertSame('completed', $product->fresh()->status);
            $this->assertSame('completed', $otherProduct->fresh()->status);
            $run = ImportRun::query()->sole();
            $this->assertSame('completed', $run->status);
            $this->assertSame(1, $run->summary['quarantined']);
            $this->assertSame(1, $run->summary['truncated_identity_holds']);
            $this->assertSame(2, StagedImportRecord::query()->where('status', 'completed')->count());
            Event::assertDispatched(SiteContentChanged::class);
        } finally {
            $this->cleanupEvidence($file);
        }
    }

    public function test_it_can_quarantine_a_published_legacy_preview_that_visual_review_proved_wrong(): void
    {
        [$site, $product, $siteProduct, $media, $file] = $this->fixture();
        $media->update(['verification_status' => ProductMedia::STATUS_LEGACY_EXACT_PREVIEW, 'verified_at' => null]);
        $payload = json_decode((string) file_get_contents($file), true, 512, JSON_THROW_ON_ERROR);
        $payload['images'][0]['current_verification_status'] = ProductMedia::STATUS_LEGACY_EXACT_PREVIEW;
        file_put_contents($file, json_encode($payload, JSON_THROW_ON_ERROR));
        try {
            $this->artisan('media:quarantine-identity-mismatches', ['site' => $site->key, 'file' => $file, '--apply' => true])->assertSuccessful();
            $this->assertSame(ProductMedia::STATUS_NEEDS_REVIEW, $media->fresh()->verification_status);
            $this->assertFalse($media->fresh()->is_published);
            $this->assertTrue($siteProduct->fresh()->is_published);
        } finally {
            $this->cleanupEvidence($file);
        }
    }

    public function test_it_fails_closed_on_duplicate_rows_equal_visible_mpn_or_current_state_drift(): void
    {
        [$site, $product, $siteProduct, $media, $file] = $this->fixture();
        $payload = json_decode((string) file_get_contents($file), true, 512, JSON_THROW_ON_ERROR);
        $payload['images'][] = $payload['images'][0];
        file_put_contents($file, json_encode($payload, JSON_THROW_ON_ERROR));
        try {
            $this->artisan('media:quarantine-identity-mismatches', ['site' => $site->key, 'file' => $file])->assertFailed();
            $this->assertSame(ProductMedia::STATUS_VERIFIED, $media->fresh()->verification_status);
            $payload['images'] = [$payload['images'][0]];
            $payload['images'][0]['observed_visible_mpn'] = 'GP1272';
            file_put_contents($file, json_encode($payload, JSON_THROW_ON_ERROR));
            $this->artisan('media:quarantine-identity-mismatches', ['site' => $site->key, 'file' => $file])->assertFailed();
            $payload['images'][0]['observed_visible_mpn'] = 'MM5512';
            $payload['images'][0]['disposition'] = 'hold_truncated_identity_preview';
            file_put_contents($file, json_encode($payload, JSON_THROW_ON_ERROR));
            $this->artisan('media:quarantine-identity-mismatches', ['site' => $site->key, 'file' => $file])->assertFailed();
            $payload['images'][0]['observed_visible_mpn'] = 'GP1272X';
            $payload['images'][0]['disposition'] = 'quarantine_wrong_product_media';
            $payload['images'][0]['review_evidence_sha256'] = str_repeat('a', 64);
            file_put_contents($file, json_encode($payload, JSON_THROW_ON_ERROR));
            $this->artisan('media:quarantine-identity-mismatches', ['site' => $site->key, 'file' => $file])->assertFailed();
            $payload['images'][0]['review_evidence_sha256'] = hash_file('sha256', $this->reviewEvidencePath);
            $media->update(['verification_status' => ProductMedia::STATUS_LEGACY_EXACT_PREVIEW]);
            $payload['images'][0]['observed_visible_mpn'] = 'GP1272X';
            $payload['images'][0]['disposition'] = 'quarantine_wrong_product_media';
            file_put_contents($file, json_encode($payload, JSON_THROW_ON_ERROR));
            $this->artisan('media:quarantine-identity-mismatches', ['site' => $site->key, 'file' => $file])->assertFailed();
            $this->assertSame(ProductMedia::STATUS_LEGACY_EXACT_PREVIEW, $media->fresh()->verification_status);
        } finally {
            $this->cleanupEvidence($file);
        }
    }

    /** @return array{Site,Product,SiteProduct,ProductMedia,string} */
    private function fixture(): array
    {
        Storage::fake('public');
        $site = Site::create(['key' => 'microchips-by', 'domain' => 'microchips-by.test', 'country_code' => 'BY', 'currency_code' => 'BYN', 'default_locale' => 'ru-BY', 'name' => 'RB', 'is_active' => true]);
        $product = Product::create(['external_id' => 'bitrix:wrong-preview', 'name' => 'CSB GP1272 F2', 'slug' => 'csb-gp1272', 'manufacturer' => 'CSB', 'mpn' => 'GP1272', 'status' => 'completed']);
        $siteProduct = SiteProduct::create(['site_id' => $site->id, 'product_id' => $product->id, 'slug' => 'csb-gp1272', 'is_published' => true, 'availability' => 'on_request', 'price' => '42.00']);
        $media = $this->media($product, 'legacy-staging/rb/wrong.png');
        $file = tempnam(sys_get_temp_dir(), 'media-mismatch-');
        $this->reviewEvidencePath = tempnam(dirname($file), 'visual-review-ledger-');
        file_put_contents($this->reviewEvidencePath, "external_id,expected,observed\nbitrix:wrong-preview,GP1272,GP1272X\n");
        file_put_contents($file, json_encode(['locale' => 'ru-BY', 'images' => [$this->row($product, $media, 'quarantine_wrong_product_media')]], JSON_THROW_ON_ERROR));

        return [$site, $product, $siteProduct, $media, $file];
    }

    /** @return array{Product,ProductMedia} */
    private function secondFixture(Site $site): array
    {
        $product = Product::create(['external_id' => 'bitrix:truncated-preview', 'name' => 'CSB GP1272 F2 spare', 'slug' => 'csb-gp1272-spare', 'manufacturer' => 'CSB', 'mpn' => 'GP127', 'status' => 'completed']);
        SiteProduct::create(['site_id' => $site->id, 'product_id' => $product->id, 'slug' => 'csb-gp1272-spare', 'is_published' => true, 'availability' => 'on_request', 'price' => '43.00']);

        return [$product, $this->media($product, 'legacy-staging/rb/hold.png')];
    }

    private function media(Product $product, string $path): ProductMedia
    {
        $bytes = 'identity-mismatch-'.$path;
        Storage::disk('public')->put($path, $bytes);

        return ProductMedia::create(['product_id' => $product->id, 'kind' => 'image', 'role' => 'primary', 'source_kind' => 'legacy_bitrix_exact_element_preview', 'source_page_url' => 'https://microchips.by/catalog/'.basename($path, '.png').'/', 'rights_basis' => 'Company-owned Microchips legacy Bitrix upload backup.', 'storage_path' => $path, 'content_sha256' => hash('sha256', $bytes), 'verification_status' => ProductMedia::STATUS_VERIFIED, 'verification_note' => 'Old verified note', 'verified_at' => now(), 'is_published' => true]);
    }

    /** @return array<string,mixed> */
    private function row(Product $product, ProductMedia $media, string $disposition): array
    {
        return ['external_id' => $product->external_id, 'media_id' => $media->id, 'content_sha256' => $media->content_sha256, 'storage_path' => $media->storage_path, 'rights_basis' => $media->rights_basis, 'current_verification_status' => ProductMedia::STATUS_VERIFIED, 'expected_catalogue_mpn' => $product->mpn, 'observed_visible_mpn' => $product->mpn === 'GP127' ? 'GP1272' : 'GP1272X', 'disposition' => $disposition, 'reason' => 'Visible label identifies a different model.', 'reviewed_at' => '2026-07-29', 'reviewer' => 'test-visual-reviewer', 'review_evidence_path' => basename($this->reviewEvidencePath), 'review_evidence_sha256' => hash_file('sha256', $this->reviewEvidencePath)];
    }

    private string $reviewEvidencePath;

    private function cleanupEvidence(string $manifest): void
    {
        @unlink($manifest);
        if (isset($this->reviewEvidencePath)) {
            @unlink($this->reviewEvidencePath);
        }
    }
}
