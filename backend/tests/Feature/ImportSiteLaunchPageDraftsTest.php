<?php

namespace Tests\Feature;

use App\Domain\Sites\SiteResolver;
use App\Models\ImportRun;
use App\Models\Site;
use App\Models\SitePage;
use App\Models\SiteSeo;
use App\Models\SiteUrl;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class ImportSiteLaunchPageDraftsTest extends TestCase
{
    use RefreshDatabase;

    public function test_dry_run_validates_but_does_not_create_a_public_route(): void
    {
        $site = $this->site();
        $this->artisan('site:import-launch-page-drafts', ['site' => $site->key, 'file' => $this->manifestFile()])->assertSuccessful();

        $this->assertDatabaseCount('site_pages', 0);
        $this->assertDatabaseCount('site_urls', 0);
        $this->assertSame('dry_run_complete', ImportRun::query()->sole()->status);
    }

    public function test_apply_creates_hidden_noindex_drafts_and_can_be_reapplied(): void
    {
        $site = $this->site();
        $args = ['site' => $site->key, 'file' => $this->manifestFile(), '--apply' => true];
        $this->artisan('site:import-launch-page-drafts', $args)->assertSuccessful();
        $this->artisan('site:import-launch-page-drafts', $args)->assertSuccessful();

        $page = SitePage::query()->sole();
        $url = SiteUrl::query()->sole();
        $seo = SiteSeo::query()->sole();
        $this->assertFalse($page->is_published);
        $this->assertFalse($url->is_indexable);
        $this->assertFalse($seo->is_indexable);
        $this->assertSame('not_found', (new SiteResolver)->resolvePath($site, '/contacts')['kind']);
        $this->assertSame(1, ImportRun::query()->latest('id')->firstOrFail()->summary['unchanged']);
    }

    public function test_refuses_to_demote_an_existing_published_page_or_route(): void
    {
        $site = $this->site();
        $page = SitePage::create(['site_id' => $site->id, 'locale' => 'ru-BY', 'slug' => 'contacts', 'title' => 'Live', 'h1' => 'Live', 'is_published' => true]);
        SiteUrl::create(['site_id' => $site->id, 'path' => '/contacts', 'locale' => 'ru-BY', 'target_type' => 'page', 'target_id' => $page->id, 'is_indexable' => true]);

        $this->artisan('site:import-launch-page-drafts', ['site' => $site->key, 'file' => $this->manifestFile(), '--apply' => true])->assertFailed();

        $this->assertTrue($page->fresh()->is_published);
        $this->assertTrue(SiteUrl::query()->sole()->is_indexable);
        $this->assertSame('failed', ImportRun::query()->sole()->status);
    }

    public function test_manifest_must_explicitly_request_unpublished_noindex_pages(): void
    {
        $site = $this->site();
        $file = $this->manifestJson(['schema_version' => 1, 'pages' => [[
            'locale' => 'ru-BY', 'slug' => 'contacts', 'path' => '/contacts', 'title' => 'Title', 'h1' => 'H1', 'content' => 'Content', 'description' => 'Description', 'is_published' => true, 'is_indexable' => false,
        ]]]);

        $this->artisan('site:import-launch-page-drafts', ['site' => $site->key, 'file' => $file])->assertFailed();
        $this->assertDatabaseCount('site_pages', 0);
        $this->assertSame('failed', ImportRun::query()->sole()->status);
    }

    private function site(): Site
    {
        $site = Site::create(['key' => 'microchips-by', 'domain' => 'microchips.by', 'country_code' => 'BY', 'currency_code' => 'BYN', 'default_locale' => 'ru-BY', 'name' => 'Microchips Беларусь', 'is_active' => true]);
        $site->locales()->create(['locale' => 'ru-BY', 'language' => 'ru', 'is_default' => true, 'is_enabled' => true]);

        return $site;
    }

    private function manifestFile(): string
    {
        return $this->manifestJson(['schema_version' => 1, 'pages' => [[
            'locale' => 'ru-BY', 'slug' => 'contacts', 'path' => '/contacts', 'title' => 'Контакты', 'h1' => 'Контакты', 'content' => 'Проверяемый черновик.', 'description' => 'Описание черновика.', 'is_published' => false, 'is_indexable' => false,
        ]]]);
    }

    /** @param array<string, mixed> $contents */
    private function manifestJson(array $contents): string
    {
        $file = storage_path('framework/testing/launch-pages-'.uniqid().'.json');
        file_put_contents($file, json_encode($contents, JSON_THROW_ON_ERROR | JSON_UNESCAPED_UNICODE));

        return $file;
    }
}
