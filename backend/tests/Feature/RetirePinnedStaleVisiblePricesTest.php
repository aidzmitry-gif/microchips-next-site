<?php

namespace Tests\Feature;

use App\Events\SiteContentChanged;
use App\Models\ImportRun;
use App\Models\Product;
use App\Models\Site;
use App\Models\SiteProduct;
use App\Models\SiteProductPriceEvidence;
use App\Models\SiteUrl;
use App\Models\StagedImportRecord;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Carbon;
use Illuminate\Support\Facades\Artisan;
use Illuminate\Support\Facades\Event;
use Tests\TestCase;

class RetirePinnedStaleVisiblePricesTest extends TestCase
{
    use RefreshDatabase;

    /** @var list<string> */
    private array $temporaryFiles = [];

    protected function setUp(): void
    {
        parent::setUp();
        Carbon::setTestNow('2026-07-30 12:00:00 UTC');
    }

    protected function tearDown(): void
    {
        Carbon::setTestNow();
        foreach ($this->temporaryFiles as $file) {
            @unlink($file);
        }
        parent::tearDown();
    }

    public function test_dry_run_exercises_exact_write_path_without_persisting_or_auditing(): void
    {
        [$site, $product, $siteProduct, $evidence, $url] = $this->pricedProduct();
        $manifest = $this->writeManifest($this->retirementManifest($site, $product, $siteProduct, $evidence, $url));

        Event::fake([SiteContentChanged::class]);
        $this->assertSame(0, Artisan::call('catalog:retire-stale-visible-prices', ['site' => $site->key, 'file' => $manifest]));

        $this->assertSame('85.00', $siteProduct->fresh()->price);
        $this->assertTrue($evidence->fresh()->is_current);
        $this->assertDatabaseCount('import_runs', 0);
        $this->assertDatabaseCount('staged_import_records', 0);
        Event::assertNotDispatched(SiteContentChanged::class);
    }

    public function test_apply_retires_only_price_and_exact_current_evidence_with_audit_and_revalidation(): void
    {
        [$site, $product, $siteProduct, $evidence, $url] = $this->pricedProduct();
        $before = $siteProduct->only(['availability', 'is_published', 'seo', 'slug']);
        $urlBefore = $url->only(['path', 'locale', 'is_indexable']);
        $manifest = $this->writeManifest($this->retirementManifest($site, $product, $siteProduct, $evidence, $url));
        $rollback = $manifest.'.rollback.json';
        $this->temporaryFiles[] = $rollback;

        Event::fake([SiteContentChanged::class]);
        $this->artisan('catalog:retire-stale-visible-prices', [
            'site' => $site->key,
            'file' => $manifest,
            '--apply' => true,
            '--rollback-output' => $rollback,
        ])->assertExitCode(0);

        $this->assertNull($siteProduct->fresh()->price);
        $this->assertFalse($evidence->fresh()->is_current);
        $this->assertSame($before, $siteProduct->fresh()->only(['availability', 'is_published', 'seo', 'slug']));
        $this->assertSame($urlBefore, $url->fresh()->only(['path', 'locale', 'is_indexable']));
        $this->assertSame('Panasonic', $product->fresh()->manufacturer);
        $this->assertFileExists($rollback);
        $this->assertSame('rb_stale_visible_price_rollback_v1', json_decode((string) file_get_contents($rollback), true)['schema']);
        $this->assertSame('completed', ImportRun::query()->sole()->status);
        $this->assertSame('retired', StagedImportRecord::query()->sole()->status);
        $this->assertSame(0, ImportRun::query()->sole()->summary['publication_changes']);
        Event::assertDispatched(SiteContentChanged::class, fn (SiteContentChanged $event): bool => $event->site->is($site)
            && in_array($url->path, $event->paths, true)
            && in_array('/catalog', $event->paths, true)
        );
    }

    public function test_fresh_evidence_price_mismatch_and_hash_drift_fail_closed_without_partial_changes(): void
    {
        [$site, $productA, $siteProductA, $evidenceA, $urlA] = $this->pricedProduct('bitrix:1147', '85.00', 1);
        [$unused, $productB, $siteProductB, $evidenceB, $urlB] = $this->pricedProduct('bitrix:1149', '64.00', 2, $site);
        $manifestData = $this->retirementManifest(
            $site,
            $productA,
            $siteProductA,
            $evidenceA,
            $urlA,
            [[$productB, $siteProductB, $evidenceB, $urlB]]
        );
        $evidenceB->update(['observed_at' => now()->subDays(5)]);
        $manifestData['products'][1]['evidence_observed_at'] = $evidenceB->fresh()->observed_at?->toAtomString();
        $manifestData['products'][1]['evidence_state_sha256'] = $this->hashState($this->evidenceState($evidenceB->fresh()));
        $manifest = $this->writeManifest($manifestData);

        $this->assertSame(1, Artisan::call('catalog:retire-stale-visible-prices', [
            'site' => $site->key, 'file' => $manifest, '--apply' => true,
        ]));
        $this->assertStringContainsString('evidence is not older than 30 full days', Artisan::output());
        $this->assertSame('85.00', $siteProductA->fresh()->price);
        $this->assertSame('64.00', $siteProductB->fresh()->price);
        $this->assertTrue($evidenceA->fresh()->is_current);
        $this->assertDatabaseCount('import_runs', 0);

        $evidenceB->update(['observed_at' => now()->subDays(37)]);
        $manifestData['products'][1]['evidence_observed_at'] = $evidenceB->fresh()->observed_at?->toAtomString();
        $manifestData['products'][1]['evidence_state_sha256'] = $this->hashState($this->evidenceState($evidenceB->fresh()));
        $manifestData['products'][0]['site_product_state_sha256'] = str_repeat('0', 64);
        $manifest = $this->writeManifest($manifestData);
        $this->artisan('catalog:retire-stale-visible-prices', ['site' => $site->key, 'file' => $manifest])
            ->expectsOutputToContain('site_product_state_sha256')
            ->assertExitCode(1);
    }

    public function test_apply_then_default_dry_run_and_applied_rollback_restore_only_exact_fields(): void
    {
        [$site, $product, $siteProduct, $evidence, $url] = $this->pricedProduct();
        $manifest = $this->writeManifest($this->retirementManifest($site, $product, $siteProduct, $evidence, $url));
        $rollback = $manifest.'.rollback.json';
        $this->temporaryFiles[] = $rollback;
        $this->artisan('catalog:retire-stale-visible-prices', [
            'site' => $site->key, 'file' => $manifest, '--apply' => true, '--rollback-output' => $rollback,
        ])->assertExitCode(0);

        $this->artisan('catalog:retire-stale-visible-prices', [
            'site' => $site->key, 'file' => $rollback, '--rollback' => true,
        ])->expectsOutputToContain('"mode": "dry_run"')->assertExitCode(0);
        $this->assertNull($siteProduct->fresh()->price);
        $this->assertFalse($evidence->fresh()->is_current);

        $this->artisan('catalog:retire-stale-visible-prices', [
            'site' => $site->key, 'file' => $rollback, '--rollback' => true, '--apply' => true,
        ])->assertExitCode(0);
        $this->assertSame('85.00', $siteProduct->fresh()->price);
        $this->assertTrue($evidence->fresh()->is_current);
        $this->assertFalse($url->fresh()->is_indexable);
        $this->assertSame(['retired', 'restored'], StagedImportRecord::query()->orderBy('id')->pluck('status')->all());
    }

    public function test_rollback_refuses_state_drift_or_a_new_current_evidence(): void
    {
        [$site, $product, $siteProduct, $evidence, $url] = $this->pricedProduct();
        $manifest = $this->writeManifest($this->retirementManifest($site, $product, $siteProduct, $evidence, $url));
        $rollback = $manifest.'.rollback.json';
        $this->temporaryFiles[] = $rollback;
        $this->artisan('catalog:retire-stale-visible-prices', [
            'site' => $site->key, 'file' => $manifest, '--apply' => true, '--rollback-output' => $rollback,
        ])->assertExitCode(0);

        SiteProductPriceEvidence::create([
            'site_id' => $site->id,
            'site_product_id' => $siteProduct->id,
            'source' => SiteProductPriceEvidence::SOURCE_ONE_C_X2,
            'source_price' => '50.0000',
            'multiplier' => '2.0000',
            'calculated_price' => '100.00',
            'currency' => 'BYN',
            'source_reference' => '1c://fresh',
            'observed_at' => now(),
            'evidence_key' => hash('sha256', 'fresh-new-evidence'),
            'is_current' => true,
        ]);
        $this->artisan('catalog:retire-stale-visible-prices', [
            'site' => $site->key, 'file' => $rollback, '--rollback' => true, '--apply' => true,
        ])->expectsOutputToContain('refuses to supersede newer current price evidence')->assertExitCode(1);
        $this->assertNull($siteProduct->fresh()->price);
        $this->assertFalse($evidence->fresh()->is_current);
    }

    /** @return array{Site, Product, SiteProduct, SiteProductPriceEvidence, SiteUrl} */
    private function pricedProduct(
        string $externalId = 'bitrix:1147',
        string $price = '85.00',
        int $suffix = 1,
        ?Site $site = null
    ): array {
        $site ??= Site::create([
            'key' => 'microchips-by',
            'domain' => 'microchips.by',
            'country_code' => 'BY',
            'currency_code' => 'BYN',
            'default_locale' => 'ru-BY',
            'name' => 'Microchips Belarus',
            'is_active' => true,
        ]);
        $product = Product::create([
            'external_id' => $externalId,
            'manufacturer' => 'Panasonic',
            'mpn' => 'LC-P0612P-'.$suffix,
            'slug' => 'panasonic-'.$suffix,
            'name' => 'Panasonic '.$suffix,
            'status' => 'active',
        ]);
        $siteProduct = SiteProduct::create([
            'site_id' => $site->id,
            'product_id' => $product->id,
            'slug' => 'panasonic-'.$suffix,
            'is_published' => true,
            'availability' => 'on_request',
            'price' => $price,
            'seo' => ['unchanged' => true],
        ]);
        $evidence = SiteProductPriceEvidence::create([
            'site_id' => $site->id,
            'site_product_id' => $siteProduct->id,
            'source' => SiteProductPriceEvidence::SOURCE_LEGACY_SITE,
            'source_price' => $price,
            'multiplier' => '1.0000',
            'calculated_price' => $price,
            'currency' => 'BYN',
            'price_type' => 'legacy_public_price',
            'source_reference' => 'bitrix-backup://product/'.$suffix,
            'observed_at' => now()->subDays(37),
            'evidence_key' => hash('sha256', 'price-'.$suffix),
            'is_current' => true,
        ]);
        $url = SiteUrl::create([
            'site_id' => $site->id,
            'path' => '/catalog/industrial-batteries/batteries-ups/panasonic-'.$suffix,
            'locale' => 'ru-BY',
            'target_type' => 'product',
            'target_id' => $siteProduct->id,
            'is_indexable' => false,
        ]);

        return [$site, $product, $siteProduct, $evidence, $url];
    }

    /**
     * @param  list<array{Product, SiteProduct, SiteProductPriceEvidence, SiteUrl}>  $additional
     * @return array<string, mixed>
     */
    private function retirementManifest(
        Site $site,
        Product $product,
        SiteProduct $siteProduct,
        SiteProductPriceEvidence $evidence,
        SiteUrl $url,
        array $additional = []
    ): array {
        $cohort = tempnam(sys_get_temp_dir(), 'rb-wave249a-cohort-');
        if ($cohort === false) {
            $this->fail('Could not create source cohort fixture.');
        }
        file_put_contents($cohort, '{"wave":"249a"}');
        $this->temporaryFiles[] = $cohort;
        $sets = [[$product, $siteProduct, $evidence, $url], ...$additional];

        return [
            'schema' => 'rb_stale_visible_price_retirement_v1',
            'site_key' => $site->key,
            'source_cohort' => ['path' => $cohort, 'sha256' => hash_file('sha256', $cohort)],
            'max_age_days' => 30,
            'products' => array_map(function (array $set): array {
                [$product, $siteProduct, $evidence, $url] = array_map(fn ($model) => $model->fresh(), $set);

                return [
                    'external_id' => $product->external_id,
                    'product_id' => $product->id,
                    'site_product_id' => $siteProduct->id,
                    'price_evidence_id' => $evidence->id,
                    'site_url_id' => $url->id,
                    'path' => $url->path,
                    'visible_price' => $siteProduct->price,
                    'currency' => $evidence->currency,
                    'evidence_observed_at' => $evidence->observed_at?->toAtomString(),
                    'evidence_key' => $evidence->evidence_key,
                    'product_state_sha256' => $this->hashState($this->productState($product)),
                    'site_product_state_sha256' => $this->hashState($this->siteProductState($siteProduct)),
                    'evidence_state_sha256' => $this->hashState($this->evidenceState($evidence)),
                    'url_state_sha256' => $this->hashState($this->urlState($url)),
                ];
            }, $sets),
        ];
    }

    /** @param array<string, mixed> $manifest */
    private function writeManifest(array $manifest): string
    {
        $path = tempnam(sys_get_temp_dir(), 'rb-stale-prices-');
        if ($path === false) {
            $this->fail('Could not create manifest fixture.');
        }
        file_put_contents($path, json_encode($manifest, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES));
        $this->temporaryFiles[] = $path;

        return $path;
    }

    /** @return array<string, mixed> */
    private function productState(Product $product): array
    {
        return [
            'id' => $product->id, 'external_id' => $product->external_id, 'sku' => $product->sku,
            'manufacturer' => $product->manufacturer, 'mpn' => $product->mpn, 'slug' => $product->slug,
            'name' => $product->name, 'short_description' => $product->short_description,
            'technical_attributes' => $product->technical_attributes, 'status' => $product->status,
        ];
    }

    /** @return array<string, mixed> */
    private function siteProductState(SiteProduct $siteProduct): array
    {
        return [
            'id' => $siteProduct->id, 'site_id' => $siteProduct->site_id, 'product_id' => $siteProduct->product_id,
            'slug' => $siteProduct->slug,
            'price' => $siteProduct->price === null ? null : number_format((float) $siteProduct->price, 2, '.', ''),
            'availability' => $siteProduct->availability, 'is_published' => (bool) $siteProduct->is_published,
            'seo' => $siteProduct->seo, 'sort_order' => $siteProduct->sort_order,
        ];
    }

    /** @return array<string, mixed> */
    private function evidenceState(SiteProductPriceEvidence $evidence): array
    {
        return [
            'id' => $evidence->id, 'site_id' => $evidence->site_id, 'site_product_id' => $evidence->site_product_id,
            'source' => $evidence->source, 'source_price' => number_format((float) $evidence->source_price, 4, '.', ''),
            'multiplier' => number_format((float) $evidence->multiplier, 4, '.', ''),
            'calculated_price' => number_format((float) $evidence->calculated_price, 2, '.', ''),
            'currency' => $evidence->currency, 'price_type' => $evidence->price_type,
            'source_external_id' => $evidence->source_external_id, 'source_reference' => $evidence->source_reference,
            'observed_at' => $evidence->observed_at?->toAtomString(), 'evidence_key' => $evidence->evidence_key,
            'evidence' => $evidence->evidence, 'is_current' => (bool) $evidence->is_current,
        ];
    }

    /** @return array<string, mixed> */
    private function urlState(SiteUrl $url): array
    {
        return [
            'id' => $url->id, 'site_id' => $url->site_id, 'path' => $url->path, 'locale' => $url->locale,
            'target_type' => $url->target_type, 'target_id' => $url->target_id, 'is_indexable' => (bool) $url->is_indexable,
        ];
    }

    /** @param array<string, mixed> $state */
    private function hashState(array $state): string
    {
        return hash('sha256', json_encode($this->canonicalize($state), JSON_THROW_ON_ERROR | JSON_UNESCAPED_SLASHES));
    }

    private function canonicalize(mixed $value): mixed
    {
        if (! is_array($value)) {
            return $value;
        }
        if (! array_is_list($value)) {
            ksort($value);
        }
        foreach ($value as $key => $child) {
            $value[$key] = $this->canonicalize($child);
        }

        return $value;
    }
}
