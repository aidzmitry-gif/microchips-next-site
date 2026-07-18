<?php

namespace Tests\Feature;

use App\Events\SiteContentChanged;
use App\Jobs\RevalidateNextSite;
use App\Models\Product;
use App\Models\Site;
use App\Models\SitePage;
use App\Models\SiteProduct;
use App\Models\SiteUrl;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Bus;
use Illuminate\Support\Facades\Event;
use Tests\TestCase;

class SiteContentChangedTest extends TestCase
{
    use RefreshDatabase;

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
            return $event->site->is($site) && $event->paths === ['/'];
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
            return $event->site->is($site) && $event->paths === ['/catalog/alpha-battery'];
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
            return $event->site->is($site) && $event->paths === ['/contacts'];
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
