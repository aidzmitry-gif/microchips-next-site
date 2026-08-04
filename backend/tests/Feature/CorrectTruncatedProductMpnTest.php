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

class CorrectTruncatedProductMpnTest extends TestCase
{
    use RefreshDatabase;

    public function test_it_dry_runs_then_corrects_only_the_truncated_mpn_with_audit_evidence(): void
    {
        Event::fake([SiteContentChanged::class]);
        [$site, $product, $siteProduct, $media, $file] = $this->fixture();
        try {
            $this->artisan('catalog:correct-truncated-mpn', ['site' => $site->key, 'file' => $file])
                ->expectsOutputToContain('"mode": "dry_run"')->assertSuccessful();
            $this->assertSame('S 12/6', $product->fresh()->mpn);
            $this->assertSame('dry_run_complete', ImportRun::query()->latest('id')->first()->status);

            $beforeSite = $siteProduct->only(['is_published', 'availability', 'price']);
            $this->artisan('catalog:correct-truncated-mpn', ['site' => $site->key, 'file' => $file, '--apply' => true])
                ->expectsOutputToContain('"corrected": 1')->assertSuccessful();
            $product->refresh();
            $this->assertSame('S12/6.6 S', $product->mpn);
            $this->assertSame('s1266s', $product->mpn_normalized);
            $this->assertSame($beforeSite, $siteProduct->fresh()->only(['is_published', 'availability', 'price']));
            $this->assertSame(ProductMedia::STATUS_LEGACY_EXACT_PREVIEW, $media->fresh()->verification_status);
            $this->assertSame(2, ImportRun::query()->count());
            $this->assertSame(2, StagedImportRecord::query()->count());
            Event::assertDispatched(SiteContentChanged::class);
        } finally {
            $this->cleanupEvidence($file);
        }
    }

    public function test_it_rejects_non_prefix_duplicate_and_unpinned_evidence(): void
    {
        [$site, $product, $siteProduct, $media, $file] = $this->fixture();
        $payload = json_decode((string) file_get_contents($file), true, 512, JSON_THROW_ON_ERROR);
        try {
            $payload['corrections'][0]['corrected_mpn'] = 'OTHER-1';
            file_put_contents($file, json_encode($payload, JSON_THROW_ON_ERROR));
            $this->artisan('catalog:correct-truncated-mpn', ['site' => $site->key, 'file' => $file, '--apply' => true])->assertFailed();
            $this->assertSame('S 12/6', $product->fresh()->mpn);

            $payload = $this->payload($product, $media);
            $payload['corrections'][0]['source_snapshot_sha256'] = str_repeat('a', 64);
            file_put_contents($file, json_encode($payload, JSON_THROW_ON_ERROR));
            $this->artisan('catalog:correct-truncated-mpn', ['site' => $site->key, 'file' => $file])->assertFailed();

            $payload = $this->payload($product, $media);
            $payload['corrections'][0]['source_evidence_text_sha256'] = str_repeat('a', 64);
            file_put_contents($file, json_encode($payload, JSON_THROW_ON_ERROR));
            $this->artisan('catalog:correct-truncated-mpn', ['site' => $site->key, 'file' => $file])->assertFailed();
            $this->assertSame('S 12/6', $product->fresh()->mpn);
        } finally {
            $this->cleanupEvidence($file);
        }
    }

    /** @return array{Site,Product,SiteProduct,ProductMedia,string} */
    private function fixture(): array
    {
        Storage::fake('public');
        $site = Site::create(['key' => 'microchips-by', 'domain' => 'microchips-by.test', 'country_code' => 'BY', 'currency_code' => 'BYN', 'default_locale' => 'ru-BY', 'name' => 'RB', 'is_active' => true]);
        $product = Product::create(['external_id' => 'bitrix:3117', 'name' => 'Sonnenschein Solar S 12/6.6 S GEL', 'slug' => 's-12-6-6-s', 'manufacturer' => 'Sonnenschein', 'mpn' => 'S 12/6', 'status' => 'draft']);
        $siteProduct = SiteProduct::create(['site_id' => $site->id, 'product_id' => $product->id, 'slug' => 's-12-6-6-s', 'is_published' => true, 'availability' => 'on_request', 'price' => null]);
        $path = 'legacy-staging/rb/bitrix-3117.png';
        $bytes = 'visible-S12-6.6-S-label';
        Storage::disk('public')->put($path, $bytes);
        $media = ProductMedia::create(['product_id' => $product->id, 'kind' => 'image', 'role' => 'primary', 'source_kind' => 'legacy_bitrix_exact_element_preview', 'source_page_url' => 'https://microchips.by/catalog/s-12-6-6-s/', 'rights_basis' => 'Company-owned Microchips legacy Bitrix upload backup.', 'storage_path' => $path, 'content_sha256' => hash('sha256', $bytes), 'verification_status' => ProductMedia::STATUS_LEGACY_EXACT_PREVIEW, 'verification_note' => 'Identity correction hold.', 'is_published' => true]);
        $file = tempnam(sys_get_temp_dir(), 'truncated-mpn-');
        $snapshot = tempnam(dirname($file), 'official-snapshot-');
        $extraction = tempnam(dirname($file), 'official-extraction-');
        file_put_contents($snapshot, '%PDF pinned official catalogue bytes');
        file_put_contents($extraction, 'Official catalogue: Sonnenschein Solar S12/6.6 S, 12 V, 6.60 Ah.');
        $this->sourceSnapshot = $snapshot;
        $this->sourceExtraction = $extraction;
        file_put_contents($file, json_encode($this->payload($product, $media), JSON_THROW_ON_ERROR));

        return [$site, $product, $siteProduct, $media, $file];
    }

    /** @return array<string,mixed> */
    private function payload(Product $product, ProductMedia $media): array
    {
        $text = 'Official catalogue: Sonnenschein Solar S12/6.6 S, 12 V, 6.60 Ah.';

        return ['locale' => 'ru-BY', 'corrections' => [[
            'external_id' => $product->external_id, 'current_name' => $product->name, 'manufacturer' => 'Sonnenschein',
            'current_mpn' => 'S 12/6', 'corrected_mpn' => 'S12/6.6 S',
            'source_url' => 'https://www.exidegroup.com/solar.pdf', 'source_kind' => 'official_manufacturer_catalogue',
            'source_snapshot_path' => basename($this->sourceSnapshot), 'source_snapshot_sha256' => hash_file('sha256', $this->sourceSnapshot),
            'source_extraction_path' => basename($this->sourceExtraction), 'source_extraction_sha256' => hash_file('sha256', $this->sourceExtraction),
            'source_evidence_text' => $text,
            'source_evidence_text_sha256' => hash('sha256', $text), 'media_id' => $media->id,
            'media_content_sha256' => $media->content_sha256, 'storage_path' => $media->storage_path,
            'rights_basis' => $media->rights_basis, 'observed_visible_mpn' => 'S12/6.6 S',
            'checked_at' => '2026-07-29', 'review_note' => 'Legacy MPN was truncated.',
        ]]];
    }

    private string $sourceSnapshot;

    private string $sourceExtraction;

    private function cleanupEvidence(string $manifest): void
    {
        @unlink($manifest);
        if (isset($this->sourceSnapshot)) {
            @unlink($this->sourceSnapshot);
        }
        if (isset($this->sourceExtraction)) {
            @unlink($this->sourceExtraction);
        }
    }
}
