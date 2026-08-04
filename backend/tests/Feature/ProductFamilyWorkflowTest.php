<?php

namespace Tests\Feature;

use App\Models\Category;
use App\Models\Product;
use App\Models\ProductDescriptionDraft;
use App\Models\ProductFamily;
use App\Models\Site;
use App\Models\SiteCategory;
use App\Models\SiteLocale;
use App\Models\SiteProduct;
use App\Models\SiteRedirect;
use App\Models\SiteUrl;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class ProductFamilyWorkflowTest extends TestCase
{
    use RefreshDatabase;

    public function test_reviewed_variant_is_selected_on_one_canonical_page_and_removed_from_flat_catalogue(): void
    {
        [$site, $canonical, $variant, $canonicalSiteProduct, $variantSiteProduct, $source] = $this->familyFixture();
        $manifest = $this->manifest($site, $canonical, $variant, $source);
        $file = $this->writeManifest($manifest);

        try {
            $this->artisan('catalog:import-product-families', ['site' => $site->key, 'file' => $file])
                ->expectsOutputToContain('"mode": "dry_run"')
                ->assertSuccessful();
            $this->assertDatabaseCount('product_families', 0);

            $this->artisan('catalog:import-product-families', ['site' => $site->key, 'file' => $file, '--apply' => true])
                ->expectsOutputToContain('"variants": 1')
                ->assertSuccessful();
        } finally {
            @unlink($file);
        }

        $this->assertDatabaseHas('product_families', [
            'site_id' => $site->id,
            'family_key' => 'csb-gp1272',
            'canonical_product_id' => $canonical->id,
            'status' => ProductFamily::STATUS_VERIFIED,
        ]);
        $this->assertDatabaseHas('product_variants', [
            'product_id' => $variant->id,
            'variant_key' => 'f2',
            'is_active' => true,
        ]);
        $this->assertTrue($variantSiteProduct->fresh()->is_published);

        $this->getJson('/api/v1/sites/microchips-by/catalog/products')
            ->assertOk()
            ->assertJsonPath('meta.total', 1)
            ->assertJsonPath('data.0.name', 'Аккумулятор CSB GP1272')
            ->assertJsonMissing(['name' => 'Аккумулятор CSB GP1272 F2']);

        $this->getJson('/api/v1/sites/microchips.by/resolve?path=/catalog/batteries/csb-gp1272')
            ->assertOk()
            ->assertJsonPath('product.name', 'Аккумулятор CSB GP1272')
            ->assertJsonPath('product.variant_group.family_key', 'csb-gp1272')
            ->assertJsonPath('product.variant_group.label', 'Тип вывода')
            ->assertJsonPath('product.variant_group.canonical_label', 'F1 / Faston 187')
            ->assertJsonPath('product.variant_group.canonical_attributes.Тип вывода', 'F1 / Faston 187')
            ->assertJsonPath('product.variant_group.options.0.external_id', 'VAR-1272-F2')
            ->assertJsonPath('product.variant_group.options.0.attributes.Тип вывода', 'F2 / Faston 250');

        $this->assertDatabaseMissing('site_urls', [
            'site_id' => $site->id,
            'target_type' => 'product',
            'target_id' => $variantSiteProduct->id,
        ]);
        $this->assertDatabaseHas('site_urls', [
            'site_id' => $site->id,
            'target_type' => 'product',
            'target_id' => $canonicalSiteProduct->id,
            'is_indexable' => false,
        ]);
    }

    public function test_import_fails_closed_when_a_variant_already_has_a_product_url(): void
    {
        [$site, $canonical, $variant, , $variantSiteProduct, $source] = $this->familyFixture();
        SiteUrl::create([
            'site_id' => $site->id,
            'path' => '/catalog/batteries/csb-gp1272-f2',
            'locale' => 'ru-BY',
            'target_type' => 'product',
            'target_id' => $variantSiteProduct->id,
            'is_indexable' => false,
        ]);
        $file = $this->writeManifest($this->manifest($site, $canonical, $variant, $source));

        try {
            $this->artisan('catalog:import-product-families', ['site' => $site->key, 'file' => $file, '--apply' => true])
                ->expectsOutputToContain('URL set does not exactly match retire_paths')
                ->assertFailed();
        } finally {
            @unlink($file);
        }

        $this->assertDatabaseCount('product_families', 0);
        $this->assertDatabaseCount('product_variants', 0);
    }

    public function test_family_membership_is_scoped_to_one_market(): void
    {
        [$site, $canonical, $variant, , , $source] = $this->familyFixture();
        $ru = Site::create([
            'key' => 'microchips-ru', 'domain' => 'microchips.ru', 'country_code' => 'RU',
            'currency_code' => 'RUB', 'default_locale' => 'ru-RU', 'name' => 'RU', 'is_active' => true,
        ]);
        SiteLocale::create([
            'site_id' => $ru->id, 'locale' => 'ru-RU', 'language' => 'ru',
            'is_default' => true, 'is_enabled' => true,
        ]);
        SiteProduct::create([
            'site_id' => $ru->id, 'product_id' => $variant->id, 'slug' => 'csb-gp1272-f2',
            'is_published' => true, 'availability' => 'on_request',
        ]);
        $file = $this->writeManifest($this->manifest($site, $canonical, $variant, $source));

        try {
            $this->artisan('catalog:import-product-families', ['site' => $site->key, 'file' => $file, '--apply' => true])
                ->assertSuccessful();
        } finally {
            @unlink($file);
        }

        $this->getJson('/api/v1/sites/microchips-ru/catalog/products')
            ->assertOk()
            ->assertJsonPath('meta.total', 1)
            ->assertJsonPath('data.0.name', 'Аккумулятор CSB GP1272 F2');
    }

    public function test_false_family_duplicate_is_collapsed_without_deleting_shared_product(): void
    {
        [$site, $canonical, $variant, , $variantSiteProduct, $source] = $this->familyFixture();
        $manifestFile = $this->writeManifest($this->manifest($site, $canonical, $variant, $source));
        $collapseFile = tempnam(sys_get_temp_dir(), 'family-collapse-');
        if ($collapseFile === false) {
            $this->fail('Cannot create temporary collapse manifest.');
        }
        file_put_contents($collapseFile, "duplicate_external_id,survivor_external_id\n{$variant->external_id},{$canonical->external_id}\n");

        try {
            $this->artisan('catalog:import-product-families', ['site' => $site->key, 'file' => $manifestFile, '--apply' => true])
                ->assertSuccessful();
            $this->artisan('catalog:collapse-family-duplicates', ['site' => $site->key, 'file' => $collapseFile])
                ->assertSuccessful();
            $this->assertDatabaseHas('site_products', ['id' => $variantSiteProduct->id]);
            $this->assertDatabaseHas('product_variants', ['product_id' => $variant->id]);
            $this->artisan('catalog:collapse-family-duplicates', ['site' => $site->key, 'file' => $collapseFile, '--apply' => true])
                ->assertSuccessful();
            $this->artisan('catalog:collapse-family-duplicates', ['site' => $site->key, 'file' => $collapseFile])
                ->assertSuccessful();
        } finally {
            @unlink($manifestFile);
            @unlink($collapseFile);
        }

        $this->assertDatabaseMissing('site_products', ['id' => $variantSiteProduct->id]);
        $this->assertDatabaseMissing('product_variants', ['product_id' => $variant->id]);
        $this->assertDatabaseMissing('product_families', ['canonical_product_id' => $canonical->id, 'site_id' => $site->id]);
        $this->assertDatabaseHas('products', ['id' => $variant->id, 'external_id' => $variant->external_id]);
    }

    public function test_explicit_noindex_variant_path_is_retired_to_the_canonical_family_idempotently(): void
    {
        [$site, $canonical, $variant, , $variantSiteProduct, $source] = $this->familyFixture();
        $legacyPath = '/catalog/batteries/csb-gp1272-f2';
        SiteUrl::create([
            'site_id' => $site->id,
            'path' => $legacyPath,
            'locale' => 'ru-BY',
            'target_type' => 'product',
            'target_id' => $variantSiteProduct->id,
            'is_indexable' => false,
        ]);
        $manifest = $this->manifest($site, $canonical, $variant, $source);
        $manifest['families'][0]['variants'][0]['retire_paths'] = [$legacyPath];
        $file = $this->writeManifest($manifest);

        try {
            $this->artisan('catalog:import-product-families', ['site' => $site->key, 'file' => $file, '--apply' => true])
                ->expectsOutputToContain('"variant_urls_retired": 1')
                ->assertSuccessful();
            $this->artisan('catalog:import-product-families', ['site' => $site->key, 'file' => $file, '--apply' => true])
                ->expectsOutputToContain('"variant_urls_retired": 0')
                ->assertSuccessful();
        } finally {
            @unlink($file);
        }

        $this->assertDatabaseMissing('site_urls', ['site_id' => $site->id, 'path' => $legacyPath]);
        $this->assertDatabaseHas('site_redirects', [
            'site_id' => $site->id,
            'source_path' => $legacyPath,
            'target_path' => '/catalog/batteries/csb-gp1272',
            'status_code' => 301,
            'purpose' => SiteRedirect::PURPOSE_PREVIEW,
            'is_active' => true,
        ]);
        $this->assertSame(1, SiteRedirect::query()->where('site_id', $site->id)->where('source_path', $legacyPath)->count());
    }

    /** @return array{Site, Product, Product, SiteProduct, SiteProduct, string} */
    private function familyFixture(): array
    {
        $site = Site::create([
            'key' => 'microchips-by', 'domain' => 'microchips.by', 'country_code' => 'BY',
            'currency_code' => 'BYN', 'default_locale' => 'ru-BY', 'name' => 'RB', 'is_active' => true,
        ]);
        SiteLocale::create([
            'site_id' => $site->id, 'locale' => 'ru-BY', 'language' => 'ru',
            'is_default' => true, 'is_enabled' => true,
        ]);
        $category = Category::create(['slug' => 'batteries', 'name' => 'Аккумуляторы']);
        $siteCategory = SiteCategory::create([
            'site_id' => $site->id, 'category_id' => $category->id, 'slug' => 'batteries',
            'name' => 'Аккумуляторы', 'is_published' => true,
        ]);
        $canonical = Product::create([
            'external_id' => 'CAN-1272', 'manufacturer' => 'CSB', 'slug' => 'csb-gp1272',
            'name' => 'Аккумулятор CSB GP1272', 'short_description' => 'Проверенное описание.', 'status' => 'active',
        ]);
        $variant = Product::create([
            'external_id' => 'VAR-1272-F2', 'manufacturer' => 'CSB', 'slug' => 'csb-gp1272-f2',
            'name' => 'Аккумулятор CSB GP1272 F2', 'short_description' => 'Проверенное описание варианта.', 'status' => 'active',
        ]);
        $canonicalSiteProduct = SiteProduct::create([
            'site_id' => $site->id, 'product_id' => $canonical->id, 'slug' => 'csb-gp1272',
            'is_published' => true, 'availability' => 'on_request',
        ]);
        $variantSiteProduct = SiteProduct::create([
            'site_id' => $site->id, 'product_id' => $variant->id, 'slug' => 'csb-gp1272-f2',
            'is_published' => false, 'availability' => 'on_request',
        ]);
        $canonicalSiteProduct->categories()->attach($siteCategory->id, ['site_id' => $site->id]);
        SiteUrl::create([
            'site_id' => $site->id, 'path' => '/catalog/batteries/csb-gp1272', 'locale' => 'ru-BY',
            'target_type' => 'product', 'target_id' => $canonicalSiteProduct->id, 'is_indexable' => false,
        ]);
        $source = 'https://csb-battery.example.test/gp1272.pdf';
        foreach ([$canonical, $variant] as $product) {
            $verifiedAttributes = $product->is($canonical)
                ? ['Технология' => 'VRLA AGM', 'Напряжение' => '12 В', 'Тип вывода' => 'F1 / Faston 187']
                : ['Технология' => 'VRLA AGM', 'Напряжение' => '12 В', 'Тип вывода' => 'F2 / Faston 250'];
            ProductDescriptionDraft::create([
                'product_id' => $product->id, 'locale' => 'ru-BY', 'title' => $product->name,
                'content' => $product->short_description,
                'verified_fields' => ['technical_attributes' => $verifiedAttributes],
                'source_urls' => [$source],
                'source_kind' => 'official_manufacturer_datasheet', 'source_tier' => 'primary_manufacturer',
                'source_publisher' => 'CSB', 'manufacturer_primary' => true, 'identity_scope' => 'exact',
                'status' => 'applied',
            ]);
        }

        return [$site, $canonical, $variant, $canonicalSiteProduct, $variantSiteProduct, $source];
    }

    /** @return array<string, mixed> */
    private function manifest(Site $site, Product $canonical, Product $variant, string $source): array
    {
        return [
            'schema_version' => 1,
            'site_key' => $site->key,
            'families' => [[
                'family_key' => 'csb-gp1272',
                'name' => 'CSB GP1272',
                'canonical_external_id' => $canonical->external_id,
                'manufacturer' => 'CSB',
                'model_core' => 'GP1272',
                'selector_label' => 'Тип вывода',
                'canonical_label' => 'F1 / Faston 187',
                'canonical_attributes' => ['Тип вывода' => 'F1 / Faston 187'],
                'source_url' => $source,
                'shared_attributes' => ['Технология' => 'VRLA AGM', 'Напряжение' => '12 В'],
                'variants' => [[
                    'external_id' => $variant->external_id,
                    'variant_key' => 'f2',
                    'label' => 'F2 / Faston 250',
                    'source_url' => $source,
                    'attributes' => ['Тип вывода' => 'F2 / Faston 250'],
                ]],
            ]],
        ];
    }

    /** @param array<string, mixed> $manifest */
    private function writeManifest(array $manifest): string
    {
        $file = tempnam(sys_get_temp_dir(), 'family-manifest-');
        if ($file === false) {
            $this->fail('Cannot create temporary manifest.');
        }
        file_put_contents($file, json_encode($manifest, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE | JSON_THROW_ON_ERROR));

        return $file;
    }
}
