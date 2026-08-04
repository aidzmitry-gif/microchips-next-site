<?php

namespace Tests\Feature;

use App\Domain\Seo\SiteSeoReleaseAuditor;
use App\Models\Product;
use App\Models\Site;
use App\Models\SiteCommercialFact;
use App\Models\SiteContact;
use App\Models\SiteProduct;
use App\Models\SiteProductPriceEvidence;
use App\Models\SiteSeo;
use App\Models\SiteUrl;
use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class SiteSeoPriceFreshnessTest extends TestCase
{
    use RefreshDatabase;

    public function test_fresh_matching_evidence_allows_an_indexable_numeric_price(): void
    {
        [$site, $siteProduct] = $this->productUrl(indexable: true);
        $this->verifiedProfile($site);
        $this->priceEvidence($site, $siteProduct, now()->subDays(30)->addSecond());

        $report = app(SiteSeoReleaseAuditor::class)->audit($site);

        $this->assertTrue($report['passed']);
        $this->assertNotContains('SEO_VISIBLE_PRICE_EVIDENCE_MISSING', $this->issueCodes($report));
        $this->assertNotContains('SEO_VISIBLE_PRICE_EVIDENCE_STALE', $this->issueCodes($report));
    }

    public function test_stale_matching_evidence_blocks_an_indexable_numeric_price(): void
    {
        [$site, $siteProduct] = $this->productUrl(indexable: true);
        $this->verifiedProfile($site);
        $this->priceEvidence($site, $siteProduct, now()->subDays(31));

        $report = app(SiteSeoReleaseAuditor::class)->audit($site);

        $this->assertFalse($report['passed']);
        $this->assertContains('SEO_VISIBLE_PRICE_EVIDENCE_STALE', $this->issueCodes($report));
    }

    public function test_stale_price_on_a_noindex_preview_does_not_block_release(): void
    {
        [$site, $siteProduct] = $this->productUrl(indexable: false);
        $this->priceEvidence($site, $siteProduct, now()->subDays(31));

        $report = app(SiteSeoReleaseAuditor::class)->audit($site);

        $this->assertTrue($report['passed']);
        $this->assertNotContains('SEO_VISIBLE_PRICE_EVIDENCE_STALE', $this->issueCodes($report));
    }

    /** @return array{Site, SiteProduct} */
    private function productUrl(bool $indexable): array
    {
        $site = Site::create([
            'key' => 'microchips-by',
            'domain' => 'microchips.by',
            'country_code' => 'BY',
            'currency_code' => 'BYN',
            'default_locale' => 'ru-BY',
            'name' => 'Microchips Belarus',
            'is_active' => true,
        ]);
        $site->locales()->create([
            'locale' => 'ru-BY',
            'language' => 'ru',
            'is_default' => true,
            'is_enabled' => true,
        ]);
        $product = Product::create(['external_id' => 'PRICE-FRESHNESS-1', 'slug' => 'price-freshness-1', 'name' => 'Price freshness battery', 'status' => 'active']);
        $siteProduct = SiteProduct::create([
            'site_id' => $site->id,
            'product_id' => $product->id,
            'slug' => 'price-freshness-1',
            'is_published' => true,
            'availability' => 'on_request',
            'price' => '20.00',
        ]);
        $path = '/catalog/price-freshness-1';
        SiteUrl::create([
            'site_id' => $site->id,
            'path' => $path,
            'locale' => 'ru-BY',
            'target_type' => 'product',
            'target_id' => $siteProduct->id,
            'is_indexable' => $indexable,
        ]);
        SiteSeo::create([
            'site_id' => $site->id,
            'locale' => 'ru-BY',
            'resource_type' => 'product',
            'resource_id' => $siteProduct->id,
            'canonical_path' => $path,
            'title' => 'Price freshness battery',
            'is_indexable' => $indexable,
        ]);

        return [$site, $siteProduct];
    }

    private function priceEvidence(Site $site, SiteProduct $siteProduct, \DateTimeInterface $observedAt): void
    {
        SiteProductPriceEvidence::create([
            'site_id' => $site->id,
            'site_product_id' => $siteProduct->id,
            'source' => SiteProductPriceEvidence::SOURCE_LEGACY_SITE,
            'source_price' => '20.0000',
            'multiplier' => '1.0000',
            'calculated_price' => '20.00',
            'currency' => 'BYN',
            'price_type' => 'legacy_public_price',
            'source_reference' => 'bitrix-backup://test/element/1',
            'observed_at' => $observedAt,
            'evidence_key' => hash('sha256', 'price-freshness-'.$observedAt->format(DATE_ATOM)),
            'is_current' => true,
        ]);
    }

    private function verifiedProfile(Site $site): void
    {
        $verifier = User::factory()->create(['is_admin' => true]);
        foreach (['legal_entity' => 'Microchips LLC', 'address' => 'Minsk', 'phone' => '+375 29 123 45 67', 'email' => 'sales@example.by'] as $type => $value) {
            $contact = SiteContact::create(['site_id' => $site->id, 'locale' => 'ru-BY', 'type' => $type, 'label' => $type, 'value' => $value]);
            $contact->publish($verifier, 'Verified against source document');
        }
        foreach (['legal_name' => 'Microchips LLC', 'legal_address' => 'Minsk', 'delivery_terms' => 'Delivery terms', 'payment_terms' => 'Payment terms'] as $key => $value) {
            $fact = SiteCommercialFact::create(['site_id' => $site->id, 'locale' => 'ru-BY', 'key' => $key, 'value' => $value]);
            $fact->publish($verifier, 'Verified against source document');
        }
    }

    /** @param array{issues: list<array{code: string}>} $report
     * @return list<string>
     */
    private function issueCodes(array $report): array
    {
        return array_map(fn (array $issue) => $issue['code'], $report['issues']);
    }
}
