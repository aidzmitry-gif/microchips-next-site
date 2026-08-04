<?php

namespace Tests\Feature;

use App\Models\Category;
use App\Models\Site;
use App\Models\SiteCategory;
use App\Models\SiteSeo;
use App\Models\SiteUrl;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class ImportSiteCategoryContentTest extends TestCase
{
    use RefreshDatabase;

    public function test_it_updates_only_existing_noindex_category_content_and_is_idempotent(): void
    {
        $site = Site::create([
            'key' => 'microchips-by', 'domain' => 'microchips-by.test',
            'country_code' => 'BY', 'currency_code' => 'BYN',
            'default_locale' => 'ru-BY', 'name' => 'RB', 'is_active' => true,
        ]);
        $category = Category::create(['name' => 'UPS', 'slug' => 'ups']);
        $siteCategory = SiteCategory::create([
            'site_id' => $site->id, 'category_id' => $category->id,
            'external_id' => 'seo:ups-systems', 'slug' => 'catalog/power-systems/ups-systems',
            'name' => 'ИБП', 'is_published' => true,
        ]);
        SiteUrl::create([
            'site_id' => $site->id, 'locale' => 'ru-BY',
            'path' => '/catalog/power-systems/ups-systems',
            'target_type' => 'category', 'target_id' => $siteCategory->id,
            'is_indexable' => false,
        ]);
        $seo = SiteSeo::create([
            'site_id' => $site->id, 'locale' => 'ru-BY',
            'resource_type' => 'category', 'resource_id' => $siteCategory->id,
            'canonical_path' => '/catalog/power-systems/ups-systems',
            'title' => 'ИБП', 'description' => null, 'is_indexable' => false,
        ]);
        $file = tempnam(sys_get_temp_dir(), 'category-content-');
        $description = 'Источники бесперебойного питания для серверов, сетевого и промышленного оборудования. Подбор выполняется по мощности, топологии и времени автономии.';
        file_put_contents($file, json_encode(['locale' => 'ru-BY', 'categories' => [[
            'external_id' => 'seo:ups-systems',
            'title' => 'Источники бесперебойного питания (ИБП)',
            'description' => $description,
        ]]], JSON_THROW_ON_ERROR));

        try {
            $this->artisan('content:import-site-category-content', [
                'site' => 'microchips-by', 'file' => $file,
            ])->expectsOutputToContain('"updated": 1')->assertSuccessful();
            $this->assertNull($seo->fresh()->description);

            $this->artisan('content:import-site-category-content', [
                'site' => 'microchips-by', 'file' => $file, '--apply' => true,
            ])->expectsOutputToContain('"updated": 1')->assertSuccessful();
            $seo->refresh();
            $this->assertSame($description, $seo->description);
            $this->assertFalse($seo->is_indexable);

            $this->artisan('content:import-site-category-content', [
                'site' => 'microchips-by', 'file' => $file, '--apply' => true,
            ])->expectsOutputToContain('"unchanged": 1')->assertSuccessful();
        } finally {
            @unlink($file);
        }
    }

    public function test_it_rejects_an_indexable_category(): void
    {
        $site = Site::create([
            'key' => 'microchips-by', 'domain' => 'microchips-by.test',
            'country_code' => 'BY', 'currency_code' => 'BYN',
            'default_locale' => 'ru-BY', 'name' => 'RB', 'is_active' => true,
        ]);
        $category = Category::create(['name' => 'UPS', 'slug' => 'ups']);
        $siteCategory = SiteCategory::create([
            'site_id' => $site->id, 'category_id' => $category->id,
            'external_id' => 'seo:ups-systems', 'slug' => 'catalog/ups',
            'name' => 'ИБП', 'is_published' => true,
        ]);
        SiteUrl::create([
            'site_id' => $site->id, 'locale' => 'ru-BY', 'path' => '/catalog/ups',
            'target_type' => 'category', 'target_id' => $siteCategory->id,
            'is_indexable' => true,
        ]);
        SiteSeo::create([
            'site_id' => $site->id, 'locale' => 'ru-BY',
            'resource_type' => 'category', 'resource_id' => $siteCategory->id,
            'canonical_path' => '/catalog/ups', 'title' => 'ИБП',
            'description' => null, 'is_indexable' => true,
        ]);
        $file = tempnam(sys_get_temp_dir(), 'category-content-');
        file_put_contents($file, json_encode(['locale' => 'ru-BY', 'categories' => [[
            'external_id' => 'seo:ups-systems',
            'title' => 'Источники бесперебойного питания (ИБП)',
            'description' => str_repeat('Проверенное описание. ', 8),
        ]]], JSON_THROW_ON_ERROR));

        try {
            $this->artisan('content:import-site-category-content', [
                'site' => 'microchips-by', 'file' => $file,
            ])->expectsOutputToContain('must have an existing noindex URL')->assertFailed();
        } finally {
            @unlink($file);
        }
    }
}
