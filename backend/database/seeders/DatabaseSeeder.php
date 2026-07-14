<?php

namespace Database\Seeders;

use App\Models\Site;
use App\Models\SiteLocale;
use App\Models\SitePage;
use App\Models\SiteSeo;
use App\Models\SiteUrl;
use App\Models\User;
use Illuminate\Database\Console\Seeds\WithoutModelEvents;
use Illuminate\Database\Seeder;
use Illuminate\Support\Facades\Hash;

class DatabaseSeeder extends Seeder
{
    use WithoutModelEvents;

    /**
     * Seed the application's database.
     */
    public function run(): void
    {
        $siteProfiles = [
            ['key' => 'microchips-by', 'domain' => 'microchips-by.test', 'country_code' => 'BY', 'currency_code' => 'BYN', 'default_locale' => 'ru-BY', 'name' => 'Microchips Беларусь', 'locales' => [['locale' => 'ru-BY', 'language' => 'ru', 'is_default' => true]]],
            ['key' => 'microchips-ru', 'domain' => 'microchips-ru.test', 'country_code' => 'RU', 'currency_code' => 'RUB', 'default_locale' => 'ru-RU', 'name' => 'Microchips Россия', 'locales' => [['locale' => 'ru-RU', 'language' => 'ru', 'is_default' => true]]],
            ['key' => 'microchips-uz', 'domain' => 'microchips-uz.test', 'country_code' => 'UZ', 'currency_code' => 'UZS', 'default_locale' => 'ru-UZ', 'name' => 'Microchips Uzbekistan', 'locales' => [['locale' => 'ru-UZ', 'language' => 'ru', 'is_default' => true], ['locale' => 'uz-UZ', 'language' => 'uz', 'is_default' => false]]],
            ['key' => 'microchips-site-4', 'domain' => 'microchips-site-4.test', 'country_code' => 'KZ', 'currency_code' => 'KZT', 'default_locale' => 'ru-KZ', 'name' => 'Microchips Site 4', 'locales' => [['locale' => 'ru-KZ', 'language' => 'ru', 'is_default' => true]]],
        ];

        foreach ($siteProfiles as $profile) {
            $site = Site::query()->updateOrCreate(
                ['key' => $profile['key']],
                collect($profile)->except('locales')->all(),
            );

            foreach ($profile['locales'] as $locale) {
                SiteLocale::query()->updateOrCreate(
                    ['site_id' => $site->id, 'locale' => $locale['locale']],
                    [...$locale, 'site_id' => $site->id, 'is_enabled' => true],
                );
            }

            $page = SitePage::query()->updateOrCreate(
                ['site_id' => $site->id, 'locale' => $site->default_locale, 'slug' => 'home'],
                [
                    'title' => $site->name,
                    'h1' => 'Промышленные аккумуляторы и технические решения',
                    'content' => 'Демо-контент для разработки. Перед запуском замените его подтверждёнными региональными условиями, контактами, документами и экспертными материалами.',
                    'is_published' => true,
                ],
            );

            SiteUrl::query()->updateOrCreate(
                ['site_id' => $site->id, 'path' => '/'],
                ['target_type' => 'page', 'target_id' => $page->id, 'locale' => $site->default_locale, 'is_indexable' => false],
            );

            SiteSeo::query()->updateOrCreate(
                ['site_id' => $site->id, 'locale' => $site->default_locale, 'resource_type' => 'page', 'resource_id' => $page->id],
                ['canonical_path' => '/', 'title' => $site->name, 'description' => null, 'is_indexable' => false],
            );
        }

        User::query()->updateOrCreate(
            ['email' => 'admin@microchips.test'],
            [
                'name' => 'Platform Admin',
                'password' => Hash::make(env('INITIAL_ADMIN_PASSWORD', 'change-me-before-production')),
                'is_admin' => true,
            ],
        );
    }
}
