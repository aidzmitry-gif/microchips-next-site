<?php

namespace App\Console\Commands;

use App\Models\Site;
use App\Models\SitePage;
use App\Models\SiteSeo;
use App\Models\SiteUrl;
use Illuminate\Console\Command;
use Illuminate\Support\Collection;
use Illuminate\Support\Facades\DB;
use RuntimeException;

/**
 * Makes the reviewed RB commercial pages resolvable while keeping every page
 * noindex. This is not a country launch command and never publishes products,
 * categories, a sitemap entry, or a commercial offer.
 */
class PublishCommercialPagesPackage extends Command
{
    protected $signature = 'site:publish-commercial-pages-package
                            {site : Site key}
                            {--apply : Persist the reviewed noindex package}';

    protected $description = 'Publish the reviewed commercial pages as noindex pages after validating their routes and SEO records';

    /** @var list<string> */
    private const SLUGS = ['contacts', 'delivery', 'payment', 'warranty'];

    public function handle(): int
    {
        $site = Site::query()->where('key', $this->argument('site'))->first();
        if ($site === null) {
            $this->components->error('Site was not found.');

            return self::FAILURE;
        }

        try {
            $pages = $this->validatedPages($site);
        } catch (RuntimeException $exception) {
            $this->components->error($exception->getMessage());

            return self::FAILURE;
        }

        $summary = [
            'mode' => $this->option('apply') ? 'apply' : 'dry_run',
            'site_key' => $site->key,
            'locale' => $site->default_locale,
            'pages' => $pages->count(),
            'pages_already_published' => $pages->where('is_published', true)->count(),
            'indexable_urls' => 0,
            'indexable_seo_records' => 0,
            'product_or_category_publication_changed' => false,
        ];

        if ($this->option('apply')) {
            DB::transaction(function () use ($pages): void {
                foreach ($pages as $page) {
                    if (! $page->is_published) {
                        $page->update(['is_published' => true]);
                    }
                }
            });
        }

        $this->line(json_encode($summary, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE));

        return self::SUCCESS;
    }

    /** @return Collection<int, SitePage> */
    private function validatedPages(Site $site): Collection
    {
        $pages = SitePage::query()
            ->where('site_id', $site->id)
            ->where('locale', $site->default_locale)
            ->whereIn('slug', self::SLUGS)
            ->get()
            ->keyBy('slug');

        if ($pages->count() !== count(self::SLUGS)) {
            throw new RuntimeException('Commercial page package is incomplete; no state was changed.');
        }

        foreach (self::SLUGS as $slug) {
            $page = $pages->get($slug);
            $path = '/'.$slug;
            $url = SiteUrl::query()
                ->where('site_id', $site->id)
                ->where('path', $path)
                ->first();
            $seo = SiteSeo::query()
                ->where('site_id', $site->id)
                ->where('locale', $site->default_locale)
                ->where('resource_type', 'page')
                ->where('resource_id', $page->id)
                ->first();

            if ($url === null || $url->target_type !== 'page' || $url->target_id !== $page->id || $url->is_indexable) {
                throw new RuntimeException("Commercial page {$slug} does not have its expected noindex route; no state was changed.");
            }
            if ($seo === null || $seo->canonical_path !== $path || $seo->is_indexable) {
                throw new RuntimeException("Commercial page {$slug} does not have its expected noindex SEO record; no state was changed.");
            }
        }

        return $pages->values();
    }
}
