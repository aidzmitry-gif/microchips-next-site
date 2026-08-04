<?php

namespace Tests\Feature;

use App\Events\SiteContentChanged;
use App\Models\ImportRun;
use App\Models\Product;
use App\Models\ProductMedia;
use App\Models\Site;
use App\Models\SiteCommercialFact;
use App\Models\SiteContact;
use App\Models\SitePage;
use App\Models\SiteProduct;
use App\Models\SiteProductPriceEvidence;
use App\Models\SiteSeo;
use App\Models\SiteUrl;
use App\Models\StagedImportRecord;
use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Event;
use Illuminate\Support\Facades\Storage;
use Tests\TestCase;

class ReleasePinnedProductCohortTest extends TestCase
{
    use RefreshDatabase;

    /** @var list<string> */
    private array $temporaryFiles = [];

    protected function setUp(): void
    {
        parent::setUp();
        Storage::fake('public');
    }

    protected function tearDown(): void
    {
        foreach ($this->temporaryFiles as $file) {
            @unlink($file);
        }
        parent::tearDown();
    }

    public function test_dry_run_exercises_release_audit_without_persisting_or_writing_audit_rows(): void
    {
        [$site, $product, $siteProduct, $url, $seo, $media] = $this->releaseReadyProduct();
        $manifest = $this->writeManifest($this->releaseManifest($site, $product, $siteProduct, $url, $seo, $media));

        Event::fake([SiteContentChanged::class]);
        $this->artisan('seo:release-product-cohort', ['site' => $site->key, 'file' => $manifest])
            ->expectsOutputToContain('"mode": "dry_run"')
            ->assertExitCode(0);

        $this->assertFalse($url->fresh()->is_indexable);
        $this->assertFalse($seo->fresh()->is_indexable);
        $this->assertDatabaseCount('import_runs', 0);
        $this->assertDatabaseCount('staged_import_records', 0);
        Event::assertNotDispatched(SiteContentChanged::class);
    }

    public function test_apply_is_atomic_writes_rollback_audit_and_one_revalidation_event(): void
    {
        [$site, $product, $siteProduct, $url, $seo, $media] = $this->releaseReadyProduct();
        $manifest = $this->writeManifest($this->releaseManifest($site, $product, $siteProduct, $url, $seo, $media));
        $rollback = $manifest.'.rollback-output.json';
        $this->temporaryFiles[] = $rollback;

        Event::fake([SiteContentChanged::class]);
        $this->artisan('seo:release-product-cohort', [
            'site' => $site->key,
            'file' => $manifest,
            '--apply' => true,
            '--rollback-output' => $rollback,
        ])->assertExitCode(0);

        $this->assertTrue($url->fresh()->is_indexable);
        $this->assertTrue($seo->fresh()->is_indexable);
        $this->assertFileExists($rollback);
        $this->assertSame('rb_product_indexability_rollback_v1', json_decode((string) file_get_contents($rollback), true)['schema']);
        $this->assertSame('completed', ImportRun::query()->sole()->status);
        $this->assertSame('released_indexable', StagedImportRecord::query()->sole()->status);
        Event::assertDispatched(SiteContentChanged::class, fn (SiteContentChanged $event): bool => $event->site->is($site) && in_array($url->path, $event->paths, true) && in_array('/sitemap.xml', $event->paths, true)
        );
    }

    public function test_stale_visible_price_is_refused_by_shared_auditor_and_entire_release_rolls_back(): void
    {
        [$site, $product, $siteProduct, $url, $seo, $media] = $this->releaseReadyProduct(price: '20.00');
        SiteProductPriceEvidence::create([
            'site_id' => $site->id,
            'site_product_id' => $siteProduct->id,
            'source' => SiteProductPriceEvidence::SOURCE_LEGACY_SITE,
            'source_price' => '20.0000',
            'multiplier' => '1.0000',
            'calculated_price' => '20.00',
            'currency' => 'BYN',
            'price_type' => 'legacy_public_price',
            'source_reference' => 'bitrix-backup://test/1',
            'observed_at' => now()->subDays(31),
            'evidence_key' => hash('sha256', 'stale-release-price'),
            'is_current' => true,
        ]);
        $manifest = $this->writeManifest($this->releaseManifest($site, $product, $siteProduct->fresh(), $url, $seo, $media));

        $this->artisan('seo:release-product-cohort', ['site' => $site->key, 'file' => $manifest, '--apply' => true])
            ->expectsOutputToContain('SEO_VISIBLE_PRICE_EVIDENCE_STALE')
            ->assertExitCode(1);

        $this->assertFalse($url->fresh()->is_indexable);
        $this->assertFalse($seo->fresh()->is_indexable);
        $this->assertDatabaseCount('import_runs', 0);
    }

    public function test_product_release_is_refused_while_root_keeps_global_robots_disallow_active(): void
    {
        [$site, $product, $siteProduct, $url, $seo, $media] = $this->releaseReadyProduct();
        $manifest = $this->writeManifest($this->releaseManifest($site, $product, $siteProduct, $url, $seo, $media));
        SiteUrl::query()->where('site_id', $site->id)->where('path', '/')->update(['is_indexable' => false]);

        $this->artisan('seo:release-product-cohort', ['site' => $site->key, 'file' => $manifest, '--apply' => true])
            ->expectsOutputToContain('robots.txt otherwise disallows the whole site')
            ->assertExitCode(1);

        $this->assertFalse($url->fresh()->is_indexable);
        $this->assertFalse($seo->fresh()->is_indexable);
    }

    public function test_non_verified_media_and_any_manifest_state_drift_are_refused(): void
    {
        [$site, $product, $siteProduct, $url, $seo, $media] = $this->releaseReadyProduct();
        $manifestData = $this->releaseManifest($site, $product, $siteProduct, $url, $seo, $media);
        $media->update(['verification_status' => ProductMedia::STATUS_NEEDS_REVIEW, 'verified_at' => null]);
        $manifest = $this->writeManifest($manifestData);

        $this->artisan('seo:release-product-cohort', ['site' => $site->key, 'file' => $manifest])
            ->expectsOutputToContain('not the current storefront-ready verified asset')
            ->assertExitCode(1);

        $media->update(['verification_status' => ProductMedia::STATUS_VERIFIED, 'verified_at' => now()]);
        $manifestData = $this->releaseManifest($site, $product->fresh(), $siteProduct, $url, $seo, $media->fresh());
        $product->update(['short_description' => str_repeat('Changed source-backed description. ', 8)]);
        $manifest = $this->writeManifest($manifestData);
        $this->artisan('seo:release-product-cohort', ['site' => $site->key, 'file' => $manifest])
            ->expectsOutputToContain('product_state_sha256')
            ->assertExitCode(1);

        $this->assertFalse($url->fresh()->is_indexable);
    }

    public function test_generated_rollback_manifest_restores_only_indexability_and_is_itself_dry_run_by_default(): void
    {
        [$site, $product, $siteProduct, $url, $seo, $media] = $this->releaseReadyProduct();
        $manifest = $this->writeManifest($this->releaseManifest($site, $product, $siteProduct, $url, $seo, $media));
        $rollback = $manifest.'.rollback.json';
        $this->temporaryFiles[] = $rollback;
        $this->artisan('seo:release-product-cohort', [
            'site' => $site->key, 'file' => $manifest, '--apply' => true, '--rollback-output' => $rollback,
        ])->assertExitCode(0);

        $this->artisan('seo:release-product-cohort', [
            'site' => $site->key, 'file' => $rollback, '--rollback' => true,
        ])->expectsOutputToContain('"mode": "dry_run"')->assertExitCode(0);
        $this->assertTrue($url->fresh()->is_indexable);

        $this->artisan('seo:release-product-cohort', [
            'site' => $site->key, 'file' => $rollback, '--rollback' => true, '--apply' => true,
        ])->assertExitCode(0);
        $this->assertFalse($url->fresh()->is_indexable);
        $this->assertFalse($seo->fresh()->is_indexable);
        $this->assertSame(2, ImportRun::query()->count());
        $this->assertSame(['released_indexable', 'restored_noindex'], StagedImportRecord::query()->orderBy('id')->pluck('status')->all());
    }

    public function test_builder_generates_exact_release_hashes_from_strict_wave249a_and_live_records(): void
    {
        [$site, $product, $siteProduct, $url, $seo, $media] = $this->releaseReadyProduct();
        $cohortPath = $this->newNonexistentPath('rb-wave249a-').'.json';
        $outputPath = dirname($cohortPath).DIRECTORY_SEPARATOR.'release-'.bin2hex(random_bytes(5)).'.json';
        $this->temporaryFiles = [...$this->temporaryFiles, $cohortPath, $outputPath];
        $cohort = [
            'schema_version' => 1,
            'wave' => 'wave249a_first_indexable_b2b_cohort',
            'mode' => 'live_database_read_only',
            'site_key' => $site->key,
            'selected' => 1,
            'quality' => [
                'selected_unique_external_ids' => 1, 'selected_unique_identity_pairs' => 1,
                'selected_unique_canonical_paths' => 1, 'selected_with_verified_media' => 1,
                'selected_with_valid_source_provenance' => 1, 'selected_open_conflicts' => 0,
                'selected_stale_or_unpinned_visible_prices' => 0, 'database_mutations' => 0,
            ],
            'records' => [[
                'product_external_id' => $product->external_id,
                'product_id' => (string) $product->id,
                'site_product_id' => (string) $siteProduct->id,
                'canonical_path' => $url->path,
                'verified_media_ids' => json_encode([$media->id], JSON_THROW_ON_ERROR),
                'release_decision' => 'READY_FOR_BOUNDED_INDEXABLE_RELEASE',
            ]],
        ];
        file_put_contents($cohortPath, json_encode($cohort, JSON_THROW_ON_ERROR));

        $this->artisan('seo:build-product-release-manifest', [
            'site' => $site->key, 'cohort' => $cohortPath, 'output' => $outputPath,
        ])->expectsOutputToContain('"database_mutations": 0')->assertExitCode(0);

        $manifest = json_decode((string) file_get_contents($outputPath), true, 512, JSON_THROW_ON_ERROR);
        $this->assertSame(hash_file('sha256', $cohortPath), $manifest['source_cohort_sha256']);
        $this->assertSame($media->id, $manifest['products'][0]['verified_media']['media_id']);
        $this->assertMatchesRegularExpression('/^[a-f0-9]{64}$/', $manifest['root_state_sha256']);
        $this->artisan('seo:release-product-cohort', ['site' => $site->key, 'file' => $outputPath])
            ->expectsOutputToContain('"mode": "dry_run"')->assertExitCode(0);
        $this->assertFalse($url->fresh()->is_indexable);
    }

    /** @return array{Site, Product, SiteProduct, SiteUrl, SiteSeo, ProductMedia} */
    private function releaseReadyProduct(?string $price = null): array
    {
        $site = Site::create([
            'key' => 'microchips-by', 'domain' => 'microchips.by', 'country_code' => 'BY', 'currency_code' => 'BYN',
            'default_locale' => 'ru-BY', 'name' => 'Microchips Belarus', 'is_active' => true,
        ]);
        $site->locales()->create(['locale' => 'ru-BY', 'language' => 'ru', 'is_default' => true, 'is_enabled' => true]);
        $this->verifiedProfile($site);
        $home = SitePage::create([
            'site_id' => $site->id, 'locale' => 'ru-BY', 'slug' => 'home', 'title' => 'Промышленные аккумуляторы',
            'h1' => 'Аккумуляторные решения для бизнеса', 'content' => 'Проверенная главная страница белорусского поставщика.', 'is_published' => true,
        ]);
        SiteUrl::create([
            'site_id' => $site->id, 'path' => '/', 'locale' => 'ru-BY', 'target_type' => 'page', 'target_id' => $home->id, 'is_indexable' => true,
        ]);
        SiteSeo::create([
            'site_id' => $site->id, 'locale' => 'ru-BY', 'resource_type' => 'page', 'resource_id' => $home->id,
            'canonical_path' => '/', 'title' => 'Промышленные аккумуляторы для бизнеса', 'description' => 'Поставка и подбор аккумуляторов.', 'is_indexable' => true,
        ]);
        $product = Product::create([
            'external_id' => 'bitrix:release-1', 'manufacturer' => 'EnerSys', 'mpn' => '12HX25',
            'slug' => 'enersys-12hx25', 'name' => 'EnerSys 12HX25',
            'short_description' => str_repeat('Verified manufacturer-backed technical description. ', 4),
            'technical_attributes' => ['voltage' => '12 V'], 'status' => 'active',
        ]);
        $siteProduct = SiteProduct::create([
            'site_id' => $site->id, 'product_id' => $product->id, 'slug' => 'enersys-12hx25',
            'is_published' => true, 'availability' => 'on_request', 'price' => $price,
        ]);
        $url = SiteUrl::create([
            'site_id' => $site->id, 'path' => '/catalog/ups-batteries/enersys-12hx25', 'locale' => 'ru-BY',
            'target_type' => 'product', 'target_id' => $siteProduct->id, 'is_indexable' => false,
        ]);
        $seo = SiteSeo::create([
            'site_id' => $site->id, 'locale' => 'ru-BY', 'resource_type' => 'product', 'resource_id' => $siteProduct->id,
            'canonical_path' => $url->path, 'title' => 'EnerSys 12HX25', 'description' => 'Verified local product description.',
            'is_indexable' => false, 'schema' => null,
        ]);
        $bytes = 'verified exact image bytes';
        $storagePath = 'products/release/enersys-12hx25.jpg';
        Storage::disk('public')->put($storagePath, $bytes);
        $media = ProductMedia::create([
            'product_id' => $product->id, 'kind' => 'image', 'role' => 'primary',
            'source_page_url' => 'https://www.enersys.com/example/12hx25', 'source_kind' => 'manufacturer_primary',
            'rights_basis' => 'Company-owned licensed manufacturer asset.', 'storage_path' => $storagePath,
            'content_sha256' => hash('sha256', $bytes), 'verification_status' => ProductMedia::STATUS_VERIFIED,
            'verification_note' => 'Exact model and rights verified.', 'verified_at' => now(), 'is_published' => true,
        ]);

        return [$site, $product, $siteProduct, $url, $seo, $media];
    }

    private function verifiedProfile(Site $site): void
    {
        $verifier = User::factory()->create(['is_admin' => true]);
        foreach ([
            'legal_entity' => 'ООО Аккумуляторные решения', 'address' => 'Минск', 'phone' => '+375 (33) 347-75-10',
            'email' => 'order@microchips.by', 'working_hours' => '09:00-17:00',
        ] as $type => $value) {
            $contact = SiteContact::create(['site_id' => $site->id, 'locale' => 'ru-BY', 'type' => $type, 'label' => $type, 'value' => $value]);
            $contact->publish($verifier, 'Verified owner data.');
        }
        foreach ([
            'legal_name' => 'ООО Аккумуляторные решения', 'legal_address' => 'Минск',
            'delivery_terms' => 'По согласованию', 'payment_terms' => 'Безналичная оплата', 'warranty_terms' => 'По документам производителя',
        ] as $key => $value) {
            $fact = SiteCommercialFact::create(['site_id' => $site->id, 'locale' => 'ru-BY', 'key' => $key, 'value' => $value]);
            $fact->publish($verifier, 'Verified owner data.');
        }
    }

    /** @return array<string, mixed> */
    private function releaseManifest(Site $site, Product $product, SiteProduct $siteProduct, SiteUrl $url, SiteSeo $seo, ProductMedia $media): array
    {
        $product = $product->fresh();
        $siteProduct = $siteProduct->fresh();
        $url = $url->fresh();
        $seo = $seo->fresh();
        $media = $media->fresh();

        return [
            'schema' => 'rb_product_indexability_release_v1',
            'site_key' => $site->key,
            'locale' => $site->default_locale,
            'commercial_profile_sha256' => $this->hashState([
                'contacts' => SiteContact::query()->where('site_id', $site->id)->where('locale', $site->default_locale)
                    ->published()->whereNotNull('verified_at')->whereNotNull('verified_by')->orderBy('id')
                    ->get(['id', 'locale', 'type', 'label', 'value', 'is_primary', 'verified_at', 'verified_by', 'verification_note'])->toArray(),
                'facts' => SiteCommercialFact::query()->where('site_id', $site->id)->where('locale', $site->default_locale)
                    ->published()->whereNotNull('verified_at')->whereNotNull('verified_by')->orderBy('id')
                    ->get(['id', 'locale', 'key', 'value', 'verified_at', 'verified_by', 'verification_note'])->toArray(),
            ]),
            'root_state_sha256' => $this->hashState($this->rootState($site)),
            'products' => [[
                'external_id' => $product->external_id,
                'product_id' => $product->id,
                'site_product_id' => $siteProduct->id,
                'site_url_id' => $url->id,
                'site_seo_id' => $seo->id,
                'path' => $url->path,
                'product_state_sha256' => $this->hashState($product->only(['id', 'external_id', 'manufacturer', 'mpn', 'sku', 'name', 'short_description', 'technical_attributes', 'status'])),
                'site_product_state_sha256' => $this->hashState($siteProduct->only(['id', 'site_id', 'product_id', 'slug', 'is_published', 'availability', 'price', 'seo', 'sort_order'])),
                'url_state_sha256' => $this->hashState($url->only(['id', 'site_id', 'path', 'locale', 'target_type', 'target_id', 'is_indexable'])),
                'seo_state_sha256' => $this->hashState($seo->only(['id', 'site_id', 'locale', 'resource_type', 'resource_id', 'canonical_path', 'title', 'description', 'is_indexable', 'schema'])),
                'verified_media' => [
                    'media_id' => $media->id, 'storage_path' => $media->storage_path, 'content_sha256' => $media->content_sha256,
                    'rights_basis' => $media->rights_basis, 'verified_at' => $media->verified_at?->toAtomString(),
                ],
            ]],
        ];
    }

    /** @param array<string, mixed> $manifest */
    private function writeManifest(array $manifest): string
    {
        $path = tempnam(sys_get_temp_dir(), 'rb-release-');
        if ($path === false) {
            $this->fail('Could not create temporary release manifest.');
        }
        $source = $path.'.wave249a.json';
        file_put_contents($source, json_encode(['wave' => 'wave249a_first_indexable_b2b_cohort'], JSON_THROW_ON_ERROR));
        $manifest['source_wave'] = 'wave249a_first_indexable_b2b_cohort';
        $manifest['source_cohort_file'] = basename($source);
        $manifest['source_cohort_sha256'] = hash_file('sha256', $source);
        file_put_contents($path, json_encode($manifest, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES));
        $this->temporaryFiles[] = $path;
        $this->temporaryFiles[] = $source;

        return $path;
    }

    private function newNonexistentPath(string $prefix): string
    {
        $path = tempnam(sys_get_temp_dir(), $prefix);
        if ($path === false) {
            $this->fail('Could not reserve a temporary test path.');
        }
        @unlink($path);

        return $path;
    }

    /** @return array<string, mixed> */
    private function rootState(Site $site): array
    {
        $url = SiteUrl::query()->where('site_id', $site->id)->where('path', '/')->sole();
        $page = SitePage::query()->findOrFail($url->target_id);
        $seo = SiteSeo::query()->where('site_id', $site->id)->where('resource_type', 'page')->where('resource_id', $page->id)->sole();

        return [
            'url' => $url->only(['id', 'site_id', 'path', 'locale', 'target_type', 'target_id', 'is_indexable']),
            'page' => $page->only(['id', 'site_id', 'locale', 'slug', 'title', 'h1', 'content', 'is_published']),
            'seo' => $seo->only(['id', 'site_id', 'locale', 'resource_type', 'resource_id', 'canonical_path', 'title', 'description', 'is_indexable', 'schema']),
        ];
    }

    /** @param array<string, mixed> $state */
    private function hashState(array $state): string
    {
        return hash('sha256', json_encode($this->canonicalize($state), JSON_THROW_ON_ERROR | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES));
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
