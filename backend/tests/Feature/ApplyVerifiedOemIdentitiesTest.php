<?php

namespace Tests\Feature;

use App\Events\SiteContentChanged;
use App\Models\ImportRun;
use App\Models\Product;
use App\Models\Site;
use App\Models\SiteProduct;
use App\Models\SiteSeo;
use App\Models\SiteUrl;
use App\Models\StagedImportRecord;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Artisan;
use Illuminate\Support\Facades\Event;
use Tests\TestCase;

class ApplyVerifiedOemIdentitiesTest extends TestCase
{
    use RefreshDatabase;

    /** @var list<string> */
    private array $temporaryEvidenceFiles = [];

    protected function setUp(): void
    {
        parent::setUp();
        Event::fake([SiteContentChanged::class]);
    }

    protected function tearDown(): void
    {
        foreach ($this->temporaryEvidenceFiles as $file) {
            @unlink($file);
        }

        parent::tearDown();
    }

    public function test_dry_run_then_apply_fills_only_blank_identity_and_is_idempotent(): void
    {
        [$site, $product, $siteProduct] = $this->catalogueProduct();
        $file = $this->manifest();

        try {
            $this->artisan('catalog:apply-verified-oem-identities', ['site' => $site->key, 'file' => $file])
                ->assertSuccessful()
                ->expectsOutputToContain('"mode": "dry_run"');
            $this->assertNull($product->fresh()->manufacturer);
            $this->assertNull($product->fresh()->mpn);
            $this->assertDatabaseCount('import_runs', 0);
            $this->assertDatabaseCount('staged_import_records', 0);

            $beforeSite = $siteProduct->only(['is_published', 'availability', 'price']);
            $beforeProduct = $product->only(['name', 'sku', 'status']);
            $arguments = ['site' => $site->key, 'file' => $file, '--apply' => true];
            $this->artisan('catalog:apply-verified-oem-identities', $arguments)
                ->assertSuccessful()
                ->expectsOutputToContain('"identities_filled": 1');

            $product->refresh();
            $siteProduct->refresh();
            $this->assertSame('Zebra', $product->manufacturer);
            $this->assertSame('P1083277-002', $product->mpn);
            $this->assertSame($beforeProduct, $product->only(['name', 'sku', 'status']));
            $this->assertSame($beforeSite, $siteProduct->only(['is_published', 'availability', 'price']));
            $this->assertDatabaseCount('import_runs', 1);
            $this->assertDatabaseCount('staged_import_records', 1);
            $this->assertSame('reviewed_evidence', StagedImportRecord::query()->sole()->status);
            Event::assertDispatched(SiteContentChanged::class, fn (SiteContentChanged $event): bool => $event->site->is($site));

            $this->artisan('catalog:apply-verified-oem-identities', $arguments)
                ->assertSuccessful()
                ->expectsOutputToContain('"unchanged": 1');
            $this->assertDatabaseCount('import_runs', 1);
            $this->assertDatabaseCount('staged_import_records', 1);
            $this->assertSame('completed', ImportRun::query()->sole()->status);
        } finally {
            @unlink($file);
        }
    }

    public function test_it_blocks_current_name_drift_and_indexable_pages(): void
    {
        [$site, $product] = $this->catalogueProduct();
        $file = $this->manifest(['current_name' => $product->name.' drift']);
        try {
            $this->artisan('catalog:apply-verified-oem-identities', ['site' => $site->key, 'file' => $file, '--apply' => true])
                ->assertFailed();
            $this->assertNull($product->fresh()->manufacturer);
            $this->assertDatabaseCount('import_runs', 0);
        } finally {
            @unlink($file);
        }

        SiteUrl::query()->update(['is_indexable' => true]);
        $file = $this->manifest();
        try {
            $this->artisan('catalog:apply-verified-oem-identities', ['site' => $site->key, 'file' => $file, '--apply' => true])
                ->assertFailed();
            $this->assertNull($product->fresh()->manufacturer);
            $this->assertDatabaseCount('import_runs', 0);
        } finally {
            @unlink($file);
        }
    }

    public function test_it_blocks_an_mpn_collision_without_mutating_evidence_or_products(): void
    {
        [$site, $product] = $this->catalogueProduct();
        Product::query()->create([
            'external_id' => '1c:existing-zebra',
            'name' => 'Existing Zebra battery',
            'slug' => 'existing-zebra',
            'manufacturer' => 'Zebra',
            'mpn' => 'P1083277-002',
            'status' => 'active',
        ]);
        $file = $this->manifest();
        try {
            $this->artisan('catalog:apply-verified-oem-identities', ['site' => $site->key, 'file' => $file, '--apply' => true])
                ->assertFailed();
            $this->assertNull($product->fresh()->manufacturer);
            $this->assertNull($product->fresh()->mpn);
            $this->assertDatabaseCount('import_runs', 0);
            $this->assertDatabaseCount('staged_import_records', 0);
        } finally {
            @unlink($file);
        }
    }

    public function test_it_blocks_non_drafts_and_a_changed_source_snapshot(): void
    {
        [$site, $product] = $this->catalogueProduct();
        $product->update(['status' => 'active']);
        $file = $this->manifest();
        $this->artisan('catalog:apply-verified-oem-identities', ['site' => $site->key, 'file' => $file, '--apply' => true])
            ->assertFailed();
        $this->assertNull($product->fresh()->manufacturer);

        $product->update(['status' => 'draft']);
        $snapshot = $this->temporaryEvidenceFiles[array_key_last($this->temporaryEvidenceFiles) - 1];
        file_put_contents($snapshot, 'source changed after manifest creation');
        $this->artisan('catalog:apply-verified-oem-identities', ['site' => $site->key, 'file' => $file, '--apply' => true])
            ->assertFailed();
        $this->assertNull($product->fresh()->manufacturer);
        $this->assertDatabaseCount('import_runs', 0);
    }

    public function test_it_accepts_a_hash_pinned_authorized_distributor_catalogue_for_identity_only(): void
    {
        [$site, $product, $siteProduct] = $this->catalogueProduct();
        $name = 'Аккумулятор Fiamm FG10121 (AGM, 1.2Ah)';
        $product->update(['name' => $name]);
        $authority = $this->authorityFixture();
        $statement = 'FIAMM Industrial RUS is the official authorized distributor of FIAMM Energy Technology S.p.A.';
        $file = $this->manifest([
            'external_id' => $product->external_id,
            'current_name' => $name,
            'manufacturer' => 'Fiamm',
            'mpn' => 'FG10121',
            'product_type' => 'stationary VRLA battery',
            'source_url' => 'https://fiamm.example.test/catalogue/fg.pdf',
            'source_kind' => 'official_authorized_distributor_catalogue',
            'source_publisher' => 'FIAMM Industrial RUS',
            'authority_url' => 'https://fiamm.example.test/about/authority',
            'authority_snapshot_path' => $authority,
            'authority_snapshot_sha256' => hash_file('sha256', $authority),
            'authority_statement' => $statement,
        ]);

        $beforeSite = $siteProduct->only(['is_published', 'availability', 'price']);
        $this->artisan('catalog:apply-verified-oem-identities', [
            'site' => $site->key, 'file' => $file, '--apply' => true,
        ])->assertSuccessful()->expectsOutputToContain('"identities_filled": 1');

        $this->assertSame('Fiamm', $product->fresh()->manufacturer);
        $this->assertSame('FG10121', $product->fresh()->mpn);
        $this->assertSame($beforeSite, $siteProduct->fresh()->only(['is_published', 'availability', 'price']));
        $this->assertStringContainsString(
            'authorised-distributor catalogue',
            StagedImportRecord::query()->sole()->review_note,
        );
    }

    public function test_it_rejects_unpinned_or_cross_host_distributor_authority(): void
    {
        [$site, $product] = $this->catalogueProduct();
        $name = 'Аккумулятор Fiamm FG10121 (AGM, 1.2Ah)';
        $product->update(['name' => $name]);
        $authority = $this->authorityFixture();
        $base = [
            'external_id' => $product->external_id,
            'current_name' => $name,
            'manufacturer' => 'Fiamm',
            'mpn' => 'FG10121',
            'source_url' => 'https://fiamm.example.test/catalogue/fg.pdf',
            'source_kind' => 'official_authorized_distributor_catalogue',
            'source_publisher' => 'FIAMM Industrial RUS',
            'authority_url' => 'https://other.example.test/about/authority',
            'authority_snapshot_path' => $authority,
            'authority_snapshot_sha256' => hash_file('sha256', $authority),
            'authority_statement' => 'FIAMM Industrial RUS is the official authorized distributor of FIAMM Energy Technology S.p.A.',
        ];
        $file = $this->manifest($base);
        $this->artisan('catalog:apply-verified-oem-identities', [
            'site' => $site->key, 'file' => $file, '--apply' => true,
        ])->assertFailed();

        $base['authority_url'] = 'https://fiamm.example.test/about/authority';
        $file = $this->manifest($base);
        file_put_contents($authority, 'authority proof changed after manifest creation');
        $this->artisan('catalog:apply-verified-oem-identities', [
            'site' => $site->key, 'file' => $file, '--apply' => true,
        ])->assertFailed();

        $this->assertNull($product->fresh()->manufacturer);
        $this->assertDatabaseCount('import_runs', 0);
    }

    public function test_it_fills_only_blank_mpn_on_an_exact_active_1c_noindex_product(): void
    {
        [$site, $product, $siteProduct] = $this->catalogueProduct();
        $name = 'Panasonic BR2032';
        Product::withoutEvents(function () use ($product, $name): void {
            $product->forceFill([
                'external_id' => 'КА-00003142',
                'name' => $name,
                'status' => 'active',
                'manufacturer' => 'Panasonic',
            ])->save();
        });
        $file = $this->manifest([
            'external_id' => 'КА-00003142',
            'current_name' => $name,
            'manufacturer' => 'Panasonic',
            'mpn' => 'BR2032',
            'product_type' => 'primary lithium coin battery',
            'source_url' => 'https://energy.panasonic.com/catalogue/coin-lithium.pdf',
            'source_kind' => 'official_manufacturer_catalogue',
            'source_publisher' => 'Panasonic Energy',
        ], 'active_1c');

        $beforeSite = $siteProduct->only(['is_published', 'availability', 'price']);
        $arguments = ['site' => $site->key, 'file' => $file, '--apply' => true];
        $status = Artisan::call('catalog:apply-verified-oem-identities', $arguments);
        $output = Artisan::output();
        $this->assertSame(0, $status, $output);
        $this->assertStringContainsString('"target_kind": "active_1c"', $output);
        $this->assertStringContainsString('"identities_filled": 1', $output);

        $this->assertSame('Panasonic', $product->fresh()->manufacturer);
        $this->assertSame('BR2032', $product->fresh()->mpn);
        $this->assertSame('active', $product->fresh()->status);
        $this->assertSame($beforeSite, $siteProduct->fresh()->only(['is_published', 'availability', 'price']));
        $this->assertSame('verified_oem_identity_active_1c:microchips-by', ImportRun::query()->sole()->source);
        $this->assertStringContainsString('active 1C product', StagedImportRecord::query()->sole()->review_note);

        $this->artisan('catalog:apply-verified-oem-identities', $arguments)
            ->assertSuccessful()
            ->expectsOutputToContain('"unchanged": 1');
        $this->assertDatabaseCount('import_runs', 1);
    }

    public function test_active_1c_target_rejects_bitrix_drafts_and_unknown_target_kinds(): void
    {
        [$site, $product] = $this->catalogueProduct();
        $file = $this->manifest([], 'active_1c');
        $this->artisan('catalog:apply-verified-oem-identities', [
            'site' => $site->key, 'file' => $file, '--apply' => true,
        ])->assertFailed();

        $file = $this->manifest([], 'untrusted_scope');
        $this->artisan('catalog:apply-verified-oem-identities', [
            'site' => $site->key, 'file' => $file, '--apply' => true,
        ])->assertFailed();

        $this->assertNull($product->fresh()->mpn);
        $this->assertDatabaseCount('import_runs', 0);
    }

    public function test_it_rejects_corrupt_completed_evidence_instead_of_claiming_idempotence(): void
    {
        [$site] = $this->catalogueProduct();
        $file = $this->manifest();
        $arguments = ['site' => $site->key, 'file' => $file, '--apply' => true];
        $this->artisan('catalog:apply-verified-oem-identities', $arguments)->assertSuccessful();
        StagedImportRecord::query()->sole()->update([
            'normalized_payload' => ['evidence_checksum' => str_repeat('0', 64)],
        ]);

        $this->artisan('catalog:apply-verified-oem-identities', $arguments)
            ->expectsOutputToContain('incomplete or does not match')
            ->assertFailed();
        $this->assertDatabaseCount('import_runs', 1);
        $this->assertDatabaseCount('staged_import_records', 1);
    }

    /** @return array{Site,Product,SiteProduct} */
    private function catalogueProduct(): array
    {
        $site = Site::query()->create([
            'key' => 'microchips-by',
            'domain' => 'microchips-by.test',
            'country_code' => 'BY',
            'currency_code' => 'BYN',
            'default_locale' => 'ru-BY',
            'name' => 'RB',
            'is_active' => true,
        ]);
        $product = Product::query()->create([
            'external_id' => 'bitrix:12122',
            'name' => 'Аккумуляторная батарея для мобильного принтера Zebra ZQ300 P1083277-002 2200mAh 7.2V',
            'slug' => 'legacy-bitrix-12122',
            'sku' => null,
            'mpn' => null,
            'manufacturer' => null,
            'status' => 'draft',
        ]);
        $siteProduct = SiteProduct::query()->create([
            'site_id' => $site->id,
            'product_id' => $product->id,
            'slug' => 'legacy-bitrix-12122',
            'is_published' => true,
            'availability' => 'on_request',
            'price' => null,
        ]);
        SiteUrl::query()->create([
            'site_id' => $site->id,
            'path' => '/catalog/industrial-batteries/batteries-industrial/legacy-bitrix-12122',
            'locale' => 'ru-BY',
            'target_type' => 'product',
            'target_id' => $siteProduct->id,
            'is_indexable' => false,
        ]);
        SiteSeo::query()->create([
            'site_id' => $site->id,
            'locale' => 'ru-BY',
            'resource_type' => 'product',
            'resource_id' => $siteProduct->id,
            'canonical_path' => '/catalog/industrial-batteries/batteries-industrial/legacy-bitrix-12122',
            'title' => $product->name,
            'is_indexable' => false,
            'schema' => null,
        ]);

        return [$site, $product, $siteProduct];
    }

    /** @param array<string,mixed> $overrides */
    private function manifest(array $overrides = [], ?string $targetKind = null): string
    {
        $snapshot = tempnam(sys_get_temp_dir(), 'verified-oem-source-');
        file_put_contents($snapshot, 'Pinned first-party Zebra source fixture for P1083277-002.');
        $this->temporaryEvidenceFiles[] = $snapshot;
        $row = array_replace([
            'external_id' => 'bitrix:12122',
            'current_name' => 'Аккумуляторная батарея для мобильного принтера Zebra ZQ300 P1083277-002 2200mAh 7.2V',
            'manufacturer' => 'Zebra',
            'mpn' => 'P1083277-002',
            'product_type' => 'Standard Battery',
            'source_url' => 'https://www.zebra.com/content/dam/zebra_dam/en/guide/corporate/bts-guide-batteries-where-used-hyperlinks-en-us.pdf',
            'source_kind' => 'official_manufacturer_accessory_catalogue',
            'source_publisher' => 'Zebra Technologies',
            'checked_at' => '2026-07-29',
            'source_snapshot_path' => basename($snapshot),
            'source_snapshot_sha256' => hash_file('sha256', $snapshot),
        ], $overrides);
        $file = tempnam(sys_get_temp_dir(), 'verified-oem-identity-');
        $manifest = [
            'schema_version' => 1,
            'site_key' => 'microchips-by',
            'products' => [$row],
        ];
        if ($targetKind !== null) {
            $manifest['target_kind'] = $targetKind;
        }
        file_put_contents($file, json_encode(
            $manifest,
            JSON_THROW_ON_ERROR | JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE,
        ));
        $this->temporaryEvidenceFiles[] = $file;

        return $file;
    }

    private function authorityFixture(): string
    {
        $file = tempnam(sys_get_temp_dir(), 'verified-distributor-authority-');
        file_put_contents(
            $file,
            'FIAMM Industrial RUS is the official authorized distributor of FIAMM Energy Technology S.p.A.',
        );
        $this->temporaryEvidenceFiles[] = $file;

        return $file;
    }
}
