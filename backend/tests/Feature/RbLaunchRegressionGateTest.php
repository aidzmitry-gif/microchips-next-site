<?php

namespace Tests\Feature;

use App\Jobs\SyncLeadToBitrix24;
use App\Models\Category;
use App\Models\Product;
use App\Models\Site;
use App\Models\SiteCategory;
use App\Models\SiteCommercialFact;
use App\Models\SiteContact;
use App\Models\SiteProduct;
use App\Models\SiteSeo;
use App\Models\SiteUrl;
use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Queue;
use Tests\TestCase;

/**
 * One fixture-driven regression gate for the Belarus launch slice. It is not
 * a publication test: every URL stays noindex and the real database remains
 * untouched by RefreshDatabase.
 */
class RbLaunchRegressionGateTest extends TestCase
{
    use RefreshDatabase;

    public function test_rb_fixtures_preserve_verified_commercial_data_and_safe_unpublished_catalog_lead_flow(): void
    {
        Queue::fake();
        $site = $this->site();
        $this->importDraftFixtures($site);
        $this->verifyCommercialProfile($site);
        [$category, $siteProduct] = $this->unpublishedProductSlice($site);

        $this->assertDatabaseCount('site_pages', 4);
        $this->assertDatabaseCount('site_contacts', 7);
        $this->assertDatabaseCount('site_commercial_facts', 5);
        $this->assertTrue(SiteContact::query()->published()->count() === 7);
        $this->assertTrue(SiteCommercialFact::query()->published()->count() === 5);
        $this->assertSame(0, SiteUrl::query()->where('is_indexable', true)->count());

        // Draft local pages are neither routable nor leak their profile.
        $this->getJson('/api/v1/sites/microchips.by/resolve?path=/contacts')
            ->assertOk()
            ->assertJsonPath('kind', 'not_found')
            ->assertJsonMissingPath('site.commercialProfile');
        $this->getJson('/api/v1/sites/microchips.by/resolve?path=/catalog/legacy-bitrix-123')
            ->assertOk()
            ->assertJsonPath('kind', 'not_found');

        // A site-scoped category is available to the UI only as noindex;
        // product price and Offer schema are absent while commercial data is
        // still on-request.
        $this->getJson('/api/v1/sites/microchips-by/catalog/products?category='.$category->slug.'&locale=ru-BY')
            ->assertOk()
            ->assertJsonCount(1, 'data')
            ->assertJsonPath('data.0.slug', $siteProduct->slug)
            ->assertJsonPath('data.0.price', null);
        $this->getJson('/api/v1/sites/microchips.by/resolve?path=/catalog/akkumulyatory/fiamm-12fgl120')
            ->assertOk()
            ->assertJsonPath('kind', 'product')
            ->assertJsonPath('seo.isIndexable', false)
            ->assertJsonPath('product.price', null)
            ->assertJsonPath('product.availability', 'on_request')
            ->assertJsonPath('site.commercialProfile.legalName', 'ООО «Аккумуляторные решения», УНП 192766048')
            ->assertJsonPath('seo.schema.@type', 'Product')
            ->assertJsonMissingPath('seo.schema.offers');

        // The local inbox receives a site-bound, locale-bound lead with an
        // absolute URL. No CRM queue is created unless that integration is
        // expressly enabled for this market.
        $this->postJson('/api/v1/leads/quote', [
            'site_key' => $site->key,
            'locale' => 'ru-BY',
            'company' => 'ООО Тестовый заказчик',
            'contact_name' => 'Иван Иванов',
            'email' => 'ivan@example.test',
            'page_url' => 'https://microchips.by/catalog/akkumulyatory/fiamm-12fgl120',
            'cart' => [['name' => 'Fiamm 12FGL120', 'quantity' => 1]],
            'utm' => ['utm_source' => 'rb-regression'],
        ])
            ->assertCreated()
            ->assertJsonPath('status', 'accepted');
        $this->assertDatabaseHas('leads', [
            'site_id' => $site->id,
            'locale' => 'ru-BY',
            'page_url' => 'https://microchips.by/catalog/akkumulyatory/fiamm-12fgl120',
            'status' => 'new',
        ]);
        Queue::assertNotPushed(SyncLeadToBitrix24::class);
    }

    private function site(): Site
    {
        $site = Site::create(['key' => 'microchips-by', 'domain' => 'microchips.by', 'country_code' => 'BY', 'currency_code' => 'BYN', 'default_locale' => 'ru-BY', 'name' => 'Microchips Беларусь', 'is_active' => true]);
        $site->locales()->create(['locale' => 'ru-BY', 'language' => 'ru', 'is_default' => true, 'is_enabled' => true]);

        return $site;
    }

    private function importDraftFixtures(Site $site): void
    {
        $this->artisan('site:import-launch-page-drafts', ['site' => $site->key, 'file' => $this->fixture('rb-launch-page-drafts.json'), '--apply' => true])->assertSuccessful();
        $this->artisan('site:import-commercial-profile-drafts', ['site' => $site->key, 'file' => $this->fixture('rb-commercial-profile-drafts.json'), '--apply' => true])->assertSuccessful();
    }

    private function verifyCommercialProfile(Site $site): void
    {
        $verifier = User::factory()->create(['is_admin' => true]);
        SiteContact::query()->where('site_id', $site->id)->each(fn (SiteContact $contact) => $contact->publish($verifier, 'RB regression fixture verified.'));
        SiteCommercialFact::query()->where('site_id', $site->id)->each(fn (SiteCommercialFact $fact) => $fact->publish($verifier, 'RB regression fixture verified.'));
    }

    /** @return array{SiteCategory, SiteProduct} */
    private function unpublishedProductSlice(Site $site): array
    {
        $canonical = Category::create(['slug' => 'akkumulyatory', 'name' => 'Аккумуляторы']);
        $category = SiteCategory::create(['site_id' => $site->id, 'category_id' => $canonical->id, 'slug' => 'catalog/akkumulyatory', 'name' => 'Аккумуляторы', 'is_published' => true]);
        SiteUrl::create(['site_id' => $site->id, 'path' => '/catalog/akkumulyatory', 'locale' => 'ru-BY', 'target_type' => 'category', 'target_id' => $category->id, 'is_indexable' => false]);
        $product = Product::create(['slug' => 'fiamm-12fgl120', 'name' => 'Аккумулятор Fiamm 12FGL120', 'status' => 'active', 'technical_attributes' => ['technology' => 'AGM', 'capacity' => '120 Ah', 'voltage' => '12 V']]);
        $siteProduct = SiteProduct::create(['site_id' => $site->id, 'product_id' => $product->id, 'slug' => 'fiamm-12fgl120', 'is_published' => true, 'availability' => 'on_request', 'price' => null]);
        $category->products()->attach($siteProduct->id);
        $url = SiteUrl::create(['site_id' => $site->id, 'path' => '/catalog/akkumulyatory/fiamm-12fgl120', 'locale' => 'ru-BY', 'target_type' => 'product', 'target_id' => $siteProduct->id, 'is_indexable' => false]);
        SiteSeo::create(['site_id' => $site->id, 'locale' => 'ru-BY', 'resource_type' => 'product', 'resource_id' => $siteProduct->id, 'canonical_path' => $url->path, 'is_indexable' => false, 'schema' => ['@type' => 'Product', 'offers' => ['@type' => 'Offer', 'price' => '123']]]);

        return [$category, $siteProduct];
    }

    private function fixture(string $name): string
    {
        return dirname(base_path()).'/docs/imports/'.$name;
    }
}
