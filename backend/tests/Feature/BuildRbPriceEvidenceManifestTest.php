<?php

namespace Tests\Feature;

use App\Models\CatalogIdentityCandidate;
use App\Models\ImportRun;
use App\Models\OneCNomenclatureItem;
use App\Models\Product;
use App\Models\Site;
use App\Models\SiteProduct;
use App\Models\SiteProductPriceEvidence;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class BuildRbPriceEvidenceManifestTest extends TestCase
{
    use RefreshDatabase;

    public function test_it_builds_a_one_c_x2_row_from_only_the_required_commercial_columns(): void
    {
        $site = Site::create([
            'key' => 'microchips-by', 'domain' => 'microchips-by.test', 'country_code' => 'BY',
            'currency_code' => 'BYN', 'default_locale' => 'ru-BY', 'name' => 'RB', 'is_active' => true,
        ]);
        $product = Product::create([
            'external_id' => '1C-PRICE-1', 'slug' => 'price-1', 'name' => 'Price product', 'status' => 'draft',
        ]);
        SiteProduct::create([
            'site_id' => $site->id, 'product_id' => $product->id, 'slug' => 'price-1',
            'availability' => 'on_request', 'price' => null,
        ]);
        $run = ImportRun::create([
            'source' => '1c_csv', 'status' => 'inventory_ready', 'started_at' => now()->subMinutes(2),
            'finished_at' => now()->subMinute(),
        ]);
        OneCNomenclatureItem::create([
            'import_run_id' => $run->id,
            'source_key' => '1c_nomenclature',
            'external_id' => '1C-PRICE-1',
            'is_group' => false,
            'name' => 'Price product',
            'price' => '10.1250',
            'currency' => 'BYN',
            'price_type' => 'retail',
            'classification_status' => 'in_scope',
            'source_payload' => ['large_payload_is_not_required' => str_repeat('x', 1000)],
            'source_checksum' => hash('sha256', '1C-PRICE-1'),
        ]);

        $legacy = tempnam(sys_get_temp_dir(), 'legacy-price-manifest-');
        $output = tempnam(sys_get_temp_dir(), 'built-price-evidence-');
        file_put_contents($legacy, implode(',', [
            'legacy_element_id', 'price_byn', 'price_status', 'price_source', 'legacy_url_candidate',
        ]).PHP_EOL);

        try {
            $this->artisan('catalog:build-rb-price-evidence', [
                'bitrix_manifest' => $legacy,
                'output' => $output,
                '--site' => 'microchips-by',
            ])->expectsOutputToContain('one_c_x2=1')->assertSuccessful();

            $handle = fopen($output, 'rb');
            $headers = fgetcsv($handle, separator: ';', escape: '');
            $values = fgetcsv($handle, separator: ';', escape: '');
            fclose($handle);
            $row = array_combine($headers, $values);

            $this->assertSame('1C-PRICE-1', $row['product_external_id']);
            $this->assertSame('one_c_x2', $row['source']);
            $this->assertSame(10.125, (float) $row['source_price']);
            $this->assertSame('2', $row['multiplier']);
            $this->assertSame('retail', $row['price_type']);
        } finally {
            @unlink($legacy);
            @unlink($output);
        }
    }

    public function test_it_builds_a_direct_bitrix_row_only_with_the_exact_manifest_pin(): void
    {
        [$site, $siteProduct] = $this->directBitrixProduct(published: true);
        $legacy = $this->legacyManifest();
        $output = tempnam(sys_get_temp_dir(), 'built-direct-bitrix-price-');

        try {
            $this->artisan('catalog:build-rb-price-evidence', [
                'bitrix_manifest' => $legacy,
                'output' => $output,
                '--site' => $site->key,
                '--bitrix-manifest-sha256' => hash_file('sha256', $legacy),
            ])->expectsOutputToContain('direct_bitrix=1')->assertSuccessful();

            $rows = $this->readEvidenceRows($output);
            $this->assertCount(1, $rows);
            $this->assertSame('bitrix:3219', $rows[0]['product_external_id']);
            $this->assertSame('legacy_site', $rows[0]['source']);
            $this->assertSame('439.5', $rows[0]['source_price']);
            $this->assertSame('BYN', $rows[0]['currency']);
            $this->assertSame('2026-06-23T00:00:00+03:00', $rows[0]['observed_at']);
            $this->assertSame('bitrix-backup://2026-06-23/element/3219', $rows[0]['source_reference']);
            $this->assertSame('3219', $rows[0]['source_external_id']);
            $this->assertSame('1', $rows[0]['multiplier']);
            $this->assertSame('legacy_public_price_direct_bitrix', $rows[0]['price_type']);
            $this->assertNull($siteProduct->fresh()->price);
        } finally {
            @unlink($legacy);
            @unlink($output);
        }
    }

    public function test_it_rejects_a_mismatched_direct_bitrix_manifest_pin(): void
    {
        [$site] = $this->directBitrixProduct(published: true);
        $legacy = $this->legacyManifest();
        $output = tempnam(sys_get_temp_dir(), 'built-direct-bitrix-price-');

        try {
            $this->artisan('catalog:build-rb-price-evidence', [
                'bitrix_manifest' => $legacy,
                'output' => $output,
                '--site' => $site->key,
                '--bitrix-manifest-sha256' => str_repeat('0', 64),
            ])->expectsOutputToContain('SHA-256 pin mismatch')->assertFailed();
        } finally {
            @unlink($legacy);
            @unlink($output);
        }
    }

    public function test_it_does_not_enable_direct_bitrix_without_a_pin(): void
    {
        [$site] = $this->directBitrixProduct(published: true);
        $legacy = $this->legacyManifest();
        $output = tempnam(sys_get_temp_dir(), 'built-direct-bitrix-price-');

        try {
            $this->artisan('catalog:build-rb-price-evidence', [
                'bitrix_manifest' => $legacy,
                'output' => $output,
                '--site' => $site->key,
            ])->expectsOutputToContain('direct_bitrix=0')->assertSuccessful();

            $this->assertSame([], $this->readEvidenceRows($output));
        } finally {
            @unlink($legacy);
            @unlink($output);
        }
    }

    public function test_direct_bitrix_is_blocked_by_a_candidate_of_any_status(): void
    {
        [$site] = $this->directBitrixProduct(published: true);
        $this->identityCandidate('3219', 'pending');

        $this->assertDirectBitrixIsBlocked($site, $this->legacyManifest());
    }

    public function test_direct_bitrix_is_blocked_for_an_unpublished_site_product(): void
    {
        [$site] = $this->directBitrixProduct(published: false);

        $this->assertDirectBitrixIsBlocked($site, $this->legacyManifest());
    }

    public function test_direct_bitrix_is_blocked_by_current_price_evidence(): void
    {
        [$site, $siteProduct] = $this->directBitrixProduct(published: true);
        SiteProductPriceEvidence::create([
            'site_id' => $site->id,
            'site_product_id' => $siteProduct->id,
            'source' => 'legacy_site',
            'source_price' => '400.0000',
            'multiplier' => '1.0000',
            'calculated_price' => '400.00',
            'currency' => 'BYN',
            'price_type' => 'legacy_public_price',
            'source_external_id' => '3219',
            'source_reference' => 'bitrix-backup://2026-06-23/element/3219',
            'observed_at' => now()->subDay(),
            'evidence_key' => hash('sha256', 'existing-3219-price'),
            'is_current' => true,
        ]);

        $this->assertDirectBitrixIsBlocked($site, $this->legacyManifest());
    }

    public function test_direct_bitrix_is_blocked_for_a_wrong_legacy_source(): void
    {
        [$site] = $this->directBitrixProduct(published: true);

        $this->assertDirectBitrixIsBlocked($site, $this->legacyManifest('bitrix_backup_2026-06-22'));
    }

    /** @return array{Site, SiteProduct} */
    private function directBitrixProduct(bool $published): array
    {
        $site = Site::create([
            'key' => 'microchips-by', 'domain' => 'microchips-by.test', 'country_code' => 'BY',
            'currency_code' => 'BYN', 'default_locale' => 'ru-BY', 'name' => 'RB', 'is_active' => true,
        ]);
        $product = Product::create([
            'external_id' => 'bitrix:3219', 'slug' => 'bitrix-3219', 'name' => 'Legacy product', 'status' => 'active',
        ]);
        $siteProduct = SiteProduct::create([
            'site_id' => $site->id, 'product_id' => $product->id, 'slug' => 'bitrix-3219',
            'is_published' => $published, 'availability' => 'on_request', 'price' => null,
        ]);

        return [$site, $siteProduct];
    }

    private function identityCandidate(string $legacyId, string $status): void
    {
        $inventoryRun = ImportRun::create(['source' => '1c_csv', 'status' => 'inventory_ready']);
        $item = OneCNomenclatureItem::create([
            'import_run_id' => $inventoryRun->id,
            'source_key' => '1c_nomenclature',
            'external_id' => '1C-CANDIDATE-'.$legacyId,
            'is_group' => false,
            'name' => 'Candidate product',
            'classification_status' => 'needs_identity_review',
            'source_payload' => ['legacy_id' => $legacyId],
            'source_checksum' => hash('sha256', 'candidate-item-'.$legacyId),
        ]);
        $candidateRun = ImportRun::create(['source' => 'identity_candidates', 'status' => 'review_queue_ready']);
        CatalogIdentityCandidate::create([
            'import_run_id' => $candidateRun->id,
            'one_c_nomenclature_item_id' => $item->id,
            'legacy_source' => 'bitrix',
            'legacy_id' => $legacyId,
            'legacy_name' => 'Candidate legacy product',
            'review_priority' => 1,
            'review_batch' => 'test',
            'confidence' => '0.9000',
            'match_method' => 'test',
            'review_status' => $status,
            'source_payload' => ['legacy_id' => $legacyId],
            'source_checksum' => hash('sha256', 'candidate-'.$legacyId),
        ]);
    }

    private function legacyManifest(string $source = 'bitrix_backup_2026-06-23'): string
    {
        $path = tempnam(sys_get_temp_dir(), 'legacy-price-manifest-');
        $handle = fopen($path, 'wb');
        $this->assertNotFalse($handle);
        fputcsv($handle, [
            'legacy_element_id', 'price_byn', 'price_status', 'price_source', 'legacy_url_candidate',
        ], ',', '"', '');
        fputcsv($handle, [
            '3219', '439.5', 'ok', $source, '/catalog/akkumulyatory/dlya_ibp/agm/3219/',
        ], ',', '"', '');
        fclose($handle);

        return $path;
    }

    private function assertDirectBitrixIsBlocked(Site $site, string $legacy): void
    {
        $output = tempnam(sys_get_temp_dir(), 'built-direct-bitrix-price-');
        try {
            $this->artisan('catalog:build-rb-price-evidence', [
                'bitrix_manifest' => $legacy,
                'output' => $output,
                '--site' => $site->key,
                '--bitrix-manifest-sha256' => hash_file('sha256', $legacy),
            ])->expectsOutputToContain('direct_bitrix=0')->assertSuccessful();

            $this->assertSame([], $this->readEvidenceRows($output));
        } finally {
            @unlink($legacy);
            @unlink($output);
        }
    }

    /** @return list<array<string, string>> */
    private function readEvidenceRows(string $path): array
    {
        $handle = fopen($path, 'rb');
        $this->assertNotFalse($handle);
        $headers = fgetcsv($handle, separator: ';', escape: '');
        $this->assertIsArray($headers);
        $rows = [];
        while (($values = fgetcsv($handle, separator: ';', escape: '')) !== false) {
            $rows[] = array_combine($headers, $values);
        }
        fclose($handle);

        return $rows;
    }
}
