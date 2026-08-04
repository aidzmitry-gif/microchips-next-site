<?php

namespace Tests\Feature;

use App\Events\SiteContentChanged;
use App\Models\ImportRun;
use App\Models\Product;
use App\Models\Site;
use App\Models\SiteProduct;
use App\Models\SiteUrl;
use App\Models\StagedImportRecord;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Artisan;
use Illuminate\Support\Facades\Event;
use Tests\TestCase;

class ReclassifyTechnicalAttributesTest extends TestCase
{
    use RefreshDatabase;

    private const SOURCE_KEY = 'Технология';

    private const TARGET_KEY = 'Тип устройства';

    private const VALUE = 'Внешний батарейный модуль для ИБП';

    public function test_dry_run_is_write_free_and_reports_shared_canonical_scope(): void
    {
        [$site, $product] = $this->fixture();
        Event::fake([SiteContentChanged::class]);
        $before = $product->technical_attributes;
        $file = $this->manifest($site, $product, $before);

        $this->artisan('catalog:reclassify-technical-attributes', [
            'site' => $site->key,
            'file' => $file,
        ])->expectsOutputToContain('"mode": "dry_run"')
            ->expectsOutputToContain('shared canonical products table')
            ->assertSuccessful();

        $this->assertSame($before, $product->fresh()->technical_attributes);
        $this->assertDatabaseCount('import_runs', 0);
        $this->assertDatabaseCount('staged_import_records', 0);
        Event::assertNotDispatched(SiteContentChanged::class);
    }

    public function test_apply_moves_only_the_key_audits_the_change_and_revalidates_every_linked_site(): void
    {
        Event::fake([SiteContentChanged::class]);
        [$belarus, $product, $belarusProduct] = $this->fixture();
        $russia = $this->site('microchips-ru', 'RU', 'RUB', 'ru-RU');
        $russiaProduct = SiteProduct::query()->create([
            'site_id' => $russia->id,
            'product_id' => $product->id,
            'slug' => 'apc-surt192rmxlbp',
            'is_published' => false,
            'availability' => 'on_request',
            'price' => null,
        ]);
        SiteUrl::query()->create([
            'site_id' => $russia->id,
            'path' => '/catalog/apc-surt192rmxlbp',
            'locale' => 'ru-RU',
            'target_type' => 'product',
            'target_id' => $russiaProduct->id,
            'is_indexable' => false,
        ]);
        Event::fake([SiteContentChanged::class]);

        $beforeAttributes = $product->fresh()->technical_attributes;
        $file = $this->manifest($belarus, $product, $beforeAttributes, ['microchips-by', 'microchips-ru']);
        $identityBefore = $product->only(['external_id', 'sku', 'mpn', 'manufacturer', 'name', 'slug', 'status']);
        $commercialBefore = [
            $belarusProduct->id => $belarusProduct->fresh()->only(['is_published', 'availability', 'price', 'seo', 'sort_order']),
            $russiaProduct->id => $russiaProduct->fresh()->only(['is_published', 'availability', 'price', 'seo', 'sort_order']),
        ];

        $this->artisan('catalog:reclassify-technical-attributes', [
            'site' => $belarus->key,
            'file' => $file,
            '--apply' => true,
        ])->assertSuccessful();

        $attributes = $product->fresh()->technical_attributes;
        $this->assertArrayNotHasKey(self::SOURCE_KEY, $attributes);
        $this->assertSame(self::VALUE, $attributes[self::TARGET_KEY]);
        $this->assertSame('192 В', $attributes['Номинальное напряжение батареи']);
        $this->assertSame($identityBefore, $product->only(array_keys($identityBefore)));
        $this->assertSame($commercialBefore[$belarusProduct->id], $belarusProduct->fresh()->only(array_keys($commercialBefore[$belarusProduct->id])));
        $this->assertSame($commercialBefore[$russiaProduct->id], $russiaProduct->fresh()->only(array_keys($commercialBefore[$russiaProduct->id])));

        $run = ImportRun::query()->sole();
        $this->assertSame('technical_attribute_reclassification_manifest', $run->source);
        $this->assertSame('completed', $run->status);
        $this->assertSame(1, $run->processed_records);
        $this->assertTrue($run->summary['writes_canonical_product_attributes']);
        $this->assertSame(['microchips-by', 'microchips-ru'], $run->summary['affected_site_keys']);
        $this->assertSame(0, $run->summary['publication_changes']);
        $this->assertSame(0, $run->summary['commercial_changes']);
        $this->assertSame(0, $run->summary['identity_changes']);

        $record = StagedImportRecord::query()->sole();
        $this->assertSame('applied', $record->status);
        $this->assertSame($product->external_id, $record->external_id);
        $this->assertEquals($beforeAttributes, $record->normalized_payload['before_technical_attributes']);
        $this->assertEquals($attributes, $record->normalized_payload['after_technical_attributes']);
        $this->assertSame(0, $record->publication_snapshot['publication_changes']);
        $this->assertTrue($record->publication_snapshot['canonical_product_attribute_change']);

        Event::assertDispatchedTimes(SiteContentChanged::class, 2);
        Event::assertDispatched(SiteContentChanged::class, fn (SiteContentChanged $event): bool => $event->site->is($belarus)
            && in_array('/catalog/apc-surt192rmxlbp', $event->paths, true)
            && in_array('/catalog', $event->paths, true)
            && in_array('/sitemap.xml', $event->paths, true));
        Event::assertDispatched(SiteContentChanged::class, fn (SiteContentChanged $event): bool => $event->site->is($russia)
            && in_array('/catalog/apc-surt192rmxlbp', $event->paths, true));

        $this->assertSame(0, Artisan::call('catalog:reclassify-technical-attributes', [
            'site' => $belarus->key,
            'file' => $file,
        ]));
        $output = Artisan::output();
        $this->assertStringContainsString('"pending": 0', $output);
        $this->assertStringContainsString('"already_applied": 1', $output);
        $this->assertDatabaseCount('import_runs', 1);
        $this->assertDatabaseCount('staged_import_records', 1);
    }

    public function test_any_identity_or_attribute_drift_blocks_the_whole_manifest_without_audit_writes(): void
    {
        [$site, $product] = $this->fixture();
        Event::fake([SiteContentChanged::class]);
        $file = $this->manifest($site, $product, $product->technical_attributes);
        $attributes = $product->technical_attributes;
        $attributes['Монтаж'] = 'Напольный';
        $product->technical_attributes = $attributes;
        $product->save();

        $this->artisan('catalog:reclassify-technical-attributes', [
            'site' => $site->key,
            'file' => $file,
            '--apply' => true,
        ])->expectsOutputToContain('technical attributes drifted')
            ->assertFailed();

        $this->assertSame('Напольный', $product->fresh()->technical_attributes['Монтаж']);
        $this->assertArrayHasKey(self::SOURCE_KEY, $product->technical_attributes);
        $this->assertDatabaseCount('import_runs', 0);
        $this->assertDatabaseCount('staged_import_records', 0);
        Event::assertNotDispatched(SiteContentChanged::class);
    }

    public function test_manifest_cannot_change_the_fact_value_or_overwrite_a_target_key(): void
    {
        [$site, $product] = $this->fixture();
        $before = $product->technical_attributes;
        $after = $before;
        unset($after[self::SOURCE_KEY]);
        $after[self::TARGET_KEY] = 'ИБП';
        $file = $this->writeManifest([
            'schema_version' => 1,
            'site_key' => $site->key,
            'corrections' => [$this->row($product, $before, $after, [$site->key])],
        ]);

        $this->artisan('catalog:reclassify-technical-attributes', [
            'site' => $site->key,
            'file' => $file,
            '--apply' => true,
        ])->expectsOutputToContain('must only move the unchanged source value')
            ->assertFailed();

        $this->assertSame($before, $product->fresh()->technical_attributes);
        $this->assertDatabaseCount('import_runs', 0);
    }

    /** @return array{Site, Product, SiteProduct} */
    private function fixture(): array
    {
        $site = $this->site('microchips-by', 'BY', 'BYN', 'ru-BY');
        $product = Product::query()->create([
            'external_id' => 'КА-00005622',
            'sku' => null,
            'mpn' => 'SURT192RMXLBP',
            'manufacturer' => 'APC',
            'slug' => 'apc-surt192rmxlbp',
            'name' => 'Внешний батарейный модуль APC Smart-UPS RT SURT192RMXLBP',
            'technical_attributes' => [
                'Назначение' => 'Внешний батарейный модуль для APC Smart-UPS RT',
                'Номинальное напряжение батареи' => '192 В',
                'Тип батареи' => 'Свинцово-кислотная',
                'Монтаж' => 'Стоечный',
                'Высота в стойке' => '3U',
                self::SOURCE_KEY => self::VALUE,
            ],
            'status' => 'active',
        ]);
        $siteProduct = SiteProduct::query()->create([
            'site_id' => $site->id,
            'product_id' => $product->id,
            'slug' => 'apc-surt192rmxlbp',
            'is_published' => true,
            'availability' => 'on_request',
            'price' => null,
            'seo' => ['robots' => 'noindex,follow'],
            'sort_order' => 7,
        ]);
        SiteUrl::query()->create([
            'site_id' => $site->id,
            'path' => '/catalog/apc-surt192rmxlbp',
            'locale' => 'ru-BY',
            'target_type' => 'product',
            'target_id' => $siteProduct->id,
            'is_indexable' => false,
        ]);

        return [$site, $product, $siteProduct];
    }

    private function site(string $key, string $country, string $currency, string $locale): Site
    {
        return Site::query()->create([
            'key' => $key,
            'domain' => $key.'.test',
            'country_code' => $country,
            'currency_code' => $currency,
            'default_locale' => $locale,
            'name' => $key,
        ]);
    }

    /** @param array<string, mixed> $before @param list<string> $linkedSiteKeys */
    private function manifest(Site $site, Product $product, array $before, array $linkedSiteKeys = ['microchips-by']): string
    {
        $after = $before;
        unset($after[self::SOURCE_KEY]);
        $after[self::TARGET_KEY] = self::VALUE;

        return $this->writeManifest([
            'schema_version' => 1,
            'site_key' => $site->key,
            'corrections' => [$this->row($product, $before, $after, $linkedSiteKeys)],
        ]);
    }

    /** @param array<string, mixed> $before @param array<string, mixed> $after @param list<string> $linkedSiteKeys
     * @return array<string, mixed>
     */
    private function row(Product $product, array $before, array $after, array $linkedSiteKeys): array
    {
        return [
            'external_id' => $product->external_id,
            'expected_name' => $product->name,
            'expected_manufacturer' => (string) $product->manufacturer,
            'expected_mpn' => (string) $product->mpn,
            'name_evidence_phrase' => 'Внешний батарейный модуль',
            'source_key' => self::SOURCE_KEY,
            'source_value' => self::VALUE,
            'target_key' => self::TARGET_KEY,
            'expected_linked_site_keys' => $linkedSiteKeys,
            'expected_before_attributes' => $before,
            'expected_after_attributes' => $after,
            'evidence_note' => 'Exact product name identifies this fact as a device type, not battery chemistry.',
        ];
    }

    /** @param array<string, mixed> $manifest */
    private function writeManifest(array $manifest): string
    {
        $file = storage_path('framework/testing/reclassify-attributes-'.uniqid().'.json');
        file_put_contents($file, json_encode($manifest, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR));

        return $file;
    }
}
