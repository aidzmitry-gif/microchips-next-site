<?php

namespace Tests\Feature;

use App\Events\SiteContentChanged;
use App\Jobs\RevalidateNextSite;
use App\Models\Category;
use App\Models\Product;
use App\Models\Site;
use App\Models\SiteCategory;
use App\Models\SiteCommercialFact;
use App\Models\SitePage;
use App\Models\SiteProduct;
use App\Models\SiteRedirect;
use App\Models\SiteSeo;
use App\Models\SiteUrl;
use App\Models\SiteUrlAlternate;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Bus;
use Illuminate\Support\Facades\Event;
use Tests\TestCase;

class SiteContentChangedTest extends TestCase
{
    use RefreshDatabase;

    public function test_saving_a_commercial_fact_revalidates_warranty_and_legacy_warranty_routes(): void
    {
        Event::fake([SiteContentChanged::class]);
        $site = $this->site();

        SiteCommercialFact::create([
            'site_id' => $site->id,
            'locale' => 'ru-BY',
            'key' => 'warranty_terms',
            'value' => 'Проверяемые условия гарантии.',
        ]);

        Event::assertDispatched(SiteContentChanged::class, function (SiteContentChanged $event) use ($site): bool {
            return $event->site->is($site)
                && $event->paths === ['/', '/contacts', '/delivery', '/payment', '/warranty', '/warranty-and-documents', '/sitemap.xml'];
        });
    }

    public function test_saving_a_site_page_dispatches_site_content_changed_falling_back_to_root_path(): void
    {
        Event::fake([SiteContentChanged::class]);
        $site = $this->site();

        $page = SitePage::create([
            'site_id' => $site->id,
            'locale' => 'ru-BY',
            'slug' => 'delivery',
            'title' => 'Доставка',
            'h1' => 'Доставка',
            'content' => 'Текст',
            'is_published' => true,
        ]);

        Event::assertDispatched(SiteContentChanged::class, function (SiteContentChanged $event) use ($site, $page) {
            return $event->site->is($site) && $event->paths === ['/'] && $page->exists;
        });
    }

    public function test_saving_a_site_page_dispatches_site_content_changed_with_its_matching_site_urls(): void
    {
        Event::fake([SiteContentChanged::class]);
        $site = $this->site();

        $page = SitePage::create([
            'site_id' => $site->id,
            'locale' => 'ru-BY',
            'slug' => 'delivery',
            'title' => 'Доставка',
            'h1' => 'Доставка',
            'content' => 'Текст',
            'is_published' => true,
        ]);
        SiteUrl::create([
            'site_id' => $site->id,
            'path' => '/delivery',
            'locale' => 'ru-BY',
            'target_type' => 'page',
            'target_id' => $page->id,
        ]);

        $page->update(['title' => 'Доставка (обновлено)']);

        Event::assertDispatched(SiteContentChanged::class, function (SiteContentChanged $event) use ($site) {
            return $event->site->is($site) && $event->paths === ['/delivery'];
        });
    }

    public function test_saving_a_site_product_dispatches_site_content_changed_with_its_matching_site_urls(): void
    {
        Event::fake([SiteContentChanged::class]);
        $site = $this->site();
        $product = Product::create(['slug' => 'alpha-battery', 'name' => 'Alpha Battery', 'status' => 'active']);

        $siteProduct = SiteProduct::create([
            'site_id' => $site->id,
            'product_id' => $product->id,
            'slug' => 'alpha-battery',
            'is_published' => true,
            'availability' => 'in_stock',
        ]);

        Event::assertDispatched(SiteContentChanged::class, function (SiteContentChanged $event) use ($site) {
            return $event->site->is($site) && $event->paths === ['/catalog'];
        });

        SiteUrl::create([
            'site_id' => $site->id,
            'path' => '/catalog/alpha-battery',
            'locale' => 'ru-BY',
            'target_type' => 'product',
            'target_id' => $siteProduct->id,
        ]);

        $siteProduct->update(['availability' => 'on_request']);

        Event::assertDispatched(SiteContentChanged::class, function (SiteContentChanged $event) use ($site) {
            return $event->site->is($site) && $event->paths === ['/catalog/alpha-battery', '/catalog'];
        });
    }

    public function test_saving_a_site_category_and_its_membership_revalidates_the_category_path(): void
    {
        $site = $this->site();
        $parentCanonical = Category::create(['slug' => 'batteries', 'name' => 'Batteries']);
        $childCanonical = Category::create(['slug' => 'ups', 'name' => 'UPS', 'parent_id' => $parentCanonical->id]);
        $parent = SiteCategory::create([
            'site_id' => $site->id,
            'category_id' => $parentCanonical->id,
            'slug' => 'batteries',
            'name' => 'Batteries',
            'is_published' => true,
        ]);
        $siteCategory = SiteCategory::create([
            'site_id' => $site->id,
            'category_id' => $childCanonical->id,
            'slug' => 'ups',
            'name' => 'UPS',
            'is_published' => true,
        ]);
        SiteUrl::create([
            'site_id' => $site->id,
            'path' => '/catalog/batteries',
            'locale' => 'ru-BY',
            'target_type' => 'category',
            'target_id' => $parent->id,
        ]);
        SiteUrl::create([
            'site_id' => $site->id,
            'path' => '/catalog/ups',
            'locale' => 'ru-BY',
            'target_type' => 'category',
            'target_id' => $siteCategory->id,
        ]);
        $product = Product::create(['slug' => 'beta-battery', 'name' => 'Beta Battery', 'status' => 'active']);
        $siteProduct = SiteProduct::create([
            'site_id' => $site->id,
            'product_id' => $product->id,
            'slug' => 'beta-battery',
            'is_published' => true,
            'availability' => 'in_stock',
        ]);
        SiteUrl::create([
            'site_id' => $site->id,
            'path' => '/catalog/beta-battery',
            'locale' => 'ru-BY',
            'target_type' => 'product',
            'target_id' => $siteProduct->id,
        ]);

        Event::fake([SiteContentChanged::class]);
        $siteCategory->products()->attach($siteProduct->id);

        Event::assertDispatched(SiteContentChanged::class, function (SiteContentChanged $event) use ($site) {
            $paths = $event->paths;
            sort($paths);

            return $event->site->is($site) && $paths === ['/catalog', '/catalog/batteries', '/catalog/ups'];
        });

        Event::fake([SiteContentChanged::class]);
        $siteProduct->update(['availability' => 'on_request']);

        Event::assertDispatched(SiteContentChanged::class, function (SiteContentChanged $event) use ($site) {
            $paths = $event->paths;
            sort($paths);

            return $event->site->is($site) && $paths === [
                '/catalog',
                '/catalog/batteries',
                '/catalog/beta-battery',
                '/catalog/ups',
            ];
        });
    }

    public function test_saving_a_site_url_dispatches_site_content_changed_with_its_own_path(): void
    {
        Event::fake([SiteContentChanged::class]);
        $site = $this->site();

        SiteUrl::create([
            'site_id' => $site->id,
            'path' => '/contacts',
            'locale' => 'ru-BY',
            'target_type' => 'page',
            'target_id' => null,
        ]);

        Event::assertDispatched(SiteContentChanged::class, function (SiteContentChanged $event) use ($site) {
            return $event->site->is($site) && $event->paths === ['/contacts', '/sitemap.xml'];
        });
    }

    public function test_url_rename_and_delete_revalidate_both_cache_surfaces(): void
    {
        $site = $this->site();
        $url = SiteUrl::create([
            'site_id' => $site->id,
            'path' => '/old-contact',
            'locale' => 'ru-BY',
            'target_type' => 'page',
        ]);

        Event::fake([SiteContentChanged::class]);
        $url->update(['path' => '/new-contact']);

        Event::assertDispatched(SiteContentChanged::class, function (SiteContentChanged $event) use ($site) {
            $paths = $event->paths;
            sort($paths);

            return $event->site->is($site) && $paths === ['/new-contact', '/old-contact', '/sitemap.xml'];
        });

        Event::fake([SiteContentChanged::class]);
        $url->delete();

        Event::assertDispatched(SiteContentChanged::class, function (SiteContentChanged $event) use ($site) {
            return $event->site->is($site) && $event->paths === ['/new-contact', '/sitemap.xml'];
        });
    }

    public function test_seo_redirect_and_hreflang_changes_revalidate_their_affected_urls(): void
    {
        $belarus = $this->site();
        $russia = Site::create([
            'key' => 'microchips-ru',
            'domain' => 'microchips.ru',
            'country_code' => 'RU',
            'currency_code' => 'RUB',
            'default_locale' => 'ru-RU',
            'name' => 'Microchips Russia',
            'is_active' => true,
        ]);
        $source = SiteUrl::create(['site_id' => $belarus->id, 'path' => '/battery', 'locale' => 'ru-BY', 'target_type' => 'page', 'target_id' => 7]);
        $target = SiteUrl::create(['site_id' => $russia->id, 'path' => '/battery', 'locale' => 'ru-RU', 'target_type' => 'page', 'target_id' => 9]);

        Event::fake([SiteContentChanged::class]);
        SiteSeo::create(['site_id' => $belarus->id, 'locale' => 'ru-BY', 'resource_type' => 'page', 'resource_id' => 7, 'canonical_path' => '/battery', 'is_indexable' => false]);
        SiteRedirect::create(['site_id' => $belarus->id, 'source_path' => '/old-battery', 'target_path' => '/battery', 'status_code' => 301, 'is_active' => true]);
        SiteUrlAlternate::create(['source_url_id' => $source->id, 'alternate_url_id' => $target->id, 'locale' => 'ru-RU']);

        Event::assertDispatched(SiteContentChanged::class, function (SiteContentChanged $event) use ($belarus) {
            return $event->site->is($belarus) && $event->paths === ['/battery', '/sitemap.xml'];
        });
        Event::assertDispatched(SiteContentChanged::class, function (SiteContentChanged $event) use ($belarus) {
            return $event->site->is($belarus) && $event->paths === ['/old-battery', '/battery', '/sitemap.xml'];
        });
        Event::assertDispatched(SiteContentChanged::class, function (SiteContentChanged $event) use ($russia) {
            return $event->site->is($russia) && $event->paths === ['/battery', '/sitemap.xml'];
        });
    }

    public function test_the_registered_listener_queues_a_revalidate_job_for_the_event_site_and_paths(): void
    {
        Bus::fake();
        $site = $this->site();
        $event = new SiteContentChanged($site, ['/catalog/alpha-battery']);

        foreach (app('events')->getListeners(SiteContentChanged::class) as $listener) {
            $listener($event, [$event]);
        }

        Bus::assertDispatched(RevalidateNextSite::class, function (RevalidateNextSite $job) use ($site) {
            return $job->siteId === $site->id && $job->paths === ['/catalog/alpha-battery'];
        });
    }

    private function site(): Site
    {
        return Site::create([
            'key' => 'microchips-by',
            'domain' => 'microchips.by',
            'country_code' => 'BY',
            'currency_code' => 'BYN',
            'default_locale' => 'ru-BY',
            'name' => 'Microchips Belarus',
            'is_active' => true,
        ]);
    }
}
