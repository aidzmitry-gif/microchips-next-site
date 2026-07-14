<?php

namespace Tests\Feature;

use App\Models\Product;
use App\Models\Site;
use App\Models\SitePage;
use App\Models\SiteProduct;
use App\Models\SiteRedirect;
use App\Models\SiteUrl;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class MultiSiteApiTest extends TestCase
{
    use RefreshDatabase;

    public function test_it_resolves_a_site_scoped_page_by_hostname_and_path(): void
    {
        $site = $this->site('microchips-by', 'microchips.by', 'BY', 'BYN', 'ru-BY');
        $site->locales()->create(['locale' => 'ru-BY', 'language' => 'ru', 'is_default' => true, 'is_enabled' => true]);
        $page = SitePage::create([
            'site_id' => $site->id,
            'locale' => 'ru-BY',
            'slug' => 'delivery',
            'title' => 'Доставка в Беларуси',
            'h1' => 'Доставка',
            'content' => 'Подтверждённые условия доставки.',
            'is_published' => true,
        ]);
        SiteUrl::create(['site_id' => $site->id, 'path' => '/delivery', 'locale' => 'ru-BY', 'target_type' => 'page', 'target_id' => $page->id]);

        $this->getJson('/api/v1/sites/microchips.by/resolve?path=/delivery')
            ->assertOk()
            ->assertJsonPath('kind', 'page')
            ->assertJsonPath('site.key', 'microchips-by')
            ->assertJsonPath('page.h1', 'Доставка')
            ->assertJsonPath('seo.canonicalPath', '/delivery');
    }

    public function test_it_returns_a_structured_redirect_instead_of_guessing_a_page(): void
    {
        $site = $this->site('microchips-by', 'microchips.by', 'BY', 'BYN', 'ru-BY');
        SiteRedirect::create(['site_id' => $site->id, 'source_path' => '/legacy-battery', 'target_path' => '/catalog/battery', 'status_code' => 301, 'is_active' => true]);

        $this->getJson('/api/v1/sites/microchips.by/resolve?path=/legacy-battery')
            ->assertOk()
            ->assertJsonPath('kind', 'redirect')
            ->assertJsonPath('redirect.to', '/catalog/battery')
            ->assertJsonPath('redirect.status', 301);
    }

    public function test_catalog_endpoint_never_leaks_products_from_another_site(): void
    {
        $belarus = $this->site('microchips-by', 'microchips.by', 'BY', 'BYN', 'ru-BY');
        $russia = $this->site('microchips-ru', 'microchips.ru', 'RU', 'RUB', 'ru-RU');
        $product = Product::create(['slug' => 'alpha-battery', 'name' => 'Alpha Battery', 'status' => 'active']);

        SiteProduct::create(['site_id' => $belarus->id, 'product_id' => $product->id, 'slug' => 'alpha-battery', 'is_published' => true, 'availability' => 'in_stock']);

        $this->getJson('/api/v1/sites/microchips-ru/catalog/products')
            ->assertOk()
            ->assertJsonCount(0, 'data');

        $this->getJson('/api/v1/sites/microchips-by/catalog/products')
            ->assertOk()
            ->assertJsonCount(1, 'data')
            ->assertJsonPath('data.0.name', 'Alpha Battery');
    }

    public function test_quote_lead_persists_site_locale_utm_page_and_cart_before_sync(): void
    {
        $site = $this->site('microchips-by', 'microchips.by', 'BY', 'BYN', 'ru-BY');

        $this->postJson('/api/v1/leads/quote', [
            'site_key' => 'microchips-by',
            'locale' => 'ru-BY',
            'company' => 'ООО Тест',
            'contact_name' => 'Иван Иванов',
            'email' => 'ivan@example.test',
            'page_url' => 'https://microchips.by/catalog/alpha-battery',
            'cart' => [['sku' => 'ALPHA-01', 'quantity' => 2]],
            'utm' => ['utm_source' => 'google', 'utm_campaign' => 'test'],
        ])
            ->assertCreated()
            ->assertJsonPath('status', 'accepted');

        $this->assertDatabaseHas('leads', [
            'site_id' => $site->id,
            'locale' => 'ru-BY',
            'type' => 'quote',
            'company' => 'ООО Тест',
            'page_url' => 'https://microchips.by/catalog/alpha-battery',
        ]);
    }

    public function test_quote_lead_rejects_the_legacy_prototype_shape(): void
    {
        $this->site('microchips-by', 'microchips.by', 'BY', 'BYN', 'ru-BY');

        $this->postJson('/api/v1/leads/quote', [
            'site_key' => 'microchips-by',
            'name' => 'Иван Иванов',
            'contact' => 'ivan@example.test',
            'requirement' => 'Аккумуляторы для ИБП',
            'page_url' => '/catalog/akkumulyatory/promyshlennye/',
            'cart' => '[]',
            'utm_source' => 'prototype',
        ])
            ->assertUnprocessable()
            ->assertJsonValidationErrors([
                'company',
                'contact_name',
                'email',
                'phone',
                'page_url',
                'cart',
            ]);
    }

    private function site(string $key, string $domain, string $country, string $currency, string $locale): Site
    {
        return Site::create([
            'key' => $key,
            'domain' => $domain,
            'country_code' => $country,
            'currency_code' => $currency,
            'default_locale' => $locale,
            'name' => $key,
            'is_active' => true,
        ]);
    }
}
