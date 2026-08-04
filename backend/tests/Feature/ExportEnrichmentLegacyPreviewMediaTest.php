<?php

namespace Tests\Feature;

use App\Models\Product;
use App\Models\ProductMedia;
use App\Models\Site;
use App\Models\SiteProduct;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class ExportEnrichmentLegacyPreviewMediaTest extends TestCase
{
    use RefreshDatabase;

    public function test_it_exports_only_unreviewed_company_owned_legacy_preview_media_for_published_queue_products(): void
    {
        $site = $this->site();
        $eligible = $this->product($site, 'bitrix:eligible', 'Panasonic CR2032 battery', 'CR2032', 'Panasonic', true);
        $reviewed = $this->product($site, 'bitrix:reviewed', 'Panasonic CR2016 battery', 'CR2016', 'Panasonic', true);
        $unpublished = $this->product($site, 'bitrix:unpublished', 'Panasonic CR2025 battery', 'CR2025', 'Panasonic', false);
        $exported = $this->previewMedia($eligible, 'legacy-staging/rb/eligible.png', str_repeat('a', 64));
        $reviewedMedia = $this->previewMedia($reviewed, 'legacy-staging/rb/reviewed.png', str_repeat('b', 64));
        $this->previewMedia($unpublished, 'legacy-staging/rb/unpublished.png', str_repeat('c', 64));
        $this->previewMedia($eligible, 'legacy-staging/rb/not-owned.png', str_repeat('d', 64), 'third-party rights');
        $this->previewMedia($eligible, 'legacy-staging/rb/verified.png', str_repeat('e', 64), 'Company-owned Microchips legacy Bitrix upload backup.', ProductMedia::STATUS_VERIFIED);

        [$queue, $ledger, $output] = $this->files(
            "product_external_id,mpn,manufacturer\nbitrix:eligible,CR2032,Panasonic\nbitrix:reviewed,CR2016,Panasonic\nbitrix:unpublished,CR2025,Panasonic\n",
            "external_id,media_id\nbitrix:reviewed,{$reviewedMedia->id}\n",
        );
        try {
            $this->artisan('media:export-enrichment-legacy-preview-candidates', [
                'site' => $site->key, 'queue' => $queue, 'output' => $output, '--review-ledger' => [$ledger],
            ])->expectsOutputToContain('"mode": "read_only_export"')
                ->expectsOutputToContain('"exported_media": 1')
                ->expectsOutputToContain('"excluded_reviewed_media": 1')
                ->assertSuccessful();

            $rows = $this->csv($output);
            $this->assertCount(1, $rows);
            $this->assertSame([
                'external_id' => 'bitrix:eligible', 'media_id' => (string) $exported->id,
                'storage_path' => 'legacy-staging/rb/eligible.png', 'content_sha256' => str_repeat('a', 64),
                'rights_basis' => 'Company-owned Microchips legacy Bitrix upload backup.',
                'identity_scope' => 'exact', 'mpn' => 'CR2032', 'model_core' => '', 'manufacturer' => '',
            ], $rows[0]);
            $this->assertSame(ProductMedia::STATUS_LEGACY_EXACT_PREVIEW, $exported->fresh()->verification_status);
            $this->assertSame(ProductMedia::STATUS_LEGACY_EXACT_PREVIEW, $reviewedMedia->fresh()->verification_status);
        } finally {
            @unlink($queue);
            @unlink($ledger);
            @unlink($output);
        }
    }

    public function test_it_can_export_an_explicit_queue_model_core_when_the_product_has_no_mpn(): void
    {
        $site = $this->site();
        $product = $this->product($site, 'bitrix:model-core', 'Panasonic BR-2/3A primary cell', null, 'Panasonic', true);
        $media = $this->previewMedia($product, 'legacy-staging/rb/model-core.png', str_repeat('f', 64));
        [$queue, $ledger, $output] = $this->files(
            "product_external_id,mpn,model_core,manufacturer\nbitrix:model-core,,BR-2/3A,Panasonic\n",
            "external_id,media_id\n",
        );
        try {
            $this->artisan('media:export-enrichment-legacy-preview-candidates', [
                'site' => $site->key, 'queue' => $queue, 'output' => $output, '--review-ledger' => [$ledger],
            ])->assertSuccessful();
            $row = $this->csv($output)[0];
            $this->assertSame((string) $media->id, $row['media_id']);
            $this->assertSame('model_core', $row['identity_scope']);
            $this->assertSame('', $row['mpn']);
            $this->assertSame('BR-2/3A', $row['model_core']);
            $this->assertSame('Panasonic', $row['manufacturer']);
        } finally {
            @unlink($queue);
            @unlink($ledger);
            @unlink($output);
        }
    }

    public function test_it_fails_closed_for_duplicate_queue_external_ids_without_writing_an_export(): void
    {
        $site = $this->site();
        [$queue, $ledger, $output] = $this->files(
            "product_external_id,mpn\nbitrix:duplicate,CR2032\nbitrix:duplicate,CR2032\n",
            "external_id,media_id\n",
        );
        @unlink($output);
        try {
            $this->artisan('media:export-enrichment-legacy-preview-candidates', [
                'site' => $site->key, 'queue' => $queue, 'output' => $output, '--review-ledger' => [$ledger],
            ])->assertFailed();
            $this->assertFileDoesNotExist($output);
        } finally {
            @unlink($queue);
            @unlink($ledger);
            @unlink($output);
        }
    }

    private function site(): Site
    {
        return Site::create(['key' => 'microchips-by', 'domain' => 'microchips-by.test', 'country_code' => 'BY', 'currency_code' => 'BYN', 'default_locale' => 'ru-BY', 'name' => 'RB']);
    }

    private function product(Site $site, string $externalId, string $name, ?string $mpn, ?string $manufacturer, bool $published): Product
    {
        $product = Product::create(['external_id' => $externalId, 'slug' => str_replace(':', '-', $externalId), 'name' => $name, 'mpn' => $mpn, 'manufacturer' => $manufacturer, 'status' => 'active']);
        SiteProduct::create(['site_id' => $site->id, 'product_id' => $product->id, 'slug' => $product->slug, 'is_published' => $published, 'availability' => 'on_request']);

        return $product;
    }

    private function previewMedia(Product $product, string $path, string $hash, string $rights = 'Company-owned Microchips legacy Bitrix upload backup.', string $status = ProductMedia::STATUS_LEGACY_EXACT_PREVIEW): ProductMedia
    {
        return ProductMedia::create([
            'product_id' => $product->id, 'kind' => 'image', 'role' => 'primary',
            'source_page_url' => 'bitrix-backup://element/'.$product->id, 'source_asset_url' => 'bitrix-backup://file/'.$product->id,
            'source_kind' => 'legacy_bitrix_exact_element_preview', 'rights_basis' => $rights,
            'storage_path' => $path, 'content_sha256' => $hash, 'verification_status' => $status, 'is_published' => true,
        ]);
    }

    /** @return array{string, string, string} */
    private function files(string $queueContents, string $ledgerContents): array
    {
        $queue = tempnam(sys_get_temp_dir(), 'enrichment-queue-');
        $ledger = tempnam(sys_get_temp_dir(), 'reviewed-media-ledger-');
        $output = tempnam(sys_get_temp_dir(), 'legacy-preview-export-');
        file_put_contents($queue, $queueContents);
        file_put_contents($ledger, $ledgerContents);

        return [$queue, $ledger, $output];
    }

    /** @return list<array<string, string>> */
    private function csv(string $path): array
    {
        $handle = fopen($path, 'rb');
        $header = fgetcsv($handle, 0, ',', '"', '');
        $header[0] = ltrim((string) $header[0], "\xEF\xBB\xBF");
        $rows = [];
        while (($values = fgetcsv($handle, 0, ',', '"', '')) !== false) {
            $rows[] = array_combine($header, $values);
        }
        fclose($handle);

        return $rows;
    }
}
