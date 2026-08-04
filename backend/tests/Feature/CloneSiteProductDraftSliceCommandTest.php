<?php

namespace Tests\Feature;

use App\Models\Product;
use App\Models\Site;
use App\Models\SiteContact;
use App\Models\SiteProduct;
use App\Models\SiteUrl;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class CloneSiteProductDraftSliceCommandTest extends TestCase
{
    use RefreshDatabase;

    public function test_it_defaults_to_dry_run_and_requires_an_exact_source_count(): void
    {
        [$source, $target] = $this->sites();
        $this->sourceDraft($source, 'delta-dt-12100', 'source-commercial-url');

        $this->artisan('catalog:clone-site-draft-slice', [
            'source-site' => $source->key,
            'target-site' => $target->key,
            '--expected-count' => 1,
        ])->assertSuccessful();

        $this->assertDatabaseCount('site_products', 1);

        $this->artisan('catalog:clone-site-draft-slice', [
            'source-site' => $source->key,
            'target-site' => $target->key,
            '--expected-count' => 2,
            '--apply' => true,
        ])->assertFailed();

        $this->assertDatabaseCount('site_products', 1);
    }

    public function test_it_clones_identity_only_as_an_idempotent_non_public_target_draft(): void
    {
        [$source, $target] = $this->sites();
        $sourceDraft = $this->sourceDraft($source, 'delta-dt-12100', 'source-commercial-url');
        SiteUrl::create([
            'site_id' => $source->id,
            'path' => '/catalog/source-commercial-url',
            'locale' => 'ru-BY',
            'target_type' => 'product',
            'target_id' => $sourceDraft->id,
            'is_indexable' => true,
        ]);
        SiteContact::create([
            'site_id' => $source->id,
            'locale' => 'ru-BY',
            'type' => 'phone',
            'label' => 'Source phone',
            'value' => '+375 33 347-75-10',
            'is_primary' => true,
            'is_published' => false,
        ]);

        $arguments = [
            'source-site' => $source->key,
            'target-site' => $target->key,
            '--expected-count' => 1,
            '--apply' => true,
        ];

        $this->artisan('catalog:clone-site-draft-slice', $arguments)->assertSuccessful();

        $targetDraft = SiteProduct::query()->where('site_id', $target->id)->sole();
        $this->assertSame($sourceDraft->product_id, $targetDraft->product_id);
        $this->assertNotSame($sourceDraft->slug, $targetDraft->slug);
        $this->assertFalse($targetDraft->is_published);
        $this->assertSame('on_request', $targetDraft->availability);
        $this->assertNull($targetDraft->price);
        $this->assertNull($targetDraft->seo);
        $this->assertSame(0, $targetDraft->sort_order);
        $this->assertDatabaseMissing('site_urls', ['site_id' => $target->id]);
        $this->assertDatabaseMissing('site_contacts', ['site_id' => $target->id]);

        // A repeat must not overwrite target-market commercial decisions that
        // an operator may have added after the first draft preparation.
        $targetDraft->update([
            'availability' => 'in_stock',
            'price' => '999.00',
            'seo' => ['title' => 'Target market decision'],
            'sort_order' => 7,
        ]);
        $this->artisan('catalog:clone-site-draft-slice', $arguments)->assertSuccessful();
        $this->assertDatabaseCount('site_products', 2);
        $this->assertDatabaseMissing('site_products', ['site_id' => $target->id, 'is_published' => true]);
        $this->assertDatabaseHas('site_products', [
            'id' => $targetDraft->id,
            'availability' => 'in_stock',
            'price' => '999.00',
            'sort_order' => 7,
        ]);
        $this->assertSame(['title' => 'Target market decision'], $targetDraft->fresh()->seo);
    }

    private function sourceDraft(Site $site, string $productSlug, string $siteSlug): SiteProduct
    {
        $product = Product::create([
            'external_id' => "1c-{$productSlug}",
            'sku' => 'DT-12100',
            'mpn' => 'DT12100',
            'manufacturer' => 'Delta',
            'slug' => $productSlug,
            'name' => 'Delta DT 12100',
            'status' => 'active',
        ]);

        return SiteProduct::create([
            'site_id' => $site->id,
            'product_id' => $product->id,
            'slug' => $siteSlug,
            'is_published' => false,
            'availability' => 'in_stock',
            'price' => '1000.00',
            'seo' => ['title' => 'Do not copy this regional SEO'],
            'sort_order' => 99,
        ]);
    }

    /** @return array{Site, Site} */
    private function sites(): array
    {
        return [
            Site::create([
                'key' => 'microchips-by',
                'domain' => 'microchips.by',
                'country_code' => 'BY',
                'currency_code' => 'BYN',
                'default_locale' => 'ru-BY',
                'name' => 'Microchips Belarus',
                'is_active' => true,
            ]),
            Site::create([
                'key' => 'microchips-ru',
                'domain' => 'microchips.ru',
                'country_code' => 'RU',
                'currency_code' => 'RUB',
                'default_locale' => 'ru-RU',
                'name' => 'Microchips Russia',
                'is_active' => true,
            ]),
        ];
    }
}
